"""
Routes for the home blueprint, and functions for initializing a session or a request, etc.
"""

import ast
import collections

import urllib.parse

from datetime import date, datetime
import glob
import html
import math
import os
import os.path
from pathlib import Path
import pickle
import re
import requests
from shutil import copyfile, move, rmtree
import subprocess
import time
from urllib.parse import urlencode, urlparse, quote, unquote
from zipfile import ZipFile

from flask import (
    Blueprint, flash, render_template, redirect, request, url_for,
    session, jsonify, send_file, g
)

from flask_login import (
    current_user, login_required
)

from flask import Flask, current_app

from markupsafe import Markup

from webapp.home.utils.file_utils import sanitize_filename
from webapp.home.utils.security import validate_download_url, validate_user_data_path, validate_filename

import webapp.home.utils.node_utils
import webapp.mimemail as mimemail

from webapp.config import Config
from webapp.home.home_utils import (
    log_error, log_info, log_available_memory, url_without_query_string, url_without_ui_element_id_query_string
)
import webapp.home.texttype_node_processing as texttype_node_processing
from webapp.home.log_usage import annotations_actions, log_qudt_annotations_usage
import webapp.home.utils.qudt_annotations as qudt_annotations

import csv

from webapp.home.exceptions import (
    ezEMLError,
    AuthTokenExpired,
    DataTableError,
    DeprecatedCodeError,
    MissingFileError,
    Unauthorized,
    UnicodeDecodeErrorInternal
)

from webapp.home.forms import ( 
    EDIForm, CreateEMLForm, ImportPackageForm,
    OpenEMLDocumentForm, ValidateEMLFileForm, SaveAsForm, RenamePackageForm,
    LoadMetadataForm, LoadDataForm, LoadOtherEntityForm,
    ImportEMLForm, ImportEMLItemsForm, ImportPartiesFromTemplateForm,
    ImportItemsForm, ImportItemsSortableForm, ImportSingleItemForm,
    SubmitToEDIForm, SendToColleagueForm, EDIForm,
    SelectUserForm, SelectDataFileForm, SelectEMLFileForm,
    SettingsForm, OpenTemplateForm, SaveAsTemplateForm, DeleteTemplateForm
)

import webapp.utils as utils

from webapp.views.data_tables.load_data import (
    load_other_entity, get_md5_hash, data_filename_is_unique
)
from webapp.home.import_package import (
    copy_ezeml_package, upload_ezeml_package, import_ezeml_package, cull_uploads
)
from webapp.home.import_xml import (
    save_xml_file_in_temp_folder, parse_xml_file, determine_package_name_for_copy
)
from webapp.home.log_usage import (
    actions,
    log_usage,
)
from webapp.home.manage_packages import get_data_packages, get_data_usage

from webapp.home.home_utils import RELEASE_NUMBER, get_check_metadata_status, url_without_query_string
from webapp.home.utils.hidden_buttons import is_hidden_button, handle_hidden_buttons, non_saving_hidden_buttons_decorator

from webapp.home.utils.node_utils import remove_child, new_child_node
from webapp.home.utils.hidden_buttons import is_hidden_button, handle_hidden_buttons, check_val_for_hidden_buttons
from webapp.home.utils.load_and_save import get_pathname, load_eml, load_template, save_old_to_new, \
    strip_elements_added_by_pasta, save_eml, fixup_distribution_urls, \
    package_contains_elements_unhandled_by_ezeml, save_both_formats, create_eml, add_imported_from_xml_metadata, \
    get_imported_from_xml_metadata, clear_taxonomy_imported_from_xml_flag
from webapp.home.utils.import_nodes import import_responsible_parties, import_keyword_nodes, import_coverage_nodes, \
    import_funding_award_nodes, compose_funding_award_label, compose_project_label, import_project_node, \
    import_related_project_nodes, compose_rp_label, compose_simple_label, compose_individual_name_label
from webapp.home.utils.lists import list_data_packages, list_templates, list_files_in_dir, template_display_name, \
    compose_full_gc_label, truncate_middle, compose_taxonomic_label, UP_ARROW, DOWN_ARROW
from webapp.home.utils.create_nodes import add_fetched_from_edi_metadata, get_fetched_from_edi_metadata
from webapp.home.utils.template_management import (
    init_template_management,
    template_folders_for_user,
    templates_for_user,
    check_overwrite_user_data,
    copy_template_to_user_data,
    copy_document_to_template_folder,
    delete_template_file
)

import webapp.home.check_data_table_contents as check_data_table_contents
from webapp.home.check_data_table_contents import format_date_time_formats_list
from webapp.home.check_metadata import check_eml, is_valid_uuid
from webapp.home.forms import init_form_md5
from webapp.home.standard_units import init_standard_units
from webapp.views.collaborations.collaborations import (
    init_db,
    close_package,
    release_acquired_lock,
    create_auto_collaboration
)
import webapp.views.collaborations.collaborations as collaborations
from webapp.buttons import *
from webapp.pages import *

from metapype.eml import names
from metapype.model.node import Node, Shift
from werkzeug.utils import secure_filename

from webapp.home.fetch_data import (
    import_data, get_pasta_identifiers, get_revisions_list, get_metadata_revision_from_pasta,
    get_data_entity_sizes, convert_file_size
)

import webapp.auth.user_data as user_data
from webapp.home.texttype_node_processing import (
    check_xml_validity,
    model_has_complex_texttypes
)
import emlvp.unicode_inspector as ui
import emlvp.validator as validator
from emlvp.validator import Validator
from emlvp.exceptions import ValidationError, ParseError, ParserError, XIncludeError, XMLSchemaParseError, \
    XMLSyntaxError
from emlvp.parser import Parser
from lxml import etree as etree

app = Flask(__name__)

import daiquiri
logger = daiquiri.getLogger(f'home: {__name__}')

home_bp = Blueprint('home', __name__, template_folder='templates')
help_dict = {}
keywords = {}

badge_data = {}

AUTH_TOKEN_FLASH_MSG = 'Authorization to access data was denied. This can be caused by a login timeout. Please log out, log back in, and try again.'


@home_bp.before_app_request
def release_to_owner_link():
    """
    If the current user is an EDI curator and has control of a package under curation, we provide a link to release
    the package back to the owner.
    """
    if current_user and hasattr(current_user, 'get_user_login'):
        user_login = current_user.get_user_login()
        session['release_to_owner_link'] = collaborations.release_to_owner(user_login)
    else:
        session['release_to_owner_link'] = None


@home_bp.route('/release_to_owner/', methods=['GET','POST'])
@home_bp.route('/release_to_owner/<filename>', methods=['GET','POST'])
def release_to_owner(filename=None):
    """
    Release a package back to the owner.
    """
    if current_user and hasattr(current_user, 'get_user_login'):
        user_login = current_user.get_user_login()
        active_package_id = collaborations.release_to_owner(user_login)
        if active_package_id:
            return redirect(url_for(PAGE_RELEASE_GROUP_LOCK, package_id=active_package_id))
    return redirect(url_for('home.index'))


@home_bp.before_app_request
def log_request():
    """
    Log the incoming request.
    """
    if not Config.LOG_REQUESTS:
        return

    url = request.url
    if '/static/' in url or 'youtube.png' in url or 'favicon.ico' in url or 'logo.png' in url:
        return

    referrer = request.referrer
    if referrer is not None: # We don't want to log the every-five-minute pings checking server status
        log_info(f'**** INCOMING REQUEST: {url} [{request.method}]   REFERRER: {referrer}')
        log_available_memory()


@home_bp.after_app_request
def log_response(response):
    """
    Log the outgoing response.
    """
    if not Config.LOG_RESPONSES:
        return response

    url = request.url
    if '/static/' in url or 'youtube.png' in url or 'favicon.ico' in url or 'logo.png' in url:
        return response

    if response:
        log_info(f'**** OUTGOING RESPONSE: {request.remote_addr}  [{request.method}]  {request.full_path}  {response.status}')
    else:
        log_info('**** OUTGOING RESPONSE: None')
    log_available_memory()
    return response


def log_node_lineage(prefix, node):
    # For debugging use
    if node is None:
        return
    from webapp.home.home_utils import log_info
    log_info(f'{prefix} {node.name} {node.id} with python id {id(Node.get_node_instance(node.id))}')
    log_node_lineage(f'  ...parent', node.parent)


def check_node_identity(node):
    # For debugging use
    from webapp.home.home_utils import log_info
    node_id = node.id
    if node_id:
        node_in_store = Node.get_node_instance(node_id)
        if node_in_store is not node:
            log_node_lineage(f'node_in_store', node_in_store)
            log_node_lineage(f'node', node)
            log_info(f'***** Node {node.name} {node.id} with python id {id(node)} is not the same as '
                             f'node_in_store {node_in_store.name} {node_in_store.id} with python id {id(node_in_store)}')
            return False
            # raise ValueError(f'Node {node.name} {node.id} with python id {id(node)} is not the same as '
            #                  f'node_in_store {node_in_store.name} {node_in_store.id} with python id {id(node_in_store)}')


def check_tree_identity(node):
    # For debugging use
    # The code that handles the Metapype store uses the actual identity of the node objects. E.g., remove_child expects
    #  the actual node object, not a copy of it -- i.e., not just a node with the same id. This function checks that
    #  the node objects in the tree are the same as the corresponding node objects in the Metapype store. When that
    #  is not the case, very subtle bugs can occur. A case in point was that when a package was fetched from EDI, the
    #  keyword sets were duplicated -- but only if the data objects were also fetched!
    if not check_node_identity(node):
        return
    for child in node.children:
        if not check_tree_identity(child):
            return


def url_of_interest():
    """
    We want to log Metapype store info only when processing the URLs that are of interest to us.
    For example, if the user is retrieving the EDI logo, we don't want to log Metapype store info.
    This function returns True iff the current URL is of interest.
    """
    if Config.MEM_FILTER_URLS_TO_CLEAR_METAPYPE_STORE:
        parsed_url = urlparse(request.base_url)
        url_prefix = f"{parsed_url.scheme}://{parsed_url.netloc}/eml/"
        if url_prefix not in request.url:
            # This filters out logging for urls that do things like retrieving the EDI logo
            return False
        if parsed_url.path in ['/eml/', '/eml/auth/login']:
            # We suppress logging for these two URLs because they are called every 5 minutes by uptime monitor
            return False
    return True


@home_bp.route('/test_page')
def test_page():
    """
    A basically empty page for testing purposes.
    """

    return render_template('test_page.html')


@home_bp.before_app_request
def post_debug_info_to_session():
    """
    This function is called before every request. It stores some debug info in the session so it can be accessed
    by templates. This is useful for debugging.
    """
    try:
        user_login = current_user.get_user_login()
        if user_login:
            active_package = collaborations.get_active_package(user_login)
            if active_package:
                session["active_package_id"] = active_package.package_id
            else:
                session["active_package_id"] = None
    except Exception as e:
        session["active_package_id"] = None


@home_bp.before_app_request
def check_metapype_store():
    """
    This function is called before every request. It checks the size of the Metapype store and logs it if it is
    greater than zero, then clears it. This is useful for debugging.
    """
    if not Config.MEM_CLEAR_METAPYPE_STORE_AFTER_EACH_REQUEST:
        return
    if url_of_interest():
        store_len = len(Node.store)
        if store_len > 0:
            Node.store.clear()
            log_info(f'********************************************************')
            log_info(f'*** check_metapype_store ***: store_len={store_len}     {request.url}')
            log_info(f'********************************************************')


@home_bp.after_app_request
def clear_metapype_store(response):
    """
    This function is called after every request. It clears the Metapype store. We ensure that the store doesn't
    accumulate nodes from previous requests. It is populated anew for each request when the EML model is loaded
    via load_eml().
    """
    if not Config.MEM_CLEAR_METAPYPE_STORE_AFTER_EACH_REQUEST:
        return response
    if url_of_interest():
        store_len = len(Node.store)
        if store_len > 0:
            if Config.MEM_LOG_METAPYPE_STORE_ACTIONS:
                log_info(f'*** clear_metapype_store ***: store_len={store_len}     {request.url}')
            Node.store.clear()
    return response


def non_breaking(_str):
    """ Replace spaces with non-breaking spaces. """
    return _str.replace(' ', html.unescape('&nbsp;'))


def breaking(_str):
    """ Replace non-breaking spaces with spaces. """
    return _str.replace(html.unescape('&nbsp;'), ' ')


def debug_msg(msg):
    if Config.LOG_DEBUG:
        app = Flask(__name__)
        with app.app_context():
            current_app.logger.info(msg)


def debug_None(x, msg):
    if x is None:
        if Config.LOG_DEBUG:
            app = Flask(__name__)
            with app.app_context():
                current_app.logger.info(msg)


def reload_metadata():
    """ Reload the metadata to get the check_metadata badge status updated.
        NOTE: This updates eml_node, so callers should capture the return value.
    """
    if not current_user.is_authenticated:
        return None, None
    current_document = current_user.get_filename()
    if not current_document:
        # if we've just deleted the current document, it won't exist
        return None, None
    # Call load_eml here to get the check_metadata status set correctly
    eml_node = load_eml(filename=current_document)
    return current_document, eml_node


@home_bp.route('/sleep/<seconds>', methods=['GET'])
def sleep(seconds:str=None):
    """ Sleep for the specified number of seconds. This is used for testing. """
    try:
        seconds = int(seconds)
    except Exception as e:
        seconds = 1
    time.sleep(seconds)
    return redirect(url_for(PAGE_INDEX))


# Endpoint for AJAX calls to validate XML
@home_bp.route('/check_xml/<xml>/<parent_name>', methods=['GET'])
def check_xml(xml:str=None, parent_name:str=None):
    """ Check the validity of the XML and return the result. This is called by AJAX. """
    response = check_xml_validity(xml, parent_name)
    log_usage(actions['CHECK_XML'], parent_name, response)
    response = jsonify({"response": response})
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response


# Endpoint for AJAX calls to log help usage
@home_bp.route('/log_help_usage/<help_id>', methods=['GET'])
def log_help_usage(help_id:str=None):
    """
    Log the usage of a help page. This is called by AJAX. The macro help_script calls macro log_help_usage,
     which passes the ID of the help page to this endpoint. This lets us know which help pages are being used. """
    log_usage(actions['HELP'], help_id)
    response = jsonify({"response": 'OK'})
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response


# Endpoint for AJAX calls to log User Guide usage
@home_bp.route('/log_user_guide_usage/<title>', methods=['GET'])
def log_user_guide_usage(title:str=None):
    """
    Log the usage of the User Guide. The user guide page has links to the various chapters. Those links include
    AJAX calls to the this endpoint, which logs the usage of those links so we know which chapters are being used.
    """
    log_usage(actions['USER_GUIDE'], title)
    response = jsonify({"response": 'OK'})
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response


# Endpoint for AJAX calls to log login usage
@home_bp.route('/log_login_usage/<login_type>', methods=['GET'])
def log_login_usage(login_type:str=None):
    """
    Log the usage of the login. The login page has links to the various login options (Google, ORCID, etc.).
    Those links include AJAX calls to the this endpoint, which logs the usage of those links so we know which login
    options are being used.
    """
    log_usage(actions['LOGIN'], login_type)
    response = jsonify({"response": 'OK'})
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response


# Endpoint for a REST Service to get a list of a data table's columns and their variable types.
@home_bp.route('/get_data_table_columns/', methods=['GET','POST'])
def get_data_table_columns():
    """
    Endpoint for a REST Service to get a list of a data table's columns and their variable types.

    Note that this returns the names as they are defined in the metadata, not as they are defined in the table.
    This is a REST service rather than a direct function call because we want to support eventually making
     Check Data Table a separate, standalone service.
    """
    eml_file_url = request.headers.get('eml_file_url')
    data_table_name = request.headers.get('data_table_name')
    data_table_node = check_data_table_contents.find_data_table_node(eml_file_url, data_table_name)
    columns = check_data_table_contents.get_data_table_columns(data_table_node)
    response = jsonify({"columns": columns})
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response


# Endpoint for REST Service to check a data table's CSV file.
@home_bp.route('/check_data_table/', methods=['POST'])
def check_data_table():
    """
    Endpoint for REST Service to check a data table's CSV file.

    This is a REST service rather than a direct function call because we want to support eventually making
     Check Data Table a separate, standalone service.
    """
    eml_file_url = request.headers.get('eml_file_url')
    csv_file_url = request.headers.get('csv_file_url')
    data_table_name = request.headers.get('data_table_name')
    column_names = request.headers.get('column_names').split(',')
    # return profile_and_save("check_data_table", check_data_table_contents.check_data_table(eml_file_url, csv_file_url, data_table_name, column_names))
    return check_data_table_contents.check_data_table(eml_file_url, csv_file_url, data_table_name, column_names)


