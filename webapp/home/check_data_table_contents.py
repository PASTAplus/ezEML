import os

from collections import OrderedDict
import csv
from flask import session, flash
import glob
import hashlib
import json
import pandas as pd
import re
import requests
from requests_file import FileAdapter
from typing import List

import webapp.auth.user_data as user_data
from webapp.config import Config
from webapp.home.import_data import convert_file_size

from metapype.eml import names
from webapp.exceptions import ezEMLXMLError
from metapype.model import metapype_io
from metapype.model.node import Node
import webapp.home.metapype_client as metapype_client


data_time_format_strings = None
date_time_format_regex = None
DATE_TIME_FORMAT_STRINGS_FILENAME = 'webapp/static/dateTimeFormatString_list.csv'
DATE_TIME_FORMAT_REGEX_FILENAME = 'webapp/static/dateTimeFormatString_regex.csv'

from flask_login import (
    current_user
)
import daiquiri
logger = daiquiri.getLogger('check_data_table_contents: ' + __name__)


def log_info(msg):
    if current_user and hasattr(current_user, 'get_username'):
        logger.info(msg, USER=current_user.get_username())
    else:
        logger.info(msg)


def load_eml_file(eml_file_url:str):

    s = requests.Session()
    s.mount('file://', FileAdapter())

    # Get the eml file
    try:
        response = s.get(eml_file_url)
        response.raise_for_status()
    except Exception as err:
        raise ezEMLXMLError(f'Error loading EML file: {err.response.content}')
    xml = response.content.decode('utf-8')
    eml_node = metapype_io.from_xml(xml,
                                    clean=True,
                                    collapse=True,
                                    literals=['literalLayout', 'markdown', 'attributeName', 'code'])
    assert isinstance(eml_node, Node)
    return eml_node


def load_df(eml_node, csv_url, data_table_name):
    data_table_node = find_data_table_node(eml_node, data_table_name)

    field_delimiter_node = data_table_node.find_descendant(names.FIELDDELIMITER)
    if field_delimiter_node:
        delimiter = field_delimiter_node.content
    else:
        delimiter = ','
    quote_char_node = data_table_node.find_descendant(names.QUOTECHARACTER)
    if quote_char_node:
        quote_char = quote_char_node.content
    else:
        quote_char = '"'

    num_header_lines_node = data_table_node.find_descendant(names.NUMHEADERLINES)
    num_header_lines = 1
    try:
        num_header_lines = int(num_header_lines_node.content)
    except:
        pass

    num_footer_lines_node = data_table_node.find_descendant(names.NUMFOOTERLINES)
    num_footer_lines = 0
    try:
        num_footer_lines = int(num_footer_lines_node.content)
    except:
        pass

    return pd.read_csv(csv_url, encoding='utf-8-sig', sep=delimiter, quotechar=quote_char,
                       keep_default_na=False, skiprows=range(1, num_header_lines), skipfooter=num_footer_lines)


def find_data_table_node(eml_node, data_table_name):
    # FIX ME - what if dataset has multiple tables with the same name?
    data_table_nodes = []
    eml_node.find_all_descendants(names.DATATABLE, data_table_nodes)
    for data_table_node in data_table_nodes:
        if get_data_table_name(data_table_node) == data_table_name:
            return data_table_node
    raise ValueError(f'Data table "{data_table_name}" not found in EML')


def get_attribute_name(attribute_node):
    attribute_name_node = attribute_node.find_child(names.ATTRIBUTENAME)
    if attribute_name_node:
        return attribute_name_node.content
    raise ValueError(f'Column not found in EML')


def normalize_column_name(name):
    # Strip whitespace and convert to lowercase
    return name.strip().lower()


def names_match(column_name, attribute_name):
    return normalize_column_name(column_name) == normalize_column_name(attribute_name)


def get_attribute_node(data_table_node, attribute_name):
    attribute_nodes = []
    data_table_node.find_all_descendants(names.ATTRIBUTE, attribute_nodes)
    for attribute_node in attribute_nodes:
        attribute_name_node = attribute_node.find_child(names.ATTRIBUTENAME)
        if attribute_name_node and names_match(attribute_name_node.content, attribute_name):
            return attribute_node
    raise ValueError  # use custom exception
    raise ValueError(f'Column "{attribute_name}" not found in EML')


