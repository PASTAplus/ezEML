from datetime import datetime
from flask_login import (
    current_user, login_required
)

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Border, Font, PatternFill, Side

from webapp.home import exceptions as exceptions
from webapp.home.utils.load_and_save import load_eml, save_eml
from webapp.home.utils.lists import compose_attribute_mscale
from webapp.home.utils.node_utils import new_child_node
from metapype.model.node import Node
from metapype.eml import names


wb = None
ws = None
row = None
maxcol = None

def rgb_to_hex(rgb):
    return '{:02X}{:02X}{:02X}'.format(*rgb)

REQUIRED = rgb_to_hex((232, 200, 200))
RECOMMENDED = rgb_to_hex((252, 235, 166))
OPTIONAL = rgb_to_hex((211, 237, 244))
RARELY_USED = rgb_to_hex((242, 242, 242))
FONT_SIZE = 14


def next_spreadsheet_column(column, i=1):
    global maxcol
    """
    Given a spreadsheet column name (e.g., 'A', 'Z', 'AA') and an integer i,
    returns the column name i positions greater.
    """
    def column_to_number(col):
        """Convert a column code to a number."""
        number = 0
        for c in col:
            number = number * 26 + (ord(c) - ord('A') + 1)
        return number

    def number_to_column(n):
        """Convert a number back to a column code."""
        col = []
        while n > 0:
            n, remainder = divmod(n - 1, 26)
            col.append(chr(65 + remainder))
        return ''.join(reversed(col))

    # Convert the current column to a number, add i, and convert back
    current_col_num = column_to_number(column)
    next_col_num = current_col_num + i
    if maxcol is None or next_col_num > maxcol:
        maxcol = next_col_num
    return number_to_column(next_col_num)


def is_categorical(attribute_node):
    enumerated_domain_node = attribute_node.find_descendant(names.ENUMERATEDDOMAIN)
    if enumerated_domain_node:
        return True
    return False


def is_datetime(attribute_node):
    datetime_node = attribute_node.find_child(names.DATETIME)
    if datetime_node:
        return True
    return False


def interval_or_ratio_node(attribute_node):
    measurement_scale_node = attribute_node.find_child(names.MEASUREMENTSCALE)
    if measurement_scale_node:
        interval_node = measurement_scale_node.find_child(names.INTERVAL)
        if interval_node:
            return interval_node
        ratio_node = measurement_scale_node.find_child(names.RATIO)
        if ratio_node:
            return ratio_node
    return None


def is_numerical(attribute_node):
    if interval_or_ratio_node(attribute_node):
        return True
    return False


####################################################################################################
# Functions for writing metadata to a spreadsheet
####################################################################################################

def set_maxcol(cell):
    global maxcol
    col = cell[0]
    col_num = ord(col) - ord('A') + 1
    if maxcol is None or col_num > maxcol:
        maxcol = col_num


def highlight_cell(cell, color):
    fill = PatternFill(start_color=color, end_color=color, fill_type='solid')
    border_side = Side(style='thin', color='000000')
    border = Border(left=border_side, right=border_side, top=border_side, bottom=border_side)
    ws[cell].font = Font(size=FONT_SIZE)
    ws[cell].fill = fill
    ws[cell].border = border
    set_maxcol(cell)


def bold(cell, text):
    ws[cell].font = Font(size=FONT_SIZE, bold=True)
    ws[cell] = text
    set_maxcol(cell)


def normal(cell, text):
    ws[cell].font = Font(size=FONT_SIZE)
    ws[cell] = text
    set_maxcol(cell)


def required(cell, text):
    normal(cell, text)
    highlight_cell(cell, REQUIRED)


def recommended(cell, text):
    normal(cell, text)
    highlight_cell(cell, RECOMMENDED)


def optional(cell, text):
    normal(cell, text)
    highlight_cell(cell, OPTIONAL)


def rarely_used(cell, text):
    normal(cell, text)
    highlight_cell(cell, RARELY_USED)


def start_table(package_name, table_name, description=''):
    global row
    bold('A1', 'Package Name')
    normal('B1', package_name)
    bold('A2', 'Table Name')
    normal('B2', table_name)
    bold('A3', 'Date Downloaded')
    normal('B3', datetime.now().strftime('%Y-%m-%d'))
    row = 4


