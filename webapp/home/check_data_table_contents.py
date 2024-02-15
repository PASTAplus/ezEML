"""
Helper functions for Check Data Tables.

This code is set up to allow Check Data Tables to be called as a web service by another application.
So, for example, its functions load_eml_file() and load_df() take arguments in the form of URLs rather than file paths.
Likewise, the errors are returned as a JSON object rather than a Python dictionary, say.


We want to memoize the results of checking a data table so we can merely link to the results and not have to recompute
them. 

However, we need to allow for the fact that the data table's metadata may have changed since the check was done, and we
need an easy way to detect that that has happened.

We do the following:
    Let's say we have a data table file foobar.csv and we run check data table on it.
    
    We compute a hash of the data table metadata using the function hash_data_table_metadata_settings().
    Let's say the hash is 1234567890. We save the JSON results of the check in a file named foobar.csv_eval_1234567890.
    Then whenever we generate the Check Data Tables page, we can check to see if the metadata hash differs from the 
    current metadata hash.

    If it does, we know we need to recompute the check, so on the Check Data Tables page, instead of displaying a
    "Show errors" link for the table, we display a "Check data table" link so the check will be performed anew.

    If check data table returns no errors, we create a file foobar.csv_eval_1234567890_ok, where the "ok"
    lets us know the table has no errors without our having to open the file and see that the errors list is empty.

One motivation for all this is that we frequently need to set the badge color for the Check Data Tables menu item,
so we want to know as quickly as possible what the error check status is for each of the tables.
"""

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
import urllib.parse
from urllib.parse import unquote_plus
import urllib.request
import warnings

import webapp.home.metapype_client
from webapp.home.home_utils import log_error, log_info, log_available_memory
import webapp.home.utils.load_and_save
from webapp.utils import path_exists, path_isdir, path_join

import webapp.auth.user_data as user_data
from webapp.config import Config
from webapp.home.fetch_data import convert_file_size
from webapp.config import Config

import webapp.views.data_tables.load_data as load_data

from metapype.eml import names
from webapp.exceptions import ezEMLXMLError
from metapype.model import metapype_io
from metapype.model.node import Node


data_time_format_strings = None
date_time_format_regex = None
DATE_TIME_FORMAT_STRINGS_FILENAME = 'webapp/static/dateTimeFormatString_list.csv'
DATE_TIME_FORMAT_REGEX_FILENAME = 'webapp/static/dateTimeFormatString_regex.csv'


def load_eml_file(eml_file_url:str):
    """
    Retrieve an EML file from a URL and return the root node of the EML document.

    Analogous to load_eml() that is used everywhere else in ezEML.
    """
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
    eml_node, nsmap_changed = webapp.home.utils.load_and_save.fixup_eml_namespaces_on_import(eml_node)
    return eml_node, nsmap_changed


def load_df(eml_node, csv_url, data_table_name, max_rows=None):
    """
    Retrieve a data table CSV file from a URL and return:
     a Pandas data frame for it, and
     a flag indicating whether the data frame was truncated.
    """

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
    num_header_lines = 1  # Default, if unspecified in the EML.
    try:
        num_header_lines = int(num_header_lines_node.content)
    except:
        pass

    num_footer_lines_node = data_table_node.find_descendant(names.NUMFOOTERLINES)
    num_footer_lines = 0  # Default, if unspecified in the EML.
    try:
        num_footer_lines = int(num_footer_lines_node.content)
    except:
        pass

    try:
        if delimiter == '\\t':
            delimiter = '\t'

        num_rows = load_data.get_num_rows(unquote_plus(csv_url), delimiter=delimiter, quote_char=quote_char)
        if max_rows is None:
            max_rows = num_rows
        truncated = num_rows > max_rows
        df = pd.read_csv(unquote_plus(csv_url), encoding='utf-8-sig', sep=delimiter, quotechar=quote_char, comment='#',
                           keep_default_na=False, skiprows=range(1, num_header_lines), nrows=max_rows,
                           skipfooter=num_footer_lines, low_memory=False, infer_datetime_format=True,
                           dtype=str)   # Set dtype to str to prevent pandas from converting empty strings to NaN,
                                        # whole numbers to floats, etc.
        return df, truncated

    except Exception as err:
        log_info(f'Error loading CSV file: {err}')
        raise


def find_data_table_node(eml_node, data_table_name):
    """
    Find the data table node in an EML document, based on its name. If there are multiple data tables with the same
    name, raise ValueError. Likewise, if the named table is not found in the EML, raise ValueError.
    """
    data_table_nodes = []
    names_found = []
    eml_node.find_all_descendants(names.DATATABLE, data_table_nodes)
    for data_table_node in data_table_nodes:
        name_found = get_data_table_name(data_table_node)
        if name_found in names_found:
            raise ValueError(f'Duplicate data table "{name_found}" found in EML')
        if name_found == data_table_name:
            return data_table_node
    raise ValueError(f'Data table "{data_table_name}" not found in EML')