def get_variable_type(attribute_node):
    measurement_scale_node = attribute_node.find_child(names.MEASUREMENTSCALE)
    if measurement_scale_node:

        nominal_or_ordinal_node = measurement_scale_node.find_child(names.NOMINAL)
        if not nominal_or_ordinal_node:
            nominal_or_ordinal_node = measurement_scale_node.find_child(names.ORDINAL)
        if nominal_or_ordinal_node:
            if nominal_or_ordinal_node.find_single_node_by_path([names.NONNUMERICDOMAIN, names.ENUMERATEDDOMAIN]):
                return metapype_client.VariableType.CATEGORICAL.name
            if nominal_or_ordinal_node.find_single_node_by_path([names.NONNUMERICDOMAIN, names.TEXTDOMAIN]):
                return metapype_client.VariableType.TEXT.name

        ratio_or_interval_node = measurement_scale_node.find_child(names.RATIO)
        if not ratio_or_interval_node:
            ratio_or_interval_node = measurement_scale_node.find_child(names.INTERVAL)
        if ratio_or_interval_node:
            return metapype_client.VariableType.NUMERICAL.name

        datetime_node = measurement_scale_node.find_child(names.DATETIME)
        if datetime_node:
            return metapype_client.VariableType.DATETIME.name
    raise ValueError  # use custom exception


def get_data_table_columns(data_table_node):
    columns = []
    attribute_nodes = []
    data_table_node.find_all_descendants(names.ATTRIBUTE, attribute_nodes)
    for attribute_node in attribute_nodes:
        attribute_name = get_attribute_name(attribute_node)
        variable_type = get_variable_type(attribute_node)
        columns.append({ 'name': attribute_name, 'type': variable_type })
    return columns


def create_result_json(eml_url, csv_url, columns_checked, errors, max_errs_per_column):
    if not max_errs_per_column:
        max_errs_per_column = '""'
    result_1 = f'"eml_file_url": "{eml_url}", "csv_file_url": "{csv_url}", "columns_checked": {json.dumps(columns_checked)}, "max_errs_per_column": {max_errs_per_column}, '
    errors = ','.join(errors)
    result_2 = f'"errors": [{errors}]'
    return f"{{ {result_1}{result_2} }}"


def create_error_json(data_table_name, column_name, row_index, error_type, expected, found):
    if data_table_name and column_name and row_index:
        error_scope = 'element'
    elif data_table_name and column_name:
        error_scope = 'column'
    elif data_table_name and row_index:
        error_scope = 'row'
    elif data_table_name:
        error_scope = 'table'
    else:
        raise ValueError  # use custom exception

    if not column_name:
        column_name = ''
    if not row_index:
        row_index = ''
    location = f'{{ "table": "{data_table_name}", "column": "{column_name}", "row": "{row_index}" }}'
    return f'{{ "error_scope": "{error_scope}", "location": {location}, "error_type": "{error_type}", "expected": {json.dumps(expected)}, "found": {json.dumps(found)}}}'


def get_date_time_format_specification(data_table_node, attribute_name):
    attribute_node = get_attribute_node(data_table_node, attribute_name)
    if attribute_node:
        format_string_node = attribute_node.find_single_node_by_path(
            [names.MEASUREMENTSCALE, names.DATETIME, names.FORMATSTRING])
        if format_string_node:
            return format_string_node.content
    raise ValueError  # use custom exception


def get_date_time_format_regex(data_table_node, attribute_name):
    date_time_format = get_date_time_format_specification(data_table_node, attribute_name)
    return get_regex_for_format(date_time_format)


def get_regex_for_format(format):
    load_date_time_format_files()
    return date_time_format_regex.get(format, None)


def get_missing_value_codes(data_table_node, column_name):
    attribute_node = get_attribute_node(data_table_node, column_name)
    missing_value_codes = []
    if attribute_node:
        missing_value_code_nodes = attribute_node.find_all_nodes_by_path([names.MISSINGVALUECODE, names.CODE])
        for missing_value_code_node in missing_value_code_nodes:
            if missing_value_code_node.content:
                missing_value_codes.append(re.escape(missing_value_code_node.content))
    return missing_value_codes


def get_categorical_codes(attribute_node):
    codes = []
    code_nodes = []
    attribute_node.find_all_descendants(names.CODE, code_nodes)
    for code_node in code_nodes:
        if code_node.content:
            codes.append(code_node.content)
    return codes


