#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: load_data_table.py

:Synopsis:

:Author:
    costa

:Created:
    5/9/19
"""

import os
import re
import pandas as pd

from metapype.eml.exceptions import MetapypeRuleError
from metapype.eml import export
from metapype.eml import evaluate
from metapype.eml import names
from metapype.eml import rule
from metapype.eml import validate
from metapype.model import mp_io
from metapype.model.node import Node

from webapp.home.metapype_client import ( 
    add_child
)


def get_file_size(full_path:str=''):
    file_size = None
    if full_path:
        file_size = os.path.getsize(full_path)
    return file_size


def entity_name_from_data_file(filename:str=''):
    entity_name = ''
    if filename:
        entity_name = filename.rsplit('.', 1)[0]
    return entity_name


def is_datetime_column(col:str=None):
    is_datetime = False

    if col:
        if re.search('datetime', col, flags=re.IGNORECASE):
            is_datetime = True
        elif re.search('^date$', col, flags=re.IGNORECASE):
            is_datetime = True

    return is_datetime


def load_data_table(dataset_node:Node=None, uploads_path:str=None, data_file:str=''):
    full_path = f'{uploads_path}/{data_file}'
    datatable_node = Node(names.DATATABLE, parent=dataset_node)
    add_child(dataset_node, datatable_node)

    physical_node = Node(names.PHYSICAL, parent=datatable_node)
    add_child(datatable_node, physical_node)
    physical_node.add_attribute('system', 'EDI')

    entity_name_node = Node(names.ENTITYNAME, parent=datatable_node)
    add_child(datatable_node, entity_name_node)
    entity_name = entity_name_from_data_file(data_file)
    entity_name_node.content = entity_name

    object_name_node = Node(names.OBJECTNAME, parent=physical_node)
    add_child(physical_node, object_name_node)
    object_name_node.content = data_file

    file_size = get_file_size(full_path)
    if file_size is not None:
        size_node = Node(names.SIZE, parent=physical_node)
        add_child(physical_node, size_node)
        size_node.add_attribute('unit', 'byte')
        size_node.content = str(file_size)

    data_format_node = Node(names.DATAFORMAT, parent=physical_node)
    add_child(physical_node, data_format_node)

    text_format_node = Node(names.TEXTFORMAT, parent=data_format_node)
    add_child(data_format_node, text_format_node)

    num_header_lines_node = Node(names.NUMHEADERLINES, parent=text_format_node)
    add_child(text_format_node, num_header_lines_node)
    num_header_lines_node.content = '1'
    
    num_footer_lines_node = Node(names.NUMFOOTERLINES, parent=text_format_node)
    add_child(text_format_node, num_footer_lines_node)
    num_footer_lines_node.content = '0'

    data_frame = pd.read_csv(full_path, comment='#')

    if data_frame is not None:

        number_of_records = Node(names.NUMBEROFRECORDS, parent=datatable_node)
        add_child(datatable_node, number_of_records)
        row_count = data_frame.shape[0]
        number_of_records.content = f'{row_count}'

        attribute_list_node = Node(names.ATTRIBUTELIST, parent=datatable_node)
        add_child(datatable_node, attribute_list_node)

        columns = data_frame.columns

        for col in columns:
            dtype = str(data_frame[col].dtype)
            print(f'{col}: {dtype}')

            attribute_node = Node(names.ATTRIBUTE, parent=attribute_list_node)
            add_child(attribute_list_node, attribute_node)
        
            attribute_name_node = Node(names.ATTRIBUTENAME, parent=attribute_node)
            add_child(attribute_node, attribute_name_node)
            attribute_name_node.content = col
        
            att_label_node = Node(names.ATTRIBUTELABEL, parent=attribute_node)
            add_child(attribute_node, att_label_node)
            att_label_node.content = col
        
            att_def_node = Node(names.ATTRIBUTEDEFINITION, parent=attribute_node)
            add_child(attribute_node, att_def_node)
            att_def_node.content = f'Attribute definition for {col}'
        
            ms_node = Node(names.MEASUREMENTSCALE, parent=attribute_node)
            add_child(attribute_node, ms_node)

            if dtype == 'bool':

                nominal_node = Node(names.NOMINAL, parent=ms_node)
                add_child(ms_node, nominal_node)

                non_numeric_domain_node = Node(names.NONNUMERICDOMAIN, parent=nominal_node)
                add_child(nominal_node, non_numeric_domain_node)

            elif dtype == 'object':

                if is_datetime_column(col):
                    datetime_node = Node(names.DATETIME, parent=ms_node)
                    add_child(ms_node, datetime_node)

                    format_string_node = Node(names.FORMATSTRING, parent=datetime_node)
                    add_child(datetime_node, format_string_node)
                    format_string_node.content = ''

                else:
                    nominal_node = Node(names.NOMINAL, parent=ms_node)
                    add_child(ms_node, nominal_node)

                    non_numeric_domain_node = Node(names.NONNUMERICDOMAIN, parent=nominal_node)
                    add_child(nominal_node, non_numeric_domain_node)

            elif dtype.startswith('float') or dtype.startswith('int'):

                number_type = 'real'
                if dtype.startswith('int'):
                    number_type = 'integer'

                ratio_node = Node(names.RATIO, parent=ms_node)
                add_child(ms_node, ratio_node)

                numeric_domain_ratio_node = Node(names.NUMERICDOMAIN, parent=ratio_node)
                add_child(ratio_node, numeric_domain_ratio_node)

                number_type_ratio_node = Node(names.NUMBERTYPE, parent=numeric_domain_ratio_node)
                add_child(numeric_domain_ratio_node, number_type_ratio_node)
                number_type_ratio_node.content = number_type

    delete_data_files(uploads_path)

    return datatable_node


def delete_data_files(data_folder:str=None):
    if data_folder:
        for data_file in os.listdir(data_folder):
            file_path = os.path.join(data_folder, data_file)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                print(e)
