#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: views.py

:Synopsis:

:Author:
    costa
    servilla

:Created:
    7/23/18
"""
import daiquiri
import html
import os.path
import pickle
from datetime import date


from flask import (
    Blueprint, flash, render_template, redirect, request, url_for, session
)

from flask_login import (
    current_user, login_required
)

import xlrd

from webapp.auth.user_data import (
    delete_eml, download_eml, get_active_packageid, get_user_document_list,
    get_user_uploads_folder_name
)

from webapp.home.forms import ( 
    CreateEMLForm,
    DownloadEMLForm,
    OpenEMLDocumentForm, DeleteEMLForm, SaveAsForm,
    LoadDataForm, LoadMetadataForm, LoadOtherEntityForm
)

from webapp.home.load_data_table import (
    load_data_table, load_other_entity
)

from webapp.home.metapype_client import ( 
    load_eml, save_both_formats, remove_child, create_eml,
    move_up, move_down, UP_ARROW, DOWN_ARROW,
    save_old_to_new, read_xml, new_child_node
)

from webapp.home.evaulate import check_eml

from webapp.buttons import *
from webapp.pages import *

from metapype.eml import names
from metapype.model.node import Node
from werkzeug.utils import secure_filename


logger = daiquiri.getLogger('views: ' + __name__)
home = Blueprint('home', __name__, template_folder='templates')
help_dict = {}
keywords = {}


def non_breaking(_str):
    return _str.replace(' ', html.unescape('&nbsp;'))


@home.before_app_first_request
def load_eval_entries():
    workbook = xlrd.open_workbook('webapp/static/evaluate.xlsx')
    worksheet = workbook.sheet_by_index(0)
    for row in range(1, worksheet.nrows):
        id = worksheet.cell_value(row, 0)
        vals = [worksheet.cell_value(row, i) for i in range(1, worksheet.ncols)]
        session[f'__eval__{id}'] = vals


@home.before_app_request  # FIXME - temporary
@home.before_app_first_request
def init_keywords():
    lter_keywords = pickle.load(open('webapp/static/lter_keywords.pkl', 'rb'))
    keywords['LTER'] = lter_keywords


def get_keywords(which):
    return keywords.get(which, [])


# @home.before_app_request  # FIXME - temporary
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
        title, content = help_dict.get(id)
        helps.append((f'__help__{id}', title, content))
    return helps


@home.route('/')
def index():
    if current_user.is_authenticated:
        current_packageid = get_active_packageid()
        if current_packageid:
            eml_node = load_eml(packageid=current_packageid)
            new_page = PAGE_TITLE if eml_node else PAGE_FILE_ERROR
            return redirect(url_for(new_page, packageid=current_packageid))
    return render_template('index.html')


@home.route('/edit/<page>')
def edit(page:str=None):
    '''
    The edit page allows for direct editing of a top-level element such as
    title, abstract, creators, etc. This function simply redirects to the
    specified page, passing the packageid as the only parameter.
    '''
    if current_user.is_authenticated and page:
        current_packageid = get_active_packageid()
        if current_packageid:
            eml_node = load_eml(packageid=current_packageid)
            new_page = page if eml_node else PAGE_FILE_ERROR
            return redirect(url_for(new_page, packageid=current_packageid))
    return render_template('index.html')


@home.route('/about')
def about():
    return render_template('about.html')


@home.route('/file_error/<packageid>')
def file_error(packageid=None):
    return render_template('file_error.html', packageid=packageid)


@home.route('/delete', methods=['GET', 'POST'])
@login_required
def delete():
    form = DeleteEMLForm()
    choices = []
    packageids = get_user_document_list()
    for packageid in packageids:
        pid_tuple = (packageid, packageid)
        choices.append(pid_tuple)
    form.packageid.choices = choices
    # Process POST
    if form.validate_on_submit():
        packageid = form.packageid.data
        return_value = delete_eml(packageid=packageid)
        if isinstance(return_value, str):
            flash(return_value)
        else:
            flash(f'Deleted {packageid}')
        new_page = PAGE_DELETE   # Return the Response object
        return redirect(url_for(new_page))
    # Process GET
    return render_template('delete_eml.html', title='Delete EML', 
                           form=form)


@home.route('/save', methods=['GET', 'POST'])
@login_required
def save():
    current_packageid = current_user.get_packageid()
    
    if not current_packageid:
        flash('No document currently open')
        return render_template('index.html')

    eml_node = load_eml(packageid=current_packageid)
    if not eml_node:
        flash(f'Unable to open {current_packageid}')
        return render_template('index.html')

    save_both_formats(packageid=current_packageid, eml_node=eml_node)
    flash(f'Saved {current_packageid}')
         
    return redirect(url_for(PAGE_TITLE, packageid=current_packageid))


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
    current_packageid = current_user.get_packageid()

    # Process POST
    if form.validate_on_submit():
        if submit_type == 'Cancel':
            if current_packageid:
                new_packageid = current_packageid  # Revert back to the old packageid
                new_page = PAGE_TITLE
            else:
                return render_template('index.html')
        elif submit_type == 'Save':
            if not current_packageid:
                flash('No document currently open')
                return render_template('index.html')

            eml_node = load_eml(packageid=current_packageid)
            if not eml_node:
                flash(f'Unable to open {current_packageid}')
                return render_template('index.html')

            new_packageid = form.packageid.data
            return_value = save_old_to_new(
                            old_packageid=current_packageid, 
                            new_packageid=new_packageid,
                            eml_node=eml_node)
            if isinstance(return_value, str):
                flash(return_value)
                new_packageid = current_packageid  # Revert back to the old packageid
            else:
                current_user.set_packageid(packageid=new_packageid)
                flash(f'Saved as {new_packageid}')
            new_page = PAGE_TITLE   # Return the Response object
        
        return redirect(url_for(new_page, packageid=new_packageid))

     # Process GET
    if current_packageid:
        form.packageid.data = current_packageid
        return render_template('save_as.html',
                           packageid=current_packageid, 
                           title='Save As', 
                           form=form)
    else:
        flash("No document currently open")
        return render_template('index.html')


@home.route('/download', methods=['GET', 'POST'])
@login_required
def download():
    form = DownloadEMLForm()
    choices = []
    packageids = get_user_document_list()
    for packageid in packageids:
        pid_tuple = (packageid, packageid)
        choices.append(pid_tuple)
    form.packageid.choices = choices
    # Process POST
    if form.validate_on_submit():
        packageid = form.packageid.data
        return_value = download_eml(packageid=packageid)
        if isinstance(return_value, str):
            flash(return_value)
        else:
            return return_value
    # Process GET
    return render_template('download_eml.html', title='Download EML', 
                           form=form)


@home.route('/check_metadata/<packageid>', methods=['GET', 'POST'])
@login_required
def check_metadata(packageid:str):
    current_packageid = get_active_packageid()
    content = check_eml(current_packageid)
    # Process POST
    if request.method == 'POST':
        # return render_template(PAGE_CHECK, packageid=packageid)
        return redirect(url_for(PAGE_CHECK, packageid=current_packageid))

    else:
        return render_template('check_metadata.html', content=content)


@home.route('/download_current', methods=['GET', 'POST'])
@login_required
def download_current():
    current_packageid = get_active_packageid()
    if current_packageid:
        return_value = download_eml(packageid=current_packageid)
        if isinstance(return_value, str):
            flash(return_value)
        else:
            return return_value


def allowed_data_file(filename):
    ALLOWED_EXTENSIONS = set(['csv', 'tsv', 'txt', 'xml'])    
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
    if form.validate_on_submit():
        packageid = form.packageid.data
        user_packageids = get_user_document_list()
        if user_packageids and packageid and packageid in user_packageids:
            flash(f'{packageid} already exists')
            return render_template('create_eml.html', title='Create New EML', 
                            form=form)
        create_eml(packageid=packageid)
        current_user.set_packageid(packageid)
        return redirect(url_for(PAGE_TITLE, packageid=packageid))
    # Process GET
    return render_template('create_eml.html', title='Create New EML', 
                           form=form)


@home.route('/open_eml_document', methods=['GET', 'POST'])
@login_required
def open_eml_document():
    form = OpenEMLDocumentForm()

    choices = []
    user_packageids = get_user_document_list()
    for packageid in user_packageids:
        pid_tuple = (packageid, packageid)
        choices.append(pid_tuple)
    form.packageid.choices = choices

    # Process POST
    if form.validate_on_submit():
        packageid = form.packageid.data
        eml_node = load_eml(packageid)
        if eml_node:
            current_user.set_packageid(packageid)
            create_eml(packageid=packageid)
            new_page = PAGE_TITLE
        else:
            new_page = PAGE_FILE_ERROR
        return redirect(url_for(new_page, packageid=packageid))
    
    # Process GET
    return render_template('open_eml_document.html', title='Open EML Document', 
                           form=form)


@home.route('/load_data', methods=['GET', 'POST'])
@login_required
def load_data():
    form = LoadDataForm()
    packageid = current_user.get_packageid()
    uploads_folder = get_user_uploads_folder_name()

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
                data_file = filename
                data_file_path = f'{uploads_folder}/{data_file}'
                flash(f'Loaded {data_file}')
                eml_node = load_eml(packageid=packageid)
                dataset_node = eml_node.find_child(names.DATASET)
                if not dataset_node:
                    dataset_node = new_child_node(names.DATASET, eml_node)
                dt_node = load_data_table(dataset_node, uploads_folder, data_file)
                save_both_formats(packageid=packageid, eml_node=eml_node)
                return redirect(url_for(PAGE_DATA_TABLE, packageid=packageid, node_id=dt_node.id))
            else:
                flash(f'{filename} is not a supported data file type')
                return redirect(request.url)
    # Process GET
    return render_template('load_data.html', title='Load Data', 
                           form=form)


@home.route('/load_other_entity', methods=['GET', 'POST'])
@login_required
def load_entity():
    form = LoadOtherEntityForm()
    packageid = current_user.get_packageid()
    uploads_folder = get_user_uploads_folder_name()

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
            else:
                file.save(os.path.join(uploads_folder, filename))
                data_file = filename
                data_file_path = f'{uploads_folder}/{data_file}'
                flash(f'Loaded {data_file_path}')
                eml_node = load_eml(packageid=packageid)
                dataset_node = eml_node.find_child(names.DATASET)
                other_entity_node = load_other_entity(dataset_node, uploads_folder, data_file)
                save_both_formats(packageid=packageid, eml_node=eml_node)
                return redirect(url_for(PAGE_OTHER_ENTITY, packageid=packageid, node_id=other_entity_node.id))

    # Process GET
    return render_template('load_other_entity.html', title='Load Other Entity',
                           form=form)


@home.route('/load_metadata', methods=['GET', 'POST'])
@login_required
def load_metadata():
    form = LoadMetadataForm()
    packageid = current_user.get_packageid()
    uploads_folder = get_user_uploads_folder_name()

    # Process POST
    if  request.method == 'POST' and form.validate_on_submit():
        # Check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)

        file = request.files['file']
        if file:
            filename = secure_filename(file.filename)
            
            if filename is None or filename == '':
                flash('No selected file')           
            elif allowed_metadata_file(filename):
                file.save(os.path.join(uploads_folder, filename))
                metadata_file = filename
                metadata_file_path = f'{uploads_folder}/{metadata_file}'
                with open(metadata_file_path, 'r') as file:
                    metadata_str = file.read()
                    try:
                        eml_node = read_xml(metadata_str)
                    except Exception as e:
                        flash(e)
                    if eml_node:
                        packageid = eml_node.attribute_value('packageId')
                        if packageid:
                            current_user.set_packageid(packageid)
                            save_both_formats(packageid=packageid, eml_node=eml_node)
                            return redirect(url_for(PAGE_TITLE, packageid=packageid))
                        else:
                            flash(f'Unable to determine packageid from file {filename}')
                    else:
                        flash(f'Unable to load metadata from file {filename}')
            else:
                flash(f'{filename} is not a supported data file type')
                return redirect(request.url)
    # Process GET
    return render_template('load_metadata.html', title='Load Metadata', 
                           form=form)


@home.route('/close', methods=['GET', 'POST'])
@login_required
def close():
    current_packageid = current_user.get_packageid()
    
    if current_packageid:
        current_user.set_packageid(None)
        flash(f'Closed {current_packageid}')
    else:
        flash("There was no package open")
        
    return render_template('index.html')


def select_post(packageid=None, form=None, form_dict=None,
                method=None, this_page=None, back_page=None, 
                next_page=None, edit_page=None):
    node_id = ''
    new_page = ''
    if form_dict:
        for key in form_dict:
            val = form_dict[key][0]  # value is the first list element
            if val in (BTN_BACK, BTN_DONE):
                new_page = back_page
            elif val[0:4] == BTN_BACK:
                new_page = back_page
            elif val in [BTN_NEXT, BTN_SAVE_AND_CONTINUE]:
                new_page = next_page
            elif val == BTN_EDIT:
                new_page = edit_page
                node_id = key
            elif val == BTN_REMOVE:
                new_page = this_page
                node_id = key
                eml_node = load_eml(packageid=packageid)
                remove_child(node_id=node_id)
                save_both_formats(packageid=packageid, eml_node=eml_node)
            elif val == BTN_HIDDEN_CHECK:
                new_page = PAGE_CHECK
            elif val == BTN_HIDDEN_SAVE:
                new_page = this_page
            elif val == BTN_HIDDEN_DOWNLOAD:
                new_page = PAGE_DOWNLOAD
            elif val == UP_ARROW:
                new_page = this_page
                node_id = key
                process_up_button(packageid, node_id)
            elif val == DOWN_ARROW:
                new_page = this_page
                node_id = key
                process_down_button(packageid, node_id)
            elif val[0:3] == BTN_ADD:
                new_page = edit_page
                node_id = '1'
            elif val == BTN_LOAD_DATA_TABLE:
                new_page = PAGE_LOAD_DATA
                node_id = '1'
            elif val== BTN_LOAD_OTHER_ENTITY:
                new_page = PAGE_LOAD_OTHER_ENTITY
                node_id = '1'

    if form.validate_on_submit():   
       return url_for(new_page, packageid=packageid, node_id=node_id)


def process_up_button(packageid:str=None, node_id:str=None):
    process_updown_button(packageid, node_id, move_up)


def process_down_button(packageid:str=None, node_id:str=None):
    process_updown_button(packageid, node_id, move_down)


def process_updown_button(packageid:str=None, node_id:str=None, move_function=None):
    if packageid and node_id and move_function:
        eml_node = load_eml(packageid=packageid)
        child_node = Node.get_node_instance(node_id)
        if child_node:
            parent_node = child_node.parent
            if parent_node:
                move_function(parent_node, child_node)
                save_both_formats(packageid=packageid, eml_node=eml_node)


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