def get_number_type(attribute_node):
    number_type_node = attribute_node.find_descendant(names.NUMBERTYPE)
    if not number_type_node:
        attribute_name = get_attribute_name(attribute_node)
        raise ValueError(f'Column {attribute_name} is missing a numberType element')
    number_type = number_type_node.content
    if number_type not in ('natural', 'whole', 'integer', 'real'):
        attribute_name = get_attribute_name(attribute_node)
        raise ValueError(f'Column {attribute_name} has unexpected numberType: {number_type}')
    return number_type


def display_nonprintable(s):
    if s.isprintable():
        return s
    return ''.join([c if c.isprintable() else "�" for c in s])


def match_with_regex(col_values, regex, empty_is_ok=True):
    if empty_is_ok:
        regex = f'^({regex})?$'
    matches = col_values.str.contains(regex)
    return matches


def check_columns_existence_against_metadata(data_table_node, df):
    errors = []
    # Get the column names from the metadata
    attribute_name_nodes = []
    metadata_column_names = []
    data_table_node.find_all_descendants(names.ATTRIBUTENAME, attribute_name_nodes)
    for attribute_name_node in attribute_name_nodes:
        metadata_column_names.append(attribute_name_node.content)
    data_table_column_names = list(df.columns)
    if len(metadata_column_names) != len(data_table_column_names):
        errors.append(create_error_json(get_data_table_name(data_table_node), None, None,
                                        'Metadata defines a different number of columns than the data table',
                                        len(metadata_column_names), len(data_table_column_names)))
    else:
        maxlen = max(len(metadata_column_names), len(data_table_column_names))
        for i in range(maxlen):
            if not names_match(metadata_column_names[i], data_table_column_names[i]):
                error = create_error_json(get_data_table_name(data_table_node), data_table_column_names[i], None,
                                          'Metadata column name does not match column name in data table',
                                          display_nonprintable(metadata_column_names[i]),
                                          display_nonprintable(data_table_column_names[i]))
                errors.append(error)
    return errors, data_table_column_names, metadata_column_names


def get_num_header_lines(data_table_node):
    num_header_lines_node = data_table_node.find_descendant(names.NUMHEADERLINES)
    try:
        return int(num_header_lines_node.content)
    except:
        return 1


def check_numerical_column(df, data_table_node, column_name, max_errs_per_column):
    # from datetime import datetime
    # start = datetime.now()

    attribute_node = get_attribute_node(data_table_node, column_name)
    number_type = get_number_type(attribute_node)
    col_values = df[column_name].astype(str)

    if number_type == 'integer':
        regex = '^[-+]?[0-9]+$'
    elif number_type == 'whole' or number_type == 'natural':
        regex = '^[0-9]+$'
    else:
        regex = '^[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?$'
    # Allow empty string
    regex = '^$|' + regex
    try:
        matches = match_with_regex(col_values, regex)
    except KeyError:
        return [create_error_json(get_data_table_name(data_table_node), column_name, None,
                                 'Column not found in data table', column_name, 'Not found')]
    mvc = get_missing_value_codes(data_table_node, column_name)
    if len(mvc) > 0:
        mvc_regex = '^' + '|'.join(mvc) + '$'
        mvc_matches = col_values.str.contains(mvc_regex)
        # Errors are rows with matches == False and mvc_matches == False
        result = ~(matches | mvc_matches)
    else:
        result = ~matches
    error_indices = result[result].index.values

    data_table_name = get_data_table_name(data_table_node)
    expected = number_type
    if number_type == 'real':
        expected = 'A real number (e.g., 123.4)'
    elif number_type == 'integer':
        expected = 'An integer (e.g. -3, 0, 42)'
    elif number_type == 'whole':
        expected = 'A whole number (e.g. 0, 1, 2)'
    elif number_type == 'natural':
        expected = 'A natural number (e.g. 0, 1, 2)'
    errors = []
    num_header_lines = get_num_header_lines(data_table_node)
    for index in error_indices:
        # Make the index 1-based and taking into account the number of header rows. I.e., make it match what they'd see in Excel.
        errors.append(create_error_json(data_table_name, column_name,
                                        index + num_header_lines + 1,
                                        'Numerical element not of the expected type',
                                        expected, col_values[index]))
        if max_errs_per_column and len(errors) > max_errs_per_column:
            break

    # end = datetime.now()
    # elapsed = (end - start).total_seconds()
    # print(column_name, elapsed, len(errors))

    return errors


