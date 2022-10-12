#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: views.py

:Synopsis:

:Author:
    costa
    servilla
    ide

:Created:
    7/23/18
"""
import ast
import daiquiri
from datetime import date, datetime
import glob
import html
import json
import math
import os
import os.path
import pandas as pd
from pathlib import Path
import pickle
import requests
from requests_file import FileAdapter
from shutil import copyfile
from urllib.parse import urlencode, urlparse, quote, unquote
from zipfile import ZipFile


from flask import (
    Blueprint, flash, render_template, redirect, request, url_for,
    session, Markup, jsonify, send_file
)

from flask_login import (
    current_user, login_required
)

from flask import Flask, current_app

import webapp.mimemail as mimemail

from webapp.config import Config

import csv

from webapp.home.exceptions import (
    ezEMLError,
    AuthTokenExpired,
    DataTableError,
    MissingFileError,
    Unauthorized,
    UnicodeDecodeErrorInternal
)

from webapp.home.forms import ( 
    CreateEMLForm, DownloadEMLForm, ImportPackageForm,
    OpenEMLDocumentForm, DeleteEMLForm, SaveAsForm,
    LoadDataForm, LoadMetadataForm, LoadOtherEntityForm,
    ImportEMLForm, ImportEMLItemsForm,
    ImportItemsForm, ImportSingleItemForm,
    SubmitToEDIForm, SendToColleagueForm, EDIForm,
    SelectUserForm, SelectDataFileForm, SelectEMLFileForm
)

from webapp.home.load_data import (
    load_data_table, load_other_entity, delete_data_files, get_md5_hash
)
from webapp.home.import_package import (
    copy_ezeml_package, upload_ezeml_package, import_ezeml_package, cull_uploads
)
from webapp.home.import_xml import (
    save_xml_file, parse_xml_file, determine_package_name
)
from webapp.home.log_usage import (
    actions,
    log_usage,
)

from webapp.home.metapype_client import ( 
    load_eml, save_both_formats, new_child_node, remove_child, create_eml,
    move_up, move_down, UP_ARROW, DOWN_ARROW, RELEASE_NUMBER,
    save_old_to_new, read_xml, new_child_node, truncate_middle,
    compose_rp_label, compose_full_gc_label, compose_taxonomic_label,
    compose_funding_award_label, compose_project_label, list_data_packages,
    import_responsible_parties, import_coverage_nodes, import_funding_award_nodes,
    import_project_node, import_related_project_nodes, get_check_metadata_status,
    handle_hidden_buttons, check_val_for_hidden_buttons,
    add_fetched_from_edi_metadata, get_fetched_from_edi_metadata,
    add_imported_from_xml_metadata, get_imported_from_xml_metadata,
    clear_taxonomy_imported_from_xml, taxonomy_imported_from_xml,
    is_hidden_button, handle_hidden_buttons
)

import webapp.home.check_data_table_contents as check_data_table_contents
from webapp.home.check_data_table_contents import format_date_time_formats_list
from webapp.home.check_metadata import check_eml
from webapp.home.forms import form_md5

from webapp.buttons import *
from webapp.pages import *

from metapype.eml import names
from metapype.model import mp_io
from metapype.model.node import Node
from werkzeug.utils import secure_filename

from webapp.home.import_data import (
    import_data, get_pasta_identifiers, get_newest_metadata_revision_from_pasta,
    get_data_entity_sizes, convert_file_size
)

import webapp.views.data_tables.dt as dt
import webapp.auth.user_data as user_data
from webapp.home.texttype_node_processing import (
    check_xml_validity,
    invalid_xml_error_message,
    is_valid_xml_fragment,
    model_has_complex_texttypes
)

logger = daiquiri.getLogger('views: ' + __name__)
home = Blueprint('home', __name__, template_folder='templates')
help_dict = {}
keywords = {}

AUTH_TOKEN_FLASH_MSG = 'Authorization to access data was denied. This can be caused by a login timeout. Please log out, log back in, and try again.'


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


def non_breaking(_str):
    return _str.replace(' ', html.unescape('&nbsp;'))


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
    current_document = current_user.get_filename()
    if not current_document:
        # if we've just deleted the current document, it won't exist
        return redirect(url_for(PAGE_INDEX))
    # Call load_eml here to get the check_metadata status set correctly
    eml_node = load_eml(filename=current_document)
    return current_document, eml_node


# Endpoint for AJAX calls to validate XML
@home.route('/check_xml/<xml>/<parent_name>', methods=['GET'])
def check_xml(xml:str=None, parent_name:str=None):
    response = check_xml_validity(xml, parent_name)
    log_usage(actions['CHECK_XML'], parent_name, response)
    response = jsonify({"response": response})
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response


# Endpoint for AJAX calls to log help usage
@home.route('/log_help_usage/<help_id>', methods=['GET'])
def log_help_usage(help_id:str=None):
    log_usage(actions['HELP'], help_id)
    response = jsonify({"response": 'OK'})
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response


# Endpoint for AJAX calls to log User Guide usage
@home.route('/log_user_guide_usage/<title>', methods=['GET'])
def log_user_guide_usage(title:str=None):
    log_usage(actions['USER_GUIDE'], title)
    response = jsonify({"response": 'OK'})
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response


# Endpoint for AJAX calls to log login usage
@home.route('/log_login_usage/<login_type>', methods=['GET'])
def log_login_usage(login_type:str=None):
    log_usage(actions['LOGIN'], login_type)
    response = jsonify({"response": 'OK'})
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response


# Endpoint for REST Service to get a list of a data table's columns and their variable types
# Note that this returns the names as they are defined in the metadata, not the names as they are displayed in the table
@home.route('/get_data_table_columns/', methods=['GET','POST'])
def get_data_table_columns():
    eml_file_url = request.headers.get('eml_file_url')
    data_table_name = request.headers.get('data_table_name')
    data_table_node = check_data_table_contents.find_data_table_node(eml_file_url, data_table_name)
    columns = check_data_table_contents.get_data_table_columns(data_table_node)
    response = jsonify({"columns": columns})
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response


# Endpoint for REST Service to check a data table's CSV file
@home.route('/check_data_table/', methods=['POST'])
def check_data_table():
    eml_file_url = request.headers.get('eml_file_url')
    csv_file_url = request.headers.get('csv_file_url')
    data_table_name = request.headers.get('data_table_name')
    column_names = request.headers.get('column_names').split(',')
    return check_data_table_contents.check_data_table(eml_file_url, csv_file_url, data_table_name, column_names)


@home.route('/data_table_errors/<data_table_name>', methods=['GET', 'POST'])
@login_required
def data_table_errors(data_table_name:str=None):
    current_document = user_data.get_active_document()
    if not current_document:
        raise FileNotFoundError

    if is_hidden_button():
        new_page = handle_hidden_buttons(PAGE_DATA_TABLE_ERRORS, PAGE_DATA_TABLE_ERRORS)
        return redirect(url_for(new_page, filename=current_document))

    eml_node = load_eml(filename=current_document)
    data_table_nodes = []
    eml_node.find_all_descendants(names.DATATABLE, data_table_nodes)
    data_table_node = None
    for _data_table_node in data_table_nodes:
        if check_data_table_contents.get_data_table_name(_data_table_node) == data_table_name:
            data_table_node = _data_table_node
            break
    if not data_table_node:
        raise ValueError  # TODO: use custom exception

    eml_file_url = check_data_table_contents.get_eml_file_url(current_document, eml_node)
    csv_file_url = check_data_table_contents.get_csv_file_url(current_document, data_table_node)
    csv_filename = check_data_table_contents.get_data_table_filename(data_table_node)
    csv_filepath = check_data_table_contents.get_csv_filepath(current_document, csv_filename)
    data_table_size = check_data_table_contents.get_data_table_size(data_table_node)

    metadata_hash = check_data_table_contents.hash_data_table_metadata_settings(eml_node, data_table_name)

    errors = check_data_table_contents.get_data_file_eval(current_document, csv_filename, metadata_hash)
    if not errors:
        try:
            # start = datetime.now()
            errors = check_data_table_contents.check_data_table(eml_file_url, csv_file_url, data_table_name,
                                                                max_errs_per_column=None)
            # end = datetime.now()
            # elapsed = (end - start).total_seconds()
            # print(elapsed)
        except UnicodeDecodeError:
            errors = display_decode_error_lines(csv_filepath)
            return render_template('encoding_error.html', filename=os.path.basename(csv_filepath), errors=errors)
        except Exception as err:
            flash(err, 'error')
            help = get_helps(['data_table_errors'])
            return render_template('data_table_errors.html', data_table_name=data_table_name, column_errs='', help=help, back_url=get_back_url())

    column_errs, has_blanks = check_data_table_contents.generate_error_info_for_webpage(data_table_node, errors)
    column_errs = check_data_table_contents.collapse_error_info_for_webpage(column_errs)

    check_data_table_contents.save_data_file_eval(current_document, csv_filename, metadata_hash, errors)
    check_data_table_contents.set_check_data_tables_badge_status(current_document, eml_node)
    help = get_helps(['data_table_errors'])
    return render_template('data_table_errors.html',
                           data_table_name=data_table_name,
                           column_errs=column_errs,
                           has_blanks=has_blanks,
                           help=help,
                           back_url=get_back_url())


@home.before_app_request
def init_session_vars():
    if not session.get("check_metadata_status"):
        session["check_metadata_status"] = "green"
    if not session.get("check_data_tables_status"):
        session["check_data_tables_status"] = "green"
    if not session.get("privileged_logins"):
        session["privileged_logins"] = Config.PRIVILEGED_LOGINS


@home.before_app_first_request
def fixup_upload_management():
    return
    USER_DATA_DIR = 'user-data'
    to_delete = set()
    # loop on the various users' data directories
    for user_folder_name in os.listdir(USER_DATA_DIR):
        if user_folder_name == 'uploads' or user_folder_name == 'zip_temp':
            continue
        if os.path.isdir(os.path.join(USER_DATA_DIR, user_folder_name)):
            user_data.clear_data_table_upload_filenames(user_folder_name)
            full_path = os.path.join(USER_DATA_DIR, user_folder_name)
            uploads_path = os.path.join(full_path, 'uploads')
            # look at the EML model json files
            for file in os.listdir(full_path):
                full_file = os.path.join(full_path, file)
                if os.path.isfile(full_file) and full_file.lower().endswith('.json') and file != '__user_properties__.json':
                    # some directories may have obsolete 'user_properties.json' files
                    if file == 'user_properties.json':
                        to_delete.add(os.path.join(full_path, 'user_properties.json'))
                        continue
                    # create a subdir of the user's uploads directory for this document's uploads
                    document_name = file[:-5]
                    subdir_name = os.path.join(uploads_path, document_name)
                    try:
                        os.mkdir(subdir_name)
                    except OSError:
                        pass
                    # open the model file
                    with open(full_file, "r") as json_file:
                        json_obj = json.load(json_file)
                        eml_node = mp_io.from_json(json_obj)
                    # look at data tables
                    data_table_nodes = []
                    eml_node.find_all_descendants(names.DATATABLE, data_table_nodes)
                    for data_table_node in data_table_nodes:
                        object_name_node = data_table_node.find_descendant(names.OBJECTNAME)
                        if object_name_node:
                            object_name = object_name_node.content
                            object_path = os.path.join(uploads_path, object_name)
                            target_path = os.path.join(subdir_name, object_name)
                            if os.path.isfile(object_path):
                                to_delete.add(object_path)
                                copyfile(object_path, target_path)
                    # look at other entities
                    other_entity_nodes = []
                    eml_node.find_all_descendants(names.OTHERENTITY, other_entity_nodes)
                    for other_entity_node in other_entity_nodes:
                        object_name_node = other_entity_node.find_descendant(names.OBJECTNAME)
                        if object_name_node:
                            object_name = object_name_node.content
                            object_path = os.path.join(uploads_path, object_name)
                            if os.path.isfile(object_path):
                                to_delete.add(object_path)
                                copyfile(object_path, os.path.join(subdir_name, object_name))
                    # clean up temp files
                    for path in os.listdir(subdir_name):
                        path = os.path.join(subdir_name, path)
                        if os.path.isfile(path) and path.endswith('ezeml_tmp'):
                            to_delete.add(path)

            # now capture all uploaded file names in the user data
            for file in os.listdir(uploads_path):
                uploads_folder = os.path.join(uploads_path, file)
                if os.path.isdir(uploads_folder):
                    # add the uploaded files to the user data
                    for uploaded_file in os.listdir(uploads_folder):
                        user_data.add_data_table_upload_filename(uploaded_file, user_folder_name, file)

            # clean up temp files
            for path in os.listdir(full_path):
                path = os.path.join(full_path, path)
                if os.path.isfile(path) and path.endswith('ezeml_tmp'):
                    to_delete.add(path)

    # now we can delete the files we've copied
    for file in to_delete:
        os.remove(file)


@home.before_app_request
def load_eval_entries():
    if session.get('__eval__title_01'):
        return
    rows = []
    with open('webapp/static/evaluate.csv') as csv_file:
        csv_reader = csv.reader(csv_file)
        for row in csv_reader:
            rows.append(row)
    for row_num in range(1, len(rows)):
        id, *vals = rows[row_num]
        session[f'__eval__{id}'] = vals


@home.before_app_request
def init_keywords():
    if keywords:
        return
    lter_keywords = pickle.load(open('webapp/static/lter_keywords.pkl', 'rb'))
    keywords['LTER'] = lter_keywords


def get_keywords(which):
    return keywords.get(which, [])


@home.before_app_request
def init_help():
    if help_dict:
        if not session.get('__help__contents'):
            # special case for supporting base.html template
            session['__help__contents'] = help_dict.get('contents')
        return

    with open('webapp/static/help.txt') as help:
        lines = help.readlines()
    index = 0

    def get_help_item(lines, index):
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
        (id, title, content), index = get_help_item(lines, index)
        help_dict[id] = (title, content)
        if id == 'contents':
            # special case for supporting base.html template
            session[f'__help__{id}'] = (title, content)


def get_help(id):
    title, content = help_dict.get(id)
    return f'__help__{id}', title, content


def get_helps(ids):
    helps = []
    for id in ids:
        if id in help_dict:
            title, content = help_dict.get(id)
            helps.append((f'__help__{id}', title, content))
    return helps


@home.route('/')
def index():
    if current_user.is_authenticated:
        current_document = user_data.get_active_document()
        if current_document:
            eml_node = load_eml(filename=current_document)
            if eml_node:
                new_page = PAGE_TITLE
            else:
                user_data.remove_active_file()
                new_page = PAGE_FILE_ERROR
            return redirect(url_for(new_page, filename=current_document))
    return render_template('index.html')


@home.route('/edit/<page>')
def edit(page:str=None):
    '''
    The edit page allows for direct editing of a top-level element such as
    title, abstract, creators, etc. This function simply redirects to the
    specified page, passing the packageid as the only parameter.
    '''
    if current_user.is_authenticated and page:
        current_filename = user_data.get_active_document()
        if current_filename:
            # We skip metadata check here because we will do load_eml again on the target page
            eml_node = load_eml(filename=current_filename, skip_metadata_check=True)
            new_page = page if eml_node else PAGE_FILE_ERROR
            return redirect(url_for(new_page, filename=current_filename))
    return render_template('index.html')


def get_back_url():
    url = url_for(PAGE_INDEX)
    if current_user.is_authenticated:
        new_page = get_redirect_target_page()
        filename = user_data.get_active_document()
        if new_page and filename:
            url = url_for(new_page, filename=filename)
    return url


@home.route('/about')
def about():
    return render_template('about.html', back_url=get_back_url(), title='About')


@home.route('/user_guide')
def user_guide():
    # Logging usage of User Guide is done via AJAX endpoint log_user_guide_usage
    return render_template('user_guide.html', back_url=get_back_url(), title='User Guide')


@home.route('/news')
def news():
    return render_template('news.html', back_url=get_back_url(), title="What's New")


@home.route('/restore_welcome_dialog')
def restore_welcome_dialog():
    return render_template('restore_welcome_dialog.html', back_url=get_back_url())


@home.route('/encoding_error/<filename>')
def encoding_error(filename=None, errors=None):
    return render_template('encoding_error.html', filename=filename, errors=errors, title='Encoding Errors')


@home.route('/file_error/<filename>')
def file_error(filename=None):
    return render_template('file_error.html', filename=filename, title='File Error')


@home.route('/delete', methods=['GET', 'POST'])
@login_required
def delete():
    form = DeleteEMLForm()
    form.filename.choices = list_data_packages(True, True)

    # Process POST
    if request.method == 'POST':
        if 'Cancel' in request.form:
            return redirect(get_back_url())
        if form.validate_on_submit():
            filename = form.filename.data
            user_data.discard_data_table_upload_filenames_for_package(filename)
            return_value = user_data.delete_eml(filename=filename)
            log_usage(actions['DELETE_DOCUMENT'], filename)
            if filename == user_data.get_active_document():
                current_user.set_filename(None)
            if isinstance(return_value, str):
                flash(return_value)
            else:
                flash(f'Deleted {filename}')
            return redirect(url_for(PAGE_INDEX))

    # Process GET
    return render_template('delete_eml.html', title='Delete EML',
                           form=form)


@home.route('/save', methods=['GET', 'POST'])
@login_required
def save():
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


def copy_uploads(from_package, to_package):
    from_folder = user_data.get_document_uploads_folder_name(from_package)
    to_folder = user_data.get_document_uploads_folder_name(to_package)
    for filename in os.listdir(from_folder):
        from_path = os.path.join(from_folder, filename)
        to_path = os.path.join(to_folder, filename)
        copyfile(from_path, to_path)
        user_data.add_data_table_upload_filename(filename, document_name=to_package)


@home.route('/save_as', methods=['GET', 'POST'])
@login_required
def save_as():
    # Determine POST type
    if request.method == 'POST':
        if BTN_SAVE in request.form:
            submit_type = 'Save'
        elif BTN_CANCEL in request.form:
            submit_type = 'Cancel'
        else:
            submit_type = None
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
                flash(return_value)
                new_filename = current_document  # Revert back to the old filename
            else:
                copy_uploads(current_document, new_document)
                log_usage(actions['SAVE_AS_DOCUMENT'], new_document)
                current_user.set_filename(filename=new_document)
                flash(f'Saved as {new_document}')
            new_page = PAGE_TITLE   # Return the Response object

            return redirect(url_for(new_page, filename=new_document))
        # else:
        #     return redirect(url_for(PAGE_SAVE_AS, filename=current_filename))

     # Process GET
    if current_document:
        # form.filename.data = current_filename
        help = get_helps(['save_as_document'])
        return render_template('save_as.html',
                               filename=current_document,
                               title='Save As',
                               form=form,
                               help=help)
    else:
        flash("No document currently open")
        return render_template('index.html')


@home.route('/download', methods=['GET', 'POST'])
@login_required
def download():
    form = DownloadEMLForm()
    form.filename.choices = list_data_packages(True, True)

    # Process POST
    if form.validate_on_submit():
        filename = form.filename.data
        return_value = user_data.download_eml(filename=filename)
        if isinstance(return_value, str):
            flash(return_value)
        else:
            return return_value
    # Process GET
    return render_template('download_eml.html', title='Download EML', 
                           form=form)


@home.route('/check_data_tables', methods=['GET', 'POST'])
@login_required
def check_data_tables():
    current_document = user_data.get_active_document()
    if not current_document:
        raise FileNotFoundError
    eml_node = load_eml(filename=current_document)
    log_usage(actions['CHECK_DATA_TABLES'])
    set_current_page('check_data_tables')
    content = check_data_table_contents.create_check_data_tables_status_page_content(current_document, eml_node)
    check_data_table_contents.set_check_data_tables_badge_status(current_document, eml_node)
    if is_hidden_button():
        new_page = handle_hidden_buttons(PAGE_CHECK_DATA_TABLES, PAGE_CHECK_DATA_TABLES)
        return redirect(url_for(new_page, filename=current_document))

    help = get_helps(['check_data_tables'])
    return render_template('check_data_tables.html', help=help, content=content)


@home.route('/check_metadata/<filename>', methods=['GET', 'POST'])
@login_required
def check_metadata(filename:str):
    current_document = user_data.get_active_document()
    if not current_document:
        raise FileNotFoundError
    eml_node = load_eml(filename=current_document, skip_metadata_check=True)
    content = check_eml(eml_node, filename)
    log_usage(actions['CHECK_METADATA'])

    # Process POST
    if request.method == 'POST':
        return redirect(url_for(PAGE_CHECK, filename=current_document))

    else:
        set_current_page('check_metadata')
        return render_template('check_metadata.html', content=content, title='Check Metadata')


@home.route('/datetime_formats', methods=['GET', 'POST'])
@login_required
def datetime_formats():
    content = format_date_time_formats_list()
    # log_usage(actions['CHECK_METADATA'])

    # Process POST
    if request.method == 'POST':
        return redirect(url_for(PAGE_DATETIME_FORMATS))

    else:
        # set_current_page('check_metadata')
        return render_template('datetime_formats.html', content=content)


@home.route('/download_current', methods=['GET', 'POST'])
@login_required
def download_current():
    current_document = user_data.get_active_document()
    if current_document:
        # Force the document to be saved, so it gets cleaned, and incorporate the upload URLs for the data
        eml_node = load_eml(filename=current_document)
        insert_upload_urls(current_document, eml_node)
        save_both_formats(filename=current_document, eml_node=eml_node)

        # Do the download
        package_id = eml_node.attribute_value("packageId")
        return_value = user_data.download_eml(filename=current_document, package_id=package_id)
        log_usage(actions['DOWNLOAD_EML_FILE'], package_id)

        if isinstance(return_value, str):
            flash(return_value)
        else:
            return return_value


def allowed_data_file(filename):
    ALLOWED_EXTENSIONS = set(['csv', 'tsv', 'txt', 'xml', 'ezeml_tmp'])
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def allowed_metadata_file(filename):
    ALLOWED_EXTENSIONS = set(['xml'])    
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


'''
This function is deprecated. It was originally used as a first 
step in a two-step process for data table upload, but that process 
has been consolidated into a single step (see the load_data()
function).

@home.route('/upload_data_file', methods=['GET', 'POST'])
@login_required
def upload_data_file():
    uploads_folder = get_user_uploads_folder_name()
    form = UploadDataFileForm()

    # Process POST
    if request.method == 'POST' and form.validate_on_submit():
        # Check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)

        file = request.files['file']
        if file:
            filename = secure_filename(file.filename)
            
            if filename is None or filename == '':
                flash('No selected file')           
            elif allowed_data_file(filename):
                file.save(os.path.join(uploads_folder, filename))
                flash(f'{filename} uploaded')
            else:
                flash(f'{filename} is not a supported data file type')
            
        return redirect(request.url)

    # Process GET
    return render_template('upload_data_file.html', title='Upload Data File', 
                           form=form)
'''

@home.route('/create', methods=['GET', 'POST'])
@login_required
def create():
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
                return render_template('create_eml.html', help=help,
                                form=form)
            create_eml(filename=filename)
            current_user.set_filename(filename)
            current_user.set_packageid(None)
            log_usage(actions['NEW_DOCUMENT'])
            return redirect(url_for(PAGE_TITLE, filename=filename))

    # Process GET
    return render_template('create_eml.html', help=help, form=form)


@home.route('/open_eml_document', methods=['GET', 'POST'])
@login_required
def open_eml_document():
    form = OpenEMLDocumentForm()
    form.filename.choices = list_data_packages(True, True)

    # Process POST
    if request.method == 'POST':

        if BTN_CANCEL in request.form:
            return redirect(get_back_url())

        if form.validate_on_submit():
            filename = form.filename.data
            eml_node = load_eml(filename)
            if eml_node:
                current_user.set_filename(filename)
                packageid = eml_node.attributes.get('packageId', None)
                if packageid:
                    current_user.set_packageid(packageid)
                create_eml(filename=filename)
                new_page = PAGE_TITLE
                log_usage(actions['OPEN_DOCUMENT'])
                check_data_table_contents.set_check_data_tables_badge_status(filename, eml_node)

            else:
                new_page = PAGE_FILE_ERROR
            return redirect(url_for(new_page, filename=filename))
    
    # Process GET
    return render_template('open_eml_document.html', title='Open EML Document', 
                           form=form)


def get_subdirs(dir):
    print(f"get_subdirs: {dir}")
    subdirs = []
    for fname in sorted(os.listdir(dir), key=str.lower):
        if os.path.isdir(os.path.join(dir, fname)):
            subdirs.append(os.path.join(dir, fname))
    return subdirs


def get_files(dir):
    print(f"get_files: {dir}")
    files = []
    for fname in sorted(os.listdir(dir), key=str.lower):
        if os.path.isdir(os.path.join(dir, fname)) or fname.endswith('.json'):
            files.append(os.path.join(dir, fname))
    return files


def add_file(fname, output):
    dir = os.path.dirname(fname)
    dir = dir.replace(f"{Config.TEMPLATE_DIR}/", '')
    fname = os.path.splitext(os.path.basename(fname))[0]
    output += f'<li onclick="setTarget(\'{fname}\', \'{dir}\');" style="color:steelblue;cursor:pointer;">{fname}</li>\n'

    return output


def form_template_tree(file, output):
    # print(f"form_template_tree: file={file}, output={output}")

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
                output += f'<ul style="display: none;">\n'
                have_ul = True
        for file in files:
            output = form_template_tree(file, output)
    else:
        if file:
            output = add_file(file, output)
    if have_ul:
        output += "</ul>\n"
    output += "</li>\n"

    # print(f"form_template_tree: returns output={output}")
    return output


def import_selected_template(template_filename, output_filename):
    # Copy the template into the user's directory
    user_folder = user_data.get_user_folder_name()
    copyfile(f"{Config.TEMPLATE_DIR}/{template_filename}", f"{user_folder}/{output_filename}.json")
    create_eml(filename=output_filename)


@home.route('/import_template', methods=['GET', 'POST'])
@login_required
def import_template():
    if request.method == 'POST':
        form = request.form
        if BTN_CANCEL in form:
            return redirect(get_back_url())

        form_dict = form.to_dict(flat=False)
        # Find the key with value = 'OK'. That gives the path of the template.
        template_path = ''
        for key, val in form_dict.items():
            if val == ['OK']:
                template_path = key
                break
        if template_path:
            template_path = template_path.replace('/', '\\')
            return redirect(url_for(PAGE_IMPORT_TEMPLATE_2, template_filename=template_path))
        else:
            new_page = PAGE_IMPORT_TEMPLATE_2
            this_page = PAGE_IMPORT_TEMPLATE
            new_page = handle_hidden_buttons(new_page, this_page)
            return redirect(url_for(new_page))

    # Process GET
    output = '<ul class="directory-list">\n'
    output = form_template_tree(Config.TEMPLATE_DIR, output)
    output += '</ul>'

    help = get_helps(['import_template'])
    return render_template('import_template.html', directory_list=output, help=help)


@home.route('/import_template_2/<template_filename>/', methods=['GET', 'POST'])
@login_required
def import_template_2(template_filename):
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
                return render_template('create_eml.html', help=help,
                                form=form)

            template_filename = template_filename.replace('\\', '/')
            template_path = f'{template_filename}.json'

            import_selected_template(template_path, filename)
            current_user.set_filename(filename)
            log_usage(actions['NEW_FROM_TEMPLATE'], template_filename)
            current_user.set_packageid(None)
            new_page = PAGE_TITLE
            return redirect(url_for(new_page, filename=filename))

    # Process GET
    return render_template('import_template_2.html', help=help, form=form)


@home.route('/import_parties', methods=['GET', 'POST'])
@login_required
def import_parties():
    form = ImportEMLForm()
    form.filename.choices = list_data_packages(True, True)

    # Process POST
    if request.method == 'POST':
        if BTN_CANCEL in request.form:
            return redirect(get_back_url())

        if form.validate_on_submit():
            filename = form.filename.data
            return redirect(url_for('home.import_parties_2', filename=filename))

    # Process GET
    help = get_helps(['import_responsible_parties'])
    return render_template('import_parties.html', help=help, form=form)


def get_redirect_target_page():
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
        return PAGE_CHECK
    elif current_page == 'export_package':
        return PAGE_EXPORT_DATA_PACKAGE
    elif current_page == 'data_package_id':
        return PAGE_DATA_PACKAGE_ID
    elif current_page == 'submit_package':
        return PAGE_SUBMIT_TO_EDI
    elif current_page == 'send_to_other':
        return PAGE_SEND_TO_OTHER
    else:
        return PAGE_TITLE


@home.route('/import_parties_2/<filename>/', methods=['GET', 'POST'])
@login_required
def import_parties_2(filename):
    form = ImportEMLItemsForm()

    eml_node = load_eml(filename)
    parties = get_responsible_parties_for_import(eml_node)
    choices = [[party[2], party[1]] for party in parties]
    form.to_import.choices = choices
    targets = [
        ("Creators", "Creators"),
        ("Metadata Providers", "Metadata Providers"),
        ("Associated Parties", "Associated Parties"),
        ("Contacts", "Contacts"),
        ("Publisher", "Publisher"),
        ("Project Personnel", "Project Personnel")]
    form.target.choices = targets

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

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
        elif target_class == 'Project Personnel':
            new_page = PAGE_PROJECT_PERSONNEL_SELECT
        return redirect(url_for(new_page, filename=target_filename))

    # Process GET
    help = get_helps(['import_responsible_parties_2'])
    return render_template('import_parties_2.html', target_filename=filename, help=help, form=form)


def get_responsible_parties_for_import(eml_node):
    parties = []
    for node in eml_node.find_all_nodes_by_path([names.DATASET, names.CREATOR]):
        label = compose_rp_label(node)
        parties.append(('Creator', f'{label} (Creator)', node.id))
    for node in eml_node.find_all_nodes_by_path([names.DATASET, names.METADATAPROVIDER]):
        label = compose_rp_label(node)
        parties.append(('Metadata Provider', f'{label} (Metadata Provider)', node.id))
    for node in eml_node.find_all_nodes_by_path([names.DATASET, names.ASSOCIATEDPARTY]):
        label = compose_rp_label(node)
        parties.append(('Associated Party', f'{label} (Associated Party)', node.id))
    for node in eml_node.find_all_nodes_by_path([names.DATASET, names.CONTACT]):
        label = compose_rp_label(node)
        parties.append(('Contact', f'{label} (Contact)', node.id))
    for node in eml_node.find_all_nodes_by_path([names.DATASET, names.PUBLISHER]):
        label = compose_rp_label(node)
        parties.append(('Publisher', f'{label} (Publisher)', node.id))
    for node in eml_node.find_all_nodes_by_path([names.DATASET, names.PROJECT, names.PERSONNEL]):
        label = compose_rp_label(node)
        parties.append(('Project Personnel', f'{label} (Project Personnel)', node.id))
    return parties


@home.route('/import_geo_coverage', methods=['GET', 'POST'])
@login_required
def import_geo_coverage():
    form = ImportEMLForm()
    form.filename.choices = list_data_packages(False, False)

    # Process POST
    if request.method == 'POST':
        if BTN_CANCEL in request.form:
            return redirect(get_back_url())
        if form.validate_on_submit():
            filename = form.filename.data
            return redirect(url_for('home.import_geo_coverage_2', filename=filename))

    # Process GET
    help = get_helps(['import_geographic_coverage'])
    return render_template('import_geo_coverage.html', help=help, form=form)


@home.route('/import_geo_coverage_2/<filename>/', methods=['GET', 'POST'])
@login_required
def import_geo_coverage_2(filename):
    form = ImportItemsForm()

    eml_node = load_eml(filename)
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
    return render_template('import_geo_coverage_2.html', help=help, target_filename=filename, form=form)


def get_geo_coverages_for_import(eml_node):
    coverages = []
    for node in eml_node.find_all_nodes_by_path([names.DATASET, names.COVERAGE, names.GEOGRAPHICCOVERAGE]):
        label = compose_full_gc_label(node)
        coverages.append((f'{label}', node.id))
    return coverages


@home.route('/import_temporal_coverage', methods=['GET', 'POST'])
@login_required
def import_temporal_coverage():
    form = ImportEMLForm()
    form.filename.choices = list_data_packages(False, False)

    # Process POST
    if request.method == 'POST':
        if BTN_CANCEL in request.form:
            return redirect(get_back_url())
            # new_page = get_redirect_target_page()
            # url = url_for(new_page, filename=current_user.get_filename())
            # return redirect(url)
        if form.validate_on_submit():
            filename = form.filename.data
            return redirect(url_for('home.import_temporal_coverage_2', filename=filename))

    # Process GET
    return render_template('import_temporal_coverage.html', form=form)


@home.route('/import_temporal_coverage_2/<filename>/', methods=['GET', 'POST'])
@login_required
def import_temporal_coverage_2(filename):
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


def get_temporal_coverages_for_import(eml_node):
    coverages = []
    for node in eml_node.find_all_nodes_by_path([names.DATASET, names.COVERAGE, names.TEMPORALCOVERAGE]):
        label = compose_full_gc_label(node) # FIXME
        coverages.append((f'{label}', node.id))
    return coverages


@home.route('/import_taxonomic_coverage', methods=['GET', 'POST'])
@login_required
def import_taxonomic_coverage():
    form = ImportEMLForm()
    form.filename.choices = list_data_packages(False, False)

    # Process POST
    if request.method == 'POST':
        if BTN_CANCEL in request.form:
            return redirect(get_back_url())
        if form.validate_on_submit():
            filename = form.filename.data
            return redirect(url_for('home.import_taxonomic_coverage_2', filename=filename))

    # Process GET
    help = get_helps(['import_taxonomic_coverage'])
    return render_template('import_taxonomic_coverage.html', help=help, form=form)


@home.route('/import_taxonomic_coverage_2/<filename>/', methods=['GET', 'POST'])
@login_required
def import_taxonomic_coverage_2(filename):
    form = ImportItemsForm()

    eml_node = load_eml(filename)
    coverages = get_taxonomic_coverages_for_import(eml_node)
    choices = [[coverage[1], coverage[0]] for coverage in coverages]
    form.to_import.choices = choices

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    if form.validate_on_submit():
        node_ids_to_import = form.data['to_import']
        target_package = current_user.get_filename()
        eml_node = import_coverage_nodes(target_package, node_ids_to_import)
        clear_taxonomy_imported_from_xml(eml_node, target_package)
        log_usage(actions['IMPORT_TAXONOMIC_COVERAGE'], filename)
        return redirect(url_for(PAGE_TAXONOMIC_COVERAGE_SELECT, filename=target_package))

    # Process GET
    help = get_helps(['import_taxonomic_coverage_2'])
    return render_template('import_taxonomic_coverage_2.html', help=help, target_filename=filename, form=form)


def get_taxonomic_coverages_for_import(eml_node):
    coverages = []
    for node in eml_node.find_all_nodes_by_path([names.DATASET, names.COVERAGE, names.TAXONOMICCOVERAGE]):
        label = truncate_middle(compose_taxonomic_label(node), 100, ' ... ')
        coverages.append((f'{label}', node.id))
    return coverages


@home.route('/import_funding_awards', methods=['GET', 'POST'])
@login_required
def import_funding_awards():
    form = ImportEMLForm()
    form.filename.choices = list_data_packages(False, False)

    # Process POST
    if request.method == 'POST':
        if BTN_CANCEL in request.form:
            return redirect(get_back_url())
        if form.validate_on_submit():
            filename = form.filename.data
            return redirect(url_for('home.import_funding_awards_2', filename=filename))

    # Process GET
    help = get_helps(['import_funding_awards'])
    return render_template('import_funding_awards.html', help=help, form=form)


@home.route('/import_funding_awards_2/<filename>/', methods=['GET', 'POST'])
@login_required
def import_funding_awards_2(filename):
    form = ImportItemsForm()

    eml_node = load_eml(filename)
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
    return render_template('import_funding_awards_2.html', help=help, target_filename=filename, form=form)


def get_funding_awards_for_import(eml_node):
    awards = []
    award_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.PROJECT, names.AWARD])
    for award_node in award_nodes:
        label = truncate_middle(compose_funding_award_label(award_node), 80, ' ... ')
        awards.append((f'{label}', award_node.id))
    return awards


@home.route('/import_related_projects', methods=['GET', 'POST'])
@login_required
def import_related_projects():
    form = ImportEMLForm()
    form.filename.choices = list_data_packages(False, False)

    # Process POST
    if request.method == 'POST':
        if BTN_CANCEL in request.form:
            return redirect(get_back_url())
        if form.validate_on_submit():
            filename = form.filename.data
            return redirect(url_for('home.import_related_projects_2', filename=filename))

    # Process GET
    help = get_helps(['import_related_projects'])
    return render_template('import_related_projects.html', help=help, form=form)


@home.route('/import_related_projects_2/<filename>/', methods=['GET', 'POST'])
@login_required
def import_related_projects_2(filename):
    form = ImportItemsForm()

    eml_node = load_eml(filename)
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
    return render_template('import_related_projects_2.html', help=help, target_filename=filename, form=form)


@home.route('/import_project', methods=['GET', 'POST'])
@login_required
def import_project():
    form = ImportEMLForm()
    form.filename.choices = list_data_packages(False, False)

    # Process POST
    if request.method == 'POST':
        if BTN_CANCEL in request.form:
            return redirect(get_back_url())
        if form.validate_on_submit():
            filename = form.filename.data
            return redirect(url_for('home.import_project_2', filename=filename))

    # Process GET
    help = get_helps(['import_project'])
    return render_template('import_project.html', help=help, form=form)


@home.route('/import_project_2/<filename>/', methods=['GET', 'POST'])
@login_required
def import_project_2(filename):
    form = ImportSingleItemForm()

    eml_node = load_eml(filename)
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
    return render_template('import_project_2.html', help=help, target_filename=filename, form=form)


def get_projects_for_import(eml_node):
    projects = []
    project = eml_node.find_single_node_by_path([names.DATASET, names.PROJECT])
    project_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.PROJECT, names.RELATED_PROJECT])
    if project:
        project_nodes.append(project)
    for project_node in project_nodes:
        label = truncate_middle(compose_project_label(project_node), 80, ' ... ')
        projects.append((f'{label}', project_node.id))
    return projects


def display_decode_error_lines(filename):
    errors = []
    with open(filename, 'r', errors='replace') as f:
        lines = f.readlines()
    for index, line in enumerate(lines, start=1):
        if "�" in line:
            errors.append((index, line))
    return errors


def create_ezeml_package_manifest(user_folder, manifest_files):
    with open(f'{user_folder}/ezEML_manifest.txt', 'w') as manifest_file:
        manifest_file.write(f'ezEML Data Archive Manifest\n')
        manifest_file.write(f'ezEML Release {RELEASE_NUMBER}\n')
        manifest_file.write(f'--------------------\n')
        for filetype, filename, filepath in manifest_files:
            manifest_file.write(f'{filetype}\n')
            manifest_file.write(f'{filename}\n')
            manifest_file.write(f'{get_md5_hash(filepath)}\n')


def zip_package(current_document=None, eml_node=None, include_data=True):
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
        arcname = f'{package_id}.xml'
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
    current_document = current_user.get_filename()
    if not current_document:
        raise FileNotFoundError

    user_folder = user_data.get_user_folder_name()

    # Create the exports folder
    timestamp = datetime.now().date().strftime('%Y_%m_%d') + '_' + datetime.now().time().strftime('%H_%M_%S')
    export_folder = os.path.join(user_folder, 'exports', current_document, timestamp)
    os.makedirs(export_folder, exist_ok=True)

    _, archive_basename = os.path.split(archive_file)
    src = archive_file
    dest = f'{export_folder}/{archive_basename}'
    copyfile(src, dest)

    parsed_url = urlparse(request.base_url)
    download_url = f"{parsed_url.scheme}://{parsed_url.netloc}/{dest}"
    return archive_basename, download_url


@home.route('/export_package', methods=['GET', 'POST'])
@login_required
def export_package():
    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    if request.method == 'POST':
        insert_upload_urls(current_document, eml_node)
        save_both_formats(current_document, eml_node)
        zipfile_path = zip_package(current_document, eml_node)
        if zipfile_path:
            archive_basename, download_url = save_as_ezeml_package_export(zipfile_path)
            if download_url:
                log_usage(actions['EXPORT_EZEML_DATA_PACKAGE'])
                return redirect(url_for('home.export_package_2', package_name=archive_basename,
                                        download_url=get_shortened_url(download_url), safe=''))

        # archive_basename, download_url = save_as_ezeml_package_export(zipfile_path)
        # if download_url:
        #     return redirect(url_for('home.export_package_2', package_name=archive_basename,
        #                             download_url=get_shortened_url(download_url), safe=''))

    # Process GET
    help = get_helps(['export_package'])
    return render_template('export_package.html', back_url=get_back_url(), title='Export Data Package', help=help)


@home.route('/export_package_2/<package_name>/<path:download_url>', methods=['GET', 'POST'])
@login_required
def export_package_2(package_name, download_url):
    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    reload_metadata()  # So check_metadata status is correct

    return render_template('export_package_2.html', back_url=get_back_url(), title='Export Data Package',
                           package_name=package_name, download_url=download_url)


def submit_package_mail_body(name=None, email_address=None, archive_name=None, download_url=None,
                             download_url_without_data=None, notes=None):
    # Note: get_shortened_url handles blanks
    msg = 'Dear EDI Data Curator:' + '\n\n' + \
        'This email was auto-generated by ezEML.\n\n\n' + \
        'Please submit the following data package to the EDI data repository.\n\n' + \
        '   Sender\'s name: ' + name + '\n\n' + \
        '   Sender\'s email: ' + email_address + '\n\n' + \
        '   Package name: ' + archive_name + '\n\n' + \
        '   Download URL: ' + quote(download_url, safe=':/') + '\n\n' + \
        '   Download URL without data files: ' + quote(download_url_without_data, safe=':/') + '\n\n'
        # '   Download URL: ' + get_shortened_url(download_url) + '\n\n' + \
        # '   Download URL without data files: ' + get_shortened_url(download_url_without_data) + '\n\n'
    if notes:
        msg += '   Sender\'s Notes: ' + notes
    return msg


def keep_existing_url(distribution_node, uploads_folder):
    # If a distribution node exists, check to see if there's a URL and, if so, whether it points to a different
    #  user's account or a different package. The case we want to guard against is one where we've imported a
    #  "without data" ezEML Data Package and all we're doing is modifying the EML (e.g., changing the data package ID)
    #  before uploading to PASTA. In such a case, we want to leave existing distribution nodes as we've found them, so
    #  they will point to the original user's ezEML account and package.
    url_node = distribution_node.find_descendant(names.URL)
    if url_node:
        url = url_node.content
        if url:
            if uploads_folder not in url and uploads_folder.replace(' ', '%20') not in url:
                # log_info(f"keep_existing_url returning True for {url}")
                return True
    return False


def insert_urls(uploads_url_prefix, uploads_folder, eml_node, node_type):
    # log_info(f"insert_urls... node_type={node_type}")
    upload_nodes = []
    eml_node.find_all_descendants(node_type, upload_nodes)
    for upload_node in upload_nodes:
        try:
            physical_node = upload_node.find_descendant(names.PHYSICAL)
            object_name_node = physical_node.find_child(names.OBJECTNAME)
            if not object_name_node:
                continue
            object_name = object_name_node.content
            distribution_node = physical_node.find_child(names.DISTRIBUTION)
            if distribution_node:
                if keep_existing_url(distribution_node, uploads_folder):
                    continue
                physical_node.remove_child(distribution_node)
            # See if file exists before adding a distribution URL pointing to our copy.
            filepath = os.path.join(uploads_folder, object_name)
            if not os.path.exists(filepath):
                continue
            distribution_node = new_child_node(names.DISTRIBUTION, physical_node)
            online_node = new_child_node(names.ONLINE, distribution_node)
            url_node = new_child_node(names.URL, online_node)
            url_node.add_attribute('function', 'download')
            url_node.content = f"{uploads_url_prefix}/{object_name}".replace(' ', '%20')
            # log_info(f"  object_name={object_name_node.content}... url={url_node.content}")
        except Exception as err:
            flash(err)
            continue


def insert_upload_urls(current_document, eml_node):
    user_folder = user_data.get_user_folder_name()
    uploads_folder = f'{user_folder}/uploads/{current_document}'

    parsed_url = urlparse(request.base_url)
    uploads_url_prefix = f"{parsed_url.scheme}://{parsed_url.netloc}/{uploads_folder}"

    insert_urls(uploads_url_prefix, uploads_folder, eml_node, names.DATATABLE)
    insert_urls(uploads_url_prefix, uploads_folder, eml_node, names.OTHERENTITY)


@home.route('/submit_package', methods=['GET', 'POST'])
@login_required
def submit_package():
    form = SubmitToEDIForm()

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    if form.validate_on_submit():
        # If the user has clicked Save in the EML Documents menu, for example, we want to ignore the
        #  programmatically generated Submit
        if request.form.get(BTN_SUBMIT) == BTN_SUBMIT_TO_EDI:
            name = form.data['name']
            email_address = form.data['email_address']
            notes = form.data['notes']

            # update the EML to include URLs to data table files and other entity files
            insert_upload_urls(current_document, eml_node)
            save_both_formats(filename=current_document, eml_node=eml_node)

            try:
                zipfile_path = zip_package(current_document, eml_node)
                zipfile_path_without_data = zip_package(current_document, eml_node, include_data=False)
            except ezEMLError as e:
                flash(str(e), 'error')
                print(redirect(get_back_url()))
                return redirect(get_back_url())

            if zipfile_path and zipfile_path_without_data:
                _, download_url = save_as_ezeml_package_export(zipfile_path)
                _, download_url_without_data = save_as_ezeml_package_export(zipfile_path_without_data)

                msg = submit_package_mail_body(name, email_address, current_document, download_url,
                                               download_url_without_data, notes)
                msg += get_fetched_from_edi_metadata(eml_node)
                msg += get_imported_from_xml_metadata(eml_node)
                subject = 'ezEML-Generated Data Submission Request'
                to_address = [Config.TO]
                sent = mimemail.send_mail(subject=subject, msg=msg, to=to_address, sender_name=name, sender_email=email_address)
                if sent:
                    log_usage(actions['SEND_TO_EDI'], name, email_address)
                    flash(f'Package "{current_document}" has been sent to EDI. We will notify you when it has been added to the repository.')
                    flash(f"If you don't hear back from us within 48 hours, please contact us at support@edirepository.org.")
                else:
                    log_usage(actions['SEND_TO_EDI'], 'failed')
                    flash(f'Email failed to send', 'error')

            return redirect(get_back_url())

    set_current_page('submit_package')
    help = get_helps(['submit_package'])
    return render_template('submit_package.html',
                           title='Send to EDI',
                           check_metadata_status=get_check_metadata_status(eml_node, current_document),
                           form=form, help=help)


def get_shortened_url(long_url):
    encoded_url = urlencode({'url':long_url})
    r = requests.get(f'https://tinyurl.com/api-create.php?{encoded_url}')
    try:
        r.raise_for_status()
        return r.text
    except requests.exceptions.HTTPError as e:
        return long_url


def send_to_other_email(name, email_address, title, url):
    name_quoted = quote(name)
    email_address_quoted = quote(email_address)
    title_quoted = quote(title)
    url = get_shortened_url(url)  # Note; get_shortened_url handles blank chars
    msg_quoted = f'mailto:{email_address}?subject=ezEML-Generated%20Data%20Package&body=Dear%20{name}%3A%0D%0A%0D%0A' \
          f'I%20have%20created%20a%20data%20package%20containing%20EML%20metadata%20and%20associated%20data%20files%20' \
          f'for%20your%20inspection.%0D%0A%0D%0ATitle%3A%20%22{title}%22%0D%0A%0D%0AThe%20data%20package%20is%20' \
          f'available%20for%20download%20here%3A%20{url}%0D%0A%0D%0AThe%20package%20was%20created%20using%20ezEML.%20' \
          f'After%20you%20download%20the%20package%2C%20you%20can%20import%20it%20into%20ezEML%2C%20or%20you%20can%20' \
          f'unzip%20it%20to%20extract%20the%20EML%20file%20and%20associated%20data%20files%20to%20work%20with%20them%20' \
          f'directly.%0D%0A%0D%0ATo%20learn%20more%20about%20ezEML%2C%20go%20to%20https%3A%2F%2Fezeml.edirepository.org.' \
          f'%0D%0A%0D%0AThanks!'
    msg_html = Markup(f'Dear {name}:<p><br>'
          f'I have created a data package containing EML metadata and associated data files '
          f'for your inspection.<p>Title: "{title}"<p>The data package is '
          f'available for download here: {url}.<p>The package was created using ezEML. '
          f'After you download the package, you can import it into ezEML, or you can '
          f'unzip it to extract the EML file and associated data files to work with them '
          f'directly.<p>To learn more about ezEML, go to https://ezeml.edirepository.org.'
          f'<p>Thanks!')
    msg_raw = f'Dear {name}:\n\n' \
          f'I have created a data package containing EML metadata and associated data files ' \
          f'for your inspection.\n\nTitle: "{title}"\n\nThe data package is ' \
          f'available for download here: {url}.\n\nThe package was created using ezEML. ' \
          f'After you download the package, you can import it into ezEML, or you can ' \
          f'unzip it to extract the EML file and associated data files to work with them ' \
          f'directly.\n\nTo learn more about ezEML, go to https://ezeml.edirepository.org.' \
          f'\n\nThanks!'
    return msg_quoted, msg_html, msg_raw


@home.route('/send_to_other/<filename>/', methods=['GET', 'POST'])
@home.route('/send_to_other/<filename>/<mailto>/', methods=['GET', 'POST'])
@login_required
def send_to_other(filename=None, mailto=None):
    form = SendToColleagueForm()

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    if form.validate_on_submit():
        # If the user has clicked Save in the EML Documents menu, for example, we want to ignore the
        #  programmatically generated Submit
        if request.form.get(BTN_SUBMIT) == BTN_SEND_TO_OTHER:

            colleague_name = form.data['colleague_name']
            email_address = form.data['email_address']

            eml_node = load_eml(filename=filename)
            insert_upload_urls(current_document, eml_node)
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

            _, download_url = save_as_ezeml_package_export(zipfile_path)

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


def get_column_properties(eml_node, document, dt_node, object_name):
    data_file = object_name
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
        new_dt_node, new_column_vartypes, new_column_names, new_column_categorical_codes, *_ = load_data_table(
            uploads_folder, data_file, num_header_rows, delimiter, quote_char)

        user_data.add_uploaded_table_properties(data_file,
                                      new_column_vartypes,
                                      new_column_names,
                                      new_column_categorical_codes)

        clear_distribution_url(dt_node)
        insert_upload_urls(document, eml_node)

        return new_column_vartypes

    except FileNotFoundError:
        raise FileNotFoundError('The older version of the data table is missing from our server. Please use "Load Data Table from CSV File" instead of "Re-upload".')

    except Exception as err:
        raise Exception('Internal error 103')

    except UnicodeDecodeError as err:
        fullpath = os.path.join(uploads_folder, data_file)
        errors = display_decode_error_lines(fullpath)
        return render_template('encoding_error.html', filename=data_file, errors=errors)


def check_data_table_similarity(old_dt_node, new_dt_node, new_column_vartypes, new_column_names, new_column_codes):
    if not old_dt_node or not new_dt_node:
        raise Exception('Internal error 100')
    old_attribute_list = old_dt_node.find_child(names.ATTRIBUTELIST)
    new_attribute_list = new_dt_node.find_child(names.ATTRIBUTELIST)
    if len(old_attribute_list.children) != len(new_attribute_list.children):
        raise IndexError('The new table has a different number of columns from the original table.')
    document = current_user.get_filename()
    old_object_name_node = old_dt_node.find_descendant(names.OBJECTNAME)
    if not old_object_name_node:
        raise Exception('Internal error 101')
    old_object_name = old_object_name_node.content
    if not old_object_name:
        raise Exception('Internal error 102')
    old_column_vartypes, _, _ = user_data.get_uploaded_table_column_properties(old_object_name)
    if not old_column_vartypes:
        # column properties weren't saved. compute them anew.
        eml_node = load_eml(filename=document)
        old_column_vartypes = get_column_properties(eml_node, document, old_dt_node, old_object_name)
    if old_column_vartypes != new_column_vartypes:
        diffs = []
        for col_name, old_type, new_type, attr_node in zip(new_column_names, old_column_vartypes, new_column_vartypes, old_attribute_list.children):
            if old_type != new_type:
                diffs.append((col_name, old_type, new_type, attr_node))
        raise ValueError(diffs)


def substitute_nans(codes):
    substituted = []
    if codes:
        for code in codes:
            if isinstance(code, list):
                substituted.append(substitute_nans(code))
            elif not isinstance(code, float) or not math.isnan(code):
                substituted.append(code)
            else:
                substituted.append('NAN')
    else:
        substituted.append(None)
    return substituted


def compare_codes(old_codes, new_codes):
    old_substituted = substitute_nans(old_codes)
    new_substituted = substitute_nans(new_codes)
    return old_substituted == new_substituted


def add_node_if_missing(parent_node, child_name):
    child = parent_node.find_descendant(child_name)
    if not child:
        child = new_child_node(child_name, parent=parent_node)
    return child


def update_data_table(old_dt_node, new_dt_node, new_column_names, new_column_categorical_codes, doing_xml_import=False):
    debug_msg(f'Entering update_data_table')

    if not old_dt_node or not new_dt_node:
        return

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
        old_record_delimiter_node.parent.remove_child(old_record_delimiter_node)

    # quote char node is not required, so may be missing
    if new_quote_char_node:
        old_quote_char_node.content = new_quote_char_node.content
    else:
        old_quote_char_node.parent.remove_child(old_quote_char_node)

    if not doing_xml_import:
        _, old_column_names, old_column_categorical_codes = user_data.get_uploaded_table_column_properties(old_object_name)
        if old_column_names and old_column_names != new_column_names:
            # substitute the new column names
            old_attribute_list_node = old_dt_node.find_child(names.ATTRIBUTELIST)
            old_attribute_names_nodes = []
            old_attribute_list_node.find_all_descendants(names.ATTRIBUTENAME, old_attribute_names_nodes)
            for old_attribute_names_node, old_name, new_name in zip(old_attribute_names_nodes, old_column_names, new_column_names):
                if old_name != new_name:
                    debug_None(old_attribute_names_node, 'old_attribute_names_node is None')
                    old_attribute_names_node.content = new_name
        if not compare_codes(old_column_categorical_codes, new_column_categorical_codes):
            # need to fix up the categorical codes
            old_attribute_list_node = old_dt_node.find_child(names.ATTRIBUTELIST)
            old_aattribute_nodes = old_attribute_list_node.find_all_children(names.ATTRIBUTE)
            new_attribute_list_node = new_dt_node.find_child(names.ATTRIBUTELIST)
            new_attribute_nodes = new_attribute_list_node.find_all_children(names.ATTRIBUTE)
            for old_attribute_node, old_codes, new_attribute_node, new_codes in zip(old_aattribute_nodes,
                                                                                    old_column_categorical_codes,
                                                                                    new_attribute_nodes,
                                                                                    new_column_categorical_codes):
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
                        parent_node.remove_child(old_code_definition_node)
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
    debug_msg(f'Leaving update_data_table')


def backup_metadata(filename):
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
    # The parameters are actually lists, but Flask drops parameters that are empty lists, so what's passed are the
    #  string representations. In addition, the string may contain '/' characters, which will not be encoded by default,
    #  thereby breaking the routing, so we need them to be encoded. Setting safe to an empty string accomplishes that.
    return quote(repr(param), safe='')


def decode_from_query_string(param):
    # The inverse operation of encode_for_query_string(), turning the parameter back into a list.
    return ast.literal_eval(unquote(param))


@home.route('/import_xml', methods=['GET', 'POST'])
@login_required
def import_xml():
    form = ImportPackageForm()

    # Process POST

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    reload_metadata()  # So check_metadata status is correct
    eml_node = None

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
            filename = file.filename

            if not os.path.splitext(filename)[1] == '.xml':
                flash('Please select a file with file extension ".xml".', 'error')
                return redirect(request.url)

            package_base_filename = os.path.basename(filename)
            package_name = os.path.splitext(package_base_filename)[0]

            filepath = save_xml_file(file)
            # See if package with that name already exists
            if package_name in user_data.get_user_document_list():
                return redirect(url_for('home.import_xml_2', package_name=package_name, filename=filename))

            eml_node, unknown_nodes, attr_errs, child_errs, other_errs, pruned_nodes = parse_xml_file(filename, filepath)

            if eml_node:
                add_imported_from_xml_metadata(eml_node, filename, package_name)
                has_errors = unknown_nodes or attr_errs or child_errs or other_errs or pruned_nodes
                log_usage(actions['IMPORT_EML_XML_FILE'], filename, has_errors, model_has_complex_texttypes(eml_node))
                save_both_formats(filename=package_name, eml_node=eml_node)
                current_user.set_filename(filename=package_name)
                if unknown_nodes or attr_errs or child_errs or other_errs or pruned_nodes:
                    # The parameters are actually lists, but Flask drops parameters that are empty lists, so what's passed are the
                    #  string representations.
                    return redirect(url_for(PAGE_IMPORT_XML_3,
                                            unknown_nodes=encode_for_query_string(unknown_nodes),
                                            attr_errs=encode_for_query_string(attr_errs),
                                            child_errs=encode_for_query_string(child_errs),
                                            other_errs=encode_for_query_string(other_errs),
                                            pruned_nodes=encode_for_query_string(pruned_nodes),
                                            filename=package_name,
                                            fetched=False))
                else:
                    flash(f"{package_name} was imported without errors")
                    return redirect(url_for(PAGE_IMPORT_XML_4, filename=package_name, fetched=False))
            else:
                raise Exception  # TODO: Error handling

    # Process GET
    help = get_helps(['import_xml'])
    return render_template('import_xml.html', title='Import an XML File (XML)',
                           form=form, help=help)


@home.route('/import_xml_2/<package_name>/<filename>', methods=['GET', 'POST'])
@home.route('/import_xml_2/<package_name>/<filename>/<fetched>', methods=['GET', 'POST'])
@login_required
def import_xml_2(package_name, filename, fetched=False):
    form = ImportPackageForm()

    # Process POST

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    reload_metadata()  # So check_metadata status is correct

    if request.method == 'POST' and form.validate_on_submit():
        form = request.form
        if form['replace_copy'] == 'copy':
            package_name = determine_package_name(package_name)

        user_path = user_data.get_user_folder_name()
        work_path = os.path.join(user_path, 'zip_temp')
        filepath = os.path.join(work_path, filename)

        eml_node, unknown_nodes, attr_errs, child_errs, other_errs, pruned_nodes = parse_xml_file(filename, filepath)

        if eml_node:
            # save fact that EML was fetched from EDI in additional metadata
            add_fetched_from_edi_metadata(eml_node, package_name)
            add_imported_from_xml_metadata(eml_node, filename, package_name)
            has_errors = unknown_nodes or attr_errs or child_errs or other_errs or pruned_nodes
            log_usage(actions['IMPORT_EML_XML_FILE'], filename, has_errors, model_has_complex_texttypes(eml_node))
            save_both_formats(filename=package_name, eml_node=eml_node)
            current_user.set_filename(filename=package_name)

            if has_errors:
                # The parameters are actually lists, but Flask drops parameters that are empty lists, so we pass the
                #  string representations.
                return redirect(url_for(PAGE_IMPORT_XML_3,
                                        unknown_nodes=encode_for_query_string(unknown_nodes),
                                        attr_errs=encode_for_query_string(attr_errs),
                                        child_errs=encode_for_query_string(child_errs),
                                        other_errs=encode_for_query_string(other_errs),
                                        pruned_nodes=encode_for_query_string(pruned_nodes),
                                        filename=package_name,
                                        fetched=fetched))

            else:
                flash(f"{package_name} was imported without errors")
                return redirect(url_for(PAGE_IMPORT_XML_4, filename=package_name, fetched=fetched))
        else:
            raise Exception  # TODO: Error handling

    # Process GET
    help = get_helps(['import_xml_2'])
    return render_template('import_xml_2.html', title='Import an EML XML File',
                           package_name=package_name, form=form, help=help)


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


def construct_xml_error_descriptions(filename=None, unknown_nodes=None, attr_errs=None, child_errs=None,
                                    other_errs=None, pruned_nodes=None):
    err_html = ''
    err_text = ''

    unknown_nodes = decode_from_query_string(unknown_nodes)
    attr_errs = decode_from_query_string(attr_errs)
    child_errs = decode_from_query_string(child_errs)
    other_errs = decode_from_query_string(other_errs)
    pruned_nodes = decode_from_query_string(pruned_nodes)

    excluded_nodes = set(unknown_nodes)

    err_html, err_text = display_list(err_html, err_text, unknown_nodes,
        "The following EML element types are unknown to ezEML, so they have been omitted:")

    processed_child_errs = []
    for err in child_errs:
        _, child_name, _, parent_name, *_ = err.split("'")
        if child_name not in unknown_nodes:
            excluded_nodes.add(child_name)
            processed_child_errs.append(f"{child_name} within {parent_name}")

    err_html, err_text = display_list(err_html, err_text, processed_child_errs,
        "The following EML elements occur in unexpected locations in the EML, so they have been omitted:")

    # err_html, err_text = display_list(err_html, err_text, attr_errs, "The following errors involving node attributes have been detected:")

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

    err_heading = ""
    if len(excluded_nodes) > 0:
        err_heading = "<br>ezEML does not cover the complete EML standard. It imports as much of the EML " \
                      "as possible, but in this case it had to omit some EML elements. Details follow:<p><br>"

    return err_html, err_text, err_heading


def get_data_size(filename):
    try:
        scope, identifier, revision = filename.split('.')
        _, total = get_data_entity_sizes(scope, identifier, revision)
        kb, mb, gb = convert_file_size(total)
        return round(mb)
    except (AuthTokenExpired, Unauthorized):
        raise
    except Exception as e:
        return 0


@home.route('/import_xml_3/<unknown_nodes>/<attr_errs>/<child_errs>/<other_errs>/<pruned_nodes>/<filename>/<fetched>', methods=['GET', 'POST'])
@login_required
def import_xml_3(unknown_nodes=None, attr_errs=None, child_errs=None,
                 other_errs=None, pruned_nodes=None, filename=None, fetched=False):

    form = EDIForm()
    eml_node = load_eml(filename=filename)

    # Process POST

    reload_metadata()  # So check_metadata status is correct

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
            if not eval(fetched):
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
    form.md5.data = form_md5(form)

    err_html, err_text, err_heading = construct_xml_error_descriptions(filename, unknown_nodes, attr_errs,
                                                                       child_errs, other_errs, pruned_nodes)

    try:
        mb = get_data_size(filename)
        if mb > 100:
            mb = f' This package has <b>{mb} MB</b> of associated data.<br>&nbsp;'
        else:
            mb = ''
    except (AuthTokenExpired, Unauthorized) as e:
        flash(AUTH_TOKEN_FLASH_MSG, 'error')
        help = get_helps(['import_xml_3'])
        if not eval(fetched):
            return redirect(url_for('home.import_xml', form=form, help=help))
        else:
            return redirect(url_for('home.fetch_xml', form=form, help=help))

    help = get_helps(['import_xml_3', 'complex_xml'])
    complex_xml = model_has_complex_texttypes(eml_node)
    return render_template('import_xml_3.html', err_html=err_html, err_text=err_text, err_heading=err_heading,
                           mb=mb, complex_xml=complex_xml, form=form, help=help)


@home.route('/import_xml_4/<filename>/<fetched>', methods=['GET', 'POST'])
@login_required
def import_xml_4(filename=None, fetched=False):

    form = EDIForm()
    eml_node = load_eml(filename=filename)

    # Process POST

    reload_metadata()  # So check_metadata status is correct

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(url_for(PAGE_TITLE, filename=filename))

    if request.method == 'POST' and form.validate_on_submit():
        form = request.form
        try:
            total_size = import_data(filename, eml_node)
        except (AuthTokenExpired, Unauthorized) as e:
            flash(AUTH_TOKEN_FLASH_MSG, 'error')
            help = get_helps(['import_xml_3'])
            if not eval(fetched):
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
    form.md5.data = form_md5(form)

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


@home.route('/fetch_xml/', methods=['GET', 'POST'])
@login_required
def fetch_xml(scope=''):

    form = EDIForm()

    # Process POST

    reload_metadata()  # So check_metadata status is correct

    if request.method == 'POST' and BTN_CANCEL in request.form:
        filename = user_data.get_active_document()
        if filename:
            return redirect(url_for(PAGE_TITLE, filename=filename))
        else:
            return redirect(url_for(PAGE_INDEX))

    # Process GET
    form.md5.data = form_md5(form)

    try:
        ids = get_pasta_identifiers(scope)
    except (AuthTokenExpired, Unauthorized) as e:
        flash(AUTH_TOKEN_FLASH_MSG, 'error')
        help = get_helps(['fetch_from_edi'])
        return redirect(url_for('home.fetch_xml', scope=scope, form=form, help=help))

    package_links = ''
    parsed_url = urlparse(request.base_url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}/eml"
    for id in ids:
        new_link = f"{base_url}/fetch_xml_2/{id}"
        new_anchor = f'<br><a href="{new_link}">{id}</a>'
        package_links = package_links + new_anchor

    help = get_helps(['fetch_from_edi'])
    return render_template('fetch_xml.html', package_links=package_links, form=form, help=help)


@home.route('/fetch_xml_2/<scope>', methods=['GET', 'POST'])
@login_required
def fetch_xml_2(scope=''):

    form = EDIForm()

    # Process POST

    reload_metadata()  # So check_metadata status is correct

    if request.method == 'POST' and BTN_CANCEL in request.form:
        filename = user_data.get_active_document()
        if filename:
            return redirect(url_for(PAGE_TITLE, filename=filename))
        else:
            return redirect(url_for(PAGE_INDEX))

    # Process GET
    form.md5.data = form_md5(form)

    ids = get_pasta_identifiers(scope)
    package_links = ''
    parsed_url = urlparse(request.base_url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}/eml"
    for id in ids:
        new_link = f"{base_url}/fetch_xml_3/{scope}.{id}"
        new_anchor = f'<br><a href="{new_link}">{scope}.{id}</a>'
        package_links = package_links + new_anchor

    help = get_helps(['fetch_from_edi'])
    return render_template('fetch_xml_2.html', package_links=package_links, form=form, help=help)


@home.route('/fetch_xml_3/<scope_identifier>', methods=['GET', 'POST'])
@login_required
def fetch_xml_3(scope_identifier=''):

    form = EDIForm()

    # Process POST

    reload_metadata()  # So check_metadata status is correct

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(url_for(PAGE_TITLE, filename=None))

    # Process GET
    form.md5.data = form_md5(form)

    scope, identifier = scope_identifier.split('.')
    try:
        revision, metadata = get_newest_metadata_revision_from_pasta(scope, identifier)
        log_usage(actions['FETCH_FROM_EDI'], f"{scope}.{identifier}.{revision}")
    except (AuthTokenExpired, Unauthorized) as e:
        flash(AUTH_TOKEN_FLASH_MSG, 'error')
        help = get_helps(['import_xml_3'])
        return redirect(url_for('home.fetch_xml', form=form, help=help))
    except Exception as e:
        flash(f'Unable to fetch package {scope}.{identifier}: {str(e)}', 'error')
        help = get_helps(['import_xml_3'])
        return redirect(url_for('home.fetch_xml', form=form, help=help))

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

    # See if package with that name already exists
    if package_name in user_data.get_user_document_list():
        return redirect(url_for('home.import_xml_2', package_name=package_name, filename=filename, fetched=True))

    user_data_dir = user_data.get_user_folder_name()
    work_path = os.path.join(user_data_dir, 'zip_temp')
    filepath = os.path.join(work_path, filename)

    eml_node, unknown_nodes, attr_errs, child_errs, other_errs, pruned_nodes = parse_xml_file(filename, filepath)

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
                                    unknown_nodes=encode_for_query_string(unknown_nodes),
                                    attr_errs=encode_for_query_string(attr_errs),
                                    child_errs=encode_for_query_string(child_errs),
                                    other_errs=encode_for_query_string(other_errs),
                                    pruned_nodes=encode_for_query_string(pruned_nodes),
                                    filename=package_name,
                                    fetched=True))
        else:
            flash(f"{package_name} was imported without errors")
            return redirect(url_for(PAGE_IMPORT_XML_4, filename=package_name, fetched=True))
    else:
        raise Exception  # TODO: Error handling

    help = get_helps(['import_xml_3'])
    return render_template('fetch_xml_3.html', package_links=package_links, form=form, help=help)


@home.route('/import_package', methods=['GET', 'POST'])
@login_required
def import_package():
    form = ImportPackageForm()

    package_list = user_data.get_user_document_list()

    # Process POST

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    reload_metadata()  # So check_metadata status is correct

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
                return redirect(url_for('home.import_package_2', package_name=unversioned_package_name))
            else:
                import_ezeml_package(unversioned_package_name)
                fixup_upload_management()
                cull_uploads(unversioned_package_name)
                current_user.set_filename(filename=unversioned_package_name)
                log_usage(actions['IMPORT_EZEML_DATA_PACKAGE'])
                return redirect(url_for(PAGE_TITLE, filename=unversioned_package_name))

    # Process GET
    help = get_helps(['import_package'])
    return render_template('import_package.html', title='Import an ezEML Data Package',
                           packages=package_list, form=form, help=help)


@home.route('/import_package_2/<package_name>', methods=['GET', 'POST'])
@login_required
def import_package_2(package_name):
    form = ImportPackageForm()

    # Process POST

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    reload_metadata()  # So check_metadata status is correct

    if request.method == 'POST' and form.validate_on_submit():
        form = request.form
        if form['replace_copy'] == 'copy':
            package_name = copy_ezeml_package(package_name)

        import_ezeml_package(package_name)
        fixup_upload_management()
        cull_uploads(package_name)
        current_user.set_filename(filename=package_name)
        log_usage(actions['IMPORT_EZEML_DATA_PACKAGE'])
        return redirect(url_for(PAGE_TITLE, filename=package_name))

    # Process GET
    help = get_helps(['import_package_2'])
    return render_template('import_package_2.html', title='Import an ezEML Data Package',
                           package_name=package_name, form=form, help=help)


def column_names_changed(filepath, delimiter, quote_char, dt_node):
    # Assumes CSV file has been saved to the file system
    # This function is called only in the reupload case.

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

    return old_column_names != new_column_names


def clear_distribution_url(entity_node):
    distribution_node = entity_node.find_descendant(names.DISTRIBUTION)
    if distribution_node:
        url_node = distribution_node.find_descendant(names.URL)
        if url_node:
            url_node.content = None


@home.route('/get_data_file/', methods=['GET', 'POST'])
@login_required
def get_data_file():
    if current_user and hasattr(current_user, 'get_username'):
        username = current_user.get_username()
        if username != 'EDI':
            flash('The get_data_file page is available only to the EDI user.', 'error')
            return render_template('index.html')

    form = SelectUserForm()

    if BTN_CANCEL in request.form:
        return redirect(get_back_url())

    if request.method == 'POST':
        user = form.user.data
        return redirect(url_for('home.get_data_file_2', user=user))

    if request.method == 'GET':
        # Get the list of users
        user_data_dir = user_data.USER_DATA_DIR
        filelist = glob.glob(f'{user_data_dir}/*')
        files = sorted([os.path.basename(x) for x in filelist if '-' in os.path.basename(x)], key=str.casefold)
        # print(files)
        form.user.choices = files
        return render_template('get_data_file.html', form=form)


def download_data_file(filename: str = '', user: str=''):
    if filename:
        user_data_dir = user_data.USER_DATA_DIR
        filepath = f'../{user_data_dir}/{user}/uploads/{filename}'
        return send_file(filepath, as_attachment=True, attachment_filename=os.path.basename(filename))


@home.route('/get_data_file_2/<user>', methods=['GET', 'POST'])
@login_required
def get_data_file_2(user):
    if current_user and hasattr(current_user, 'get_username'):
        username = current_user.get_username()
        if username != 'EDI':
            flash('The get_data_file page is available only to the EDI user.', 'error')
            return render_template('index.html')

    form = SelectDataFileForm()

    if BTN_CANCEL in request.form:
        return redirect(get_back_url())

    if request.method == 'POST':
        data_file = form.data_file.data
        # Get the data file
        return download_data_file(data_file, user)

    if request.method == 'GET':
        # Get the list of data files for the user
        csv_list = []
        user_data_dir = user_data.USER_DATA_DIR
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


@home.route('/get_eml_file/', methods=['GET', 'POST'])
@login_required
def get_eml_file():
    if current_user and hasattr(current_user, 'get_username'):
        username = current_user.get_username()
        if username != 'EDI':
            flash('The get_eml_file page is available only to the EDI user.', 'error')
            return render_template('index.html')

    form = SelectUserForm()

    if BTN_CANCEL in request.form:
        return redirect(get_back_url())

    if request.method == 'POST':
        user = form.user.data
        return redirect(url_for('home.get_eml_file_2', user=user))

    if request.method == 'GET':
        # Get the list of users
        user_data_dir = user_data.USER_DATA_DIR
        filelist = glob.glob(f'{user_data_dir}/*')
        files = sorted([os.path.basename(x) for x in filelist if '-' in os.path.basename(x)], key=str.casefold)
        # print(files)
        form.user.choices = files
        return render_template('get_eml_file.html', form=form)


def download_eml_file(filename: str = '', user: str=''):
    if filename:
        # We will create and download a zip file with both the xml and json files
        edi_user_folder = user_data.get_user_folder_name()
        user_folder = os.path.join(user_data.USER_DATA_DIR, user)
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
        return send_file('../' + zip_file_pathname, as_attachment=True, attachment_filename=basename + '.zip')


@home.route('/get_eml_file_2/<user>', methods=['GET', 'POST'])
@login_required
def get_eml_file_2(user):
    if current_user and hasattr(current_user, 'get_username'):
        username = current_user.get_username()
        if username != 'EDI':
            flash('The get_eml_file page is available only to the EDI user.', 'error')
            return render_template('index.html')

    form = SelectEMLFileForm()

    if BTN_CANCEL in request.form:
        return redirect(get_back_url())

    if request.method == 'POST':
        eml_file = form.eml_file.data
        # Get the data file
        return download_eml_file(eml_file, user)

    if request.method == 'GET':
        # Get the list of eml files for the user
        csv_list = []
        user_data_dir = user_data.USER_DATA_DIR
        xml_files = glob.glob(f'{user_data_dir}/{user}/*.xml')
        xml_files = sorted([os.path.basename(x) for x in xml_files], key=str.casefold)
        form.eml_file.choices = xml_files
        return render_template('get_eml_file_2.html', form=form)


@home.route('/reupload_data_with_col_names_changed/<saved_filename>/<dt_node_id>', methods=['GET', 'POST'])
@login_required
def reupload_data_with_col_names_changed(saved_filename, dt_node_id):

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


def data_table_is_unique(eml_node, data_table_filename):
    data_table_name, _ = os.path.splitext(os.path.basename(data_table_filename))
    data_table_nodes = []
    eml_node.find_all_descendants(names.DATATABLE, data_table_nodes)
    for data_table_node in data_table_nodes:
        data_table_name_node = data_table_node.find_child(names.ENTITYNAME)
        if data_table_name_node and data_table_name_node.content == data_table_name:
            return False
        data_table_object_name_node = data_table_node.find_descendant(names.OBJECTNAME)
        if data_table_object_name_node and data_table_object_name_node.content == data_table_filename:
            return False
    return True


@home.route('/load_data/<filename>', methods=['GET', 'POST'])
@login_required
def load_data(filename=None):
    # log_info(f'Entering load_data: request.method={request.method}')
    # filename that's passed in is actually the document name, for historical reasons.
    # We'll clear it to avoid misunderstandings...
    filename = None

    form = LoadDataForm()
    document = current_user.get_filename()
    uploads_folder = user_data.get_document_uploads_folder_name()

    # Process POST

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    if request.method == 'POST' and form.validate_on_submit():

        # Check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)

        eml_node = load_eml(filename=document)
        dataset_node = eml_node.find_child(names.DATASET)
        if not dataset_node:
            dataset_node = new_child_node(names.DATASET, eml_node)

        file = request.files['file']
        if file:
            filename = file.filename

        if filename:
            if filename is None or filename == '':
                flash('No selected file', 'error')
            elif allowed_data_file(filename):
                # Make sure we don't already have a data table with this name
                if not data_table_is_unique(eml_node, filename):
                    flash('The selected name has already been used in this data package. Data table names must be unique within a data package.', 'error')
                    return redirect(request.url)

                # Make sure the user's uploads directory exists
                Path(uploads_folder).mkdir(parents=True, exist_ok=True)
                filepath = os.path.join(uploads_folder, filename)
                if file:
                    # Upload the file to the uploads directory
                    file.save(filepath)

                num_header_rows = '1'
                delimiter = form.delimiter.data
                quote_char = form.quote.data

                try:
                    dt_node, new_column_vartypes, new_column_names, new_column_categorical_codes, *_ = \
                        load_data_table(uploads_folder, filename, num_header_rows, delimiter, quote_char)

                except UnicodeDecodeError as err:
                    errors = display_decode_error_lines(filepath)
                    return render_template('encoding_error.html', filename=filename, errors=errors)
                except UnicodeDecodeErrorInternal as err:
                    filepath = err.message
                    errors = display_decode_error_lines(filepath)
                    return render_template('encoding_error.html', filename=os.path.basename(filepath), errors=errors)
                except DataTableError as err:
                    flash(f'Data table has an error: {err.message}', 'error')
                    return redirect(request.url)

                flash(f"Loaded {filename}")

                dt_node.parent = dataset_node
                dataset_node.add_child(dt_node)

                user_data.add_data_table_upload_filename(filename)
                if new_column_vartypes:
                    user_data.add_uploaded_table_properties(filename,
                                                  new_column_vartypes,
                                                  new_column_names,
                                                  new_column_categorical_codes)

                delete_data_files(uploads_folder)

                clear_distribution_url(dt_node)
                insert_upload_urls(document, eml_node)
                log_usage(actions['LOAD_DATA_TABLE'], filename)

                check_data_table_contents.set_check_data_tables_badge_status(document, eml_node)
                save_both_formats(filename=document, eml_node=eml_node)

                return redirect(url_for(PAGE_DATA_TABLE, filename=document, dt_node_id=dt_node.id, delimiter=delimiter, quote_char=quote_char))

            else:
                flash(f'{filename} is not a supported data file type')
                return redirect(request.url)

    # Process GET
    return render_template('load_data.html', title='Load Data',
                           form=form)


def handle_reupload(dt_node_id=None, saved_filename=None, document=None,
                    eml_node=None, uploads_folder=None, name_chg_ok=False,
                    delimiter=None, quote_char=None):

    dataset_node = eml_node.find_child(names.DATASET)
    if not dataset_node:
        dataset_node = new_child_node(names.DATASET, eml_node)

    if not saved_filename:
        raise MissingFileError('Unexpected error: file not found')

    dt_node = Node.get_node_instance(dt_node_id)

    num_header_rows = '1'
    filepath = os.path.join(uploads_folder, saved_filename)

    if not name_chg_ok:
        try:
            if column_names_changed(filepath, delimiter, quote_char, dt_node):
                # Go get confirmation
                return redirect(url_for(PAGE_REUPLOAD_WITH_COL_NAMES_CHANGED,
                                        saved_filename=saved_filename,
                                        dt_node_id=dt_node_id),
                                code=307)
        except UnicodeDecodeError as err:
            errors = display_decode_error_lines(filepath)
            filename = os.path.basename(filepath)
            return render_template('encoding_error.html', filename=filename, errors=errors)

    try:
        new_dt_node, new_column_vartypes, new_column_names, new_column_categorical_codes, *_ = load_data_table(
            uploads_folder, saved_filename, num_header_rows, delimiter, quote_char)

        types_changed = None
        try:
            check_data_table_similarity(dt_node,
                                        new_dt_node,
                                        new_column_vartypes,
                                        new_column_names,
                                        new_column_categorical_codes)
        except ValueError as err:
            types_changed = err.args[0]

        except FileNotFoundError as err:
            error = err.args[0]
            flash(error, 'error')
            return redirect(url_for(PAGE_DATA_TABLE_SELECT, filename=document))

        except IndexError as err:
            error = err.args[0]
            flash(f'Re-upload not done. {error}', 'error')
            return redirect(url_for(PAGE_DATA_TABLE_SELECT, filename=document))

        try:
            # use the existing dt_node, but update objectName, size, rows, MD5, etc.
            # also, update column names and categorical codes, as needed
            update_data_table(dt_node, new_dt_node, new_column_names, new_column_categorical_codes)
            # rename the temp file
            os.rename(filepath, filepath.replace('.ezeml_tmp', ''))

            if types_changed:
                err_string = 'Please note: One or more columns in the new table have a different data type than they had in the old table.<ul>'
                for col_name, old_type, new_type, attr_node in types_changed:
                    dt.change_measurement_scale(attr_node, old_type.name, new_type.name)
                    err_string += f'<li><b>{col_name}</b> changed from {old_type.name} to {new_type.name}'
                err_string += '</ul>'
                flash(Markup(err_string))

        except Exception as err:
            # display error
            error = err.args[0]
            flash(f"Data table could not be re-uploaded. {error}", 'error')
            return redirect(url_for(PAGE_DATA_TABLE_SELECT, filename=document))

    except UnicodeDecodeError as err:
        errors = display_decode_error_lines(filepath)
        return render_template('encoding_error.html', filename=document, errors=errors)

    except UnicodeDecodeErrorInternal as err:
            filepath = err.message
            errors = display_decode_error_lines(filepath)
            return render_template('encoding_error.html', filename=os.path.basename(filepath), errors=errors)

    except DataTableError as err:
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
                                                new_column_categorical_codes)

    delete_data_files(uploads_folder)

    clear_distribution_url(dt_node)
    insert_upload_urls(document, eml_node)

    backup_metadata(filename=document)  # FIXME - what is this doing? is it obsolete?

    check_data_table_contents.reset_data_file_eval_status(document, data_file)
    check_data_table_contents.set_check_data_tables_badge_status(document, eml_node)

    save_both_formats(filename=document, eml_node=eml_node)
    return redirect(url_for(PAGE_DATA_TABLE, filename=document, dt_node_id=dt_node.id, delimiter=delimiter,
                            quote_char=quote_char))


@home.route('/reupload_data/<filename>/<dt_node_id>', methods=['GET', 'POST'])
@home.route('/reupload_data/<filename>/<dt_node_id>/<saved_filename>/<name_chg_ok>', methods=['GET', 'POST'])
@login_required
def reupload_data(dt_node_id=None, filename=None, saved_filename=None, name_chg_ok=False):
    # filename that's passed in is actually the document name, for historical reasons.
    # We'll clear it to avoid misunderstandings...
    filename = None

    form = LoadDataForm()
    document = current_user.get_filename()
    uploads_folder = user_data.get_document_uploads_folder_name()
    eml_node = load_eml(filename=document)

    data_table_name = ''
    dt_node = Node.get_node_instance(dt_node_id)
    if dt_node:
        entity_name_node = dt_node.find_child(names.ENTITYNAME)
        if entity_name_node:
            data_table_name = entity_name_node.content
            if not data_table_name:
                flash(f'Data table name not found in the metadata.', 'error')
                return redirect(request.url)

    if request.method == 'POST' and BTN_CANCEL in request.form:
        url = url_for(PAGE_DATA_TABLE_SELECT, filename=document)
        return redirect(url)

    if request.method == 'POST':
        if dt_node:
            if saved_filename:
                filename = saved_filename
                unmodified_filename = filename
            else:
                file = request.files['file']
                if file:
                    filename = f"{file.filename}"
                    unmodified_filename = filename
                    if allowed_data_file(filename):
                        # We upload the new version of the CSV file under a temp name so we have both files to inspect.
                        filename = f"{filename}.ezeml_tmp"
                        filepath = os.path.join(uploads_folder, filename)
                        file.save(filepath)
                    else:
                        flash(f'{filename} is not a supported data file type', 'error')
                        return redirect(request.url)

            delimiter = form.delimiter.data
            quote_char = form.quote.data

            try:
                goto = handle_reupload(dt_node_id=dt_node_id, saved_filename=filename, document=document,
                                       eml_node=eml_node, uploads_folder=uploads_folder, name_chg_ok=name_chg_ok,
                                       delimiter=delimiter, quote_char=quote_char)
                log_usage(actions['RE_UPLOAD_DATA_TABLE'], unmodified_filename)
                return goto

            except MissingFileError as err:
                flash(err.message, 'error')
                return redirect(request.url)

            except Exception as err:
                return redirect(request.url)

    # Process GET
    help = get_helps(['data_table_reupload_full'])
    return render_template('reupload_data.html', title='Re-upload Data Table',
                           form=form, name=data_table_name, help=help)


@home.route('/reupload_other_entity/<filename>/<node_id>', methods=['GET', 'POST'])
@login_required
def reupload_other_entity(filename, node_id):
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


@home.route('/load_other_entity/<node_id>', methods=['GET', 'POST'])
@login_required
def load_entity(node_id=None):
    form = LoadOtherEntityForm()
    document = current_user.get_filename()
    uploads_folder = user_data.get_document_uploads_folder_name()

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
            # TODO: Possibly reconsider whether to use secure_filename in the future. It would require
            #  separately keeping track of the original filename and the possibly modified filename.
            # filename = secure_filename(file.filename)
            filename = file.filename

            if filename is None or filename == '':
                flash('No selected file', 'error')
            else:
                file.save(os.path.join(uploads_folder, filename))
                data_file = filename
                data_file_path = f'{uploads_folder}/{data_file}'
                flash(f'Loaded {data_file}')
                eml_node = load_eml(filename=document)
                dataset_node = eml_node.find_child(names.DATASET)
                other_entity_node = load_other_entity(dataset_node, uploads_folder, data_file, node_id=node_id)

                doing_reupload = node_id is not None and node_id != '1'
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


@home.route('/load_metadata', methods=['GET', 'POST'])
@login_required
def load_metadata():
    form = LoadMetadataForm()
    document = current_user.get_filename()
    uploads_folder = user_data.get_document_uploads_folder_name()

    # Process POST
    if  request.method == 'POST' and form.validate_on_submit():
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


@home.route('/close', methods=['GET', 'POST'])
@login_required
def close():
    current_document = current_user.get_filename()
    
    if current_document:
        log_usage(actions['CLOSE_DOCUMENT'])
        current_user.set_filename(None)
        flash(f'Closed {current_document}')
    else:
        flash("There was no package open")

    set_current_page('')

    return render_template('index.html')


def select_post(filename=None, form=None, form_dict=None,
                method=None, this_page=None, back_page=None, 
                next_page=None, edit_page=None, project_node_id=None, reupload_page=None):

    def extract_ids(key):
        if '|' not in key:
            node_id = key
            project_node_id = None
        else:
            node_id, project_node_id = key.split('|')
            if project_node_id == 'None':
                project_node_id = None
        return node_id, project_node_id

    node_id = None
    new_page = None

    if form_dict:
        for key in form_dict:
            val = form_dict[key][0]  # value is the first list element
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
                node_id, project_node_id = extract_ids(key)
            elif val == BTN_REMOVE:
                new_page = this_page
                node_id, project_node_id = extract_ids(key)
                eml_node = load_eml(filename=filename)
                # Get the data table filename, if any, so we can remove it from the uploaded list
                # dt_node = Node.get_node_instance(node_id)
                # if dt_node and dt_node.name == names.DATATABLE:
                #     object_name_node = dt_node.find_single_node_by_path([names.PHYSICAL, names.OBJECTNAME])
                #     if object_name_node:
                #         object_name = object_name_node.content
                #         if object_name:
                #             user_data.discard_data_table_upload_filename(object_name)
                remove_child(node_id=node_id)
                # node_id = project_node_id  # for relatedProject case
                save_both_formats(filename=filename, eml_node=eml_node)
            elif val == BTN_REUPLOAD:
                node_id, project_node_id = extract_ids(key)
                if reupload_page:
                    new_page = reupload_page
                else:
                    # node_id = key
                    new_page = PAGE_REUPLOAD
            elif val == UP_ARROW:
                new_page = this_page
                node_id, project_node_id = extract_ids(key)
                process_up_button(filename, node_id)
            elif val == DOWN_ARROW:
                new_page = this_page
                node_id, project_node_id = extract_ids(key)
                process_down_button(filename, node_id)
            elif val[0:3] == BTN_ADD:
                new_page = edit_page
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
            new_page = check_val_for_hidden_buttons(val, new_page, this_page)

    if form.validate_on_submit():
        if new_page in [PAGE_DATA_TABLE, PAGE_LOAD_DATA, PAGE_REUPLOAD, PAGE_REUPLOAD_WITH_COL_NAMES_CHANGED ]:
            return url_for(new_page, filename=filename, dt_node_id=node_id, project_node_id=project_node_id)
        else:
            return url_for(new_page, filename=filename, node_id=node_id, project_node_id=project_node_id)


def process_up_button(filename:str=None, node_id:str=None):
    process_updown_button(filename, node_id, move_up)


def process_down_button(filename:str=None, node_id:str=None):
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

    # date.fromisoformat() is a Python 3.7 feature
    #if begin_date_str and end_date_str:
        #begin_date = date.fromisoformat(begin_date_str)
        #end_date = date.fromisoformat(end_date_str)

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
    session['current_page'] = page


def get_current_page():
    return session.get('current_page')
