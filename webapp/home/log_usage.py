"""
    Write usage info to usage log
"""

from datetime import date, datetime
from flask_login import current_user

from webapp.home.fetch_data import convert_file_size
from webapp.home.home_utils import log_info
from webapp.home.utils.node_utils import get_unit_text
from metapype.eml import names


ANNOTATIONS_LOG_FILE = 'qudt_annotations.log'
USAGE_LOG_FILE = 'usage.log'


actions = {
    'ACCEPT_INVITATION': 'Accept Invitation',
    'CHECK_DATA_TABLES': 'Check Data Tables',
    'CHECK_METADATA': 'Check Metadata',
    'CHECK_XML': 'Check XML',
    'CLONE_COLUMN_PROPERTIES': 'Clone Column Properties',
    'CLOSE_DOCUMENT': 'Close',
    'COLLABORATE': 'Collaborate',
    'COLLABORATION_BACKUPS': 'Collaboration Backups',
    'DELETE_DOCUMENT': 'Delete',
    'DOWNLOAD_COLUMN_PROPERTIES_SPREADSHEET': 'Download Column Properties Spreadsheet',
    'DOWNLOAD_EML_FILE': 'Download EML File',
    'ENABLE_EDI_CURATION': 'Enable EDI Curation',
    'END_COLLABORATION': 'End Collaboration',
    'END_GROUP_COLLABORATION': 'End Group Collaboration',
    'EXPLORE_DATA_TABLES': 'Explore Data Tables',
    'EXPORT_EZEML_DATA_PACKAGE': 'Export ezEML Data Package',
    'FETCH_FROM_EDI': 'Fetch from EDI',
    'FETCH_PROVENANCE_INFO': 'Fetch Provenance Info from EDI',
    'FILL_TAXONOMIC_HIERARCHY': 'Fill Taxonomic Hierarchy',
    'GET_ASSOCIATED_DATA_FILES': 'Get Associated Data Files',
    'HELP': 'Help',
    'IMPORT_EML_XML_FILE': 'Import EML File (XML)',
    'IMPORT_EZEML_DATA_PACKAGE': 'Import ezEML Data Package',
    'IMPORT_FUNDING_AWARDS': 'Import Funding Awards',
    'IMPORT_GEOGRAPHIC_COVERAGE': 'Import Geographic Coverage',
    'IMPORT_KEYWORDS': 'Import Keywords',
    'IMPORT_PROJECT': 'Import Project',
    'IMPORT_RELATED_PROJECTS': 'Import Related Projects',
    'IMPORT_RESPONSIBLE_PARTIES': 'Import Responsible Parties',
    'IMPORT_TAXONOMIC_COVERAGE': 'Import Taxonomic Coverage',
    'INVITE_COLLABORATOR': 'Invite a Collaborator',
    'LOAD_DATA_TABLE': 'Load Data Table',
    'LOAD_GEOGRAPHIC_COVERAGE': 'Load Geographic Coverage',
    'LOAD_OTHER_ENTITY': 'Load Other Entity',
    'LOAD_RESPONSIBLE_PARTIES': 'Load Responsible Parties',
    'LOAD_TAXONOMIC_COVERAGE': 'Load Taxonomic Coverage',
    'LOGIN': 'Login',
    'LOGOUT': 'Logout',
    'MANAGE_DATA_USAGE': 'Manage Data Usage',
    'MANAGE_PACKAGES': 'Manage Packages',
    'NEW_DOCUMENT': 'New',
    'NEW_FROM_TEMPLATE': 'New from Template',
    'OPEN_BY_COLLABORATOR': 'Open by Collaborator',
    'OPEN_DOCUMENT': 'Open',
    'QUDT_ACCEPT': 'Accept QUDT Annotation',
    'QUDT_ACCEPT_ALL': 'Accept All QUDT Annotations',
    'QUDT_REJECT': 'Reject QUDT Annotation',
    'QUDT_REJECT_ALL': 'Reject All QUDT Annotations',
    'RE_UPLOAD_DATA_TABLE': 'Re-upload Data Table',
    'RE_UPLOAD_OTHER_ENTITY': 'Re-upload Other Entity',
    'RENAME_PACKAGE' : 'Rename Package',
    'SAVE_AS_DOCUMENT': 'Save As',
    'SAVE_DOCUMENT': 'Save',
    'SEND_TO_EDI': 'Send to EDI',
    'SEND_TO_COLLEAGUE': 'Send to Colleague',
    'SETTINGS': 'Settings',
    'UPLOAD_COLUMN_PROPERTIES_SPREADSHEET': 'Upload Column Properties Spreadsheet',
    'USER_GUIDE': 'User Guide',
    'VALIDATE_EML': 'Validate EML'
}

annotations_actions = {
    'ACCEPT': 'ACCEPT',
    'ADD_TO_EML': 'ADD_TO_EML',
    'REJECT': 'REJECT',
    'REMOVE_FROM_EML': 'REMOVE_FROM_EML'
}


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


def preamble():
    date = datetime.now().date().strftime('%Y-%m-%d')
    time = datetime.now().time().strftime('%H:%M:%S')
    if current_user and hasattr(current_user, 'get_username'):
        username = current_user.get_username()
        current_document = current_user.get_filename() or ''
    else:
        username = ''
        current_document = ''
    return date, time, username, current_document


def log_usage(action, *args):
    args = handle_special_cases(action, args)
    date, time, username, current_document = preamble()
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
        line = f"{date},{time},{username},{action},{current_document},{data}"
        log.write(f"{line}\n")
        log_info(line)


def log_qudt_annotations_usage(action, attribute_node):
    try:
        date, time, username, document_name = preamble()
        data_table_node = attribute_node.parent.parent
        entity_name_node = data_table_node.find_child(names.ENTITYNAME)
        data_table_name = entity_name_node.content
        attribute_name_node = attribute_node.find_child(names.ATTRIBUTENAME)
        column_name = attribute_name_node.content
        unit_as_entered = get_unit_text(attribute_node)
        value_uri_node = attribute_node.find_descendant(names.VALUEURI)
        qudt_label = value_uri_node.attribute_value('label')
        qudt_uri = value_uri_node.content or ''
        qudt_code = qudt_uri.split('/')[-1]
        with open(ANNOTATIONS_LOG_FILE, 'a') as log:
            line = f"{date},{time},{username},{document_name},{action},{data_table_name},{column_name},{unit_as_entered},{qudt_label},{qudt_code}"
            log.write(f"{line}\n")
            log_info(line)
    except Exception as e:
        pass