def check_categorical_column(df, data_table_node, column_name, max_errs_per_column):
    # from datetime import datetime
    # start = datetime.now()

    errors = []
    attribute_node = get_attribute_node(data_table_node, column_name)
    col_values = df[column_name].astype(str)

    # If the metadata says codes values are not "enforced" to be the defined codes, then there cannot be errors
    enumerated_domain_node = attribute_node.find_descendant(names.ENUMERATEDDOMAIN)
    if enumerated_domain_node and enumerated_domain_node.attribute_value('enforced') == 'no':
        return []

    codes = list(map(re.escape, get_categorical_codes(attribute_node)))
    codes_regex = '^' + '|'.join(codes) + '$'
    # Allow empty string
    codes_regex = '^$|' + codes_regex
    try:
        matches = match_with_regex(col_values, codes_regex)
    except KeyError:
        return errors   # This indicates the column is missing, but that type of error is reported via
                        # check_columns_existence_against_metadata()
    mvc = get_missing_value_codes(data_table_node, column_name)
    if len(mvc) > 0:
        mvc_regex = '^' + '|'.join(mvc) + '$'
        mvc_matches = col_values.str.contains(mvc_regex)
        # Errors are rows with matches == False and mvc_matches == False
        result = ~(matches | mvc_matches)
    else:
        result = ~matches
    error_indices = result[result].index.values
    data_table_name = get_data_table_name(data_table_node)
    expected = 'A defined code'
    num_header_lines = get_num_header_lines(data_table_node)
    for index in error_indices:
        # Make the index 1-based and taking into account the number of header rows. I.e., make it match what they'd see in Excel.
        errors.append(create_error_json(data_table_name, column_name,
                                        index + num_header_lines + 1,
                                        'Categorical element is not a defined code',
                                        expected, col_values[index]))
        if max_errs_per_column and len(errors) > max_errs_per_column:
            break

    # end = datetime.now()
    # elapsed = (end - start).total_seconds()
    # print(column_name, elapsed, len(errors))

    return errors


def check_date_time_column(df, data_table_node, column_name, max_errs_per_column):
    # from datetime import datetime
    # start = datetime.now()

    col_values = df[column_name].astype(str)
    regex = get_date_time_format_regex(data_table_node, column_name)
    if not regex:
        date_time_format = get_date_time_format_specification(data_table_node, column_name)
        return [create_error_json(get_data_table_name(data_table_node), column_name, None,
                                 'The specified DateTime Format String is not supported.',
                                  'A <a href="../datetime_formats">supported</a> format',
                                  date_time_format)]
    try:
        matches = match_with_regex(col_values, regex)
    except KeyError:
        return [create_error_json(get_data_table_name(data_table_node), column_name, None,
                                 'Column not found in table', (column_name), 'Not found')]
    mvc = get_missing_value_codes(data_table_node, column_name)
    if len(mvc) > 0:
        mvc_regex = '^' + '|'.join(mvc) + '$'
        mvc_matches = col_values.str.contains(mvc_regex)
        # Errors are rows with matches == False and mvc_matches == False
        result = ~(matches | mvc_matches)
    else:
        result = ~matches
    error_indices = result[result].index.values
    data_table_name = get_data_table_name(data_table_node)
    expected = get_date_time_format_specification(data_table_node, column_name)
    errors = []
    num_header_lines = get_num_header_lines(data_table_node)
    for index in error_indices:
        # Make the index 1-based and taking into account the number of header rows. I.e., make it match what they'd see in Excel.
        errors.append(create_error_json(data_table_name, column_name,
                                        index + num_header_lines + 1,
                                        'DateTime element does not have expected format',
                                        expected, col_values[index]))
        if max_errs_per_column and len(errors) > max_errs_per_column:
            break

    # end = datetime.now()
    # elapsed = (end - start).total_seconds()
    # print(column_name, elapsed, len(errors))

    return errors


