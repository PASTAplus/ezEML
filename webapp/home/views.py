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
import shutil

import daiquiri
from datetime import date, datetime
import html
import json
import math
import glob
import os.path
import pandas as pd
from pathlib import Path
import pickle
import requests
from shutil import copyfile
from urllib.parse import urlparse, quote
from zipfile import ZipFile
from lxml import etree #pt7/16
import re

from flask import (
    Blueprint, flash, render_template, redirect, request, url_for, session, Markup
)

from flask_login import (
    current_user, login_required
)

from flask import Flask, current_app

from webapp import mailout

from webapp.config import Config

# import csv

from webapp.home.exceptions import DataTableError, MissingFileError

from webapp.home.forms import (
    CreateEMLForm, DownloadEMLForm, ImportPackageForm,
    OpenEMLDocumentForm, DeleteEMLForm, SaveAsForm,
    LoadDataForm, LoadMetadataForm, LoadOtherEntityForm,
    ImportEMLForm, ImportEMLItemsForm, ImportItemsForm,
    SubmitToEDIForm, SendToColleagueForm
)

from webapp.home.load_data_table import (
    load_data_table, load_other_entity, delete_data_files, get_md5_hash
)
from webapp.home.import_package import (
    copy_ezeml_package, upload_ezeml_package, import_ezeml_package
)

from webapp.home.metapype_client import (
    load_eml, save_both_formats, new_child_node, remove_child, create_eml,
    move_up, move_down, UP_ARROW, DOWN_ARROW, RELEASE_NUMBER,
    save_old_to_new, read_xml, new_child_node, truncate_middle,
    compose_rp_label, compose_full_gc_label, compose_taxonomic_label,
    compose_funding_award_label, compose_project_label, list_data_packages,
    import_responsible_parties, import_coverage_nodes, import_funding_award_nodes,
    import_project_nodes, get_check_metadata_status, clear_other_entity, set_session_vars
)

from webapp.home.motherpype import clean_mother_node, get_image_name_node

from webapp.home.check_metadata import check_eml

from webapp.home import motherpype_names as mdb_names

from webapp.buttons import *
from webapp.pages import *

from metapype.eml import names
from metapype.model import mp_io
from metapype.model.node import Node
from werkzeug.utils import secure_filename

import webapp.views.data_tables.dt as dt
import webapp.auth.user_data as user_data

from metapype.model import metapype_io

logger = daiquiri.getLogger('views: ' + __name__)
home = Blueprint('home', __name__, template_folder='templates')
help_dict = {}
keywords = {}


def log_info(msg):
    app = Flask(__name__)
    with app.app_context():
        current_app.logger.info(msg)


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


@home.before_app_first_request
def init_session_vars():
    session["check_metadata_status"] = "green"
    session['thumb_name'] = "unavailable"


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


# code in here will run only once for every initial page load by checking for the home blueprint
# does not occur after form submission since the reused blueprint's data does not get reloaded
@home.before_request
def on_load_save(filename: str = None, eml_node: Node = None):
    if current_user.is_authenticated and filename and eml_node:
        set_session_vars(filename, eml_node)


@home.before_app_request
@home.before_app_first_request
def init_keywords():
    lter_keywords = pickle.load(open('webapp/static/lter_keywords.pkl', 'rb'))
    keywords['LTER'] = lter_keywords


def get_keywords(which):
    return keywords.get(which, [])


@home.before_app_request
@home.before_app_first_request
def init_help():
    lines = []
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
            eml_node = load_eml(filename=current_filename)
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
    return render_template('user_guide.html', back_url=get_back_url(), title='User Guide')


@home.route('/news')
def news():
    return render_template('news.html', back_url=get_back_url(), title="What's New")


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
                # new_filename = current_document  # Revert back to the old filename
            else:
                # copy_uploads(current_document, new_document)
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


@home.route('/check_metadata/<filename>', methods=['GET', 'POST'])
@login_required
def check_metadata(filename:str):
    current_document = user_data.get_active_document()
    if not current_document:
        raise FileNotFoundError
    eml_node = load_eml(filename=current_document)
    content = check_eml(eml_node, filename)
    help = [get_help('check_metadata')]
    # Process POST
    if request.method == 'POST':
        # return render_template(PAGE_CHECK, filename=filename)
        return redirect(url_for(PAGE_CHECK, filename=current_document))

    else:
        set_current_page('check_metadata')
        return render_template('check_metadata.html', content=content, title='Check Metadata', help=help)


