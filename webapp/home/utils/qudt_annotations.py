"""
Add QUDT units annotations, where available, to numerical attributes.

This code is based largely on the work of John Porter and the rest of the LTER Units Working Group.

Porter, J.H., O’Brien, M., Frants, M., Earl, S. Martin, M., and Laney, C.
Using a units ontology to annotate pre-existing metadata. Sci Data 12, 304 (2025).
https://doi.org/10.1038/s41597-025-04587-8
"""

import collections

import os
import pandas as pd
import pickle
import re
import uuid

from metapype.eml import names
from metapype.model.node import Node


def add_attribute_ids(eml_node):
    """
    Add a UUID id attribute for each attribute node that doesn't already have an id.
    Caller is responsible for saving the updated model. Returns True iff the model has been modified.
    """
    modified = False
    attribute_nodes = []
    eml_node.find_all_descendants(names.ATTRIBUTE, attribute_nodes)
    for attribute_node in attribute_nodes:
        if not attribute_node.attribute_value('id'):
            attribute_node.add_attribute('id', str(uuid.uuid4()))
            modified = True
    return modified


def convert_special_characters(in_string):
    """Convert Unicode code points like <U+2019> to their actual characters."""
    out_string = in_string
    patterns = [
        (r"<U\+([0-9A-Fa-f]{4})>", r"\\u\1"),
        (r"<U\+([0-9A-Fa-f]{5})>", r"\\U000\1"),
        (r"<U\+([0-9A-Fa-f]{6})>", r"\\U00\1"),
        (r"<U\+([0-9A-Fa-f]{7})>", r"\\U0\1"),
        (r"<U\+([0-9A-Fa-f]{8})>", r"\\U\1"),
        (r"<U\+([0-9A-Fa-f]{1})>", r"\\u000\1"),
        (r"<U\+([0-9A-Fa-f]{2})>", r"\\u00\1"),
        (r"<U\+([0-9A-Fa-f]{3})>", r"\\u0\1")
    ]
    for pattern, replacement in patterns:
        out_string = re.sub(pattern, replacement, out_string)
    out_string = out_string.encode().decode('unicode_escape', errors='ignore')
    return out_string


def add_qudt_annotations(eml_node, overwrite_existing=True):
    """
    Add QUDT unit annotations where available.

    Caller is responsible for saving the updated model. Returns True iff the model has been modified.
    """
    def has_existing_unit_annotation(attribute_node):
        """Check if an annotation with 'hasUnit' exists."""
        annotation_node = attribute_node.find_child(names.ANNOTATION)
        if annotation_node:
            property_uri_node = annotation_node.find_child(names.PROPERTYURI)
            if property_uri_node and 'hasUnit' in (property_uri_node.content or ""):
                return True
        return False

    def remove_existing_unit_annotation(attribute_node):
        """Remove existing unit annotation"""
        annotation_node = attribute_node.find_child(names.ANNOTATION)
        if annotation_node:
            property_uri_node = annotation_node.find_child(names.PROPERTYURI)
            if property_uri_node and 'hasUnit' in (property_uri_node.content or ""):
                attribute_node.remove_child(annotation_node)

    qudt_info_df = pd.read_csv('webapp/static/unitsWithQUDTInfo.csv')
    attribute_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.DATATABLE, names.ATTRIBUTELIST, names.ATTRIBUTE])
    for attribute_node in attribute_nodes:
        unit_text = None
        standard_unit_node = attribute_node.find_descendant(names.STANDARDUNIT)
        if standard_unit_node:
            unit_text = standard_unit_node.content.strip().lower()
        custom_unit_node = attribute_node.find_descendant(names.CUSTOMUNIT)
        if custom_unit_node:
            unit_text = custom_unit_node.content.strip().lower()
        if unit_text:
            my_qudt_info_df = qudt_info_df[
                qudt_info_df["unit"].str.strip().str.lower() == unit_text.lower()
            ]
            my_qudt_info_df = my_qudt_info_df[
                (~my_qudt_info_df["qudtUri"].duplicated()) &
                (my_qudt_info_df["qudtUri"].notna()) &
                (my_qudt_info_df["unit"].notna()) &
                (my_qudt_info_df["unit"] != "NA")
            ]
            if len(my_qudt_info_df) == 1:
                if is_rejected_annotation(attribute_node.id):
                    continue
                if has_existing_unit_annotation(attribute_node) and overwrite_existing:
                    remove_existing_unit_annotation(attribute_node)
                if not has_existing_unit_annotation(attribute_node):
                    annotation_node = Node(names.ANNOTATION)
                    attribute_node.add_child(annotation_node)
                    property_uri_node = Node(names.PROPERTYURI)
                    annotation_node.add_child(property_uri_node)
                    property_uri_node.add_attribute('label', 'has unit')
                    property_uri_node.content = 'https://qudt.org/schema/qudt/hasUnit'
                    value_uri_node = Node(names.VALUEURI)
                    annotation_node.add_child(value_uri_node)
                    value_uri_node.add_attribute('label', my_qudt_info_df.iloc[0]["qudtLabel"].strip())
                    value_uri_node.content = my_qudt_info_df.iloc[0]["qudtUri"]