def check_data_table(eml_file_url:str=None,
                     csv_file_url:str=None,
                     data_table_name:str=None,
                     column_names:List[str]=None,
                     max_errs_per_column=100,
                     collapse_errs:bool=False):
    eml_node = load_eml_file(eml_file_url)
    df = load_df(eml_node, csv_file_url, data_table_name)

    data_table_node = find_data_table_node(eml_node, data_table_name)
    errors, data_table_column_names, metadata_column_names = check_columns_existence_against_metadata(data_table_node, df)

    if not column_names:
        # check them all... we will use the data table column names. they may not exactly match the metadata column
        # names, for example if there are spaces at the end of column names.
        column_names = data_table_column_names
    columns_checked = []
    for column_name in column_names:
        if column_name not in data_table_column_names:
            continue
        try:
            attribute_node = get_attribute_node(data_table_node, column_name)
        except ValueError:
            # If the column is not found in the metadata, then it is a column name mismatch error that will have been
            #  reported above by check_columns_existence_against_metadata().
            continue
        variable_type = get_variable_type(attribute_node)
        if variable_type == 'CATEGORICAL':
            columns_checked.append(column_name)
            errors.extend(check_categorical_column(df, data_table_node, column_name, max_errs_per_column))
        elif variable_type == 'DATETIME':
            columns_checked.append(column_name)
            errors.extend(check_date_time_column(df, data_table_node, column_name, max_errs_per_column))
        elif variable_type == 'NUMERICAL':
            columns_checked.append(column_name)
            errors.extend(check_numerical_column(df, data_table_node, column_name, max_errs_per_column))

    return create_result_json(eml_file_url, csv_file_url, columns_checked, errors, max_errs_per_column)


def load_date_time_format_files(strings_filename=DATE_TIME_FORMAT_STRINGS_FILENAME,
                                regex_filename=DATE_TIME_FORMAT_REGEX_FILENAME):
    global data_time_format_strings, date_time_format_regex
    if not data_time_format_strings:
        data_time_format_strings = OrderedDict()
        with open(strings_filename, 'r', encoding='utf-8-sig') as csv_file:
            csv_reader = csv.DictReader(csv_file)
            for line in csv_reader:
                format = line['Format']
                example = line['Example']
                data_time_format_strings[format] = example
    if not date_time_format_regex:
        date_time_format_regex = OrderedDict()
        with open(regex_filename, 'r', encoding='utf-8-sig') as csv_file:
            csv_reader = csv.DictReader(csv_file)
            for line in csv_reader:
                format = line['Format']
                regex = line['Regex']
                date_time_format_regex[format] = regex


def get_regex_for_format(format):
    load_date_time_format_files()
    return date_time_format_regex.get(format, None)


def load_xml(filename):
    with open(f"{filename}", "r") as f:
        xml = "".join(f.readlines())
    eml_node = metapype_io.from_xml(xml)
    assert isinstance(eml_node, Node)
    return eml_node


def get_data_table_name(data_table_node):
    data_table_name_node = data_table_node.find_child(names.ENTITYNAME)
    if data_table_name_node:
        return data_table_name_node.content.strip()


def get_data_table_filename(data_table_node):
    data_table_object_name_node = data_table_node.find_descendant(names.OBJECTNAME)
    if data_table_object_name_node:
        return data_table_object_name_node.content


def get_data_table_size(data_table_node):
    data_table_size_node = data_table_node.find_descendant(names.SIZE)
    if data_table_size_node:
        return data_table_size_node.content


def check_date_time_format_specification(specification):
    load_date_time_format_files()
    return specification in data_time_format_strings.keys()


def check_date_time_attribute(attribute_node):
    format_string_node = attribute_node.find_single_node_by_path(
        [names.MEASUREMENTSCALE, names.DATETIME, names.FORMATSTRING])
    if format_string_node:
        format_string = format_string_node.content
        if not check_date_time_format_specification(format_string):
            return format_string


def format_date_time_formats_list():
    load_date_time_format_files()

    output = '<span style="font-family: Helvetica,Arial,sans-serif;">'
    output += '<table class="eval_table" width=100% style="padding: 10px;">'
    output += '<tr><th style="font-size:120%;">Format</th><th style="font-size:120%;">Example</th></tr>'

    for format, example in data_time_format_strings.items():
        output += f'<tr>'
        output += f'<td class="eval_table" valign="top">{format}</td>'
        output += f'<td class="eval_table" valign="top">{example}</td>'
        output += '</tr>'

    output += '</table>'
    output += '</span>'
    return output


EML_FILES_PATH = '/Users/jide/git/umbra/eml_files'
def get_existing_eml_files():
    import glob
    import os
    filelist = glob.glob(f'{EML_FILES_PATH}/*.xml')
    return sorted([os.path.basename(x) for x in filelist])


