#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: load_data.py

:Synopsis:
Contains the helper functions for loading data tables and other entities, including reupload.
"""

import csv
import hashlib
import math
import mimetypes
import os
import re
import numpy as np
import pandas as pd
import time

from flask import flash, render_template, redirect, url_for, request, Markup
from flask_login import current_user

import daiquiri

import webapp.home.home_utils
import webapp.home.metapype_client
import webapp.home.utils.create_nodes
import webapp.home.utils.load_and_save
import webapp.home.utils.node_utils
from metapype.eml import names
from metapype.model.node import Node

from webapp.home import exceptions, check_data_table_contents

from webapp.home.exceptions import DataTableError, UnicodeDecodeErrorInternal, ExtraWhitespaceInColumnNames

import webapp.views.data_tables as data_tables

from webapp.config import Config

import webapp.auth.user_data as user_data

from flask import Blueprint

from webapp.home.utils.node_utils import new_child_node, add_child, remove_child
import webapp.home.views as views
from webapp.home.home_utils import log_error, log_info

from webapp.pages import PAGE_REUPLOAD_WITH_COL_NAMES_CHANGED, PAGE_DATA_TABLE_SELECT, PAGE_DATA_TABLE

MAX_ROWS_TO_CHECK = 10 ** 5


def get_file_size(full_path: str = ''):
    """Return the size of a file in bytes if the file exists. Otherwise, return None."""
    file_size = None
    if full_path:
        file_size = os.path.getsize(full_path)
    return file_size


def get_md5_hash(full_path: str = ''):
    """Return the MD5 hash of a file if the file exists. Otherwise, return None."""
    digest = None
    if full_path:
        with open(full_path, 'rb') as file:
            content = file.read()
            md5_hash = hashlib.md5()
            md5_hash.update(content)
            digest = md5_hash.hexdigest()
    return digest


def entity_name_from_data_file(filename: str = ''):
    """Return the entity name from a data file name. For example, if filename is FOO.CSV, return FOO."""
    entity_name = ''
    if filename:
        entity_name = filename.rsplit('.', 1)[0]
    return entity_name


def format_name_from_data_file(filename: str = ''):
    """Return the file format from a data file name. For example, if filename is FOO.CSV, return CSV."""
    if filename:
        mimetype, _ = mimetypes.guess_type(filename)
        if mimetype:
            return mimetype
        else:
            return os.path.splitext(filename)[1] # use the file extension
    else:
        return ''


# def is_datetime_column(col: str = None):
#     is_datetime = False
#
#     if col:
#         if re.search('datetime', col, flags=re.IGNORECASE):
#             is_datetime = True
#         elif re.search('^date$', col, flags=re.IGNORECASE):
#             is_datetime = True
#
#     return is_datetime


def sort_codes(codes):
    """Sorts a list of codes, putting numbers first, then text, and sorting each group alphabetically."""
    def sort_codes_key(x):
        return str(x).lower()

    nums = []
    text = []
    for code in codes:
        if isinstance(code, float) or isinstance(code, int):
            nums.append(code)
        else:
            text.append(code)
    sorted_nums = sorted(nums)
    sorted_text = sorted(text, key=sort_codes_key)
    return sorted_nums + sorted_text


def is_datetime(data_frame, col):
    """
    Attempt to determine if the column is a datetime column.

    We use an arbitrary heuristic based on the fraction of unique values that are valid datetimes.
    If not more than 20% of the values are not valid datetimes, then we assume it is a datetime column. The allowance
    for invalid datetimes is to allow for missing values codes.
    """
    rows_to_check = min(len(data_frame[col]), MAX_ROWS_TO_CHECK)
    s = pd.to_datetime(data_frame[col][1:rows_to_check], errors='coerce')
    missing = sum(bool(s.iloc[i] is pd.NaT)
              for i in range(len(s)))
    # see how many missing values... arbitrary cutoff allowing for missing values
    if len(s) > 0:
        return float(missing) / float(len(s)) < 0.2
    else:
        return False


def infer_datetime_format(dt_col):
    """Determine if the datetime column is in a known format. If so, return the format string. Otherwise, return ''."""
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
            time.strptime(dt_col, f)
        except:
            continue
        return fout
    return ''


def infer_col_type(data_frame, data_frame_raw, col):
    """
    Apply heuristics to infer the column type, expressed as a home_utils.VariableType.

    If the variable type is categorical, return a tuple (type, codes), where codes is a list of the categorical codes.
    If the variable type is datetime, return a tuple (type, format), where format is a string representing the datetime format.
    If the variable type is numerical or text, just return the variable type.
    """
    sorted_codes = None
    codes = data_frame_raw[col].unique().tolist()
    num_codes = len(codes)
    col_size = len(data_frame[col])
    # heuristic to distinguish categorical from text and numeric
    if col_size > 0:
        fraction = float(num_codes) / float(col_size)
    else:
        fraction = 1.0
    # for very large tables, this can take a very long time, so we limit to MAX_ROWS_TO_CHECK values
    rows_to_check = min(col_size, MAX_ROWS_TO_CHECK)
    dtype = data_frame[col][1:rows_to_check].infer_objects().dtype
    if dtype == np.float64 or dtype == np.int64:
        # If the values are numbers, we require 5 or fewer values to call it categorical
        is_categorical = num_codes <= 5
    else:
        is_categorical = (fraction < 0.1 and num_codes < 15) or (fraction < 0.25 and num_codes < 10) or num_codes <= 5
    if is_categorical:
        col_type = webapp.home.metapype_client.VariableType.CATEGORICAL
        sorted_codes = sort_codes(codes)
    else:
        if dtype == object:
            if is_datetime(data_frame, col):
                return webapp.home.metapype_client.VariableType.DATETIME, infer_datetime_format(data_frame[col][1])
            else:
                col_type = webapp.home.metapype_client.VariableType.TEXT
        else:
            col_type = webapp.home.metapype_client.VariableType.NUMERICAL

    # does it look like a date?
    lc_col = col.lower()
    if (
            ('year' in lc_col or 'date' in lc_col)
            and col_type == webapp.home.metapype_client.VariableType.CATEGORICAL
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

        if year_like >= len(sorted_codes) - 3:  # allowing for up to 3 distinct missing value codes
            return webapp.home.metapype_client.VariableType.DATETIME, 'YYYY'

    return col_type, sorted_codes


def guess_missing_value_code(filepath, delimiter, quotechar, colname):
    """Apply heuristics to guess the missing value code for a column in a CSV file."""

    def get_raw_csv_column_values(filepath, delimiter, quotechar, colname):
        """Get the raw column values from a CSV file. I.e., do not let pandas interpret the values."""
        if colname.startswith('Unnamed:'):
            raise DataTableError('Missing column header')

        col_values = set()
        with open(filepath, 'r', encoding='utf-8-sig') as csv_file:
            csv_reader = csv.DictReader(csv_file, delimiter=delimiter, quotechar=quotechar)
            rows = 0
            for line in csv_reader:
                val = line[colname]
                if val is not None:
                    # Sorting will fail if None values are allowed
                    col_values.add(val)
                    rows += 1
                if rows > MAX_ROWS_TO_CHECK:
                    break
        return sorted(col_values)

    col_values = get_raw_csv_column_values(filepath, delimiter, quotechar, colname)
    mvcode = None
    candidate_codes = [
        ['NA', 'na', 'N/A', 'n/a', 'NAN', 'NaN', 'nan', '#N/A'],  # These take precedence because they are the most
                                                                  # common in the EML files in the repository.
        ['Inf', 'inf', '-Inf', '-inf', 'NULL', 'Null', 'null', 'None', 'none', '-', '.']
    ]
    # See if any of the candidate codes are present in the column values. We take the first one we find.
    # The candidates are in order of precedence.
    for codes in candidate_codes:
        for code in codes:
            if code in col_values:
                mvcode = code
                break
        if mvcode:
            break
    if not mvcode:
        """
        A scan of existing EML files shows that the following codes are used quite often. Since they are likely to be
        very uncommon as actual data values, we will take them to be missing value codes if they are present in the 
        data. The only missing value codes that are used more often are NA, NaN, NAN, none, NULL, Null.
        """
        for val in col_values:
            if val.startswith('9999') or val.startswith('-9999'):
                mvcode = val
                break
    return mvcode


def force_missing_value_code(missing_value_code, dtype, codes):
    """
    If we're doing a categorical column where the codes are numerical, pandas will
     have replaced missing value codes with nan. If we've detected a missing value
     code, we substitute it for nan.
    Also, if we've picked up the missing value code as a categorical code, we remove it.
     E.g., if 'NA" is the missing value code, we don't want it to be a category.
    """

    if missing_value_code and missing_value_code in codes:
            codes.remove(missing_value_code)

    if dtype != np.float64:
        return codes

    # Sometimes we cannot use math.isnan because the code is a string
    try:
        isnan = np.isnan(codes)
    except TypeError as e:
        return codes

    if not True in isnan:
        return codes

    if missing_value_code:
        for code in codes:
            if math.isnan(code):
                codes.remove(code)
                return codes
    return codes


def force_categorical_codes(attribute_node, dtype, codes):
    """
    If we're doing a categorical column where the codes are numerical, pandas will
     treat them as floats. Codes 1, 2, 3, for example, will be interpreted as 1.0, 2.0, 3.0.
    Also, if we have picked up an empty string as a code, we remove it. I.e., we interpret
     empty strings as missing values, but we don't require that the user use an actual missing
     value code, since that would be overly fussy.
    """
    if dtype == np.float64:
        # See if the codes can be treated as ints
        ok = True
        int_codes = []
        for code in codes:
            as_is = False
            try:
                as_is = math.isnan(code)
            except TypeError as e:
                as_is = True
            if not as_is:
                try:
                    if code == int(code):
                        int_codes.append(int(code))
                    else:
                        ok = False
                        break
                except:
                    ok = False
                    break
            else:
                int_codes.append(code)
        if ok:
            codes = int_codes

    if '' in codes:
        codes.remove('')

    return sort_codes(codes)


def check_column_name_uniqueness(csv_file_path, delimiter):
    """Check that column names are unique."""
    with open(csv_file_path, 'r', encoding='utf-8-sig') as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=delimiter)
        column_names = []
        try:
            for row in csv_reader:
                column_names = row
                break
        except UnicodeDecodeError as err:
            raise UnicodeDecodeErrorInternal(csv_file_path)
        if len(set(column_names)) != len(column_names):
            raise DataTableError("Duplicated column name. Please make column names unique and try again.")


def get_num_rows(csv_filepath, delimiter: str = ',', quote_char: str = '"'):
    """Return the number of rows in a CSV file. For efficiency, we use only the first column."""
    df = pd.read_csv(csv_filepath, encoding='utf8', usecols=[0], sep=delimiter, quotechar=quote_char)
    return df.shape[0]


def load_data_table(uploads_path: str = None,
                    data_file: str = '',
                    num_header_rows: str = '1',
                    delimiter: str = ',',
                    quote_char: str = '"',
                    check_column_names: bool = False):
    """
    Load a data table CSV file and infer the corresponding metadata.

    Fills in the metadata and returns a tuple of items for use by the caller. The tuple contains the following items:
        datatable_node - the Metapype node for the data table,
        column_vartypes - a list of the variable types of the columns,
        column_names - a list of the column's names,
        column_codes - a list of codes per column. For a categorical column, the entry is a list of the categorical codes
          in the column. For a datetime column, it's the format string. For other columns, it's None.
        data_frame - the pandas data_frame for the table,
        missing_value_code - a list of missing value codes per column.
    """
    if Config.LOG_DEBUG:
        log_info(f'Entering load_data_table: {data_file}')

    full_path = f'{uploads_path}/{data_file}'

    datatable_node = new_child_node(names.DATATABLE, parent=None)

    physical_node = new_child_node(names.PHYSICAL, parent=datatable_node, attribute=('system', 'EDI'))

    entity_name_node = new_child_node(names.ENTITYNAME, parent=datatable_node,
                                      content=entity_name_from_data_file(data_file))

    object_name_node = new_child_node(names.OBJECTNAME, parent=physical_node, content=data_file)

    file_size = get_file_size(full_path)
    if file_size is not None:
        size_node = new_child_node(names.SIZE, physical_node, content=str(file_size), attribute=('unit', 'byte'))

    md5_hash = get_md5_hash(full_path)
    if md5_hash is not None:
        hash_node = new_child_node(names.AUTHENTICATION,
                                   parent=physical_node,
                                   content=str(md5_hash),
                                   attribute=('method', 'MD5'))

    data_format_node = new_child_node(names.DATAFORMAT, parent=physical_node)

    text_format_node = new_child_node(names.TEXTFORMAT, parent=data_format_node)

    num_header_lines_node = new_child_node(names.NUMHEADERLINES,
                                           parent=text_format_node,
                                           content=num_header_rows)

    num_footer_lines_node =  new_child_node(names.NUMFOOTERLINES, parent=text_format_node, content='0')

    simple_delimited_node = new_child_node(names.SIMPLEDELIMITED, parent=text_format_node)

    field_delimiter_node = new_child_node(names.FIELDDELIMITER,
                                          parent=simple_delimited_node,
                                          content=delimiter)

    quote_character_node = new_child_node(names.QUOTECHARACTER,
                                          parent=simple_delimited_node,
                                          content=quote_char)

    if file_size == 0:
        raise DataTableError("The CSV file is empty.")

    check_column_name_uniqueness(full_path, delimiter)

    with open(full_path) as file:
        next(file)
        # If the file has mixed line terminators, we get a tuple of line terminators, but PASTA doesn't
        #  support that. So we just use the first one.
        newlines = file.newlines
        if newlines is not None and isinstance(newlines, tuple):
            newlines = newlines[0]
        line_terminator = repr(newlines).replace("'", "")
    record_delimiter_node = new_child_node(names.RECORDDELIMITER,
                                           parent=text_format_node,
                                           content=line_terminator)

    # log_info('pd.read_csv')
    try:
        num_rows = get_num_rows(full_path, delimiter=delimiter, quote_char=quote_char)
        # If the number of rows is greater than a million, we will base the metadata on what we see in the
        #  first million rows.
        if num_rows > 10**6:
            flash(f'The number of rows in {os.path.basename(full_path)} is greater than 1 million. ezEML uses the '
                  f'first million rows to determine the data types of the columns and the codes used in categorical '
                  f'columns. If the first million rows are not representative of the entire file, you may need to '
                  f'manually correct the data types and categorical codes.')
        data_frame = pd.read_csv(full_path, encoding='utf8', sep=delimiter, quotechar=quote_char, nrows=min(num_rows, 10**6))
        # Load the CSV file without conversions. Used when getting the categorical codes and missing value codes.
        data_frame_raw = pd.read_csv(full_path, encoding='utf8', sep=delimiter, quotechar=quote_char,
                                     keep_default_na=False, na_values=[], dtype=str, nrows=min(num_rows, 10**6))

    except pd.errors.ParserError as e:
        raise DataTableError(e.args[0])

    column_vartypes = []
    column_names = []
    column_codes = []

    if data_frame is not None:

        number_of_records = new_child_node(names.NUMBEROFRECORDS,
                                           parent=datatable_node,
                                           content=f'{num_rows}')

        attribute_list_node = new_child_node(names.ATTRIBUTELIST, parent=datatable_node)

        # data_frame = data_frame.convert_dtypes()

        columns = data_frame.columns

        if check_column_names:
            # Check for leading/trailing whitespace in column names. We don't allow that if check_column_names is True.
            # We limit cases where we check it because we didn't used to limit in this way, so we'll have issues with
            #  Re-upload, for example, if we apply the limitation across the board.
            bad_names = []
            for col in columns:
                if col != col.strip():
                    bad_names.append(col)
            if len(bad_names) > 0:
                raise ExtraWhitespaceInColumnNames(bad_names)

        for col in columns:
            dtype = data_frame[col][1:].infer_objects().dtype

            var_type, codes = infer_col_type(data_frame, data_frame_raw, col)
            if Config.LOG_DEBUG:
                log_info(f'col: {col}  var_type: {var_type}')

            column_vartypes.append(var_type)
            column_names.append(col)
            column_codes.append(codes)

            attribute_node = new_child_node(names.ATTRIBUTE, parent=attribute_list_node)
            attribute_name_node = new_child_node(names.ATTRIBUTENAME, parent=attribute_node, content=col)

            att_label_node = new_child_node(names.ATTRIBUTELABEL, parent=attribute_node, content=col)

            att_def_node = new_child_node(names.ATTRIBUTEDEFINITION, parent=attribute_node)

            ms_node = new_child_node(names.MEASUREMENTSCALE, parent=attribute_node)

            missing_value_code = guess_missing_value_code(full_path, delimiter, quote_char, col)

            if missing_value_code:
                mv_node = new_child_node(names.MISSINGVALUECODE, parent=attribute_node)
                code_node = new_child_node(names.CODE, parent=mv_node, content=missing_value_code)

            if var_type == webapp.home.metapype_client.VariableType.CATEGORICAL:
                codes = force_categorical_codes(attribute_node, dtype, codes)
                codes = force_missing_value_code(missing_value_code, dtype, codes)

                # nominal / nonNumericDomain / enumeratedDomain / ...codes...
                nominal_node = new_child_node(names.NOMINAL, ms_node)
                non_numeric_domain_node = new_child_node(names.NONNUMERICDOMAIN, nominal_node)
                enumerated_domain_node = new_child_node(names.ENUMERATEDDOMAIN, non_numeric_domain_node)

                for code in codes:
                    code_definition_node = new_child_node(names.CODEDEFINITION, enumerated_domain_node)
                    code_node = new_child_node(names.CODE, code_definition_node, content=str(code))
                    definition_node = new_child_node(names.DEFINITION, code_definition_node)

            elif var_type == webapp.home.metapype_client.VariableType.NUMERICAL:
                # ratio / numericDomain
                ratio_node = new_child_node(names.RATIO, ms_node)
                numeric_domain_node = new_child_node(names.NUMERICDOMAIN, ratio_node)
                number_type = 'real'
                if str(dtype).startswith('int'):  # FIXME - we can do better than this
                    number_type = 'integer'
                number_type_node = new_child_node(names.NUMBERTYPE, numeric_domain_node, content=number_type)
                numeric_domain_node = new_child_node(names.UNIT, ratio_node)

            elif var_type == webapp.home.metapype_client.VariableType.TEXT:
                # nominal / nonNumericDomain / textDomain
                nominal_node = new_child_node(names.NOMINAL, ms_node)
                non_numeric_domain_node = new_child_node(names.NONNUMERICDOMAIN, nominal_node)
                text_domain_node = new_child_node(names.TEXTDOMAIN, non_numeric_domain_node)
                definition_node = new_child_node(names.DEFINITION, text_domain_node)

            elif var_type == webapp.home.metapype_client.VariableType.DATETIME:
                # dateTime / formatString
                datetime_node = Node(names.DATETIME, parent=ms_node)
                add_child(ms_node, datetime_node)

                format_string_node = Node(names.FORMATSTRING, parent=datetime_node)
                add_child(datetime_node, format_string_node)
                format_string_node.content = codes

    if Config.LOG_DEBUG:
        log_info(f'Leaving load_data_table')

    return datatable_node, column_vartypes, column_names, column_codes, data_frame, missing_value_code


def load_other_entity(dataset_node: Node = None, uploads_path: str = None, data_file: str = '', node_id: str = None):
    """
    Load an other data entity and fill in the corresponding metadata.

    Returns the other entity node in the metadata model.
    """
    full_path = f'{uploads_path}/{data_file}'

    doing_reupload = node_id is not None and node_id != '1'

    if doing_reupload:
        other_entity_node = Node.get_node_instance(node_id)
        object_name_node = other_entity_node.find_descendant(names.OBJECTNAME)
    else:
        other_entity_node = new_child_node(names.OTHERENTITY, parent=dataset_node)

        physical_node = new_child_node(names.PHYSICAL,
                                                                    parent=other_entity_node,
                                                                    attribute=('system', 'EDI'))

        entity_name_node = new_child_node(names.ENTITYNAME,
                                                                       parent=other_entity_node,
                                                                       content=entity_name_from_data_file(data_file))

        object_name_node = new_child_node(names.OBJECTNAME,
                                                                       parent=physical_node,
                                                                       content=data_file)

    physical_node = other_entity_node.find_descendant(names.PHYSICAL)

    file_size = get_file_size(full_path)
    if file_size is not None:
        size_node = other_entity_node.find_descendant(names.SIZE)
        if size_node is None:
            size_node = new_child_node(names.SIZE,
                                                                    parent=physical_node,
                                                                    content=str(file_size),
                                                                    attribute=('unit', 'byte'))

    md5_hash = get_md5_hash(full_path)
    if md5_hash is not None:
        hash_node = physical_node.find_descendant(names.AUTHENTICATION)
        if hash_node is None:
            hash_node = new_child_node(names.AUTHENTICATION,
                                                                    parent=physical_node,
                                                                    content=str(md5_hash),
                                                                    attribute=('method', 'MD5'))

    data_format_node = physical_node.find_descendant(names.DATAFORMAT)
    if data_format_node is None:
        data_format_node = new_child_node(names.DATAFORMAT, parent=physical_node)

    # If the package was created in ezEML, the dataFormat will be externallyDefinedFormat.
    # We force that to be the case here, so that's what ezEML knows how to handle.
    data_format_node.children = []

    externally_defined_format_node = new_child_node(names.EXTERNALLYDEFINEDFORMAT, parent=data_format_node)

    format_name_node = new_child_node(names.FORMATNAME,
                                                                   parent=externally_defined_format_node,
                                                                   content=format_name_from_data_file(data_file))

    if not doing_reupload:
        entity_type_node = new_child_node(names.ENTITYTYPE, parent=other_entity_node)
    else:
        entity_type_node = other_entity_node.find_descendant(names.ENTITYTYPE)
    entity_type_node.content = format_name_from_data_file(data_file)

    user_data.add_data_table_upload_filename(data_file)

    cull_data_files(uploads_path)

    return other_entity_node


def cull_data_files(data_folder: str = None):
    """
    Delete data files that are too large or are temp files.
    """
    if data_folder:
        for data_file in os.listdir(data_folder):
            file_path = os.path.join(data_folder, data_file)
            try:
                if os.path.isfile(file_path):
                    # Keep files that are under 1.5 GB except for temp files
                    # if os.path.getsize(file_path) > 1.5 * 1024**3 or file_path.endswith('.ezeml_tmp'):
                    # Get rid of temp files
                    if file_path.endswith('.ezeml_tmp'):
                        os.unlink(file_path)
            except Exception as e:
                print(e)


def data_filename_is_unique(eml_node, data_filename):
    """
    Check if the data filename is unique across both data tables and other entities. Uniqueness is required.
    """
    data_entity_name, _ = os.path.splitext(os.path.basename(data_filename))
    data_table_nodes = []
    eml_node.find_all_descendants(names.DATATABLE, data_table_nodes)
    for data_table_node in data_table_nodes:
        entity_name_node = data_table_node.find_child(names.ENTITYNAME)
        if entity_name_node and entity_name_node.content == data_entity_name:
            return False
        object_name_node = data_table_node.find_descendant(names.OBJECTNAME)
        if object_name_node and object_name_node.content == data_filename:
            return False
    other_entity_nodes = []
    eml_node.find_all_descendants(names.OTHERENTITY, other_entity_nodes)
    for other_entity_node in other_entity_nodes:
        entity_name_node = other_entity_node.find_child(names.ENTITYNAME)
        if entity_name_node and entity_name_node.content == data_entity_name:
            return False
        object_name_node = other_entity_node.find_descendant(names.OBJECTNAME)
        if object_name_node and object_name_node.content == data_filename:
            return False
    return True


def column_names_changed(filepath, delimiter, quote_char, dt_node):
    """
    Determine if column names have changed.

    Logically, this function belongs as a nested function within handle_reupload(), but such nesting makes
    handle_reupload() too hard to read.

    Assumes CSV file has been saved to the file system.
    """
    data_frame = pd.read_csv(filepath, encoding='utf8', sep=delimiter, quotechar=quote_char, nrows=1)
    columns = data_frame.columns
    new_column_names = []
    for col in columns:
        new_column_names.append(col)

    old_column_names = []
    if dt_node:
        attribute_list_node = dt_node.find_child(names.ATTRIBUTELIST)
        if attribute_list_node:
            for attribute_node in attribute_list_node.children:
                attribute_name_node = attribute_node.find_child(names.ATTRIBUTENAME)
                if attribute_name_node:
                    old_column_names.append(attribute_name_node.content)

    if len(old_column_names) != len(new_column_names):
        raise exceptions.NumberOfColumnsHasChanged(
            f'Number of columns has changed from {len(old_column_names)} to {len(new_column_names)}.')

    return old_column_names != new_column_names


def get_column_properties(eml_node, document, dt_node, object_name):
    """
    Load the data table and return its column properties -- e.g., variable types, column names, codes, etc.

    Logically, this function belongs as a nested function within handle_reupload(), but such nesting makes
    handle_reupload() too hard to read.
    """
    data_file = object_name
    # If we have already uploaded this file, we can get the column properties from the user data.
    column_vartypes, _, _ = user_data.get_uploaded_table_column_properties(data_file)
    if column_vartypes:
        return column_vartypes

    uploads_folder = user_data.get_document_uploads_folder_name()
    num_header_rows = '1'
    field_delimiter_node = dt_node.find_descendant(names.FIELDDELIMITER)
    if field_delimiter_node:
        delimiter = field_delimiter_node.content
    else:
        delimiter = ','
    quote_char_node = dt_node.find_descendant(names.QUOTECHARACTER)
    if quote_char_node:
        quote_char = quote_char_node.content
    else:
        quote_char = '"'
    try:
        # Load the data table from the file system and get the column properties.
        new_dt_node, new_column_vartypes, new_column_names, new_column_codes, *_ = load_data_table(
            uploads_folder, data_file, num_header_rows, delimiter, quote_char)

        # Save the column properties to the user data.
        user_data.add_uploaded_table_properties(data_file,
                                                new_column_vartypes,
                                                new_column_names,
                                                new_column_codes)

        return new_column_vartypes

    except FileNotFoundError:
        raise FileNotFoundError(
            'The older version of the data table is missing from our server. Please use "Load Data Table from CSV File" instead of "Re-upload".')

    except Exception as err:
        raise exceptions.InternalError('Internal error 103')

    except UnicodeDecodeError as err:
        fullpath = os.path.join(uploads_folder, data_file)
        errors = views.display_decode_error_lines(fullpath)
        return render_template('encoding_error.html', filename=data_file, errors=errors)


def check_data_table_similarity(old_dt_node, new_dt_node, new_column_vartypes, new_column_names, new_column_codes):
    """
    Examine the old and new data tables to determine if they are similar enough to be amenable to re-uploading.
    If they are not similar enough, raise an exception. We use exceptions rather than a boolean return value so
    we can provide the user with a meaningful error message.

    Logically, this function belongs as a nested function within handle_reupload(), but such nesting makes
    handle_reupload() too hard to read.
    """
    if not old_dt_node or not new_dt_node:
        raise exceptions.InternalError('Internal error 100')

    # See if the old and new tables have the same number of columns
    old_attribute_list = old_dt_node.find_child(names.ATTRIBUTELIST)
    new_attribute_list = new_dt_node.find_child(names.ATTRIBUTELIST)
    if len(old_attribute_list.children) != len(new_attribute_list.children):
        raise exceptions.ReuploadTableNumColumnsError('The new table has a different number of columns from the original table.')

    # See if the old and new tables have the same column types
    document = current_user.get_filename()
    old_object_name_node = old_dt_node.find_descendant(names.OBJECTNAME)
    if not old_object_name_node:
        raise exceptions.InternalError('Internal error 101')
    old_object_name = old_object_name_node.content
    if not old_object_name:
        raise exceptions.InternalError('Internal error 102')
    old_column_vartypes, _, _ = user_data.get_uploaded_table_column_properties(old_object_name)
    if not old_column_vartypes:
        # column properties weren't saved. compute them anew.
        eml_node = webapp.home.utils.load_and_save.load_eml(filename=document)
        old_column_vartypes = get_column_properties(eml_node, document, old_dt_node, old_object_name)
    if old_column_vartypes != new_column_vartypes:
        diffs = []
        for col_name, old_type, new_type, attr_node in zip(new_column_names, old_column_vartypes,
                                                           new_column_vartypes, old_attribute_list.children):
            if old_type != new_type:
                diffs.append((col_name, old_type, new_type, attr_node))
        raise exceptions.ReuploadTableColumnTypesError(diffs)


def handle_reupload(dt_node_id=None, saved_filename=None, document=None,
                    eml_node=None, uploads_folder=None, name_chg_ok=False,
                    delimiter=None, quote_char=None):
    """
    When a data table is re-uploaded, we need to perform various checks in addition to doing load_data_table().
    Also, we need to re-use existing nodes where possible so that we don't lose any user edits for attribute
    descriptions and the like.
    """
    dataset_node = eml_node.find_child(names.DATASET)
    if not dataset_node:
        dataset_node = new_child_node(names.DATASET, eml_node)

    # saved_filename is the name of the file on the server. It is not the same as the original filename because
    #  we've saved the file as a temp file so we have both files and can compare them.
    if not saved_filename:
        raise exceptions.MissingFileError('Unexpected error: file not found')

    dt_node = Node.get_node_instance(dt_node_id)

    num_header_rows = '1'
    filepath = os.path.join(uploads_folder, saved_filename)

    if not name_chg_ok:
        try:
            # If column names have changed, we get confirmation from the user before proceeding. This is done
            #  to safeguard against the user accidentally uploading the wrong file.
            if column_names_changed(filepath, delimiter, quote_char, dt_node):
                # Go get confirmation
                return redirect(url_for(PAGE_REUPLOAD_WITH_COL_NAMES_CHANGED,
                                        saved_filename=saved_filename,
                                        dt_node_id=dt_node_id),
                                code=307)
        except exceptions.NumberOfColumnsHasChanged as err:
            flash('The number of columns in the uploaded file is different from the number of columns in the table '
                  'it is replacing. Instead of using Re-upload, you will need to upload the table as a new '
                  'table. You can then use "Clone Column Properties from Another Data Table" to copy the column '
                  'properties that the tables have in common, after which you can delete the old version.', 'error')
            return redirect(url_for(PAGE_DATA_TABLE_SELECT, filename=document))
        except UnicodeDecodeError as err:
            errors = views.display_decode_error_lines(filepath)
            filename = os.path.basename(filepath)
            return render_template('encoding_error.html', filename=filename, errors=errors)
    try:
        new_dt_node, new_column_vartypes, new_column_names, new_column_codes, *_ = load_data_table(
            uploads_folder, saved_filename, num_header_rows, delimiter, quote_char)

        types_changed = None
        try:
            check_data_table_similarity(dt_node,
                                        new_dt_node,
                                        new_column_vartypes,
                                        new_column_names,
                                        new_column_codes)

        except exceptions.ReuploadTableColumnTypesError as err:
            # One or more column types have changed. Capture the list of changes from the exception and proceed.
            # This isn't an error, but we need to know that the types have changed so that we can tell the user.
            types_changed = err.args[0]

        except FileNotFoundError as err:
            error = err.args[0]
            flash(error, 'error')
            return redirect(url_for(PAGE_DATA_TABLE_SELECT, filename=document))

        except exceptions.ReuploadTableNumColumnsError as err:
            error = err.args[0]
            flash(f'Re-upload not done. {error}', 'error')
            return redirect(url_for(PAGE_DATA_TABLE_SELECT, filename=document))

        try:
            # use the existing dt_node, but update objectName, size, rows, MD5, etc.
            # also, update column names and categorical codes, as needed
            update_data_table(dt_node, new_dt_node, new_column_names, new_column_codes)
            # rename the temp file
            os.rename(filepath, filepath.replace('.ezeml_tmp', ''))

            if types_changed:
                err_string = 'Please note: One or more columns in the new table have a different data type than they '\
                             'had in the old table.<ul>'
                for col_name, old_type, new_type, attr_node in types_changed:
                    data_tables.dt.change_measurement_scale(attr_node, old_type.name, new_type.name)
                    err_string += f'<li><b>{col_name}</b> changed from {old_type.name} to {new_type.name}'
                err_string += '</ul>'
                flash(Markup(err_string))

        except Exception as err:
            # display error
            error = err.args[0]
            flash(f"Data table could not be re-uploaded. {error}", 'error')
            return redirect(url_for(PAGE_DATA_TABLE_SELECT, filename=document))

    except UnicodeDecodeError as err:
        errors = views.display_decode_error_lines(filepath)
        return render_template('encoding_error.html', filename=document, errors=errors)

    except exceptions.UnicodeDecodeErrorInternal as err:
            filepath = err.message
            errors = views.display_decode_error_lines(filepath)
            return render_template('encoding_error.html', filename=os.path.basename(filepath), errors=errors)

    except exceptions.DataTableError as err:
        flash(f'Data table has an error: {err.message}', 'error')
        return redirect(request.url)

    data_file = saved_filename.replace('.ezeml_tmp', '')
    flash(f"Loaded {data_file}")

    dt_node.parent = dataset_node
    object_name_node = dt_node.find_descendant(names.OBJECTNAME)
    if object_name_node:
        object_name_node.content = data_file

    user_data.add_data_table_upload_filename(data_file)
    if new_column_vartypes:
        user_data.add_uploaded_table_properties(data_file,
                                                new_column_vartypes,
                                                new_column_names,
                                                new_column_codes)

    cull_data_files(uploads_folder)

    views.clear_distribution_url(dt_node)
    views.insert_upload_urls(document, eml_node)

    views.backup_metadata(filename=document)  # FIXME - what is this doing? is it obsolete?

    check_data_table_contents.reset_data_file_eval_status(document, data_file)
    check_data_table_contents.set_check_data_tables_badge_status(document, eml_node)

    webapp.home.utils.load_and_save.save_both_formats(filename=document, eml_node=eml_node)
    return redirect(url_for(PAGE_DATA_TABLE, filename=document, dt_node_id=dt_node.id, delimiter=delimiter,
                            quote_char=quote_char))


def update_data_table(old_dt_node, new_dt_node, new_column_names, new_column_codes, doing_xml_import=False):
    """
    Update the metadata for a data table that is being fetched or reuploaded. In such cases, metadata for the table
    already exists (e.g., in fetch, we fetch the package's metadata first and then do the data tables), but we need to
    update it with new information -- e.g., number of rows, column names, categorical codes, etc., may have changed.
    """

    def compare_codes(old_codes, new_codes):
        """
        Determine if the old and new column codes are the same.
        For a categorical column, the list entry is a list of categorical codes. For a datetime column, it's the format
            string. For a numeric column, it's None.
        """

        def substitute_nans(codes):
            """ Replace NaNs with 'NAN' so that codes can be compared without differently expressed NaNs causing
            false positives. """
            substituted = []
            if codes:
                for code in codes:
                    if isinstance(code, list):
                        # A list, so we're dealing with a categorical column. Recursively call this function to
                        #   substitute NaNs in the list of categorical codes.
                        substituted.append(substitute_nans(code))
                    elif not isinstance(code, float) or not math.isnan(code):
                        # Not a NaN, so just append it.
                        substituted.append(code)
                    else:
                        # A NaN, so append 'NAN'. That way, we can compare the old and new codes and not be fooled
                        #   by NaNs expressed differently.
                        substituted.append('NAN')
            else:
                substituted.append(None)
            return substituted

        old_substituted = substitute_nans(old_codes)
        new_substituted = substitute_nans(new_codes)
        return old_substituted == new_substituted

    def add_node_if_missing(parent_node, child_name):
        """ Add a child node to a parent node if the child doesn't already exist. """
        child = parent_node.find_descendant(child_name)
        if not child:
            child = new_child_node(child_name, parent=parent_node)
        return child

    views.debug_msg(f'Entering update_data_table')

    if not old_dt_node or not new_dt_node:
        return

    # Get the old and new table attributes.

    old_object_name_node = old_dt_node.find_descendant(names.OBJECTNAME)
    old_physical_node = add_node_if_missing(old_dt_node, names.PHYSICAL)
    old_data_format_node = add_node_if_missing(old_physical_node, names.DATAFORMAT)
    old_text_format_node = add_node_if_missing(old_data_format_node, names.TEXTFORMAT)
    old_simple_delimited_node = add_node_if_missing(old_text_format_node, names.SIMPLEDELIMITED)

    old_size_node = add_node_if_missing(old_physical_node, names.SIZE)
    old_records_node = add_node_if_missing(old_dt_node, names.NUMBEROFRECORDS)
    old_md5_node = add_node_if_missing(old_physical_node, names.AUTHENTICATION)
    old_field_delimiter_node = add_node_if_missing(old_simple_delimited_node, names.FIELDDELIMITER)
    old_record_delimiter_node = add_node_if_missing(old_text_format_node, names.RECORDDELIMITER)
    old_quote_char_node = add_node_if_missing(old_simple_delimited_node, names.QUOTECHARACTER)

    new_object_name_node = new_dt_node.find_descendant(names.OBJECTNAME)
    new_size_node = new_dt_node.find_descendant(names.SIZE)
    new_records_node = new_dt_node.find_descendant(names.NUMBEROFRECORDS)
    new_md5_node = new_dt_node.find_descendant(names.AUTHENTICATION)
    new_field_delimiter_node = new_dt_node.find_descendant(names.FIELDDELIMITER)
    new_record_delimiter_node = new_dt_node.find_descendant(names.RECORDDELIMITER)
    new_quote_char_node = new_dt_node.find_descendant(names.QUOTECHARACTER)

    old_object_name = old_object_name_node.content
    old_object_name_node.content = new_object_name_node.content.replace('.ezeml_tmp', '')

    old_size_node.content = new_size_node.content
    old_records_node.content = new_records_node.content
    old_md5_node.content = new_md5_node.content
    old_field_delimiter_node.content = new_field_delimiter_node.content

    # record delimiter node is not required, so may be missing
    if new_record_delimiter_node:
        old_record_delimiter_node.content = new_record_delimiter_node.content
    else:
        remove_child(old_record_delimiter_node)

    # quote char node is not required, so may be missing
    if new_quote_char_node:
        old_quote_char_node.content = new_quote_char_node.content
    else:
        remove_child(old_quote_char_node)

    # If we're fetching the package, we take the metadata as given. But if we're doing re-upload, we need to update
    #   the metadata as needed. We don't want to lost things like column definitions that have been entered by the user.

    if not doing_xml_import:
        _, old_column_names, old_column_codes = user_data.get_uploaded_table_column_properties(old_object_name)
        if old_column_names and old_column_names != new_column_names:
            # substitute the new column names
            old_attribute_list_node = old_dt_node.find_child(names.ATTRIBUTELIST)
            old_attribute_names_nodes = []
            old_attribute_list_node.find_all_descendants(names.ATTRIBUTENAME, old_attribute_names_nodes)
            for old_attribute_names_node, old_name, new_name in zip(old_attribute_names_nodes, old_column_names, new_column_names):
                if old_name != new_name:
                    views.debug_None(old_attribute_names_node, 'old_attribute_names_node is None')
                    old_attribute_names_node.content = new_name
        if not compare_codes(old_column_codes, new_column_codes):
            # need to fix up the categorical codes
            old_attribute_list_node = old_dt_node.find_child(names.ATTRIBUTELIST)
            old_attribute_nodes = old_attribute_list_node.find_all_children(names.ATTRIBUTE)
            new_attribute_list_node = new_dt_node.find_child(names.ATTRIBUTELIST)
            new_attribute_nodes = new_attribute_list_node.find_all_children(names.ATTRIBUTE)
            for old_attribute_node, old_codes, new_attribute_node, new_codes in zip(old_attribute_nodes,
                                                                                    old_column_codes,
                                                                                    new_attribute_nodes,
                                                                                    new_column_codes):
                if not compare_codes(old_codes, new_codes):
                    # use the new_codes, preserving any relevant code definitions
                    # first, get the old codes and their definitions
                    old_code_definition_nodes = []
                    old_attribute_node.find_all_descendants(names.CODEDEFINITION, old_code_definition_nodes)
                    code_definitions = {}
                    parent_node = None
                    for old_code_definition_node in old_code_definition_nodes:
                        code_node = old_code_definition_node.find_child(names.CODE)
                        code = None
                        if code_node:
                            code = str(code_node.content)
                        definition_node = old_code_definition_node.find_child(names.DEFINITION)
                        definition = None
                        if definition_node:
                            definition = definition_node.content
                        if code and definition:
                            code_definitions[code] = definition
                        # remove the old code definition node
                        parent_node = old_code_definition_node.parent
                        remove_child(old_code_definition_node)
                    # add clones of new definition nodes and set their definitions, if known
                    if not parent_node:
                        continue
                    new_code_definition_nodes = []
                    new_attribute_node.find_all_descendants(names.CODEDEFINITION, new_code_definition_nodes)
                    for new_code_definition_node in new_code_definition_nodes:
                        clone = new_code_definition_node.copy()
                        parent_node.add_child(clone)
                        clone.parent = parent_node
                        code_node = clone.find_child(names.CODE)
                        if code_node:
                            code = str(code_node.content)
                        else:
                            code = None
                        definition_node = clone.find_child(names.DEFINITION)
                        definition = code_definitions.get(code)
                        if definition:
                            definition_node.content = definition
    views.debug_msg(f'Leaving update_data_table')