AvailableAnnotationEntry = collections.namedtuple(
    'AvailableAnnotationEntry',
    [
        "data_table_node_id",
        "attribute_node_id",
        "column_number",
        "column_name",
        "unit_in_metadata",
        "qudt_label",
        "qudt_code",
        "action_link"
    ])

def available_qudt_annotations(eml_node, filename):
    """
    Generate a list of available QUDT annotations. Some may have been entered in the metadata, others may have been removed.
    """
    qudt_info_df = pd.read_csv('webapp/static/unitsWithQUDTInfo.csv')

    data_table_list = []
    data_table_nodes = []
    eml_node.find_all_descendants(names.DATATABLE, data_table_nodes)
    for data_table_node in data_table_nodes:
        entity_name_node = data_table_node.find_child(names.ENTITYNAME)
        if not entity_name_node or not entity_name_node.content:
            continue
        data_table_node_id = data_table_node.id
        data_table_name = entity_name_node.content
        attribute_nodes = []
        data_table_node.find_all_descendants(names.ATTRIBUTE, attribute_nodes)
        column_number = 0

        available_qudt_annotations = []
        for attribute_node in attribute_nodes:
            column_number += 1
            unit_text = None
            standard_unit_node = attribute_node.find_descendant(names.STANDARDUNIT)
            if standard_unit_node:
                unit_text = standard_unit_node.content.strip().lower()
            custom_unit_node = attribute_node.find_descendant(names.CUSTOMUNIT)
            if custom_unit_node:
                unit_text = custom_unit_node.content.strip().lower()
            if unit_text:
                my_qudt_info_df = qudt_info_df[
                    qudt_info_df["unit"].str.strip().str.lower() == unit_text.lower()
                ]
                my_qudt_info_df = my_qudt_info_df[
                    (~my_qudt_info_df["qudtUri"].duplicated()) &
                    (my_qudt_info_df["qudtUri"].notna()) &
                    (my_qudt_info_df["unit"].notna()) &
                    (my_qudt_info_df["unit"] != "NA")
                ]
                if len(my_qudt_info_df) == 1:
                    # if has_existing_unit_annotation(attribute_node):
                    #     remove_existing_unit_annotation(attribute_node)
                    # if not has_existing_unit_annotation(attribute_node):
                    #     pass
                    annotation_exists = False
                    attribute_node_id = attribute_node.id
                    attribute_name_node = attribute_node.find_child(names.ATTRIBUTENAME)
                    column_name = attribute_name_node.content
                    unit_in_metadata = unit_text
                    qudt_label = my_qudt_info_df.iloc[0]["qudtLabel"].strip()
                    qudt_code = my_qudt_info_df.iloc[0]["qudtUri"].replace('http://', 'https://')
                    # Determine if annotation exists in the model
                    annotation_nodes = attribute_node.find_all_children(names.ANNOTATION)
                    for annotation_node in annotation_nodes:
                        property_uri_node = annotation_node.find_child(names.PROPERTYURI)
                        if not property_uri_node:
                            continue
                        if not property_uri_node.attribute_value('label') == 'has unit':
                            continue
                        if not property_uri_node.content in ('http://qudt.org/schema/qudt/hasUnit', 'https://qudt.org/schema/qudt/hasUnit'):
                            continue
                        value_uri_node = annotation_node.find_child(names.VALUEURI)
                        if not value_uri_node:
                            continue
                        if value_uri_node.attribute_value('label') != qudt_label:
                            continue
                        if value_uri_node.content not in (qudt_code, qudt_code.replace('https://', 'http://')):
                            continue
                        annotation_exists = True
                        break
                    if annotation_exists:
                        action_link = f'<a href="/eml/reject_qudt_annotation/{filename}/{annotation_node.id}">Reject</a>'
                    else:
                        action_link = f'<a href="/eml/restore_qudt_annotation/{filename}/{attribute_node_id}">Accept</a>'
                    segments = qudt_code.split('/')
                    qudt_code = f'<a href="{qudt_code}" target="_ezeml_qudt">{segments[-1]}</a>'
                    available_qudt_annotations.append(
                        AvailableAnnotationEntry(data_table_node_id,
                                                 attribute_node_id,
                                                 column_number,
                                                 column_name,
                                                 unit_in_metadata,
                                                 qudt_label,
                                                 qudt_code,
                                                 action_link)
                    )
        data_table_list.append((data_table_name, data_table_node_id, available_qudt_annotations))
    return data_table_list


