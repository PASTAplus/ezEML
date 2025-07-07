"""
Add QUDT units annotations, where available, to numerical attributes.

This code is based largely on the work of John Porter and the rest of the LTER Units Working Group.

Porter, J.H., O’Brien, M., Frants, M., Earl, S. Martin, M., and Laney, C.
Using a units ontology to annotate pre-existing metadata. Sci Data 12, 304 (2025).
https://doi.org/10.1038/s41597-025-04587-8
"""

ANNOTATIONS_ACTIONS_FILENAME = '__annotations_actions__.pkl'

import collections

import os
import pandas as pd
import pickle
import re
import uuid

from webapp.auth import user_data
from webapp.home.utils.node_utils import get_unit_text
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


def add_qudt_annotations(eml_node, automatically_add=True, overwrite_existing=False):
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

    def node_matches(annotation_node, qudt_label, qudt_uri):
        property_uri_node = annotation_node.find_child(names.PROPERTYURI)
        value_uri_node = annotation_node.find_child(names.VALUEURI)
        if not property_uri_node or not value_uri_node:
            return False
        if property_uri_node.attribute_value('label') != 'has unit':
            return False
        if property_uri_node.content != 'http://qudt.org/schema/qudt/hasUnit':
            return False
        if value_uri_node.attribute_value('label') != qudt_label:
            return False
        if value_uri_node.content != qudt_uri:
            return False
        return True

    def remove_existing_unit_annotation(attribute_node, qudt_label, qudt_uri):
        """Remove existing unit annotation if it is different from what we're about to add."""
        annotation_node = attribute_node.find_child(names.ANNOTATION)
        if annotation_node:
            property_uri_node = annotation_node.find_child(names.PROPERTYURI)
            if property_uri_node and 'hasUnit' in (property_uri_node.content or ""):
                # See if the existing node is different from what we're about to add.
                if not node_matches(annotation_node, qudt_label, qudt_uri):
                    from webapp.home.log_usage import annotations_actions, log_qudt_annotations_usage
                    log_qudt_annotations_usage(
                        annotations_actions['REMOVE_FROM_EML'],
                        attribute_node)
                    attribute_node.remove_child(annotation_node)

    enable_automatic_qudt_annotations, replace_preexisting_qudt_annotations = user_data.get_qudt_annotations_settings()
    qudt_info_df = pd.read_csv('webapp/static/unitsWithQUDTInfo.csv')
    attribute_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.DATATABLE, names.ATTRIBUTELIST, names.ATTRIBUTE])
    for attribute_node in attribute_nodes:
        unit_text = get_unit_text(attribute_node)
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
                if not enable_automatic_qudt_annotations and not is_accepted_annotation(attribute_node.id):
                    continue
                qudt_label = my_qudt_info_df.iloc[0]["qudtLabel"].strip()
                qudt_uri = my_qudt_info_df.iloc[0]["qudtUri"]
                if has_existing_unit_annotation(attribute_node) and replace_preexisting_qudt_annotations:
                    remove_existing_unit_annotation(attribute_node, qudt_label, qudt_uri)
                if not has_existing_unit_annotation(attribute_node):
                    annotation_node = Node(names.ANNOTATION)
                    attribute_node.add_child(annotation_node)
                    property_uri_node = Node(names.PROPERTYURI)
                    annotation_node.add_child(property_uri_node)
                    property_uri_node.add_attribute('label', 'has unit')
                    property_uri_node.content = 'http://qudt.org/schema/qudt/hasUnit'
                    value_uri_node = Node(names.VALUEURI)
                    annotation_node.add_child(value_uri_node)
                    value_uri_node.add_attribute('label', qudt_label)
                    value_uri_node.content = qudt_uri
                    # Log it
                    from webapp.home.log_usage import annotations_actions, log_qudt_annotations_usage
                    log_qudt_annotations_usage(
                        annotations_actions['ADD_TO_EML'],
                        attribute_node)



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