def get_attribute_name(attribute_node):
    """
    Get the name of an attribute (column) from an attribute node. If attribute_node doesn't have an
     attributeName child, raise ValueError.
     """
    attribute_name_node = attribute_node.find_child(names.ATTRIBUTENAME)
    if attribute_name_node:
        return attribute_name_node.content
    raise ValueError(f'Column not found in EML')


def normalize_column_name(name):
    """ Normalize a name: i.e., strip whitespace and convert to lowercase. """
    return name.strip().lower()


def names_match(column_name, attribute_name):
    """ Test whether normalized names are equal. """
    return normalize_column_name(column_name) == normalize_column_name(attribute_name)


def get_attribute_node(data_table_node, attribute_name):
    """
    Find an attribute node in a data table node, based on its name. If the named attribute is not found in the data
    table, raise ValueError.
    """
    attribute_nodes = []
    data_table_node.find_all_descendants(names.ATTRIBUTE, attribute_nodes)
    for attribute_node in attribute_nodes:
        attribute_name_node = attribute_node.find_child(names.ATTRIBUTENAME)
        if attribute_name_node and names_match(attribute_name_node.content, attribute_name):
            return attribute_node
    raise ValueError(f'Column "{attribute_name}" not found in EML')


def get_variable_type(attribute_node):
    """
    Get the variable type of an attribute (column) from an attribute node. Variable type here means
        metapype_client.VariableType.
    The attribute node is assumed to have the required descendants.
        E.g., it assumed to have a measurementScale child, which in turn is assumed to have a nominal, ordinal, ratio, or
        interval child. Nominal and ordinal are assumed to have a nonNumericDomain child, etc.
    If the attribute node has the required descendants, the VariableType can be inferred. Otherwise, raise ValueError.
    """
    measurement_scale_node = attribute_node.find_child(names.MEASUREMENTSCALE)
    if measurement_scale_node:

        # See if it's nominal or ordinal, and if so, whether it's categorical or text.
        nominal_or_ordinal_node = measurement_scale_node.find_child(names.NOMINAL)
        if not nominal_or_ordinal_node:
            nominal_or_ordinal_node = measurement_scale_node.find_child(names.ORDINAL)
        if nominal_or_ordinal_node:
            if nominal_or_ordinal_node.find_single_node_by_path([names.NONNUMERICDOMAIN, names.ENUMERATEDDOMAIN]):
                return webapp.home.metapype_client.VariableType.CATEGORICAL.name
            if nominal_or_ordinal_node.find_single_node_by_path([names.NONNUMERICDOMAIN, names.TEXTDOMAIN]):
                return webapp.home.metapype_client.VariableType.TEXT.name

        # See if it's ratio or interval, and if so, it's numerical.
        ratio_or_interval_node = measurement_scale_node.find_child(names.RATIO)
        if not ratio_or_interval_node:
            ratio_or_interval_node = measurement_scale_node.find_child(names.INTERVAL)
        if ratio_or_interval_node:
            return webapp.home.metapype_client.VariableType.NUMERICAL.name

        # See if it's datetime.
        datetime_node = measurement_scale_node.find_child(names.DATETIME)
        if datetime_node:
            return webapp.home.metapype_client.VariableType.DATETIME.name

    raise ValueError(f'Variable type for {get_attribute_name(attribute_node)} could not be inferred from the EML')


def get_data_table_columns(data_table_node):
    """
    Return a list of columns in a data table, where each column is represented as a dict with keys 'name' and 'type' to
    facilitate JSON serialization.
    """
    columns = []
    attribute_nodes = []
    data_table_node.find_all_descendants(names.ATTRIBUTE, attribute_nodes)
    for attribute_node in attribute_nodes:
        attribute_name = get_attribute_name(attribute_node)
        variable_type = get_variable_type(attribute_node)
        columns.append({ 'name': attribute_name, 'type': variable_type })
    return columns


def create_result_json(eml_url, csv_url, columns_checked, errors, max_errs_per_column):
    """
    Return JSON representing the results of a check. errors is a list of error JSONs (see create_error_json).
    """
    if not max_errs_per_column:
        max_errs_per_column = '""'
    result_1 = f'"eml_file_url": "{eml_url}", "csv_file_url": "{csv_url}", "columns_checked": {json.dumps(columns_checked)}, "max_errs_per_column": {max_errs_per_column}, '
    errors = ','.join(errors)
    result_2 = f'"errors": [{errors}]'
    return f"{{ {result_1}{result_2} }}"


def create_error_json(data_table_name, column_name, row_index, error_type, expected, found):
    """
    Return JSON representing an error.
    """
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
    location = f'{{ "table": "{urllib.parse.quote(data_table_name)}", "column": "{urllib.parse.quote(column_name)}", "row": "{row_index}" }}'
    return f'{{ "error_scope": "{error_scope}", "location": {location}, "error_type": "{error_type}", "expected": {json.dumps(expected)}, "found": {json.dumps(found)}}}'