@home.route('/download_current', methods=['GET', 'POST'])
@login_required
def download_current():
    current_document = user_data.get_active_document()
    if current_document:
        user_folder = user_data.get_user_folder_name()
        current_xml = current_document + '.xml'

        # Force the document to be saved, so it gets cleaned
        eml_node = load_eml(filename=current_document)
        save_both_formats(filename=current_document, eml_node=eml_node)
        # create a duplicate before running clean_mother_node on the original xml file
        shutil.copy(f'{user_folder}/{current_xml}', f'{user_folder}/temp_{current_xml}')
        clean_mother_node(eml_node, current_document)

        # Do the download
        return_value = user_data.download_eml(filename=current_document)
        if isinstance(return_value, str):
            flash(return_value)
        else:
            try:
                return return_value
            finally:
                # replace the original file with the old copy
                shutil.move(f'{user_folder}/temp_{current_xml}', f'{user_folder}/{current_xml}')



@home.route('/download_submission', methods=['GET', 'POST'])
@login_required
def download_submission():
    current_document = user_data.get_active_document()
    if current_document:
        # Do the download
        return_value = user_data.download_zip(filename=current_document)
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
                flash(f'{filename} already exists')
                return render_template('create_eml.html', help=help,
                                       form=form)
            create_eml(filename=filename)
            current_user.set_filename(filename)
            current_user.set_packageid(None)
            return redirect(url_for(PAGE_TITLE, filename=filename))

    # Process GET
    return render_template('create_eml.html', help=help, form=form)


@home.route('/open_eml_document', methods=['GET', 'POST'])
@login_required
def open_eml_document():
    form = OpenEMLDocumentForm()
    form.filename.choices = list_data_packages(False, False)

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
            else:
                new_page = PAGE_FILE_ERROR
            return redirect(url_for(new_page, filename=filename))

    # Process GET
    return render_template('open_eml_document.html', title='Open EML Document',
                           form=form)


@home.route('/import_parties', methods=['GET', 'POST'])
@login_required
def import_parties():
    form = ImportEMLForm()
    form.filename.choices = list_data_packages(True, True)

    # Process POST
    if request.method == 'POST':
        if BTN_CANCEL in request.form:
            return redirect(get_back_url())
            # new_page = get_redirect_target_page()
            # url = url_for(new_page, filename=current_user.get_filename())
            # return redirect(url)

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
        return PAGE_OTHER_ENTITY
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
        import_coverage_nodes(target_package, node_ids_to_import)
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
    coverages = get_projects_for_import(eml_node)
    choices = [[coverage[1], coverage[0]] for coverage in coverages]
    form.to_import.choices = choices

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    if form.validate_on_submit():
        node_ids_to_import = form.data['to_import']
        target_package = current_user.get_filename()
        import_project_nodes(target_package, node_ids_to_import)
        return redirect(url_for(PAGE_RELATED_PROJECT_SELECT, filename=target_package))

    # Process GET
    help = get_helps(['import_related_projects_2'])
    return render_template('import_related_projects_2.html', help=help, target_filename=filename, form=form)


def get_projects_for_import(eml_node):
    projects = []
    project = eml_node.find_single_node_by_path([names.DATASET, names.PROJECT])
    project_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.PROJECT, names.RELATED_PROJECT])
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


def zip_package(current_document=None, eml_node=None):
    if not current_document:
        current_document = current_user.get_filename()
    if not current_document:
        raise FileNotFoundError
    if not eml_node:
        eml_node = load_eml(filename=current_document)

    user_folder = user_data.get_user_folder_name()

    zipfile_name = f'{current_document}.zip'
    zipfile_path = os.path.join(user_folder, zipfile_name)
    zip_object = ZipFile(zipfile_path, 'w')

    manifest_files = []

    pathname = f'{user_folder}/{current_document}.json'
    arcname = f'{current_document}.json'
    zip_object.write(pathname, arcname)
    manifest_files.append(('JSON', f'{current_document}.json', pathname))

    package_id = user_data.get_active_packageid()
    if package_id:
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
                flash(msg, category='error')
                return None
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
        save_both_formats(current_document, eml_node)
        zipfile_path = zip_package(current_document, eml_node)
        if zipfile_path:
            archive_basename, download_url = save_as_ezeml_package_export(zipfile_path)
            if download_url:
                return redirect(url_for('home.export_package_2', package_name=archive_basename,
                                        download_url=get_shortened_url(download_url), safe=''))
        archive_basename, download_url = save_as_ezeml_package_export(zipfile_path)
        if download_url:

            return redirect(url_for('home.export_package_2', package_name=archive_basename,
                                    download_url=get_shortened_url(download_url), safe=''))

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