def is_qudt_annotation(annotation_node):
    """
    Returns (qudt_label, qudt_code) if this is a QUDT annotation.

    If not, returns None.
    """
    property_uri_node = annotation_node.find_child(names.PROPERTYURI)
    if not property_uri_node:
        return None
    if not property_uri_node.attribute_value('label') == 'has unit':
        return None
    if not property_uri_node.content in ('http://qudt.org/schema/qudt/hasUnit', 'https://qudt.org/schema/qudt/hasUnit'):
        return None
    value_uri_node = annotation_node.find_child(names.VALUEURI)
    if not value_uri_node:
        return None
    qudt_label = value_uri_node.attribute_value('label')
    qudt_uri = value_uri_node.content
    if 'http://qudt.org/vocab/unit/' not in qudt_uri and 'https://qudt.org/vocab/unit/' not in qudt_uri:
        return None
    qudt_code = qudt_uri.split('/')[-1]
    return (qudt_label, qudt_code)


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
                    attribute_node_id = attribute_node.id
                    attribute_name_node = attribute_node.find_child(names.ATTRIBUTENAME)
                    column_name = attribute_name_node.content
                    unit_in_metadata = unit_text
                    qudt_label = my_qudt_info_df.iloc[0]["qudtLabel"].strip()
                    qudt_uri = my_qudt_info_df.iloc[0]["qudtUri"]
                    qudt_code = qudt_uri.split('/')[-1]
                    qudt_link = qudt_uri.replace('http://', 'https://')
                    qudt_link = f'<a href="{qudt_link}" target="_ezeml_qudt">{qudt_code}</a>'
                    # Determine if annotation exists in the model
                    annotation_exists = False
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
                        if value_uri_node.content not in qudt_uri and value_uri_node.content not in qudt_uri.replace('https://', 'http://'):
                            continue
                        annotation_exists = True
                        action_link = f'<a href="/eml/reject_qudt_annotation/{filename}/{annotation_node.id}/{qudt_label}/{qudt_code}">Reject</a>'
                        available_qudt_annotations.append(
                            AvailableAnnotationEntry(data_table_node_id,
                                                     attribute_node_id,
                                                     column_number,
                                                     column_name,
                                                     unit_in_metadata,
                                                     qudt_label,
                                                     qudt_link,
                                                     action_link)
                        )
                    if not annotation_exists:
                        action_link = f'<a href="/eml/accept_qudt_annotation/{filename}/{attribute_node_id}/{qudt_label}/{qudt_code}">Accept</a>'
                        available_qudt_annotations.append(
                            AvailableAnnotationEntry(data_table_node_id,
                                                     attribute_node_id,
                                                     column_number,
                                                     column_name,
                                                     unit_in_metadata,
                                                     qudt_label,
                                                     qudt_link,
                                                     action_link)
                        )
        data_table_list.append((data_table_name, data_table_node_id, available_qudt_annotations))
    return data_table_list


def load_annotations_actions():
    from webapp.auth.user_data import get_user_folder_name
    # Load the pickle file with the set of attribute IDs for rejected annotations
    user_folder_name = get_user_folder_name()
    user_properties_pathname = os.path.join(user_folder_name, ANNOTATIONS_ACTIONS_FILENAME)
    rejected_annotations_ids = set()
    accepted_annotations_ids = set()
    if os.path.exists(user_properties_pathname):
        with open(user_properties_pathname, 'rb') as file:
            rejected_annotations_ids, accepted_annotations_ids = pickle.load(file)
    return rejected_annotations_ids, accepted_annotations_ids


def save_annotations_actions(rejected_annotations_ids, accepted_annotations_ids):
    from webapp.auth.user_data import get_user_folder_name
    # Save the pickle file with the sets of rejected and accepted annotation IDs
    user_folder_name = get_user_folder_name()
    user_properties_pathname = os.path.join(user_folder_name, ANNOTATIONS_ACTIONS_FILENAME)
    with open(user_properties_pathname, 'wb') as file:
         pickle.dump((rejected_annotations_ids, accepted_annotations_ids), file)


def set_annotation_action(attribute_node_id, reject):
    rejected_annotations_ids, accepted_annotations_ids = load_annotations_actions()
    if reject:
        if attribute_node_id not in rejected_annotations_ids:
            rejected_annotations_ids.add(attribute_node_id)
            # Log the action
            try:
                attribute_node = Node.get_node_instance(attribute_node_id)
                from webapp.home.log_usage import annotations_actions, log_qudt_annotations_usage
                log_qudt_annotations_usage(
                    annotations_actions['REJECT'],
                    attribute_node)
            except Exception as e:
                pass
        accepted_annotations_ids.discard(attribute_node_id)
    else:
        if attribute_node_id not in accepted_annotations_ids:
            accepted_annotations_ids.add(attribute_node_id)
            # The addition of the annotation to the EML will be logged in qudt_annotations.py
        rejected_annotations_ids.discard(attribute_node_id)
    save_annotations_actions(rejected_annotations_ids, accepted_annotations_ids)