def get_date_time_format_specification(data_table_node, attribute_name):
    """
    Return the datetime format string, if any, found in the EML for a given attribute (column) name. If no format
    string is found, return None.

    If an attribute with the given name is not found in the EML, raise ValueError.
    """
    attribute_node = get_attribute_node(data_table_node, attribute_name)
    if attribute_node:
        format_string_node = attribute_node.find_single_node_by_path(
            [names.MEASUREMENTSCALE, names.DATETIME, names.FORMATSTRING])
        if format_string_node:
            return format_string_node.content
    raise ValueError


def get_missing_value_codes(data_table_node, column_name):
    """
    Return a list of missing value codes for a given attribute (column) name. If no missing value codes are found,
    return an empty list.
    """
    attribute_node = get_attribute_node(data_table_node, column_name)
    missing_value_codes = []
    if attribute_node:
        missing_value_code_nodes = attribute_node.find_all_nodes_by_path([names.MISSINGVALUECODE, names.CODE])
        for missing_value_code_node in missing_value_code_nodes:
            if missing_value_code_node.content:
                missing_value_codes.append(re.escape(missing_value_code_node.content))
    return missing_value_codes


def get_categorical_codes(attribute_node):
    """
    Return a list of categorical codes for a given attribute (column) name. If no categorical codes are found, return
    an empty list.
    """
    codes = []
    code_nodes = []
    attribute_node.find_all_descendants(names.CODE, code_nodes)
    for code_node in code_nodes:
        if code_node.content:
            codes.append(code_node.content)
    return codes


def get_number_type(attribute_node):
    """
    Return the numberType for a given numerical attribute (column) name.
    Number type is one of 'natural', 'whole', 'integer', or 'real'.
    If the numberType is not found, raise ValueError.
    """
    number_type_node = attribute_node.find_descendant(names.NUMBERTYPE)
    if not number_type_node:
        attribute_name = get_attribute_name(attribute_node)
        raise ValueError(f'Column {attribute_name} is missing a numberType element')
    number_type = number_type_node.content
    if number_type not in ('natural', 'whole', 'integer', 'real'):
        attribute_name = get_attribute_name(attribute_node)
        raise ValueError(f'Column {attribute_name} has unexpected numberType: {number_type}')
    return number_type


def match_with_regex(col_values, regex, mvc, empty_is_ok=True):
    """
    Return a boolean Series indicating whether each value in a column matches a given regex.
    """
    warnings.filterwarnings("ignore", 'This pattern is interpreted as a regular expression, and has match groups.')
    # If regex starts with a ^, remove it temporarily
    if regex.startswith('^'):
        regex = regex[1:]
    # If regex ends with a $, remove it temporarily
    if regex.endswith('$'):
        regex = regex[:-1]
    if mvc:
        regex = f"({regex})" + '|' + f"{'|'.join(mvc)}"
    if empty_is_ok:
        regex = '$|' + regex
    regex = f"^{regex}$"
    matches = col_values.str.contains(regex)
    return matches


def check_columns_existence_against_metadata(data_table_node, df):
    """
    Check that the columns in a data table match what's expected based on the metadata.
    """
    def display_nonprintable(s):
        if s.isprintable():
            return s
        return ''.join([c if c.isprintable() else "�" for c in s])

    errors = []
    # Get the column names from the metadata
    attribute_name_nodes = []
    metadata_column_names = []
    data_table_node.find_all_descendants(names.ATTRIBUTENAME, attribute_name_nodes)
    # Create a list of column names from the metadata
    for attribute_name_node in attribute_name_nodes:
        metadata_column_names.append(attribute_name_node.content)
    # Get the column names from the data table
    data_table_column_names = list(df.columns)
    # If the number of columns differs, that's an error.
    if len(metadata_column_names) != len(data_table_column_names):
        errors.append(create_error_json(get_data_table_name(data_table_node), None, None,
                                        'Metadata defines a different number of columns than the data table',
                                        len(metadata_column_names), len(data_table_column_names)))
    # Otherwise, check that the column names match.
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
    """
    Return the number of header lines in a data table based on the metadata.
    """
    num_header_lines_node = data_table_node.find_descendant(names.NUMHEADERLINES)
    try:
        return int(num_header_lines_node.content)
    except:
        return 1


def check_numerical_column(df, data_table_node, column_name, max_errs_per_column):
    """
    Check the contents of a numerical column. I.e., check that the values are numbers and that they match the
    numberType specified in the metadata.
    """

    attribute_node = get_attribute_node(data_table_node, column_name)
    number_type = get_number_type(attribute_node)
    col_values = df[column_name].astype(str)

    # Construct a regex based on the number type
    if number_type == 'integer':
        regex = '^[-+]?[0-9]+$'
    elif number_type == 'whole' or number_type == 'natural':
        regex = '^[0-9]+$'
    else:
        regex = '^[-+]?[0-9]*\.?[0-9]+([eE][-+]?[0-9]+)?$'
    mvc = get_missing_value_codes(data_table_node, column_name)
    truncated = False
    try:
        matches = match_with_regex(col_values, regex, mvc)
    except KeyError:
        # This indicates the column name was not found in the data table.
        return [create_error_json(get_data_table_name(data_table_node), column_name, None,
                                 'Column not found in data table', column_name, 'Not found')], truncated
    # mvc = get_missing_value_codes(data_table_node, column_name)
    # if len(mvc) > 0:
    #     mvc_regex = '^' + '|'.join(mvc) + '$'
    #     warnings.filterwarnings("ignore", 'This pattern is interpreted as a regular expression, and has match groups.')
    #     mvc_matches = col_values.str.contains(mvc_regex)
    #     # Errors are rows with both matches == False and mvc_matches == False
    #     result = ~(matches | mvc_matches)
    # else:
    #     result = ~matches
    result = ~matches
    error_indices = result[result].index.values

    data_table_name = get_data_table_name(data_table_node)
    # Set up the expected value error message based on the number type
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
            truncated = True
            break

    return errors, truncated