def insert_color_key():
    bold('D1', 'COLOR KEY')
    normal('D2', 'Required')
    normal('D3', 'Recommended')
    # normal('D4', 'Optional')
    # normal('D5', 'Rarely Used')
    required('E2', '')
    recommended('E3', '')
    # optional('E4')
    # rarely_used('E5')


def set_column_widths():
    global maxcol
    ws.column_dimensions['A'].width = 35
    for i in range(maxcol):
        ws.column_dimensions[next_spreadsheet_column('A', i + 1)].width = 25


def create_sheet():
    global wb, ws, row
    # Create a new workbook and select the active worksheet
    wb = Workbook()
    ws = wb.active
    ws.freeze_panes = 'B1'
    row = 1

    insert_color_key()


def add_all_columns_headers():
    global row
    bold('A6', 'ALL COLUMNS')
    row = 7
    bold(f'A{str(row)}', 'Column')
    bold(f'B{str(row)}', 'Type')
    bold(f'C{str(row)}', 'Definition')
    bold(f'D{str(row)}', 'Label')
    bold(f'E{str(row)}', 'Storage Type')
    bold(f'F{str(row)}', 'Storage Type System')

    bold(f'G{str(row - 1)}', 'MISSING VALUE CODES')
    bold(f'G{str(row)}', 'MVC 1')
    bold(f'H{str(row)}', 'MVC 1 Explanation')
    bold(f'I{str(row)}', 'MVC 2')
    bold(f'J{str(row)}', 'MVC 2 Explanation')
    bold(f'K{str(row)}', 'MVC 3')
    bold(f'L{str(row)}', 'MVC 3 Explanation')


def add_numerical_columns_headers():
    global row
    bold(f'A{str(row)}', 'NUMERICAL')
    row += 1
    bold(f'A{str(row)}', 'Column')
    bold(f'B{str(row)}', 'Number Type')
    bold(f'C{str(row)}', 'Standard Unit')
    bold(f'D{str(row)}', 'Custom Unit')
    bold(f'E{str(row)}', 'Custom Unit Description')
    bold(f'F{str(row)}', 'Precision')
    bold(f'G{str(row)}', 'Bounds Minimum')
    bold(f'H{str(row)}', 'Bounds Maximum')


def add_datetime_columns_headers():
    global row
    bold(f'A{str(row)}', 'DATETIME')
    row += 1
    bold(f'A{str(row)}', 'Column')
    bold(f'B{str(row)}', 'Format String')
    bold(f'C{str(row)}', 'Precision')
    bold(f'D{str(row)}', 'Bounds Minimum')
    bold(f'E{str(row)}', 'Bounds Maximum')


def add_categorical_columns_headers():
    global row
    bold(f'A{str(row)}', 'CATEGORICAL')
    row += 1
    bold(f'A{str(row)}', 'Column')
    bold(f'B{str(row)}', 'Code')
    bold(f'C{str(row)}', 'Definition')


def add_column(column, header, values, color=normal):
    global row
    bold(column + str(row), header)
    row += 1
    for value in values:
        color(column + str(row), value)
        row += 1


def add_column_names(names):
    global row
    row = 7
    add_column('A', 'Column', names)


def add_column_types(types):
    global row
    row = 7
    add_column('B', 'Type', types)


def add_column_definitions(definitions):
    global row
    row = 7
    add_column('C', 'Definition', definitions, recommended)


def add_column_labels(labels):
    global row
    row = 7
    add_column('D', 'Label', labels)


def add_storage_types(storage_types):
    global row
    row = 7
    add_column('E', 'Storage Type', storage_types)


def add_storage_type_systems(storage_type_systems):
    global row
    row = 7
    add_column('F', 'Storage Type System', storage_type_systems)


