#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: log_usage.py

:Synopsis:
    Write usage info to usage log

:Author:
    ide

:Created:
    2022-04-04
"""

from datetime import date, datetime
from flask_login import current_user

from webapp.home.import_data import convert_file_size


USAGE_LOG_FILE = 'usage.log'


def handle_special_cases(action, args):
    if action == actions['CHECK_XML']:
        page, response, *_ = args
        if response == 'Valid XML':
            return page, 'valid'
        else:
            return page, 'invalid'
    elif action == actions['GET_ASSOCIATED_DATA_FILES']:
        total_size, *_ = args
        kb, mb, gb = convert_file_size(total_size)
        return (str(round(mb)),)
    elif action == actions['HELP']:
        page, *_ = args
        if page.startswith('__help__'):
            page = page.replace('__help__', '')
        if page.endswith('_btn'):
            page = page[:-4]
        return (page,)
    elif action == actions['IMPORT_EML_XML_FILE']:
        filename, has_errors, has_complex_text, *_ = args
        error_flag = 'has errors' if has_errors else 'no errors'
        complex_text_flag = 'complex text' if has_complex_text else 'simple text'
        return filename, error_flag, complex_text_flag
    else:
        return args


def log_usage(action, *args):
    args = handle_special_cases(action, args)
    date = datetime.now().date().strftime('%Y-%m-%d')
    time = datetime.now().time().strftime('%H:%M:%S')
    if current_user and hasattr(current_user, 'get_username'):
        username = current_user.get_username()
        current_document = current_user.get_filename()
        if not current_document:
            current_document = ''
    else:
        username = ''
        current_document = ''
    NUM_DATA_COLS = 5
    data_cols = []
    for i in range(NUM_DATA_COLS):
        data_cols.append('')
    i = 0
    if args:
        for arg in args:
            data_cols[i] = str(arg)
            i += 1
    with open(USAGE_LOG_FILE, 'a') as log:
        data = ','.join(data_cols)
        line = f"{date},{time},{username},{action},{current_document},{data}\n"
        log.write(line)


actions = {
    'CHECK_METADATA': 'Check Metadata',
    'CHECK_XML': 'Check XML',
    'CLONE_COLUMN_PROPERTIES': 'Clone Column Properties',
    'CLOSE_DOCUMENT': 'Close',
    'DELETE_DOCUMENT': 'Delete',
    'DOWNLOAD_EML_FILE': 'Download EML File',
    'EXPORT_EZEML_DATA_PACKAGE': 'Export ezEML Data Package',
    'FETCH_FROM_EDI': 'Fetch from EDI',
    'FILL_TAXONOMIC_HIERARCHY': 'Fill Taxonomic Hierarchy',
    'GET_ASSOCIATED_DATA_FILES': 'Get Associated Data Files',
    'HELP': 'Help',
    'IMPORT_EML_XML_FILE': 'Import EML File (XML)',
    'IMPORT_EZEML_DATA_PACKAGE': 'Import ezEML Data Package',
    'IMPORT_FUNDING_AWARDS': 'Import Funding Awards',
    'IMPORT_GEOGRAPHIC_COVERAGE': 'Import Geographic Coverage',
    'IMPORT_PROJECT': 'Import Project',
    'IMPORT_RELATED_PROJECTS': 'Import Related Projects',
    'IMPORT_RESPONSIBLE_PARTIES': 'Import Responsible Parties',
    'IMPORT_TAXONOMIC_COVERAGE': 'Import Taxonomic Coverage',
    'LOAD_DATA_TABLE': 'Load Data Table',
    'LOAD_GEOGRAPHIC_COVERAGE': 'Load Geographic Coverage',
    'LOAD_OTHER_ENTITY': 'Load Other Entity',
    'LOGIN': 'Login',
    'LOGOUT': 'Logout',
    'NEW_DOCUMENT': 'New',
    'NEW_FROM_TEMPLATE': 'New from Template',
    'OPEN_DOCUMENT': 'Open',
    'RE_UPLOAD_DATA_TABLE': 'Re-upload Data Table',
    'RE_UPLOAD_OTHER_ENTITY': 'Re-upload Other Entity',
    'SAVE_AS_DOCUMENT': 'Save As',
    'SAVE_DOCUMENT': 'Save',
    'SEND_TO_EDI': 'Send to EDI',
    'SEND_TO_COLLEAGUE': 'Send to Colleague',
    'USER_GUIDE': 'User Guide'
}