def clear_eval_files():
    # For use while developing and debugging
    uploads_folder = f'/Users/jide/git/ezEML/user-data/EDI-1a438b985e1824a5aa709daa1b6e12d2/uploads'
    subdirs = []
    for file in os.listdir(uploads_folder):
        filepath = os.path.join(uploads_folder, file)
        if os.path.isdir(filepath):
            subdirs.append(filepath)
    for subdir in subdirs:
        filelist = glob.glob(f'{subdir}/*_eval_*')
        for filepath in filelist:
            os.remove(filepath)
    for subdir in subdirs:
        filelist = glob.glob(f'{subdir}/*_eval')
        for filepath in filelist:
            os.remove(filepath)


def find_large_data_tables():
    import os
    filenames = get_existing_eml_files()
    print(f'{len(filenames)} files in total')
    i = 0
    maxsize = 0
    maxcols = 0
    for filename in filenames:
        try:
            scope, identifier, revision, *_ = filename.split('.')
        except:
            continue
        # For now, just the edi scope
        if scope != 'edi':
            continue
        eml_node = load_xml(os.path.join(EML_FILES_PATH, filename))
        data_table_nodes = eml_node.find_all_nodes_by_path(
            [names.DATASET, names.DATATABLE])
        for data_table_node in data_table_nodes:
            data_table_name = get_data_table_name(data_table_node)
            size_node = data_table_node.find_descendant(names.SIZE)
            size = size_node.content
            attribute_nodes = []
            data_table_node.find_all_descendants(names.ATTRIBUTE, attribute_nodes)
            columns = len(attribute_nodes)
            do_print = False
            if size and (int(size) > maxsize or int(size) > 100 * 1024 * 1024):
                if int(size) > maxsize:
                    maxsize = int(size)
                do_print = True
            if columns and columns > maxcols:
                maxcols = columns
                do_print = True
            if do_print:
                print(filename)
                print(data_table_name, size, columns)
            i += 1
            if i > 100:
                break


def make_blanks_visible(s:str):
    blank = '<span style="color:red;font-size:100%;font-weight:bold;">\u274f</span>'
    # Also considered \u2420 and \u25a1
    if s.isspace():
        s = s.replace(' ', blank)
    else:
        # make leading and trailing spaces visible
        leading = len(s) - len(s.lstrip())
        trailing = len(s) - len(s.rstrip())
        s = s[:leading].replace(' ', blank) + s[leading:len(s)-trailing] + s[len(s)-trailing:].replace(' ', blank)
    has_blank = blank in s
    return s, has_blank


def generate_error_info_for_webpage(data_table_node, errors):
    errs_obj = json.loads(errors)
    data_table_name = get_data_table_name(data_table_node)
    column_name = None
    column_errs = []
    errors = []
    has_blanks = False
    for error in errs_obj['errors']:
        if error['location']['table'] != data_table_name:
            continue
        if error['location']['column'] != column_name:
            column_name = error['location']['column']
            try:
                attribute_node = get_attribute_node(data_table_node, column_name)
                variable_type = get_variable_type(attribute_node)
            except ValueError:
                variable_type = 'UNKNOWN'
            errors = []
            column_errs.append({ "column_name": column_name, "variable_type": variable_type, "errors": errors})
        expected, blank = make_blanks_visible(error['expected'])
        has_blanks = has_blanks or blank
        found, blank = make_blanks_visible(error['found'])
        has_blanks = has_blanks or blank
        errors.append({
            "row": error['location']['row'],
            "error_type": error['error_type'],
            "expected": expected,
            "found": found})
    return column_errs, has_blanks


def get_eml_file_url(document_name, eml_node):
    filepath = f'{os.path.join(Config.BASE_DIR, user_data.get_user_folder_name(), document_name)}.xml'
    if os.path.exists(filepath):
        return f'file://{filepath}'
    package_id = eml_node.attribute_value('packageId')
    if package_id:
        filepath = f'{os.path.join(Config.BASE_DIR, user_data.get_user_folder_name(), package_id)}.xml'
        if os.path.exists(filepath):
            return f'file://{filepath}'
    return None


def get_csv_file_url(document_name, data_table_node):
    csv_file_name = get_data_table_filename(data_table_node)
    return f'file://{os.path.join(Config.BASE_DIR, user_data.get_document_uploads_folder_name(), csv_file_name)}'


def get_csv_filepath(document_name, csv_file_name):
    return os.path.join(user_data.get_document_uploads_folder_name(document_name), csv_file_name)