def submit_package_mail_body(name=None, email_address=None, archive_name=None, download_url=None, notes=None):
    msg = 'Dear EDI Data Curator:' + '\n\n' + \
        'This email was auto-generated by ezEML.\n\n\n' + \
        'Please submit the following data package to the EDI data repository.\n\n' + \
        '   Sender\'s name: ' + name + '\n\n' + \
        '   Sender\'s email: ' + email_address + '\n\n' + \
        '   Package name: ' + archive_name + '\n\n' + \
        '   Download URL: ' + get_shortened_url(download_url) + '\n\n'  # Note: get_shortened_url handles blanks
    if notes:
        msg += '   Sender\'s Notes: ' + notes
    return msg


def insert_urls(uploads_url_prefix, eml_node, node_type):
    upload_nodes = []
    eml_node.find_all_descendants(node_type, upload_nodes)
    for upload_node in upload_nodes:
        try:
            physical_node = upload_node.find_descendant(names.PHYSICAL)
            object_name_node = physical_node.find_child(names.OBJECTNAME)
            object_name = object_name_node.content
            distribution_node = physical_node.find_child(names.DISTRIBUTION)
            if distribution_node:
                physical_node.remove_child(distribution_node)
            distribution_node = new_child_node(names.DISTRIBUTION, physical_node)
            online_node = new_child_node(names.ONLINE, distribution_node)
            url_node = new_child_node(names.URL, online_node)
            url_node.add_attribute('function', 'download')
            url_node.content = f"{uploads_url_prefix}/{object_name}".replace(' ', '%20')
        except Exception as err:
            flash(err)
            continue


def insert_upload_urls(current_document, eml_node):
    user_folder = user_data.get_user_folder_name()
    uploads_folder = f'{user_folder}/uploads/{current_document}'

    parsed_url = urlparse(request.base_url)
    uploads_url_prefix = f"{parsed_url.scheme}://{parsed_url.netloc}/{uploads_folder}"

    insert_urls(uploads_url_prefix, eml_node, names.DATATABLE)
    insert_urls(uploads_url_prefix, eml_node, names.OTHERENTITY)


@home.route('/submit_package', methods=['GET', 'POST'])
@login_required
def submit_package():
    form = SubmitToEDIForm()

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    if form.validate_on_submit():
        # If the user has clicked Save in the EML Documents menu, for example, we want to ignore the
        # programmatically generated Submit
        if request.form.get(BTN_SUBMIT) == BTN_SUBMIT_TO_EDI:
            name = form.data['name']
            email_address = form.data['email_address']
            notes = form.data['notes']

            # update the EML to include URLs to data table files and other entity files
            insert_upload_urls(current_document, eml_node)
            save_both_formats(filename=current_document, eml_node=eml_node)

            zipfile_path = zip_package(current_document, eml_node)
            if zipfile_path:
                _, download_url = save_as_ezeml_package_export(zipfile_path)

                msg = submit_package_mail_body(name, email_address, current_document, download_url, notes)
                subject = 'ezEML-Generated Data Submission Request'
                to_address = ['support@environmentaldatainitiative.org']
                sent = mailout.send_mail(subject=subject, msg=msg, to=to_address)
                if sent:
                    flash(f'Package {current_document} has been sent to EDI. We will notify you when it has been added to the repository.')
                else:
                    flash(f'Email failed to send', 'error')

            return redirect(get_back_url())

    set_current_page('submit_package')
    help = get_helps(['submit_package'])
    return render_template('submit_package.html',
                           title='Send to EDI',
                           check_metadata_status=get_check_metadata_status(eml_node, current_document),
                           form=form, help=help)