def check_categorical_column(df, data_table_node, column_name, max_errs_per_column):
    """
    Check the contents of a categorical column. I.e., check that the values are in the list of codes
    and missing value codes.
    """

    errors = []
    truncated = False
    attribute_node = get_attribute_node(data_table_node, column_name)
    col_values = df[column_name].astype(str)

    # If the metadata says codes values are not "enforced" to be the defined codes, then there cannot be errors
    enumerated_domain_node = attribute_node.find_descendant(names.ENUMERATEDDOMAIN)
    if enumerated_domain_node and enumerated_domain_node.attribute_value('enforced') == 'no':
        return [], truncated

    codes = list(map(re.escape, get_categorical_codes(attribute_node)))
    codes_regex = '^' + '|'.join(codes) + '$'
    mvc = get_missing_value_codes(data_table_node, column_name)
    try:
        matches = match_with_regex(col_values, codes_regex, mvc)
    except KeyError:
        return [], truncated   # This indicates the column is missing, but that type of error is reported via
                               # check_columns_existence_against_metadata()
    # mvc = get_missing_value_codes(data_table_node, column_name)
    # if len(mvc) > 0:
    #     mvc_regex = '^' + '|'.join(mvc) + '$'
    #     warnings.filterwarnings("ignore", 'This pattern is interpreted as a regular expression, and has match groups.')
    #     mvc_matches = col_values.str.contains(mvc_regex)
    #     # Errors are rows with both matches == False and mvc_matches == False
    #     result = ~(matches | mvc_matches)
    # else:
    #     result = ~matches
    result = ~matches
    error_indices = result[result].index.values
    data_table_name = get_data_table_name(data_table_node)
    expected = 'A defined code'
    num_header_lines = get_num_header_lines(data_table_node)
    for index in error_indices:
        # Make the index 1-based and take into account the number of header rows. I.e., make it match what they'd see in Excel.
        errors.append(create_error_json(data_table_name, column_name,
                                        index + num_header_lines + 1,
                                        'Categorical element is not a defined code',
                                        expected, col_values[index]))
        if max_errs_per_column and len(errors) > max_errs_per_column:
            truncated = True
            break

    return errors, truncated


def check_date_time_column(df, data_table_node, column_name, max_errs_per_column):
    """
    Check the contents of a datetime column. I.e., check that the values are in the expected format based on the
    metadata or are one of the missing value codes.
    """

    def get_date_time_format_regex(data_table_node, attribute_name):
        """ Get the regex for the date time format specified in the metadata."""
        def get_regex_for_format(format):
            load_date_time_format_files()
            return date_time_format_regex.get(format, None)

        date_time_format = get_date_time_format_specification(data_table_node, attribute_name)
        return get_regex_for_format(date_time_format)

    col_values = df[column_name].astype(str)
    truncated = False
    regex = get_date_time_format_regex(data_table_node, column_name)
    if not regex:
        date_time_format = get_date_time_format_specification(data_table_node, column_name)
        return [create_error_json(get_data_table_name(data_table_node), column_name, None,
                                 'The specified DateTime Format String is not supported.',
                                  'A <a href="../datetime_formats">supported</a> format',
                                  date_time_format)], truncated
    mvc = get_missing_value_codes(data_table_node, column_name)
    try:
        matches = match_with_regex(col_values, regex, mvc)
    # try:
    #     matches = match_with_regex(col_values, regex)
    except KeyError:
        return [create_error_json(get_data_table_name(data_table_node), column_name, None,
                                 'Column not found in table', (column_name), 'Not found')], truncated
    # mvc = get_missing_value_codes(data_table_node, column_name)
    # if len(mvc) > 0:
    #     mvc_regex = '^' + '|'.join(mvc) + '$'
    #     warnings.filterwarnings("ignore", 'This pattern is interpreted as a regular expression, and has match groups.')
    #     mvc_matches = col_values.str.contains(mvc_regex)
    #     # Errors are rows with both matches == False and mvc_matches == False
    #     result = ~(matches | mvc_matches)
    # else:
    #     result = ~matches
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
            truncated = True
            break

    return errors, truncated