def get_csv_errors_archive_filepath(document_name, csv_file_name, metadata_hash):
    archive_filepath = f"{get_csv_filepath(document_name, csv_file_name)}_eval_{metadata_hash}"
    ok_filepath = f"{get_csv_filepath(document_name, csv_file_name)}_eval_{metadata_hash}_ok"
    wildcard_filepath = f"{get_csv_filepath(document_name, csv_file_name)}_eval_??????????"
    ok_wildcard_filepath = f"{get_csv_filepath(document_name, csv_file_name)}_eval_??????????_ok"
    return archive_filepath, ok_filepath, wildcard_filepath, ok_wildcard_filepath


def set_check_data_tables_badge_status(document_name, eml_node):
    status = 'green'
    data_table_nodes = []
    eml_node.find_all_descendants(names.DATATABLE, data_table_nodes)
    for data_table_node in data_table_nodes:
        csv_file_name = get_data_table_filename(data_table_node)
        data_table_name = get_data_table_name(data_table_node)
        metadata_hash = hash_data_table_metadata_settings(eml_node, data_table_name)
        this_status = get_data_file_eval_status(data_table_node, document_name, csv_file_name, metadata_hash)
        if this_status == 'red' or this_status == 'black':
            status = 'red'
            break
        if this_status == 'yellow':
            if status == 'green':
                status = 'yellow'
    session['check_data_tables_status'] = status
    return status


def get_data_file_eval_status(data_table_node, document_name, csv_file_name, metadata_hash):
    # csv_file_name = get_data_table_filename(data_table_node)
    if not csv_file_exists(document_name, csv_file_name):
        return 'black'
    # Returns green, yellow, red, or black.
    archive_filepath, ok_filepath, wildcard_filepath, ok_wildcard_filepath = get_csv_errors_archive_filepath(document_name, csv_file_name, metadata_hash)
    if os.path.exists(archive_filepath):
        return "red"
    if os.path.exists(ok_filepath):
        return "green"
    return "yellow"


def reset_data_file_eval_status(document_name, csv_file_name):
    archive_filepath, ok_filepath, wildcard_filepath, ok_wildcard_filepath = get_csv_errors_archive_filepath(document_name, csv_file_name, '')

    filelist = glob.glob(wildcard_filepath)
    for filepath in filelist:
        os.remove(filepath)

    filelist = glob.glob(ok_wildcard_filepath)
    for filepath in filelist:
        os.remove(filepath)


def save_data_file_eval(document_name, csv_file_name, metadata_hash, errors):
    reset_data_file_eval_status(document_name, csv_file_name)
    archive_filepath, ok_filepath, wildcard_filepath, ok_wildcard_filepath = get_csv_errors_archive_filepath(document_name, csv_file_name, metadata_hash)
    errs_obj = json.loads(errors)
    if not errs_obj['errors']:
        archive_filepath = ok_filepath
    with open(archive_filepath, 'w') as eval_file:
        eval_file.write(errors)


def get_data_file_eval(document_name, csv_file_name, metadata_hash):
    archive_filepath, ok_filepath, wildcard_filepath, ok_wildcard_filepath = get_csv_errors_archive_filepath(document_name, csv_file_name, metadata_hash)
    if not os.path.exists(archive_filepath):
        archive_filepath = ok_filepath
        if not os.path.exists(archive_filepath):
            # There may exist a version with a different hash. If so, it's obsolete and we want to delete it.
            matches = glob.glob(wildcard_filepath)
            for match in matches:
                os.remove(match)
            return None
    with open(archive_filepath, 'r') as eval_file:
        return eval_file.read()


def csv_file_exists(document_name, csv_file_name):
    csv_filepath = get_csv_filepath(document_name, csv_file_name)
    return os.path.exists(csv_filepath)