REJECTED_ANNOTATIONS_FILENAME = '__rejected_annotations__.pkl'
def load_rejected_annotation_ids():
    from webapp.auth.user_data import get_user_folder_name
    # Load the pickle file with the set of attribute IDs for rejected annotations
    user_folder_name = get_user_folder_name()
    user_properties_pathname = os.path.join(user_folder_name, REJECTED_ANNOTATIONS_FILENAME)
    rejected_annotation_ids = set()
    if os.path.exists(user_properties_pathname):
        with open(user_properties_pathname, 'rb') as file:
            rejected_annotation_ids = pickle.load(file)
    return rejected_annotation_ids


def save_rejected_annotation_ids(rejected_annotation_ids):
    from webapp.auth.user_data import get_user_folder_name
    # Save the pickle file with the set of rejected annotation IDs
    user_folder_name = get_user_folder_name()
    user_properties_pathname = os.path.join(user_folder_name, REJECTED_ANNOTATIONS_FILENAME)
    with open(user_properties_pathname, 'wb') as file:
         pickle.dump(rejected_annotation_ids, file)


def set_rejected_annotation(attribute_node_id, reject):
    rejected_annotation_ids = load_rejected_annotation_ids()
    if reject:
        rejected_annotation_ids.add(attribute_node_id)
    else:
        rejected_annotation_ids.discard(attribute_node_id)
    save_rejected_annotation_ids(rejected_annotation_ids)


def is_rejected_annotation(attribute_node_id):
    rejected_annotation_ids = load_rejected_annotation_ids()
    return attribute_node_id in rejected_annotation_ids


def reject_all_qudt_annotations(eml_node, data_table_node_id):
    """
    Reject all QUDT unit annotations for a data table.
    Returns true iff a change was made. Caller is responsible for saving changes.
    """
    data_table_node = Node.get_node_instance(data_table_node_id)
    if not data_table_node:
        return
    annotation_nodes = []
    changed = False
    data_table_node.find_all_descendants(names.ANNOTATION, annotation_nodes)
    for annotation_node in annotation_nodes:
        property_uri_node = annotation_node.find_child(names.PROPERTYURI)
        value_uri_node = annotation_node.find_child(names.VALUEURI)
        if not property_uri_node or not value_uri_node:
            continue
        if (property_uri_node.attribute_value('label') != 'has unit' or
            property_uri_node.content not in ('https://qudt.org/schema/qudt/hasUnit',
                                              'http://qudt.org/schema/qudt/hasUnit')):
            continue
        if ('http://qudt.org/vocab/unit/' not in value_uri_node.content
            and 'https://qudt.org/vocab/unit/' not in value_uri_node.content):
            continue
        # We've got a QUDT unit annotation. Remove it.
        changed = True
        attribute_node = annotation_node.parent
        attribute_node.remove_child(annotation_node)
        Node.delete_node_instance(annotation_node.id)
        set_rejected_annotation(attribute_node.id, True)
    return changed


def restore_all_qudt_annotations(eml_node, data_table_node_id):
    """
    Restore all QUDT unit annotations for a data table.
    Returns true iff a change was made. Caller is responsible for saving changes.
    """
    data_table_node = Node.get_node_instance(data_table_node_id)
    if not data_table_node:
        return
    # Get the attribute node IDs and remove them from the rejected set
    rejected = load_rejected_annotation_ids()
    original_rejected = rejected.copy()
    attribute_nodes = []
    data_table_node.find_all_descendants(names.ATTRIBUTE, attribute_nodes)
    for attribute_node in attribute_nodes:
        rejected.discard(attribute_node.id)
    changed = (rejected != original_rejected)
    if changed:
        save_rejected_annotation_ids(rejected)
        add_qudt_annotations(eml_node)
    return changed

