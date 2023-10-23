#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: load_data.py

:Synopsis:

:Author:
    costa
    ide

:Created:
    5/9/19
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

import daiquiri

from metapype.eml import names
from metapype.model.node import Node

import webapp.home.metapype_client as metapype_client

from webapp.home.exceptions import DataTableError, UnicodeDecodeErrorInternal, ExtraWhitespaceInColumnNames

from flask import Flask, current_app, flash
from flask_login import current_user

from webapp.config import Config

import webapp.auth.user_data as user_data

from flask import Blueprint
home = Blueprint('home', __name__, template_folder='templates')

MAX_ROWS_TO_CHECK = 10 ** 5

logger = daiquiri.getLogger('load_data_table: ' + __name__)


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


# def log_info(msg):
#     app = Flask(__name__)
#     with app.app_context():
#         current_app.logger.info(msg)


def get_file_size(full_path: str = ''):
    file_size = None
    if full_path:
        file_size = os.path.getsize(full_path)
    return file_size


def get_md5_hash(full_path: str = ''):
    digest = None
    if full_path:
        with open(full_path, 'rb') as file:
            content = file.read()
            md5_hash = hashlib.md5()
            md5_hash.update(content)
            digest = md5_hash.hexdigest()
    return digest


def entity_name_from_data_file(filename: str = ''):
    entity_name = ''
    if filename:
        entity_name = filename.rsplit('.', 1)[0]
    return entity_name


def format_name_from_data_file(filename: str = ''):
    if filename:
        mimetype, _ = mimetypes.guess_type(filename)
        if mimetype:
            return mimetype
        else:
            return filename.rsplit('.', 1)[1]
    else:
        return ''


def is_datetime_column(col: str = None):
    is_datetime = False

    if col:
        if re.search('datetime', col, flags=re.IGNORECASE):
            is_datetime = True
        elif re.search('^date$', col, flags=re.IGNORECASE):
            is_datetime = True

    return is_datetime


def sort_codes_key(x):
    return str(x).lower()


def sort_codes(codes):
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
    rows_to_check = min(len(data_frame[col]), MAX_ROWS_TO_CHECK)
    s = pd.to_datetime(data_frame[col][1:rows_to_check], errors='coerce')
    missing = sum(1 for i in range(len(s)) if s.iloc[i] is pd.NaT)
    # see how many missing values... arbitrary cutoff allowing for missing values
    if len(s) > 0:
        return float(missing) / float(len(s)) < 0.2
    else:
        return False


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


