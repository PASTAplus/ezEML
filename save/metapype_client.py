#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: metapype_client.py

:Synopsis:

:Author:
    costa
    ide

:Created:
    7/27/18
"""
import collections
import daiquiri
from datetime import date
from enum import Enum
import html
import json
import math
import pickle

import logging
from logging import Formatter
from logging.handlers import RotatingFileHandler
from xml.sax.saxutils import escape, unescape

import os
from os import listdir
from os.path import isfile, join

from flask import Flask, flash, session, current_app, request
from flask_login import (
    current_user
)

from webapp.config import Config
from webapp.home.intellectual_rights import INTELLECTUAL_RIGHTS_CC0, INTELLECTUAL_RIGHTS_CC_BY

from metapype.eml import evaluate, validate, names, rule
from metapype.model.node import Node, Shift
from metapype.model import mp_io, metapype_io

from webapp.home.check_metadata import check_metadata_status
from webapp.home.texttype_node_processing import (
    model_has_complex_texttypes,
    construct_texttype_node,
    display_texttype_node,
    is_valid_xml_fragment,
    invalid_xml_error_message,
    sample_text,
    TEXTTYPE_NODES
)

import webapp.auth.user_data as user_data
import webapp.home.exceptions as exceptions
import webapp.home.check_data_table_contents as check_data_table_contents

from webapp.buttons import *
from webapp.pages import *
from webapp.utils import null_string

if Config.LOG_DEBUG:
    app = Flask(__name__)
    with app.app_context():
        cwd = os.path.dirname(os.path.realpath(__file__))
        logfile = cwd + '/metadata-eml-threads.log'
        file_handler = RotatingFileHandler(logfile, maxBytes=1000000000, backupCount=10)
        file_handler.setFormatter(Formatter('%(asctime)s %(levelname)s [pid:%(process)d tid:%(thread)d]: %(message)s [in %(pathname)s:%(lineno)d]'))
        file_handler.setLevel(logging.INFO)
        current_app.logger.addHandler(file_handler)
        current_app.logger.setLevel(logging.INFO)
        current_app.logger.info('*** RESTART ***')

logger = daiquiri.getLogger('metapype_client: ' + __name__)

RELEASE_NUMBER = '2023.08.30'

NO_OP = ''
UP_ARROW = html.unescape('&#x25B2;')
DOWN_ARROW = html.unescape('&#x25BC;')


class Optionality(Enum):
    REQUIRED = 1
    OPTIONAL = 2
    FORCE = 3


class VariableType(Enum):
    CATEGORICAL = 1
    DATETIME = 2
    NUMERICAL = 3
    TEXT = 4

HIDDEN_BUTTONS = [
    BTN_HIDDEN_CHECK,
    BTN_HIDDEN_SAVE,
    BTN_HIDDEN_DOWNLOAD,
    BTN_HIDDEN_NEW,
    BTN_HIDDEN_NEW_FROM_TEMPLATE,
    BTN_HIDDEN_OPEN,
    BTN_HIDDEN_CLOSE
]


def log_error(msg):
    if current_user and hasattr(current_user, 'get_username'):
        logger.error(msg, USER=current_user.get_username())
    else:
        logger.error(msg)


def log_info(msg):
    if current_user and hasattr(current_user, 'get_username'):
        logger.info(msg, USER=current_user.get_username())
    else:
        logger.info(msg)


def is_hidden_button():
    return any(button in request.form for button in HIDDEN_BUTTONS)


def handle_hidden_buttons(new_page, this_page):
    # If none of the hidden buttons is found, leave new_page as we found it
    if BTN_HIDDEN_CHECK in request.form:
        new_page = PAGE_CHECK
    elif BTN_HIDDEN_SAVE in request.form:
        new_page = this_page
    elif BTN_HIDDEN_DOWNLOAD in request.form:
        new_page = PAGE_DOWNLOAD
    elif BTN_HIDDEN_NEW in request.form:
        new_page = PAGE_CREATE
    elif BTN_HIDDEN_NEW_FROM_TEMPLATE in request.form:
        new_page = PAGE_IMPORT_TEMPLATE
    elif BTN_HIDDEN_OPEN in request.form:
        new_page = PAGE_OPEN
    elif BTN_HIDDEN_CLOSE in request.form:
        new_page = PAGE_CLOSE
    return new_page


def check_val_for_hidden_buttons(val, new_page, this_page):
    # If none of the hidden buttons is found, leave new_page as we found it
    if val == BTN_HIDDEN_CHECK:
        new_page = PAGE_CHECK
    elif val == BTN_HIDDEN_SAVE:
        new_page = this_page
    elif val == BTN_HIDDEN_DOWNLOAD:
        new_page = PAGE_DOWNLOAD
    elif val == BTN_HIDDEN_NEW:
        new_page = PAGE_CREATE
    elif val == BTN_HIDDEN_NEW_FROM_TEMPLATE:
        new_page = PAGE_IMPORT_TEMPLATE
    elif val == BTN_HIDDEN_OPEN:
        new_page = PAGE_OPEN
    elif val == BTN_HIDDEN_CLOSE:
        new_page = PAGE_CLOSE
    return new_page


def dump_node(node: Node, indent=0):
    indent_str = ' ' * indent
    print(f'{indent_str}{node.name} {node.id} {node.content}')
    for child in node.children:
        dump_node(child, indent + 2)


def node_tree_ids(node: Node, ids: list):
    ids.append(node.id)
    for child in node.children:
        id_str = node_tree_ids(child, ids)
    return ids


def calculate_node_store_checksums(eml_node):
    import hashlib
    id_string = ''
    for key, val in sorted(Node.store.items()):
        id_string += val.id
    node_store_hash = hashlib.md5(id_string.encode('utf-8')).hexdigest()
    tree_ids = sorted(node_tree_ids(eml_node, []))
    tree_hash = hashlib.md5(''.join(tree_ids).encode('utf-8')).hexdigest()
    return node_store_hash, tree_hash


def dump_node_store(eml_node, prefix=''):
    dump_node(eml_node)
    store_len = len(Node.store)
    log_info(f'*** {prefix} store_len={store_len}     {request.url}')
    node_store_hash, tree_hash = calculate_node_store_checksums(eml_node)
    log_info(f'*** {prefix} node store checksum={node_store_hash}    {request.url}')
    log_info(f'*** {prefix}  node tree checksum={tree_hash}    {request.url}')


def parse_package_id(package_id: str):
    """
    Takes a package_id in the form 'scope.identifier.revision' and returns a
    triple (scope, identifier, revision) where the identifier and revision are
    ints, suitable for sorting.
    """
    *_, scope, identifier, revision = package_id.split('.')
    return scope, int(identifier), int(revision)


def sort_package_ids(packages):
    return sorted(packages, key=lambda x: parse_package_id(x))


def list_data_packages(flag_current=False, include_current=True, current_user_directory_only=True):
    """
    Returns a list of data packages in the current user's account, as tuples suitable for
    use in a select list.  If flag_current is True, the current package is indicated. If
    include_current is False, the current package is excluded from the list.
    """
    choices = []
    user_documents = sorted(user_data.get_user_document_list(current_user_directory_only=current_user_directory_only),
                            key=str.casefold)
    current_annotation = ' (current data package)' if flag_current else ''
    for document in user_documents:
        pid_tuple = (document, document)
        if document == current_user.get_filename():
            if not include_current:
                continue
            pid_tuple = (document, f'{document}{current_annotation}')
        choices.append(pid_tuple)
    return choices


def list_files_in_dir(dirpath):
    return [f for f in listdir(dirpath) if isfile(join(dirpath, f))]


def post_process_texttype_node(text_node:Node=None):
    if not text_node:
        return
    use_complex_representation = user_data.get_model_has_complex_texttypes()
    if text_node.content:
        # If we have content, we're saving a node that's been modified. We remake the children.
        if use_complex_representation and text_node.name in TEXTTYPE_NODES:
            new_node = construct_texttype_node(text_node.content, text_node.name)
            text_node.content = new_node.content
            text_node.tail = new_node.tail
            text_node.children = new_node.children
        else:
            content = remove_paragraph_tags(text_node.content)
            # If we have para children, we're handling text that has been modified but that originally used
            #  para tags (e.g., a package imported from XML). Presumably, the user wants paras, so let's
            #  do that. We need to check for this before we remove the children.
            all_paras = False
            children = text_node.children
            if children:
                all_paras = True
                for child in children:
                    if child.name != names.PARA:
                        all_paras = False
                        break
            text_node.remove_children()
            text_node.content = content
            if all_paras or not children:  # If we have no children, we're handling simple text. Add paras there, too.
                save_content_in_para_nodes(text_node)


def save_content_in_para_nodes(text_node):
    s = text_node.content
    if s:
        paras = s.split('\n')
        for para in paras:
            para_node = Node(names.PARA, parent=text_node)
            para_node.content = para
            text_node.add_child(para_node)
        text_node.content = ''


def remove_paragraph_tags(s):
    if s:
        return unescape(s).strip().replace('</para>\n<para>', '\n').replace('<para>', '').replace('</para>', '').replace('\r', '')
    else:
        return s


def new_child_node(child_name:str, parent:Node):
    child_node = Node(child_name, parent=parent)
    add_child(parent, child_node)
    return child_node


def add_node(parent_node:Node, child_name:str, content:str=None, optionality=Optionality.REQUIRED):
    if optionality == Optionality.OPTIONAL and not content:
        return
    child_node = parent_node.find_child(child_name)
    if not child_node:
        child_node = Node(child_name, parent=parent_node)
        if not Optionality.FORCE:
            add_child(parent_node, child_node)
        else:
            # when we add to additionalMetadata, we sidestep rule checking
            parent_node.add_child(child_node)
    child_node.content = content
    return child_node


def add_child(parent_node:Node, child_node:Node):
    if parent_node and child_node:
        parent_rule = rule.get_rule(parent_node.name)
        index = parent_rule.child_insert_index(parent_node, child_node)
        parent_node.add_child(child_node, index=index)


def move_up(parent_node:Node, child_node:Node):
    if parent_node and child_node:
        parent_node.shift(child_node, Shift.LEFT)


def move_down(parent_node:Node, child_node:Node):
    if parent_node and child_node:
        parent_node.shift(child_node, Shift.RIGHT)


def force_missing_value_codes(attribute_node, codes):
    """
    Replace nan values with the missing value code, if any. This will apply the first missing value code.
    """
    missing_value_code_node = attribute_node.find_descendant(names.CODE)
    if missing_value_code_node:
        missing_value = missing_value_code_node.content
        for index, item in enumerate(codes):
            try:
                # isnan requires item to be a number. It may not be.
                if math.isnan(item):
                    codes[index] = missing_value
            except TypeError as e:
                pass


def list_data_tables(eml_node:Node=None, to_skip:str=None):
    dt_list = []
    if eml_node:
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            dt_nodes = dataset_node.find_all_children(names.DATATABLE)
            DT_Entry = collections.namedtuple(
                'DT_Entry', 
                ["id", "label", "object_name", "was_uploaded", "upval", "downval"],
                 rename=False)
            for i, dt_node in enumerate(dt_nodes):
                id = dt_node.id
                if to_skip and id == to_skip:
                    continue
                label, object_name = compose_entity_label(dt_node)
                was_uploaded = user_data.data_table_was_uploaded(object_name)
                upval = get_upval(i)
                downval = get_downval(i+1, len(dt_nodes))
                dt_entry = DT_Entry(id=id,
                                    label=label,
                                    object_name=object_name,
                                    was_uploaded=was_uploaded,
                                    upval=upval, 
                                    downval=downval)
                dt_list.append(dt_entry)
    return dt_list


def list_data_table_columns(dt_node:Node=None):
    dt_columns_list = []
    if dt_node:
        attribute_name_nodes = []
        dt_node.find_all_descendants(names.ATTRIBUTENAME, attribute_name_nodes)
        for attribute_name_node in attribute_name_nodes:
            dt_columns_list.append([attribute_name_node.id, attribute_name_node.content])
    return dt_columns_list


def list_other_entities(eml_node:Node=None):
    oe_list = []
    if eml_node:
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            oe_nodes = dataset_node.find_all_children(names.OTHERENTITY)
            OE_Entry = collections.namedtuple(
                'OE_Entry', 
                ["id", "label", "object_name", "was_uploaded", "upval", "downval"],
                rename=False)
            for i, oe_node in enumerate(oe_nodes):
                id = oe_node.id
                label, object_name = compose_entity_label(oe_node)
                was_uploaded = user_data.data_table_was_uploaded(object_name)
                upval = get_upval(i)
                downval = get_downval(i+1, len(oe_nodes))
                oe_entry = OE_Entry(id=id,
                                    label=label,
                                    object_name=object_name,
                                    was_uploaded=was_uploaded,
                                    upval=upval,
                                    downval=downval)
                oe_list.append(oe_entry)
    return oe_list


def compose_entity_label(entity_node:Node=None):
    label = ''
    object_name = ''
    if entity_node:
        entity_name_node = entity_node.find_child(names.ENTITYNAME)
        if entity_name_node:
            label = entity_name_node.content
        object_name_node = entity_node.find_descendant(names.OBJECTNAME)
        if object_name_node:
            object_name = object_name_node.content
    return label, object_name


def nominal_ordinal_from_attribute(att_node:Node=None):
    """
    If attribute has nominal or ordinal measurementScale, return its nominal or ordinal node. Otherwise return None.
    """
    if att_node:
        nominal_node = att_node.find_single_node_by_path([
            names.MEASUREMENTSCALE, names.NOMINAL
        ])
        if nominal_node:
            return nominal_node
        return att_node.find_single_node_by_path([
            names.MEASUREMENTSCALE, names.ORDINAL
        ])
    return None


def list_codes_and_definitions(att_node:Node=None):
    codes_list = []
    nominal_ordinal_node = nominal_ordinal_from_attribute(att_node)

    if nominal_ordinal_node:
        code_definition_nodes = nominal_ordinal_node.find_all_nodes_by_path([
            names.NONNUMERICDOMAIN,
            names.ENUMERATEDDOMAIN,
            names.CODEDEFINITION
        ])
        if code_definition_nodes:
            Code_Definition_Entry = collections.namedtuple(
                            'Code_Definition_Entry',
                            ["id", "code", "definition", "upval", "downval"],
                            rename=False)

            for i, cd_node in enumerate(code_definition_nodes):
                id = cd_node.id
                code, definition = compose_code_definition(cd_node)
                upval = get_upval(i)
                downval = get_downval(i+1, len(code_definition_nodes))
                cd_entry = Code_Definition_Entry(
                                id=id,
                                code=code,
                                definition=definition,
                                upval=upval,
                                downval=downval)
                codes_list.append(cd_entry)
        return codes_list


def compose_code_definition(code_definition_node:Node=None):
    code = ''
    definition = ''

    if code_definition_node:
        code_node = code_definition_node.find_child(names.CODE)
        if code_node:
            code = code_node.content
        definition_node = code_definition_node.find_child(names.DEFINITION)
        if definition_node and definition_node.content:
            definition = definition_node.content
        else:
            definition = ''

    return code, definition


def entity_name_from_data_table(dt_node:Node=None):
    entity_name = ''

    if dt_node:
        entity_name_node = dt_node.find_child(names.ENTITYNAME)
        if entity_name_node:
            entity_name = entity_name_node.content

    return entity_name
    

def attribute_name_from_attribute(att_node:Node=None):
    attribute_name = ''

    if att_node:
        attribute_name_node = att_node.find_child(names.ATTRIBUTENAME)
        if attribute_name_node:
            attribute_name = attribute_name_node.content

    return attribute_name


def code_definition_from_attribute(att_node:Node=None):
    nominal_ordinal_node = nominal_ordinal_from_attribute(att_node)
    if nominal_ordinal_node:
        return nominal_ordinal_node.find_single_node_by_path([
            names.NONNUMERICDOMAIN,
            names.ENUMERATEDDOMAIN,
            names.CODEDEFINITION
        ])
    else:
        return None


def enumerated_domain_from_attribute(att_node:Node=None):
    nominal_ordinal_node = nominal_ordinal_from_attribute(att_node)
    if nominal_ordinal_node:
        return nominal_ordinal_node.find_single_node_by_path([
            names.NONNUMERICDOMAIN, names.ENUMERATEDDOMAIN
        ])
    else:
        return None


def non_numeric_domain_from_measurement_scale(ms_node:Node=None):
    nnd_node = None

    if ms_node:
        nominal_or_ordinal_node = ms_node.find_child(names.NOMINAL)
        if not nominal_or_ordinal_node:
            nominal_or_ordinal_node = ms_node.find_child(names.ORDINAL)
        
        if nominal_or_ordinal_node:
            nnd_node = nominal_or_ordinal_node.find_child(names.NONNUMERICDOMAIN)

    return nnd_node


def mscale_from_attribute(att_node:Node=None):
    if att_node:
        mscale_node = att_node.find_child(names.MEASUREMENTSCALE)

        if mscale_node:

            # Formerly, Categorical variables were nominal. But now that we're importing externally created XML
            #  files, they may be ordinal.
            nominal_or_ordinal_node = mscale_node.find_child(names.NOMINAL)
            if not nominal_or_ordinal_node:
                nominal_or_ordinal_node = mscale_node.find_child(names.ORDINAL)
            if nominal_or_ordinal_node:
                non_numeric_domain_node = nominal_or_ordinal_node.find_child(names.NONNUMERICDOMAIN)
                if non_numeric_domain_node:
                    enumerated_domain_node = non_numeric_domain_node.find_child(names.ENUMERATEDDOMAIN)
                    if enumerated_domain_node:
                        return VariableType.CATEGORICAL.name
                    text_domain_node = non_numeric_domain_node.find_child(names.TEXTDOMAIN)
                    if text_domain_node:
                        return VariableType.TEXT.name

            # Formerly, Numerical variables were ratio. But now that we're importing externally created XML
            #  files, they may be interval.
            ratio_or_interval_node = mscale_node.find_child(names.RATIO)
            if not ratio_or_interval_node:
                ratio_or_interval_node = mscale_node.find_child(names.INTERVAL)
            if ratio_or_interval_node:
                return VariableType.NUMERICAL.name

            date_time_node = mscale_node.find_child(names.DATETIME)
            if date_time_node:
                return VariableType.DATETIME.name

    return None


def list_attributes(data_table_node:Node=None, caller:str=None, dt_node_id:str=None):
    att_list = []
    if data_table_node:
        attribute_list_node = data_table_node.find_child(names.ATTRIBUTELIST)
        if attribute_list_node:
            att_nodes = attribute_list_node.find_all_children(names.ATTRIBUTE)
            ATT_Entry = collections.namedtuple(
                'ATT_Entry', 
                ["id", "column_number", "label", "mscale", "upval", "downval"],
                 rename=False)
            for i, att_node in enumerate(att_nodes):
                id = att_node.id
                column_number = str(i+1)
                label = compose_attribute_label(att_node)
                mscale = compose_attribute_mscale(att_node)
                upval = get_upval(i)
                downval = get_downval(i+1, len(att_nodes))
                att_entry = ATT_Entry(id=id,
                                      column_number=column_number,
                                      label=label,
                                      mscale=mscale,
                                      upval=upval, 
                                      downval=downval)
                att_list.append(att_entry)

    if Config.LOG_DEBUG:
        log_info(f'Attribute list: caller={caller} dt_node_id={dt_node_id}')
        if not data_table_node:
            log_info('*** data_table_node not found ***')
        else:
            log_info(f'data_table_node.id={data_table_node.id}')
        for entry in att_list:
            log_info(f'{entry.id} {entry.label}')

    if Config.FLASH_DEBUG:
        flash(f'Attribute list: {att_list}')

    return att_list


def compose_attribute_label(att_node:Node=None):
    label = ''
    if att_node:
        attribute_name_node = att_node.find_child(names.ATTRIBUTENAME)
        if attribute_name_node:
            attribute_name = attribute_name_node.content 
            label = attribute_name
    return label


def compose_attribute_mscale(att_node:Node=None):
    mscale = ''
    if att_node:
        mscale = mscale_from_attribute(att_node)
        if mscale == VariableType.CATEGORICAL.name:
            mscale = 'Categorical'
        elif mscale == VariableType.NUMERICAL.name:
            mscale = 'Numerical'
        elif mscale == VariableType.TEXT.name:
            mscale = 'Text'
        elif mscale == VariableType.DATETIME.name:
            mscale = 'DateTime'
    return mscale


def list_responsible_parties(eml_node:Node=None, node_name:str=None, project_node_id:str=None):
    rp_list = []
    if eml_node:
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            parent_node = dataset_node
            if node_name == 'personnel':
                if not project_node_id:
                    project_node = dataset_node.find_child(names.PROJECT)
                    if project_node:
                        parent_node = project_node
                elif project_node_id != '1':
                    parent_node = Node.get_node_instance(project_node_id)

            rp_nodes = parent_node.find_all_children(node_name)
            RP_Entry = collections.namedtuple(
                'RP_Entry', ["id", "label", "upval", "downval"],
                 rename=False)
            for i, rp_node in enumerate(rp_nodes):
                label = compose_rp_label(rp_node)
                id = f"{rp_node.id}|{project_node_id}"
                upval = get_upval(i)
                downval = get_downval(i+1, len(rp_nodes))
                rp_entry = RP_Entry(id=id, label=label, upval=upval, downval=downval)
                rp_list.append(rp_entry)
    return rp_list


def list_geographic_coverages(parent_node:Node=None):
    gc_list = []
    max_len = 40
    if parent_node:
        coverage_node = parent_node.find_child(names.COVERAGE)
        if coverage_node:
            gc_nodes = \
                coverage_node.find_all_children(names.GEOGRAPHICCOVERAGE)
            GC_Entry = collections.namedtuple(
                'GC_Entry', 
                ["id", "geographic_description", "label", "upval", "downval"],
                rename=False)
            for i, gc_node in enumerate(gc_nodes):
                description = ''
                id = gc_node.id
                upval = get_upval(i)
                downval = get_downval(i+1, len(gc_nodes))
                geographic_description_node = \
                    gc_node.find_child(names.GEOGRAPHICDESCRIPTION)
                if geographic_description_node:
                    description = geographic_description_node.content
                    try:
                        if description and len(description) > max_len:
                            description = description[0:max_len]
                    except:
                        pass
                label = compose_gc_label(gc_node)
                gc_entry = GC_Entry(id=id,
                            geographic_description=description,
                            label=label,
                            upval=upval, downval=downval)
                gc_list.append(gc_entry)
    return gc_list


def get_upval(i:int):
    return NO_OP if i == 0 else UP_ARROW


def get_downval(i:int, n:int):
    return NO_OP if i >= n else DOWN_ARROW


def massage_altitude_units(units):
    retval = units
    if units == 'Foot_US':
        retval = 'foot (US)'
    elif units == 'nauticalMile':
        retval = 'nautical mile'
    elif units == 'Foot_Gold_Coast':
        retval = 'foot (Gold Coast)'
    elif units == 'Yard_Indian':
        retval = 'yard (India)'
    elif units == 'Link_Clarke':
        retval = 'Clarke link'
    elif units == 'Yard_Sears':
        retval = 'Sears yard'
    return retval


def compose_gc_label(gc_node:Node=None):
    '''
    Composes a label for a geographic coverage table entry
    '''
    label = ''
    if gc_node:
        bc_node = gc_node.find_child(names.BOUNDINGCOORDINATES)
        if bc_node:
            wbc_node = bc_node.find_child(names.WESTBOUNDINGCOORDINATE)
            ebc_node = bc_node.find_child(names.EASTBOUNDINGCOORDINATE)
            nbc_node = bc_node.find_child(names.NORTHBOUNDINGCOORDINATE)
            sbc_node = bc_node.find_child(names.SOUTHBOUNDINGCOORDINATE)
            amin_node = bc_node.find_descendant(names.ALTITUDEMINIMUM)
            amax_node = bc_node.find_descendant(names.ALTITUDEMAXIMUM)
            aunits_node = bc_node.find_descendant(names.ALTITUDEUNITS)
            if wbc_node and ebc_node and nbc_node and sbc_node:
                coordinate_list = [str(wbc_node.content),
                                   str(ebc_node.content),
                                   str(nbc_node.content),
                                   str(sbc_node.content)]
                if amin_node and amax_node and aunits_node:
                    coordinate_list.extend([str(amin_node.content),
                                            str(amax_node.content),
                                            massage_altitude_units(str(aunits_node.content))])
                label = ', '.join(coordinate_list)
    return label


def compose_full_gc_label(gc_node:Node=None):
    description = ''
    if gc_node:
        description_node = gc_node.find_child(names.GEOGRAPHICDESCRIPTION)
        if description_node and description_node.content:
            description = description_node.content
    bounding_coordinates_label = compose_gc_label(gc_node)
    return ': '.join([description, bounding_coordinates_label])


def list_temporal_coverages(parent_node:Node=None):
    tc_list = []
    if parent_node:
        coverage_node = parent_node.find_child(names.COVERAGE)
        if coverage_node:
            tc_nodes = coverage_node.find_all_children(names.TEMPORALCOVERAGE)
            TC_Entry = collections.namedtuple(
                'TC_Entry', ["id", "begin_date", "end_date", "upval", "downval"],
                    rename=False)
            for i, tc_node in enumerate(tc_nodes):
                id = tc_node.id
                upval = get_upval(i)
                downval = get_downval(i+1, len(tc_nodes))

                single_datetime_nodes = tc_node.find_all_children(names.SINGLEDATETIME)
                if single_datetime_nodes:
                    for sd_node in single_datetime_nodes:
                        calendar_date_node = sd_node.find_child(names.CALENDARDATE)
                        if calendar_date_node:
                            begin_date = calendar_date_node.content
                            end_date = ''
                            tc_entry = TC_Entry(id=id, begin_date=begin_date, end_date=end_date, upval=upval, downval=downval)
                            tc_list.append(tc_entry)

                range_of_dates_nodes = tc_node.find_all_children(names.RANGEOFDATES)
                if range_of_dates_nodes:
                    for rod_node in range_of_dates_nodes:
                        begin_date = ''
                        end_date = ''
                        begin_date_node = rod_node.find_child(names.BEGINDATE)
                        if begin_date_node:
                            calendar_date_node = begin_date_node.find_child(names.CALENDARDATE)
                            if calendar_date_node:
                                begin_date = calendar_date_node.content
                        end_date_node = rod_node.find_child(names.ENDDATE)
                        if end_date_node:
                            calendar_date_node = end_date_node.find_child(names.CALENDARDATE)
                            if calendar_date_node:
                                end_date = calendar_date_node.content
                        tc_entry = TC_Entry(id=id, begin_date=begin_date, end_date=end_date, upval=upval, downval=downval)
                        tc_list.append(tc_entry)
    return tc_list


def list_taxonomic_coverages(parent_node:Node=None):
    txc_list = []
    if parent_node:
        coverage_node = parent_node.find_child(names.COVERAGE)
        if coverage_node:
            txc_nodes = coverage_node.find_all_children(
                names.TAXONOMICCOVERAGE)
            TXC_Entry = collections.namedtuple(
                'TXC_Entry', ["id", "label", "upval", "downval"],
                rename=False)
            for i, txc_node in enumerate(txc_nodes):
                id = txc_node.id
                upval = get_upval(i)
                downval = get_downval(i+1, len(txc_nodes))
                label = truncate_middle(compose_taxonomic_label(txc_node, label=''), 70, ' ... ')
                txc_entry = TXC_Entry(
                    id=id, label=label, upval=upval, downval=downval)
                txc_list.append(txc_entry)

    return txc_list


def truncate_middle(s, n, mid='...'):
    if len(s) <= n:
        # string is already short-enough
        return s
    # half of the size, minus the middle
    n_2 = int(n / 2) - len(mid)
    # whatever's left
    n_1 = n - n_2 - len(mid)
    return f'{s[:n_1]}{mid}{s[-n_2:]}'


def compose_taxonomic_label(txc_node:Node=None, label:str=''):
    if not txc_node:
        return label
    tc_node = txc_node.find_child(names.TAXONOMICCLASSIFICATION)
    if tc_node:
        val = ''
        trv_node = tc_node.find_child(names.TAXONRANKVALUE)
        if trv_node:
            val = trv_node.content
        # new_label = label + ' ' + val if label else val
        new_label = val
        return compose_taxonomic_label(tc_node, new_label)
    else:
        return label


def reconcile_roles(node, target_class):
    """
    When importing a responsible party, the source node may or may not have a role and the target
    class may or may not require a role. If the target doesn't have role as an allowed child, remove
    the role, if present. If the target requires a role and the source doesn't have one, add a role
    child with empty content.
    """
    if target_class in ['Creators', 'Metadata Providers', 'Contacts']:
        role_node = node.find_child(names.ROLE)
        if role_node:
            node.remove_child(role_node)
    elif target_class in ['Associated Parties', 'Project Personnel']:
        role_node = node.find_child(names.ROLE)
        if not role_node:
            role_node = Node(names.ROLE)
            node.add_child(role_node)


def import_responsible_parties(target_package, node_ids_to_import, target_class):
    owner_login = user_data.get_active_document_owner_login()
    target_eml_node = load_eml(target_package, owner_login=owner_login)
    dataset_node = target_eml_node.find_child(names.DATASET)
    if target_class in ['Creators', 'Metadata Providers', 'Associated Parties', 'Contacts', 'Publisher']:
        parent_node = dataset_node
    else:
        project_node = target_eml_node.find_single_node_by_path([names.DATASET, names.PROJECT])
        if not project_node:
            project_node = new_child_node(names.PROJECT, dataset_node)
        parent_node = project_node
    new_name = None
    if target_class == 'Creators':
        new_name = names.CREATOR
    elif target_class == 'Metadata Providers':
        new_name = names.METADATAPROVIDER
    elif target_class == 'Associated Parties':
        new_name = names.ASSOCIATEDPARTY
    elif target_class == 'Contacts':
        new_name = names.CONTACT
    elif target_class == 'Publisher':
        new_name = names.PUBLISHER
    elif target_class == 'Project Personnel':
        new_name = names.PERSONNEL
    for node_id in node_ids_to_import:
        node = Node.get_node_instance(node_id)
        new_node = node.copy()
        reconcile_roles(new_node, target_class)
        new_node.name = new_name
        add_child(parent_node, new_node)
    save_both_formats(target_package, target_eml_node)


def import_coverage_nodes(target_package, node_ids_to_import):
    owner_login = user_data.get_active_document_owner_login()
    target_eml_node = load_eml(target_package, owner_login=owner_login)
    parent_node = target_eml_node.find_single_node_by_path([names.DATASET, names.COVERAGE])
    if not parent_node:
        dataset_node = target_eml_node.find_child(names.DATASET)
        coverage_node = Node(names.COVERAGE)
        add_child(dataset_node, coverage_node)
        parent_node = coverage_node
    for node_id in node_ids_to_import:
        node = Node.get_node_instance(node_id)
        new_node = node.copy()
        add_child(parent_node, new_node)
    save_both_formats(target_package, target_eml_node)
    return target_eml_node


def import_funding_award_nodes(target_package, node_ids_to_import):
    owner_login = user_data.get_active_document_owner_login()
    target_eml_node = load_eml(target_package, owner_login=owner_login)
    parent_node = target_eml_node.find_single_node_by_path([names.DATASET, names.PROJECT])
    if not parent_node:
        dataset_node = target_eml_node.find_child(names.DATASET)
        project_node = Node(names.PROJECT)
        add_child(dataset_node, project_node)
        parent_node = project_node
    for node_id in node_ids_to_import:
        node = Node.get_node_instance(node_id)
        new_node = node.copy()
        add_child(parent_node, new_node)
    save_both_formats(target_package, target_eml_node)


def compose_funding_award_label(award_node:Node=None):
    if not award_node:
        return ''
    title = ''
    title_node = award_node.find_child(names.TITLE)
    if title_node:
        title = title_node.content
    funder_name = ''
    funder_name_node = award_node.find_child(names.FUNDERNAME)
    if funder_name_node:
        funder_name = funder_name_node.content
    return f'{title}: {funder_name}'


def compose_project_label(project_node:Node=None):
    if not project_node:
        return ''
    title = ''
    title_node = project_node.find_child(names.TITLE)
    if title_node:
        title = title_node.content
    return title


def import_project_node(target_package, node_id_to_import):
    if not node_id_to_import:
        return
    imported_node = Node.get_node_instance(node_id_to_import)
    if not imported_node:
        return
    owner_login = user_data.get_active_document_owner_login()
    target_eml_node = load_eml(target_package, owner_login=owner_login)
    project_node = target_eml_node.find_single_node_by_path([names.DATASET, names.PROJECT])
    dataset_node = target_eml_node.find_child(names.DATASET)
    if project_node:
        dataset_node.remove_child(project_node)
    new_node = imported_node.copy()
    new_node.name = names.PROJECT
    # For now we will remove any related projects. User will need to import any related projects separately.
    for child in new_node.find_all_children(names.RELATED_PROJECT):
        new_node.remove_child(child)
    add_child(dataset_node, new_node)
    save_both_formats(target_package, target_eml_node)


def import_related_project_nodes(target_package, node_ids_to_import):
    owner_login = user_data.get_active_document_owner_login()
    target_eml_node = load_eml(target_package, owner_login=owner_login)
    parent_node = target_eml_node.find_single_node_by_path([names.DATASET, names.PROJECT])
    if not parent_node:
        dataset_node = target_eml_node.find_child(names.DATASET)
        project_node = Node(names.PROJECT)
        add_child(dataset_node, project_node)
        parent_node = project_node
    for node_id in node_ids_to_import:
        node = Node.get_node_instance(node_id)
        new_node = node.copy()
        new_node.name = names.RELATED_PROJECT
        # if node has related_children, remove them
        for child in new_node.find_all_children(names.RELATED_PROJECT):
            new_node.remove_child(child)
        add_child(parent_node, new_node)
    save_both_formats(target_package, target_eml_node)


def compose_rp_label(rp_node:Node=None):
    """
    What we display for a responsible party depends on the type of responsible party.
    """
    label = ''
    if rp_node:
        individual_name_node = rp_node.find_child(names.INDIVIDUALNAME)
        individual_name_label = (
            compose_individual_name_label(individual_name_node))
        role_node = rp_node.find_child(names.ROLE)
        if role_node:
            role_label = role_node.content
        else:
            role_label = ''
        organization_name_label = (
            compose_simple_label(rp_node, names.ORGANIZATIONNAME))
        position_name_label = (
            compose_simple_label(rp_node, names.POSITIONNAME))

        if individual_name_label:
            label = individual_name_label
        if position_name_label:
            if label:
                label = label + ', '
            label = label + position_name_label
        if organization_name_label:
            if label:
                label = label + ', '
            label = label + organization_name_label
        if role_label:
            if label:
                label = label + ', '
            label = label + role_label
    return label


def compose_individual_name_label(rp_node:Node=None):
    label = ''
    if rp_node:
        salutation_nodes = rp_node.find_all_children(names.SALUTATION)
        if salutation_nodes:
            for salutation_node in salutation_nodes:
                if salutation_node and salutation_node.content:
                    label = label + " " + salutation_node.content
        
        given_name_nodes = rp_node.find_all_children(names.GIVENNAME)
        if given_name_nodes:
            for given_name_node in given_name_nodes:
                if given_name_node and given_name_node.content:
                    label = label + " " + given_name_node.content
        
        surname_node = rp_node.find_child(names.SURNAME)
        if surname_node and surname_node.content:
            label = label + " " + surname_node.content

    return label


def compose_simple_label(rp_node:Node=None, child_node_name:str=''):
    label = ''
    if rp_node and child_node_name:
        child_node = rp_node.find_child(child_node_name)
        if child_node and child_node.content:
            label = child_node.content
    return label


def from_json(filename):
    eml_node = None
    try:
        with open(filename, "r") as json_file:
            json_text = json_file.read()
            # The JSON may be in one of two formats
            try:
                eml_node = metapype_io.from_json(json_text)

            except KeyError as e:
                # Must be in the old format. When saved, the JSON will be written in the new format.
                try:
                    json_dict = json.loads(json_text)
                    eml_node = mp_io.from_json(json_dict)
                except KeyError as e:
                    logger.error(e)

        try:
            check_for_nonstring_content(eml_node)
        except ValueError as e:
            logger.error(f'Nonstring content found: {str(e)}')
            fix_nonstring_content(eml_node)
            basename, ext = os.path.splitext(os.path.basename(filename))
            save_both_formats(filename=basename, eml_node=eml_node)

    except Exception as e:
         logger.error(e)
    return eml_node


def save_package_id(eml_node):
    # There are various ways of opening a new package, and we want to ensure that no matter what path we took,
    #   the package ID is updated in the current user.
    if eml_node:
        data_package_id = eml_node.attribute_value('packageId')
        if data_package_id:
            user_data.set_active_packageid(data_package_id)


def load_eml(filename:str=None,
             folder_name=None,
             use_pickle:bool=False,
             skip_metadata_check:bool=False,
             do_not_lock:bool=False,
             owner_login:str=None,
             log_the_details:bool=False):

    if not log_the_details and hasattr(Config, 'LOG_FILE_HANDLING_DETAILS'):
        log_the_details = Config.LOG_FILE_HANDLING_DETAILS

    # Usually when we load an EML file, we want to acquire a lock on it. However, there are times when we are just
    #  looking at the file, not opening it for editing. For example, when checking metadata or when getting the package
    #  size for manage packages page.
    if not do_not_lock:
        try:
            user_data.is_document_locked(filename, owner_login=owner_login)
        except Exception as e:
            logger.error(f"load_eml: is_document_locked: {e}")
            raise

    if owner_login:
        folder_name = user_data.get_user_folder_name(owner_login=owner_login)

    eml_node = None
    if folder_name:
        user_folder = folder_name
    else:
        user_folder = None
        try:
            user_folder = user_data.get_user_folder_name(log_the_details=log_the_details)
        except Exception as e:
            logger.error(f"load_eml: {e}")
    if not user_folder:
        user_folder = '.'
    ext = 'json' if not use_pickle else 'pkl'
    ext_filename = f"{user_folder}/{filename}.{ext}"
    if log_the_details:
        logger.info(f"load_eml: ext_filename: {ext_filename}")
    if os.path.isfile(ext_filename):
        if use_pickle:
            eml_node = pickle.load(open(ext_filename, 'rb'))
        else:
            eml_node = from_json(ext_filename)
    elif use_pickle:
        ext_filename = filename.replace('.pkl', '.json')
        if os.path.isfile(ext_filename):
            eml_node = from_json(ext_filename)

    if eml_node:
        if not skip_metadata_check:
            get_check_metadata_status(eml_node, filename)
            check_data_table_contents.set_check_data_tables_badge_status(filename, eml_node)
            # save_package_id(eml_node)
            user_data.set_model_has_complex_texttypes(model_has_complex_texttypes(eml_node))
    else:
        logger.error(f"load_eml: Could not load {ext_filename}")

    from webapp.home.views import url_of_interest
    if url_of_interest():
        if Config.MEM_LOG_METAPYPE_STORE_ACTIONS:
            store_len = len(Node.store)
            log_info(f'*** load_eml ***: store_len={store_len}     {request.url}')
            log_info(f'*** load_eml ***: node store checksum={calculate_node_store_checksum()}    {request.url}')

    return eml_node


def calculate_node_store_checksum():
    import hashlib
    id_string = ''
    for key, val in sorted(Node.store.items()):
        id_string += val.id
    return hashlib.md5(id_string.encode('utf-8')).hexdigest()


def remove_child(node_id:str=None):
    if node_id:
        child_node = Node.get_node_instance(node_id)
        if child_node:
            parent_node = child_node.parent
            if parent_node:
                parent_node.remove_child(child_node)


def log_as_xml(node: Node):
    xml_str = metapype_io.to_xml(node)
    logger.info("\n\n" + xml_str)


def save_old_to_new(old_filename:str=None, new_filename:str=None, eml_node:Node=None):
    """
    Do "Save As", saving the current document under a new document name.
    """
    msg = None
    if new_filename and eml_node and new_filename != old_filename:
        # We save in the current user's folder, even if we're collaborating.
        save_both_formats(filename=new_filename, eml_node=eml_node.copy(), owner_login=current_user.get_user_login())
    elif new_filename == old_filename:
        msg = 'New package id and old package id are the same'
    else:
        msg = 'Not saved'

    return msg


def strip_elements_added_by_pasta(filename:str=None, eml_node:Node=None):
    """
    PASTA adds an alternateIdentifier element to the EML document to record the package's DOI, and it adds a distribution
    element at the dataset level to record the package's URL on PASTA. We strip these elements when importing a document
    so that if the document is submitted to the repository as a revision we won't accumulate multiple such elements.
    """
    modified = False
    dataset_node = eml_node.find_child(names.DATASET)
    alternate_id_nodes = dataset_node.find_all_children(names.ALTERNATEIDENTIFIER)
    for alternate_id_node in alternate_id_nodes:
        if alternate_id_node and 'pasta' in alternate_id_node.content:
            dataset_node.remove_child(alternate_id_node)
            modified = True
    distribution_nodes = dataset_node.find_all_children(names.DISTRIBUTION)
    for distribution_node in distribution_nodes:
        online_nodes = distribution_node.find_all_children(names.ONLINE)
        for online_node in online_nodes:
            url_node = online_node.find_child(names.URL)
            if url_node and url_node.content and 'pasta' in url_node.content:
                dataset_node.remove_child(distribution_node)
                modified = True
    if modified:
        save_both_formats(filename=filename, eml_node=eml_node)
    return eml_node


def package_contains_elements_unhandled_by_ezeml(filename:str=None, eml_node:Node=None):
    """
    There are a number of elements in EML that are not exposed by the ezEML user interface. We preserve such elements
    in the model, but we want to warn the user if the document contains such elements.
    If the package contains element(s) unhandled by ezEML, this function returns a sorted list of the element names.

    Note: We don't want to include the alternateIdentifier and distribution elements that PASTA adds to the document,
    so we strip those elements before checking for unhandled elements.
    """
    unhandled = [
        names.ALTERNATEIDENTIFIER,
        names.SHORTNAME,
        names.LANGUAGE,
        names.SERIES,
        names.ADDITIONALINFO,
        names.LICENSED,
        names.DISTRIBUTION,
        names.ANNOTATION,
        names.PURPOSE,
        names.INTRODUCTION,
        names.GETTINGSTARTED,
        names.ACKNOWLEDGEMENTS,
        # names.REFERENCEPUBLICATION,
        # names.USAGECITATION,
        # names.LITERATURECITED,
        # names.ANNOTATIONS
    ]
    found = set()

    if eml_node:
        eml_node = strip_elements_added_by_pasta(filename, eml_node)
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            for child in dataset_node.children:
                if child.name in unhandled:
                    if child.name != 'distribution':
                        found.add(child.name)
                    else:
                        found.add('distribution (at dataset level)')
        # annotations_node = eml_node.find_child(names.ANNOTATIONS)
        # if annotations_node:
        #     found.add(names.ANNOTATIONS)
    return sorted(found)


def enforce_dataset_sequence(eml_node:Node=None):
    def collect_children(parent_node: Node, child_name: str, children: list):
        children.extend(parent_node.find_all_children(child_name))

    # Children of dataset node need to be in sequence. This happens "naturally" when ezEML is used as a
    #  wizard, but not when jumping around between sections
    if eml_node:
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            new_children = []
            sequence = (
                names.ALTERNATEIDENTIFIER,
                names.SHORTNAME,
                names.TITLE,
                names.CREATOR,
                names.METADATAPROVIDER,
                names.ASSOCIATEDPARTY,
                names.PUBDATE,
                names.LANGUAGE,
                names.SERIES,
                names.ABSTRACT,
                names.KEYWORDSET,
                names.ADDITIONALINFO,
                names.INTELLECTUALRIGHTS,
                names.LICENSED,
                names.DISTRIBUTION,
                names.COVERAGE,
                names.ANNOTATION,
                names.PURPOSE,
                names.INTRODUCTION,
                names.GETTINGSTARTED,
                names.ACKNOWLEDGEMENTS,
                names.MAINTENANCE,
                names.CONTACT,
                names.PUBLISHER,
                names.PUBPLACE,
                names.METHODS,
                names.PROJECT,
                names.DATATABLE,
                names.OTHERENTITY
            )
            for name in sequence:
                collect_children(dataset_node, name, new_children)
            dataset_node._children = new_children


def clean_model(eml_node):
    """
    Perform various cleanups on the model. This is called when a model is saved. Its purpose is to deal with
    cases where an existing model has glitches due to earlier bugs or because we've changed how we're doing things.
    """
    if not eml_node:
        return
    try:
        # There are some documents that have a spurious filename attribute, which gets propagated if the
        #  document is copied via Save As. Clean it up.
        eml_node.remove_attribute('filename')
    except:
        pass
    # Some documents have, due to earlier bugs, empty publisher, pubPlace, or pubDate nodes
    publisher_nodes = []
    eml_node.find_all_descendants(names.PUBLISHER, publisher_nodes)
    for publisher_node in publisher_nodes:
        if len(publisher_node.children) == 0:
            publisher_node.parent.remove_child(publisher_node)
    pubplace_nodes = []
    eml_node.find_all_descendants(names.PUBPLACE, pubplace_nodes)
    for pubplace_node in pubplace_nodes:
        if not pubplace_node.content:
            pubplace_node.parent.remove_child(pubplace_node)
    pubdate_nodes = []
    eml_node.find_all_descendants(names.PUBDATE, pubdate_nodes)
    for pubdate_node in pubdate_nodes:
        if not pubdate_node.content:
            pubdate_node.parent.remove_child(pubdate_node)
    # Some documents have, due to earlier bugs, keywordSets that contain no keywords
    keyword_sets = []
    eml_node.find_all_descendants(names.KEYWORDSET, keyword_sets)
    for keyword_set in keyword_sets:
        keywords = keyword_set.find_all_children(names.KEYWORD)
        if len(keywords) == 0:
            keyword_set.parent.remove_child(keyword_set)
    # Some documents have, due to earlier bugs, taxonomicCoverage nodes that contain no taxonomicClassification nodes
    taxonomic_coverage_nodes = []
    eml_node.find_all_descendants(names.TAXONOMICCOVERAGE, taxonomic_coverage_nodes)
    for taxonomic_coverage_node in taxonomic_coverage_nodes:
        taxonomic_classification_nodes = taxonomic_coverage_node.find_all_children(names.TAXONOMICCLASSIFICATION)
        if len(taxonomic_classification_nodes) == 0:
            taxonomic_coverage_node.parent.remove_child(taxonomic_coverage_node)
    # Some documents lack the 'unit' attribute for the names.SIZE node
    size_nodes = []
    eml_node.find_all_descendants(names.SIZE, size_nodes)
    for size_node in size_nodes:
        size_node.add_attribute('unit', 'byte')
    # Some documents have codes for categorical attributes that are ints, not strings
    code_nodes = []
    eml_node.find_all_descendants(names.CODE, code_nodes)
    for code_node in code_nodes:
        code = code_node.content
        if isinstance(code, int):
            code_node.content = str(code)
    # Some documents have taxonIds that are ints, not strings
    taxonid_nodes = []
    eml_node.find_all_descendants(names.TAXONID, taxonid_nodes)
    for taxonid_node in taxonid_nodes:
        taxonid = taxonid_node.content
        if isinstance(taxonid, int):
            taxonid_node.content = str(taxonid)
    # Some documents have an empty <funding> node. Remove it.
    funding_nodes = []
    to_remove = []
    eml_node.find_all_descendants(names.FUNDING, funding_nodes)
    for funding_node in funding_nodes:
        if not funding_node.content and len(funding_node.children) == 0:
            to_remove.append(funding_node)
    for node in to_remove:
        node.parent.remove_child(node)
    # Some documents have a <distribution> node that contains only an empty <online> node. Remove it.
    distribution_nodes = []
    to_remove = []
    eml_node.find_all_descendants(names.DISTRIBUTION, distribution_nodes)
    for distribution_node in distribution_nodes:
        online_nodes = distribution_node.find_all_children(names.ONLINE)
        if len(online_nodes) == 1 and not online_nodes[0].content and len(online_nodes[0].children) == 0:
            to_remove.append(distribution_node)
    for node in to_remove:
        node.parent.remove_child(node)

    # The EML standard permits multiple instrumentation nodes, but the ezEML UI does not.
    # If there are multiple instrumentation nodes, we will compromise by putting the
    # instrumentation content in a single node, separated by newlines. The other
    # instrumentation nodes will be deleted.
    method_step_nodes = []
    eml_node.find_all_descendants(names.METHODSTEP, method_step_nodes)
    for method_step_node in method_step_nodes:
        instrumentation = ''
        instrumentation_nodes = method_step_node.find_all_children(names.INSTRUMENTATION)
        index = 0
        for instrumentation_node in instrumentation_nodes:
            if not null_string(instrumentation_node.content):
                instrumentation += f"{instrumentation_node.content}\n"
            if index > 0:
                method_step_node.remove_child(instrumentation_node)
            index += 1
        if instrumentation:
            instrumentation_node = method_step_node.find_child(names.INSTRUMENTATION)
            if instrumentation_node:
                if instrumentation.endswith('\n'):
                    instrumentation = instrumentation[:-1]
                instrumentation_node.content = instrumentation

    # ezEML and EAL both had a bug that caused the attributeDefinition value to be copied into the definition node that
    #  is a child of the textDomain node. They should instead put "text" in that definition node.
    text_domain_nodes = []
    eml_node.find_all_descendants(names.TEXTDOMAIN, text_domain_nodes)
    for text_domain_node in text_domain_nodes:
        definition_node = text_domain_node.find_child(names.DEFINITION)
        if definition_node:
            definition_node.content = 'text'

    # If a project node no longer has any children, remove it.
    project_nodes = []
    eml_node.find_all_descendants(names.PROJECT, project_nodes)
    for project_node in project_nodes:
        if not project_node.children:
            project_node.parent.remove_child(project_node)

    # # Some documents have both a <funding> node and an <award> node. Remove the <funding> node.
    # funding_nodes = []
    # to_remove = []
    # eml_node.find_all_descendants(names.FUNDING, funding_nodes)
    # for funding_node in funding_nodes:
    #     award_nodes = funding_node.parent.find_all_children(names.AWARD)
    #     if len(award_nodes) > 0:
    #         to_remove.append(funding_node)
    # for node in to_remove:
    #     node.parent.remove_child(node)
    # # Some documents have extra tags under intellectualRights that confuse metapype's evaluation function.
    # intellectual_rights_nodes = []
    # eml_node.find_all_descendants(names.INTELLECTUALRIGHTS, intellectual_rights_nodes)
    # for intellectual_rights_node in intellectual_rights_nodes:
    #     ir_content = display_texttype_node(intellectual_rights_node)
    #     if INTELLECTUAL_RIGHTS_CC0 in ir_content:
    #         intellectual_rights_node.content = INTELLECTUAL_RIGHTS_CC0
    #         intellectual_rights_node.remove_children()
    #     elif INTELLECTUAL_RIGHTS_CC_BY in ir_content:
    #         intellectual_rights_node.content = INTELLECTUAL_RIGHTS_CC_BY
    #         intellectual_rights_node.remove_children()


def get_check_metadata_status(eml_node:Node=None, filename:str=None):
    errors, warnings = check_metadata_status(eml_node, filename)
    if errors > 0:
        status = "red"
    elif warnings > 0:
        status = "yellow"
    else:
        status = "green"
    session["check_metadata_status"] = status
    return status


def check_for_nonstring_content(node):
    if node and node.content is not None:
        if not type(node.content) is str:
            raise ValueError(f"{node.name} - {type(node.content)} - {node.content}")
    if node.children:
        for child in node.children:
            check_for_nonstring_content(child)


def fix_nonstring_content(node):
    if node and node.content is not None:
        if not type(node.content) is str:
            node.content = str(node.content)
    if node.children:
        for child in node.children:
            fix_nonstring_content(child)


NSMAP = {
    "eml": "https://eml.ecoinformatics.org/eml-2.2.0",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "stmml": "http://www.xml-cml.org/schema/stmml-1.2"
}


def create_full_xml(eml_node):
    eml_node.nsmap = NSMAP
    eml_node.prefix = 'eml'
    eml_node.extras = {
        "xsi:schemaLocation": "https://eml.ecoinformatics.org/eml-2.2.0 https://eml.ecoinformatics.org/eml-2.2.0/eml.xsd"
    }
    return metapype_io.to_xml(eml_node)


def fixup_eml_namespaces_on_import(eml_node):
    # If we have fetched an EML document created using an older version of the EML schema, we need to
    #  recursively fix up the namespaces.

    def fix_node(node, nsmap):
        node.nsmap = nsmap
        for child in node.children:
            fix_node(child, nsmap)
        return node

    initial_nsmap = eml_node.nsmap
    eml_node = fix_node(eml_node, NSMAP)
    final_nsmap = eml_node.nsmap
    nsmap_changed = \
        initial_nsmap.get('eml') != final_nsmap.get('eml') or initial_nsmap.get('stmml') != final_nsmap.get('stmml')
    return eml_node, nsmap_changed


def fixup_categorical_variables(eml_node):
    """
    There was a bug that caused some Categorical variables to have None as variable type.
    Existing ezEML documents may still contain such variables. Here we fix them.
    """
    # Importing here to sidestep circular import problem.
    from webapp.views.data_tables.dt import change_measurement_scale
    data_table_nodes = []
    file_name = ''
    eml_node.find_all_descendants(names.DATATABLE, data_table_nodes)
    for data_table_node in data_table_nodes:
        attributes_to_fix = []
        non_numeric_domain_nodes = []
        data_table_node.find_all_descendants(names.NONNUMERICDOMAIN, non_numeric_domain_nodes)
        for non_numeric_domain_node in non_numeric_domain_nodes:
            if not non_numeric_domain_node.children:
                # Have an error case. Walk back up the tree to find the containing attribute node.
                nominal_node = non_numeric_domain_node.parent
                if nominal_node:
                    measurement_scale_node = nominal_node.parent
                    if measurement_scale_node:
                        attribute_node = measurement_scale_node.parent
                        if attribute_node:
                            attributes_to_fix.append(attribute_node)
        if attributes_to_fix:
            physical_node = data_table_node.find_child(names.PHYSICAL)
            if physical_node:
                object_name_node = physical_node.find_child(names.OBJECTNAME)
                if object_name_node:
                    file_name = object_name_node.content
            for attribute_node in attributes_to_fix:
                attribute_name_node = attribute_node.find_child(names.ATTRIBUTENAME)
                if attribute_name_node:
                    attribute_name = attribute_name_node.content
                    if file_name and attribute_name:
                        log_info(f'fixup_categorical_variables: fixing "{attribute_name}" in {file_name}')
                    change_measurement_scale(attribute_node, None, VariableType.CATEGORICAL.name)


def fixup_field_delimiters(eml_node):
    field_delimiter_nodes = []
    eml_node.find_all_descendants(names.FIELDDELIMITER, field_delimiter_nodes)
    for field_delimiter_node in field_delimiter_nodes:
        if field_delimiter_node.content and field_delimiter_node.content == '\t':
            field_delimiter_node.content = '\\t'


def save_both_formats(filename:str=None, eml_node:Node=None, use_pickle:bool=False, owner_login:str=None):
    clean_model(eml_node)
    enforce_dataset_sequence(eml_node)
    get_check_metadata_status(eml_node, filename) # To keep badge up-to-date in UI
    fix_up_custom_units(eml_node)
    fixup_categorical_variables(eml_node)
    fixup_field_delimiters(eml_node)
    add_eml_editor_metadata(eml_node)
    if use_pickle:
        pickle_eml(filename, eml_node)
        return
    save_eml(filename=filename, eml_node=eml_node, format='json', owner_login=owner_login)
    save_eml(filename=filename, eml_node=eml_node, format='xml', owner_login=owner_login)


def pickle_eml(filename:str=None, eml_node:Node=None):
    user_folder = user_data.get_user_folder_name()
    if not user_folder:
        user_folder = '.'
    format = 'pkl'
    filename = f'{user_folder}/{filename}.{format}'
    with open(filename, 'wb') as f:
        pickle.dump(eml_node, f)


def save_eml(filename:str=None, eml_node:Node=None, format:str='json', owner_login:str=None):
    if filename:
        if eml_node is not None:
            from webapp.home.views import url_of_interest
            if url_of_interest():
                if Config.MEM_LOG_METAPYPE_STORE_ACTIONS:
                    log_info(f'*** save_eml ***: node store checksum={calculate_node_store_checksum()}    {filename}')

            metadata_str = None

            if format == 'json':
                metadata_str = metapype_io.to_json(eml_node)
            elif format == 'xml':
                xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
                xml_str = create_full_xml(eml_node)
                metadata_str = xml_declaration + xml_str

            if metadata_str:
                user_folder = user_data.get_user_folder_name(owner_login=owner_login)
                if not user_folder:
                    user_folder = '.'
                filename = f'{user_folder}/{filename}.{format}'
                # flash(f'Saving {format} to {filename}')
                with open(filename, "w") as fh:
                    fh.write(metadata_str)
                    fh.flush()
        else:
            raise Exception(f"No EML node was supplied for saving EML.")
    else:
        raise Exception(f"No filename value was supplied for saving EML.")


def evaluate_node(node:Node):
    if node:
        return evaluate.node(node)
    else:
        return 'pass'


def validate_tree(node:Node):
    msg = ''
    if node:
        try:
            validate.tree(node)
            msg = f"{node.name} node is valid"
        except Exception as e:
            msg = str(e)

    return msg


def create_access(parent_node:Node=None):
    access_node = new_child_node(names.ACCESS, parent=parent_node)
    access_node.add_attribute('system', Config.SYSTEM_ATTRIBUTE_VALUE)
    access_node.add_attribute('scope', Config.SCOPE_ATTRIBUTE_VALUE)
    access_node.add_attribute('order', Config.ORDER_ATTRIBUTE_VALUE)
    access_node.add_attribute('authSystem', Config.AUTH_SYSTEM_ATTRIBUTE_VALUE)
    return access_node


def create_eml(filename=None):
    user_data.set_active_document(None)

    eml_node = Node(names.EML)
    eml_node.add_attribute('system', Config.SYSTEM_ATTRIBUTE_VALUE)

    access_node = create_access(parent_node=eml_node)
    initialize_access_rules(access_node)

    _ = new_child_node(names.DATASET, parent=eml_node)

    try:
        save_both_formats(filename=filename, eml_node=eml_node)
    except Exception as e:
        logger.error(e)


def initialize_access_rules(access_node:Node):
    """
    Initialize the access element with default access rules for user and public
    """
    if current_user.is_authenticated:
        user_allow_node = new_child_node(names.ALLOW, parent=access_node)

        user_principal_node = new_child_node(names.PRINCIPAL, parent=user_allow_node)
        userid = current_user.get_dn()
        user_principal_node.content = userid

        user_permission_node = new_child_node(names.PERMISSION, parent=user_allow_node)
        user_permission_node.content = 'all'

    public_allow_node = new_child_node(names.ALLOW, parent=access_node)

    public_principal_node = new_child_node(names.PRINCIPAL, parent=public_allow_node)
    public_principal_node.content = 'public'

    public_permission_node = new_child_node(names.PERMISSION, parent=public_allow_node)
    public_permission_node.content = 'read'


def create_data_table(
    data_table_node:Node=None, 
    entity_name:str=None,
    entity_description:str=None,
    object_name:str=None,
    size:str=None,
    md5_hash:str=None,
    num_header_lines:str=None,
    record_delimiter:str=None,
    quote_character:str=None,
    attribute_orientation:str=None,
    field_delimiter:str=None,
    case_sensitive:str=None,
    number_of_records:str=None,
    online_url:str=None):

    try:

        if not data_table_node:
            data_table_node = Node(names.DATATABLE)

        if entity_name:
            entity_name_node = new_child_node(names.ENTITYNAME, parent=data_table_node)
            entity_name_node.content = entity_name

        if entity_description:
            entity_description_node = new_child_node(names.ENTITYDESCRIPTION, parent=data_table_node)
            entity_description_node.content = entity_description

        if object_name or size or md5_hash or num_header_lines or \
           record_delimiter or attribute_orientation or \
           field_delimiter or online_url:
            physical_node = new_child_node(names.PHYSICAL, parent=data_table_node)

        if object_name:
            object_name_node = new_child_node(names.OBJECTNAME, parent=physical_node)
            object_name_node.content = object_name

        if size:
            size_node = new_child_node(names.SIZE, parent=physical_node)
            size_node.add_attribute('unit', 'byte')
            size_node.content = str(size)

        if md5_hash:
            md5_hash_node = new_child_node(names.AUTHENTICATION, parent=physical_node)
            md5_hash_node.content = md5_hash
            md5_hash_node.add_attribute('method', 'MD5')
            md5_hash_node.content = str(md5_hash)

        if num_header_lines or record_delimiter or \
               attribute_orientation or field_delimiter:
            data_format_node = new_child_node(names.DATAFORMAT, parent=physical_node)
            text_format_node = new_child_node(names.TEXTFORMAT, parent=data_format_node)

        if num_header_lines:
            num_header_lines_node = new_child_node(names.NUMHEADERLINES, parent=text_format_node)
            num_header_lines_node.content = str(num_header_lines)

        if record_delimiter:
            record_delimiter_node = new_child_node(names.RECORDDELIMITER, parent=text_format_node)
            record_delimiter_node.content = record_delimiter

        if attribute_orientation:
            attribute_orientation_node = new_child_node(names.ATTRIBUTEORIENTATION, parent=text_format_node)
            attribute_orientation_node.content = attribute_orientation

        if quote_character or field_delimiter:
            simple_delimited_node = new_child_node(names.SIMPLEDELIMITED, parent=text_format_node)

        if quote_character:
            quote_character_node = new_child_node(names.QUOTECHARACTER, parent=simple_delimited_node)
            quote_character_node.content = quote_character

        if field_delimiter:
            field_delimiter_node = new_child_node(names.FIELDDELIMITER, parent=simple_delimited_node)
            field_delimiter_node.content = field_delimiter

        if online_url:
            distribution_node = new_child_node(names.DISTRIBUTION, parent=physical_node)
            online_node = new_child_node(names.ONLINE, parent=distribution_node)
            url_node = new_child_node(names.URL, parent=online_node)
            url_node.content = online_url

        if case_sensitive:
            case_sensitive_node = new_child_node(names.CASESENSITIVE, parent=data_table_node)
            case_sensitive_node.content = case_sensitive

        if number_of_records:
            number_of_records_node = new_child_node(names.NUMBEROFRECORDS, parent=data_table_node)
            number_of_records_node.content = str(number_of_records)

        return data_table_node

    except Exception as e:
        logger.error(e)


def create_missing_values(attribute_node, code_dict):
    if code_dict:
        for key, code_explanation in code_dict.items():
            code = key
            if code is not None:
                mvc_node = new_child_node(names.MISSINGVALUECODE, parent=attribute_node)
                code_node = new_child_node(names.CODE, parent=mvc_node)
                code_node.content = code
                if code_explanation:
                    code_explanation_node = new_child_node(names.CODEEXPLANATION, parent=mvc_node)
                    code_explanation_node.content = code_explanation


def create_datetime_attribute(
                    attribute_node:Node=None, 
                    attribute_name:str=None,
                    attribute_label:str=None,
                    attribute_definition:str=None,
                    storage_type:str=None,
                    storage_type_system:str=None,
                    format_string:str=None, 
                    datetime_precision:str=None,
                    bounds_minimum:str=None, 
                    bounds_minimum_exclusive:str=None, 
                    bounds_maximum:str=None, 
                    bounds_maximum_exclusive:str=None,
                    code_dict:dict=None):
    if not attribute_node:
        return
    try:
        attribute_name_node = new_child_node(names.ATTRIBUTENAME, parent=attribute_node)
        attribute_name_node.content = attribute_name

        if attribute_label:
            attribute_label_node = new_child_node(names.ATTRIBUTELABEL, parent=attribute_node)
            attribute_label_node.content = attribute_label

        attribute_definition_node = new_child_node(names.ATTRIBUTEDEFINITION, parent=attribute_node)
        attribute_definition_node.content = attribute_definition

        storage_type_node = new_child_node(names.STORAGETYPE, parent=attribute_node)
        storage_type_node.content = storage_type
        if storage_type_system:
            storage_type_node.add_attribute('typeSystem', storage_type_system)

        ms_node = new_child_node(names.MEASUREMENTSCALE, parent=attribute_node)
        datetime_node = new_child_node(names.DATETIME, parent=ms_node)
        format_string_node = new_child_node(names.FORMATSTRING, parent=datetime_node)
        format_string_node.content = format_string

        if datetime_precision:
            datetime_precision_node = new_child_node(names.DATETIMEPRECISION, parent=datetime_node)
            datetime_precision_node.content = datetime_precision

        datetime_domain_node = new_child_node(names.DATETIMEDOMAIN, parent=datetime_node)
        if bounds_minimum or bounds_maximum:
            bounds_node = new_child_node(names.BOUNDS, parent=datetime_domain_node)
        if bounds_minimum:
            bounds_minimum_node = new_child_node(names.MINIMUM, parent=bounds_node)
            bounds_minimum_node.content = bounds_minimum
            if bounds_minimum_exclusive:
                bounds_minimum_node.add_attribute('exclusive', 'true')
            else:
                bounds_minimum_node.add_attribute('exclusive', 'false')
        if bounds_maximum:
            bounds_maximum_node = new_child_node(names.MAXIMUM, parent=bounds_node)
            bounds_maximum_node.content = bounds_maximum
            if bounds_maximum_exclusive:
                bounds_maximum_node.add_attribute('exclusive', 'true')
            else:
                bounds_maximum_node.add_attribute('exclusive', 'false')

        create_missing_values(attribute_node, code_dict)

    except Exception as e:
        logger.error(e)


def create_numerical_attribute(
                    eml_node:Node=None,
                    attribute_node:Node=None, 
                    attribute_name:str=None,
                    attribute_label:str=None,
                    attribute_definition:str=None,
                    storage_type:str=None,
                    storage_type_system:str=None,
                    standard_unit:str=None, 
                    custom_unit:str=None,
                    custom_unit_description:str=None,
                    precision:str=None, 
                    number_type:str=None, 
                    bounds_minimum=None,
                    bounds_minimum_exclusive:str=None, 
                    bounds_maximum=None,
                    bounds_maximum_exclusive:str=None,
                    code_dict:dict=None,
                    mscale:str=None):
    if not attribute_node:
        return
    try:
        add_node(attribute_node, names.ATTRIBUTENAME, attribute_name, Optionality.REQUIRED)
        add_node(attribute_node, names.ATTRIBUTELABEL, attribute_label, Optionality.OPTIONAL)
        add_node(attribute_node, names.ATTRIBUTEDEFINITION, attribute_definition, Optionality.REQUIRED)

        storage_type_node = add_node(attribute_node, names.STORAGETYPE, storage_type, Optionality.OPTIONAL)
        if storage_type_system:
            storage_type_node.add_attribute('typeSystem', storage_type_system)

        mscale_node = new_child_node(names.MEASUREMENTSCALE, attribute_node)
        ratio_node = new_child_node(names.RATIO, mscale_node)
        unit_node = new_child_node(names.UNIT, ratio_node)

        if custom_unit:
            custom_unit_node = new_child_node(names.CUSTOMUNIT, parent=unit_node)
            custom_unit_node.content = custom_unit
            # need additional nodes under additionalMetadata
            handle_custom_unit_additional_metadata(eml_node, custom_unit, custom_unit_description)
        elif standard_unit:
            standard_unit_node = new_child_node(names.STANDARDUNIT, parent=unit_node)
            standard_unit_node.content = standard_unit

        if precision:
            precision_node = new_child_node(names.PRECISION, parent=ratio_node)
            precision_node.content = precision

        numeric_domain_node = new_child_node(names.NUMERICDOMAIN, parent=ratio_node)
        number_type_node = new_child_node(names.NUMBERTYPE, parent=numeric_domain_node)
        number_type_node.content = number_type

        if is_non_empty_bounds(bounds_minimum) or is_non_empty_bounds(bounds_maximum):
            bounds_node = new_child_node(names.BOUNDS, parent=numeric_domain_node)

        if is_non_empty_bounds(bounds_minimum):
            bounds_minimum_node = new_child_node(names.MINIMUM, parent=bounds_node)
            bounds_minimum_node.content = bounds_minimum
            if bounds_minimum_exclusive:
                bounds_minimum_node.add_attribute('exclusive', 'true')
            else:
                bounds_minimum_node.add_attribute('exclusive', 'false')

        if is_non_empty_bounds(bounds_maximum):
            bounds_maximum_node = new_child_node(names.MAXIMUM, parent=bounds_node)
            bounds_maximum_node.content = bounds_maximum
            if bounds_maximum_exclusive:
                bounds_maximum_node.add_attribute('exclusive', 'true')
            else:
                bounds_maximum_node.add_attribute('exclusive', 'false')

        create_missing_values(attribute_node, code_dict)

    except Exception as e:
        logger.error(e)


def add_eml_editor_metadata(eml_node:Node=None):
    eml_editor_node = eml_node.find_descendant('emlEditor')
    if eml_editor_node:
        metadata_node = eml_editor_node.parent
        additional_metadata_node = metadata_node.parent
        eml_node.remove_child(additional_metadata_node)
    additional_metadata_node = new_child_node(names.ADDITIONALMETADATA, parent=eml_node)
    metadata_node = new_child_node(names.METADATA, parent=additional_metadata_node)
    # For the emlEditor node, we need to bypass Metapype validity checking
    eml_editor_node = Node('emlEditor', parent=metadata_node)
    metadata_node.add_child(eml_editor_node)
    eml_editor_node.attributes.clear()
    eml_editor_node.add_attribute('app', 'ezEML')
    eml_editor_node.add_attribute('release', RELEASE_NUMBER)


def add_fetched_from_edi_metadata(eml_node:Node=None, pid:str=None):
    fetched_from_edi_node = eml_node.find_descendant('fetchedFromEDI')
    if fetched_from_edi_node:
        metadata_node = fetched_from_edi_node.parent
        additional_metadata_node = metadata_node.parent
        eml_node.remove_child(additional_metadata_node)
    additional_metadata_node = new_child_node(names.ADDITIONALMETADATA, parent=eml_node)
    metadata_node = new_child_node(names.METADATA, parent=additional_metadata_node)
    # For the fetchedFromEDI node, we need to bypass Metapype validity checking
    fetched_from_edi_node = Node('fetchedFromEDI', parent=metadata_node)
    metadata_node.add_child(fetched_from_edi_node)
    fetched_from_edi_node.attributes.clear()
    fetched_from_edi_node.add_attribute('packageID', pid)
    fetched_from_edi_node.add_attribute('dateFetched', str(date.today()))


def get_fetched_from_edi_metadata(eml_node:Node=None):
    fetched_from_edi_node = eml_node.find_descendant('fetchedFromEDI')
    msg = ''
    if fetched_from_edi_node:
        pid = fetched_from_edi_node.attribute_value('packageID')
        date = fetched_from_edi_node.attribute_value('dateFetched')
        if pid and date:
            msg = f'\n\n\nThis data package is based on package {pid} fetched from EDI on {date}.'
    return msg


def check_taxonomic_coverage_consistency_with_ezeml(eml_node, package_name):
    # If there is no taxonomicCoverage in the package, or if there is taxonomicCoverage but it adheres to the pattern
    #  expected by ezEML, we don't want to block access to editing of taxonomic coverage
    taxonomic_coverage_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.COVERAGE, names.TAXONOMICCOVERAGE])
    if not taxonomic_coverage_nodes:
        clear_taxonomy_imported_from_xml(eml_node, package_name)
        return True
    else:
        ezeml_valid = True
        for taxonomic_coverage_node in taxonomic_coverage_nodes:
            taxonomic_classification_nodes = taxonomic_coverage_node.find_all_children(names.TAXONOMICCLASSIFICATION)
            if len(taxonomic_classification_nodes) > 1:
                ezeml_valid = False
                break
        if ezeml_valid:
            clear_taxonomy_imported_from_xml(eml_node, package_name)
        return ezeml_valid


def add_imported_from_xml_metadata(eml_node:Node=None, xml_filename:str=None, package_name:str=None):
    imported_from_xml_node = eml_node.find_descendant('importedFromXML')
    if imported_from_xml_node:
        metadata_node = imported_from_xml_node.parent
        additional_metadata_node = metadata_node.parent
        eml_node.remove_child(additional_metadata_node)
    additional_metadata_node = new_child_node(names.ADDITIONALMETADATA, parent=eml_node)
    metadata_node = new_child_node(names.METADATA, parent=additional_metadata_node)
    # For the importedFromXML node, we need to bypass Metapype validity checking
    imported_from_xml_node = Node('importedFromXML', parent=metadata_node)
    metadata_node.add_child(imported_from_xml_node)
    imported_from_xml_node.attributes.clear()
    imported_from_xml_node.add_attribute('filename', xml_filename)
    imported_from_xml_node.add_attribute('dateImported', str(date.today()))
    check_taxonomic_coverage_consistency_with_ezeml(eml_node, package_name)


def get_imported_from_xml_metadata(eml_node:Node=None):
    imported_from_xml_node = eml_node.find_descendant('importedFromXML')
    msg = ''
    if imported_from_xml_node:
        filename = imported_from_xml_node.attribute_value('filename')
        date = imported_from_xml_node.attribute_value('dateImported')
        if filename and date:
            msg = f'\n\n\nThis data package is based on EML XML imported from {filename} on {date}.'
    return msg


def was_imported_from_xml(eml_node):
    imported_from_xml_node = eml_node.find_descendant('importedFromXML')
    if imported_from_xml_node:
        return True
    else:
        return False


def clear_taxonomy_imported_from_xml(eml_node, package_name=None):
    # If the package was imported from XML, add a flag indicating that the taxonomic coverage is OK for ezEML
    imported_from_xml_node = eml_node.find_descendant('importedFromXML')
    if imported_from_xml_node:
        imported_from_xml_node.add_attribute('taxonomicCoverageExempt', True)
        if package_name:
            save_both_formats(package_name, eml_node)


def taxonomy_imported_from_xml(eml_node, package_name):
    imported_from_xml_node = eml_node.find_descendant('importedFromXML')
    if imported_from_xml_node:
        if imported_from_xml_node.attribute_value('taxonomicCoverageExempt'):
            return False
        else:
            # There exist packages that were imported from XML before we checked the taxonomic coverage
            #  for consistency with ezEML, so we'll do it here.
            return not check_taxonomic_coverage_consistency_with_ezeml(eml_node, package_name)
    else:
        return False


def fix_up_custom_units(eml_node:Node=None):
    # The additionalMetadata nodes are handled differently from how they were handled initially.
    # Pre-existing data packages need to be fixed up. Newly-created data packages will be correct, but
    #  we need to check if this package needs fixup.
    # In addition, we check here whether we have custom units in the additionalMetadata that are no
    #  longer needed, because they no longer appear in a data table.
    # And if there are no custom units in the additionalMetadata, we remove the additionalMetadata node.
    unitlist_node = eml_node.find_descendant(names.UNITLIST)
    if unitlist_node:
        metadata_node = unitlist_node.parent
        # If there's an emlEditor node that's a sibling to unitlist_node, remove it
        eml_editor_node = metadata_node.find_child('emlEditor')
        if eml_editor_node:
            metadata_node.remove_child(eml_editor_node)
        # Remove custom unit nodes that are no longer needed
        custom_unit_nodes = []
        eml_node.find_all_descendants(names.CUSTOMUNIT, custom_unit_nodes)
        custom_units = []
        for custom_unit_node in custom_unit_nodes:
            custom_units.append(custom_unit_node.content)
        unit_nodes = unitlist_node.find_all_children(names.UNIT)
        for unit_node in unit_nodes:
            if unit_node.attribute_value('id') not in custom_units:
                unitlist_node.remove_child(unit_node)
        # If there are no custom units, remove the unitlist, metadata, and additionalMetadata nodes if they're empty
        unit_nodes = unitlist_node.find_all_children(names.UNIT)
        if len(unit_nodes) == 0:
            metadata_node.remove_child(unitlist_node)
            if not metadata_node.children:
                additional_metadata_node = metadata_node.parent
                additional_metadata_node.remove_child(metadata_node)
                if not additional_metadata_node.children:
                    eml_node.remove_child(additional_metadata_node)


def handle_custom_unit_additional_metadata(eml_node:Node=None, custom_unit_name:str=None, custom_unit_description:str=None):
    additional_metadata_nodes = []
    eml_node.find_all_descendants(names.ADDITIONALMETADATA, additional_metadata_nodes)
    metadata_node = None
    unitlist_node = None
    prefix = None
    for additional_metadata_node in additional_metadata_nodes:
        metadata_node = additional_metadata_node.find_child(names.METADATA)
        unitlist_node = metadata_node.find_child(names.UNITLIST)
        if unitlist_node:
            prefix = unitlist_node.prefix
            break
    if not unitlist_node:
        unitlist_node = add_node(metadata_node, names.UNITLIST, None, Optionality.FORCE)
    unit_nodes = []
    unitlist_node.find_all_descendants(names.UNIT, unit_nodes)

    found = False
    for unit_node in unit_nodes:
        if unit_node.attribute_value('id') == custom_unit_name:
            unit_node.add_attribute('name', custom_unit_name)
            description_node = unit_node.find_child(names.DESCRIPTION)
            if description_node:
                unit_node.remove_child(description_node)
            description_node = add_node(unit_node, names.DESCRIPTION, custom_unit_description, Optionality.FORCE)
            found = True
            break
    if not found:
        unit_node = Node(names.UNIT, parent=unitlist_node)
        unitlist_node.add_child(unit_node)
        unit_node.add_attribute('id', custom_unit_name)
        unit_node.add_attribute('name', custom_unit_name)
        description_node = add_node(unit_node, names.DESCRIPTION, custom_unit_description, Optionality.FORCE)

    if description_node:
        # e.g., unit element may be "stmml:unit", in which case we want
        # the description to be "stmml:description"
        description_node.prefix = prefix

    # save custom unit names and descriptions in session so we can do some javascript magic
    custom_units = session.get("custom_units", {})
    custom_units[custom_unit_name] = custom_unit_description
    session["custom_units"] = custom_units


def create_categorical_or_text_attribute(
                    attribute_node:Node=None, 
                    attribute_name:str=None,
                    attribute_label:str=None,
                    attribute_definition:str=None,
                    storage_type:str=None,
                    storage_type_system:str=None,
                    enforced:str=None, 
                    code_dict:dict=None,
                    mscale:str=None,
                    enumerated_domain_node:Node=None):
    if not attribute_node:
        return
    try:
        attribute_name_node = new_child_node(names.ATTRIBUTENAME, parent=attribute_node)
        attribute_name_node.content = attribute_name

        if attribute_label:
            attribute_label_node = new_child_node(names.ATTRIBUTELABEL, parent=attribute_node)
            attribute_label_node.content = attribute_label

        attribute_definition_node = new_child_node(names.ATTRIBUTEDEFINITION, parent=attribute_node)
        attribute_definition_node.content = attribute_definition

        storage_type_node = new_child_node(names.STORAGETYPE, parent=attribute_node)
        storage_type_node.content = storage_type
        if storage_type_system:
            storage_type_node.add_attribute('typeSystem', storage_type_system)

        mscale_node = new_child_node(names.MEASUREMENTSCALE, parent=attribute_node)

        nominal_node = new_child_node(names.NOMINAL, parent=mscale_node)
        non_numeric_domain_node = new_child_node(names.NONNUMERICDOMAIN, parent=nominal_node)

        if mscale == VariableType.CATEGORICAL.name:

            # get rid of textDomain node, if any
            text_domain_node = attribute_node.find_child(names.TEXTDOMAIN)
            if text_domain_node:
                attribute_node.remove_child(text_domain_node)

            if enumerated_domain_node:
                non_numeric_domain_node.add_child(enumerated_domain_node)
            else:
                enumerated_domain_node = new_child_node(names.ENUMERATEDDOMAIN, parent=non_numeric_domain_node)
            if enforced:
                enumerated_domain_node.add_attribute('enforced', enforced)

        elif mscale == VariableType.TEXT.name:

            text_domain_node = new_child_node(names.TEXTDOMAIN, parent=non_numeric_domain_node)
            definition_node = new_child_node(names.DEFINITION, parent=text_domain_node)
            definition_node.content = "text"

            # get rid of enumeratedDomain node, if any
            enumerated_domain_node = non_numeric_domain_node.find_child(names.ENUMERATEDDOMAIN)
            if enumerated_domain_node:
                non_numeric_domain_node.remove_child(enumerated_domain_node)

        create_missing_values(attribute_node, code_dict)

    except Exception as e:
        logger.error(e)


def create_code_definition(code_definition_node:Node=None,
                           code:str='',
                           definition:str='',
                           order:str=''):
    if code_definition_node:
        code_node = new_child_node(names.CODE, parent=code_definition_node)
        code_node.content = code
        definition_node = new_child_node(names.DEFINITION, parent=code_definition_node)
        definition_node.content = definition
        if order:
            code_definition_node.add_attribute('order', order)


def is_non_empty_bounds(bounds=None):
    if bounds:
        return bounds
    elif type(bounds) is str:
        return bounds in ["0.0", "0"]
    elif type(bounds) is float:
        return bounds == 0.0
    elif type(bounds) is int:
        return bounds == 0


def create_title(title=None, filename=None):
    eml_node = load_eml(filename=filename)
    title_node = None

    dataset_node = eml_node.find_child('dataset')
    if dataset_node:
        title_node = dataset_node.find_child('title')
        if not title_node:
            title_node = new_child_node(names.TITLE, parent=dataset_node)
    else:
        dataset_node = new_child_node(names.DATASET, parent=eml_node)
        title_node = new_child_node(names.TITLE, parent=dataset_node)

    title_node.content = title

    try:
        save_both_formats(filename=filename, eml_node=eml_node)
    except Exception as e:
        logger.error(e)

    return title_node


def create_data_package_id(data_package_id=None, filename=None):
    eml_node = load_eml(filename=filename)
    if data_package_id:
        eml_node.add_attribute('packageId', data_package_id)
    else:
        eml_node.remove_attribute('packageId')

    try:
        save_both_formats(filename=filename, eml_node=eml_node)
    except Exception as e:
        logger.error(e)


def create_pubinfo(pubplace=None, pubdate=None, filename=None):
    eml_node = load_eml(filename=filename)

    dataset_node = eml_node.find_child('dataset')
    if dataset_node:
        pubplace_node = dataset_node.find_child('pubPlace')
        if not pubplace_node:
            pubplace_node = new_child_node(names.PUBPLACE, parent=dataset_node)
        pubdate_node = dataset_node.find_child(names.PUBDATE)
        if not pubdate_node:
            pubdate_node = new_child_node(names.PUBDATE, parent=dataset_node)

    else:
        dataset_node = new_child_node(names.DATASET, parent=eml_node)
        pubplace_node = new_child_node(names.PUBPLACE, parent=dataset_node)
        pubdate_node = new_child_node(names.PUBDATE, parent=dataset_node)

    if pubplace:
        pubplace_node.content = pubplace
    else:
        dataset_node.remove_child(pubplace_node)
    if pubdate:
        pubdate_node.content = pubdate
    else:
        dataset_node.remove_child(pubdate_node)

    try:
        save_both_formats(filename=filename, eml_node=eml_node)
    except Exception as e:
        logger.error(e)

    return pubplace_node, pubdate_node


def create_pubplace(pubplace=None, filename=None):
    eml_node = load_eml(filename=filename)

    dataset_node = eml_node.find_child('dataset')
    if dataset_node:
        pubplace_node = dataset_node.find_child('pubPlace')
        if not pubplace_node:
            pubplace_node = new_child_node(names.PUBPLACE, parent=dataset_node)
    else:
        dataset_node = new_child_node(names.DATASET, parent=eml_node)
        pubplace_node = new_child_node(names.PUBPLACE, parent=dataset_node)

    pubplace_node.content = pubplace

    try:
        save_both_formats(filename=filename, eml_node=eml_node)
    except Exception as e:
        logger.error(e)

    return pubplace_node


def create_pubdate(pubdate=None, filename=None):
    eml_node = load_eml(filename=filename)

    dataset_node = eml_node.find_child(names.DATASET)
    if dataset_node:
        pubdate_node = dataset_node.find_child(names.PUBDATE)
        if not pubdate_node:
            pubdate_node = new_child_node(names.PUBDATE, parent=dataset_node)
    else:
        dataset_node = new_child_node(names.DATASET, parent=eml_node)
        pubdate_node = new_child_node(names.PUBDATE, parent=dataset_node)

    pubdate_node.content = pubdate

    try:
        save_both_formats(filename=filename, eml_node=eml_node)
    except Exception as e:
        logger.error(e)


def create_other_entity(
    entity_node:Node=None, 
    entity_name:str=None,
    entity_type:str=None,
    entity_description:str=None,
    object_name:str=None,
    format_name:str=None,
    size:str=None,
    md5_hash:str=None,
    online_url:str=None):

    try:

        if not entity_node:
            entity_node = Node(names.OTHERENTITY)

        if entity_name:
            entity_name_node = new_child_node(names.ENTITYNAME, parent=entity_node)
            entity_name_node.content = entity_name

        if entity_type:
            entity_type_node = new_child_node(names.ENTITYTYPE, parent=entity_node)
            entity_type_node.content = entity_type

        if entity_description:
            entity_description_node = new_child_node(names.ENTITYDESCRIPTION, parent=entity_node)
            entity_description_node.content = entity_description

        if object_name or format_name or online_url:

            physical_node = new_child_node(names.PHYSICAL, parent=entity_node)

            if object_name:
                object_name_node = new_child_node(names.OBJECTNAME, parent=physical_node)
                object_name_node.content = object_name

            if format_name:
                data_format_node = new_child_node(names.DATAFORMAT, parent=physical_node)
                externally_defined_format_node = new_child_node(names.EXTERNALLYDEFINEDFORMAT, parent=data_format_node)
                format_name_node = new_child_node(names.FORMATNAME, parent=externally_defined_format_node)
                format_name_node.content = format_name

            if size:
                size_node = new_child_node(names.SIZE, parent=physical_node)
                size_node.add_attribute('unit', 'byte')
                size_node.content = size

            if md5_hash:
                hash_node = new_child_node(names.AUTHENTICATION, parent=physical_node)
                hash_node.add_attribute('method', 'MD5')
                hash_node.content = str(md5_hash)

        if online_url:
            distribution_node = new_child_node(names.DISTRIBUTION, parent=physical_node)
            online_node = new_child_node(names.ONLINE, parent=distribution_node)
            url_node = new_child_node(names.URL, parent=online_node)
            url_node.content = online_url

        return entity_node

    except Exception as e:
        logger.error(e)


def create_abstract(filename:str=None, abstract:str=None):
    eml_node = load_eml(filename=filename)

    dataset_node = eml_node.find_child(names.DATASET)
    if dataset_node:
        abstract_node = dataset_node.find_child(names.ABSTRACT)
        if not abstract_node:
            abstract_node = new_child_node(names.ABSTRACT, parent=dataset_node)
    else:
        dataset_node = new_child_node(names.DATASET, parent=eml_node)
        abstract_node = new_child_node(names.ABSTRACT, parent=dataset_node)

    abstract_node.content = abstract
    valid, msg = is_valid_xml_fragment(abstract, names.ABSTRACT)
    if valid:
        try:
            post_process_texttype_node(abstract_node)
            try:
                save_both_formats(filename=filename, eml_node=eml_node)
            except Exception as e:
                logger.error(e)
        except exceptions.InvalidXMLError as e:
            logger.error(e)
            flash(invalid_xml_error_message(str(e)), 'error')
            return
    else:
        flash(invalid_xml_error_message(msg), 'error')


def create_intellectual_rights(filename:str=None, intellectual_rights:str=None):
    eml_node = load_eml(filename=filename)

    dataset_node = eml_node.find_child(names.DATASET)
    if dataset_node:
        intellectual_rights_node = dataset_node.find_child(names.INTELLECTUALRIGHTS)
        if not intellectual_rights_node:
            intellectual_rights_node = new_child_node(names.INTELLECTUALRIGHTS, parent=dataset_node)
    else:
        dataset_node = new_child_node(names.DATASET, parent=eml_node)
        intellectual_rights_node = new_child_node(names.INTELLECTUALRIGHTS, parent=dataset_node)

    intellectual_rights_node.content = intellectual_rights
    intellectual_rights_node.children = []
    if intellectual_rights != INTELLECTUAL_RIGHTS_CC0 and intellectual_rights != INTELLECTUAL_RIGHTS_CC_BY:
        valid, msg = is_valid_xml_fragment(intellectual_rights, names.INTELLECTUALRIGHTS)
        if valid:
            try:
                post_process_texttype_node(intellectual_rights_node)
            except exceptions.InvalidXMLError as e:
                logger.error(e)
                flash(invalid_xml_error_message(str(e)), 'error')
                return
        else:
            flash(invalid_xml_error_message(msg), 'error')
    try:
        save_both_formats(filename=filename, eml_node=eml_node)
    except Exception as e:
        logger.error(e)


def create_maintenance(dataset_node:Node=None, description:str=None, update_frequency:str=None):
    try:
        if dataset_node:
            maintenance_node = add_node(dataset_node, names.MAINTENANCE)
            description_node = add_node(maintenance_node, names.DESCRIPTION, description)
            post_process_texttype_node(description_node)

            if update_frequency:
                update_frequency_node = add_node(maintenance_node, names.MAINTENANCEUPDATEFREQUENCY, update_frequency)

    except Exception as e:
        logger.error(e)


def create_project(dataset_node:Node=None, title:str=None, abstract:str=None, funding:str=None):
    try:
        if dataset_node:
            project_node = dataset_node.find_child(names.PROJECT)
            if not project_node:
                project_node = new_child_node(names.PROJECT, parent=dataset_node)

        title_node = project_node.find_child(names.TITLE)
        if not title_node:
            title_node = new_child_node(names.TITLE, parent=project_node)
        if title:
            title_node.content = title
        else:
            # Don't keep the title node if it's empty. The user may be trying to clear out the project altogether.
            project_node.remove_child(title_node)

        abstract_node = project_node.find_child(names.ABSTRACT)
        if not abstract_node:
            abstract_node = new_child_node(names.ABSTRACT, parent=project_node)
        if abstract:
            abstract_node.content = abstract
            post_process_texttype_node(abstract_node)
        else:
            project_node.remove_child(abstract_node)

        funding_node = project_node.find_child(names.FUNDING)
        if not funding_node:
            funding_node = new_child_node(names.FUNDING, parent=project_node)
        if funding:
            funding_node.content = funding
            post_process_texttype_node(funding_node)
        else:
            project_node.remove_child(funding_node)

        # If project node is now empty, remove it.
        if not project_node.children:
            dataset_node.remove_child(project_node)

    except Exception as e:
        logger.error(e)


def create_related_project(dataset_node:Node=None, title:str=None, abstract:str=None, funding:str=None, project_node_id:str=None):
    try:
        if project_node_id != '1':
            related_project_node = Node.get_node_instance(project_node_id)
        else:
            if dataset_node:
                project_node = dataset_node.find_child(names.PROJECT)
                if not project_node:
                    project_node = new_child_node(names.PROJECT, parent=dataset_node)
                related_project_node = new_child_node(names.RELATED_PROJECT, parent=project_node)

        title_node = related_project_node.find_child(names.TITLE)
        if not title_node:
            title_node = new_child_node(names.TITLE, parent=related_project_node)
        title_node.content = title

        abstract_node = related_project_node.find_child(names.ABSTRACT)
        if not abstract_node:
            abstract_node = new_child_node(names.ABSTRACT, parent=related_project_node)
        if abstract:
            abstract_node.content = abstract
            post_process_texttype_node(abstract_node)
        else:
            related_project_node.remove_child(abstract_node)

        funding_node = related_project_node.find_child(names.FUNDING)
        if not funding_node:
            funding_node = new_child_node(names.FUNDING, parent=related_project_node)
        if funding:
            funding_node.content = funding
            post_process_texttype_node(funding_node)
        else:
            related_project_node.remove_child(funding_node)

        return related_project_node

    except Exception as e:
        logger.error(e)


def create_funding_award(
        award_node:Node=None,
        funder_name:str=None,
        award_title:str=None,
        funder_identifier:str=None,
        award_number:str=None,
        award_url:str=None):

    try:
        funder_name_node = new_child_node(names.FUNDERNAME, parent=award_node)
        funder_name_node.content = funder_name

        if funder_identifier:
            ids = funder_identifier.split(',')
            for id in ids:
                funder_identifier_node = new_child_node(names.FUNDERIDENTIFIER, parent=award_node)
                funder_identifier_node.content = id

        if award_number:
            award_number_node = new_child_node(names.AWARDNUMBER, parent=award_node)
            award_number_node.content = award_number

        award_title_node = new_child_node(names.TITLE, parent=award_node)
        award_title_node.content = award_title

        if award_url:
            award_url_node = new_child_node(names.AWARDURL, parent=award_node)
            award_url_node.content = award_url

    except Exception as e:
        logger.error(e)


def add_keyword(filename:str=None, keyword:str=None, keyword_type:str=None):
    if keyword:
        eml_node = load_eml(filename=filename)

        dataset_node = eml_node.find_child(names.DATASET)
        if not dataset_node:
            dataset_node = new_child_node(names.DATASET, parent=eml_node)

        keywordset_node = dataset_node.find_child(names.KEYWORDSET)
        if not keywordset_node:
            keywordset_node = new_child_node(names.KEYWORDSET, parent=dataset_node)

        keyword_node = None
        
        # Does a matching keyword node already exist?
        keyword_nodes = keywordset_node.find_all_children(names.KEYWORD)
        for child_node in keyword_nodes:
            if child_node.content == keyword:
                keyword_node = child_node
                break
        
        if not keyword_node:
            keyword_node = new_child_node(names.KEYWORD, parent=keywordset_node)
            keyword_node.content = keyword

        if keyword_type:
            keyword_node.add_attribute(name='keywordType', value=keyword_type)

    try:
        save_both_formats(filename=filename, eml_node=eml_node)
    except Exception as e:
        logger.error(e)


def remove_keyword(filename:str=None, keyword:str=None):
    if keyword:
        eml_node = load_eml(filename=filename)
        keywordset_node = eml_node.find_single_node_by_path([
            names.DATASET, names.KEYWORDSET
        ])
        if keywordset_node:
            current_keywords = \
                keywordset_node.find_all_children(child_name=names.KEYWORD)
            for keyword_node in current_keywords:
                if keyword_node.content == keyword:
                    keywordset_node.remove_child(keyword_node)

    try:
        save_both_formats(filename=filename, eml_node=eml_node)
    except Exception as e:
        logger.error(e)


def remove_related_project(filename:str=None, node_id:str=None):
    eml_node = load_eml(filename=filename)
    related_project_node = Node.get_node_instance(node_id)
    if related_project_node:
        parent_node = related_project_node.parent
        if parent_node:
            parent_node.remove_child(related_project_node)
            try:
                if eml_node:
                    save_both_formats(filename=filename, eml_node=eml_node)
            except Exception as e:
                logger.error(e)


def create_keywords(filename:str=None, keywords_list:list=[]):
    eml_node = load_eml(filename=filename)

    dataset_node = eml_node.find_child(names.DATASET)
    if dataset_node:
        keywordset_node = dataset_node.find_child(names.KEYWORDSET)
        if keywordset_node:
            # Get rid of the old keyword set if it exists
            dataset_node.remove_child(keywordset_node)
    else:
        dataset_node = new_child_node(names.DATASET, parent=eml_node)

    if keywords_list:
        keywordset_node = new_child_node(names.KEYWORDSET, parent=dataset_node)
        for keyword in keywords_list:
            keyword_node = new_child_node(names.KEYWORD, parent=keywordset_node)
            keyword_node.content = keyword

    try:
        save_both_formats(filename=filename, eml_node=eml_node)
    except Exception as e:
        logger.error(e)


def is_float(val):
    try:
        float(val)
        return True
    except Exception as e:
        return False


def create_geographic_coverage(
        geographic_coverage_node:Node=None,
        geographic_description:str=None,
        wbc:str=None,
        ebc:str=None,
        nbc:str=None,
        sbc:str=None,
        amin:str=None,
        amax:str=None,
        aunits:str=None
    ):
    try:
        geographic_description_node = new_child_node(names.GEOGRAPHICDESCRIPTION, parent=geographic_coverage_node)
        geographic_description_node.content = geographic_description

        bounding_coordinates_node = new_child_node(names.BOUNDINGCOORDINATES, parent=geographic_coverage_node)

        wbc_node = new_child_node(names.WESTBOUNDINGCOORDINATE, parent=bounding_coordinates_node)
        wbc_node.content = wbc

        ebc_node = new_child_node(names.EASTBOUNDINGCOORDINATE, parent=bounding_coordinates_node)
        ebc_node.content = ebc

        nbc_node = new_child_node(names.NORTHBOUNDINGCOORDINATE, parent=bounding_coordinates_node)
        nbc_node.content = nbc

        sbc_node = new_child_node(names.SOUTHBOUNDINGCOORDINATE, parent=bounding_coordinates_node)
        sbc_node.content = sbc

        if is_float(amin) or is_float(amax) or aunits:
            bounding_altitudes_node = new_child_node(names.BOUNDINGALTITUDES, parent=bounding_coordinates_node)

        if is_float(amin):
            amin_node = new_child_node(names.ALTITUDEMINIMUM, parent=bounding_altitudes_node)
            amin_node.content = amin

        if is_float(amax):
            amax_node = new_child_node(names.ALTITUDEMAXIMUM, parent=bounding_altitudes_node)
            amax_node.content = amax

        if aunits:
            aunits_node = new_child_node(names.ALTITUDEUNITS, parent=bounding_altitudes_node)
            aunits_node.content = aunits

        return geographic_coverage_node

    except Exception as e:
        logger.error(e)


def create_temporal_coverage(
                   temporal_coverage_node:Node=None,
                   begin_date:str=None,
                   end_date:str=None):
    try:
        if begin_date and end_date:
            range_of_dates_node = new_child_node(names.RANGEOFDATES, parent=temporal_coverage_node)

            begin_date_node = new_child_node(names.BEGINDATE, parent=range_of_dates_node)
            begin_calendar_date_node = new_child_node(names.CALENDARDATE, parent=begin_date_node)
            begin_calendar_date_node.content = begin_date

            end_date_node = new_child_node(names.ENDDATE, parent=range_of_dates_node)
            end_calendar_date_node = new_child_node(names.CALENDARDATE, parent=end_date_node)
            end_calendar_date_node.content = end_date

        elif begin_date:
            single_datetime_node = new_child_node(names.SINGLEDATETIME, parent=temporal_coverage_node)
            calendar_date_node = new_child_node(names.CALENDARDATE, parent=single_datetime_node)
            calendar_date_node.content = begin_date

        return temporal_coverage_node

    except Exception as e:
        logger.error(e)


def create_taxonomic_coverage(
                taxonomic_coverage_node:Node,
                general_taxonomic_coverage:str,
                hierarchy,
                global_authority):
    try:
        if taxonomic_coverage_node:
            if general_taxonomic_coverage:
                general_taxonomic_coverage_node = new_child_node(names.GENERALTAXONOMICCOVERAGE,
                                                       parent=taxonomic_coverage_node)
                general_taxonomic_coverage_node.content = general_taxonomic_coverage

            taxonomic_classification_parent_node = taxonomic_coverage_node
            for entry in hierarchy[::-1]:
                if len(entry) == 4:
                    taxon_rank, taxon_name, common_name, taxon_id = entry
                if len(entry) == 6:
                    taxon_rank, taxon_name, common_name, taxon_id, _, authority = entry
                taxonomic_classification_node = new_child_node(names.TAXONOMICCLASSIFICATION, parent=taxonomic_classification_parent_node)
                taxon_rank_name_node = new_child_node(names.TAXONRANKNAME, parent=taxonomic_classification_node)
                taxon_rank_name_node.content = taxon_rank
                taxon_rank_value_node = new_child_node(names.TAXONRANKVALUE, parent=taxonomic_classification_node)
                taxon_rank_value_node.content = taxon_name.strip()
                if common_name:
                    common_name_node = new_child_node(names.COMMONNAME, parent=taxonomic_classification_node)
                    common_name_node.content = common_name
                if not authority:
                    authority = global_authority
                if taxon_id and authority:
                    taxon_id_node = new_child_node(names.TAXONID, parent=taxonomic_classification_node)
                    taxon_id_node.content = taxon_id
                    if authority == 'EOL':
                        provider_uri = "https://eol.org"
                    elif authority == 'ITIS':
                        provider_uri = "https://www.itis.gov"
                    elif authority == 'NCBI':
                        provider_uri = "https://www.ncbi.nlm.nih.gov/taxonomy"
                    elif authority == "PLANTS":
                        provider_uri = "https://plants.usda.gov"
                    elif authority == 'WORMS':
                        provider_uri = "http://www.marinespecies.org"
                    taxon_id_node.add_attribute(names.PROVIDER, provider_uri)
                taxonomic_classification_parent_node = taxonomic_classification_node

        return taxonomic_coverage_node

    except Exception as e:
        logger.error(e)


def create_responsible_party(responsible_party_node:Node=None,
                             filename:str=None,
                             salutation:str=None,
                             gn:str=None,
                             mn:str=None,
                             sn:str=None,
                             user_id:str=None,
                             organization:str=None,
                             org_id:str=None,
                             org_id_type:str=None,
                             position_name:str=None,
                             address_1:str=None,
                             address_2:str=None,
                             city:str=None,
                             state:str=None,
                             postal_code:str=None,
                             country:str=None,
                             phone:str=None,
                             fax:str=None,
                             email:str=None,
                             online_url:str=None,
                             role:str=None):
    try:
        if salutation or gn or mn or sn:
            individual_name_node = new_child_node(names.INDIVIDUALNAME, parent=responsible_party_node)
        if salutation:
            salutation_node = new_child_node(names.SALUTATION, parent=individual_name_node)
            salutation_node.content = salutation
        if gn:
            given_name_node = new_child_node(names.GIVENNAME, parent=individual_name_node)
            given_name_node.content = gn
        if mn:
            given_name_node = new_child_node(names.GIVENNAME, parent=individual_name_node)
            given_name_node.content = mn
        if sn:
            surname_node = new_child_node(names.SURNAME, parent=individual_name_node)
            surname_node.content = sn

        if user_id:
            user_id_node = new_child_node(names.USERID, parent=responsible_party_node)
            user_id_node.content = user_id
            user_id_node.add_attribute('directory', 'https://orcid.org')

        if organization:
            organization_name_node = new_child_node(names.ORGANIZATIONNAME, parent=responsible_party_node)
            organization_name_node.content = organization

        if org_id:
            user_id_node = new_child_node(names.USERID, parent=responsible_party_node)
            user_id_node.content = org_id
            if org_id_type:
                user_id_node.add_attribute('directory', org_id_type)

        if position_name:
            position_name_node = new_child_node(names.POSITIONNAME, parent=responsible_party_node)
            position_name_node.content = position_name

        if address_1 or address_2 or city or state or postal_code or country:
            address_node = new_child_node(names.ADDRESS, parent=responsible_party_node)

        if address_1:
            delivery_point_node_1 = new_child_node(names.DELIVERYPOINT, parent=address_node)
            delivery_point_node_1.content = address_1

        if address_2:
            delivery_point_node_2 = new_child_node(names.DELIVERYPOINT, parent=address_node)
            delivery_point_node_2.content = address_2

        if city:
            city_node = new_child_node(names.CITY, parent=address_node)
            city_node.content = city

        if state:
            administrative_area_node = new_child_node(names.ADMINISTRATIVEAREA, parent=address_node)
            administrative_area_node.content = state

        if postal_code:
            postal_code_node = new_child_node(names.POSTALCODE, parent=address_node)
            postal_code_node.content = postal_code

        if country:
            country_node = new_child_node(names.COUNTRY, parent=address_node)
            country_node.content = country

        if phone:
            phone_node = new_child_node(names.PHONE, parent=responsible_party_node)
            phone_node.content = phone
            phone_node.add_attribute('phonetype', 'voice')

        if fax:
            fax_node = new_child_node(names.PHONE, parent=responsible_party_node)
            fax_node.content = fax
            fax_node.add_attribute('phonetype', 'facsimile')

        if email:
            email_node = new_child_node(names.ELECTRONICMAILADDRESS, parent=responsible_party_node)
            email_node.content = email

        if online_url:
            online_url_node = new_child_node(names.ONLINEURL, parent=responsible_party_node)
            online_url_node.content = online_url

        if role:
            role_node = new_child_node(names.ROLE, parent=responsible_party_node)
            role_node.content = role

        return responsible_party_node

    except Exception as e:
        logger.error(e)


def list_funding_awards(eml_node:Node=None, node_id=None):
    award_list = []
    if eml_node:
        if node_id:
            project_node = Node.get_node_instance(node_id)
        else:
            project_node = eml_node.find_single_node_by_path([
                names.DATASET, names.PROJECT
            ])
        if not project_node:
            return []
        award_nodes = project_node.find_all_children(names.AWARD)
        if award_nodes:
            for i, award_node in enumerate(award_nodes):
                Awards_Entry = collections.namedtuple(
                    "AwardEntry",
                    ["id", "funder_name", "funder_identifier", "award_number", "award_title", "award_url", "upval", "downval"],
                    rename=False)
                id = award_node.id
                funder_name = ''
                funder_identifier = ''  # FIX ME - list of ids
                award_number = ''
                award_title = ''
                award_url = ''
                funder_name_node = award_node.find_child(names.FUNDERNAME)
                if funder_name_node:
                    funder_name = funder_name_node.content
                funder_identifier_node = award_node.find_child(names.FUNDERIDENTIFIER)
                if funder_identifier_node:
                    funder_identifier = funder_identifier_node.content
                award_number_node = award_node.find_child(names.AWARDNUMBER)
                if award_number_node:
                    award_number = award_number_node.content
                award_title_node = award_node.find_child(names.TITLE)
                if award_title_node:
                    award_title = award_title_node.content
                award_url_node = award_node.find_child(names.AWARDURL)
                if award_url_node:
                    award_url = award_url_node.content
                upval = get_upval(i)
                downval = get_downval(i + 1, len(award_nodes))
                award_entry = Awards_Entry(id=id,
                                        funder_name=funder_name,
                                        funder_identifier=funder_identifier,
                                        award_number=award_number,
                                        award_title=award_title,
                                        award_url=award_url,
                                        upval=upval,
                                        downval=downval)
                award_list.append(award_entry)

    return award_list


def list_method_steps(parent_node:Node=None):
    ms_list = []
    if parent_node:
        methods_node = parent_node.find_child(names.METHODS)
        if methods_node:
            method_step_nodes = methods_node.find_all_children(names.METHODSTEP)
            MS_Entry = collections.namedtuple(
                'MS_Entry', 
                ["id", "description", "instrumentation", "upval", "downval"],
                rename=False)
            for i, method_step_node in enumerate(method_step_nodes):
                id = method_step_node.id
                method_step_description = compose_method_step_description(method_step_node)
                method_step_instrumentation = compose_method_step_instrumentation(method_step_node)
                upval = get_upval(i)
                downval = get_downval(i+1, len(method_step_nodes))
                ms_entry = MS_Entry(id=id,
                                    description=method_step_description,
                                    instrumentation=method_step_instrumentation,
                                    upval=upval, 
                                    downval=downval)
                ms_list.append(ms_entry)
    return ms_list


def list_keywords(eml_node:Node=None):
    kw_list = []
    if eml_node:
        kw_nodes = eml_node.find_all_nodes_by_path([
            names.DATASET, names.KEYWORDSET, names.KEYWORD
        ])
        if kw_nodes:
            KW_Entry = collections.namedtuple(
                'KW_Entry',
                ["id", "keyword", "keyword_type", "upval", "downval"],
                rename=False)
            for i, kw_node in enumerate(kw_nodes):
                id = kw_node.id
                keyword = kw_node.content
                kt = kw_node.attribute_value('keywordType')
                keyword_type = kt if kt else ''
                upval = get_upval(i)
                downval = get_downval(i+1, len(kw_nodes))
                kw_entry = KW_Entry(id=id,
                                    keyword=keyword,
                                    keyword_type=keyword_type,
                                    upval=upval,
                                    downval=downval)
                kw_list.append(kw_entry)
    return kw_list


def list_access_rules(parent_node:Node=None):
    ar_list = []
    if parent_node:
        access_node = parent_node.find_child(names.ACCESS)
        if access_node:
            allow_nodes = access_node.find_all_children(names.ALLOW)
            AR_Entry = collections.namedtuple(
                    'AR_Entry', 
                    ["id", "userid", "permission", "upval", "downval"],
                    rename=False)
            for i, allow_node in enumerate(allow_nodes):
                id = allow_node.id
                userid = get_child_content(allow_node, names.PRINCIPAL)
                permission = get_child_content(allow_node, names.PERMISSION)
                upval = get_upval(i)
                downval = get_downval(i+1, len(allow_nodes))
                ar_entry = AR_Entry(id=id,
                                    userid=userid,
                                    permission=permission,
                                    upval=upval, 
                                    downval=downval)
                ar_list.append(ar_entry)
    return ar_list


def get_child_content(parent_node:Node=None, child_name:str=None):
    content = ''

    if parent_node and child_name:
        child_node = parent_node.find_child(child_name)
        if child_node:
            content = child_node.content 

    return content


def compose_method_step_description(method_step_node:Node=None):
    description = ''
    MAX_LEN = 80

    if method_step_node:
        description_node = method_step_node.find_child(names.DESCRIPTION)
        if description_node:
            title, text = sample_text(description_node)
            if title:
                description = title
            else:
                description = text

            if description and len(description) > MAX_LEN:
                description = f'{description[0:MAX_LEN]}...'
    return description


def compose_method_step_instrumentation(method_step_node:Node=None):
    instrumentation = ''
    MAX_LEN = 40

    if method_step_node:
        instrumentation_node = method_step_node.find_child(names.INSTRUMENTATION)
        if instrumentation_node:
            instrumentation = instrumentation_node.content 
            if instrumentation and len(instrumentation) > MAX_LEN:
                instrumentation = instrumentation[0:MAX_LEN]

    return instrumentation


def create_method_step(method_step_node:Node=None, description:str=None, instrumentation:str=None, data_sources:str=None,
                       data_sources_marker_begin:str='', data_sources_marker_end:str=''):
    if method_step_node:
        description_node = method_step_node.find_child(names.DESCRIPTION)
        if not description_node:
            description_node = new_child_node(names.DESCRIPTION, parent=method_step_node)

        if data_sources:
            if not description:
                description = ''  # TODO: Handle cases with empty description but non-empty data_sources
            description = f"{description}\n{data_sources_marker_begin}\n{data_sources}\n{data_sources_marker_end}"

        if description:
            description_node.content = description
            post_process_texttype_node(description_node)

        if instrumentation:
            instrumentation_nodes = method_step_node.find_all_children(names.INSTRUMENTATION)
            if len(instrumentation_nodes) > 1:
                # The EML standard permits multiple instrumentation nodes, but the ezEML UI does not.
                # If there are multiple instrumentation nodes, we will compromise by putting the
                # instrumentation content in a single node, separated by newlines. The other
                # instrumentation nodes will be deleted.
                content = ''
                index = 0
                for instrumentation_node in instrumentation_nodes:
                    if not null_string(instrumentation_node.content):
                        content += f"{instrumentation_node.content}\n"
                    if index > 0:
                        method_step_node.remove_child(instrumentation_node)
                    index += 1
                instrumentation = f"{content}{instrumentation}"
            instrumentation_node = method_step_node.find_child(names.INSTRUMENTATION)
            if not instrumentation_node:
                instrumentation_node = new_child_node(names.INSTRUMENTATION, parent=method_step_node)

            instrumentation_node.content = instrumentation


def create_data_source(data_source_node:Node=None, title:str=None, online_description:str=None, online_url:str=None):
    if data_source_node:
        if title is None:
            title = ''
        title_node = data_source_node.find_child(names.TITLE)
        if not title_node:
            title_node = new_child_node(names.TITLE, parent=data_source_node)
        title_node.content = title

        if online_description is None:
            online_description = ''
        if online_url is None:
            online_url = ''

        distribution_node = data_source_node.find_child(names.DISTRIBUTION)
        if not distribution_node:
            distribution_node = new_child_node(names.DISTRIBUTION, parent=data_source_node)

        # We do not support the full EML schema here. The schema allows offline and inline elements, but ezEML
        #  only supports online. In addition, the schema allows connection and connectionDefinition elements as
        #  children of the online element, but ezEML supports only the url element.
        online_node = distribution_node.find_child(names.ONLINE)
        if not online_node:
            online_node = new_child_node(names.ONLINE, parent=distribution_node)

        online_description_node = online_node.find_child(names.ONLINEDESCRIPTION)
        if online_description:
            if not online_description_node:
                online_description_node = new_child_node(names.ONLINEDESCRIPTION, parent=online_node)
            online_description_node.content = online_description
        else:
            # We don't allow an empty online description, so we will delete the node if it exists
            if online_description_node:
                online_node.remove_child(online_description_node)

        online_url_node = online_node.find_child(names.URL)
        if online_url:
            if not online_url_node:
                online_url_node = new_child_node(names.URL, parent=online_node)
            online_url_node.content = online_url
        else:
            # We don't allow an empty online URL, so we will delete the node if it exists
            if online_url_node:
                online_node.remove_child(online_url_node)

        # If online node was created and now there is no online description nor url, delete the distribution node
        # The user may have just cleared the online description and url fields.
        if len(online_node.children) == 0:
            data_source_node.remove_child(distribution_node)


def create_keyword(keyword_node:Node=None, keyword:str=None, keyword_type:str=None):
    if keyword_node:
        keyword_node.content = keyword
        if keyword_type:
            keyword_node.add_attribute(name='keywordType', value=keyword_type)


def create_access_rule(allow_node:Node=None, userid:str=None, permission:str=None):
    if allow_node:
        if userid:
            principal_node = new_child_node(names.PRINCIPAL, parent=allow_node)
            principal_node.content = userid
        
        if permission:
            permission_node = new_child_node(names.PERMISSION, parent=allow_node)
            permission_node.content = permission


def nominal_to_ordinal(nominal_node:Node=None):
    if nominal_node:
        if nominal_node.name == names.NOMINAL:
            nominal_node.name = names.ORDINAL
        else:
            raise Exception(f"Expected nominal node object but a {nominal_node.name} node was passed.")
    else:
        raise Exception("Expected nominal node object but a None value was passed.")


def ordinal_to_nominal(ordinal_node:Node=None):
    if ordinal_node:
        if ordinal_node.name == names.ORDINAL:
            ordinal_node.name = names.NOMINAL
        else:
            raise Exception(f"Expected ordinal node object but a {ordinal_node.name} node was passed.")
    else:
        raise Exception("Expected ordinal node object but a None value was passed.")


def inteval_to_ratio(interval_node:Node=None):
    if interval_node:
        if interval_node.name == names.INTERVAL:
            interval_node.name = names.RATIO
        else:
            raise Exception(f"Expected interval node object but a {interval_node.name} node was passed.")
    else:
        raise Exception("Expected interval node object but a None value was passed.")


def ratio_to_interval(ratio_node:Node=None):
    if ratio_node:
        if ratio_node.name == names.RATIO:
            ratio_node.name = names.INTERVAL
        else:
            raise Exception(f"Expected ratio node object but a {ratio_node.name} node was passed.")
    else:
        raise Exception("Expected ratio node object but a None value was passed.")


def read_xml(xml:str=None):
    eml_node = None
    if xml:
        try:
            eml_node = mp_io.from_xml(xml)
        except Exception as e:
            logger.error(e)
            raise Exception(f"Error parsing XML: {e}")
    else:
        raise Exception("No XML string provided")

    return eml_node