def add_missing_value_codes(attribute_nodes):
    def add_missing_value_code(missing_value_node, column):
        code_node = missing_value_node.find_child('code')
        explanation_node = missing_value_node.find_child('codeExplanation')
        if code_node and code_node.content:
            normal(column + str(row), code_node.content)
            required(next_spreadsheet_column(column) + str(row), explanation_node.content if explanation_node else '')

    global row
    row = 8
    for attribute_node in attribute_nodes:
        missing_value_nodes = attribute_node.find_all_children('missingValueCode')
        i = 0
        for missing_value_node in missing_value_nodes:
            add_missing_value_code(missing_value_node, next_spreadsheet_column('G', 2 * i))
            i += 1
            if i > 2:
                break
        row += 1


def add_numerical_columns(attribute_nodes, eml_node):

    def get_custom_unit_description(eml_node, custom_unit_name):
        # get description, if any, from an additionalMetadata section
        additional_metadata_nodes = eml_node.find_all_children(names.ADDITIONALMETADATA)
        for additional_metadata_node in additional_metadata_nodes:
            metadata_node = additional_metadata_node.find_child(names.METADATA)
            if metadata_node:
                unit_list_node = metadata_node.find_child(names.UNITLIST)
                if unit_list_node:
                    unit_nodes = unit_list_node.find_all_children(names.UNIT)
                    unit_node = None
                    for node in unit_nodes:
                        if node.attribute_value('name') == custom_unit_name:
                            unit_node = node
                            break
                    if unit_node:
                        description_node = unit_node.find_child(names.DESCRIPTION)
                        if description_node:
                            return description_node.content
        return ''

    def add_numerical_column(attribute_node, eml_node):
        global row
        if not is_numerical(attribute_node):
            return
        row += 1
        normal('A' + str(row), attribute_node.find_child('attributeName').content)
        number_type_node = attribute_node.find_descendant('numberType')
        if number_type_node:
            required('B' + str(row), number_type_node.content)

        measurement_scale_node = attribute_node.find_child('measurementScale')
        interval_or_ratio_node = measurement_scale_node.find_child('interval') or measurement_scale_node.find_child('ratio')
        if interval_or_ratio_node:
            unit_node = interval_or_ratio_node.find_child('unit')
            if unit_node:
                standard_unit_node = unit_node.find_child('standardUnit')
                custom_unit_node = unit_node.find_child('customUnit')
                if custom_unit_node:
                    required('D' + str(row), custom_unit_node.content)
                    description = get_custom_unit_description(eml_node, custom_unit_node.content)
                    recommended('E' + str(row), description)
                elif standard_unit_node:
                    required('C' + str(row), standard_unit_node.content)
                else:
                    required('C' + str(row), '')
                    normal('D' + str(row), '')
            else:
                required('C' + str(row), '')
                normal('D' + str(row), '')
            precision_node = interval_or_ratio_node.find_child('precision')
            if precision_node:
                normal('F' + str(row), precision_node.content)
            minimum_node = interval_or_ratio_node.find_descendant('minimum')
            if minimum_node:
                normal('G' + str(row), minimum_node.content)
            maximum_node = interval_or_ratio_node.find_descendant('maximum')
            if maximum_node:
                normal('H' + str(row), maximum_node.content)

    global row
    for attribute_node in attribute_nodes:
        add_numerical_column(attribute_node, eml_node)


def add_datetime_columns(attribute_nodes):
    def add_datetime_column(attribute_node):
        global row
        if not is_datetime(attribute_node):
            return
        row += 1
        normal('A' + str(row), attribute_node.find_child('attributeName').content)
        format_node = attribute_node.find_single_node_by_path(['measurementScale', 'dateTime', 'formatString'])
        required('B' + str(row), '')
        if format_node:
            required('B' + str(row), format_node.content)
        precision_node = attribute_node.find_descendant('precision')
        if precision_node:
            normal('C' + str(row), precision_node.content)
        minimum_node = attribute_node.find_descendant('minimum')
        if minimum_node:
            normal('D' + str(row), minimum_node.content)
        maximum_node = attribute_node.find_descendant('maximum')
        if maximum_node:
            normal('E' + str(row), maximum_node.content)

    global row
    for attribute_node in attribute_nodes:
        add_datetime_column(attribute_node)