@home_bp.route('/data_table_fetch/<document_name>/<csv_filename>/<path:url>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def data_table_fetch(document_name:str=None, csv_filename:str=None, url:str=None):
    """Handle fetching a missing data table on the Check Data Tables page."""

    # We want to fetch the data table from the URL and save it in the user-data directory of the package owner.
    uploads_dir = user_data.get_user_uploads_folder_name()
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir)
    package_uploads_dir = os.path.join(uploads_dir, document_name)
    if not os.path.exists(package_uploads_dir):
        os.makedirs(package_uploads_dir)

    if not csv_filename:
        flash("No CSV filename provided to fetch data table.", "error")
        return redirect(url_for(PAGE_CHECK_DATA_TABLES))

    if not url:
        flash("No URL provided to fetch data table.", "error")
        return redirect(url_for(PAGE_CHECK_DATA_TABLES))

    save_path = os.path.join(package_uploads_dir, csv_filename)

    # Send HTTP GET request to the URL to fetch the data table
    url = validate_download_url(url)
    if url is None:
        redirect(url_for(PAGE_CHECK_DATA_TABLES))
    response = requests.get(url, stream=True)
    if response.status_code != 200:
        flash(f'Unable to fetch data table "{csv_filename}". Reason: {response.reason}', "error")
    else:
        # Save the file in chunks to avoid memory issues with large files
        with open(save_path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        flash('Data table fetched successfully.', 'success')

    return redirect(url_for(PAGE_CHECK_DATA_TABLES))


@home_bp.route('/data_table_errors/<data_table_name>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def data_table_errors(data_table_name:str=None):
    """Handle the Check data table link or Show errors link for a table on the Check Data Tables page."""

    current_document = user_data.get_active_document()
    if not current_document:
        raise FileNotFoundError

    if is_hidden_button():
        return redirect(url_for(handle_hidden_buttons(), filename=current_document))

    eml_node = load_eml(filename=current_document)
    data_table_nodes = []
    eml_node.find_all_descendants(names.DATATABLE, data_table_nodes)
    data_table_node = None
    for _data_table_node in data_table_nodes:
        if check_data_table_contents.get_data_table_name(_data_table_node) == data_table_name:
            data_table_node = _data_table_node
            break
    if not data_table_node:
        raise DataTableError

    # Save the EML to a file to fixup the namespace declarations
    save_both_formats(current_document, eml_node)

    eml_file_url = check_data_table_contents.get_eml_file_url(current_document, eml_node)
    csv_file_url = check_data_table_contents.get_csv_file_url(current_document, data_table_node)
    csv_filename = check_data_table_contents.get_data_table_filename(data_table_node)
    csv_filepath = check_data_table_contents.get_csv_filepath(current_document, csv_filename)
    data_table_size = check_data_table_contents.get_data_table_size(data_table_node)

    metadata_hash = check_data_table_contents.hash_data_table_metadata_settings(eml_node, data_table_name)

    errors = check_data_table_contents.get_data_file_eval(current_document, csv_filename, metadata_hash)
    if not errors:
        try:
            errors = check_data_table_contents.check_data_table(eml_file_url,
                                                                csv_file_url,
                                                                data_table_name)
            # start = datetime.now()
            # errors =  profile_and_save(#"check_data_table",
            #                            check_data_table_contents.check_data_table(eml_file_url, csv_file_url,
            #                                                                       data_table_name,
            #                                                                       max_errs_per_column=None))
            # log_info(f'check_data_table() returned {errors[:1000]}')
            # end = datetime.now()
            # elapsed = (end - start).total_seconds()
            # print(elapsed)
        except UnicodeDecodeError:
            errors = display_decode_error_lines(csv_filepath)
            return render_template('encoding_error.html', filename=os.path.basename(csv_filepath), errors=errors)
        except Exception as err:
            flash(err, 'error')
            help = get_helps(['data_table_errors'])
            return render_template('data_table_errors.html', data_table_name=data_table_name,
                                   column_errs='', help=help, back_url=get_back_url())

    row_errs, column_errs, has_blanks = check_data_table_contents.generate_error_info_for_webpage(data_table_node, errors)
    collapsed_errors = check_data_table_contents.collapse_error_info_for_webpage(row_errs, column_errs)

    check_data_table_contents.save_data_file_eval(eml_node, current_document, csv_filename, metadata_hash, errors)
    check_data_table_contents.set_check_data_tables_badge_status(current_document, eml_node)
    help = get_helps(['data_table_errors'])
    return render_template('data_table_errors.html',
                           data_table_name=data_table_name,
                           collapsed_errs=collapsed_errors,
                           has_blanks=has_blanks,
                           help=help,
                           back_url=get_back_url())


def init_status_badges(color="white"):
    from webapp.home.check_metadata import is_valid_uuid
    def init_status_badge(badge_name, color="white"):
        badge_name = badge_name + "_status"
        session[badge_name] = color
    status_names = ["title", "data_tables", "creators", "contacts", "associated_parties", "metadata_providers",
                    "abstract", "keywords", "intellectual_rights", "geographic_coverage", "temporal_coverage",
                    "taxonomic_coverage", "maintenance", "publisher", "publication_info", "methods", "project",
                    "other_entities", "data_package_id"]
    [init_status_badge(status_name, color) for status_name in status_names]

    # Get rid of status badges for specific nodes (data tables, etc., with node IDs). They will be re-initialized in the
    # check_metadata_status function, and we want ones that are not re-initialized to be green.
    items_to_delete = []
    for item in session:
        substrs = item.split("_")
        if len(substrs)== 2 and is_valid_uuid(substrs[0]) and substrs[-1] == "status":
            items_to_delete.append(item)
    for item in items_to_delete:
        del session[item]


@home_bp.before_app_request
def handle_highlight_id():
    def handle_special_cases(highlight_id):
        if highlight_id is not None:
            substrs = highlight_id.split("|")
            if substrs[0] == 'code_explanation_1':
                current_document = user_data.get_active_document()
                if current_document:
                    # We need to hydrate the node store
                    eml_node = load_eml(filename=current_document)
                # There are 3 missing value code explanations. Find the first missing one.
                url = url_without_query_string(request.url)
                url_substrs = url.split("/")
                for substr in url_substrs:
                    if is_valid_uuid(substr):
                        node = Node.get_node_instance(substr)
                        if node and node.name == names.ATTRIBUTE:
                            missing_value_code_nodes = node.find_all_children(names.MISSINGVALUECODE)
                            for i, missing_value_code_node in enumerate(missing_value_code_nodes):
                                code_node = missing_value_code_node.find_child(names.CODE)
                                explanation_node = missing_value_code_node.find_child(names.CODEEXPLANATION)
                                if code_node and code_node.content:
                                    if not explanation_node or not explanation_node.content:
                                        highlight_id = f"code_explanation_{i+1}|{substrs[1]}"
                                        break
        return highlight_id

    highlight_id = handle_special_cases(request.args.get("ui_element_id"))
    if highlight_id:
        session["highlight_id"] = highlight_id
    else:
        session["highlight_id"] = None


def get_news_datetime():
    news_filepath = os.path.join(Config.BASE_DIR, "webapp", "home", "templates", "news.html")
    last_modified_ticks = os.path.getmtime(news_filepath)
    return last_modified_ticks


@home_bp.before_app_request
def init_session_vars():

    """ Initialize session variables. """
    init_db()
    init_status_badges()
    init_template_management()

    session["news_datetime"] = get_news_datetime()

    if not session.get("check_metadata_status"):
        session["check_metadata_status"] = "green"
    if not session.get("check_data_tables_status"):
        session["check_data_tables_status"] = "green"
    if not session.get("admin_logins"):
        session["admin_logins"] = Config.ADMIN_LOGINS
    if not session.get("beta_tester_logins"):
        session["beta_tester_logins"] = Config.BETA_TESTER_LOGINS
    if not session.get("data_curator_logins"):
        session["data_curator_logins"] = Config.DATA_CURATOR_LOGINS

    session["enable_collaboration_features"] = Config.ENABLE_COLLABORATION_FEATURES
    collaboration_enabled_for_user = Config.ENABLE_COLLABORATION_FEATURES
    if current_user and hasattr(current_user, 'get_username'):
        if Config.COLLABORATION_BETA_TESTERS_ONLY and \
                current_user.get_username() not in Config.COLLABORATION_BETA_TESTERS:
            collaboration_enabled_for_user = False
        session["collaboration_enabled_for_user"] = collaboration_enabled_for_user
        if collaboration_enabled_for_user:
            collaborations.cull_locks()

    init_standard_units()


@home_bp.before_app_request
def load_eval_entries():
    """
    Load the Check Metadata errors and warnings from the CSV file. This provides the text that is displayed
    in the Check Metadata page.
    """
    if current_app.config.get('__eval__title_01'):
        return
    rows = []
    with open('webapp/static/evaluate.csv') as csv_file:
        csv_reader = csv.reader(csv_file)
        for row in csv_reader:
            rows.append(row)
    for row_num in range(1, len(rows)):
        id, *vals = rows[row_num]
        current_app.config[f'__eval__{id}'] = vals


@home_bp.before_app_request
def init_keywords():
    """
    Load the keywords from the pickle file if we haven't already done so and save in a dict for quick lookup.
    Currently, the only keywords list is for LTER.
    """
    if keywords:
        return
    lter_keywords = pickle.load(open('webapp/static/lter_keywords.pkl', 'rb'))
    keywords['LTER'] = lter_keywords


def get_keywords(which):
    """ Return the keywords list for the specified which. Currently, the only keywords list is for LTER. """
    return keywords.get(which, [])


@home_bp.before_app_request
def init_help():
    """
    Load the help text from the help.txt file if we haven't already done so and save in a dict for quick lookup.
    Save the help for Contents menu in the session so that it can be used in the base.html template.
    """
    if help_dict:
        # Help has already been loaded, but we need to save the help for Contents menu in the session on each request.
        if not session.get('__help__contents'):
            # special case for supporting base.html template
            session['__help__contents'] = help_dict.get('contents')
        return

    with open('webapp/static/help.txt') as help:
        lines = help.readlines()
    index = 0

    def get_help_item(lines, index):
        """ Get the specified help item and format it for HTML display and return the id, title, content, and index. """
        id = lines[index].rstrip()
        title = lines[index+1].rstrip()
        content = '<p>'
        index = index + 2
        while index < len(lines):
            line = lines[index].rstrip('\n')
            index = index + 1
            if line.startswith('--------------------'):
                break
            if len(line) == 0:
                line = '</p><p>'
            content = content + line
            if index >= len(lines):
                break
        content = content + '</p>'
        return (id, title, content), index

    while index < len(lines):
        # Create a dict of help items with the id as the key and the title and content as the value.
        (id, title, content), index = get_help_item(lines, index)
        help_dict[id] = (title, content)
        if id == 'contents':
            # Special case for supporting help for Contents menu in base.html template
            session[f'__help__{id}'] = (title, content)


def get_help(id):
    """
    Return the help title and content for the given id.

    The returned data is ready for use in the templates. The ids are prefixed with '__help__' to make them unique in
    the template.
    """
    title, content = help_dict.get(id)
    return f'__help__{id}', title, content


def get_helps(ids):
    """
    Return a list of help (id, title, content) tuples for the given list of ids.

    The returned list is ready for use in the templates. The ids are prefixed with '__help__' to make them
    unique in the template.
    """
    helps = []
    for id in ids:
        if id in help_dict:
            title, content = help_dict.get(id)
            helps.append((f'__help__{id}', title, content))
    return helps


@home_bp.route('/')
@non_saving_hidden_buttons_decorator
def index():
    """Handle the index (Home) page."""

    if current_user.is_authenticated:
        log_the_details = Config.LOG_FILE_HANDLING_DETAILS or False

        current_document = user_data.get_active_document(log_the_details=log_the_details)
        if current_document:
            eml_node = load_eml(filename=current_document, log_the_details=log_the_details)
            if eml_node:
                new_page = PAGE_TITLE
            else:
                user_data.remove_active_file()
                log_error('Error loading EML file: ' + current_document + ' in index()')
                new_page = PAGE_FILE_ERROR

            new_page = handle_hidden_buttons(new_page)
            return redirect(url_for(new_page, filename=current_document))
        else:
            new_page = 'index.html'
            new_page = handle_hidden_buttons(new_page)
            return render_template(new_page)
    else:
        return redirect(url_for(PAGE_LOGIN))


@home_bp.route('/edit/<page>')
@home_bp.route('/edit/<page>/dev')
def edit(page:str=None, dev=None):
    """
    The edit page allows for direct editing of a top-level element such as
    title, abstract, creators, etc. This function simply redirects to the
    specified page.

    This construction makes it possible for the base.html template to call
    the various top-level element pages by just calling the Edit page, and the
    Edit page handles various checks before redirecting to the correct page.
    """
    if current_user.is_authenticated and page:
        current_filename = user_data.get_active_document()
        if current_filename:
            if page not in [PAGE_COLLABORATE, PAGE_INVITE_COLLABORATOR, PAGE_ACCEPT_INVITATION]:
                # We skip metadata check here because we will do load_eml again on the target page
                eml_node = load_eml(filename=current_filename, skip_metadata_check=True, do_not_lock=True)
                if eml_node:
                    new_page = page
                else:
                    log_error('Error loading EML file: ' + current_filename + ' in edit()')
                    new_page = PAGE_FILE_ERROR
            else:
                new_page = page
            return redirect(url_for(new_page, filename=current_filename))
        else:
            return redirect(url_for(PAGE_INDEX))
    else:
        return redirect(url_for(PAGE_LOGIN))


def get_back_url(success=False):
    """ Handle the back button/link on various pages. """

    def get_redirect_target_page():
        """
        A helper function to get the page to redirect to based on the current page in the Contents main menu.
        Used, for example, when Cancel is clicked on an out-of-sequence page like an Import page.
        """
        current_page = get_current_page()
        if current_page == 'title':
            return PAGE_TITLE
        elif current_page == 'creator':
            return PAGE_CREATOR_SELECT
        elif current_page == 'metadata_provider':
            return PAGE_METADATA_PROVIDER_SELECT
        elif current_page == 'associated_party':
            return PAGE_ASSOCIATED_PARTY_SELECT
        elif current_page == 'abstract':
            return PAGE_ABSTRACT
        elif current_page == 'keyword':
            return PAGE_KEYWORD_SELECT
        elif current_page == 'intellectual_rights':
            return PAGE_INTELLECTUAL_RIGHTS
        elif current_page == 'geographic_coverage':
            return PAGE_GEOGRAPHIC_COVERAGE_SELECT
        elif current_page == 'temporal_coverage':
            return PAGE_TEMPORAL_COVERAGE_SELECT
        elif current_page == 'taxonomic_coverage':
            return PAGE_TAXONOMIC_COVERAGE_SELECT
        elif current_page == 'maintenance':
            return PAGE_MAINTENANCE
        elif current_page == 'contact':
            return PAGE_CONTACT_SELECT
        elif current_page == 'publisher':
            return PAGE_PUBLISHER
        elif current_page == 'publication_info':
            return PAGE_PUBLICATION_INFO
        elif current_page == 'method_step':
            return PAGE_METHOD_STEP_SELECT
        elif current_page == 'project':
            return PAGE_PROJECT
        elif current_page == 'data_table':
            return PAGE_DATA_TABLE_SELECT
        elif current_page == 'other_entity':
            return PAGE_OTHER_ENTITY_SELECT
        elif current_page == 'check_metadata':
            return PAGE_CHECK_METADATA
        elif current_page == 'export_package':
            return PAGE_EXPORT_EZEML_DATA_PACKAGE
        elif current_page == 'data_package_id':
            return PAGE_DATA_PACKAGE_ID
        elif current_page == 'submit_package':
            return PAGE_SUBMIT_TO_EDI
        elif current_page == 'send_to_other':
            return PAGE_SEND_TO_OTHER
        elif current_page == 'manage_data_usage':
            return PAGE_MANAGE_DATA_USAGE
        # elif current_page == 'curator_workflow':
        #     return PAGE_CURATOR_WORKFLOW
        else:
            return PAGE_TITLE

    url = url_for(PAGE_INDEX)
    if current_user.is_authenticated:
        new_page = get_redirect_target_page()
        filename = user_data.get_active_document()
        if new_page and filename:
            url = url_for(new_page, filename=filename, success=success)
        elif not filename:
            url = url_for(PAGE_INDEX)
    return url


@home_bp.route('/about')
def about():
    """Handle the About page."""
    reload_metadata()
    return render_template('about.html', back_url=get_back_url(), title='About')


@home_bp.route('/user_guide')
def user_guide():
    """
    Handle the User Guide page that displays a list of links to User Guide chapters.

    Logging usage of User Guide is done via AJAX endpoint log_user_guide_usage, which is invoked when
    one of the chapter links is clicked.
    """
    reload_metadata()
    return render_template('user_guide.html', back_url=get_back_url(), title='User Guide')


@home_bp.route('/faq')
def faq():
    """
    Handle the FAQ page.
    """
    reload_metadata()
    return render_template('faq.html', back_url=get_back_url(), title='FAQ')


@home_bp.route('/news')
def news():
    """Handle the News page."""
    reload_metadata()
    return render_template('news.html', back_url=get_back_url(), title="What's New")


@home_bp.route('/restore_welcome_dialog')
def restore_welcome_dialog():
    """Handle the Welcome popup that's displayed for first-time users."""
    return render_template('restore_welcome_dialog.html', back_url=get_back_url())


@home_bp.route('/encoding_error/<filename>')
@non_saving_hidden_buttons_decorator
def encoding_error(filename=None, errors=None):
    """Handle the error page that displays errors when characters are encountered that are not UTF-8 encoded."""
    return render_template('encoding_error.html', filename=filename, errors=errors, title='Encoding Errors')


@home_bp.route('/file_error/<filename>')
@non_saving_hidden_buttons_decorator
def file_error(filename=None):
    """Handle the error page that displays a generic error when a file cannot be loaded."""
    return render_template('file_error.html', filename=filename, title='File Error')


@home_bp.route('/save', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def save():
    """
    Handle the save route. Note, however, that when the Save item is selected in the EML Documents menu, what
    actually happens is that a "hidden save" is generated. This gives the currently open page the opportunity
    to save any user-entered values before the save actually occurs.

    So, for example, if the user is on the Title page and enters a title, then clicks Save in the EML Documents
    menu, a post of hidden save to the Title page will be performed and will save the title, saving the document in
    the process. The hidden save tells the Title page to redirect to itself after the save is done. See
    handle_hidden_buttons() and check_val_for_hidden_buttons() is home/utils/hidden_buttons.py.
    """
    current_document = current_user.get_filename()
    
    if not current_document:
        flash('No document currently open')
        return render_template('index.html')

    eml_node = load_eml(filename=current_document)
    if not eml_node:
        flash(f'Unable to open {current_document}')
        return render_template('index.html')

    save_both_formats(filename=current_document, eml_node=eml_node)
    log_usage(actions['SAVE_DOCUMENT'])
    flash(f'Saved {current_document}')
         
    return redirect(url_for(PAGE_TITLE, filename=current_document))


@home_bp.route('/rename_package', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def rename_package():
    def do_rename(current_document, new_document):

        def move_files(from_package, to_package):
            """
            Move the metadata files and uploads from one package to another as part of the 'Rename' operation.
            """
            user_folder = user_data.get_user_folder_name(current_user_directory_only=True)
            from_metadata = os.path.join(user_folder, f"{from_package}.json")
            to_metadata = os.path.join(user_folder, f"{to_package}.json")
            try:
                move(from_metadata, to_metadata)
            except FileNotFoundError:
                pass
            from_metadata = os.path.join(user_folder, f"{from_package}.xml")
            to_metadata = os.path.join(user_folder, f"{to_package}.xml")
            try:
                move(from_metadata, to_metadata)
            except FileNotFoundError:
                pass
            from_eval_pkl = os.path.join(user_folder, f"{from_package}_eval.pkl")
            to_eval_pkl = os.path.join(user_folder, f"{to_package}_eval.pkl")
            try:
                move(from_eval_pkl, to_eval_pkl)
            except FileNotFoundError:
                pass

            from_folder = user_data.get_document_uploads_folder_name(from_package)
            to_folder = user_data.get_document_uploads_folder_name(to_package)
            for filename in os.listdir(from_folder):
                from_path = os.path.join(from_folder, filename)
                to_path = os.path.join(to_folder, filename)
                move(from_path, to_path)
                user_data.add_data_table_upload_filename(filename, document_name=to_package)

        # Uploads are stored under the document name, so we need to copy them.
        move_files(current_document, new_document)
        log_usage(actions['RENAME_PACKAGE'], current_document, new_document)
        current_user.set_filename(filename=new_document)
        eml_node = load_eml(filename=new_document)
        fixup_distribution_urls(eml_node)
        save_both_formats(filename=new_document, eml_node=eml_node)
        # Rename the package in the collaborations database. It is assumed that if we got here, we've already
        #  established that the current user is the owner of the document.
        user_login = current_user.get_user_org()
        # collaborations.rename_package(user_login, current_document, new_document)
        # Delete the old package
        user_data.delete_package(current_document)

    """Handle the Rename Package page."""
    current_document = current_user.get_filename()
    if not current_document:
        flash('No document currently open')
        return render_template('index.html')

    if not user_data.user_is_owner_of_active_document():
        flash("Only the document's owner can rename it.", 'error')
        return redirect(get_back_url())

    help = get_helps(['rename_document', 'save_as_document'])

    form = RenamePackageForm()
    if BTN_CANCEL in request.form:
        if current_document:
            return redirect(get_back_url())
        else:
            return render_template('index.html')

    # Get names already in use
    user_path = user_data.get_user_folder_name(current_user_directory_only=True)
    files = list_files_in_dir(user_path)
    in_use = []
    for file in files:
        if file.endswith('.json'):
            in_use.append(file[:-5])

    if form.validate_on_submit():
        new_name = form.filename.data
        if not new_name:
            flash('Please enter a new name')
            return render_template('rename_package.html', form=form, help=help, in_use=in_use, title='Rename Package')

        if new_name == current_document:
            flash('The new name must be different from the current name.', 'error')
            return render_template('rename_package.html', form=form, help=help, in_use=in_use, title='Rename Package')

        if user_data.is_document_locked(new_name):
            flash(f'The document "{new_name}" is currently locked by another user.', 'error')
            return render_template('rename_package.html', form=form, help=help, in_use=in_use, title='Rename Package')

        do_rename(current_document, new_name)

        flash(f'Renamed "{current_document}" to "{new_name}"')
        return redirect(url_for(PAGE_TITLE, filename=new_name))

    return render_template('rename_package.html', form=form, help=help, in_use=in_use, title='Rename Package')


@home_bp.route('/manage_packages', methods=['GET', 'POST'])
@home_bp.route('/manage_packages/<to_delete>', methods=['GET', 'POST'])
@home_bp.route('/manage_packages/<to_delete>/<action>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def manage_packages(to_delete=None, action=None):
    """Handle the Manage Packages page."""

    # When a link is clicked to delete a package,the package name is passed to the server.
    # That's what the to_delete parameter is for.
    if to_delete is not None:
        # The Manage Packages page has a Back button, which makes use of the to_delete parameter, passing
        #  the special value '____back____' to indicate that the Back button was clicked.
        if to_delete == '____back____':
            action = '____back____'
        # Otherwise, the user actually clicked a link to delete a package.
        elif action != '____back____':
            user_data.is_document_locked(filename=to_delete)
            # This is where the delete is done.
            user_data.delete_package(filename=to_delete)
            log_usage(actions['MANAGE_PACKAGES'], 'delete', to_delete)
            flash(f'Deleted {to_delete}') # TO DO - handle error cases

    if action == '____back____':
        return redirect(get_back_url())

    # Set the default sort order. Other sort orders can be selected by clicking the column headers and are handled
    # in the template.
    sort_by = 'package_name'
    reverse = False

    # Get the list of packages in a form usable by the template.
    data_packages = get_data_packages(sort_by=sort_by, reverse=reverse)

    help = get_helps(['manage_packages'])
    log_usage(actions['MANAGE_PACKAGES'])

    return render_template('manage_packages.html', data_packages=data_packages, help=help)


@home_bp.route('/manage_data_usage', methods=['GET', 'POST'])
@home_bp.route('/manage_data_usage/<action>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def manage_data_usage(action=None):
    """
    Handle the Manage Data Usage page.

    This page is available only to admins and data_curators. It allows them to see how much disk space each user
    is using, and it allows them to download EML and data files from any user's account.
    """
    if not current_user.is_admin() and not current_user.is_data_curator():
        flash('You are not authorized to access the Manage Data Usage page', 'error')
        return redirect(url_for(PAGE_INDEX))

    days = Config.GC_DAYS_TO_LIVE  # default number of days to filter on

    reload_metadata()  # Reload the metadata to set badge colors

    # The action parameter is used to signal we want to return to the previous page.
    if action == '____back____':
        return redirect(get_back_url())

    if request.method == 'POST':
        # If the user clicked the Garbage Collect button, do the garbage collection.
        if 'gc' in request.form and 'days' in request.form:
            days = request.form['days']
            result = subprocess.run(['python3', 'webapp/gc.py', f'--days={days}',
                                     f'--keep_uploads={Config.GC_KEEP_UPLOADS}',
                                     f'--include_exports={Config.GC_INCLUDE_EXPORTS}',
                                     f'--exports_days={Config.GC_EXPORTS_DAYS_TO_LIVE}',
                                     f'--logonly={Config.GC_LOG_ONLY}'],
                                    capture_output=True, text=True)
            if result.returncode == 0:
                flash(f'Garbage collection completed. Days={days}.')
            else:
                flash(f'Garbage collection failed: {result.stderr}', 'error')

    # Set the default sort order. Other sort orders can be selected by clicking the column headers and are handled
    # in the template.
    sort_by = 'user_name'
    reverse = False

    total_usage, data_usages = get_data_usage(sort_by=sort_by, reverse=reverse)
    total_usage = math.ceil(total_usage / 1024**2) # MB
    total_usage = f"{total_usage:,}"

    log_usage(actions['MANAGE_DATA_USAGE'])
    help = get_helps(['manage_data_usage'])
    set_current_page('manage_data_usage')

    if not Config.GC_BUTTON_ENABLED:
        disabled = 'disabled'
    else:
        disabled = ''

    return render_template('manage_data_usage.html', total_usage=total_usage, data_usages=data_usages, days=days,
                           disabled=disabled, is_admin=current_user.is_admin(), help=help)


@home_bp.route('/save_as', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def save_as():
    """
    Handle the Save As item in the EML Documents menu.
    """

    def copy_uploads(from_package, to_package):
        """
        Copy the uploads from one package to another as part of the 'Save As' operation.
        Note that 'Save As' doesn't replace the original package. It creates a new package with a new name, so the
        uploads are copied, not moved.
        """
        from_folder = user_data.get_document_uploads_folder_name(from_package)
        to_folder = user_data.get_document_uploads_folder_name(to_package)
        for filename in os.listdir(from_folder):
            from_path = os.path.join(from_folder, filename)
            to_path = os.path.join(to_folder, filename)
            copyfile(from_path, to_path)
            user_data.add_data_table_upload_filename(filename, document_name=to_package)

    form = SaveAsForm()
    current_document = current_user.get_filename()

    # Process POST
    if request.method == 'POST':
        if BTN_CANCEL in request.form:
            if current_document:
                # Revert back to the old filename
                return redirect(get_back_url())
            else:
                return render_template('index.html')

        if form.validate_on_submit():
            if not current_document:
                flash('No document currently open')
                return render_template('index.html')

            eml_node = load_eml(filename=current_document)
            if not eml_node:
                flash(f'Unable to open {current_document}')
                return render_template('index.html')

            new_document = form.filename.data
            return_value = save_old_to_new(
                            old_filename=current_document,
                            new_filename=new_document,
                            eml_node=eml_node)
            if isinstance(return_value, str):
                # An error has occurred. The return_value is the error message.
                flash(return_value)
                new_filename = current_document  # Revert back to the old filename
            else:
                # Uploads are stored under the document name, so we need to copy them.
                copy_uploads(current_document, new_document)
                log_usage(actions['SAVE_AS_DOCUMENT'], new_document)
                current_user.set_filename(filename=new_document)
                fixup_distribution_urls(eml_node)
                save_both_formats(filename=new_document, eml_node=eml_node)
                flash(f'Saved as {new_document}')
            new_page = PAGE_TITLE   # Return the Response object

            return redirect(url_for(new_page, filename=new_document))

    # Process GET
    if current_document:
        # form.filename.data = current_document
        help = get_helps(['save_as_document'])
        return render_template('save_as.html',
                               filename=current_document,
                               title='Save As',
                               form=form,
                               help=help)
    else:
        flash("No document currently open")
        return render_template('index.html')


@home_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def settings():
    form = SettingsForm()

    if request.method == 'POST':
        if BTN_CANCEL in request.form:
            return redirect(get_back_url())

        if form.validate_on_submit():
            current_document = current_user.get_filename()
            document_setting_changed = False
            document_setting = user_data.get_enable_complex_text_element_editing_document(current_document)
            global_setting = user_data.get_enable_complex_text_element_editing_global()
            if document_setting != form.complex_text_editing_document.data or global_setting != form.complex_text_editing_global.data:
                document_setting_changed = True
            user_data.set_enable_complex_text_element_editing_document(current_document, form.complex_text_editing_document.data)
            user_data.set_enable_complex_text_element_editing_global(form.complex_text_editing_global.data)
            if document_setting_changed:
                eml_node = load_eml(filename=current_document)
                if eml_node:
                    # Setting has changed, so we need to re-process the document
                    user_data.set_model_has_complex_texttypes(texttype_node_processing.model_has_complex_texttypes(eml_node))
            user_data.set_enable_automatic_qudt_annotations(form.add_qudt_units_annotations.data)
            user_data.set_replace_preexisting_qudt_annotations(form.replace_qudt_units_annotations.data)
            log_usage(actions['SETTINGS'])
            return redirect(get_back_url())

    if request.method == 'GET':
        current_document = user_data.get_active_document()
        document_has_complex_texttypes = False
        if current_document:
            eml_node = load_eml(filename=current_document)
            document_has_complex_texttypes = texttype_node_processing.model_has_complex_texttypes(eml_node)
        form.complex_text_editing_document.data = user_data.get_enable_complex_text_element_editing_document() or \
                                                    document_has_complex_texttypes
        form.complex_text_editing_global.data = user_data.get_enable_complex_text_element_editing_global()
        form.add_qudt_units_annotations.data, form.replace_qudt_units_annotations.data = user_data.get_qudt_annotations_settings()
    help = get_helps(['settings_text', 'settings_qudt_annotations'])
    return render_template('settings.html', programmatic=document_has_complex_texttypes, form=form, help=help)


@home_bp.route('/check_data_tables', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def check_data_tables():
    """Handle the Check Data Tables item in the main Contents menu."""
    if hasattr(Config, 'LOG_FILE_HANDLING_DETAILS'):
        log_the_details = Config.LOG_FILE_HANDLING_DETAILS
    else:
        log_the_details = False
    current_document = user_data.get_active_document(log_the_details)
    if not current_document:
        raise FileNotFoundError
    eml_node = load_eml(filename=current_document)
    log_usage(actions['CHECK_DATA_TABLES'])
    set_current_page('check_data_tables')

    # Process POST
    if request.method == 'POST':
        if BTN_CHECK_ALL_TABLES in request.form:
            check_data_table_contents.check_all_tables(current_document, eml_node)

    content, btn_disabled = check_data_table_contents.create_check_data_tables_status_page_content(
        current_document, eml_node)
    tooltip = 'Nothing to check' if btn_disabled else ''

    check_data_table_contents.set_check_data_tables_badge_status(current_document, eml_node)

    help = get_helps(['check_data_tables'])
    return render_template('check_data_tables.html', help=help, content=content,
                           btn_disabled=btn_disabled, tooltip=tooltip)


@home_bp.route('/explore_data_tables', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def explore_data_tables():
    """Handle the Explore Data Tables item in the main Contents menu."""
    current_document = user_data.get_active_document()
    if not current_document:
        raise FileNotFoundError
    eml_node = load_eml(filename=current_document)
    log_usage(actions['EXPLORE_DATA_TABLES'])
    set_current_page('explore_data_tables')

    # Process POST
    content, scripts = check_data_table_contents.create_explore_data_tables_page_content(
        current_document, eml_node)

    # check_data_table_contents.set_check_data_tables_badge_status(current_document, eml_node)

    help = get_helps(['explore_data_tables'])
    return render_template('explore_data_tables.html', help=help, content=content, scripts=scripts)


@home_bp.route('/check_metadata', methods=['GET', 'POST'])
@home_bp.route('/check_metadata/<filename>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def check_metadata(filename:str = None):
    """Handle the Check Metadata item in the main Contents menu."""
    if hasattr(Config, 'LOG_FILE_HANDLING_DETAILS'):
        log_the_details = Config.LOG_FILE_HANDLING_DETAILS
    else:
        log_the_details = False
    current_document = user_data.get_active_document(log_the_details)
    if not current_document:
        raise FileNotFoundError
    eml_node = load_eml(filename=current_document, skip_metadata_check=True, do_not_lock=True)

    content, parse_errs, unicode_errs = check_eml(eml_node, current_document)

    log_usage(actions['CHECK_METADATA'])

    # Process POST
    if request.method == 'POST':
        return redirect(url_for(PAGE_CHECK_METADATA, filename=current_document))

    else:
        set_current_page('check_metadata')
        help = get_helps(['unicode_characters_active'])
        return render_template('check_metadata.html',
                               content=content,
                               parse_errs=parse_errs,
                               unicodes=unicode_errs,
                               filename=filename,
                               help=help,
                               title='Check Metadata')


@home_bp.route('/datetime_formats', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def datetime_formats():
    """Display the list of acceptable datetime formats."""
    content = format_date_time_formats_list()

    # Process POST
    if request.method == 'POST':
        if is_hidden_button():
            current_document = current_user.get_filename()
            return redirect(url_for(handle_hidden_buttons(), filename=current_document))

        return redirect(url_for(PAGE_DATETIME_FORMATS))

    else:
        return render_template('datetime_formats.html', content=content)


@home_bp.route('/download_current', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def download_current():
    """
    Handle the Download EML File (XML) page.

    This saves the current document and downloads its EML file to the client. It returns the 200 Response object if
    the download was successful. In so doing, it stays on the current page.
    """
    current_document = user_data.get_active_document()
    if current_document:

        # Force the document to be saved, so it gets cleaned
        eml_node = load_eml(filename=current_document)
        save_both_formats(filename=current_document, eml_node=eml_node)

        # Do the download
        package_id = eml_node.attribute_value("packageId")
        return_value = user_data.download_eml(filename=current_document, package_id=package_id)
        log_usage(actions['DOWNLOAD_EML_FILE'], package_id)

        if isinstance(return_value, str):
            # If there was an error, display it as a Flash message.
            flash(return_value, 'error')
            return redirect(get_back_url())
        else:
            # No error, so just return the 200 status code response object.
            return return_value


def allowed_data_file(filename):
    """Only certain file types are allowed to be uploaded as data/csv files."""
    ALLOWED_EXTENSIONS = set(['csv', 'tsv', 'txt', 'xml', 'ezeml_tmp'])
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@home_bp.route('/create', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def create():
    """Handle the New... page in EML Documents menu."""

    form = CreateEMLForm()
    help = get_helps(['new_eml_document'])

    # Process POST
    if request.method == 'POST':

        if BTN_CANCEL in request.form:
            return redirect(get_back_url())

        if form.validate_on_submit():
            filename = form.filename.data

            if '/' in filename:
                flash("Please choose a name that does not contain a slash '/' character.", 'error')
                return render_template('create_eml.html', help=help, form=form)

            if len(filename) > 100:
                flash("Please choose a name that is less than 100 characters long. This name serves only to identify your EML document within " \
                      "your ezEML account. It will not appear in your package's metadata. It just needs to be specific enough to enable you " \
                      "to distinguish this EML document from others in your account.", 'error')
                return render_template('create_eml.html', help=help, form=form)

            user_filenames = user_data.get_user_document_list()
            if user_filenames and filename and filename in user_filenames:
                flash(f'{filename} already exists. Please select another name.', 'error')
                return render_template('create_eml.html', help=help, form=form)

            log_usage(actions['NEW_DOCUMENT'])
            create_eml(filename=filename)

            # Open the document. Note that open_document() handles locking.
            return open_document(filename)

    # Process GET
    return render_template('create_eml.html', help=help, form=form)


@home_bp.route('/display_tables', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def display_tables():
    """
    For development purposes only. Display the contents of the database tables used for collaboration.
    There is no link to this page in the ezEML user interface. It is only accessible via the URL.
    """
    from webapp.views.collaborations.model import (
        User, Package, Collaboration, CollaborationStatus, Lock, GroupLock, GroupCollaboration
    )
    users = User.query.all()
    packages = Package.query.all()
    collaborations = Collaboration.query.all()
    group_collaborations = GroupCollaboration.query.all()
    collaboration_statuses = CollaborationStatus.query.all()
    locks = Lock.query.all()
    group_locks = GroupLock.query.all()

    return render_template('display_tables.html', users=users, packages=packages, collaborations=collaborations,
                           group_collaborations=group_collaborations,
                           collaboration_statuses=collaboration_statuses, locks=locks, group_locks=group_locks)


def open_document(filename, owner=None, owner_login=None):
    """
    This function is used both in opening a document via the Open... menu selection and via an Open link on the Collaborate
    page. In the latter case, it is assumed that the caller has set the active_package_id before calling. This is
    needed so that load_eml() looks in the correct folder for the EML file.

    This function takes care of locking the document if it is not already locked. In case of a failure, it takes care
    of releasing any acquired lock.
    """

    # Check if the document is locked by another user. If not, lock it.
    # If it is locked, an exception will be thrown and handled in webapp/errors/handler.py, which posts an
    #  informative message.
    lock = user_data.is_document_locked(filename)

    eml_node = load_eml(filename, owner_login=owner_login)
    loaded_ok = True
    if eml_node:
        try:
            current_user.set_filename(filename)
            # If we're doing Open via Collaborate page, the owner and owner_login will have been provided by the caller
            if owner:
                current_user.set_file_owner(owner, owner_login)
            packageid = eml_node.attributes.get('packageId', None)
            if packageid:
                current_user.set_packageid(packageid)
            new_page = PAGE_TITLE
            log_usage(actions['OPEN_DOCUMENT'])
            # Set the badge status for the Check Data Tables menu item. The Check Metadata badge status will have been
            #  set by load_eml().
            check_data_table_contents.set_check_data_tables_badge_status(filename, eml_node)
        except Exception as e:
            loaded_ok = False
            log_error('Error loading EML file: ' + filename + ' in open_document(): {e}')
    if not eml_node or not loaded_ok:
        release_acquired_lock(lock)
        if not eml_node:
            log_error('Error loading EML file: ' + filename + ' in open_document()')
        new_page = PAGE_FILE_ERROR
    return redirect(url_for(new_page, filename=filename))


@home_bp.route('/open_eml_document', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def open_eml_document():
    """Handle the Open... page in EML Documents menu."""

    form = OpenEMLDocumentForm()
    form.filename.choices = list_data_packages(True, True)

    # Process POST
    if request.method == 'POST':

        if BTN_CANCEL in request.form:
            return redirect(get_back_url())

        if form.validate_on_submit():
            filename = form.filename.data

            # Open the document. Note that open_document takes care of handling locks.
            return open_document(filename)

    # Process GET
    return render_template('open_eml_document.html', title='Open EML Document', 
                           form=form)


@home_bp.route('/save_as_template', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def save_as_template():
    """Handle the Save As Template... page in EML Documents menu."""

    """
    First, check if the user is authorized to access multiple template folders. If so, the first step is to select
    the folder in which to save the template. If not, the user will be taken directly to the Save As Template page.
    """
    template_folders = template_folders_for_user()

    form = SaveAsTemplateForm()
    reload_metadata() # To update the content menu badges.

    choices = [[folder, folder] for folder in template_folders]
    form.folder.choices = choices

    # Process POST
    if request.method == 'POST':

        if BTN_CANCEL in request.form:
            return redirect(url_for(PAGE_MANAGE_TEMPLATES))

        if form.validate_on_submit():
            filename = form.filename.data
            if len(template_folders) > 1:
                folder = form.folder.data
            elif len(template_folders) == 1:
                folder = template_folders[0]
                form.folder.data = folder
            else:
                flash('You do not have access to any template folders.', 'error')
                return redirect(url_for(PAGE_TITLE, filename=current_user.get_filename()))

            # Copy the current document to the selected template folder.
            current_document = current_user.get_filename()
            save_to_name = form.filename.data
            copy_document_to_template_folder(current_document, folder, save_to_name)

            flash(f'Template saved as "{save_to_name}" in template folder {folder}.', 'success')

            flash(f'Document "{save_to_name}" has been removed from your user folder. '
                  f"To edit it in the future, go to 'Manage Templates...' and  use the 'Open Template' button, "
                  f"which copies it to your user folder and opens it for editing.")

            return redirect(url_for(PAGE_TITLE, filename=current_document))
        else:
            if len(template_folders) > 1 and not form.folder.data:
                flash('Select a template folder and try again.', 'error')

    # Process GET
    if len(template_folders) == 1:
        form.folder.data = template_folders[0]

    form.filename.data = current_user.get_filename()

    help = get_helps(['template_name'])
    return render_template('save_as_template.html', title='Save As Template',
                           form=form, help=help)


@home_bp.route('/delete_template', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def delete_template():
    """Handle the Delete Template... page in EML Documents menu."""

    form = DeleteTemplateForm()
    form.filename.choices = templates_for_user()
    reload_metadata() # To update the content menu badges.

    # Process POST
    if request.method == 'POST':

        if BTN_CANCEL in request.form:
            return redirect(url_for(PAGE_MANAGE_TEMPLATES))

        if form.validate_on_submit():
            filename = form.filename.data

            # Delete the selected template.
            if delete_template_file(filename):
                flash(f'Template "{filename}" was deleted.', 'success')
            else:
                flash(f'Error deleting template "{filename}".', 'error')
            return redirect(url_for(PAGE_INDEX))

    # Process GET
    help = get_helps(['save_as_document'])
    return render_template('delete_template.html', title='Delete Template',
                           form=form, help=help)


@home_bp.route('/manage_templates', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def manage_templates():
    """Handle the Manage Templates... page in EML Documents menu."""

    form = EDIForm()
    reload_metadata() # To update the content menu badges.

    # Process POST
    if request.method == 'POST':

        if BTN_CANCEL in request.form:
            return redirect(get_back_url())

        if form.validate_on_submit():
            # If the user has clicked Save in the EML Documents menu, for example, we need to ignore the
            #  programmatically generated Submit

            if request.form.get(BTN_SUBMIT) == BTN_OPEN_TEMPLATE:
                return redirect(url_for(PAGE_OPEN_TEMPLATE))
            elif request.form.get(BTN_SUBMIT) == BTN_SAVE_AS_TEMPLATE:
                return redirect(url_for(PAGE_SAVE_AS_TEMPLATE))
            elif request.form.get(BTN_SUBMIT) == BTN_DELETE_TEMPLATE:
                return redirect(url_for(PAGE_DELETE_TEMPLATE))
            elif request.form.get(BTN_SUBMIT) == BTN_DISPLAY_TEMPLATES:
                return redirect(url_for(PAGE_DISPLAY_TEMPLATES))

    if not current_user.get_filename():
        save_disabled = 'disabled'
    else:
        save_disabled = ''

    help = get_helps(['manage_templates', 'open_template', 'save_as_template', 'delete_template', 'display_templates'])
    return render_template('manage_templates.html',
                           title='Manage Templates',
                           save_disabled=save_disabled,
                           form=form, help=help)


@home_bp.route('/open_template', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def open_template():
    """Handle the Open Template... page in Manage Templates... menu."""

    form = OpenTemplateForm()
    form.filename.choices = list_templates(True)
    reload_metadata() # To update the content menu badges.

    # Process POST
    if request.method == 'POST':

        if BTN_CANCEL in request.form:
            return redirect(url_for(PAGE_MANAGE_TEMPLATES))

        if form.validate_on_submit():
            filename = form.filename.data

            # Check that we are not going to overwrite a modified document in the user's data directory.
            if check_overwrite_user_data(filename):
                doc_name = os.path.basename(filename)
                doc_name = os.path.splitext(doc_name)[0]
                current_filename = current_user.get_filename()
                if doc_name == current_filename:
                    flash(f'A different version of document "{doc_name}" is currently open. '
                          f"Opening the template will overwrite it. Please delete it before opening this template.\n\n"
                          f"If desired, you can use 'Save As...' in the 'EML Documents' menu to save the currently open version "
                          f"under a different name before deleting it.\n\n"
                          f"If the currently open version is intended to replace the template, just use 'Save As Template' to save it.")
                else:
                    flash(f'A different version of document "{doc_name}" already exists in your user folder. '
                          f"Opening the template will overwrite it. Please delete it before opening this template.\n\n"
                          f"If the version in your user folder is the one you want to keep, use the ordinary 'Open' "
                          f"command to open it. You can then save it as a template if you wish.")
                return redirect(url_for(PAGE_MANAGE_TEMPLATES))

            # Copy the template to the user's data directory.
            filename = copy_template_to_user_data(filename)

            flash(f'Template "{filename}" has been copied to your user data directory and opened for editing.\n\n'
                  f"When you are done editing, use 'Save As Template' on the 'Manage Templates' page to save your changes to the template.", 'success')

            # Open the document. Note that open_document takes care of handling locks.
            return open_document(filename)

    # Process GET
    return render_template('open_template.html', title='Open Template',
                           form=form)


@home_bp.route('/open_package/<package_name>', methods=['GET', 'POST'])
@home_bp.route('/open_package/<package_name>/<owner>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def open_package(package_name, owner=None):
    """Handle a link to open a document via the Manage Packages page."""

    if not owner:
        owner = current_user.get_user_login()
    owner_data_dir = os.path.join(Config.USER_DATA_DIR, owner)

    eml_node = load_eml(package_name, folder_name=owner_data_dir)
    if eml_node:
        current_user.set_filename(package_name)
        if owner:
            if owner != current_user.get_user_login():
                current_user.set_file_owner(collaborations.display_name(owner))
            else:
                current_user.set_file_owner(None)
        packageid = eml_node.attributes.get('packageId', None)
        if packageid:
            current_user.set_packageid(packageid)
        new_page = PAGE_TITLE
        log_usage(actions['OPEN_DOCUMENT'])
        check_data_table_contents.set_check_data_tables_badge_status(package_name, eml_node)
    else:
        log_error('Error loading EML file: ' + package_name + ' in open_package()')
        new_page = PAGE_FILE_ERROR

    return redirect(url_for(new_page, filename=package_name))


def form_template_tree(file, output, collapsed=True, set_targets=True):
    """
    Note that the expansion of template folders, etc., is handled in JavaScript in the template.
    """
    def get_subdirs(dir):
        subdirs = []
        for fname in sorted(os.listdir(dir), key=str.lower):
            if os.path.isdir(os.path.join(dir, fname)):
                subdirs.append(os.path.join(dir, fname))
        return subdirs

    def get_files(dir):
        files = []
        for fname in sorted(os.listdir(dir), key=str.lower):
            if os.path.isdir(os.path.join(dir, fname)) or fname.endswith('.json'):
                files.append(os.path.join(dir, fname))
        return files

    def add_file(fname, output):
        dir = os.path.dirname(fname)
        dir = dir.replace(f"{Config.TEMPLATE_DIR}/", '')
        fname = os.path.splitext(os.path.basename(fname))[0]
        if set_targets:
            output += f'<li onclick="setTarget(\'{fname}\', \'{dir}\');" style="color:steelblue;cursor:pointer;">{fname}</li>\n'
        else:
            output += f'<li style="color:black;">{fname}</li>\n'

        return output

    if file == Config.TEMPLATE_DIR:
        subdirs = get_subdirs(file)
        if not subdirs:
            return "<i>No templates are available at this time.</i>"

    have_ul = False
    if os.path.isdir(file):
        files = get_files(file)
        if file != Config.TEMPLATE_DIR:
            output += f'<li>{os.path.basename(os.path.normpath(file))}\n'
            if files:
                if collapsed:
                    output += f'<ul style="display: none;">\n'
                else:
                    output += f'<ul style="display: block;">\n'
                have_ul = True
        for file in files:
            output = form_template_tree(file, output, collapsed=collapsed, set_targets=set_targets)
    else:
        if file:
            output = add_file(file, output)
    if have_ul:
        output += "</ul>\n"
    output += "</li>\n"

    return output


@home_bp.route('/display_templates', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def display_templates():
    """
    Handle the Display Templates... item in EML Documents menu.

    Note that the expansion of template folders, etc., is handled in JavaScript in the template.
    """
    reload_metadata() # To update the content menu badges.

    if request.method == 'POST':
        form = request.form
        if BTN_CANCEL in form:
            return redirect(url_for(PAGE_MANAGE_TEMPLATES))

        if is_hidden_button():
            new_page = handle_hidden_buttons(PAGE_MANAGE_TEMPLATES)
            return redirect(url_for(new_page))

    # Process GET
    output = '<ul class="directory-list">\n'
    output = form_template_tree(Config.TEMPLATE_DIR, output, collapsed=False, set_targets=False)
    output += '</ul>'

    help = get_helps(['new_from_template'])
    return render_template('display_templates.html', directory_list=output, help=help)


@home_bp.route('/new_from_template', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def new_from_template():
    """
    Handle the New from Template... item in EML Documents menu.

    Note that the expansion of template folders, etc., is handled in JavaScript in the template.
    """
    if request.method == 'POST':
        form = request.form
        if BTN_CANCEL in form:
            return redirect(get_back_url())

        if is_hidden_button():
            new_page = handle_hidden_buttons(PAGE_NEW_FROM_TEMPLATE_2)
            current_document = current_user.get_filename()
            return redirect(url_for(new_page, filename=current_document))

        form_dict = form.to_dict(flat=False)
        # Find the key with value = 'OK'. That gives the path of the template.
        template_path = ''
        for key, val in form_dict.items():
            if val == ['OK']:
                template_path = key
                break
        if template_path:
            template_path = template_path.replace('/', '\\')
            return redirect(url_for(PAGE_NEW_FROM_TEMPLATE_2, template_filename=template_path))
        else:
            new_page = handle_hidden_buttons(PAGE_NEW_FROM_TEMPLATE_2)
            current_document = current_user.get_filename()
            return redirect(url_for(new_page, filename=current_document))

    # Process GET
    output = '<ul class="directory-list">\n'
    output = form_template_tree(Config.TEMPLATE_DIR, output)
    output += '</ul>'

    help = get_helps(['new_from_template'])
    return render_template('new_from_template.html', directory_list=output, help=help)


@home_bp.route('/new_from_template_2/<template_filename>/', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def new_from_template_2(template_filename):
    """Handle the New from Template... item in EML Documents menu after a template has been selected."""

    def create_auto_collaborations(template_filename, package_name):
        """
        Certain sites are configured to automatically generate one or more collaborations when a new package is created
         from one of their templates. Handle that here.
        """
        # See if auto-collaborations are configured for this template, based on the template path, and if so, create them.
        auto_collaborations = Config.AUTO_COLLABORATION_SITES
        if auto_collaborations:
            for key, value in auto_collaborations.items():
                path = os.path.dirname(template_filename)
                if path == key:
                    for collaborator_info in value:
                        collaborator_login = collaborator_info[0]
                        collaborator_email = collaborator_info[1] if len(collaborator_info) > 0 else None
                        create_auto_collaboration(current_user.get_user_login(),
                                                  collaborator_login,
                                                  package_name,
                                                  template_filename,
                                                  collaborator_email)

    def new_from_selected_template(template_filename, output_filename):
        # Copy the template into the user's directory
        user_folder = user_data.get_user_folder_name(current_user_directory_only=True)
        copyfile(f"{Config.TEMPLATE_DIR}/{template_filename}", f"{user_folder}/{output_filename}.json")
        open_document(filename=output_filename)
        # Save XML
        eml_node = load_eml(output_filename)
        save_eml(filename=output_filename, eml_node=eml_node, format='xml')

    form = CreateEMLForm()

    # Process POST
    help = get_helps(['new_eml_document'])
    if request.method == 'POST':

        if BTN_CANCEL in request.form:
            return redirect(get_back_url())

        if form.validate_on_submit():
            filename = form.filename.data
            user_filenames = user_data.get_user_document_list()
            if user_filenames and filename and filename in user_filenames:
                flash(f'{filename} already exists. Please select another name.', 'error')
                return render_template('new_from_template_2.html', template_filename=template_filename,
                                       help=help, form=form)

            if len(filename) > 100:
                flash("Please choose a name that is less than 100 characters long. This name serves only to identify your EML document within " \
                      "your ezEML account. It will not appear in your package's metadata. It just needs to be specific enough to enable you " \
                      "to distinguish this EML document from others in your account.", 'error')
                return render_template('new_from_template_2.html', template_filename=template_filename,
                                       help=help, form=form)

            template_filename = template_filename.replace('\\', '/')
            template_path = f'{template_filename}.json'

            new_from_selected_template(template_path, filename)
            current_user.set_filename(filename)
            log_usage(actions['NEW_FROM_TEMPLATE'], template_filename)
            current_user.set_packageid(None)
            create_auto_collaborations(template_filename, filename)
            new_page = PAGE_TITLE
            return redirect(url_for(new_page, filename=filename))

    # Process GET
    return render_template('new_from_template_2.html', help=help, form=form)


@home_bp.route('/import_parties', methods=['GET', 'POST'])
@home_bp.route('/import_parties/<target>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def import_parties(target=None):
    """Handle the Import Responsible Parties item in Import/Export menu."""

    form = ImportEMLForm()
    form.filename.choices = list_data_packages(True, True)
    form.template.choices = list_templates()

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    # Process POST
    if request.method == 'POST':
        if BTN_CANCEL in request.form:
            return redirect(get_back_url())

        if form.validate_on_submit():
            filename = form.filename.data or current_user.get_filename()
            template = form.template.data
            is_template = 'Open Template' in request.form
            return redirect(url_for('home.import_parties_2', filename=filename, template=quote(template, safe=''),
                                    is_template=is_template, target=target))

    # Process GET
    help = get_helps(['import_responsible_parties'])
    return render_template('import_parties.html', target=target, help=help, form=form)


@home_bp.route('/import_parties_2/<filename>/<template>/<is_template>', methods=['GET', 'POST'])
@home_bp.route('/import_parties_2/<filename>/<template>/<is_template>/<target>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def import_parties_2(filename, template, is_template, target=None):
    """Handle the Import Responsible Parties item in Import/Export menu after a source document has been selected."""

    def get_name(rp_node):
        individual_name_node = rp_node.find_child(names.INDIVIDUALNAME)
        label = compose_individual_name_label(individual_name_node)
        if not label:
            label = compose_simple_label(rp_node, names.ORGANIZATIONNAME)
            position_name_label = compose_simple_label(rp_node, names.POSITIONNAME)
            if not label:
                label = position_name_label
            else:
                label = f'{label}, {position_name_label}'
        return label

    party_lookup = {}
    def add_to_lookup(rp_node):
        party_lookup[get_name(rp_node)] = True

    def check_lookup(rp_node):
        return party_lookup.get(get_name(rp_node))

    def get_responsible_parties_for_import(eml_node):
        parties = []
        for node in eml_node.find_all_nodes_by_path([names.DATASET, names.CREATOR]):
            label = compose_rp_label(node)
            if not check_lookup(node):
                parties.append(('Creator', f'{label} (Creator)', node.id))
                add_to_lookup(node)
        for node in eml_node.find_all_nodes_by_path([names.DATASET, names.CONTACT]):
            label = compose_rp_label(node)
            if not check_lookup(node):
                parties.append(('Contact', f'{label} (Contact)', node.id))
                add_to_lookup(node)
        for node in eml_node.find_all_nodes_by_path([names.DATASET, names.ASSOCIATEDPARTY]):
            label = compose_rp_label(node)
            if not check_lookup(node):
                parties.append(('Associated Party', f'{label} (Associated Party)', node.id))
                add_to_lookup(node)
        for node in eml_node.find_all_nodes_by_path([names.DATASET, names.METADATAPROVIDER]):
            label = compose_rp_label(node)
            if not check_lookup(node):
                parties.append(('Metadata Provider', f'{label} (Metadata Provider)', node.id))
                add_to_lookup(node)
        for node in eml_node.find_all_nodes_by_path([names.DATASET, names.PUBLISHER]):
            label = compose_rp_label(node)
            if not check_lookup(node):
                parties.append(('Publisher', f'{label} (Publisher)', node.id))
                add_to_lookup(node)
        for node in eml_node.find_all_nodes_by_path([names.DATASET, names.PROJECT, names.PERSONNEL]):
            label = compose_rp_label(node)
            if not check_lookup(node):
                parties.append(('Project Personnel', f'{label} (Project Personnel)', node.id))
                add_to_lookup(node)
        for node in eml_node.find_all_nodes_by_path([names.DATASET, names.PROJECT, names.RELATED_PROJECT, names.PERSONNEL]):
            label = compose_rp_label(node)
            if not check_lookup(node):
                related_project_node = node.parent
                project_title_node = related_project_node.find_child(names.TITLE)
                project_title = f' - {project_title_node.content}' if project_title_node else ''
                parties.append(
                    ('Related Project Personnel', f'{label} (Related Project Personnel{project_title})', node.id))
                add_to_lookup(node)
        return parties

    def get_sorted_parties(parties):
        def sort_key(item):
            return item[1].lower()

        # Remove the labels 'Creator', 'Contact', etc., in addition to sorting
        cleaned = [
            (t[0], t[1].rsplit(' (', 1)[0] if '(' in t[1] and ')' in t[1] else t[1], t[2])
            for t in parties]
        return sorted(cleaned, key=sort_key)

    def add_related_project_personnel_targets():
        target_filename = current_user.get_filename()
        target_eml_node = load_eml(target_filename)
        related_project_personnel_targets = []
        related_project_nodes = target_eml_node.find_all_nodes_by_path([names.DATASET, names.PROJECT, names.RELATED_PROJECT])
        for related_project_node in related_project_nodes:
            title = ''
            title_node = related_project_node.find_child(names.TITLE)
            if title_node:
                title = title_node.content
            related_project_personnel_targets.append((f'Related Project Personnel for {title}',
                                                      f'Related Project Personnel for {title}'))
        return related_project_personnel_targets

    def get_project_node_id_for_target(eml_node, target_class):
        target_eml_node = load_eml(current_user.get_filename())
        if target_class == 'Project Personnel':
            project_node = target_eml_node.find_single_node_by_path([names.DATASET, names.PROJECT])
            if project_node:
                return project_node.id
            else:
                return None
        related_project_nodes = target_eml_node.find_all_nodes_by_path([names.DATASET, names.PROJECT, names.RELATED_PROJECT])
        for related_project_node in related_project_nodes:
            title_node = related_project_node.find_child(names.TITLE)
            if title_node:
                if target_class == f'Related Project Personnel for {title_node.content}':
                    return related_project_node.id
        return None

    is_template = ast.literal_eval(is_template)
    if True or is_template:
        form = ImportPartiesFromTemplateForm()
    else:
        form = ImportEMLItemsForm()

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    if is_hidden_button():
        current_document = current_user.get_filename()
        return redirect(url_for(handle_hidden_buttons(), filename=current_document))

    if not is_template:
        source_filename = filename
        user_login = current_user.get_user_org() # If I'm importing from a data package, I'm the owner
        eml_node = load_eml(source_filename, owner_login=user_login)
    else:
        source_filename = template_display_name(unquote(template))
        eml_node = load_template(unquote(template))

    parties = get_responsible_parties_for_import(eml_node)
    choices = [[party[2], party[1]] for party in parties]
    form.to_import.choices = choices

    sorted_parties = get_sorted_parties(parties)
    sorted_choices = [[party[2], party[1]] for party in sorted_parties]
    form.to_import_sorted.choices = sorted_choices

    targets = [
        ("Creators", "Creators"),
        ("Contacts", "Contacts"),
        ("Associated Parties", "Associated Parties"),
        ("Metadata Providers", "Metadata Providers"),
        ("Publisher", "Publisher"),
        ("Project Personnel", "Project Personnel")]
    targets.extend(add_related_project_personnel_targets())
    form.target.choices = targets

    if request.method == 'POST':
        if form.validate_on_submit():
            node_ids_to_import = form.data['to_import']
            target_class = form.data['target']
            target_filename = current_user.get_filename()
            import_responsible_parties(target_filename, node_ids_to_import, target_class)
            log_usage(actions['IMPORT_RESPONSIBLE_PARTIES'], filename, target_class)
            if target_class == 'Creators':
                new_page = PAGE_CREATOR_SELECT
            elif target_class == 'Metadata Providers':
                new_page = PAGE_METADATA_PROVIDER_SELECT
            elif target_class == 'Associated Parties':
                new_page = PAGE_ASSOCIATED_PARTY_SELECT
            elif target_class == 'Contacts':
                new_page = PAGE_CONTACT_SELECT
            elif target_class == 'Publisher':
                new_page = PAGE_PUBLISHER
            elif target_class == 'Project Personnel' or target_class.startswith('Related Project Personnel'):
                new_page = PAGE_PROJECT_PERSONNEL_SELECT
                return redirect(url_for(new_page, filename=target_filename,
                                        project_node_id=get_project_node_id_for_target(eml_node, target_class)))
            return redirect(url_for(new_page, filename=target_filename, target=target))

    # Process GET

    if target:
        # If the target is specified, set the target to the specified value
        # This is used, for example, when the user clicks "Import Creator" from the Creator Select page
        form.target.data = target

    help = get_helps(['import_responsible_parties_2'])
    return render_template('import_parties_2.html', is_template=is_template,
                           source_filename=source_filename, target=target, help=help, form=form)


@home_bp.route('/import_keywords', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def import_keywords():
    """Handle the Import Keywords item in Import/Export menu."""

    form = ImportEMLForm()
    form.filename.choices = list_data_packages(False, False)
    form.template.choices = list_templates()

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    # Process POST
    if request.method == 'POST':
        if BTN_CANCEL in request.form:
            return redirect(get_back_url())

        if form.validate_on_submit():
            filename = form.filename.data or current_user.get_filename()
            template = form.template.data
            is_template = 'Open Template' in request.form
            return redirect(url_for('home.import_keywords_2', filename=filename, template=quote(template, safe=''), is_template=is_template))

    # Process GET
    help = get_helps(['import_keywords'])

    return render_template('import_keywords.html', help=help, form=form)


@home_bp.route('/import_keywords_2/<filename>/<template>/<is_template>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def import_keywords_2(filename, template, is_template):
    """Handle the Import Keywords item in Import/Export menu after a source document has been selected."""

    def get_keywords_for_import(eml_node):
        """
        Returns four items:
            - dict of keyword groups in original order
            - choices for checkboxes in orginal order
            - dict of keyword groups in sorted order (groups sorted and keywords sorted within groups)
            - choices for checkboxes in sorted order
        For now, we're not using the sorted versions.
        """
        dataset_node = eml_node.find_child(names.DATASET)
        if not dataset_node:
            return {}, [], {}, []

        keyword_tuples = []
        keyword_groups = {}
        sorted_keyword_groups = {}

        keyword_set_nodes = []
        dataset_node.find_all_descendants(names.KEYWORDSET, keyword_set_nodes)
        for keyword_set_node in keyword_set_nodes:
            keyword_nodes = []
            keyword_set_node.find_all_descendants(names.KEYWORD, keyword_nodes)
            for keyword_node in keyword_nodes:
                keyword = keyword_node.content
                if not keyword:
                    continue
                thesaurus_node = keyword_set_node.find_child(names.KEYWORDTHESAURUS)
                thesaurus = thesaurus_node.content if thesaurus_node else ''
                keyword_tuples.append((keyword_node.id, f'{keyword} {thesaurus}', keyword, thesaurus))
                keyword_groups[thesaurus] = keyword_groups.get(thesaurus, []) + [(keyword_node.id, keyword)]

        for key in keyword_groups:
            sorted_keyword_groups[key] = sorted(keyword_groups[key], key=lambda x: x[1].lower())
        sorted_keyword_groups = {key: keyword_groups[key] for key in sorted(keyword_groups)}
        return (
            keyword_groups,
            [(a, b) for a, b, _, _ in keyword_tuples],
            sorted_keyword_groups,
            [(a, b) for a, b, _, _ in sorted(keyword_tuples, key=lambda x: (x[3].lower(), x[2].lower()))])

    form = ImportItemsSortableForm()

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    is_template = ast.literal_eval(is_template)
    if not is_template:
        source_filename = filename
        user_login = current_user.get_user_org() # If I'm importing from a data package, I'm the owner
        eml_node = load_eml(source_filename, owner_login=user_login)
    else:
        source_filename = template_display_name(unquote(template))
        eml_node = load_template(unquote(template))

    keyword_groups, choices, sorted_keyword_groups, sorted_choices = get_keywords_for_import(eml_node)
    form.to_import.choices = choices
    form.to_import_sorted.choices = sorted_choices

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    if is_hidden_button():
        current_document = current_user.get_filename()
        return redirect(url_for(handle_hidden_buttons(), filename=current_document))

    if form.validate_on_submit():
        node_ids_to_import = form.data['to_import']
        target_package = current_user.get_filename()
        import_keyword_nodes(target_package, node_ids_to_import)
        log_usage(actions['IMPORT_KEYWORDS'], filename)
        return redirect(url_for(PAGE_KEYWORD_SELECT, filename=target_package))

    # Process GET
    help = get_helps(['import_keywords_2'])
    return render_template('import_keywords_2.html', help=help, source_filename=source_filename,
                           keyword_groups=keyword_groups, form=form)


@home_bp.route('/import_geo_coverage', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def import_geo_coverage():
    """Handle the Import Geographic Coverage item in Import/Export menu."""

    form = ImportEMLForm()
    form.filename.choices = list_data_packages(False, False)
    form.template.choices = list_templates()

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    # Process POST
    if request.method == 'POST':
        if BTN_CANCEL in request.form:
            return redirect(get_back_url())

        if form.validate_on_submit():
            filename = form.filename.data or current_user.get_filename()
            template = form.template.data
            is_template = 'Open Template' in request.form
            return redirect(url_for('home.import_geo_coverage_2', filename=filename, template=quote(template, safe=''), is_template=is_template))

    # Process GET
    help = get_helps(['import_geographic_coverage'])
    return render_template('import_geo_coverage.html', help=help, form=form)


@home_bp.route('/import_geo_coverage_2/<filename>/<template>/<is_template>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def import_geo_coverage_2(filename, template, is_template):
    """Handle the Import Geographic Coverage item in Import/Export menu after a source document has been selected."""

    def get_geo_coverages_for_import(eml_node):
        coverages = []
        for node in eml_node.find_all_nodes_by_path([names.DATASET, names.COVERAGE, names.GEOGRAPHICCOVERAGE]):
            label = compose_full_gc_label(node)
            coverages.append((f'{label}', node.id))
        return coverages

    form = ImportItemsForm()

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    is_template = ast.literal_eval(is_template)
    if not is_template:
        source_filename = filename
        user_login = current_user.get_user_org() # If I'm importing from a data package, I'm the owner
        eml_node = load_eml(source_filename, owner_login=user_login)
    else:
        source_filename = template_display_name(unquote(template))
        eml_node = load_template(unquote(template))

    coverages = get_geo_coverages_for_import(eml_node)
    choices = [[coverage[1], coverage[0]] for coverage in coverages]
    form.to_import.choices = choices

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    if form.validate_on_submit():
        node_ids_to_import = form.data['to_import']
        target_package = current_user.get_filename()
        import_coverage_nodes(target_package, node_ids_to_import)
        log_usage(actions['IMPORT_GEOGRAPHIC_COVERAGE'], filename)
        return redirect(url_for(PAGE_GEOGRAPHIC_COVERAGE_SELECT, filename=target_package))

    # Process GET
    help = get_helps(['import_geographic_coverage_2'])
    return render_template('import_geo_coverage_2.html', help=help,source_filename=source_filename, form=form)


@home_bp.route('/import_taxonomic_coverage', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def import_taxonomic_coverage():
    """Handle the Import Taxonomic Coverage item in Import/Export menu."""

    form = ImportEMLForm()
    form.filename.choices = list_data_packages(False, False)
    form.template.choices = list_templates()

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    # Process POST
    if request.method == 'POST':
        if BTN_CANCEL in request.form:
            return redirect(get_back_url())

        if form.validate_on_submit():
            filename = form.filename.data or current_user.get_filename()
            template = form.template.data
            is_template = 'Open Template' in request.form
            return redirect(url_for('home.import_taxonomic_coverage_2', filename=filename, template=quote(template, safe=''), is_template=is_template))

    # Process GET
    help = get_helps(['import_taxonomic_coverage'])
    return render_template('import_taxonomic_coverage.html', help=help, form=form)


@home_bp.route('/import_taxonomic_coverage_2/<filename>/<template>/<is_template>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def import_taxonomic_coverage_2(filename, template, is_template):
    """Handle the Import Taxonomic Coverage item in Import/Export menu after a source document has been selected."""

    def get_taxonomic_coverages_for_import(eml_node):
        coverages = []
        for node in eml_node.find_all_nodes_by_path([names.DATASET, names.COVERAGE, names.TAXONOMICCOVERAGE]):
            label = truncate_middle(compose_taxonomic_label(node), 100, ' ... ')
            coverages.append((f'{label}', node.id))
        return coverages

    form = ImportItemsForm()

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    is_template = ast.literal_eval(is_template)
    if not is_template:
        source_filename = filename
        user_login = current_user.get_user_org() # If I'm importing from a data package, I'm the owner
        eml_node = load_eml(source_filename, owner_login=user_login)
    else:
        source_filename = template_display_name(unquote(template))
        eml_node = load_template(unquote(template))

    coverages = get_taxonomic_coverages_for_import(eml_node)
    choices = [[coverage[1], coverage[0]] for coverage in coverages]
    form.to_import.choices = choices

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    if form.validate_on_submit():
        node_ids_to_import = form.data['to_import']
        target_package = current_user.get_filename()
        eml_node = import_coverage_nodes(target_package, node_ids_to_import)
        clear_taxonomy_imported_from_xml_flag(eml_node, target_package)
        log_usage(actions['IMPORT_TAXONOMIC_COVERAGE'], filename)
        return redirect(url_for(PAGE_TAXONOMIC_COVERAGE_SELECT, filename=target_package))

    # Process GET
    help = get_helps(['import_taxonomic_coverage_2'])
    return render_template('import_taxonomic_coverage_2.html', help=help, source_filename=source_filename, form=form)


@home_bp.route('/import_funding_awards', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def import_funding_awards():
    """Handle the Import Funding Awards item in Import/Export menu."""

    form = ImportEMLForm()
    form.filename.choices = list_data_packages(False, False)
    form.template.choices = list_templates()

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    # Process POST
    if request.method == 'POST':
        if BTN_CANCEL in request.form:
            return redirect(get_back_url())

        if form.validate_on_submit():
            filename = form.filename.data or current_user.get_filename()
            template = form.template.data
            is_template = 'Open Template' in request.form
            return redirect(url_for('home.import_funding_awards_2', filename=filename, template=quote(template, safe=''), is_template=is_template))

    # Process GET
    help = get_helps(['import_funding_awards'])
    return render_template('import_funding_awards.html', help=help, form=form)


@home_bp.route('/import_funding_awards_2/<filename>//<template>/<is_template>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def import_funding_awards_2(filename, template, is_template):
    """Handle the Import Funding Awards item in Import/Export menu after a source document has been selected."""

    def get_funding_awards_for_import(eml_node):
        awards = []
        award_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.PROJECT, names.AWARD])
        for award_node in award_nodes:
            label = truncate_middle(compose_funding_award_label(award_node), 80, ' ... ')
            awards.append((f'{label}', award_node.id))
        return awards

    form = ImportItemsForm()

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    is_template = ast.literal_eval(is_template)
    if not is_template:
        source_filename = filename
        user_login = current_user.get_user_org() # If I'm importing from a data package, I'm the owner
        eml_node = load_eml(source_filename, owner_login=user_login)
    else:
        source_filename = template_display_name(unquote(template))
        eml_node = load_template(unquote(template))

    coverages = get_funding_awards_for_import(eml_node)
    choices = [[coverage[1], coverage[0]] for coverage in coverages]
    form.to_import.choices = choices

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    if form.validate_on_submit():
        node_ids_to_import = form.data['to_import']
        target_package = current_user.get_filename()
        import_funding_award_nodes(target_package, node_ids_to_import)
        log_usage(actions['IMPORT_FUNDING_AWARDS'], filename)
        return redirect(url_for(PAGE_FUNDING_AWARD_SELECT, filename=target_package))

    # Process GET
    help = get_helps(['import_funding_awards_2'])
    return render_template('import_funding_awards_2.html', help=help, source_filename=source_filename, form=form)


@home_bp.route('/import_project', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def import_project():
    """Handle the Import Project item in Import/Export menu."""

    form = ImportEMLForm()
    form.filename.choices = list_data_packages(False, False)
    form.template.choices = list_templates()

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    # Process POST
    if request.method == 'POST':
        if BTN_CANCEL in request.form:
            return redirect(get_back_url())

        if form.validate_on_submit():
            filename = form.filename.data or current_user.get_filename()
            template = form.template.data
            is_template = 'Open Template' in request.form
            return redirect(url_for('home.import_project_2', filename=filename, template=quote(template, safe=''), is_template=is_template))

    # Process GET
    help = get_helps(['import_project'])
    return render_template('import_project.html', help=help, form=form)


def get_projects_for_import(eml_node):
    """A helper function to get a list of projects from an EML document for import. Used by both Import Project and
    Import Related Projects."""

    projects = []
    project = eml_node.find_single_node_by_path([names.DATASET, names.PROJECT])
    project_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.PROJECT, names.RELATED_PROJECT])
    if project:
        # If the project has no title, it's a case where related projects were defined without the main project,
        #  e.g., in a template. In this case, we don't want to include the project in the list of projects to import.
        project_title = project.find_child(names.TITLE)
        if project_title and project_title.content:
            project_nodes.append(project)
    for project_node in project_nodes:
        label = truncate_middle(compose_project_label(project_node), 80, ' ... ')
        projects.append((f'{label}', project_node.id))
    return projects


@home_bp.route('/import_project_2/<filename>/<template>/<is_template>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def import_project_2(filename, template, is_template):
    """Handle the Import Project item in Import/Export menu after a source document has been selected."""

    form = ImportSingleItemForm()

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    is_template = ast.literal_eval(is_template)
    if not is_template:
        source_filename = filename
        user_login = current_user.get_user_org() # If I'm importing from a data package, I'm the owner
        eml_node = load_eml(source_filename, owner_login=user_login)
    else:
        source_filename = template_display_name(unquote(template))
        eml_node = load_template(unquote(template))

    projects = get_projects_for_import(eml_node)
    choices = [[project[1], project[0]] for project in projects]
    form.to_import.choices = choices

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    if form.validate_on_submit():
        node_id_to_import = form.data['to_import']
        target_package = current_user.get_filename()
        import_project_node(target_package, node_id_to_import)
        log_usage(actions['IMPORT_PROJECT'], filename)
        return redirect(url_for(PAGE_PROJECT, filename=target_package))

    # Process GET
    help = get_helps(['import_project_2'])
    return render_template('import_project_2.html', help=help, source_filename=source_filename, form=form)


@home_bp.route('/import_related_projects', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def import_related_projects():
    """Handle the Import Related Projects item in Import/Export menu."""

    form = ImportEMLForm()
    form.filename.choices = list_data_packages(False, False)
    form.template.choices = list_templates()

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    # Process POST
    if request.method == 'POST':
        if BTN_CANCEL in request.form:
            return redirect(get_back_url())

        if form.validate_on_submit():
            filename = form.filename.data or current_user.get_filename()
            template = form.template.data
            is_template = 'Open Template' in request.form
            return redirect(url_for('home.import_related_projects_2', filename=filename, template=quote(template, safe=''), is_template=is_template))

    # Process GET
    help = get_helps(['import_related_projects'])
    return render_template('import_related_projects.html', help=help, form=form)


@home_bp.route('/import_related_projects_2/<filename>/<template>/<is_template>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def import_related_projects_2(filename, template, is_template):
    """Handle the Import Related Projects item in Import/Export menu after a source document has been selected."""

    form = ImportItemsForm()

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    is_template = ast.literal_eval(is_template)
    if not is_template:
        source_filename = filename
        user_login = current_user.get_user_org() # If I'm importing from a data package, I'm the owner
        eml_node = load_eml(source_filename, owner_login=user_login)
    else:
        source_filename = template_display_name(unquote(template))
        eml_node = load_template(unquote(template))

    projects = get_projects_for_import(eml_node)
    choices = [[project[1], project[0]] for project in projects]
    form.to_import.choices = choices

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    if form.validate_on_submit():
        node_ids_to_import = form.data['to_import']
        target_package = current_user.get_filename()
        import_related_project_nodes(target_package, node_ids_to_import)
        log_usage(actions['IMPORT_RELATED_PROJECTS'], filename)
        return redirect(url_for(PAGE_RELATED_PROJECT_SELECT, filename=target_package))

    # Process GET
    help = get_helps(['import_related_projects_2'])
    return render_template('import_related_projects_2.html', help=help, source_filename=source_filename, form=form)


def display_decode_error_lines(filename):
    """A helper function used in displaying lines with UTF-8 decode errors in a file."""
    errors = []
    with open(filename, 'r', encoding='utf-8-sig', errors='replace') as f:
        lines = f.readlines()
    for index, line in enumerate(lines, start=1):
        if "�" in line:
            errors.append((index, line))
    return errors


def zip_package(current_document=None, eml_node=None, include_data=True):
    """Create an ezEML Data Package, for example to export it or send to another user."""

    def create_ezeml_package_manifest(user_folder, manifest_files):
        with open(f'{user_folder}/ezEML_manifest.txt', 'w') as manifest_file:
            manifest_file.write(f'ezEML Data Archive Manifest\n')
            manifest_file.write(f'ezEML Release {RELEASE_NUMBER}\n')
            manifest_file.write(f'--------------------\n')
            for filetype, filename, filepath in manifest_files:
                manifest_file.write(f'{filetype}\n')
                manifest_file.write(f'{filename}\n')
                manifest_file.write(f'{get_md5_hash(filepath)}\n')

    if not current_document:
        current_document = current_user.get_filename()
    if not current_document:
        raise FileNotFoundError
    if not eml_node:
        eml_node = load_eml(filename=current_document)

    user_folder = user_data.get_user_folder_name()

    if include_data:
        zipfile_name = f'{current_document}.zip'
    else:
        zipfile_name = f'{current_document}.without_data.zip'

    zipfile_path = os.path.join(user_folder, zipfile_name)
    zip_object = ZipFile(zipfile_path, 'w')

    manifest_files = []

    pathname = f'{user_folder}/{current_document}.json'
    arcname = f'{current_document}.json'
    zip_object.write(pathname, arcname)
    manifest_files.append(('JSON', f'{current_document}.json', pathname))

    package_id = eml_node.attribute_value("packageId")
    if package_id and package_id != current_document:
        # copy the EML file using the package_id as name
        arcname = f"{package_id.replace('/', '_')}.xml"
        copyfile(f'{user_folder}/{current_document}.xml', f'{user_folder}/{arcname}')
    else:
        arcname = f'{current_document}.xml'
    # pathname = f'{user_folder}/{current_document}.xml'
    pathname = f'{user_folder}/{arcname}'
    manifest_files.append(('XML', arcname, pathname))
    zip_object.write(pathname, arcname)

    create_ezeml_package_manifest(user_folder, manifest_files)
    pathname = f'{user_folder}/ezEML_manifest.txt'
    arcname = 'ezEML_manifest.txt'
    zip_object.write(pathname, arcname)

    # We create two versions of the zip, one with the data files and one without.
    # The zip without the data files supports cases where the data files are extremely large. It lets
    #   data curators download the JSON and XML without having to download the data.

    if include_data:
        # get data files
        uploads_folder = user_data.get_document_uploads_folder_name()
        data_table_nodes = []
        eml_node.find_all_descendants(names.DATATABLE, data_table_nodes)
        entity_nodes = []
        eml_node.find_all_descendants(names.OTHERENTITY, entity_nodes)
        data_nodes = data_table_nodes + entity_nodes
        for data_node in data_nodes:
            object_name_node = data_node.find_single_node_by_path([names.PHYSICAL, names.OBJECTNAME])
            if object_name_node:
                object_name = object_name_node.content
                pathname = f'{uploads_folder}/{object_name}'
                arcname = f'data/{object_name}'
                try:
                    zip_object.write(pathname, arcname)
                except FileNotFoundError as err:
                    filename = os.path.basename(err.filename)
                    msg = f"Unable to archive the package. Missing file: {filename}."
                    raise MissingFileError(msg)
                    # flash(msg, category='error')
                    # return None

    zip_object.close()
    return zipfile_path


def save_as_ezeml_package_export(archive_file):
    """Save the ezEML Data Package to the user's export folder."""

    def encode_export_url(dest):
        subs = dest.split('/exports/')
        if len(subs) > 1:
            return f'{subs[0]}/exports/{urllib.parse.quote(subs[1])}'
        else:
            return dest

    current_document = current_user.get_filename()
    if not current_document:
        raise FileNotFoundError

    user_folder = user_data.get_user_download_folder_name()

    # Create the exports folder
    timestamp = datetime.now().date().strftime('%Y_%m_%d') + '_' + datetime.now().time().strftime('%H_%M_%S')
    export_folder = os.path.join(user_folder, 'exports', current_document, timestamp)
    os.makedirs(export_folder, exist_ok=True)

    _, archive_basename = os.path.split(archive_file)
    src = archive_file
    dest = f'{export_folder}/{archive_basename}'
    move(src, dest)

    encoded_dest = encode_export_url(dest)
    parsed_url = urlparse(request.base_url)
    download_url = f"{parsed_url.scheme}://{parsed_url.netloc}/{dest}"
    encoded_url = f"{parsed_url.scheme}://{parsed_url.netloc}/{encoded_dest}"
    return archive_basename, download_url, encoded_url


@home_bp.route('/export_package', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def export_package():
    """Handle the Export ezEML Data Package item in the Import/Export menu."""

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct
    if not current_document:
        return redirect(url_for(PAGE_INDEX))

    if request.method == 'POST':
        save_both_formats(current_document, eml_node)
        try:
            zipfile_path = zip_package(current_document, eml_node)
        except MissingFileError as err:
            flash(err.message, category='error')
            return redirect(get_back_url())

        if zipfile_path:
            archive_basename, download_url, _ = save_as_ezeml_package_export(zipfile_path)
            if download_url:
                log_usage(actions['EXPORT_EZEML_DATA_PACKAGE'])
                # We want to use the tinyurl version of the url, but we don't want to fail altogether if tinyurl.com is
                #  temporarily unavailable
                try:
                    url = make_tiny(download_url)
                except requests.exceptions.HTTPError as err:
                    # Something's wrong with tinyurl.com
                    log_error('make_tiny() failed with error: {err}')
                    url = download_url
                return redirect(url_for('home.export_package_2', package_name=archive_basename,
                                        download_url=url, safe=''))

    # Process GET
    help = get_helps(['export_package'])
    return render_template('export_package.html', back_url=get_back_url(), title='Export Data Package', help=help)


@home_bp.route('/export_package_2/<package_name>/<path:download_url>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def export_package_2(package_name, download_url):
    """Handle the Export ezEML Data Package item in the Import/Export menu."""

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    return render_template('export_package_2.html', back_url=get_back_url(), title='Export Data Package',
                           package_name=package_name, download_url=download_url)


def clear_distribution_url(entity_node):
    """ Clear the distribution URL for the specified entity node (either names.DATATABLE or names.OTHERENTITY). """

    distribution_node = entity_node.find_descendant(names.DISTRIBUTION)
    if distribution_node:
        url_node = distribution_node.find_descendant(names.URL)
        if url_node:
            url_node.content = None


def encode_distribution_url(url_node):
    """Helper function to encode a distribution URL for use in the EML."""
    url = url_node.content
    if url:
        subs = url.split('/uploads/')
        if len(subs) > 1:
            # The reason we do the convoluted replace, unquote, quote is that the URL may have been encoded
            #  incorrectly by a previous version of ezEML. We want to make sure we encode it correctly.
            url = subs[0] + '/uploads/' + quote(unquote(subs[1].replace('%20', ' ')))
        url_node.content = url
    return url


def insert_urls(uploads_url_prefix, uploads_folder, eml_node, node_type):
    """
    Helper function to insert distribution URLs into the EML for the specified node type (either names.DATATABLE
    or names.OTHERENTITY.

    Logically, this function should be nested within insert_upload_urls, but it's a separate function so
    insert_upload_urls is more readable.
    """
    def keep_existing_url(distribution_node, uploads_folder, file_exists):
        # If a distribution node exists, check to see if there's a URL and, if so, whether it points to a different
        #  user's account or a different package. The case we want to guard against is one where we've imported a
        #  "without data" ezEML Data Package and all we're doing is modifying the EML (e.g., changing the data package ID)
        #  before uploading to PASTA. In such a case, we want to leave existing distribution nodes as we've found them, so
        #  they will point to the original user's ezEML account and package.
        url_node = distribution_node.find_descendant(names.URL)
        # This encodes the URL correctly, undoing the incorrect encoding that was done in an earlier version of ezEML.
        encode_distribution_url(url_node)
        if url_node:
            url = url_node.content
            if url:
                if uploads_folder not in unquote(url):
                    # The URL points to a different location, not to the user's account. If we don't have a file in the
                    #  user's account, we'll leave the distribution node alone.
                    # We may, however, have uploaded or imported a file and thereby have a file in the user's account.
                    #  In that case, we want to use the version in the user's account.
                    if not file_exists:
                        return True
        return False

    upload_nodes = []
    eml_node.find_all_descendants(node_type, upload_nodes)
    for upload_node in upload_nodes:
        try:
            physical_node = upload_node.find_descendant(names.PHYSICAL)
            if not physical_node:
                continue
            object_name_node = physical_node.find_child(names.OBJECTNAME)
            if not object_name_node:
                continue
            object_name = object_name_node.content
            # See if file exists before adding a distribution URL pointing to our copy.
            filepath = os.path.join(uploads_folder, object_name)
            file_exists = os.path.exists(filepath)
            distribution_node = physical_node.find_child(names.DISTRIBUTION)
            if distribution_node:
                if keep_existing_url(distribution_node, uploads_folder, file_exists):
                    continue
                webapp.home.utils.node_utils.remove_child(distribution_node)
            if not file_exists:
                continue
            distribution_node = new_child_node(names.DISTRIBUTION, physical_node)
            online_node = new_child_node(names.ONLINE, distribution_node)
            url_node = new_child_node(names.URL, online_node)
            url_node.add_attribute('function', 'download')
            url_node.content = f"{uploads_url_prefix}/{object_name}"
            encode_distribution_url(url_node)
        except Exception as err:
            flash(err)
            continue


def insert_upload_urls(current_document, eml_node, clear_existing_urls=False):
    """Insert distribution URLs into the EML for uploaded files for both data tables and other entities."""

    user_folder = user_data.get_user_download_folder_name()
    uploads_folder = f'{user_folder}/uploads/{current_document}'
    parsed_url = urlparse(request.base_url)
    uploads_url_prefix = f"{parsed_url.scheme}://{parsed_url.netloc}/{quote(uploads_folder)}"

    if 'localhost:5000' not in uploads_url_prefix:
        # When developing locally, the generated URL will point to localhost:5000 and be flagged by Flask as invalid.
        # This is a pain in the neck, since we can't leave the page without clearing the URL. So, we'll just skip the
        # URL insertion when working locally. Hence, the check above.
        insert_urls(uploads_url_prefix, uploads_folder, eml_node, names.DATATABLE)
        insert_urls(uploads_url_prefix, uploads_folder, eml_node, names.OTHERENTITY)


@home_bp.route('/share_submit_package', methods=['GET', 'POST'])
@home_bp.route('/share_submit_package/<filename>', methods=['GET', 'POST'])
@home_bp.route('/share_submit_package/<filename>/<success>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def share_submit_package(filename=None, success=None):
    """Handle the Submit/Share Package page."""

    form = SubmitToEDIForm()

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct
    if not current_document:
        return redirect(url_for(PAGE_INDEX))

    if request.method == 'POST':
        # If the user has clicked Save in the EML Documents menu, for example, we need to ignore the
        #  programmatically generated Submit

        if request.form.get(BTN_SUBMIT) == BTN_SUBMIT_PACKAGE_TO_EDI:
            return redirect(url_for(PAGE_ENABLE_EDI_CURATION, filename=filename))

        if request.form.get(BTN_SUBMIT) == BTN_COLLABORATE_WITH_COLLEAGUE:
            return redirect(url_for(PAGE_COLLABORATE, filename=filename))

    set_current_page('share_submit_package')
    help = get_helps(['share_submit_package_to_edi', 'share_submit_package_colleague'])
    return render_template('share_submit_package.html',
                           title='Share/Submit Your Data Package',
                           check_metadata_status=get_check_metadata_status(eml_node, current_document),
                           form=form, help=help, success=success)


def make_tiny(url):
    """Helper function to generate a tiny URL."""
    import requests
    params = {'url': quote(url, safe=':/')}
    response = requests.post('http://tinyurl.com/api-create.php', params=params)
    response.raise_for_status()
    return response.text.replace('http://', 'https://')


def backup_metadata(filename):
    """
    When doing Clone Column Properties or Reupload, we backup the metadata. This is done purely in case our code
    messes up the metadata. I.e., it's a safety net, one that can be removed once we're confident in the code.
    """
    return
    user_folder = user_data.get_user_folder_name()
    if not user_folder:
        flash('User folder not found', 'error')
        return
    # make sure backups directory exists
    backup_path = os.path.join(user_folder, 'backups')
    try:
        os.mkdir(backup_path)
    except FileExistsError:
        pass
    timestamp = datetime.now().date().strftime('%Y_%m_%d') + '_' + datetime.now().time().strftime('%H_%M_%S')
    backup_filename = f'{user_folder}/backups/{filename}.json.{timestamp}'
    filename = f'{user_folder}/{filename}.json'
    try:
        copyfile(filename, backup_filename)
    except:
        flash(f'Error backing up file {filename}.json', 'error')


def encode_for_query_string(param):
    """Helper function for passing lists in the query string. Flask does not handle lists well, so we need to encode."""
    # The parameters are actually lists, but Flask drops parameters that are empty lists, so what's passed are the
    #  string representations. In addition, the string may contain '/' characters, which will not be encoded by default,
    #  thereby breaking the routing, so we need them to be encoded. Setting safe to an empty string accomplishes that.
    return quote(repr(param), safe='')


def decode_from_query_string(param):
    """The inverse operation of encode_for_query_string(), turning the parameter back into a list."""
    return ast.literal_eval(unquote(param))


@home_bp.route('/import_xml', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def import_xml():
    """Handle the Import EML File (XML)... item in the Import/Export menu."""

    form = ImportPackageForm()

    # Process POST

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    if request.method == 'POST' and form.validate_on_submit():

        # Check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)

        file = request.files['file']
        if file:
            filename = unquote(file.filename)

            if not os.path.splitext(filename)[1] == '.xml':
                flash('Please select a file with file extension ".xml".', 'error')
                return redirect(request.url)

            package_base_filename = os.path.basename(filename)
            package_name = os.path.splitext(package_base_filename)[0]

            filepath = save_xml_file_in_temp_folder(file)
            # See if package with that name already exists
            if package_name in user_data.get_user_document_list():
                return redirect(url_for('home.import_xml_2', package_name=package_name, filename=filename))

            try:
                # Parse the XML file and return errors, if any.
                eml_node, nsmap_changed, unknown_nodes, attr_errs, child_errs, other_errs, pruned_nodes = \
                    parse_xml_file(filename, filepath)
                eml_node = strip_elements_added_by_pasta(package_name, eml_node)
                if qudt_annotations.remove_redundant_qudt_annotations(eml_node):
                    flash('Redundant QUDT units annotations were found and removed')

                # We're done with the temp file
                utils.remove_zip_temp_folder()

                if eml_node:
                    add_imported_from_xml_metadata(eml_node, filename, package_name)
                    has_errors = unknown_nodes or attr_errs or child_errs or other_errs or pruned_nodes
                    log_usage(actions['IMPORT_EML_XML_FILE'], filename, has_errors, model_has_complex_texttypes(eml_node))
                    save_both_formats(filename=package_name, eml_node=eml_node)
                    current_user.set_filename(filename=package_name)
                    # If we have errors...
                    if unknown_nodes or attr_errs or child_errs or other_errs or pruned_nodes:
                        # The parameters are actually lists, but Flask drops parameters that are empty lists, so what's passed are the
                        #  string representations.
                        return redirect(url_for(PAGE_IMPORT_XML_3,
                                                nsmap_changed=nsmap_changed,
                                                unknown_nodes=encode_for_query_string(unknown_nodes),
                                                attr_errs=encode_for_query_string(attr_errs),
                                                child_errs=encode_for_query_string(child_errs),
                                                other_errs=encode_for_query_string(other_errs),
                                                pruned_nodes=encode_for_query_string(pruned_nodes),
                                                filename=package_name,
                                                fetched=False))
                    else:
                        flash(f"Metadata for {package_name} was imported without errors")
                        return redirect(url_for(PAGE_IMPORT_XML_4, filename=package_name, fetched=False))
                else:
                    raise Exception  # TODO: Error handling
            except Exception as e:
                flash(e, 'error')

    # Process GET
    help = get_helps(['import_xml'])
    return render_template('import_xml.html', title='Import an XML File (XML)',
                           form=form, help=help)


@home_bp.route('/import_xml_2/<package_name>/<filename>', methods=['GET', 'POST'])
@home_bp.route('/import_xml_2/<package_name>/<filename>/<fetched>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def import_xml_2(package_name, filename, fetched=False):
    """Handle the Import EML File (XML)... item in the Import/Export menu after an XML file has been selected."""

    form = ImportPackageForm()

    # Process POST

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    if is_hidden_button():
        return redirect(url_for(handle_hidden_buttons(), filename=current_document))

    if request.method == 'POST' and form.validate_on_submit():
        form = request.form

        if form['replace_copy'] == 'copy':
            package_name = determine_package_name_for_copy(package_name)
        else:
            # We need to delete the existing package, if any, before we can import the new one.
            # We don't want old versions of data tables hanging around, for example.
            user_data.delete_package(package_name)

        user_path = user_data.get_user_folder_name()
        work_path = os.path.join(user_path, 'zip_temp')
        filepath = os.path.join(work_path, filename)

        try:
            # Parse the XML file and return errors, if any.
            eml_node, nsmap_changed, unknown_nodes, attr_errs, child_errs, other_errs, pruned_nodes = \
                parse_xml_file(filename, filepath)
            eml_node = strip_elements_added_by_pasta(package_name, eml_node)
            if qudt_annotations.remove_redundant_qudt_annotations(eml_node):
                flash('Redundant QUDT units annotations were found and removed')

            # We're done with the temp file
            utils.remove_zip_temp_folder()

            if eml_node:
                # save fact that EML was imported from XML in additional metadata
                add_imported_from_xml_metadata(eml_node, filename, package_name)
                has_errors = unknown_nodes or attr_errs or child_errs or other_errs or pruned_nodes
                log_usage(actions['IMPORT_EML_XML_FILE'], filename, has_errors, model_has_complex_texttypes(eml_node))
                save_both_formats(filename=package_name, eml_node=eml_node)
                current_user.set_filename(filename=package_name)

                if has_errors:
                    # The parameters are actually lists, but Flask drops parameters that are empty lists, so we pass the
                    #  string representations.
                    return redirect(url_for(PAGE_IMPORT_XML_3,
                                            nsmap_changed=nsmap_changed,
                                            unknown_nodes=encode_for_query_string(unknown_nodes),
                                            attr_errs=encode_for_query_string(attr_errs),
                                            child_errs=encode_for_query_string(child_errs),
                                            other_errs=encode_for_query_string(other_errs),
                                            pruned_nodes=encode_for_query_string(pruned_nodes),
                                            filename=package_name,
                                            fetched=fetched))

                else:
                    flash(f"Metadata for {package_name} was imported without errors")
                    return redirect(url_for(PAGE_IMPORT_XML_4, filename=package_name, fetched=fetched))
            else:
                raise Exception  # TODO: Error handling
        except Exception as e:
            flash(e, 'error')

    # Process GET
    help = get_helps(['import_xml_2'])
    return render_template('import_xml_2.html', title='Import an EML XML File',
                           package_name=package_name, form=form, help=help)


def get_data_size(filename):
    """Return the combined size of the data entities in MB. Used by import_xml_3 and import_xml_4."""
    try:
        scope, identifier, revision = filename.split('.')
        _, total = get_data_entity_sizes(scope, identifier, revision)
        kb, mb, gb = convert_file_size(total)
        return round(mb)
    except (AuthTokenExpired, Unauthorized):
        raise
    except Exception as e:
        return 0


@home_bp.route('/import_xml_3/<nsmap_changed>/<unknown_nodes>/<attr_errs>/<child_errs>/<other_errs>/<pruned_nodes>/<filename>/<fetched>',
            methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def import_xml_3(nsmap_changed=False, unknown_nodes=None, attr_errs=None, child_errs=None,
                 other_errs=None, pruned_nodes=None, filename=None, fetched=False):
    """ Handle reporting XML parsing errors after an XML file has been imported. """

    def construct_xml_error_descriptions(filename=None, unknown_nodes=None, attr_errs=None, child_errs=None,
                                         other_errs=None, pruned_nodes=None, unhandled_elements=None):
        """ Construct the HTML and text descriptions of the XML errors. HTML is displayed, text is available to
        be copied to the clipboard. """

        def display_list(err_html, err_text, ll, explanation):
            if ll:
                err_html += f"{explanation}<ul>"
                err_text += f"{explanation}\n"
                for node in ll:
                    err_html += f"<li>{node}"
                    err_text += f"   • {node}\n"
                err_html += "</ul><p>"
                err_text += "\n"
            return err_html, err_text

        def process_other_errors(filename, other_errs):
            # eml_node = load_eml(filename=filename)
            processed_errs = []
            for err in other_errs:
                if "Minimum occurrence" in err:
                    # We suppress this kind of error because it presumably results from nodes being pruned, and such
                    #  nodes will be covered by other errors reported to the user. This "Minimum occurrence" error
                    #  would be cryptic.
                    continue
                processed_errs.append(err)
            return processed_errs

        err_html = ''
        err_text = ''

        unknown_nodes = decode_from_query_string(unknown_nodes)
        attr_errs = decode_from_query_string(attr_errs)
        child_errs = decode_from_query_string(child_errs)
        other_errs = decode_from_query_string(other_errs)
        pruned_nodes = decode_from_query_string(pruned_nodes)

        err_html, err_text = display_list(err_html, err_text, unknown_nodes,
                                          "The following EML element types are unknown to ezEML, so they have been omitted:")

        excluded_nodes = set(unknown_nodes)

        processed_child_errs = []
        for err in child_errs:
            _, child_name, _, parent_name, *_ = err.split("'")
            if child_name not in unknown_nodes:
                excluded_nodes.add(child_name)
                processed_child_errs.append(f"{child_name} within {parent_name}")

        err_html, err_text = display_list(err_html, err_text, processed_child_errs,
                                          "The following EML elements occur in unexpected locations in the EML, so they have been omitted:")

        pruned_nodes = sorted(list(set(pruned_nodes) - excluded_nodes))
        excluded_nodes = excluded_nodes | set(pruned_nodes)

        err_html, err_text = display_list(err_html, err_text, pruned_nodes,
                                          f"The following EML elements been omitted because of errors:")

        insert1 = ' '
        insert2 = ' errors have'
        if len(excluded_nodes) > 1:
            insert1 = 'additional'
        other_errs = process_other_errors(filename, other_errs)
        if len(other_errs) == 1:
            insert2 = ' error has'
        err_html, err_text = display_list(err_html, err_text, other_errs,
                                          f"The following {insert1}{insert2} been detected:")

        if len(unhandled_elements) > 0:
            err_html, err_text = display_list(err_html, err_text, unhandled_elements,
                                              "The following EML element types are preserved by ezEML but are not exposed by the user interface. "
                                              "If you wish to edit any of these elements, you will need to use an XML editor:")

        err_heading = ""
        if len(excluded_nodes) > 0:
            err_heading = "<br>ezEML does not cover the complete EML standard. It imports as much of the EML " \
                          "as possible, but in this case it had to omit some EML elements.<p><br>"

        return err_html, err_text, err_heading

    form = EDIForm()

    # Process POST

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(url_for(PAGE_TITLE, filename=filename))

    if request.method == 'POST' and form.validate_on_submit():
        form = request.form

        try:
            total_size = import_data(filename, eml_node)
            log_usage(actions['GET_ASSOCIATED_DATA_FILES'], total_size)
        except (AuthTokenExpired, Unauthorized) as e:
            flash(AUTH_TOKEN_FLASH_MSG, 'error')
            help = get_helps(['import_xml_3'])
            # This code is used both for Fetch and Import, so we need to redirect to the right page in case of error.
            if not ast.literal_eval(fetched):
                return redirect(url_for('home.import_xml', form=form, help=help))
            else:
                return redirect(url_for('home.fetch_xml', form=form, help=help))
        except UnicodeDecodeErrorInternal as err:
            filepath = err.message
            errors = display_decode_error_lines(filepath)
            return render_template('encoding_error.html', filename=os.path.basename(filepath), errors=errors)
        except Exception as e:
            flash(f'Unable to fetch package data: {str(e)}', 'error')
            help = get_helps(['import_xml_3'])
            return redirect(url_for('home.import_xml', form=form, help=help))

        return redirect(url_for(PAGE_TITLE, filename=filename))

    # Process GET
    init_form_md5(form)

    unhandled_elements = package_contains_elements_unhandled_by_ezeml(filename, eml_node)

    err_html, err_text, err_heading = construct_xml_error_descriptions(filename, unknown_nodes, attr_errs,
                                                                       child_errs, other_errs, pruned_nodes,
                                                                       unhandled_elements)

    try:
        mb = get_data_size(filename)
        if mb > 100:
            mb = f' This package has <b>{mb} MB</b> of associated data.<br>&nbsp;'
        else:
            mb = ''
    except (AuthTokenExpired, Unauthorized) as e:
        flash(AUTH_TOKEN_FLASH_MSG, 'error')
        help = get_helps(['import_xml_3'])
        # This code is used both for Fetch and Import, so we need to redirect to the right page in case of error.
        if not ast.literal_eval(fetched):
            return redirect(url_for('home.import_xml', form=form, help=help))
        else:
            return redirect(url_for('home.fetch_xml', form=form, help=help))

    help = get_helps(['import_xml_3', 'complex_xml'])
    complex_xml = model_has_complex_texttypes(eml_node)

    return render_template('import_xml_3.html', err_html=err_html, err_text=err_text, err_heading=err_heading,
                           mb=mb, complex_xml=complex_xml, nsmap_changed=nsmap_changed, form=form, help=help)


@home_bp.route('/import_xml_4/<filename>/<fetched>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def import_xml_4(filename=None, fetched=False):
    """ Handle XML import/fetch in case with no XML parsing errors. """

    form = EDIForm()
    eml_node = load_eml(filename=filename)

    # Process POST

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(url_for(PAGE_TITLE, filename=filename))

    if request.method == 'POST' and form.validate_on_submit():
        form = request.form
        try:
            total_size = import_data(filename, eml_node)
        except (AuthTokenExpired, Unauthorized) as e:
            flash(AUTH_TOKEN_FLASH_MSG, 'error')
            help = get_helps(['import_xml_3'])
            # This code is used both for Fetch and Import, so we need to redirect to the right page in case of error.
            if not ast.literal_eval(fetched):
                return redirect(url_for('home.import_xml', form=form, help=help))
            else:
                return redirect(url_for('home.fetch_xml', form=form, help=help))
        except UnicodeDecodeErrorInternal as err:
            filepath = err.message
            errors = display_decode_error_lines(filepath)
            return render_template('encoding_error.html', filename=os.path.basename(filepath), errors=errors)
        except Exception as e:
            flash(f'Unable to fetch package data: {str(e)}', 'error')
            help = get_helps(['import_xml_3'])
            return redirect(url_for('home.import_xml', form=form, help=help))

        log_usage(actions['GET_ASSOCIATED_DATA_FILES'], total_size)
        return redirect(url_for(PAGE_TITLE, filename=filename))

    # Process GET
    init_form_md5(form)

    try:
        mb = get_data_size(filename)
        if mb > 100:
            mb = f' This package has <b>{mb} MB</b> of associated data.<br>&nbsp;'
        else:
            mb = ''
    except (AuthTokenExpired, Unauthorized) as e:
        flash(AUTH_TOKEN_FLASH_MSG, 'error')
        help = get_helps(['import_xml_3'])
        return redirect(url_for('home.import_xml', form=form, help=help))

    help = get_helps(['import_xml_3', 'complex_xml'])
    complex_xml = model_has_complex_texttypes(eml_node)
    return render_template('import_xml_4.html', mb=mb, complex_xml=complex_xml, form=form, help=help)


@home_bp.route('/fetch_xml/', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def fetch_xml():
    """Handle the Fetch a Package from EDI... item in the Import/Export menu."""

    form = EDIForm()

    # Process POST

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    if is_hidden_button():
        return redirect(url_for(handle_hidden_buttons(), filename=current_document))

    if request.method == 'POST' and BTN_CANCEL in request.form:
        filename = user_data.get_active_document()
        if filename:
            return redirect(url_for(PAGE_TITLE, filename=filename))
        else:
            return redirect(url_for(PAGE_INDEX))

    # Process GET
    init_form_md5(form)

    try:
        # Get a list of PASTA scopes
        ids = get_pasta_identifiers('')
    except (AuthTokenExpired, Unauthorized) as e:
        flash(AUTH_TOKEN_FLASH_MSG, 'error')
        help = get_helps(['fetch_from_edi'])
        return redirect(url_for('home.fetch_xml', form=form, help=help))

    # Create a list of links to fetch the identifiers for each scope
    package_links = ''
    parsed_url = urlparse(request.base_url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}/eml"
    for id in ids:
        new_link = f"{base_url}/fetch_xml_2/{id}"
        new_anchor = f'<br><a href="{new_link}">{id}</a>'
        package_links = package_links + new_anchor

    help = get_helps(['fetch_from_edi'])
    return render_template('fetch_xml.html', package_links=package_links, form=form, help=help)


@home_bp.route('/fetch_xml_2/<scope>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def fetch_xml_2(scope=''):
    """Handle the Fetch a Package from EDI... item in the Import/Export menu after a scope has been selected."""

    form = EDIForm()

    # Process POST

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    if request.method == 'POST' and BTN_CANCEL in request.form:
        filename = user_data.get_active_document()
        if filename:
            return redirect(url_for(PAGE_TITLE, filename=filename))
        else:
            return redirect(url_for(PAGE_INDEX))

    # Process GET
    init_form_md5(form)

    # Get a list of PASTA identifiers for the selected scope
    ids = get_pasta_identifiers(scope)

    # Create a list of links to fetch the revisions for each identifier, or the package if there is only one revision.
    package_links = ''
    parsed_url = urlparse(request.base_url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}/eml"
    for id in ids:
        new_link = f"{base_url}/fetch_xml_2a/{scope}.{id}"
        new_anchor = f'<br><a href="{new_link}">{scope}.{id}</a>'
        package_links = package_links + new_anchor

    help = get_helps(['fetch_from_edi'])
    return render_template('fetch_xml_2.html', package_links=package_links, form=form, help=help)


@home_bp.route('/fetch_xml_2a/<scope_identifier>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def fetch_xml_2a(scope_identifier=''):
    """
    Handle the Fetch a Package from EDI... item in the Import/Export menu after an identifier within scope
    has been selected. Determines if there are multiple revisions for the (scope, identifier) pair, and if so,
    displays a list of revisions to choose from. Otherwise, goes directly to the fetch_xml_3 page.
    """

    form = EDIForm()

    # Process POST

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    if request.method == 'POST' and BTN_CANCEL in request.form:
        filename = user_data.get_active_document()
        if filename:
            return redirect(url_for(PAGE_TITLE, filename=filename))
        else:
            return redirect(url_for(PAGE_INDEX))

    # Process GET
    init_form_md5(form)

    scope, identifier = scope_identifier.split('.')

    revisions = get_revisions_list(scope, identifier)
    if len(revisions) == 1:
        return redirect(url_for('home.fetch_xml_3', scope_identifier=scope_identifier, revision=revisions[0]))
    else:
        # There are multiple revisions. Display a list of revisions to choose from, each of which is a link to the
        #  page to fetch the package.
        package_links = ''
        parsed_url = urlparse(request.base_url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}/eml"
        for revision in revisions:
            new_link = f"{base_url}/fetch_xml_3/{scope}.{identifier}/{revision}"
            new_anchor = f'<br><a href="{new_link}">{revision}</a>'
            package_links = package_links + new_anchor

        help = get_helps(['fetch_from_edi'])
        return render_template('fetch_xml_2a.html', scope_identifier=scope_identifier, package_links=package_links, form=form, help=help)


@home_bp.route('/fetch_xml_3/<scope_identifier>/<revision>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def fetch_xml_3(scope_identifier='', revision=''):
    """
    Handle the Fetch a Package from EDI... item in the Import/Export menu after a package has been selected.

    It is here that the package is actually fetched from EDI.
    """

    form = EDIForm()

    # Process POST

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    if is_hidden_button():
        return redirect(url_for(handle_hidden_buttons(), filename=current_document))

    if request.method == 'POST' and BTN_CANCEL in request.form:
        filename = user_data.get_active_document()
        if filename:
            return redirect(url_for(PAGE_TITLE, filename=filename))
        else:
            return redirect(url_for(PAGE_INDEX))

    # Process GET
    init_form_md5(form)

    scope, identifier = scope_identifier.split('.')

    try:
        # Do the fetch.
        revision, metadata = get_metadata_revision_from_pasta(scope, identifier, revision)
        log_usage(actions['FETCH_FROM_EDI'], f"{scope}.{identifier}.{revision}")
    except (AuthTokenExpired, Unauthorized) as e:
        flash(AUTH_TOKEN_FLASH_MSG, 'error')
        help = get_helps(['import_xml_3'])
        return redirect(url_for('home.fetch_xml', form=form, help=help))
    except Exception as e:
        flash(f'Unable to fetch package {scope}.{identifier}: {str(e)}', 'error')
        help = get_helps(['import_xml_3'])
        return redirect(url_for('home.fetch_xml', form=form, help=help))

    # Save the metadata to a file in the user's zip_temp folder.
    filename = f"{scope}.{identifier}.{revision}.xml"
    user_data_dir = user_data.get_user_folder_name()
    work_path = os.path.join(user_data_dir, 'zip_temp')
    try:
        os.mkdir(work_path)
    except FileExistsError:
        pass
    save_path = os.path.join(work_path, filename)
    with open(save_path, 'wb') as metadata_file:
        metadata_file.write(metadata)

    package_base_filename = os.path.basename(filename)
    package_name = os.path.splitext(package_base_filename)[0]

    # See if package with that name already exists. If so, go to import_xml_2 page to allow user to choose
    #  whether to replace or make a copy.
    if package_name in user_data.get_user_document_list():
        return redirect(url_for('home.import_xml_2', package_name=package_name, filename=filename, fetched=True))

    # Parse the metadata file.
    user_data_dir = user_data.get_user_folder_name()
    work_path = os.path.join(user_data_dir, 'zip_temp')
    filepath = os.path.join(work_path, filename)

    try:
        eml_node, nsmap_changed, unknown_nodes, attr_errs, child_errs, other_errs, pruned_nodes = \
            parse_xml_file(filename, filepath)
        eml_node = strip_elements_added_by_pasta(package_name, eml_node)
        if qudt_annotations.remove_redundant_qudt_annotations(eml_node):
            flash('Redundant QUDT units annotations were found and removed')

        # We're done with the temp file
        utils.remove_zip_temp_folder()

        if eml_node:
            # save fact that EML was fetched from EDI in additional metadata
            add_fetched_from_edi_metadata(eml_node, package_name)
            add_imported_from_xml_metadata(eml_node, filename, package_name)
            save_both_formats(filename=package_name, eml_node=eml_node)
            current_user.set_filename(filename=package_name)
            if unknown_nodes or attr_errs or child_errs or other_errs or pruned_nodes:
                # The parameters are actually lists, but Flask drops parameters that are empty lists, so what's passed are the
                #  string representations.
                return redirect(url_for(PAGE_IMPORT_XML_3,
                                        nsmap_changed=nsmap_changed,
                                        unknown_nodes=encode_for_query_string(unknown_nodes),
                                        attr_errs=encode_for_query_string(attr_errs),
                                        child_errs=encode_for_query_string(child_errs),
                                        other_errs=encode_for_query_string(other_errs),
                                        pruned_nodes=encode_for_query_string(pruned_nodes),
                                        filename=package_name,
                                        fetched=True))
            else:
                flash(f"Metadata for {package_name} was imported without errors")
                return redirect(url_for(PAGE_IMPORT_XML_4, filename=package_name, fetched=True))
        else:
            raise Exception  # TODO: Error handling
    except Exception as e:
        flash(e, 'error')

    flash(f"Metadata for {package_name} was imported without errors")
    return redirect(url_for(PAGE_IMPORT_XML_4, filename=package_name, fetched=True))


@home_bp.route('/preview_data_portal', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def preview_data_portal():
    """Handle the Preview in EDI Data Portal item from the Import/Export menu."""
    form = EDIForm()

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    return render_template('preview_data_portal.html', form=form, help=get_helps(['preview_data_portal']))


@home_bp.route('/preview_data_portal_2', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def preview_data_portal_2():
    """Handle the Preview in EDI Data Portal item from the Import/Export menu."""
    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    current_document = current_user.get_filename()

    if request.method == 'GET':
        pathname = get_pathname(current_document, file_extension='xml')
        with open(pathname, 'rb') as f:
            xml = f.read()
            return xml
    return None


@home_bp.route('/import_package', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def import_package():
    """Handle the Import ezEML Data Package... item from the Import/Export menu."""

    form = ImportPackageForm()

    package_list = user_data.get_user_document_list()

    # Process POST

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    if request.method == 'POST' and form.validate_on_submit():

        # Check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)

        file = request.files['file']
        if file:
            filename = file.filename

            if not os.path.splitext(filename)[1] == '.zip':
                flash('Please select a file with file extension ".zip".', 'error')
                return redirect(request.url)

            package_base_filename = os.path.basename(filename)
            package_name = os.path.splitext(package_base_filename)[0]

            # See if package with that name already exists
            try:
                unversioned_package_name = upload_ezeml_package(file, package_name)
            except FileNotFoundError as err:
                # Manifest file is missing
                flash(f'The selected file does not appear to be a valid ezEML data package file. '
                      'Please select a different file or check with the package provider for a corrected file.',
                      'error')
                return redirect(request.url)
            except ValueError as err:
                # A bad checksum
                filename = err.args[0]
                flash(f'The selected package appears to have been modified manually outside of ezEML. '
                      'Please ask the package provider to provide a package file exported directly '
                      'from ezEML.', 'error')
                return redirect(request.url)

            if unversioned_package_name in user_data.get_user_document_list():
                # Package with that name already exists. Go to import_package_2 page to allow user to choose
                #  whether to replace or make a copy.
                return redirect(url_for('home.import_package_2', package_name=unversioned_package_name))
            else:
                # Package with that name does not exist. Import it.
                import_ezeml_package(unversioned_package_name)
                # fixup_upload_management()
                # Get rid of uploads not represented in the metadata.
                cull_uploads(unversioned_package_name)
                current_user.set_filename(filename=unversioned_package_name)
                log_usage(actions['IMPORT_EZEML_DATA_PACKAGE'])
                return redirect(url_for(PAGE_TITLE, filename=unversioned_package_name))

    # Process GET
    help = get_helps(['import_package'])
    return render_template('import_package.html', title='Import an ezEML Data Package',
                           packages=package_list, form=form, help=help)


@home_bp.route('/import_package_2/<package_name>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def import_package_2(package_name):
    """Handle the Import ezEML Data Package... item from the Import/Export menu after a file has been selected
    and a file with that filename already exists. Let the user choose whether to replace the existing file or
    make a copy of the new file."""

    form = ImportPackageForm()

    # Process POST

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    if request.method == 'POST' and form.validate_on_submit():
        form = request.form
        # If the user wants to copy the package, add a version number to the package name and copy the package
        # to the new name.
        if form['replace_copy'] == 'copy':
            package_name = copy_ezeml_package(package_name)

        # Perform the import.
        import_ezeml_package(package_name)
        # fixup_upload_management()
        # Get rid of uploads not represented in the metadata.
        cull_uploads(package_name)
        current_user.set_filename(filename=package_name)
        log_usage(actions['IMPORT_EZEML_DATA_PACKAGE'])
        return redirect(url_for(PAGE_TITLE, filename=package_name))

    # Process GET
    help = get_helps(['import_package_2'])
    return render_template('import_package_2.html', title='Import an ezEML Data Package',
                           package_name=package_name, form=form, help=help)


@home_bp.route('/get_data_file/', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def get_data_file():
    """
    This route is an admin tool for use by the EDI team to download an uploaded data file from any user's account.
    """
    if not (current_user and (current_user.is_admin() or current_user.is_data_curator())):
        flash('You are not authorized to use Download Data.', 'error')
        return render_template('index.html')

    form = SelectUserForm()

    if BTN_CANCEL in request.form:
        return redirect(url_for(PAGE_MANAGE_DATA_USAGE))

    if request.method == 'POST':
        user = form.user.data
        if user:
            return redirect(url_for('home.get_data_file_2', user=user))

    # Get the list of users
    user_data_dir = Config.USER_DATA_DIR
    filelist = glob.glob(f'{user_data_dir}/*')
    files = sorted([os.path.basename(x) for x in filelist if '-' in os.path.basename(x)], key=str.casefold)
    # print(files)
    form.user.choices = files
    return render_template('get_data_file.html', form=form)


@home_bp.route('/get_data_file_2/<user>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def get_data_file_2(user):
    """
    This route is an admin tool for use by the EDI team to download an uploaded data file from any user's account.
    """
    def download_data_file(filename: str = '', user: str = ''):
        if filename:
            user_data_dir = Config.USER_DATA_DIR
            filepath = f'{user_data_dir}/{user}/uploads/{filename}'
            return send_file(filepath, as_attachment=True, download_name=os.path.basename(filename))

    if not (current_user and (current_user.is_admin() or current_user.is_data_curator())):
        flash('You are not authorized to use Download Data.', 'error')
        return render_template('index.html')

    form = SelectDataFileForm()

    if BTN_CANCEL in request.form:
        return redirect(url_for(PAGE_MANAGE_DATA_USAGE))

    if request.method == 'POST':
        data_file = form.data_file.data
        # Get the data file
        if data_file:
            return download_data_file(data_file, user)

    # Get the list of data files for the user
    csv_list = []
    user_data_dir = Config.USER_DATA_DIR
    dir_list = glob.glob(f'{user_data_dir}/{user}/uploads/*')
    dirs = sorted(dir_list, key=str.casefold)
    for dir in dirs:
        if os.path.isdir(dir):
            _, dir_name = dir.split('uploads/')
            csv_paths = glob.glob(f'{dir}/*.csv')
            csvs = sorted([os.path.basename(x) for x in csv_paths], key=str.casefold)
            qualified_csvs = []
            for csv in csvs:
                qualified_csvs.append(f'{dir_name}/{csv}')
            csv_list.extend(qualified_csvs)
    form.data_file.choices = csv_list
    return render_template('get_data_file_2.html', form=form)


@home_bp.route('/get_eml_file/', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def get_eml_file():
    """
    This route is an admin tool for use by the EDI team to download an EML file from any user's account.
    """
    if not (current_user and (current_user.is_admin() or current_user.is_data_curator())):
        flash('You are not authorized to use Download EML (XML and JSON).', 'error')
        return render_template('index.html')

    form = SelectUserForm()

    if BTN_CANCEL in request.form:
        return redirect(url_for(PAGE_MANAGE_DATA_USAGE))

    if request.method == 'POST':
        user = form.user.data
        if user:
            return redirect(url_for('home.get_eml_file_2', user=user))

    # Get the list of users
    user_data_dir = Config.USER_DATA_DIR
    filelist = glob.glob(f'{user_data_dir}/*')
    files = sorted([os.path.basename(x) for x in filelist if '-' in os.path.basename(x)], key=str.casefold)
    # print(files)
    form.user.choices = files
    return render_template('get_eml_file.html', form=form)


@home_bp.route('/get_eml_file_2/<user>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def get_eml_file_2(user):
    """
    This route is an admin tool for use by the EDI team to download an EML file from any user's account.
    """
    def download_eml_file(filename: str = '', user: str = ''):
        if filename:
            # We will create and download a zip file with both the xml and json files
            edi_user_folder = user_data.get_user_folder_name()
            user_folder = os.path.join(Config.USER_DATA_DIR, user)
            basename = os.path.splitext(os.path.basename(filename))[0]
            xml_file_pathname = os.path.join(user_folder, basename) + '.xml'
            json_file_pathname = os.path.join(user_folder, basename) + '.json'
            zip_file_workpath = os.path.join(edi_user_folder, 'zip_temp')
            try:
                os.mkdir(zip_file_workpath)
            except FileExistsError:
                pass
            zip_file_pathname = os.path.join(zip_file_workpath, basename) + '.zip'
            zip_object = ZipFile(zip_file_pathname, 'w')
            if os.path.exists(xml_file_pathname):
                zip_object.write(xml_file_pathname, arcname=basename + '.xml')
            else:
                log_info(f'File not found: {xml_file_pathname}')
            if os.path.exists(json_file_pathname):
                zip_object.write(json_file_pathname, arcname=basename + '.json')
            else:
                log_info(f'File not found: {json_file_pathname}')
            zip_object.close()
            return send_file(zip_file_pathname, as_attachment=True, download_name=basename + '.zip')

    if not (current_user and (current_user.is_admin() or current_user.is_data_curator())):
        flash('You are not authorized to use Download EML (XML and JSON).', 'error')
        return render_template('index.html')

    form = SelectEMLFileForm()

    if BTN_CANCEL in request.form:
        return redirect(url_for(PAGE_MANAGE_DATA_USAGE))

    if request.method == 'POST':
        eml_file = form.eml_file.data
        if eml_file:
            # Get the data file
            return download_eml_file(eml_file, user)

    # Get the list of eml files for the user
    user_data_dir = Config.USER_DATA_DIR
    xml_files = glob.glob(f'{user_data_dir}/{user}/*.xml')
    xml_files = sorted([os.path.basename(x) for x in xml_files], key=str.casefold)
    form.eml_file.choices = xml_files
    return render_template('get_eml_file_2.html', form=form)


@home_bp.route('/get_collaboration_database/', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def get_collaboration_database():
    """
    This route is an admin tool for use by the EDI team to download the database used to track collaboration status.
    """
    if not (current_user and (current_user.is_admin() or current_user.is_data_curator())):
        flash('You are not authorized to download the collaboration database.', 'error')
        return render_template('index.html')

    db_pathname = os.path.join(Config.USER_DATA_DIR, '__db', 'collaborations.db.sqlite3')
    return send_file(db_pathname, as_attachment=True, download_name='collaborations.db.sqlite3')


@home_bp.route('/get_curator_workflow_database/', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def get_curator_workflow_database():
    """
    This route is an admin tool for use by the EDI team to download the database used to track curator workflow status.
    """
    if not (current_user and (current_user.is_admin() or current_user.is_data_curator())):
        flash('You are not authorized to download the curator workflow database.', 'error')
        return render_template('index.html')

    db_pathname = os.path.join(Config.USER_DATA_DIR, '__db', 'curator_workflows.db.sqlite3')
    return send_file(db_pathname, as_attachment=True, download_name='curator_workflows.db.sqlite3')


@home_bp.route('/reupload_data_with_col_names_changed/<saved_filename>/<dt_node_id>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def reupload_data_with_col_names_changed(saved_filename, dt_node_id):
    """
    When a user uploads a data table with column names that are different from the original data table, we need to
     get confirmation from the user that they are aware of this and want to proceed.
    """

    form = LoadDataForm()
    document = current_user.get_filename()

    if request.method == 'POST':

        if BTN_CANCEL in request.form:
            return redirect(get_back_url())

        if BTN_CONTINUE in request.form:
            return redirect(url_for(PAGE_REUPLOAD, filename=document, dt_node_id=dt_node_id, saved_filename=saved_filename, name_chg_ok=True), code=307) # 307 keeps it a POST

        help = get_helps(['data_table_reupload_full'])
        return render_template('reupload_data_with_col_names_changed.html', title='Re-upload Data Table',
                               form=form, saved_filename=saved_filename, dt_node_id=dt_node_id, help=help)


@home_bp.route('/reupload_other_entity/<filename>/<node_id>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def reupload_other_entity(filename, node_id):
    """
    Route to handle reupload of an other data entity.
    """

    form = LoadOtherEntityForm()
    document = current_user.get_filename()
    uploads_folder = user_data.get_document_uploads_folder_name()
    eml_node = load_eml(filename=document)

    other_entity_name = ''
    oe_node = Node.get_node_instance(node_id)
    if oe_node:
        entity_name_node = oe_node.find_child(names.ENTITYNAME)
        if entity_name_node:
            other_entity_name = entity_name_node.content
            if not other_entity_name:
                raise ValueError("Other entity's name not found")

    if request.method == 'POST' and BTN_CANCEL in request.form:
        url = url_for(PAGE_OTHER_ENTITY_SELECT, filename=filename)
        return redirect(url)

    if request.method == 'POST':
        return redirect(url_for(PAGE_LOAD_OTHER_ENTITY, node_id=node_id), code=307) # 307 keeps it a POST

    help = get_helps(['other_entity_reupload'])
    return render_template('reupload_other_entity.html', title='Re-upload Other Entity',
                           form=form, name=other_entity_name, help=help)


@home_bp.route('/load_other_entity/<node_id>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def load_entity(node_id=None):
    """
    Route to handle uploading of an other data entity.
    """

    form = LoadOtherEntityForm()
    uploads_folder = user_data.get_document_uploads_folder_name()

    document, eml_node = reload_metadata()  # So check_metadata status is correct

    # Process POST
    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    if request.method == 'POST' and form.validate_on_submit():
        # Check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)

        file = request.files['file']
        if file:
            filename = file.filename

            if filename is None or filename == '':
                flash('No selected file', 'error')
            else:
                doing_reupload = node_id is not None and node_id != '1'
                eml_node = load_eml(filename=document)

                # Make sure we don't already have a data table or other entity with this name
                if not data_filename_is_unique(eml_node, filename, node_id):
                    flash('The selected name has already been used in this data package. Names of data tables and other entities must be unique within a data package.', 'error')
                    return redirect(request.url)

                filename = validate_filename(filename)
                file.save(os.path.join(validate_user_data_path(uploads_folder), filename))
                data_file = filename
                flash(f'Loaded {data_file}')
                dataset_node = eml_node.find_child(names.DATASET)
                other_entity_node = load_other_entity(dataset_node, uploads_folder, data_file, node_id=node_id)

                if not doing_reupload:
                    log_usage(actions['LOAD_OTHER_ENTITY'], data_file)
                else:
                    log_usage(actions['RE_UPLOAD_OTHER_ENTITY'], data_file)

                clear_distribution_url(other_entity_node)
                insert_upload_urls(document, eml_node)

                save_both_formats(filename=document, eml_node=eml_node)
                return redirect(url_for(PAGE_OTHER_ENTITY, filename=document, node_id=other_entity_node.id))

    # Process GET
    return render_template('load_other_entity.html', title='Load Other Entity',
                           form=form)


def close_document():
    current_user.set_filename(None)
    user_login = current_user.get_user_login()
    close_package(user_login)
    set_current_page('')


@home_bp.route('/close', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def close():
    current_document = current_user.get_filename()

    if is_hidden_button():
        return redirect(url_for(handle_hidden_buttons(), filename=current_document))

    log_usage(actions['CLOSE_DOCUMENT'])
    close_document()
    aux_msg = request.args.get('aux_msg', '')
    if current_document:
        flash(f'Closed "{current_document}". {aux_msg}')

    set_current_page('')

    return render_template('index.html')


def remove_from_uploads(filename):
    package_name = user_data.get_active_document()
    uploads_dir = user_data.get_user_uploads_folder_name()
    uploaded_file = os.path.join(uploads_dir, package_name, filename)

    filelist = glob.glob(f'{uploaded_file}*')  # We want to get the eval file, if any, as well
    for f in filelist:
        log_info(f'Removing file {f}')
        utils.remove(f)


def select_post(filename=None, form=None, form_dict=None,
                method=None, this_page=None, back_page=None, 
                next_page=None, edit_page=None, project_node_id=None, reupload_page=None,
                import_page=None, import_target=None, rp_node_id=None):

    def extract_ids(key):
        if '|' not in key:
            node_id = key
            secondary_node_id = None
        else:
            node_id, secondary_node_id = key.split('|')
            if secondary_node_id == 'None':
                secondary_node_id = None
        return node_id, secondary_node_id

    node_id = None
    new_page = None

    if form_dict:
        for key in form_dict:
            val = breaking(form_dict[key][0])  # value is the first list element
            if val in (BTN_BACK, BTN_DONE):
                new_page = back_page
            elif val[0:4] == BTN_BACK:
                node_id = project_node_id
                new_page = back_page
            elif val in [BTN_NEXT, BTN_SAVE_AND_CONTINUE]:
                node_id = project_node_id
                new_page = next_page
            elif val == BTN_EDIT:
                new_page = edit_page
                node_id, secondary_node_id = extract_ids(key)
            elif val == BTN_REMOVE:
                new_page = this_page
                node_id, secondary_node_id = extract_ids(key)
                eml_node = load_eml(filename=filename)
                # Get the data table filename, if any, so we can remove it from the uploaded list
                node = Node.get_node_instance(node_id)
                if node and node.name == names.DATATABLE:
                    object_name_node = node.find_single_node_by_path([names.PHYSICAL, names.OBJECTNAME])
                    if object_name_node:
                        object_name = object_name_node.content
                        if object_name:
                            user_data.discard_data_table_upload_filename(object_name)
                            remove_from_uploads(object_name)
                remove_child(node)
                # node_id = project_node_id  # for relatedProject case
                save_both_formats(filename=filename, eml_node=eml_node)
            elif val == BTN_PREVIEW:
                new_page = 'cov.preview_geographic_coverage'
                node_id, _ = extract_ids(key)
            elif val == BTN_REUPLOAD:
                node_id, secondary_node_id = extract_ids(key)
                if reupload_page:
                    new_page = reupload_page
                else:
                    # node_id = key
                    new_page = PAGE_REUPLOAD
            elif val == BTN_SAVE_CHANGES:
                # We'll go back to the same page with the same URL, minus the ui_element_id query string, if any
                url = request.url
                return url_without_ui_element_id_query_string(url)
            elif val == UP_ARROW:
                new_page = this_page
                node_id, secondary_node_id = extract_ids(key)
                process_up_button(filename, node_id)
            elif val == DOWN_ARROW:
                new_page = this_page
                node_id, secondary_node_id = extract_ids(key)
                process_down_button(filename, node_id)
            elif val[0:3] == BTN_ADD:
                new_page = edit_page
                if node_id is None:
                    node_id = '1'
            elif val[0:6] == BTN_IMPORT:
                new_page = import_page
                if node_id is None:
                    node_id = '1'
            elif val == BTN_LOAD_ASSOCIATED_PARTIES:
                new_page = PAGE_LOAD_RESPONSIBLE_PARTIES
                node_name = names.ASSOCIATEDPARTY
                node_id = '1'
            elif val == BTN_LOAD_CONTACTS:
                new_page = PAGE_LOAD_RESPONSIBLE_PARTIES
                node_name = names.CONTACT
                node_id = '1'
            elif val == BTN_LOAD_CREATORS:
                new_page = PAGE_LOAD_RESPONSIBLE_PARTIES
                node_name = names.CREATOR
                node_id = '1'
            elif val == BTN_LOAD_METADATA_PROVIDERS:
                new_page = PAGE_LOAD_RESPONSIBLE_PARTIES
                node_name = names.METADATAPROVIDER
                node_id = '1'
            elif val == BTN_LOAD_DATA_TABLE:
                new_page = PAGE_LOAD_DATA
                node_id = '1'
            elif val == BTN_LOAD_GEO_COVERAGE:
                new_page = PAGE_LOAD_GEO_COVERAGE
                node_id = '1'
            elif val == BTN_LOAD_TAXONOMIC_COVERAGE:
                new_page = PAGE_LOAD_TAXONOMIC_COVERAGE
            elif val == BTN_LOAD_OTHER_ENTITY:
                new_page = PAGE_LOAD_OTHER_ENTITY
                node_id = '1'
            elif val == BTN_REUSE:
                new_page = PAGE_IMPORT_PARTY
                node_id = '1'
            new_page = check_val_for_hidden_buttons(val, new_page)
            if new_page:
                break

    if form.validate_on_submit():
        if new_page in [PAGE_DATA_TABLE, PAGE_LOAD_DATA, PAGE_REUPLOAD, PAGE_REUPLOAD_WITH_COL_NAMES_CHANGED ]:
            return url_for(new_page, filename=filename, dt_node_id=node_id, project_node_id=project_node_id)
        elif new_page in [PAGE_DATA_SOURCE, PAGE_DATA_SOURCE_PERSONNEL]:
            return url_for(new_page, filename=filename, ms_node_id=node_id, data_source_node_id=secondary_node_id)
        elif new_page in [PAGE_FUNDING_AWARD_SELECT, PAGE_PROJECT]:
            return url_for(new_page, filename=filename, project_node_id=project_node_id)
        elif new_page in [PAGE_PROJECT_PERSONNEL, PAGE_PROJECT_PERSONNEL_SELECT]:
            return url_for(new_page, filename=filename, node_id=node_id, project_node_id=project_node_id)
        elif new_page == PAGE_IMPORT_PARTIES:
            return url_for(new_page, filename=filename, target=import_target)
        elif new_page == PAGE_LOAD_RESPONSIBLE_PARTIES:
            return url_for(new_page, filename=filename, node_name=node_name)
        else:
            if new_page is None:
                # url_for would raise an exception... log debug info
                vals = []
                for key in form_dict:
                    vals.append(form_dict[key][0])  # value is the first list element
                new_page = PAGE_INDEX  # so we don't raise a general error exception
            return url_for(new_page, filename=filename, node_id=node_id)


def process_up_button(filename:str=None, node_id:str=None):
    def move_up(parent_node: Node, child_node: Node):
        if parent_node and child_node:
            parent_node.shift(child_node, Shift.LEFT)

    process_updown_button(filename, node_id, move_up)


def process_down_button(filename:str=None, node_id:str=None):
    def move_down(parent_node: Node, child_node: Node):
        if parent_node and child_node:
            parent_node.shift(child_node, Shift.RIGHT)

    process_updown_button(filename, node_id, move_down)


def process_updown_button(filename:str=None, node_id:str=None, move_function=None):
    if filename and node_id and move_function:
        eml_node = load_eml(filename=filename)
        child_node = Node.get_node_instance(node_id)
        if child_node:
            parent_node = child_node.parent
            if parent_node:
                move_function(parent_node, child_node)
                save_both_formats(filename=filename, eml_node=eml_node)


def compare_begin_end_dates(begin_date_str:str=None, end_date_str:str=None):
    begin_date = None
    end_date = None
    flash_msg = None

    if len(begin_date_str) == 4:
        begin_date_str += '-01-01'

    if len(end_date_str) == 4:
        end_date_str += '-01-01'

    if begin_date and end_date and begin_date > end_date:
        flash_msg = 'Begin date should be less than or equal to end date'

    if end_date:
        today_date = date.today()
        if end_date > today_date:
            msg = "End date should not be greater than today's date"
            if flash_msg:
                flash_msg += ";  " + msg
            else:
                flash_msg = msg 

    return flash_msg


def set_current_page(page):
    """Set the current page so it can be highlighted in the Contents menu."""
    from inspect import getframeinfo, stack
    caller = getframeinfo(stack()[1][0])
    # import webapp.home.home_utils as home_utils
    # home_utils.log_info(f'{caller.filename} @ line {caller.lineno} - set_current_page: {page}')

    session['current_page'] = page


def get_current_page():
    """Return the current page, for example to redirect back to it."""
    import webapp.home.home_utils as home_utils
    page = session.get('current_page')
    # home_utils.log_info(f'get_current_page: {page}')
    return session.get('current_page')


AnnotationEntry = collections.namedtuple(
    'AnnotationEntry',
    ["column_name", "unit_in_metadata", "qudt_label", "qudt_code", "link", "attribute_node_id"])


@home_bp.route('/review_qudt_annotations/<filename>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def review_qudt_annotations(filename):
    from webapp.home.utils.qudt_annotations import available_qudt_annotations
    """
    Route to display the QUDT Units Annotations in the model.
    """
    eml_node = load_eml(filename)

    qudt_annotations = available_qudt_annotations(eml_node, filename)

    help = get_helps(['qudt_units_annotations', 'reject_qudt_annotations'])
    return render_template('review_qudt_annotations.html', filename=filename, annotations=qudt_annotations, help=help)


@home_bp.route('/reject_qudt_annotation/<filename>/<annotation_id>/<qudt_label>/<qudt_code>', methods=['GET', 'POST'])
@login_required
def reject_qudt_annotation(filename, annotation_id, qudt_label, qudt_code):
    from webapp.home.utils.qudt_annotations import set_annotation_action
    eml_node = load_eml(filename)
    annotation_node = Node.get_node_instance(annotation_id)
    attribute_node = annotation_node.parent
    set_annotation_action(attribute_node.id, True)
    annotation_node.parent.remove_child(annotation_node)
    Node.delete_node_instance(annotation_id)
    try:
        attribute_name_node = attribute_node.find_child(names.ATTRIBUTENAME)
        attribute_name = attribute_name_node.content or ''
        data_table_node = attribute_node.parent.parent
        entity_name_node = data_table_node.find_child(names.ENTITYNAME)
        data_table_name = entity_name_node.content
        log_usage(actions['QUDT_REJECT'], data_table_name, attribute_name, qudt_label, qudt_code)
    except:
        pass
    save_both_formats(filename=filename, eml_node=eml_node)
    return redirect(url_for(PAGE_REVIEW_QUDT_ANNOTATIONS, filename=filename))


@home_bp.route('/accept_qudt_annotation/<filename>/<attribute_id>/<qudt_label>/<qudt_code>', methods=['GET', 'POST'])
@login_required
def accept_qudt_annotation(filename, attribute_id, qudt_label, qudt_code):
    from webapp.home.utils.qudt_annotations import set_annotation_action, add_qudt_annotations
    eml_node = load_eml(filename)
    try:
        attribute_node = Node.get_node_instance(attribute_id)
        attribute_name_node = attribute_node.find_child(names.ATTRIBUTENAME)
        attribute_name = attribute_name_node.content or ''
        data_table_node = attribute_node.parent.parent
        entity_name_node = data_table_node.find_child(names.ENTITYNAME)
        data_table_name = entity_name_node.content
        log_usage(actions['QUDT_ACCEPT'], data_table_name, attribute_name, qudt_label, qudt_code)
    except:
        pass
    set_annotation_action(attribute_id, False)
    add_qudt_annotations(eml_node)
    save_both_formats(filename=filename, eml_node=eml_node)
    return redirect(url_for(PAGE_REVIEW_QUDT_ANNOTATIONS, filename=filename))


@home_bp.route('/reject_all_qudt_annotations/<filename>/<data_table_node_id>', methods=['GET', 'POST'])
@login_required
def reject_all_qudt_annotations(filename, data_table_node_id):
    from webapp.home.utils.qudt_annotations import reject_all_qudt_annotations
    eml_node = load_eml(filename)
    try:
        data_table_node = Node.get_node_instance(data_table_node_id)
        entity_name_node = data_table_node.find_child(names.ENTITYNAME)
        data_table_name = entity_name_node.content
        log_usage(actions['QUDT_REJECT_ALL'], data_table_name)
    except:
        pass
    if reject_all_qudt_annotations(eml_node, data_table_node_id):
        save_both_formats(filename=filename, eml_node=eml_node)
    return redirect(url_for(PAGE_REVIEW_QUDT_ANNOTATIONS, filename=filename))


@home_bp.route('/accept_all_qudt_annotations/<filename>/<data_table_node_id>', methods=['GET', 'POST'])
@login_required
def accept_all_qudt_annotations(filename, data_table_node_id):
    from webapp.home.utils.qudt_annotations import accept_all_qudt_annotations
    eml_node = load_eml(filename)
    try:
        data_table_node = Node.get_node_instance(data_table_node_id)
        entity_name_node = data_table_node.find_child(names.ENTITYNAME)
        data_table_name = entity_name_node.content
        log_usage(actions['QUDT_ACCEPT_ALL'], data_table_name)
    except:
        pass
    if accept_all_qudt_annotations(eml_node, data_table_node_id):
        save_both_formats(filename=filename, eml_node=eml_node)
    return redirect(url_for(PAGE_REVIEW_QUDT_ANNOTATIONS, filename=filename))


@home_bp.route('/validate_eml', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def validate_eml():
    """
    Route to handle validating an EML file.
    """

    form = ValidateEMLFileForm()

    uploads_folder = os.path.join(validate_user_data_path(user_data.get_user_uploads_folder_name()), '__tmpdir__')
    Path(uploads_folder).mkdir(parents=True, exist_ok=True)

    document, eml_node = reload_metadata()  # So check_metadata status is correct

    # Process POST
    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    if request.method == 'POST':
        if 'Validate' in request.form:
            # We're validating the currently active document
            user_folder = user_data.get_user_folder_name(current_user_directory_only=False)
            current_document = user_data.get_active_document()
            if current_document:
                filename = f'{current_document}.xml'
                pathname = f'{user_folder}/{filename}'
                if os.path.exists(pathname):
                    return redirect(url_for(PAGE_VALIDATE_EML_2, filename=filename, active='True'))
                else:
                    return redirect(url_for(PAGE_VALIDATE_EML))

        # Check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)

        file = request.files['file']
        if file:
            filename = validate_filename(file.filename)

            if filename is None or filename == '':
                flash('No selected file', 'error')
            else:
                # Delete old tmp files... We don't want to delete the new one even after the validation, in case
                #  the user refreshes the validate_eml_2 page. It'll get deleted next time around.
                pattern = os.path.join(uploads_folder, "*.xml.tmp")
                files = glob.glob(pattern)
                for f in files:
                    os.remove(f)

                file.save(os.path.join(uploads_folder, filename + '.tmp'))

                log_usage(actions['VALIDATE_EML'], filename)

                return redirect(url_for(PAGE_VALIDATE_EML_2, filename=filename))

    # Process GET
    help = get_helps(['validate_xml'])
    return render_template('validate_eml.html', title='Validate an EML File', form=form, help=help)


def parse_and_validate(pathname=None, parse_only=False):
    # This would be contained in validate_eml_2 except that it is also called by check_metadata, in which
    #  case parse_only == True, since check_metadata handles schema errors.
    with open(validate_user_data_path(pathname), 'r') as f:
        xml = f.read()

    schema_path = validator.schema_path()

    if "https://eml.ecoinformatics.org/eml-2.2.0" in xml:
        schema = schema_path + "/EML2.2.0/xsd/eml.xsd"
    elif "eml://ecoinformatics.org/eml-2.1.1" in xml:
        schema = schema_path + "/EML2.1.1/eml.xsd"
    elif "eml://ecoinformatics.org/eml-2.1.0" in xml:
        schema = schema_path + "/EML2.1.0/eml.xsd"
    else:
        raise ValueError("Cannot determine EML schema")

    v = Validator(schema)
    validation_errs = []
    if not parse_only:
        try:
            v.validate(xml)
        except ValidationError as e:
            errors = e.args[0]
            for error in errors:
                line = error.line
                cause = error.message.replace('\n', '\\n')
                validation_errs.append((line, cause))

        except XMLSyntaxError as e:
            pass

    p = Parser()
    parse_errs = []
    try:
        p.parse(xml)
    except (ParseError, ParserError, ValueError, XIncludeError, XMLSchemaParseError, XMLSyntaxError, etree.XMLSyntaxError) as e:
        errors = str(e.args[0]).split('\n')
        for error in errors:
            e_parts = [p.strip() for p in error.split(':', 1)]
            try:
                details = ','.join(ast.literal_eval(e_parts[1]))
            except:
                if len(e_parts) > 1:
                    details = e_parts[1]
                else:
                    details = None
            parse_errs.append((e_parts[0], details))

    unicodes = ui.unicode_list(xml)

    return validation_errs, parse_errs, unicodes


@home_bp.route('/validate_eml_2/<filename>', methods=['GET', 'POST'])
@home_bp.route('/validate_eml_2/<filename>/<active>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def validate_eml_2(filename, active=False):
    def parse_error_message(input_string):
        parts = input_string.split(':')

        line_number = parts[1]

        # Find the sixth colon
        count = 0
        for index, char in enumerate(input_string):
            if char == ':':
                count += 1
                if count == 6:
                    break

        error = input_string[index + 2:]

        # Find the first colon not inside a pair of quotes or braces
        inside_quotes = False
        inside_braces = False
        for index, char in enumerate(error):
            if char == '"':
                inside_quotes = not inside_quotes
            elif char == '{':
                inside_braces = True
            elif char == '}':
                inside_braces = False
            elif char == ':' and not inside_quotes and not inside_braces:
                break
        element_name = error[:index]
        error_message = error[index + 2:]
        return line_number, element_name, error_message

    form = EDIForm()

    pathname = None
    if not active == 'True':
        uploads_folder = os.path.join(user_data.get_user_uploads_folder_name(), '__tmpdir__')
        Path(uploads_folder).mkdir(parents=True, exist_ok=True)
        pathname = os.path.join(uploads_folder, filename + '.tmp')
    else:
        user_folder = user_data.get_user_folder_name(current_user_directory_only=False)
        current_document = user_data.get_active_document()
        if current_document:
            filename = f'{current_document}.xml'
            pathname = f'{user_folder}/{filename}'

    validation_errs, parse_errs, unicodes = parse_and_validate(pathname)

    if active == 'True':
        help = get_helps(['validate_xml', 'unicode_characters_active'])
    else:
        help = get_helps(['validate_xml', 'unicode_characters'])

    reload_metadata()
    return render_template('validate_eml_2.html', form=form, help=help, filename=filename,
                           validation_errs=validation_errs, parse_errs=parse_errs, unicodes=unicodes)


"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
Code below is no longer used. Keeping it around in case we change our minds...
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""

@home_bp.route('/slow_poke')
def slow_poke():
    """
    This is a dummy page that was used to test multi-threading. It is no longer used.
    """
    import time
    from datetime import datetime
    entry = datetime.now()
    entry_time = entry.strftime("%H:%M:%S")
    time.sleep(60)
    user_name = current_user.get_username()
    current_packageid = current_user.get_filename()
    pid = os.getpid()
    metapype_store_size = len(Node.store)
    leaving = datetime.now()
    leaving_time = leaving.strftime("%H:%M:%S")

    return render_template('slow_poke.html', user=user_name, package=current_packageid, pid=pid,
                           store_size=metapype_store_size, entry=entry_time, leaving=leaving_time)


@home_bp.route('/import_temporal_coverage', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def import_temporal_coverage():
    """Handle the Import Temporal Coverage item in Import/Export menu. Not currently used."""

    raise DeprecatedCodeError('import_temporal_coverage()')

    form = ImportEMLForm()
    form.filename.choices = list_data_packages(False, False)
    form.template.choices = list_templates()

    # Process POST
    if request.method == 'POST':
        if BTN_CANCEL in request.form:
            return redirect(get_back_url())
            # new_page = get_redirect_target_page()
            # url = url_for(new_page, filename=current_user.get_filename())
            # return redirect(url)
        if form.validate_on_submit():
            filename = form.filename.data or current_user.get_filename()
            template = form.template.data
            is_template = 'Open Template' in request.form
            return redirect(url_for('home.import_temporal_coverage_2', filename=filename, template=quote(template, safe=''), is_template=is_template))

    # Process GET
    return render_template('import_temporal_coverage.html', form=form)


@home_bp.route('/import_temporal_coverage_2/<filename>/', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def import_temporal_coverage_2(filename):
    """Handle the Import Temporal Coverage item in Import/Export menu after a source document has been selected.
    Not currently used."""

    raise DeprecatedCodeError('import_temporal_coverage_2()')

    def get_temporal_coverages_for_import(eml_node):
        coverages = []
        for node in eml_node.find_all_nodes_by_path([names.DATASET, names.COVERAGE, names.TEMPORALCOVERAGE]):
            label = compose_full_gc_label(node)  # FIXME
            coverages.append((f'{label}', node.id))
        return coverages

    form = ImportItemsForm()

    eml_node = load_eml(filename)
    coverages = get_temporal_coverages_for_import(eml_node)
    choices = [[coverage[1], coverage[0]] for coverage in coverages]
    form.to_import.choices = choices

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    if form.validate_on_submit():
        node_ids_to_import = form.data['to_import']
        target_package = current_user.get_filename()
        import_coverage_nodes(target_package, node_ids_to_import)
        return redirect(url_for(PAGE_TEMPORAL_COVERAGE_SELECT, filename=target_package))

    # Process GET
    return render_template('import_temporal_coverage_2.html', target_filename=filename, title='Import Metadata',
                           form=form)


@home_bp.route('/submit_package', methods=['GET', 'POST'])
@home_bp.route('/submit_package/<filename>', methods=['GET', 'POST'])
@home_bp.route('/submit_package/<filename>/<success>', methods=['GET', 'POST'])
@login_required
def submit_package(filename=None, success=None):
    """Handle the former version of Submit to EDI page. Not currently used."""

    raise DeprecatedCodeError('submit_package()')

    def submit_package_mail_body(name=None, email_address=None, archive_name=None, encoded_url=None,
                                 encoded_url_without_data=None, notes=None):
        # Note: get_shortened_url handles blanks
        msg = 'Dear EDI Data Curator:' + '\n\n' + \
              'This email was auto-generated by ezEML.\n\n\n' + \
              'Please submit the following data package to the EDI data repository.\n\n' + \
              '   Sender\'s name: ' + name + '\n\n' + \
              '   Sender\'s email: ' + email_address + '\n\n' + \
              '   Package name: ' + archive_name + '\n\n' + \
              '   Download URL: ' + encoded_url + '\n\n' + \
              '   Download URL without data files: ' + encoded_url_without_data + '\n\n'
        if notes:
            msg += '   Sender\'s Notes: ' + notes
        return msg

    form = SubmitToEDIForm()

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct
    if not current_document:
        return redirect(url_for(PAGE_INDEX))

    if form.validate_on_submit():
        # If the user has clicked Save in the EML Documents menu, for example, we want to ignore the
        #  programmatically generated Submit
        if request.form.get(BTN_SUBMIT) == BTN_SUBMIT_TO_EDI:
            name = form.data['name']
            email_address = form.data['email_address']
            notes = form.data['notes']

            save_both_formats(filename=current_document, eml_node=eml_node)

            try:
                zipfile_path = zip_package(current_document, eml_node)
                zipfile_path_without_data = zip_package(current_document, eml_node, include_data=False)
            except ezEMLError as e:
                flash(str(e), 'error')
                return redirect(get_back_url(success=False))

            if zipfile_path and zipfile_path_without_data:
                _, _, encoded_url = save_as_ezeml_package_export(zipfile_path)
                _, _, encoded_url_without_data = save_as_ezeml_package_export(zipfile_path_without_data)

                msg = submit_package_mail_body(name, email_address, current_document, encoded_url,
                                               encoded_url_without_data, notes)
                msg += get_fetched_from_edi_metadata(eml_node)
                msg += get_imported_from_xml_metadata(eml_node)
                subject = 'ezEML-Generated Data Submission Request'
                to_address = [Config.TO]
                sent = mimemail.send_mail(subject=subject, msg=msg, to=to_address)
                if sent is True:
                    log_usage(actions['SEND_TO_EDI'], name, email_address)
                    flash(f'Package "{current_document}" has been sent to EDI. We will notify you when it has been added to the repository.')
                    flash(f"If you don't hear back from us within 48 hours, please contact us at support@edirepository.org.")
                    success = True
                else:
                    log_usage(actions['SEND_TO_EDI'], 'failed')
                    flash(sent, 'error')

            return redirect(get_back_url(success=success))

    set_current_page('submit_package')
    help = get_helps(['submit_package', 'submit_package_success'])
    return render_template('submit_package.html',
                           title='Send to EDI',
                           check_metadata_status=get_check_metadata_status(eml_node, current_document),
                           form=form, help=help, success=success)


@home_bp.route('/send_to_other/<filename>/', methods=['GET', 'POST'])
@home_bp.route('/send_to_other/<filename>/<mailto>/', methods=['GET', 'POST'])
@login_required
def send_to_other(filename=None, mailto=None):

    raise DeprecatedCodeError('send_to_other()')

    def send_to_other_email(name, email_address, title, url):
        name_quoted = quote(name)
        email_address_quoted = quote(email_address)
        title_quoted = quote(title)
        # We want to use the tinyurl version of the url, but we don't want to fail altogether if tinyurl.com is
        #  temporarily unavailable
        try:
            tiny_url = make_tiny(url)  # Note: it is assumed the URL has not been encoded
        except requests.exceptions.HTTPError as err:
            # Something's wrong with tinyurl.com
            log_error('make_tiny() failed with error: {err}')
            tiny_url = url
        msg_quoted = f'mailto:{email_address_quoted}?subject=ezEML-Generated%20Data%20Package&body=Dear%20{name_quoted}%3A%0D%0A%0D%0A' \
                     f'I%20have%20created%20a%20data%20package%20containing%20EML%20metadata%20and%20associated%20data%20files%20' \
                     f'for%20your%20inspection.%0D%0A%0D%0ATitle%3A%20%22{title_quoted}%22%0D%0A%0D%0AThe%20data%20package%20is%20' \
                     f'available%20for%20download%20here%3A%20{tiny_url}%0D%0A%0D%0AThe%20package%20was%20created%20using%20ezEML.%20' \
                     f'After%20you%20download%20the%20package%2C%20you%20can%20import%20it%20into%20ezEML%2C%20or%20you%20can%20' \
                     f'unzip%20it%20to%20extract%20the%20EML%20file%20and%20associated%20data%20files%20to%20work%20with%20them%20' \
                     f'directly.%0D%0A%0D%0ATo%20learn%20more%20about%20ezEML%2C%20go%20to%20https%3A%2F%2Fezeml.edirepository.org.' \
                     f'%0D%0A%0D%0AThanks!'
        msg_html = Markup(f'Dear {name}:<p><br>'
                          f'I have created a data package containing EML metadata and associated data files '
                          f'for your inspection.<p>Title: "{title}"<p>The data package is '
                          f'available for download here: {tiny_url}.<p>The package was created using ezEML. '
                          f'After you download the package, you can import it into ezEML, or you can '
                          f'unzip it to extract the EML file and associated data files to work with them '
                          f'directly.<p>To learn more about ezEML, go to https://ezeml.edirepository.org.'
                          f'<p>Thanks!')
        msg_raw = f'Dear {name}:\n\n' \
                  f'I have created a data package containing EML metadata and associated data files ' \
                  f'for your inspection.\n\nTitle: "{title}"\n\nThe data package is ' \
                  f'available for download here: {tiny_url}.\n\nThe package was created using ezEML. ' \
                  f'After you download the package, you can import it into ezEML, or you can ' \
                  f'unzip it to extract the EML file and associated data files to work with them ' \
                  f'directly.\n\nTo learn more about ezEML, go to https://ezeml.edirepository.org.' \
                  f'\n\nThanks!'
        return msg_quoted, msg_html, msg_raw

    form = SendToColleagueForm()

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct
    if not current_document:
        return redirect(url_for(PAGE_INDEX))

    if form.validate_on_submit():
        # If the user has clicked Save in the EML Documents menu, for example, we want to ignore the
        #  programmatically generated Submit
        if request.form.get(BTN_SUBMIT) == BTN_SEND_TO_OTHER:

            colleague_name = form.data['colleague_name']
            email_address = form.data['email_address']

            eml_node = load_eml(filename=filename)
            log_usage(actions['SEND_TO_COLLEAGUE'], colleague_name, email_address)

            dataset_node = eml_node.find_child(child_name=names.DATASET)
            title_node = dataset_node.find_child(names.TITLE)
            title = ''
            if title_node:
                title = title_node.content
            if not title:
                # The GET path will display an error message saying the title is required
                return redirect(get_back_url())

            try:
                zipfile_path = zip_package(current_document, eml_node)
            except ezEMLError as e:
                flash(str(e), 'error')
                print(redirect(get_back_url()))
                return redirect(get_back_url())

            _, download_url, _ = save_as_ezeml_package_export(zipfile_path)

            if not mailto:
                mailto, mailto_html, mailto_raw = send_to_other_email(colleague_name, email_address, title, download_url)
            else:
                mailto = None  # so we don't pop up the email client when the page is returned to after sending the 1st time
                mailto_html = None
                mailto_raw=None

    eml_node = load_eml(filename=filename)
    title_node = eml_node.find_single_node_by_path([names.DATASET, names.TITLE])
    if not title_node or not title_node.content:
        flash('The data package must have a Title before it can be sent.', 'error')

    set_current_page('send_to_other')
    if mailto:
        form.colleague_name.data = ''
        form.email_address.data = ''
        help = get_helps(['send_to_colleague_2'])
        return render_template('send_to_other_2.html',
                               title='Send to Other',
                               mailto=mailto,
                               mailto_html=mailto_html,
                               mailto_raw=mailto_raw,
                               check_metadata_status=get_check_metadata_status(eml_node, current_document),
                               form=form, help=help)
    else:
        help = get_helps(['send_to_colleague'])
        return render_template('send_to_other.html',
                               title='Send to Other',
                               check_metadata_status=get_check_metadata_status(eml_node, current_document),
                               form=form, help=help)


@home_bp.route('/load_metadata', methods=['GET', 'POST'])
@login_required
def load_metadata():
    raise DeprecatedCodeError('load_metadata()')

    def allowed_metadata_file(filename):
        """Only certain file types are allowed to be uploaded as metadata files."""
        ALLOWED_EXTENSIONS = set(['xml'])
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    def read_xml(xml: str = None):
        eml_node = None
        if xml:
            try:
                eml_node = mp_io.from_xml(xml)
            except Exception as e:
                logger.error(e)
                raise Exception(f"Error parsing XML: {e}")
        else:
            raise Exception("No XML string provided")

        return eml_node

    form = LoadMetadataForm()
    document = current_user.get_filename()
    uploads_folder = user_data.get_document_uploads_folder_name()

    # Process POST
    if request.method == 'POST' and form.validate_on_submit():
        # Check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)

        file = request.files['file']
        if file:
            # TODO: Possibly reconsider whether to use secure_filename in the future. It would require
            #  separately keeping track of the original filename and the possibly modified filename.
            # filename = secure_filename(file.filename)
            # filename = file.filename
            filename = secure_filename(file.filename)

            if filename is None or filename == '':
                flash('No selected file', 'error')
            elif allowed_metadata_file(filename):
                Path(uploads_folder).mkdir(parents=True, exist_ok=True)
                file.save(os.path.join(uploads_folder, filename))
                metadata_file = filename
                metadata_file_path = f'{uploads_folder}/{metadata_file}'
                with open(metadata_file_path, 'r') as file:
                    metadata_str = file.read()
                    try:
                        eml_node = read_xml(metadata_str)
                    except Exception as e:
                        flash(e, 'error')
                    if eml_node:
                        packageid = eml_node.attribute_value('packageId')
                        if packageid:
                            current_user.set_packageid(packageid)
                            save_both_formats(filename=filename, eml_node=eml_node)
                            return redirect(url_for(PAGE_TITLE, filename=filename))
                        else:
                            flash(f'Unable to determine packageid from file {filename}', 'error')
                    else:
                        flash(f'Unable to load metadata from file {filename}', 'error')
            else:
                flash(f'{filename} is not a supported data file type', 'error')
                return redirect(request.url)
    # Process GET
    return render_template('load_metadata.html', title='Load Metadata',
                           form=form)


# def clean_zip_temp_files(days, user_dir, logger, logonly):
#     # Remove zip_temp files that are more than 'days' days old
#     today = datetime.today()
#     zip_temp_dir = os.path.join(user_dir, 'zip_temp')
#     if os.path.exists(zip_temp_dir) and os.path.isdir(zip_temp_dir):
#         for file in os.listdir(zip_temp_dir):
#             filepath = os.path.join(zip_temp_dir, file)
#             t = os.stat(filepath).st_mtime
#             filetime = today - datetime.fromtimestamp(t)
#             if filetime.days >= days:
#                 try:
#                     logger.info(f'Removing file {filepath}')
#                     if not logonly:
#                         if not os.path.isdir(filepath):
#                             os.remove(filepath)
#                         else:
#                             rmtree(filepath, ignore_errors=True)
#                 except FileNotFoundError:
#                     pass


# @home_bp.before_app_first_request
# def cleanup_zip_temp_folders():
#     if not Config.GC_CLEAN_ZIP_TEMPS_ON_STARTUP:
#         return
#     # get the user directories
#     base = Config.USER_DATA_DIR
#     for dir in os.listdir(base):
#         if os.path.isdir(os.path.join(base, dir)):
#             if dir.startswith('.'):
#                 continue
#
#             # got a user directory
#             user_dir = os.path.join(base, dir)
#
#             days = Config.GC_ZIP_TEMPS_DAYS_TO_LIVE
#             logonly = Config.GC_LOG_ONLY
#             clean_zip_temp_files(days, user_dir, logger, logonly)


# @home_bp.before_app_first_request
# def fixup_upload_management():
#     return
#     USER_DATA_DIR = 'user-data'
#     to_delete = set()
#     # loop on the various users' data directories
#     for user_folder_name in os.listdir(USER_DATA_DIR):
#         if user_folder_name == 'uploads' or user_folder_name == 'zip_temp':
#             continue
#         if os.path.isdir(os.path.join(USER_DATA_DIR, user_folder_name)):
#             user_data.clear_data_table_upload_filenames(user_folder_name)
#             full_path = os.path.join(USER_DATA_DIR, user_folder_name)
#             uploads_path = os.path.join(full_path, 'uploads')
#             # look at the EML model json files
#             for file in os.listdir(full_path):
#                 full_file = os.path.join(full_path, file)
#                 if os.path.isfile(full_file) and full_file.lower().endswith('.json') and file != '__user_properties__.json':
#                     # some directories may have obsolete 'user_properties.json' files
#                     if file == 'user_properties.json':
#                         to_delete.add(os.path.join(full_path, 'user_properties.json'))
#                         continue
#                     # create a subdir of the user's uploads directory for this document's uploads
#                     document_name = file[:-5]
#                     subdir_name = os.path.join(uploads_path, document_name)
#                     try:
#                         os.mkdir(subdir_name)
#                     except OSError:
#                         pass
#                     # open the model file
#                     with open(full_file, "r") as json_file:
#                         json_obj = json.load(json_file)
#                         eml_node = mp_io.from_json(json_obj)
#                     # look at data tables
#                     data_table_nodes = []
#                     eml_node.find_all_descendants(names.DATATABLE, data_table_nodes)
#                     for data_table_node in data_table_nodes:
#                         object_name_node = data_table_node.find_descendant(names.OBJECTNAME)
#                         if object_name_node:
#                             object_name = object_name_node.content
#                             object_path = os.path.join(uploads_path, object_name)
#                             target_path = os.path.join(subdir_name, object_name)
#                             if os.path.isfile(object_path):
#                                 to_delete.add(object_path)
#                                 copyfile(object_path, target_path)
#                     # look at other entities
#                     other_entity_nodes = []
#                     eml_node.find_all_descendants(names.OTHERENTITY, other_entity_nodes)
#                     for other_entity_node in other_entity_nodes:
#                         object_name_node = other_entity_node.find_descendant(names.OBJECTNAME)
#                         if object_name_node:
#                             object_name = object_name_node.content
#                             object_path = os.path.join(uploads_path, object_name)
#                             if os.path.isfile(object_path):
#                                 to_delete.add(object_path)
#                                 copyfile(object_path, os.path.join(subdir_name, object_name))
#                     # clean up temp files
#                     for path in os.listdir(subdir_name):
#                         path = os.path.join(subdir_name, path)
#                         if os.path.isfile(path) and path.endswith('ezeml_tmp'):
#                             to_delete.add(path)
#
#             # now capture all uploaded file names in the user data
#             for file in os.listdir(uploads_path):
#                 uploads_folder = os.path.join(uploads_path, file)
#                 if os.path.isdir(uploads_folder):
#                     # add the uploaded files to the user data
#                     for uploaded_file in os.listdir(uploads_folder):
#                         user_data.add_data_table_upload_filename(uploaded_file, user_folder_name, file)
#
#             # clean up temp files
#             for path in os.listdir(full_path):
#                 path = os.path.join(full_path, path)
#                 if os.path.isfile(path) and path.endswith('ezeml_tmp'):
#                     to_delete.add(path)
#
#     # now we can delete the files we've copied
#     for file in to_delete:
#         os.remove(file)


# @home_bp.route('/download', methods=['GET', 'POST'])
# @login_required
# def download():
#     form = DownloadEMLForm()
#     form.filename.choices = list_data_packages(True, True)
#
#     # Process POST
#     if form.validate_on_submit():
#         filename = form.filename.data
#         return_value = user_data.download_eml(filename=filename)
#         if isinstance(return_value, str):
#             flash(return_value)
#         else:
#             return return_value
#     # Process GET
#     return render_template('download_eml.html', title='Download EML',
#                            form=form)