def is_rejected_annotation(attribute_node_id):
    rejected_annotation_ids, accepted_annotations_ids = load_annotations_actions()
    return attribute_node_id in rejected_annotation_ids


def is_accepted_annotation(attribute_node_id):
    rejected_annotation_ids, accepted_annotations_ids = load_annotations_actions()
    return attribute_node_id in accepted_annotations_ids


def reject_all_qudt_annotations(eml_node, data_table_node_id):
    """
    Reject all QUDT unit annotations for a data table.
    Returns true iff a change was made. Caller is responsible for saving changes.
    """
    data_table_node = Node.get_node_instance(data_table_node_id)
    if not data_table_node:
        return
    annotation_nodes = []
    rejected_annotations_ids, accepted_annotations_ids = load_annotations_actions()
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
        rejected_annotations_ids.add(attribute_node.id)
        accepted_annotations_ids.discard(attribute_node.id)
        # Log it
        # qudt_label = value_uri_node.attribute_value('label')
        # qudt_uri = value_uri_node.content or ''
        # qudt_code = qudt_uri.split('/')[-1]
        from webapp.home.log_usage import annotations_actions, log_qudt_annotations_usage
        log_qudt_annotations_usage(
            annotations_actions['REJECT'],
            attribute_node)
        attribute_node.remove_child(annotation_node)
        Node.delete_node_instance(annotation_node.id)
    if changed:
        save_annotations_actions(rejected_annotations_ids, accepted_annotations_ids)
    return changed


def accept_all_qudt_annotations(eml_node, data_table_node_id):
    """
    Accept all QUDT unit annotations for a data table. Besides updating the reject/accept sets,
     this adds the annotations to the model.
    Returns true iff a change was made. Caller is responsible for saving changes.
    """
    data_table_node = Node.get_node_instance(data_table_node_id)
    if not data_table_node:
        return
    # Get the attribute node IDs and remove them from the rejected set, add to the accepted set
    rejected_annotations_ids, accepted_annotations_ids = load_annotations_actions()
    original_rejected = rejected_annotations_ids.copy()
    original_accepted = accepted_annotations_ids.copy()
    attribute_nodes = []
    data_table_node.find_all_descendants(names.ATTRIBUTE, attribute_nodes)
    for attribute_node in attribute_nodes:
        if attribute_node.id not in accepted_annotations_ids:
            # Log it
            try:
                value_uri_node = attribute_node.find_descendant(names.VALUEURI)
                qudt_label = value_uri_node.attribute_value('label')
                qudt_uri = value_uri_node.content or ''
                qudt_code = qudt_uri.split('/')[-1]
                from webapp.home.log_usage import annotations_actions, log_qudt_annotations_usage
                log_qudt_annotations_usage(
                    annotations_actions['ACCEPT'],
                    attribute_node,
                    qudt_label,
                    qudt_code)
            except:
                pass
        rejected_annotations_ids.discard(attribute_node.id)
        accepted_annotations_ids.add(attribute_node.id)

    changed = (rejected_annotations_ids != original_rejected) or (accepted_annotations_ids != original_accepted)
    if changed:
        save_annotations_actions(rejected_annotations_ids, accepted_annotations_ids)
        add_qudt_annotations(eml_node)
    return changed


def remove_redundant_qudt_annotations(eml_node):
    """
    Finds and removes redundant QUDT units annotations.

    Returns True iff a change was made. Caller is responsible for saving the model if changed.
    """
    data_table_nodes = []
    eml_node.find_all_descendants(names.DATATABLE, data_table_nodes)
    changed = False
    for data_table_node in data_table_nodes:
        attribute_nodes = []
        data_table_node.find_all_descendants(names.ATTRIBUTE, attribute_nodes)
        for attribute_node in attribute_nodes:
            found = set()
            annotation_nodes = attribute_node.find_all_children(names.ANNOTATION)
            if len(annotation_nodes) < 2:
                continue
            for annotation_node in annotation_nodes:
                # See if it's a QUDT unit annotation
                qudt_label, qudt_code = is_qudt_annotation(annotation_node)
                if (qudt_label, qudt_code) in found:
                    # Have a duplicate. Remove it.
                    attribute_node.remove_child(annotation_node)
                    changed = True
                else:
                    found.add((qudt_label, qudt_code))
    return changed