def add_categorical_columns(attribute_nodes, header_row):
    global row

    def add_categorical_column(attribute_node, column):
        global row
        if not is_categorical(attribute_node):
            return
        row += 1
        normal('A' + str(row), attribute_node.find_child('attributeName').content)
        code_definition_nodes = []
        attribute_node.find_all_descendants('codeDefinition', code_definition_nodes)
        for code_definition_node in code_definition_nodes:
            bold(f'{column}{header_row}', 'Code')
            bold(f'{next_spreadsheet_column(column)}{header_row}', 'Definition')
            code_node = code_definition_node.find_child('code')
            definition_node = code_definition_node.find_child('definition')
            if code_node:
                normal(f'{column}{row}', code_node.content if code_node else '')
                required(f'{next_spreadsheet_column(column)}{row}', definition_node.content if definition_node else '')
            column = next_spreadsheet_column(column, 2)

    for attribute_node in attribute_nodes:
        column = 'B'
        add_categorical_column(attribute_node, column)


def generate_data_entry_spreadsheet(data_table_node, filename, data_table_name):
    global row
    if not data_table_node:
        return None

    eml_node = load_eml(filename)

    create_sheet()
    add_all_columns_headers()

    if not data_table_node.name:
        return None

    entity_name_node = data_table_node.find_child('entityName')
    start_table(filename, entity_name_node.content if entity_name_node else '')

    attribute_nodes = data_table_node.find_child('attributeList').children
    column_names = []
    column_types = []
    column_definitions = []
    column_labels = []
    storage_types = []
    storage_type_systems = []
    for attribute_node in attribute_nodes:
        attribute_name_node = attribute_node.find_child(names.ATTRIBUTENAME)
        column_names.append(attribute_name_node.content if attribute_name_node else '')
        column_types.append(compose_attribute_mscale(attribute_node))
        column_definitions.append(attribute_node.find_child(names.ATTRIBUTEDEFINITION).content if attribute_node.find_child(names.ATTRIBUTEDEFINITION) else '')
        column_labels.append(attribute_node.find_child(names.ATTRIBUTELABEL).content if attribute_node.find_child(names.ATTRIBUTELABEL) else '')
        storage_type_node = attribute_node.find_child(names.STORAGETYPE)
        if storage_type_node:
            storage_types.append(storage_type_node.content)
            storage_type_systems.append(storage_type_node.attributes.get(names.TYPESYSTEM))
        else:
            storage_types.append('')
            storage_type_systems.append('')

    add_column_names(column_names)
    add_column_types(column_types)
    add_column_definitions(column_definitions)
    add_column_labels(column_labels)
    add_storage_types(storage_types)
    add_storage_type_systems(storage_type_systems)
    add_missing_value_codes(attribute_nodes)

    if 'Numerical' in column_types:
        row += 2
        add_numerical_columns_headers()
        add_numerical_columns(attribute_nodes, eml_node)

    if 'DateTime' in column_types:
        row += 3
        add_datetime_columns_headers()
        add_datetime_columns(attribute_nodes)

    if 'Categorical' in column_types:
        row += 3
        add_categorical_columns_headers()
        add_categorical_columns(attribute_nodes, row)

    set_column_widths()

    import os
    from pathlib import Path
    import webapp.auth.user_data as user_data
    user_folder = user_data.get_user_folder_name()
    sheets_folder = os.path.join(user_folder, 'spreadsheets')
    Path(sheets_folder).mkdir(parents=True, exist_ok=True)
    outfile = os.path.join(sheets_folder, f'{filename}_{data_table_name}.xlsx')
    wb.save(outfile)
    return outfile


####################################################################################################
# Functions for reading metadata from a spreadsheet
####################################################################################################

def get_package_name(sheet):
    return sheet['B1'].value


def get_data_table_name(sheet):
    return sheet['B2'].value


def get_column_values(sheet, column, row=8, length=None):
    values = []
    i = row
    while True:
        cell = sheet[f'{column}{i}']
        i += 1
        if not cell.value and not length:
            break
        values.append(cell.value)
        if length and i - row >= length:
            break
    row = i
    return values


def get_column_names(sheet):
    return get_column_values(sheet, 'A')


def get_column_types(sheet, length=None):
    return get_column_values(sheet, 'B', length=length)


def get_column_definitions(sheet, length=None):
    return get_column_values(sheet, 'C', length=length)