def infer_col_type(data_frame, data_frame_raw, col):
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
        col_type = metapype_client.VariableType.CATEGORICAL
        sorted_codes = sort_codes(codes)
    else:
        if dtype == object:
            if is_datetime(data_frame, col):
                return metapype_client.VariableType.DATETIME, infer_datetime_format(data_frame[col][1])
            else:
                col_type = metapype_client.VariableType.TEXT
        else:
            col_type = metapype_client.VariableType.NUMERICAL

    # does it look like a date?
    lc_col = col.lower()
    if (
            ('year' in lc_col or 'date' in lc_col)
            and col_type == metapype_client.VariableType.CATEGORICAL
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
            return metapype_client.VariableType.DATETIME, 'YYYY'

    return col_type, sorted_codes


def get_raw_csv_column_values(filepath, delimiter, quotechar, colname):
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


def guess_missing_value_code(filepath, delimiter, quotechar, colname):
    col_values = get_raw_csv_column_values(filepath, delimiter, quotechar, colname)
    mvcode = None
    candidate_codes = [
        ['NA', 'na', 'N/A', 'n/a', 'NAN', 'NaN', 'nan', '#N/A'],  # These take precedence
        ['Inf', 'inf', '-Inf', '-inf', 'NULL', 'Null', 'null', 'None', 'none', '-', '.']
    ]
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
    df = pd.read_csv(csv_filepath, encoding='utf8', usecols=[0], sep=delimiter, quotechar=quote_char)
    return df.shape[0]


def load_data_table(uploads_path: str = None, data_file: str = '',
                    num_header_rows: str = '1', delimiter: str = ',', quote_char: str = '"', check_column_names: bool = False):
    if Config.LOG_DEBUG:
        log_info(f'Entering load_data_table: {data_file}')

    full_path = f'{uploads_path}/{data_file}'

    datatable_node = metapype_client.new_child_node(names.DATATABLE, parent=None)

    physical_node = metapype_client.new_child_node(names.PHYSICAL, parent=datatable_node)
    physical_node.add_attribute('system', 'EDI')

    entity_name_node = metapype_client.new_child_node(names.ENTITYNAME, parent=datatable_node)
    entity_name = entity_name_from_data_file(data_file)
    entity_name_node.content = entity_name

    object_name_node = metapype_client.new_child_node(names.OBJECTNAME, parent=physical_node)
    object_name_node.content = data_file

    file_size = get_file_size(full_path)
    if file_size is not None:
        size_node = metapype_client.new_child_node(names.SIZE, physical_node)
        size_node.add_attribute('unit', 'byte')
        size_node.content = str(file_size)

    md5_hash = get_md5_hash(full_path)
    if md5_hash is not None:
        hash_node = Node(names.AUTHENTICATION, parent=physical_node)
        metapype_client.add_child(physical_node, hash_node)
        hash_node.add_attribute('method', 'MD5')
        hash_node.content = str(md5_hash)

    data_format_node = Node(names.DATAFORMAT, parent=physical_node)
    metapype_client.add_child(physical_node, data_format_node)

    text_format_node = Node(names.TEXTFORMAT, parent=data_format_node)
    metapype_client.add_child(data_format_node, text_format_node)

    num_header_lines_node = Node(names.NUMHEADERLINES, parent=text_format_node)
    metapype_client.add_child(text_format_node, num_header_lines_node)
    num_header_lines_node.content = num_header_rows

    num_footer_lines_node = Node(names.NUMFOOTERLINES, parent=text_format_node)
    metapype_client.add_child(text_format_node, num_footer_lines_node)
    num_footer_lines_node.content = '0'

    simple_delimited_node = Node(names.SIMPLEDELIMITED, parent=text_format_node)
    metapype_client.add_child(text_format_node, simple_delimited_node)

    field_delimiter_node = Node(names.FIELDDELIMITER, parent=simple_delimited_node)
    metapype_client.add_child(simple_delimited_node, field_delimiter_node)
    field_delimiter_node.content = delimiter

    quote_character_node = Node(names.QUOTECHARACTER, parent=simple_delimited_node)
    metapype_client.add_child(simple_delimited_node, quote_character_node)
    quote_character_node.content = quote_char

    if file_size == 0:
        raise DataTableError("The CSV file is empty.")

    check_column_name_uniqueness(full_path, delimiter)

    with open(full_path) as file:
        next(file)
        # TODO TEMP
        # If the file has mixed line terminators, we get a tuple of line terminators, but PASTA doesn't
        #  support that. So we just use the first one.
        newlines = file.newlines
        if newlines is not None and isinstance(newlines, tuple):
            newlines = newlines[0]
        line_terminator = repr(newlines).replace("'", "")
    record_delimiter_node = Node(names.RECORDDELIMITER, parent=text_format_node)
    metapype_client.add_child(text_format_node, record_delimiter_node)
    record_delimiter_node.content = line_terminator

    # log_info('pd.read_csv')
    try:
        num_rows = get_num_rows(full_path, delimiter=delimiter, quote_char=quote_char)
        # If the number of rows is greater than a million, we will base the metadata on what we see in the
        #  first million rows.
        if num_rows > 10**6:
            flash(f'The number of rows in {os.path.basename(full_path)} is greater than 1 million. ezEML uses the '
                  f'first million rows to determine the data types of the columns and the codes for categorical '
                  f'columns. If the first million rows are not representative of the entire file, you may need to '
                  f'manually correct the data type and categorical codes.')
        data_frame = pd.read_csv(full_path, encoding='utf8', sep=delimiter, quotechar=quote_char, nrows=min(num_rows, 10**6))
        # Load the CSV file without conversions. Used when getting the categorical codes and missing value codes.
        data_frame_raw = pd.read_csv(full_path, encoding='utf8', sep=delimiter, quotechar=quote_char, keep_default_na=False, na_values=[], dtype=str)
    except pd.errors.ParserError as e:
        raise DataTableError(e.args[0])

    column_vartypes = []
    column_names = []
    column_categorical_codes = []

    if data_frame is not None:

        number_of_records = Node(names.NUMBEROFRECORDS, parent=datatable_node)
        metapype_client.add_child(datatable_node, number_of_records)
        number_of_records.content = f'{num_rows}'

        attribute_list_node = Node(names.ATTRIBUTELIST, parent=datatable_node)
        metapype_client.add_child(datatable_node, attribute_list_node)

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
            column_categorical_codes.append(codes)

            attribute_node = metapype_client.new_child_node(names.ATTRIBUTE, attribute_list_node)
            attribute_name_node = metapype_client.new_child_node(names.ATTRIBUTENAME, attribute_node)
            attribute_name_node.content = col

            att_label_node = Node(names.ATTRIBUTELABEL, parent=attribute_node)
            metapype_client.add_child(attribute_node, att_label_node)
            att_label_node.content = col

            att_def_node = Node(names.ATTRIBUTEDEFINITION, parent=attribute_node)
            metapype_client.add_child(attribute_node, att_def_node)

            ms_node = Node(names.MEASUREMENTSCALE, parent=attribute_node)
            metapype_client.add_child(attribute_node, ms_node)

            missing_value_code = guess_missing_value_code(full_path, delimiter, quote_char, col)

            if missing_value_code:
                mv_node = Node(names.MISSINGVALUECODE, parent=attribute_node)
                metapype_client.add_child(attribute_node, mv_node)
                code_node = Node(names.CODE, parent=mv_node)
                metapype_client.add_child(mv_node, code_node)
                code_node.content = missing_value_code

            if var_type == metapype_client.VariableType.CATEGORICAL:
                codes = force_categorical_codes(attribute_node, dtype, codes)
                codes = force_missing_value_code(missing_value_code, dtype, codes)

                # nominal / nonNumericDomain / enumeratedDomain / ...codes...
                nominal_node = metapype_client.new_child_node(names.NOMINAL, ms_node)
                non_numeric_domain_node = metapype_client.new_child_node(names.NONNUMERICDOMAIN, nominal_node)
                enumerated_domain_node = metapype_client.new_child_node(names.ENUMERATEDDOMAIN, non_numeric_domain_node)

                for code in codes:
                    code_definition_node = metapype_client.new_child_node(names.CODEDEFINITION, enumerated_domain_node)
                    code_node = metapype_client.new_child_node(names.CODE, code_definition_node)
                    code_node.content = str(code)
                    definition_node = metapype_client.new_child_node(names.DEFINITION, code_definition_node)

            elif var_type == metapype_client.VariableType.NUMERICAL:
                # ratio / numericDomain
                ratio_node = metapype_client.new_child_node(names.RATIO, ms_node)
                numeric_domain_node = metapype_client.new_child_node(names.NUMERICDOMAIN, ratio_node)
                number_type = 'real'
                if str(dtype).startswith('int'):  # FIXME - we can do better than this
                    number_type = 'integer'
                number_type_node = metapype_client.new_child_node(names.NUMBERTYPE, numeric_domain_node)
                number_type_node.content = number_type
                numeric_domain_node = metapype_client.new_child_node(names.UNIT, ratio_node)

            elif var_type == metapype_client.VariableType.TEXT:
                # nominal / nonNumericDomain / textDomain
                nominal_node = metapype_client.new_child_node(names.NOMINAL, ms_node)
                non_numeric_domain_node = metapype_client.new_child_node(names.NONNUMERICDOMAIN, nominal_node)
                text_domain_node = metapype_client.new_child_node(names.TEXTDOMAIN, non_numeric_domain_node)
                definition_node = metapype_client.new_child_node(names.DEFINITION, text_domain_node)

            elif var_type == metapype_client.VariableType.DATETIME:
                # dateTime / formatString
                datetime_node = Node(names.DATETIME, parent=ms_node)
                metapype_client.add_child(ms_node, datetime_node)

                format_string_node = Node(names.FORMATSTRING, parent=datetime_node)
                metapype_client.add_child(datetime_node, format_string_node)
                format_string_node.content = codes

    if Config.LOG_DEBUG:
        log_info(f'Leaving load_data_table')

    return datatable_node, column_vartypes, column_names, column_categorical_codes, data_frame, missing_value_code


def load_other_entity(dataset_node: Node = None, uploads_path: str = None, data_file: str = '', node_id: str = None):
    full_path = f'{uploads_path}/{data_file}'

    doing_reupload = node_id is not None and node_id != '1'

    if doing_reupload:
        other_entity_node = Node.get_node_instance(node_id)
        object_name_node = other_entity_node.find_descendant(names.OBJECTNAME)
    else:
        other_entity_node = Node(names.OTHERENTITY, parent=dataset_node)
        metapype_client.add_child(dataset_node, other_entity_node)

        physical_node = Node(names.PHYSICAL, parent=other_entity_node)
        metapype_client.add_child(other_entity_node, physical_node)
        physical_node.add_attribute('system', 'EDI')

        entity_name_node = Node(names.ENTITYNAME, parent=other_entity_node)
        metapype_client.add_child(other_entity_node, entity_name_node)

        entity_name = entity_name_from_data_file(data_file)
        entity_name_node.content = entity_name

        object_name_node = Node(names.OBJECTNAME, parent=physical_node)
        metapype_client.add_child(physical_node, object_name_node)

    object_name_node.content = data_file

    physical_node = other_entity_node.find_descendant(names.PHYSICAL)

    file_size = get_file_size(full_path)
    if file_size is not None:
        size_node = other_entity_node.find_descendant(names.SIZE)
        if size_node is None:
            size_node = Node(names.SIZE, parent=physical_node)
            metapype_client.add_child(physical_node, size_node)
        size_node.add_attribute('unit', 'byte')
        size_node.content = str(file_size)

    md5_hash = get_md5_hash(full_path)
    if md5_hash is not None:
        hash_node = physical_node.find_descendant(names.AUTHENTICATION)
        if hash_node is None:
            hash_node = Node(names.AUTHENTICATION, parent=physical_node)
            metapype_client.add_child(physical_node, hash_node)
        hash_node.add_attribute('method', 'MD5')
        hash_node.content = str(md5_hash)

    data_format_node = physical_node.find_descendant(names.DATAFORMAT)
    if data_format_node is None:
        data_format_node = Node(names.DATAFORMAT, parent=physical_node)
        metapype_client.add_child(physical_node, data_format_node)

    # If the package was created in ezEML, the dataFormat will be externallyDefinedFormat.
    # We force that to be the case here, so that's what ezEML knows how to handle.
    data_format_node.children = []

    externally_defined_format_node = Node(names.EXTERNALLYDEFINEDFORMAT, parent=data_format_node)
    metapype_client.add_child(data_format_node, externally_defined_format_node)

    format_name_node = Node(names.FORMATNAME, parent=externally_defined_format_node)
    metapype_client.add_child(externally_defined_format_node, format_name_node)
    format_name_node.content = format_name_from_data_file(data_file)

    if not doing_reupload:
        entity_type_node = metapype_client.new_child_node(names.ENTITYTYPE, parent=other_entity_node)
    else:
        entity_type_node = other_entity_node.find_descendant(names.ENTITYTYPE)
    entity_type_node.content = format_name_from_data_file(data_file)

    user_data.add_data_table_upload_filename(data_file)

    delete_data_files(uploads_path)

    return other_entity_node


def delete_data_files(data_folder: str = None):
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