def get_shortened_url(long_url):
    # Note: full URL encoding via urllib.parse.quote causes hideuri to throw an error that URL is invalid.
    #  So, we just encode blanks.
    r = requests.post('https://hideuri.com/api/v1/shorten', data={'url': long_url.replace(' ', '%20')})
    try:
        r.raise_for_status()
        return r.json()['result_url']
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

    # set temp and upload folders
    user_folder = user_data.get_user_folder_name()
    upload_folder = user_data.get_document_uploads_folder_name()
    temp_folder = user_data.get_temp_folder()
    image_name = get_image_name_node()

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    current_document, eml_node = reload_metadata()  # So check_metadata status is correct

    if form.validate_on_submit():
        # colleague_name = form.data['colleague_name']
        # email_address = form.data['email_address']

        dataset_node = eml_node.find_child(child_name=names.DATASET)
        title_node = dataset_node.find_child(names.TITLE)
        title = ''
        if title_node:
            title = title_node.content
        if not title:
            flash('The image requires a Title.', 'error')
            return redirect(get_back_url())

        name_node = dataset_node.find_single_node_by_path([names.OTHERENTITY, names.ENTITYNAME])
        name = ''
        if name_node:
            name = name_node.content
        if not name:
            flash('The image requires a Name.', 'error')
            return redirect(get_back_url())

        # clear appropriate uploads folder
        user_data.clear_folder(upload_folder)

        # move files from temp folder to appropriate uploads folder
        images = glob.glob(os.path.join(temp_folder, '*'))
        for f in images:
            fname = os.path.basename(f)
            if fname == user_data.get_image_full_name_node():
                shutil.copy(f, f'{upload_folder}/{fname}')

        # copy xml file to uploads folder
        eml_node = load_eml(filename=current_document)
        save_both_formats(filename=current_document, eml_node=eml_node)
        current_xml = current_document + '.xml'
        # create a duplicate before running clean_mother_node on the original xml file
        shutil.copy(f'{user_folder}/{current_xml}',f'{user_folder}/temp_{current_xml}')
        clean_mother_node(eml_node, current_document)
        shutil.move(user_folder + '/' + current_xml, f'{upload_folder}/{image_name}.xml')
        shutil.move(f'{user_folder}/temp_{current_xml}', f'{user_folder}/{current_xml}')

        # create zip of uploads folder
        zipfile_path = os.path.join(user_folder, current_document)
        shutil.make_archive(zipfile_path, 'zip', upload_folder)

        # zipfile_path = zip_package(current_document, eml_node)
        # _, download_url = save_as_ezeml_package_export(zipfile_path)

        if not mailto:
            mailto = True
            # mailto, mailto_html, mailto_raw = send_to_other_email(colleague_name, email_address, title, download_url)
        else:
            mailto = None  # so we don't pop up the email client when the page is returned to after sending the 1st time
            mailto_html = None
            mailto_raw=None

    eml_node = load_eml(filename=filename)
    title_node = eml_node.find_single_node_by_path([names.DATASET, names.TITLE])
    if not title_node or not title_node.content:
        flash('The image must have a Title before it can be submitted.', 'error')
    name_node = eml_node.find_single_node_by_path([names.DATASET, names.OTHERENTITY, names.ENTITYNAME])
    if not name_node or not name_node.content:
        flash('The image must have a Name before it can be submitted.', 'error')

    set_current_page('send_to_other')
    if mailto:
        form.colleague_name.data = ''
        form.email_address.data = ''
        help = get_helps(['send_to_colleague_2'])
        return render_template('send_to_other_2.html',
                               title='Submit Metadata',
                               # mailto=mailto,
                               # mailto_html=mailto_html,
                               # mailto_raw=mailto_raw,
                               zip_path=user_data.get_zip_file_path(),
                               check_metadata_status=get_check_metadata_status(eml_node, current_document),
                               form=form, help=help)
    else:
        help = get_helps(['send_to_colleague'])

        uploads = glob.glob(os.path.join(upload_folder, '*'))
        for f in uploads:
            form.overwrite_existing.data = "Yes"

        return render_template('send_to_other.html',
                               title='Submit Metadata',
                               #set image and xml file names to display
                               image_name=user_data.get_temp_file_name(),
                               xml_name=get_image_name_node(),
                               check_metadata_status=get_check_metadata_status(eml_node, current_document),
                               form=form, help=help)


def get_column_properties(dt_node, object_name):
    data_file = object_name
    column_vartypes, _, _ = user_data.get_uploaded_table_column_properties(data_file)
    if column_vartypes:
        return column_vartypes

    uploads_folder = user_data.get_document_uploads_folder_name()
    num_header_rows = 1
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
        return new_column_vartypes

    except FileNotFoundError:
        raise FileNotFoundError('The older version of the data table is missing from our server. Please use "Load Data Table from CSV File" instead of "Re-upload".')

    except Exception as err:
        raise Exception('Internal error 103')


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
        old_column_vartypes = get_column_properties(old_dt_node, old_object_name)
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