def get_column_labels(sheet, length=None):
    return get_column_values(sheet, 'D', length=length)


def get_storage_types(sheet, length=None):
    return get_column_values(sheet, 'E', length=length)


def get_storage_type_systems(sheet, length=None):
    return get_column_values(sheet, 'F', length=length)


def get_missing_values(sheet, length=None):
    mvc1 = get_column_values(sheet, 'G', length=length)
    mvc_explanations_1 = get_column_values(sheet, 'H', length=length)
    mvc2 = get_column_values(sheet, 'I', length=length)
    mvc_explanations_2 = get_column_values(sheet, 'J', length=length)
    mvc3 = get_column_values(sheet, 'K', length=length)
    mvc_explanations_3 = get_column_values(sheet, 'L', length=length)
    return mvc1, mvc_explanations_1, mvc2, mvc_explanations_2, mvc3, mvc_explanations_3


def get_numerical_variables(sheet, num_numerical_variables):
    global row
    number_types = get_column_values(sheet, 'B', row=row, length=num_numerical_variables)
    standard_units = get_column_values(sheet, 'C', row=row, length=num_numerical_variables)
    custom_units = get_column_values(sheet, 'D', row=row, length=num_numerical_variables)
    custom_unit_descriptions = get_column_values(sheet, 'E', row=row, length=num_numerical_variables)
    precisions = get_column_values(sheet, 'F', row=row, length=num_numerical_variables)
    bounds_minima = get_column_values(sheet, 'G', row=row, length=num_numerical_variables)
    bounds_maxima = get_column_values(sheet, 'H', row=row, length=num_numerical_variables)
    return number_types, standard_units, custom_units, custom_unit_descriptions, precisions, bounds_minima, bounds_maxima


def get_datetime_variables(sheet, num_datetime_variables):
    format_strings = get_column_values(sheet, 'B', row=row, length=num_datetime_variables)
    precisions = get_column_values(sheet, 'C', row=row, length=num_datetime_variables)
    bounds_minima = get_column_values(sheet, 'D', row=row, length=num_datetime_variables)
    bounds_maxima = get_column_values(sheet, 'E', row=row, length=num_datetime_variables)
    return format_strings, precisions, bounds_minima, bounds_maxima


def get_categorical_variables(sheet, num_categorical_variables):
    def get_a_categorical_variable():
        codes = []
        definitions = []
        column = 'B'
        while True:
            cell = sheet[f'{column}{row}']
            if cell.value is None:
                break
            codes.append(cell.value)
            column = next_spreadsheet_column(column)
            cell = sheet[f'{column}{row}']
            definitions.append(cell.value)
            column = next_spreadsheet_column(column)
        return codes, definitions

    global row
    codes_list = []
    definitions_list = []
    for i in range(num_categorical_variables):
        row += 1
        codes, definitions = get_a_categorical_variable()
        codes_list.append(codes)
        definitions_list.append(definitions)
    return codes_list, definitions_list