def create_check_data_tables_status_page_content(document_name, eml_node):
    data_table_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.DATATABLE])
    output = '<table class="eval_table" width=100% style="padding: 10px;"><tr><th></th><th>Data Table Name</th><th></th></tr>'
    for data_table_node in data_table_nodes:
        data_table_name = get_data_table_name(data_table_node)
        csv_file_name = get_data_table_filename(data_table_node)
        metadata_hash = hash_data_table_metadata_settings(eml_node, data_table_name)
        status = get_data_file_eval_status(data_table_node, document_name, csv_file_name, metadata_hash)
        if status == 'yellow':
            onclick = ''
            size = get_data_table_size(data_table_node)
            if size and int(size) > 10**8:
                kb, mb, gb = convert_file_size(size)
                mb = round(mb)
                onclick = f'onclick="return confirm(\'This data table may take up to several minutes to check. Continue?\');"'
            action = f'<a href="data_table_errors/{data_table_name}" {onclick}>Check data table</a>'
        elif status == 'red':
            action = f'<a href="data_table_errors/{data_table_name}">Show errors</a>'
        elif status == 'green':
            action = 'No errors found'
        else:  # black
            status = 'red'
            action = 'CSV file missing. Upload via the Data Tables page.'
        output += f'<tr><td width=2%><span class ="nav_link {status}_circle"></span></td>'
        output += f'<td width=63%>{data_table_name}</td>'
        output += f'<td width=35%>{action}</td></tr>'
    output += '</table>'
    return output


def collapse_error_info_for_webpage(errors):
    for column_errors in errors:
        collapse_error_info_for_column(column_errors)
    return errors


def error_as_dict(error_info):
    row, error_type, expected, found = error_info
    return {
        'row': str(row),
        'error_type': error_type,
        'expected': expected,
        'found': found
    }


def hash_data_table_metadata_settings(eml_node, data_table_name):
    # Various metadata settings affect the checking of data tables, so if they are changed the data table needs to be
    #  treated as not having been checked yet. We capture the settings as text, generate a hash for them, and return
    #  the hash. This will be saved as part of the filename for the eval file so we can compare it with the current
    #  value without having to open the eval file.
    # The relevant settings are these:
    #    Attribute (column) names and variable types
    #    For Categorical attributes: codes, the "enforced" flag, missing value codes
    #    For DateTime attributes: format string, missing value codes
    #    For Numerical attributes: number type, missing value codes
    # For now, though, we'll just capture the entire metadata tree under the data table node
    data_table_node = find_data_table_node(eml_node, data_table_name)
    _json = metapype_io.to_json(data_table_node)
    hash = hashlib.shake_256(_json.encode()).hexdigest(5)
    return hash


def collapse_error_info_for_column(column_errors):
    # When essentially the same error is repeated on a sequence of consecutive rows, we want to collapse the sequence
    collapsed_errors = []
    prev_row_number = None
    prev_info = None
    skipped = []
    first_row = True

    for error in column_errors.get('errors'):
        row_number = error.get('row')
        if row_number:
            row_number = int(row_number)
            info = (row_number, error.get('error_type'), error.get('expected'), error.get('found'))
            if first_row:
                # prime the pump
                prev_row_number = row_number
                prev_info = info
                collapsed_errors.append(error_as_dict(info))
                first_row = False
                continue
            if row_number == prev_row_number + 1 and info[1:3] == prev_info[1:3]:
                # This error is part of a consecutive repetitive sequence
                skipped.append(info)
                prev_info = info
                prev_row_number = row_number
                continue

            prev_info = info
            prev_row_number = row_number

            # Have we completed a sequence?
            if len(skipped) <= 2:
                for skipped_item in skipped:
                    collapsed_errors.append(error_as_dict(skipped_item))
                skipped = []
                collapsed_errors.append(error_as_dict(info))
                continue
            collapsed_errors.append(error_as_dict(('', '...', '', '')))
            collapsed_errors.append(error_as_dict(skipped[-1]))
            collapsed_errors.append(error_as_dict(info))
            skipped = []
        else:
            info = (row_number, error.get('error_type'), error.get('expected'), error.get('found'))
            collapsed_errors.append(error_as_dict(info))
            prev_row_number = None
            prev_info = None
            skipped = []
            first_row = True

    # Handle last entries...
    if len(skipped) <= 2:
        for skipped_item in skipped:
            collapsed_errors.append(error_as_dict(skipped_item))
    else:
        collapsed_errors.append(error_as_dict(('', '...', '', '')))
        collapsed_errors.append(error_as_dict(info))
    column_errors['errors'] = collapsed_errors
    return column_errors


if __name__ == "__main__":
    find_large_data_tables()
    clear_eval_files()
    import sys
    sys.exit(0)

    # load_date_time_format_files('/Users/jide/git/ezeml/webapp/static/dateTimeFormatString_list.csv',
    #                             '/Users/jide/git/ezeml/webapp/static/dateTimeFormatString_regex.csv')
    # result = check_date_time_format_specification('YYYY-MM-DD')
    # result = check_date_time_format_specification('foobar')
