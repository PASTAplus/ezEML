#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: metapype_client.py

:Synopsis:

:Author:
    costa

:Created:
    7/27/18
"""
import collections
import daiquiri
import html
import json
import os

from flask import (
    send_file
)

from flask_login import (
    current_user
)

from webapp.auth.user_data import (
    get_user_folder_name
)

from metapype.eml2_1_1 import export, validate, names, rule
from metapype.model.node import Node, Shift
from metapype.model import io


logger = daiquiri.getLogger('metapyp_client: ' + __name__)

UP_ARROW = html.unescape('&#x25B2;')
DOWN_ARROW = html.unescape('&#x25BC;')


def list_data_tables(eml_node:Node=None):
    dt_list = []
    if eml_node:
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            dt_nodes = dataset_node.find_all_children(names.DATATABLE)
            DT_Entry = collections.namedtuple(
                'DT_Entry', 
                ["id", "label", "upval", "downval"],
                 rename=False)
            for i, dt_node in enumerate(dt_nodes):
                id = dt_node.id
                label = compose_data_table_label(dt_node)
                upval = get_upval(i)
                downval = get_downval(i+1, len(dt_nodes))
                dt_entry = DT_Entry(id=id,
                                    label=label,
                                    upval=upval, 
                                    downval=downval)
                dt_list.append(dt_entry)
    return dt_list


def compose_data_table_label(dt_node:Node=None):
    label = ''
    if dt_node:
        entity_name_node = dt_node.find_child(names.ENTITYNAME)
        entity_name = entity_name_node.content 
        label = entity_name
    return label


def list_codes_and_definitions(att_node:Node=None):
    codes_list = []
    if att_node:
        mscale_node = att_node.find_child(names.MEASUREMENTSCALE)
        if mscale_node:
            nominal_ordinal_node = None
            nominal_node = mscale_node.find_child(names.NOMINAL)
            if nominal_node:
                nominal_ordinal_node = nominal_node
            else:
                nominal_ordinal_node = mscale_node.find_child(names.ORDINAL)

            if nominal_ordinal_node:
                non_number_domain_node = nominal_ordinal_node.find_child(names.NONNUMERICDOMAIN)
                if non_number_domain_node:
                    enumerated_domain_node = non_number_domain_node.find_child(names.ENUMERATEDDOMAIN)
                    if enumerated_domain_node:
                        code_definition_nodes = enumerated_domain_node.find_all_children(names.CODEDEFINITION)

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
        if definition_node:
            definition = definition_node.content

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


def enumerated_domain_from_attribute(att_node:Node=None):
    enumerated_domain_node = None

    if att_node:
        nominal_or_ordinal_node = att_node.find_child(names.NOMINAL)
        if not nominal_or_ordinal_node:
            nominal_or_ordinal_node = att_node.find_child(names.ORDINAL)
        
        if nominal_or_ordinal_node:
            non_numeric_domain_node = nominal_or_ordinal_node.find_child(names.NONNUMERICDOMAIN)

            if non_numeric_domain_node:
                enumerated_domain_node = non_numeric_domain_node.find_child(names.ENUMERATEDDOMAIN)

    return enumerated_domain_node
    

def mscale_from_attribute(att_node:Node=None):
    mscale = ''

    if att_node:
        mscale_node = att_node.find_child(names.MEASUREMENTSCALE)

        if mscale_node:
        
            nominal_node = mscale_node.find_child(names.NOMINAL)
            if nominal_node:
                return names.NOMINAL

            ordinal_node = mscale_node.find_child(names.ORDINAL)
            if ordinal_node:
                return names.ORDINAL

            interval_node = mscale_node.find_child(names.INTERVAL)
            if interval_node:
                return names.INTERVAL

            ratio_node = mscale_node.find_child(names.RATIO)
            if ratio_node:
                return names.RATIO

            datetime_node = mscale_node.find_child(names.DATETIME)
            if datetime_node:
                return names.DATETIME

    return mscale
    

def list_attributes(data_table_node:Node=None):
    att_list = []
    if data_table_node:
        attribute_list_node = data_table_node.find_child(names.ATTRIBUTELIST)
        if attribute_list_node:
            att_nodes = attribute_list_node.find_all_children(names.ATTRIBUTE)
            ATT_Entry = collections.namedtuple(
                'ATT_Entry', 
                ["id", "label", "upval", "downval"],
                 rename=False)
            for i, att_node in enumerate(att_nodes):
                id = att_node.id
                label = compose_attribute_label(att_node)
                upval = get_upval(i)
                downval = get_downval(i+1, len(att_nodes))
                att_entry = ATT_Entry(id=id,
                                      label=label,
                                      upval=upval, 
                                      downval=downval)
                att_list.append(att_entry)
    return att_list


def compose_attribute_label(att_node:Node=None):
    label = ''
    if att_node:
        attribute_name_node = att_node.find_child(names.ATTRIBUTENAME)
        if attribute_name_node:
            attribute_name = attribute_name_node.content 
            label = attribute_name
    return label


def list_responsible_parties(eml_node:Node=None, node_name:str=None):
    rp_list = []
    if eml_node:
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            rp_nodes = dataset_node.find_all_children(node_name)
            RP_Entry = collections.namedtuple(
                'RP_Entry', ["id", "label", "upval", "downval"], 
                 rename=False)
            for i, rp_node in enumerate(rp_nodes):
                label = compose_rp_label(rp_node)
                id = rp_node.id
                upval = get_upval(i)
                downval = get_downval(i+1, len(rp_nodes))
                rp_entry = RP_Entry(id=id, label=label, upval=upval, downval=downval)
                rp_list.append(rp_entry)
    return rp_list


def list_geographic_coverages(eml_node:Node=None):
    gc_list = []
    if eml_node:
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            coverage_node = eml_node.find_child(names.COVERAGE)
            if coverage_node:
                gc_nodes = \
                    coverage_node.find_all_children(names.GEOGRAPHICCOVERAGE)
                GC_Entry = collections.namedtuple(
                    'GC_Entry', 
                    ["id", "geographic_description", "label", "upval", "downval"],
                     rename=False)
                for i, gc_node in enumerate(gc_nodes):
                    id = gc_node.id
                    upval = get_upval(i)
                    downval = get_downval(i+1, len(gc_nodes))
                    geographic_description_node = \
                        gc_node.find_child(names.GEOGRAPHICDESCRIPTION)
                    geographic_description = geographic_description_node.content
                    label = compose_gc_label(gc_node)
                    gc_entry = GC_Entry(id=id,
                                        geographic_description=geographic_description,
                                        label=label,
                                        upval=upval, downval=downval)
                    gc_list.append(gc_entry)
    return gc_list


def get_upval(i:int):
    upval = '[  ]' if i == 0 else UP_ARROW
    return upval


def get_downval(i:int, n:int):
    downval = '[  ]' if i >= n else DOWN_ARROW
    return downval


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
            if wbc_node and ebc_node and nbc_node and sbc_node:
                coordinate_list = [str(wbc_node.content),
                                   str(ebc_node.content),
                                   str(nbc_node.content),
                                   str(sbc_node.content)]
                label = ', '.join(coordinate_list)
    return label


def list_temporal_coverages(eml_node:Node=None):
    tc_list = []
    if eml_node:
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            coverage_node = eml_node.find_child(names.COVERAGE)
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
                            begin_date_node = rod_node.find_child(names.BEGINDATE)
                            if begin_date_node:
                                calendar_date_node = begin_date_node.find_child(names.CALENDARDATE)
                                begin_date = calendar_date_node.content
                            end_date_node = rod_node.find_child(names.ENDDATE)
                            if end_date_node:
                                calendar_date_node = end_date_node.find_child(names.CALENDARDATE)
                                end_date = calendar_date_node.content
                            tc_entry = TC_Entry(id=id, begin_date=begin_date, end_date=end_date, upval=upval, downval=downval)
                            tc_list.append(tc_entry)
    return tc_list


def list_taxonomic_coverages(eml_node:Node=None):
    txc_list = []
    if eml_node:
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            coverage_node = eml_node.find_child(names.COVERAGE)
            if coverage_node:
                txc_nodes = coverage_node.find_all_children(names.TAXONOMICCOVERAGE)
                TXC_Entry = collections.namedtuple(
                    'TXC_Entry', ["id", "label", "upval", "downval"],
                     rename=False)
                for i, txc_node in enumerate(txc_nodes):
                    id = txc_node.id
                    upval = get_upval(i)
                    downval = get_downval(i+1, len(txc_nodes))
                    label = compose_taxonomic_label(txc_node, label='')
                    txc_entry = TXC_Entry(id=id, label=label, upval=upval, downval=downval)
                    txc_list.append(txc_entry)

    return txc_list


def compose_taxonomic_label(txc_node:Node=None, label:str=''):
    if txc_node:
        tc_node = txc_node.find_child(names.TAXONOMICCLASSIFICATION)
        if tc_node:
            trv_node = tc_node.find_child(names.TAXONRANKVALUE)
            val = trv_node.content 
            new_label = label + ' ' + val if label else val
            return compose_taxonomic_label(tc_node, new_label)
        else:
            return label
    else:
        return label


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


def compose_rp_label(rp_node:Node=None):
    label = ''
    if rp_node:
        individual_name_node = rp_node.find_child(names.INDIVIDUALNAME)
        individual_name_label = (
            compose_individual_name_label(individual_name_node))
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


def load_eml(packageid:str=None):
    eml_node = None
    user_folder = get_user_folder_name()
    if not user_folder:
        user_folder = '.'
    filename = f"{user_folder}/{packageid}.json"
    if os.path.isfile(filename):
        with open(filename, "r") as json_file:
            json_obj = json.load(json_file)
            eml_node = io.from_json(json_obj)
    return eml_node


def remove_child(node_id:str=None):
    if node_id:
        child_node = Node.get_node_instance(node_id)
        if child_node:
            parent_node = child_node.parent
            if parent_node:
                parent_node.remove_child(child_node)


def log_as_xml(node: Node):
    xml_str = export.to_xml(node)
    logger.info("\n\n" + xml_str)


def save_old_to_new(old_packageid:str=None, new_packageid:str=None, eml_node:Node=None):
    msg = None
    if new_packageid and eml_node and new_packageid != old_packageid:
        eml_node.add_attribute('packageId', new_packageid)
        save_eml(packageid=new_packageid, eml_node=eml_node, format='json')
        save_both_formats(packageid=new_packageid, eml_node=eml_node)
    elif new_packageid == old_packageid:
        msg = 'New package id and old package id are the same'
    else:
        msg = 'Not saved'

    return msg


def save_both_formats(packageid:str=None, eml_node:Node=None):
    save_eml(packageid=packageid, eml_node=eml_node, format='json')
    save_eml(packageid=packageid, eml_node=eml_node, format='xml')


def save_eml(packageid:str=None, eml_node:Node=None, format:str='json'):
    if packageid:
        if eml_node is not None:
            metadata_str = None

            if format == 'json':
                metadata_str = io.to_json(eml_node)
            elif format == 'xml':
                xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
                xml_str = export.to_xml(eml_node)
                metadata_str = xml_declaration + xml_str
            
            if metadata_str:
                user_folder = get_user_folder_name()
                if not user_folder:
                    user_folder = '.'
                filename = f'{user_folder}/{packageid}.{format}'
                with open(filename, "w") as fh:
                    fh.write(metadata_str)
        else:
            raise Exception(f"No EML node was supplied for saving EML.")
    else:
        raise Exception(f"No packageid value was supplied for saving EML.")


def validate_tree(node:Node):
    msg = ''
    if node:
        try:
            validate.tree(node)
            msg = f"{node.name} node is valid"
        except Exception as e:
            msg = str(e)

    return msg


def create_eml(packageid=None):
    eml_node = load_eml(packageid=packageid)

    if not eml_node:
        eml_node = Node(names.EML)
        eml_node.add_attribute('packageId', packageid)
        eml_node.add_attribute('system', 'https://pasta.edirepository.org')
        dataset_node = Node(names.DATASET, parent=eml_node)
        add_child(eml_node, dataset_node)

        try:
            save_both_formats(packageid=packageid, eml_node=eml_node)
        except Exception as e:
            logger.error(e)


def create_data_table(
    data_table_node:Node=None, 
    entity_name:str=None,
    entity_description:str=None,
    object_name:str=None,
    size:str=None,
    num_header_lines:str=None,
    record_delimiter:str=None,
    attribute_orientation:str=None,
    field_delimiter:str=None,
    case_sensitive:str=None,
    number_of_records:str=None,
    online_url:str=None):

    try:

        if not data_table_node:
            data_table_node = Node(names.DATATABLE)

        if entity_name:
            entity_name_node = Node(names.ENTITYNAME, parent=data_table_node)
            entity_name_node.content = entity_name
            add_child(data_table_node, entity_name_node)

        if entity_description:
            entity_description_node = Node(names.ENTITYDESCRIPTION, parent=data_table_node)
            entity_description_node.content = entity_description
            add_child(data_table_node, entity_description_node)

        if object_name or size or num_header_lines or \
           record_delimiter or attribute_orientation or \
           field_delimiter or online_url:

            physical_node = Node(names.PHYSICAL, parent=data_table_node)
            add_child(data_table_node, physical_node)

            if object_name:
                object_name_node = Node(names.OBJECTNAME, parent=physical_node)
                object_name_node.content = object_name
                add_child(physical_node, object_name_node)

            if size:
                size_node = Node(names.SIZE, parent=physical_node)
                size_node.content = size
                add_child(physical_node, size_node)

            if num_header_lines or record_delimiter or \
               attribute_orientation or field_delimiter:

                data_format_node = Node(names.DATAFORMAT, parent=physical_node)
                add_child(physical_node, data_format_node)
    
                text_format_node = Node(names.TEXTFORMAT, parent=data_format_node)
                add_child(data_format_node, text_format_node)

                if num_header_lines:
                    num_header_lines_node = Node(names.NUMHEADERLINES, parent=text_format_node)
                    num_header_lines_node.content = num_header_lines
                    add_child(text_format_node, num_header_lines_node)
                
                if record_delimiter:
                    record_delimiter_node = Node(names.RECORDDELIMITER, parent=text_format_node)
                    record_delimiter_node.content = record_delimiter
                    add_child(text_format_node, record_delimiter_node)

                if attribute_orientation:
                    attribute_orientation_node = Node(names.ATTRIBUTEORIENTATION, parent=text_format_node)
                    attribute_orientation_node.content = attribute_orientation
                    add_child(text_format_node, attribute_orientation_node)

                if field_delimiter:
                    simple_delimited_node = Node(names.SIMPLEDELIMITED, parent=text_format_node)
                    add_child(text_format_node, simple_delimited_node)

                    field_delimiter_node = Node(names.FIELDDELIMITER, parent=simple_delimited_node)
                    field_delimiter_node.content = field_delimiter
                    add_child(simple_delimited_node, field_delimiter_node)

            if online_url:
                distribution_node = Node(names.DISTRIBUTION, parent=physical_node)
                add_child(physical_node, distribution_node)

                online_node = Node(names.ONLINE, parent=distribution_node)
                add_child(distribution_node, online_node)

                url_node = Node(names.URL, parent=online_node)
                url_node.content = online_url
                add_child(online_node, url_node)

        if case_sensitive:
            case_sensitive_node = Node(names.CASESENSITIVE, parent=data_table_node)
            case_sensitive_node.content = case_sensitive
            add_child(data_table_node, case_sensitive_node)

        if number_of_records:
            number_of_records_node = Node(names.NUMBEROFRECORDS, parent=data_table_node)
            number_of_records_node.content = number_of_records
            add_child(data_table_node, number_of_records_node)

        return data_table_node

    except Exception as e:
        logger.error(e)


def create_attribute(attribute_node:Node=None, 
                     attribute_name:str=None,
                     attribute_label:str=None,
                     attribute_definition:str=None,
                     storage_type:str=None,
                     storage_type_system:str=None,
                     code_dict:dict=None):
    if attribute_node:
        try:
            attribute_name_node = Node(names.ATTRIBUTENAME, parent=attribute_node)
            attribute_name_node.content = attribute_name
            add_child(attribute_node, attribute_name_node)
            
            if attribute_label:
                attribute_label_node = Node(names.ATTRIBUTELABEL, parent=attribute_node)
                attribute_label_node.content = attribute_label
                add_child(attribute_node, attribute_label_node)
            
            attribute_definition_node = Node(names.ATTRIBUTEDEFINITION, parent=attribute_node)
            attribute_definition_node.content = attribute_definition
            add_child(attribute_node, attribute_definition_node)

            storage_type_node = Node(names.STORAGETYPE, parent=attribute_node)
            storage_type_node.content = storage_type
            if storage_type_system:
                storage_type_node.add_attribute('typeSystem', storage_type_system)
            add_child(attribute_node, storage_type_node)

            if code_dict:
                for key in code_dict:
                    if code_dict[key]:
                        code = key
                        code_explanation = code_dict[key]
                        if code and code_explanation:
                            mvc_node = Node(names.MISSINGVALUECODE, parent=attribute_node)
                            add_child(attribute_node, mvc_node)
                            code_node = Node(names.CODE, parent=mvc_node)
                            code_node.content = code
                            add_child(mvc_node, code_node)
                            code_explanation_node = Node(names.CODEEXPLANATION, parent=mvc_node)
                            code_explanation_node.content = code_explanation
                            add_child(mvc_node, code_explanation_node)

        except Exception as e:
            logger.error(e)


def create_code_definition(code_definition_node:Node=None,
                           code:str='',
                           definition:str='',
                           order:str=''):
    if code_definition_node:
        code_node = Node(names.CODE, parent=code_definition_node)
        code_node.content = code
        add_child(code_definition_node, code_node)
        definition_node = Node(names.DEFINITION, parent=code_definition_node)
        definition_node.content = definition
        add_child(code_definition_node, definition_node)
        if order:
            code_definition_node.add_attribute('order', order)


# node is either the interval or ratio node to be constructed under
# the measurementScale node
def create_interval_ratio(node:Node, standard_unit:str, custom_unit:str,
                        precision:str, number_type:str, bounds_minimum:str,
                        bounds_minimum_exclusive:str, bounds_maximum:str,
                        bounds_maximum_exclusive:str):
    if node:
        unit_node = Node(names.UNIT, parent=node)
        add_child(node, unit_node)
        if custom_unit:
            custom_unit_node = Node(names.CUSTOMUNIT, parent=unit_node)
            custom_unit_node.content = custom_unit
            add_child(unit_node, custom_unit_node)
        else:
            standard_unit_node = Node(names.STANDARDUNIT, parent=unit_node)
            standard_unit_node.content = standard_unit
            add_child(unit_node, standard_unit_node)
        if precision:
            precision_node = Node(names.PRECISION, parent=node)
            precision_node.content = precision
            add_child(node, precision_node)
        numeric_domain_node = Node(names.NUMERICDOMAIN, parent=node)
        add_child(node, numeric_domain_node)
        number_type_node = Node(names.NUMBERTYPE, parent=numeric_domain_node)
        add_child(numeric_domain_node, number_type_node)
        number_type_node.content = number_type
        if bounds_minimum or bounds_maximum:
            bounds_node = Node(names.BOUNDS, parent=numeric_domain_node)
            add_child(numeric_domain_node, bounds_node)
            if bounds_minimum:
                bounds_minimum_node = Node(names.MINIMUM, parent=bounds_node)
                bounds_minimum_node.content = bounds_minimum
                if bounds_minimum_exclusive:
                    bounds_minimum_node.add_attribute('exclusive', 'true')
                else:
                    bounds_minimum_node.add_attribute('exclusive', 'false')
                add_child(bounds_node, bounds_minimum_node)
            if bounds_maximum:
                bounds_maximum_node = Node(names.MAXIMUM, parent=bounds_node)
                bounds_maximum_node.content = bounds_maximum
                if bounds_maximum_exclusive:
                    bounds_maximum_node.add_attribute('exclusive', 'true')
                else:
                    bounds_maximum_node.add_attribute('exclusive', 'false')
                add_child(bounds_node, bounds_maximum_node)


# node is the datetime node to be constructed under
# the measurementScale node
def create_datetime(node:Node, format_string:str, datetime_precision:str,
                    bounds_minimum:str, bounds_minimum_exclusive:str, 
                    bounds_maximum:str, bounds_maximum_exclusive:str):
    if node:
        format_string_node = Node(names.FORMATSTRING, parent=node)
        format_string_node.content = format_string
        add_child(node, format_string_node)
        if datetime_precision:
            datetime_precision_node = Node(names.DATETIMEPRECISION, parent=node)
            datetime_precision_node.content = datetime_precision
            add_child(node, datetime_precision_node)
        datetime_domain_node = Node(names.DATETIMEDOMAIN, parent=node)
        add_child(node, datetime_domain_node)
        if bounds_minimum or bounds_maximum:
            bounds_node = Node(names.BOUNDS, parent=datetime_domain_node)
            add_child(datetime_domain_node, bounds_node)
            if bounds_minimum:
                bounds_minimum_node = Node(names.MINIMUM, parent=bounds_node)
                bounds_minimum_node.content = bounds_minimum
                if bounds_minimum_exclusive:
                    bounds_minimum_node.add_attribute('exclusive', 'true')
                else:
                    bounds_minimum_node.add_attribute('exclusive', 'false')
                add_child(bounds_node, bounds_minimum_node)
            if bounds_maximum:
                bounds_maximum_node = Node(names.MAXIMUM, parent=bounds_node)
                bounds_maximum_node.content = bounds_maximum
                if bounds_maximum_exclusive:
                    bounds_maximum_node.add_attribute('exclusive', 'true')
                else:
                    bounds_maximum_node.add_attribute('exclusive', 'false')
                add_child(bounds_node, bounds_maximum_node)


def create_title(title=None, packageid=None):
    eml_node = load_eml(packageid=packageid)

    dataset_node = eml_node.find_child('dataset')
    if dataset_node:
        title_node = dataset_node.find_child('title')
        if not title_node:
            title_node = Node(names.TITLE, parent=dataset_node)
            add_child(dataset_node, title_node)
    else:
        dataset_node = Node(names.DATASET, parent=eml_node)
        add_child(eml_node, dataset_node)
        title_node = Node(names.TITLE, parent=dataset_node)
        add_child(dataset_node, title_node)

    title_node.content = title

    try:
        save_both_formats(packageid=packageid, eml_node=eml_node)
    except Exception as e:
        logger.error(e)


def create_pubdate(pubdate=None, packageid=None):
    eml_node = load_eml(packageid=packageid)

    dataset_node = eml_node.find_child(names.DATASET)
    if dataset_node:
        pubdate_node = dataset_node.find_child(names.PUBDATE)
        if not pubdate_node:
            pubdate_node = Node(names.PUBDATE, parent=dataset_node)
            add_child(dataset_node, pubdate_node)
    else:
        dataset_node = Node(names.DATASET, parent=eml_node)
        add_child(eml_node, dataset_node)
        pubdate_node = Node(names.PUBDATE, parent=dataset_node)
        add_child(dataset_node, pubdate_node)

    pubdate_node.content = pubdate

    try:
        save_both_formats(packageid=packageid, eml_node=eml_node)
    except Exception as e:
        logger.error(e)


def create_abstract(packageid=None, abstract=None):
    eml_node = load_eml(packageid=packageid)

    dataset_node = eml_node.find_child(names.DATASET)
    if dataset_node:
        abstract_node = dataset_node.find_child(names.ABSTRACT)
        if not abstract_node:
            abstract_node = Node(names.ABSTRACT, parent=dataset_node)
            add_child(dataset_node, abstract_node)
    else:
        dataset_node = Node(names.DATASET, parent=eml_node)
        add_child(eml_node, dataset_node)
        abstract_node = Node(names.ABSTRACT, parent=dataset_node)
        add_child(dataset_node, abstract_node)

    abstract_node.content = abstract

    try:
        save_both_formats(packageid=packageid, eml_node=eml_node)
    except Exception as e:
        logger.error(e)


def add_keyword(packageid:str=None, keyword:str=None, keyword_type:str=None):
    if keyword:
        eml_node = load_eml(packageid=packageid)

        dataset_node = eml_node.find_child(names.DATASET)
        if not dataset_node:
            dataset_node = Node(names.DATASET, parent=eml_node)
            add_child(eml_node, dataset_node)

        keywordset_node = dataset_node.find_child(names.KEYWORDSET)
        if not keywordset_node:
            keywordset_node = Node(names.KEYWORDSET, parent=dataset_node)
            add_child(dataset_node, keywordset_node)

        keyword_node = None
        
        # Does a matching keyword node already exist?
        keyword_nodes = keywordset_node.find_all_children(names.KEYWORD)
        for child_node in keyword_nodes:
            if child_node.content == keyword:
                keyword_node = child_node
                break
        
        if not keyword_node:
            keyword_node = Node(names.KEYWORD, parent=keywordset_node)
            keyword_node.content = keyword
            add_child(keywordset_node, keyword_node)
        
        if keyword_type:
            keyword_node.add_attribute(name='keywordType', value=keyword_type)

    try:
        save_both_formats(packageid=packageid, eml_node=eml_node)
    except Exception as e:
        logger.error(e)


def remove_keyword(packageid:str=None, keyword:str=None):
    if keyword:
        eml_node = load_eml(packageid=packageid)
        keywordset_node = eml_node.find_child(names.KEYWORDSET)
        if keywordset_node:
            current_keywords = \
                keywordset_node.find_all_children(child_name=names.KEYWORD)
            for keyword_node in current_keywords:
                if keyword_node.content == keyword:
                    keywordset_node.remove_child(keyword_node)

    try:
        save_both_formats(packageid=packageid, eml_node=eml_node)
    except Exception as e:
        logger.error(e)


def create_keywords(packageid:str=None, keywords_list:list=[]):
    eml_node = load_eml(packageid=packageid)

    dataset_node = eml_node.find_child(names.DATASET)
    if dataset_node:
        keywordset_node = dataset_node.find_child(names.KEYWORDSET)
        if keywordset_node:
            # Get rid of the old keyword set if it exists
            dataset_node.remove_child(keywordset_node)
    else:
        dataset_node = Node(names.DATASET, parent=eml_node)
        add_child(eml_node, dataset_node)
    
    if keywords_list:
        keywordset_node = Node(names.KEYWORDSET, parent=dataset_node)
        add_child(dataset_node, keywordset_node)
        for keyword in keywords_list:
            keyword_node = Node(names.KEYWORD, parent=keywordset_node)
            keyword_node.content = keyword
            add_child(keywordset_node, keyword_node)

    try:
        save_both_formats(packageid=packageid, eml_node=eml_node)
    except Exception as e:
        logger.error(e)


def create_geographic_coverage(
                   geographic_coverage_node:Node=None,
                   geographic_description:str=None,
                   wbc:str=None,
                   ebc:str=None,
                   nbc:str=None,
                   sbc:str=None):
    try:
        geographic_description_node = Node(names.GEOGRAPHICDESCRIPTION)
        geographic_description_node.content = geographic_description
        add_child(geographic_coverage_node, geographic_description_node)

        bounding_coordinates_node = Node(names.BOUNDINGCOORDINATES)

        wbc_node = Node(names.WESTBOUNDINGCOORDINATE)
        wbc_node.content = wbc
        add_child(bounding_coordinates_node, wbc_node)

        ebc_node = Node(names.EASTBOUNDINGCOORDINATE)
        ebc_node.content = ebc
        add_child(bounding_coordinates_node, ebc_node)

        nbc_node = Node(names.NORTHBOUNDINGCOORDINATE)
        nbc_node.content = nbc
        add_child(bounding_coordinates_node, nbc_node)

        sbc_node = Node(names.SOUTHBOUNDINGCOORDINATE)
        sbc_node.content = sbc
        add_child(bounding_coordinates_node, sbc_node)

        add_child(geographic_coverage_node, bounding_coordinates_node)

        return geographic_coverage_node

    except Exception as e:
        logger.error(e)


def create_temporal_coverage(
                   temporal_coverage_node:Node=None,
                   begin_date:str=None,
                   end_date:str=None):
    try:
        if begin_date and end_date:
            range_of_dates_node = Node(names.RANGEOFDATES, parent=temporal_coverage_node)
            add_child(temporal_coverage_node, range_of_dates_node)

            begin_date_node = Node(names.BEGINDATE, parent=range_of_dates_node)
            add_child(range_of_dates_node, begin_date_node)
            begin_calendar_date_node = Node(names.CALENDARDATE, parent=begin_date_node)
            add_child(begin_date_node, begin_calendar_date_node)
            begin_calendar_date_node.content = begin_date

            end_date_node = Node(names.ENDDATE, parent=range_of_dates_node)
            add_child(range_of_dates_node, end_date_node)
            end_calendar_date_node = Node(names.CALENDARDATE, parent=end_date_node)
            add_child(end_date_node, end_calendar_date_node)
            end_calendar_date_node.content = end_date
        elif begin_date:
            single_datetime_node = Node(names.SINGLEDATETIME, parent=temporal_coverage_node)
            add_child(temporal_coverage_node, single_datetime_node)
            calendar_date_node = Node(names.CALENDARDATE, parent=single_datetime_node)
            add_child(single_datetime_node, calendar_date_node)
            calendar_date_node.content = begin_date

        return temporal_coverage_node

    except Exception as e:
        logger.error(e)


def create_taxonomic_coverage(
                taxonomic_coverage_node:Node,
                general_taxonomic_coverage:str,
                kingdom_value:str,
                kingdom_common_name:str,
                phylum_value:str,
                phylum_common_name:str,
                class_value:str,
                class_common_name:str,
                order_value:str,
                order_common_name:str,
                family_value:str,
                family_common_name:str,
                genus_value:str,
                genus_common_name:str,
                species_value:str,
                species_common_name:str):
    try:
        if taxonomic_coverage_node:
            if general_taxonomic_coverage:
                general_taxonomic_coverage_node = Node(names.GENERALTAXONOMICCOVERAGE, 
                                                       parent=taxonomic_coverage_node)
                general_taxonomic_coverage_node.content = general_taxonomic_coverage
                add_child(taxonomic_coverage_node, general_taxonomic_coverage_node)

            taxonomic_classification_parent_node = taxonomic_coverage_node
            
            if kingdom_value:
                taxonomic_classification_node = Node(names.TAXONOMICCLASSIFICATION, parent=taxonomic_classification_parent_node)
                add_child(taxonomic_classification_parent_node, taxonomic_classification_node)
                taxon_rank_name_node = Node(names.TAXONRANKNAME, parent=taxonomic_classification_node)
                add_child(taxonomic_classification_node, taxon_rank_name_node)
                taxon_rank_name_node.content = 'Kingdom'
                taxon_rank_value_node = Node(names.TAXONRANKVALUE, parent=taxonomic_classification_node)
                add_child(taxonomic_classification_node, taxon_rank_value_node)
                taxon_rank_value_node.content = kingdom_value
                if kingdom_common_name:
                    common_name_node = Node(names.COMMONNAME, parent=taxonomic_classification_node)
                    common_name_node.content=kingdom_common_name
                    add_child(taxonomic_classification_node, common_name_node)
                taxonomic_classification_parent_node = taxonomic_classification_node

            if phylum_value:
                taxonomic_classification_node = Node(names.TAXONOMICCLASSIFICATION, parent=taxonomic_classification_parent_node)
                add_child(taxonomic_classification_parent_node, taxonomic_classification_node)
                taxon_rank_name_node = Node(names.TAXONRANKNAME, parent=taxonomic_classification_node)
                add_child(taxonomic_classification_node, taxon_rank_name_node)
                taxon_rank_name_node.content = 'Phylum'
                taxon_rank_value_node = Node(names.TAXONRANKVALUE, parent=taxonomic_classification_node)
                add_child(taxonomic_classification_node, taxon_rank_value_node)
                taxon_rank_value_node.content = phylum_value
                if phylum_common_name:
                    common_name_node = Node(names.COMMONNAME, parent=taxonomic_classification_node)
                    common_name_node.content = phylum_common_name
                    add_child(taxonomic_classification_node, common_name_node)
                taxonomic_classification_parent_node = taxonomic_classification_node

            if class_value:
                taxonomic_classification_node = Node(names.TAXONOMICCLASSIFICATION, parent=taxonomic_classification_parent_node)
                add_child(taxonomic_classification_parent_node, taxonomic_classification_node)
                taxon_rank_name_node = Node(names.TAXONRANKNAME, parent=taxonomic_classification_node)
                add_child(taxonomic_classification_node, taxon_rank_name_node)
                taxon_rank_name_node.content = 'Class'
                taxon_rank_value_node = Node(names.TAXONRANKVALUE, parent=taxonomic_classification_node)
                add_child(taxonomic_classification_node, taxon_rank_value_node)
                taxon_rank_value_node.content = class_value
                if class_common_name:
                    common_name_node = Node(names.COMMONNAME, parent=taxonomic_classification_node)
                    common_name_node.content = class_common_name
                    add_child(taxonomic_classification_node, common_name_node)
                taxonomic_classification_parent_node = taxonomic_classification_node

            if order_value:
                taxonomic_classification_node = Node(names.TAXONOMICCLASSIFICATION, parent=taxonomic_classification_parent_node)
                add_child(taxonomic_classification_parent_node, taxonomic_classification_node)
                taxon_rank_name_node = Node(names.TAXONRANKNAME, parent=taxonomic_classification_node)
                add_child(taxonomic_classification_node, taxon_rank_name_node)
                taxon_rank_name_node.content = 'Order'
                taxon_rank_value_node = Node(names.TAXONRANKVALUE, parent=taxonomic_classification_node)
                add_child(taxonomic_classification_node, taxon_rank_value_node)
                taxon_rank_value_node.content = order_value
                if order_common_name:
                    common_name_node = Node(names.COMMONNAME, parent=taxonomic_classification_node)
                    common_name_node.content = order_common_name
                    add_child(taxonomic_classification_node, common_name_node)
                taxonomic_classification_parent_node = taxonomic_classification_node

            if family_value:
                taxonomic_classification_node = Node(names.TAXONOMICCLASSIFICATION, parent=taxonomic_classification_parent_node)
                add_child(taxonomic_classification_parent_node, taxonomic_classification_node)
                taxon_rank_name_node = Node(names.TAXONRANKNAME, parent=taxonomic_classification_node)
                add_child(taxonomic_classification_node, taxon_rank_name_node)
                taxon_rank_name_node.content = 'Family'
                taxon_rank_value_node = Node(names.TAXONRANKVALUE, parent=taxonomic_classification_node)
                add_child(taxonomic_classification_node, taxon_rank_value_node)
                taxon_rank_value_node.content = family_value
                if family_common_name:
                    common_name_node = Node(names.COMMONNAME, parent=taxonomic_classification_node)
                    common_name_node.content = family_common_name
                    add_child(taxonomic_classification_node, common_name_node)
                taxonomic_classification_parent_node = taxonomic_classification_node

            if genus_value:
                taxonomic_classification_node = Node(names.TAXONOMICCLASSIFICATION, parent=taxonomic_classification_parent_node)
                add_child(taxonomic_classification_parent_node, taxonomic_classification_node)
                taxon_rank_name_node = Node(names.TAXONRANKNAME, parent=taxonomic_classification_node)
                add_child(taxonomic_classification_node, taxon_rank_name_node)
                taxon_rank_name_node.content = 'Genus'
                taxon_rank_value_node = Node(names.TAXONRANKVALUE, parent=taxonomic_classification_node)
                add_child(taxonomic_classification_node, taxon_rank_value_node)
                taxon_rank_value_node.content = genus_value
                if genus_common_name:
                    common_name_node = Node(names.COMMONNAME, parent=taxonomic_classification_node)
                    common_name_node.content = genus_common_name
                    add_child(taxonomic_classification_node, common_name_node)
                taxonomic_classification_parent_node = taxonomic_classification_node

            if species_value:
                taxonomic_classification_node = Node(names.TAXONOMICCLASSIFICATION, parent=taxonomic_classification_parent_node)
                add_child(taxonomic_classification_parent_node, taxonomic_classification_node)
                taxon_rank_name_node = Node(names.TAXONRANKNAME, parent=taxonomic_classification_node)
                add_child(taxonomic_classification_node, taxon_rank_name_node)
                taxon_rank_name_node.content = 'Species'
                taxon_rank_value_node = Node(names.TAXONRANKVALUE, parent=taxonomic_classification_node)
                add_child(taxonomic_classification_node, taxon_rank_value_node)
                taxon_rank_value_node.content = species_value
                if species_common_name:
                    common_name_node = Node(names.COMMONNAME, parent=taxonomic_classification_node)
                    common_name_node.content = species_common_name
                    add_child(taxonomic_classification_node, common_name_node)
                taxonomic_classification_parent_node = taxonomic_classification_node

        return taxonomic_coverage_node

    except Exception as e:
        logger.error(e)


def create_responsible_party(
                   parent_node:Node=None,
                   responsible_party_node:Node=None,
                   packageid:str=None, 
                   salutation:str=None,
                   gn:str=None,
                   sn:str=None,
                   organization:str=None,
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
                   online_url:str=None):
    try:
        node_name = responsible_party_node.name

        if parent_node:
            old_responsible_party_node = parent_node.find_child(node_name)
            if old_responsible_party_node:
                pass
                # Get rid of the old node if it exists
                #dataset_node.remove_child(old_responsible_party_node)

        if salutation or gn or sn:
            individual_name_node = Node(names.INDIVIDUALNAME)
            if salutation:
                salutation_node = Node(names.SALUTATION)
                salutation_node.content = salutation
                add_child(individual_name_node, salutation_node)
            if gn:
                given_name_node = Node(names.GIVENNAME)
                given_name_node.content = gn
                add_child(individual_name_node, given_name_node)
            if sn:
                surname_node = Node(names.SURNAME)
                surname_node.content = sn
                add_child(individual_name_node, surname_node)
            add_child(responsible_party_node, individual_name_node)

        if organization:
            organization_name_node = Node(names.ORGANIZATIONNAME)
            organization_name_node.content = organization
            add_child(responsible_party_node, organization_name_node)

        if position_name:
            position_name_node = Node(names.POSITIONNAME)
            position_name_node.content = position_name
            add_child(responsible_party_node, position_name_node)

        if address_1 or address_2 or city or state or postal_code or country:
            address_node = Node(names.ADDRESS)

            if address_1:
                delivery_point_node_1 = Node(names.DELIVERYPOINT)
                delivery_point_node_1.content = address_1
                add_child(address_node, delivery_point_node_1)

            if address_2:
                delivery_point_node_2 = Node(names.DELIVERYPOINT)
                delivery_point_node_2.content = address_2
                add_child(address_node, delivery_point_node_2)

            if city:
                city_node = Node(names.CITY)
                city_node.content = city
                add_child(address_node, city_node)

            if state:
                administrative_area_node = Node(names.ADMINISTRATIVEAREA)
                administrative_area_node.content = state
                add_child(address_node, administrative_area_node)

            if postal_code:
                postal_code_node = Node(names.POSTALCODE)
                postal_code_node.content = postal_code
                add_child(address_node, postal_code_node)

            if country:
                country_node = Node(names.COUNTRY)
                country_node.content = country
                add_child(address_node,country_node)

            add_child(responsible_party_node, address_node)

        if phone:
            phone_node = Node(names.PHONE)
            phone_node.content = phone
            phone_node.add_attribute('phonetype', 'voice')
            add_child(responsible_party_node, phone_node)

        if fax:
            fax_node = Node(names.PHONE)
            fax_node.content = fax
            fax_node.add_attribute('phonetype', 'facsimile')
            add_child(responsible_party_node, fax_node)

        if email:
            email_node = Node(names.ELECTRONICMAILADDRESS)
            email_node.content = email
            add_child(responsible_party_node, email_node)

        if online_url:
            online_url_node = Node(names.ONLINEURL)
            online_url_node.content = online_url
            add_child(responsible_party_node, online_url_node)
             
        return responsible_party_node

    except Exception as e:
        logger.error(e)


def validate_minimal(packageid=None, title=None, contact_gn=None, 
                     contact_sn=None, creator_gn=None, creator_sn=None):
    msg = ''
    eml = Node(names.EML)

    eml.add_attribute('packageId', packageid)
    eml.add_attribute('system', 'https://pasta.edirepository.org')

    dataset = Node(names.DATASET, parent=eml)
    add_child(eml, dataset)

    title_node = Node(names.TITLE)
    title_node.content = title
    add_child(dataset, title_node)
    
    creator_node = Node(names.CREATOR, parent=dataset)
    add_child(dataset, creator_node)

    individualName_creator = Node(names.INDIVIDUALNAME, parent=creator_node)
    add_child(creator_node, individualName_creator)

    givenName_creator = Node(names.GIVENNAME, parent=individualName_creator)
    givenName_creator.content = creator_gn
    add_child(individualName_creator, givenName_creator)

    surName_creator = Node(names.SURNAME, parent=individualName_creator)
    surName_creator.content = creator_sn
    add_child(individualName_creator, surName_creator)

    contact_node = Node(names.CONTACT, parent=dataset)
    add_child(dataset, contact_node)

    individualName_contact = Node(names.INDIVIDUALNAME, parent=contact_node)
    add_child(contact_node, individualName_contact)

    givenName_contact = Node(names.GIVENNAME, parent=individualName_contact)
    givenName_contact.content = contact_gn
    add_child(individualName_contact, givenName_contact)

    surName_contact = Node(names.SURNAME, parent=individualName_contact)
    surName_contact.content = contact_sn
    add_child(individualName_contact, surName_contact)

    xml_str =  export.to_xml(eml)
    print(xml_str)

    if eml:
        msg = validate_tree(eml)

    return msg