def read_data_table_sheet(filepath):
    global row

    def set_child_node(child_name, parent_node, content=None):
        child_node = parent_node.find_child(child_name)
        if content:
            if child_node is None:
                child_node = new_child_node(child_name, parent_node, content=content)
            else:
                child_node.content = content
            return child_node
        else:
            try:
                parent_node.remove_child(child_node)
            except ValueError:
                pass

    def set_bounds(domain_node, bounds_min, bounds_max):
        # Bounds
        bounds_node = domain_node.find_child(names.BOUNDS)
        if bounds_min:
            if bounds_node is None:
                bounds_node = domain_node.add_child(names.BOUNDS)
            set_child_node(names.MINIMUM, bounds_node, bounds_min)
        else:
            try:
                domain_node.remove_child(bounds_node)
            except ValueError:
                pass
        if bounds_max:
            bounds_node = domain_node.find_child(names.BOUNDS)
            if bounds_node is None:
                bounds_node = domain_node.add_child(names.BOUNDS)
            set_child_node(names.MAXIMUM, bounds_node, bounds_max)
        elif not bounds_min:
            try:
                domain_node.remove_child(bounds_node)
            except ValueError:
                pass

    def set_missing_value(attribute_node, mvc, mvc_explanation):
        # TODO - if no mvc, we need to remove the missing value code node if it exists
        if mvc:
            missing_value_code_node = attribute_node.find_child(names.MISSINGVALUECODE)
            if missing_value_code_node is None:
                missing_value_code_node = new_child_node(names.MISSINGVALUECODE, attribute_node)
            code_node = missing_value_code_node.find_child(names.CODE)
            if code_node is None:
                code_node = new_child_node(names.CODE, missing_value_code_node, content=mvc)
            code_explanation_node = missing_value_code_node.find_child(names.CODEEXPLANATION)
            if code_explanation_node is None:
                code_explanation_node = new_child_node(names.CODEEXPLANATION, missing_value_code_node, content=mvc_explanation)

    def set_numerical_variable(attribute_node, number_type, standard_unit, custom_unit, custom_unit_description, precision, bounds_min, bounds_max):
        if not is_numerical(attribute_node):
            return
        ir_node = interval_or_ratio_node(attribute_node)
        numeric_domain_node = ir_node.find_child(names.NUMERICDOMAIN)
        if numeric_domain_node is None:
            numeric_domain_node = attribute_node.add_child(names.NUMERICDOMAIN)

        # Number type
        set_child_node(names.NUMBERTYPE, numeric_domain_node, number_type)

        # Precision
        set_child_node(names.PRECISION, ir_node, precision)

        # Bounds
        set_bounds(numeric_domain_node, bounds_min, bounds_max)

        # Units
        unit_node = attribute_node.find_descendant(names.UNIT)
        if unit_node is None:
            unit_node = new_child_node(names.UNIT, attribute_node)
        standard_unit_node = set_child_node(names.STANDARDUNIT, unit_node, standard_unit)
        custom_unit_node = set_child_node(names.CUSTOMUNIT, unit_node, custom_unit)
        if custom_unit and not standard_unit:
            if custom_unit_description:
                custom_unit_description_node = unit_node.find_child(names.DESCRIPTION)
                # TODO - handle custom unit description in additional metadata
                # if custom_unit_description_node is None:
                #     custom_unit_description_node = new_child_node(names.DESCRIPTION, unit_node, custom_unit_description)

    def set_datetime_variable(attribute_node, format_string, precision, bounds_min, bounds_max):
        if not is_datetime(attribute_node):
            return
        datetime_node = attribute_node.find_descendant(names.DATETIME)

        # Format string
        set_child_node(names.FORMAT, datetime_node, format_string)

        # Precision
        set_child_node(names.PRECISION, datetime_node, precision)

        # Bounds
        date_time_domain_node = datetime_node.find_child(names.DATETIMEDOMAIN)
        set_bounds(date_time_domain_node, bounds_min, bounds_max)

    def set_categorical_variable(attribute_node, codes, definitions):
        if not is_categorical(attribute_node):
            return
        # Remove all codeDefinition children of enumeratedDomain
        # We'll just remove the enumeratedDomain node and recreate it
        non_numeric_domain_node = attribute_node.find_descendant(names.NONNUMERICDOMAIN)
        enumerated_domain_node = non_numeric_domain_node.find_child(names.ENUMERATEDDOMAIN)
        if enumerated_domain_node is not None:
            non_numeric_domain_node.remove_child(enumerated_domain_node)
        enumerated_domain_node = new_child_node(names.ENUMERATEDDOMAIN, non_numeric_domain_node)
        # Create the codeDefinition children
        for code, definition in zip(codes, definitions):
            code_definition_node = new_child_node(names.CODEDEFINITION, enumerated_domain_node)
            code_node = new_child_node(names.CODE, code_definition_node, content=code)
            definition_node = new_child_node(names.DEFINITION, code_definition_node, content=definition)

    current_document = current_user.get_filename()

    wb = None
    try:
        wb = load_workbook(filepath)
    except Exception as e:
        print(e)
        raise
    sheet = wb['Sheet']

    package_name = get_package_name(sheet)
    data_table_name = get_data_table_name(sheet)
    column_names = get_column_names(sheet)
    length = len(column_names)
    row = length + 8
    column_types = get_column_types(sheet, length=length)
    column_definitions = get_column_definitions(sheet, length=length)
    column_labels = get_column_labels(sheet, length=length)
    mvc1, mvc_explanations_1, mvc2, mvc_explanations_2, mvc3, mvc_explanations_3 = get_missing_values(sheet, length=length)

    num_numerical_variables = column_types.count('Numerical')
    row += 4
    number_types, standard_units, custom_units, custom_unit_descriptions, num_precisions, num_bounds_minima, num_bounds_maxima = \
        get_numerical_variables(sheet, num_numerical_variables=num_numerical_variables)

    num_datetime_variables = column_types.count('DateTime')
    row += num_numerical_variables + 4
    format_strings, dt_precisions, dt_bounds_minima, dt_bounds_maxima = get_datetime_variables(sheet, num_datetime_variables=num_datetime_variables)

    num_categorical_variables = column_types.count('Categorical')
    row += 4
    # TODO - guard against an empty categorical code
    codes, code_definitions = get_categorical_variables(sheet, num_categorical_variables=num_categorical_variables)

    eml_node = load_eml(current_document)
    data_table_nodes = []
    eml_node.find_all_descendants(names.DATATABLE, data_table_nodes)
    for data_table_node in data_table_nodes:
        entity_name_node =  data_table_node.find_child('entityName')
        if entity_name_node and entity_name_node.content == data_table_name:
            break
        else:
            data_table_node = None
    if data_table_node is None:
        msg = f'No data table with name {data_table_name} was found in {current_document}'
        raise exceptions.DataTableNameNotFound(msg)

    # Check column names
    attribute_list_node = data_table_node.find_child(names.ATTRIBUTELIST)
    attribute_nodes = attribute_list_node.children
    for i, attribute_node in enumerate(attribute_nodes):
        attribute_name_node = attribute_node.find_child(names.ATTRIBUTENAME)
        if attribute_name_node.content != column_names[i]:
            msg = f'Column name {attribute_name_node.content} found where column name {column_names[i]} was expected. ' \
                    f'Changing column names needs to be done in the ezEML editor, not in a spreadsheet.'
            raise exceptions.DataTableNameNotFound(msg)

    # Check column types
    for i, attribute_node in enumerate(attribute_nodes):
        if compose_attribute_mscale(attribute_node) != column_types[i]:
            # TODO: error handling
            return None

    # Set column definitions
    for i, attribute_node in enumerate(attribute_nodes):
        set_child_node(names.ATTRIBUTEDEFINITION, attribute_node, column_definitions[i])

    # Set column labels
    for i, attribute_node in enumerate(attribute_nodes):
        set_child_node(names.ATTRIBUTELABEL, attribute_node, column_labels[i])

    # Set missing value codes
    # mvc1, mvc_explanations_1, mvc2, mvc_explanations_2, mvc3, mvc_explanations_3 = get_missing_values(sheet, length=length)
    for i, attribute_node in enumerate(attribute_nodes):
        set_missing_value(attribute_node, mvc1[i], mvc_explanations_1[i])
        set_missing_value(attribute_node, mvc2[i], mvc_explanations_2[i])
        set_missing_value(attribute_node, mvc3[i], mvc_explanations_3[i])

    # Handle numerical variables
    i = 0
    for attribute_node in attribute_nodes:
        if not is_numerical(attribute_node):
            continue
        set_numerical_variable(attribute_node, number_types[i], standard_units[i], custom_units[i], custom_unit_descriptions[i],
                                   num_precisions[i], num_bounds_minima[i], num_bounds_maxima[i])
        i += 1

    # Handle datetime variables
    i = 0
    for attribute_node in attribute_nodes:
        if not is_datetime(attribute_node):
            continue
        set_datetime_variable(attribute_node, format_strings[i], dt_precisions[i], dt_bounds_minima[i], dt_bounds_maxima[i])
        i += 1

    # Handle categorical variables
    i = 0
    for attribute_node in attribute_nodes:
        if not is_categorical(attribute_node):
            continue
        set_categorical_variable(attribute_node, codes[i], code_definitions[i])
        i += 1

    save_eml(current_document, eml_node)

    return