def check_data_table(eml_file_url:str=None,
                     csv_file_url:str=None,
                     data_table_name:str=None,
                     column_names:List[str]=None,
                     max_errs_per_column=Config.MAX_ERRS_PER_COLUMN,
                     collapse_errs:bool=False):
    """
    Check a data table and return JSON with information about what was checked and a list of any errors found.

    The caller can specify a list of column names to check. If not specified, all columns will be checked.

    eml_file and csv_file are provided as URLs. Check the column names match the metadata, and for each column check
    its contents based on the metadata specification for the column.
    """
    eml_node, _ = load_eml_file(eml_file_url)

    if not check_table_headers(csv_file_url=csv_file_url):
        flash(f'A column header in table {data_table_name} contains a "#" character, which is not allowed. '
              'Please remove this character and re-upload the file.', 'error')
        return False

    max_rows = Config.MAX_DATA_ROWS_TO_CHECK
    df, truncated = load_df(eml_node, csv_file_url, data_table_name, max_rows=max_rows)
    if truncated:
        flash(f'The number of rows in {os.path.basename(unquote_plus(csv_file_url))} is greater than {max_rows:,}. ezEML checks '
              f'only the first {max_rows:,} rows. Often this suffices to indicate the kinds of errors that are present.\nThe full '
              f'file will be checked when you submit the data package to the EDI repository.', 'warning')

    log_info('After loading the data table')
    log_available_memory()

    data_table_node = find_data_table_node(eml_node, data_table_name)
    errors, data_table_column_names, metadata_column_names = check_columns_existence_against_metadata(data_table_node, df)

    # Check for empty rows
    data_table_name = get_data_table_name(data_table_node)
    num_header_lines = get_num_header_lines(data_table_node)
    errors.extend(check_for_empty_rows(df, data_table_name, num_header_lines))

    if not column_names:
        # check them all... we will use the data table column names. they may not exactly match the metadata column
        # names, for example if there are spaces at the end of column names.
        column_names = data_table_column_names
    columns_checked = []
    truncated = False
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
        from datetime import date, datetime
        start = datetime.now()
        if variable_type == 'CATEGORICAL':
            columns_checked.append(column_name)
            new_errors, truncated = check_categorical_column(df, data_table_node, column_name, max_errs_per_column)
            errors.extend(new_errors)
        elif variable_type == 'DATETIME':
            columns_checked.append(column_name)
            new_errors, truncated = check_date_time_column(df, data_table_node, column_name, max_errs_per_column)
            errors.extend(new_errors)
        elif variable_type == 'NUMERICAL':
            columns_checked.append(column_name)
            new_errors, truncated = check_numerical_column(df, data_table_node, column_name, max_errs_per_column)
            errors.extend(new_errors)
        end = datetime.now()
        elapsed = (end - start).total_seconds()
        log_info(f'After checking column: {column_name}... elapsed time: {elapsed:.1f} seconds')
        log_available_memory()

    results = create_result_json(eml_file_url, csv_file_url, columns_checked, errors, max_errs_per_column)

    if truncated:
        flash('Only partial results are shown below because the number of errors has exceeded the maximum allowed.\n' \
              'To find additional errors, correct the errors shown below, re-upload the table, and run the check again.')

    log_info(f'After creating result JSON')
    log_available_memory()

    return results


def load_date_time_format_files(strings_filename=DATE_TIME_FORMAT_STRINGS_FILENAME,
                                regex_filename=DATE_TIME_FORMAT_REGEX_FILENAME):
    """
    Load the date time format strings and corresponding regexes from the CSV files and save in global variables.
    """
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


def get_data_table_name(data_table_node):
    """ Return the name of the data table according to the metadata. """
    data_table_name_node = data_table_node.find_child(names.ENTITYNAME)
    if data_table_name_node:
        return data_table_name_node.content.strip()


def get_data_table_filename(data_table_node, encoded_for_url=False):
    """
    Get the filename of the data table. If encoded_for_url is True, then the returned filename will be encoded for use
    in a URL.
    """
    data_table_object_name_node = data_table_node.find_descendant(names.OBJECTNAME)
    if data_table_object_name_node:
        if not encoded_for_url:
            return data_table_object_name_node.content
        else:
            return urllib.parse.quote(data_table_object_name_node.content)


def get_data_table_size(data_table_node):
    """ Return the size of the data table according to the metadata. """
    data_table_size_node = data_table_node.find_descendant(names.SIZE)
    if data_table_size_node:
        return data_table_size_node.content


def check_date_time_attribute(attribute_node):
    """
    Check a datetime attribute to see if it has a format string that is not in the list of known format strings. If so,
    return None. Otherwise, return the format string.

    This function is used by Check Metadata. It's here because it uses load_date_time_format_files() and that function
    is used by other functions in this module.
    """

    def check_date_time_format_specification(specification):
        """ Check if a datetime specification has a valid format according to our list of supported formats. """
        load_date_time_format_files()
        return specification in data_time_format_strings.keys()

    format_string_node = attribute_node.find_single_node_by_path(
        [names.MEASUREMENTSCALE, names.DATETIME, names.FORMATSTRING])
    if format_string_node:
        format_string = format_string_node.content
        if not check_date_time_format_specification(format_string):
            return format_string


