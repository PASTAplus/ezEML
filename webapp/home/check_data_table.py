from collections import OrderedDict
import csv
import json

from metapype.eml import names
from metapype.model import metapype_io
from metapype.model.node import Node


data_time_format_strings = None
date_time_format_regex = None
DATE_TIME_FORMAT_STRINGS_FILENAME = 'webapp/static/dateTimeFormatString_list.csv'
DATE_TIME_FORMAT_REGEX_FILENAME = 'webapp/static/dateTimeFormatString_regex.csv'
# DATE_TIME_FORMAT_STRINGS_FILENAME = '/Users/jide/git/ezeml/webapp/static/dateTimeFormatString_list.csv'
# DATE_TIME_FORMAT_REGEX_FILENAME = '/Users/jide/git/ezeml/webapp/static/dateTimeFormatString_regex.csv'


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
    return date_time_format_regex.get(format, None)


def check_values_against_format(df, col_name, format):
    pass


def load_xml(filename):
    with open(f"{filename}", "r") as f:
        xml = "".join(f.readlines())
    eml_node = metapype_io.from_xml(xml)
    assert isinstance(eml_node, Node)
    return eml_node


def json_from_xml(filename):
    eml_node = load_xml(filename)
    _json = metapype_io.to_json(eml_node)
    parsed = json.loads(_json)
    return json.dumps(parsed, indent=1, sort_keys=False)


def find_nodes(eml_node, node_path):
    nodes = []
    if '|' in node_path:
        parents = []
        parent_name, child_name = node_path.split('|')
        eml_node.find_all_descendants(parent_name, parents)
        for parent in parents:
            nodes.extend(parent.find_all_children(child_name))
    else:
        eml_node.find_all_descendants(node_path, nodes)
    return nodes


def get_date_time_columns(data_table_node):
    date_time_columns = []
    attribute_nodes = data_table_node.get_descendants(names.ATTRIBUTE)
    for attribute_node in attribute_nodes:
        format_string_node = attribute_node.find_descendants(names.FORMATSTRING)
        if format_string_node:
            column_name = attribute_node.attribute_name
            format_string = format_string_node.contents
            date_time_columns.append((column_name, format_string))
    return date_time_columns


def get_data_table_name(data_table_node):
    data_table_name_node = data_table_node.find_child(names.ENTITYNAME)
    if data_table_name_node:
        return data_table_name_node.content


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


def check_data_table_formats(data_table_node):
    errors = []
    # Find DateTime attributes
    attribute_list_node = data_table_node.find_descendant(names.ATTRIBUTELIST)
    attribute_nodes = attribute_list_node.find_all_children(names.ATTRIBUTE)
    for attribute_node in attribute_nodes:
        format_string_node = attribute_node.find_single_node_by_path([names.MEASUREMENTSCALE, names.DATETIME, names.FORMATSTRING])
        if format_string_node:
            format_string = format_string_node.content
            if not check_date_time_format_specification(format_string_node):
                errors.append((get_data_table_name(data_table_node), format_string))
    return errors


def check_data_table_contents(data_table_node):
    pass


def check_data_tables(eml_node, check_to_run):
    data_table_nodes = []
    eml_node.find_all_descendants(names.DATATABLE, data_table_nodes)
    for data_table_node in data_table_nodes:
        data_table_name_node = data_table_node.find_child(names.ENTITYNAME)
        if data_table_name_node:
            data_table_name = data_table_name_node.content
            print(f'Checking {data_table_name}')
        errors = check_to_run(data_table_node)
    return errors


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


if __name__ == "__main__":
    print('Hello')
    load_date_time_format_files('/Users/jide/git/ezeml/webapp/static/dateTimeFormatString_list.csv',
                                '/Users/jide/git/ezeml/webapp/static/dateTimeFormatString_regex.csv')
    result = check_date_time_format_specification('YYYY-MM-DD')
    result = check_date_time_format_specification('foobar')
    EML_FILES_PATH = '/Users/jide/git/umbra/eml_files'
    eml_node = load_xml(f'{EML_FILES_PATH}/edi.1.1.xml')
    format_errors = check_data_tables(eml_node, check_data_table_formats)
    if len(format_errors) > 0:
        print(format_errors)
    else:
        print('DateTime formats are ok')