def update_data_table(old_dt_node, new_dt_node, new_column_names, new_column_categorical_codes):
    debug_msg(f'Entering update_data_table')

    if not old_dt_node or not new_dt_node:
        return

    old_object_name_node = old_dt_node.find_descendant(names.OBJECTNAME)
    old_size_node = old_dt_node.find_descendant(names.SIZE)
    old_records_node = old_dt_node.find_descendant(names.NUMBEROFRECORDS)
    old_md5_node = old_dt_node.find_descendant(names.AUTHENTICATION)
    old_field_delimiter_node = old_dt_node.find_descendant(names.FIELDDELIMITER)
    old_record_delimiter_node = old_dt_node.find_descendant(names.RECORDDELIMITER)
    old_quote_char_node = old_dt_node.find_descendant(names.QUOTECHARACTER)

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
    if old_record_delimiter_node:
        if new_record_delimiter_node:
            old_record_delimiter_node.content = new_record_delimiter_node.content
        else:
            old_record_delimiter_node.parent.remove_child(old_record_delimiter_node)
    else:
        if new_record_delimiter_node:
            # make sure needed ancestor nodes exist
            physical_node = add_node_if_missing(old_dt_node, names.PHYSICAL)
            data_format_node = add_node_if_missing(physical_node, names.DATAFORMAT)
            text_format_node = add_node_if_missing(data_format_node, names.TEXTFORMAT)
            new_child_node(names.RECORDDELIMITER, text_format_node).content = new_record_delimiter_node.content
    # quote char node is not required, so may be missing
    if old_quote_char_node:
        if new_quote_char_node:
            old_quote_char_node.content = new_quote_char_node.content
        else:
            old_quote_char_node.parent.remove_child(old_quote_char_node)
    else:
        if new_quote_char_node:
            new_child_node(names.QUOTECHARACTER, old_field_delimiter_node.parent).content = new_quote_char_node.content

    _, old_column_names, old_column_categorical_codes = user_data.get_uploaded_table_column_properties(old_object_name)
    if old_column_names != new_column_names:
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

            if not os.path.splitext(filename)[1] == '.xml':
                flash('Please select a file with file extension ".xml".', 'error')
                return redirect(request.url)

            package_base_filename = os.path.basename(filename)
            package_name = os.path.splitext(package_base_filename)[0]

            # Check package for errors
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

            import_ezeml_package(unversioned_package_name)
            fixup_upload_management()

            filename = user_data.get_active_document()
            # Convert XML file to JSON format
            user_folder = user_data.get_user_folder_name()
            if not user_folder:
                user_folder = '.'
            # Changed filename extension from json to xml format -NM 3/2/2022
            filepath = f"{user_folder}/{filename}.xml"
            with open(filepath, "r") as file:
                data = file.read()

            try:
                xml_to_json = metapype_io.to_json(metapype_io.from_xml(data))
                eml_validator_request = requests.post('https://knb.ecoinformatics.org/emlparser/parse', data={"action": "textparse", "doctext": data})
                pattern = r'<h4>(.*?)<\/h4>'  # Grab h4 elements from html response
                errors_pattern = r'<h4>(.*?)</h4>(?:\s*<p>(.*?)</p>)+' # Get h4 elements and the p elements after that store the error info
                validator_results = re.findall(pattern, eml_validator_request.text)  # [h4 eml, h4 xml]
                error_messages = re.findall(errors_pattern, eml_validator_request.text)

                eml_valid = "Passed" in validator_results[0]
                xml_valid = "Warning" in validator_results[1] or "Passed" in validator_results[1]
                if eml_valid and xml_valid:
                    converted_file = filepath.replace(".xml", ".json")

                    with open(converted_file, "w") as file:
                        file.write(xml_to_json)
                        file.close()

                    # Remove Image data if present
                    user_data.clear_temp_folder()
                    eml_node = load_eml(filename)
                    dataset_node = eml_node.find_child(names.DATASET)
                    if dataset_node:
                        for entity_node in dataset_node.find_all_children(names.OTHERENTITY):
                            clear_other_entity(entity_node)
                        title_node = dataset_node.find_child(names.TITLE)
                        if title_node:
                            dataset_node.remove_child(title_node)
                    slideID_node = eml_node.find_single_node_by_path([names.ADDITIONALMETADATA, names.METADATA, mdb_names.MOTHER, mdb_names.SLIDE_ID])
                    if slideID_node:
                        slideID_node.parent.remove_child(slideID_node)

                    save_both_formats(filename=filename, eml_node=eml_node)
                    return redirect(url_for(PAGE_TITLE, filename=user_data.get_active_document()))
                else:
                    flash("Invalid XML with respect to ezEML and Mother", 'error')
                    if not eml_valid:
                        flash(f"{' '.join(error_messages[0])}")
                    if not xml_valid:
                        flash(f"{' '.join(error_messages[1])}")
            except Exception as e:
                full_string = str(e)
                try:
                    message = full_string.split(',', 1)[0] + '.'
                except:
                    message = type(e).__name__
                flash("Syntax Error: " + message)



    # Process GET
    help = get_helps(['import_package'])
    return render_template('import_package.html', title='Upload XML File',
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
        current_user.set_filename(filename=package_name)
        return redirect(url_for(PAGE_TITLE, filename=package_name))

    # Process GET
    help = get_helps(['import_package_2'])
    return render_template('import_package_2.html', title='Upload XML File',
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


@home.route('/load_data/<filename>', methods=['GET', 'POST'])
@login_required
def load_data(filename=None):
    log_info(f'Entering load_data: request.method={request.method}')
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
                # Make sure the user's uploads directory exists
                Path(uploads_folder).mkdir(parents=True, exist_ok=True)
                filepath = os.path.join(uploads_folder, filename)
                if file:
                    # Upload the file to the uploads directory
                    file.save(filepath)

                num_header_rows = 1
                delimiter = form.delimiter.data
                quote_char = form.quote.data

                try:
                    dt_node, new_column_vartypes, new_column_names, new_column_categorical_codes, *_ = \
                        load_data_table(uploads_folder, filename, num_header_rows, delimiter, quote_char)

                except UnicodeDecodeError as err:
                    errors = display_decode_error_lines(filepath)
                    return render_template('encoding_error.html', filename=filename, errors=errors)
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

    num_header_rows = 1
    filepath = os.path.join(uploads_folder, saved_filename)

    if not name_chg_ok:
        if column_names_changed(filepath, delimiter, quote_char, dt_node):
            # Go get confirmation
            return redirect(url_for(PAGE_REUPLOAD_WITH_COL_NAMES_CHANGED,
                                    saved_filename=saved_filename,
                                    dt_node_id=dt_node_id),
                            code=307)

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

    backup_metadata(filename=document)

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
            else:
                file = request.files['file']
                if file:
                    filename = f"{file.filename}"
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
                return handle_reupload(dt_node_id=dt_node_id, saved_filename=filename, document=document,
                                       eml_node=eml_node, uploads_folder=uploads_folder, name_chg_ok=name_chg_ok,
                                       delimiter=delimiter, quote_char=quote_char)

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
        url = url_for(PAGE_OTHER_ENTITY, filename=filename)
        return redirect(url)

    if request.method == 'POST':
        return redirect(url_for(PAGE_LOAD_OTHER_ENTITY, node_id=node_id), code=307) # 307 keeps it a POST

    help = get_helps(['data_table_reupload_full']) # FIXME
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
        current_user.set_filename(None)
        flash(f'Closed {current_document}')
    else:
        flash("There was no package open")

    set_current_page('')

    return render_template('index.html')


def select_post(filename=None, form=None, form_dict=None,
                method=None, this_page=None, back_page=None,
                next_page=None, edit_page=None, project_node_id=None, reupload_page=None):
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
                node_id = key
            elif val == BTN_REMOVE:
                new_page = this_page
                node_id = key
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
                node_id = key
                if reupload_page:
                    new_page = reupload_page
                else:
                    node_id = key
                    new_page = PAGE_REUPLOAD
            elif val == BTN_HIDDEN_CHECK:
                new_page = PAGE_CHECK
            elif val == BTN_HIDDEN_SAVE:
                new_page = this_page
            elif val == BTN_HIDDEN_DOWNLOAD:
                new_page = PAGE_DOWNLOAD
            elif val == BTN_HIDDEN_NEW:
                new_page = PAGE_CREATE
            elif val == BTN_HIDDEN_OPEN:
                new_page = PAGE_OPEN
            elif val == BTN_HIDDEN_CLOSE:
                new_page = PAGE_CLOSE
            elif val == UP_ARROW:
                new_page = this_page
                node_id = key
                process_up_button(filename, node_id)
            elif val == DOWN_ARROW:
                new_page = this_page
                node_id = key
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
            elif val == BTN_LOAD_OTHER_ENTITY:
                new_page = PAGE_LOAD_OTHER_ENTITY
                node_id = '1'
            elif val == BTN_REUSE:
                new_page = PAGE_IMPORT_PARTY
                node_id = '1'

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