def check_for_empty_rows(df, data_table_name, num_header_lines):
    """
    Check for empty rows in the data table.
    """
    errors = []
    # Check for empty rows
    empty_rows = df.eq('').all(axis=1)
    empty_row_indices = empty_rows[empty_rows].index
    for index in empty_row_indices:
        # Make the index 1-based and take into account the number of header rows. I.e., make it match what they'd see in Excel.
        errors.append(create_error_json(data_table_name, None,
                                        index + num_header_lines + 1,
                                        'Row is empty', 'Data', 'No data'))
    return errors


def format_date_time_formats_list():
    """
    Format the list of supported date time formats for display in HTML.

    This function is used by Check Metadata. It's here because it uses load_date_time_format_files() and that function
    is used by other functions in this module.
    """

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


def generate_error_info_for_webpage(data_table_node, errors):
    """
    Given the JSON errors output, generate the HTML for the data table errors page.
    """

    def make_blanks_visible(s: str):
        """ If the string contains blanks, make those blanks highly noticeable in the HTML. """
        if not s:
            return s, ''
        s = str(s)
        blank = '<span style="color:red;font-size:100%;font-weight:bold;">\u274f</span>'
        # Also considered \u2420 and \u25a1
        if s.isspace():
            s = s.replace(' ', blank)
        else:
            # make leading and trailing spaces visible
            leading = len(s) - len(s.lstrip())
            trailing = len(s) - len(s.rstrip())
            s = s[:leading].replace(' ', blank) + s[leading:len(s) - trailing] + s[len(s) - trailing:].replace(' ',
                                                                                                               blank)
        has_blank = blank in s
        return s, has_blank

    errs_obj = json.loads(errors)
    data_table_name = get_data_table_name(data_table_node)
    column_name = None
    row_errs = []
    column_errs = []
    errors = []
    has_blanks = False
    for error in errs_obj['errors']:
        if error['location']['table'] != urllib.parse.quote(data_table_name):
            continue
        if error['error_scope'] in ['column', 'element']:
            if error['location']['column'] != (urllib.parse.quote(column_name) if column_name else None):
                column_name = urllib.parse.unquote(error['location']['column'])
                try:
                    attribute_node = get_attribute_node(data_table_node, column_name)
                    variable_type = get_variable_type(attribute_node)
                except ValueError:
                    variable_type = 'UNKNOWN'
                errors = []
                column_errs.append({ "column_name": column_name, "variable_type": variable_type, "errors": errors})
        if error['error_scope'] in ['table', 'row']:
            if not row_errs:
                errors = []
                row_errs.append({ "column_name": '', "variable_type": '', "errors": errors})
        expected, blank = make_blanks_visible(error['expected'])
        has_blanks = has_blanks or blank
        found, blank = make_blanks_visible(error['found'])
        has_blanks = has_blanks or blank
        errors.append({
            "row": error['location']['row'],
            "error_type": error['error_type'],
            "expected": expected,
            "found": found})
    return row_errs, column_errs, has_blanks


def get_eml_file_url(document_name, eml_node):
    """ Return the EML file location as a URL for use in the check data tables code. """
    filepath = f'{path_join(Config.BASE_DIR, user_data.get_user_folder_name(), document_name)}.xml'
    encoded_for_url = f'{path_join(Config.BASE_DIR, user_data.get_user_folder_name(), urllib.parse.quote(document_name))}.xml'
    if path_exists(filepath):
        return f'file://{encoded_for_url}'
    package_id = eml_node.attribute_value('packageId')
    if package_id:
        filepath = f'{path_join(Config.BASE_DIR, user_data.get_user_folder_name(), package_id)}.xml'
        if path_exists(filepath):
            return f'file://{filepath}'
    return None


def get_csv_file_url(document_name, data_table_node):
    """ Return the CSV file location as a URL for use in the check data tables code. """
    csv_file_name = get_data_table_filename(data_table_node)
    return f'file://{os.path.join(Config.BASE_DIR, user_data.get_document_uploads_folder_name(encoded_for_url=True), urllib.parse.quote(csv_file_name))}'


def get_csv_filepath(document_name, csv_file_name):
    """ Return the CSV file location as a filepath for use in the check data tables code. """
    try:
        return os.path.join(user_data.get_document_uploads_folder_name(document_name), csv_file_name)
    except:
        log_info(f"get_csv_filepath: {document_name}, {csv_file_name}")
        return None


def get_csv_errors_archive_filepath(document_name, csv_file_name, metadata_hash):
    """ Return the file paths associated with the  CSV file. """

    archive_filepath = f"{get_csv_filepath(document_name, csv_file_name)}_eval_{metadata_hash}"
    ok_filepath = f"{get_csv_filepath(document_name, csv_file_name)}_eval_{metadata_hash}_ok"
    # Allow for the metadata hash forming part of the eval file's filename.
    wildcard_filepath = f"{get_csv_filepath(document_name, csv_file_name)}_eval_??????????"
    ok_wildcard_filepath = f"{get_csv_filepath(document_name, csv_file_name)}_eval_??????????_ok"
    return archive_filepath, ok_filepath, wildcard_filepath, ok_wildcard_filepath


