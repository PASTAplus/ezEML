#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: load_data_table.py

:Synopsis:

:Author:
    costa
    ide

:Created:
    5/9/19
"""

import hashlib
import os
import re
import pandas as pd
import time

from metapype.eml import names
from metapype.model.node import Node

from webapp.home.metapype_client import ( 
    add_child, new_child_node, VariableType
)

from webapp.auth.user_data import (
    add_data_table_upload_filename
)


def get_file_size(full_path:str=''):
    file_size = None
    if full_path:
        file_size = os.path.getsize(full_path)
    return file_size


def get_md5_hash(full_path:str=''):
    digest = None
    if full_path:
        with open(full_path, 'rb') as file:
            content = file.read()
            md5_hash = hashlib.md5()
            md5_hash.update(content)
            digest = md5_hash.hexdigest()
    return digest


def entity_name_from_data_file(filename:str=''):
    entity_name = ''
    if filename:
        entity_name = filename.rsplit('.', 1)[0]
    return entity_name


def format_name_from_data_file(filename:str=''):
    format_name = ''
    if filename:
        format_name = filename.rsplit('.', 1)[1]
    return format_name


def is_datetime_column(col:str=None):
    is_datetime = False

    if col:
        if re.search('datetime', col, flags=re.IGNORECASE):
            is_datetime = True
        elif re.search('^date$', col, flags=re.IGNORECASE):
            is_datetime = True

    return is_datetime


def sort_codes_key(x):
    try:
        i = int(x)
        return str(i)
    except:
        pass
    return str(x).lower()


def sort_codes(codes):
    nums = []
    text = []
    for code in codes:
        try:
            i = int(code)
            nums.append(i)
        except:
            text.append(code)
    sorted_nums = sorted(nums)
    all_sorted = sorted(text, key=sort_codes_key)
    for num in sorted_nums:
        all_sorted.append(str(num))
    return all_sorted


def is_datetime(data_frame, col):
    s = pd.to_datetime(data_frame[col][1:], errors='coerce')
    missing = sum(1 for i in range(len(s)) if s.iloc[i] is pd.NaT)
    # see how many missing values... arbitrary cutoff allowing for missing values
    return float(missing) / float(len(s)) < 0.2


def infer_datetime_format(dt):
    formats = [
        ('%Y', 'YYYY'),
        ('%Y-%m-%d', 'YYYY-MM-DD'),
        ('%Y-%m-%d %H:%M', 'YYYY-MM-DD hh:mm'),
        ('%Y-%m-%d %H:%M:%S', 'YYYY-MM-DD hh:mm:ss'),
        ('%Y-%m-%dT%H:%M', 'YYYY-MM-DDThh:mm'),
        ('%Y-%m-%dT%H:%M:%S', 'YYYY-MM-DDThh:mm:ss'),
        ('%Y-%m-%dT%H:%M:%S-%H', 'YYYY-MM-DDThh:mm:ss-hh')
    ]
    for f, fout in formats:
        try:
            time.strptime(dt, f)
        except:
            continue
        return fout
    return ''


def infer_col_type(data_frame, col):
    col_type = None
    sorted_codes = None
    codes = data_frame[col].unique().tolist()
    num_codes = len(codes)
    col_size = len(data_frame[col])
    # arbitrary test to distinguish categorical from text
    is_categorical = float(num_codes) / float(col_size) < 0.1 and num_codes < 15
    if is_categorical:
        col_type = VariableType.CATEGORICAL
        sorted_codes = sort_codes(codes)
    else:
        dtype = data_frame[col][1:].infer_objects().dtype
        if dtype == object:
            if is_datetime(data_frame, col):
                return VariableType.DATETIME, infer_datetime_format(data_frame[col][1])
            else:
                col_type = VariableType.TEXT
        else:
            col_type = VariableType.NUMERICAL

    # does it look like a date?
    lc_col = col.lower()
    if (
        ('year' in lc_col or 'date' in lc_col)
        and col_type == VariableType.CATEGORICAL
        and is_datetime(data_frame, col)
    ):
        # make sure we don't just have numerical codes that are incorrectly being treated as years
        # see if most of the codes look like years
        # we say "most" to allow for missing-value codes
        year_like = 0
        for code in sorted_codes:
            try:
                year = int(code)
                if year >= 1900 and year <= 2100:
                    year_like += 1
            except:
                pass

        if year_like >= len(sorted_codes) - 3:  # allowing for up to 3 missing value codes
            return VariableType.DATETIME, 'YYYY'

    return col_type, sorted_codes


def load_data_table(dataset_node:Node=None, uploads_path:str=None, data_file:str=''):
    full_path = f'{uploads_path}/{data_file}'

    datatable_node = new_child_node(names.DATATABLE, parent=dataset_node)

    physical_node = new_child_node(names.PHYSICAL, parent=datatable_node)
    physical_node.add_attribute('system', 'EDI')

    entity_name_node = new_child_node(names.ENTITYNAME, parent=datatable_node)
    entity_name = entity_name_from_data_file(data_file)
    entity_name_node.content = entity_name

    object_name_node = new_child_node(names.OBJECTNAME, parent=physical_node)
    object_name_node.content = data_file

    file_size = get_file_size(full_path)
    if file_size is not None:
        size_node = new_child_node(names.SIZE, physical_node)
        size_node.add_attribute('unit', 'byte')
        size_node.content = str(file_size)

    md5_hash = get_md5_hash(full_path)
    if md5_hash is not None:
        hash_node = Node(names.AUTHENTICATION, parent=physical_node)
        add_child(physical_node, hash_node)
        hash_node.add_attribute('method', 'MD5')
        hash_node.content = str(md5_hash)

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

    with open(full_path) as file:
        next(file)
        line_terminator = repr(file.newlines).replace("'", "")
    record_delimiter_node = Node(names.RECORDDELIMITER, parent=text_format_node)
    add_child(text_format_node, record_delimiter_node)
    record_delimiter_node.content = line_terminator

    data_frame = pd.read_csv(full_path, comment='#')

    if data_frame is not None:

        number_of_records = Node(names.NUMBEROFRECORDS, parent=datatable_node)
        add_child(datatable_node, number_of_records)
        row_count = data_frame.shape[0]
        record_count = row_count
        number_of_records.content = f'{record_count}'

        attribute_list_node = Node(names.ATTRIBUTELIST, parent=datatable_node)
        add_child(datatable_node, attribute_list_node)

        columns = data_frame.columns

        for col in columns:
            dtype = data_frame[col][1:].infer_objects().dtype

            var_type, codes = infer_col_type(data_frame, col)

            attribute_node = new_child_node(names.ATTRIBUTE, attribute_list_node)
            attribute_name_node = new_child_node(names.ATTRIBUTENAME, attribute_node)
            attribute_name_node.content = col
        
            att_label_node = Node(names.ATTRIBUTELABEL, parent=attribute_node)
            add_child(attribute_node, att_label_node)
            att_label_node.content = col
        
            att_def_node = Node(names.ATTRIBUTEDEFINITION, parent=attribute_node)
            add_child(attribute_node, att_def_node)

            ms_node = Node(names.MEASUREMENTSCALE, parent=attribute_node)
            add_child(attribute_node, ms_node)

            if var_type == VariableType.CATEGORICAL:
                # nominal / nonNumericDomain / enumeratedDomain / ...codes...
                nominal_node = new_child_node(names.NOMINAL, ms_node)
                non_numeric_domain_node = new_child_node(names.NONNUMERICDOMAIN, nominal_node)
                enumerated_domain_node = new_child_node(names.ENUMERATEDDOMAIN, non_numeric_domain_node)

                for code in codes:
                    code_definition_node = new_child_node(names.CODEDEFINITION, enumerated_domain_node)
                    code_node = new_child_node(names.CODE, code_definition_node)
                    code_node.content = code
                    definition_node = new_child_node(names.DEFINITION, code_definition_node)

            elif var_type == VariableType.NUMERICAL:
                # ratio / numericDomain
                ratio_node = new_child_node(names.RATIO, ms_node)
                numeric_domain_node = new_child_node(names.NUMERICDOMAIN, ratio_node)
                number_type = 'real'
                if str(dtype).startswith('int'):  # FIXME - we can do better than this
                    number_type = 'integer'
                number_type_node = new_child_node(names.NUMBERTYPE, numeric_domain_node)
                number_type_node.content = number_type
                numeric_domain_node = new_child_node(names.UNIT, ratio_node)

            elif var_type == VariableType.TEXT:
                # nominal / nonNumericDomain / textDomain
                nominal_node = new_child_node(names.NOMINAL, ms_node)
                non_numeric_domain_node = new_child_node(names.NONNUMERICDOMAIN, nominal_node)
                text_domain_node = new_child_node(names.TEXTDOMAIN, non_numeric_domain_node)
                definition_node = new_child_node(names.DEFINITION, text_domain_node)

            elif var_type == VariableType.DATETIME:
                # dateTime / formatString
                datetime_node = Node(names.DATETIME, parent=ms_node)
                add_child(ms_node, datetime_node)

                format_string_node = Node(names.FORMATSTRING, parent=datetime_node)
                add_child(datetime_node, format_string_node)
                format_string_node.content = codes

    add_data_table_upload_filename(data_file)

    delete_data_files(uploads_path)

    return datatable_node


def load_other_entity(dataset_node: Node = None, uploads_path: str = None, data_file: str = ''):
    full_path = f'{uploads_path}/{data_file}'

    other_entity_node = Node(names.OTHERENTITY, parent=dataset_node)
    add_child(dataset_node, other_entity_node)

    physical_node = Node(names.PHYSICAL, parent=other_entity_node)
    add_child(other_entity_node, physical_node)
    physical_node.add_attribute('system', 'EDI')

    entity_name_node = Node(names.ENTITYNAME, parent=other_entity_node)
    add_child(other_entity_node, entity_name_node)
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

    md5_hash = get_md5_hash(full_path)
    if md5_hash is not None:
        hash_node = Node(names.AUTHENTICATION, parent=physical_node)
        add_child(physical_node, hash_node)
        hash_node.add_attribute('method', 'MD5')
        hash_node.content = str(md5_hash)

    data_format_node = Node(names.DATAFORMAT, parent=physical_node)
    add_child(physical_node, data_format_node)

    externally_defined_format_node = Node(names.EXTERNALLYDEFINEDFORMAT, parent=data_format_node)
    add_child(data_format_node, externally_defined_format_node)

    format_name_node = Node(names.FORMATNAME, parent=externally_defined_format_node)
    add_child(externally_defined_format_node, format_name_node)
    format_name_node.content = format_name_from_data_file(data_file)

    entity_type_node = new_child_node(names.ENTITYTYPE, parent=other_entity_node)
    entity_type_node.content = format_name_from_data_file(data_file)

    delete_data_files(uploads_path)

    return other_entity_node


def delete_data_files(data_folder:str=None):
    if data_folder:
        for data_file in os.listdir(data_folder):
            file_path = os.path.join(data_folder, data_file)
            try:
                if os.path.isfile(file_path):
                    # Keep smaller files around for troubleshooting purposes
                    if os.path.getsize(file_path) > 10**7:
                        os.unlink(file_path)
            except Exception as e:
                print(e)
