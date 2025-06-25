"""
Add QUDT units annotations, where available, to numerical attributes.

This code is based largely on the work of John Porter and the rest of the LTER Units Working Group.

Porter, J.H., O’Brien, M., Frants, M., Earl, S. Martin, M., and Laney, C.
Using a units ontology to annotate pre-existing metadata. Sci Data 12, 304 (2025).
https://doi.org/10.1038/s41597-025-04587-8
"""

import io
import os.path

import pandas as pd
import re
import requests
import uuid

from metapype.eml import names
from metapype.model.node import Node, Shift


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
                if has_existing_unit_annotation(attribute_node) and overwrite_existing:
                    remove_existing_unit_annotation(attribute_node)
                if not has_existing_unit_annotation(attribute_node):
                    annotation_node = Node(names.ANNOTATION)
                    attribute_node.add_child(annotation_node)
                    property_uri_node = Node(names.PROPERTYURI)
                    annotation_node.add_child(property_uri_node)
                    property_uri_node.add_attribute('label', 'has unit')
                    property_uri_node.content = 'http://qudt.org/schema/qudt/hasUnit'
                    value_uri_node = Node(names.VALUEURI)
                    annotation_node.add_child(value_uri_node)
                    value_uri_node.add_attribute('label', my_qudt_info_df.iloc[0]["qudtLabel"].strip())
                    value_uri_node.content = my_qudt_info_df.iloc[0]["qudtUri"]