def set_check_data_tables_badge_status(document_name, eml_node):
    """ Determine the color of the Check Data Tables badge in the main Contents menu. """
    status = 'green'
    data_table_nodes = []
    eml_node.find_all_descendants(names.DATATABLE, data_table_nodes)
    for data_table_node in data_table_nodes:
        csv_file_name = get_data_table_filename(data_table_node)
        data_table_name = get_data_table_name(data_table_node)
        metadata_hash = hash_data_table_metadata_settings(eml_node, data_table_name)
        this_status = get_data_file_eval_status(document_name, csv_file_name, metadata_hash)
        if this_status == 'red' or this_status == 'black':
            status = 'red'
            break
        if this_status == 'yellow' and status == 'green':
            status = 'yellow'
    session['check_data_tables_status'] = status
    return status


def get_data_file_eval_status(document_name, csv_file_name, metadata_hash):
    """ Determine the color of the badge for an individual data table in the Check Data Tables page."""

    def csv_file_exists(document_name, csv_file_name):
        csv_filepath = get_csv_filepath(document_name, csv_file_name)
        return path_exists(csv_filepath)

    if not csv_file_exists(document_name, csv_file_name):
        return 'black'
    # Returns green, yellow, red, or black.
    archive_filepath, ok_filepath, wildcard_filepath, ok_wildcard_filepath = \
        get_csv_errors_archive_filepath(document_name, csv_file_name, metadata_hash)
    if path_exists(archive_filepath):
        return "red"
    if path_exists(ok_filepath):
        return "green"
    return "yellow"


def reset_data_file_eval_status(document_name, csv_file_name):
    """ Reset the data table to unevaluated state, for example because a Reupload has been done. """

    archive_filepath, ok_filepath, wildcard_filepath, ok_wildcard_filepath = \
        get_csv_errors_archive_filepath(document_name, csv_file_name, '')

    filelist = glob.glob(wildcard_filepath)
    for filepath in filelist:
        os.remove(filepath)

    filelist = glob.glob(ok_wildcard_filepath)
    for filepath in filelist:
        os.remove(filepath)


def save_data_file_eval(document_name, csv_file_name, metadata_hash, errors):
    """ Save the results of the data table evaluation. """

    reset_data_file_eval_status(document_name, csv_file_name)
    archive_filepath, ok_filepath, wildcard_filepath, ok_wildcard_filepath = \
        get_csv_errors_archive_filepath(document_name, csv_file_name, metadata_hash)
    errs_obj = json.loads(errors)
    if not errs_obj['errors']:
        archive_filepath = ok_filepath
    with open(archive_filepath, 'w') as eval_file:
        eval_file.write(errors)


def get_data_file_eval(document_name, csv_file_name, metadata_hash):
    """ Return the data table evaluation results as saved in an eval file, or None if no eval file exists. """

    archive_filepath, ok_filepath, wildcard_filepath, ok_wildcard_filepath = \
        get_csv_errors_archive_filepath(document_name, csv_file_name, metadata_hash)
    if not path_exists(archive_filepath):
        archive_filepath = ok_filepath
        if not path_exists(archive_filepath):
            # There may exist a version with a different hash. If so, it's obsolete and we want to delete it.
            matches = glob.glob(wildcard_filepath)
            for match in matches:
                os.remove(match)
            return None
    with open(archive_filepath, 'r') as eval_file:
        return eval_file.read()


def check_table_headers(current_document=None, data_table_node=None, csv_file_url=None):
    """
        Check for special chars in table headers. Currently, we check only for '#' chars.
        We need to look directly in the CSV file rather than the EML, since if a header contains
        a '#' char, loading it will fail.
    """
    if csv_file_url is None:
        assert(current_document and data_table_node)
        csv_file_url = get_csv_file_url(current_document, data_table_node)
    for line in urllib.request.urlopen(csv_file_url):
        if '#' in line.decode('utf-8'):
            return False
        break
    return True


def check_all_tables(current_document, eml_node):
    def check_all_table_headers(current_document, eml_node):
        data_table_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.DATATABLE])
        for data_table_node in data_table_nodes:
            if not check_table_headers(current_document=current_document, data_table_node=data_table_node):
                data_table_name = get_data_table_name(data_table_node)
                flash(f'A column header in table {data_table_name} contains a "#" character, which is not allowed. '
                      'Please remove this character and re-upload the file.', 'error')
                return False
        return True

    def check_a_table(current_document, eml_node, data_table_node, data_table_name):
        eml_file_url = get_eml_file_url(current_document, eml_node)
        csv_file_url = get_csv_file_url(current_document, data_table_node)
        csv_filename = get_data_table_filename(data_table_node)
        csv_filepath = get_csv_filepath(current_document, csv_filename)
        data_table_size = get_data_table_size(data_table_node)

        metadata_hash = hash_data_table_metadata_settings(eml_node, data_table_name)

        errors = get_data_file_eval(current_document, csv_filename, metadata_hash)
        if not errors:
            errors = check_data_table(eml_file_url, csv_file_url, data_table_name)

        row_errs, column_errs, has_blanks = generate_error_info_for_webpage(data_table_node, errors)
        collapsed_errors = collapse_error_info_for_webpage(row_errs, column_errs)

        save_data_file_eval(current_document, csv_filename, metadata_hash, errors)
        set_check_data_tables_badge_status(current_document, eml_node)

    if not check_all_table_headers(current_document, eml_node):
        return

    data_table_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.DATATABLE])
    for data_table_node in data_table_nodes:
        data_table_name = get_data_table_name(data_table_node)
        csv_file_name = get_data_table_filename(data_table_node)
        metadata_hash = hash_data_table_metadata_settings(eml_node, data_table_name)
        status = get_data_file_eval_status(current_document, csv_file_name, metadata_hash)
        if status == 'yellow':
            check_a_table(current_document, eml_node, data_table_node, data_table_name)


def create_check_data_tables_status_page_content(document_name, eml_node):
    """
    Create the HTML content for the Check Data Tables page. This lists the tables and their badges and has links to
    check the table or show errors for the table, or if no errors, simple say "No errors found".

    In addition, it returns a string indicating whether the Check All Tables button should be enabled or disabled.
    """
    btn_status = 'disabled'
    data_table_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.DATATABLE])
    output = '<table class="eval_table" width=100% style="padding: 10px;"><tr><th></th><th>Data Table Name</th><th></th></tr>'
    for data_table_node in data_table_nodes:
        data_table_name = get_data_table_name(data_table_node)
        csv_file_name = get_data_table_filename(data_table_node)
        metadata_hash = hash_data_table_metadata_settings(eml_node, data_table_name)
        status = get_data_file_eval_status(document_name, csv_file_name, metadata_hash)
        if status == 'yellow':
            btn_status = ''
            onclick = ''
            size = get_data_table_size(data_table_node)
            if size and int(size) > 10**7:
                kb, mb, gb = convert_file_size(size)
                mb = round(mb)
                onclick = f'onclick="return confirm(\'This data table may take several minutes to check. Continue?\');"'
            action = f'<a href="data_table_errors/{urllib.parse.quote(data_table_name)}" {onclick}>Check data table</a>'
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
    return output, btn_status


def error_as_dict(error_info):
    """ Convert an error_info tuple to a dict. """
    row, error_type, expected, found = error_info
    return {
        'row': str(row),
        'error_type': error_type,
        'expected': expected,
        'found': found
    }


def hash_data_table_metadata_settings(eml_node, data_table_name):
    """
    Generate a hash of data table metadata settings. This is used to determine if the metadata has changed, in which
    case memoized error results are obsolete.

    Various metadata settings affect the checking of data tables, so if they are changed the data table needs to be
     treated as not having been checked yet. We capture the settings as text, generate a hash for them, and return
     the hash. This will be saved as part of the filename for the eval file so we can compare it with the current
     value without having to open the eval file.
    The relevant settings are these:
       Attribute (column) names and variable types
       For Categorical attributes: codes, the "enforced" flag, missing value codes
       For DateTime attributes: format string, missing value codes
       For Numerical attributes: number type, missing value codes
    For now, though, we'll just capture the entire metadata tree under the data table node
    """
    data_table_node = find_data_table_node(eml_node, data_table_name)
    _json = metapype_io.to_json(data_table_node)
    hash = hashlib.shake_256(_json.encode()).hexdigest(5)
    return hash


def collapse_error_info_for_webpage(row_errs, column_errs):
    """
    When essentially the same error is repeated on a sequence of consecutive rows, we want to collapse the sequence.
    """

    def collapse_error_info(column_errors):
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

    errors = row_errs + column_errs
    for error in errors:
        collapse_error_info(error)
    return errors


EML_FILES_PATH = '/Users/jide/git/umbra/eml_files'
def get_existing_eml_files():
    # For use while developing and debugging
    import glob
    import os
    filelist = glob.glob(f'{EML_FILES_PATH}/*.xml')
    return sorted([os.path.basename(x) for x in filelist])


def clear_eval_files():
    # For use while developing and debugging
    uploads_folder = f'/Users/jide/git/ezEML/user-data/EDI-1a438b985e1824a5aa709daa1b6e12d2/uploads'
    subdirs = []
    for file in os.listdir(uploads_folder):
        filepath = path_join(uploads_folder, file)
        if path_isdir(filepath):
            subdirs.append(filepath)
    for subdir in subdirs:
        filelist = glob.glob(f'{subdir}/*_eval_*')
        for filepath in filelist:
            os.remove(filepath)
    for subdir in subdirs:
        filelist = glob.glob(f'{subdir}/*_eval')
        for filepath in filelist:
            os.remove(filepath)
