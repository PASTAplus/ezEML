#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Helper functions for accessing data regarding the current user.
"""

from datetime import datetime
import json
import os
import os.path
from json import JSONDecodeError
from pathlib import Path
import pickle
import shutil
import urllib.parse

import daiquiri
from flask import send_file, Flask, current_app
from flask_login import current_user

from webapp.config import Config
import webapp.home.views as views
import webapp.views.collaborations.collaborations as collaborations
import webapp.home.exceptions as exceptions
from webapp.home.home_utils import log_error, log_info
from webapp.home.utils.security import validate_user_data_path

USER_PROPERTIES_FILENAME = '__user_properties__.json'


def get_all_user_dirs():
    """
    Returns a list of all user directories in the user data directory. Used by Manage Data Usage page.
    """
    user_dirs = []
    if os.path.exists(Config.USER_DATA_DIR):
        for f in os.listdir(Config.USER_DATA_DIR):
            path = os.path.join(Config.USER_DATA_DIR, f)
            if os.path.isdir(path) and not f.startswith('.'):
                user_dirs.append(f)
    return sorted(user_dirs)


def get_template_folder_name():
    return Config.TEMPLATE_DIR


def get_user_folder_name(current_user_directory_only=False,
                         prefix=Config.USER_DATA_DIR,
                         owner_login=None,
                         log_the_details=False):

    user_folder_name = f'{Config.USER_DATA_DIR}/anonymous-user'
    user_login = current_user.get_user_org()

    if not current_user_directory_only and not owner_login:
        owner_login = collaborations.get_active_package_owner_login(user_login)
    elif current_user_directory_only:
        owner_login = None

    if owner_login:
        user_folder_name = f'{prefix}/{owner_login}'
    elif user_login:
        user_folder_name = f'{prefix}/{user_login}'

    if log_the_details:
        log_info(f'current_user_directory_only: {current_user_directory_only}')
        log_info(f'user_login: {user_login}')
        log_info(f'owner_login: {owner_login}')
        log_info(f'user_folder_name: {user_folder_name}')
    return user_folder_name


def get_user_download_folder_name():
    return get_user_folder_name(prefix='user-data')


def get_user_uploads_folder_name():
    user_folder_name = validate_user_data_path(get_user_folder_name(current_user_directory_only=False))
    user_uploads_folder_name = f'{user_folder_name}/uploads'

    return user_uploads_folder_name


def get_document_uploads_folder_name(document_name=None, encoded_for_url=False):
    if not document_name:
        if get_active_document():
            document_name  = get_active_document()
            if encoded_for_url:
                document_name = urllib.parse.quote(document_name)
    if document_name:
        document_uploads_folder = os.path.join(get_user_uploads_folder_name(), document_name)
        Path(document_uploads_folder).mkdir(parents=True, exist_ok=True)
        return document_uploads_folder
    else:
        return None


def get_user_document_list(current_user_directory_only=True):
    packageids = []
    user_folder = get_user_folder_name(current_user_directory_only=current_user_directory_only)
    try:
        folder_contents = os.listdir(user_folder)
        onlyfiles = [f for f in folder_contents if os.path.isfile(os.path.join(user_folder, f))]
        if onlyfiles:
            for filename in onlyfiles:
                if filename and filename.endswith('.json') and filename != USER_PROPERTIES_FILENAME:
                    packageid = os.path.splitext(filename)[0]
                    packageids.append(packageid)
    except:
        pass
    return packageids


def initialize_user_data(cname, idp, uid, auth_token, sub=None):
    user_folder_name = get_user_folder_name(current_user_directory_only=True)
    user_uploads_folder_name = get_user_uploads_folder_name()
    if not os.path.exists(Config.USER_DATA_DIR):
        os.mkdir(Config.USER_DATA_DIR)
    if user_folder_name and not os.path.exists(user_folder_name):
        os.mkdir(user_folder_name)
    if (user_uploads_folder_name and 
        os.path.exists(user_folder_name) and not 
        os.path.exists(user_uploads_folder_name)
       ):
        os.mkdir(user_uploads_folder_name)
    user_properties = get_user_properties()
    user_properties['cname'] = cname
    user_properties['idp'] = idp
    user_properties['uid'] = uid
    user_properties['datetime'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    user_properties['auth_token'] = auth_token
    user_properties['sub'] = sub
    save_user_properties(user_properties)


def get_user_properties(folder_name=None):
    if not folder_name:
        user_folder_name = get_user_folder_name()
    else:
        user_folder_name = f'{Config.USER_DATA_DIR}/{folder_name}'
    user_properties_filename = os.path.join(user_folder_name, USER_PROPERTIES_FILENAME)
    user_properties = {}
    # if properties file doesn't exist, create one with an empty dict
    if not os.path.isfile(user_properties_filename):
        save_user_properties(user_properties, folder_name)
    with open(user_properties_filename, 'r') as user_properties_file:
        try:
            user_properties = json.load(user_properties_file)
        except JSONDecodeError:
            # something's wrong with the user properties file. make a new one and initialize it.
            save_user_properties(user_properties, folder_name)
            # views.fixup_upload_management()
    return user_properties


def save_user_properties(user_properties, user_folder_name=None):
    if not user_folder_name:
        user_folder_name = get_user_folder_name()
    else:
        user_folder_name = f'{Config.USER_DATA_DIR}/{user_folder_name}'
    user_properties_filename = os.path.join(user_folder_name, USER_PROPERTIES_FILENAME)
    with open(user_properties_filename, 'w') as user_properties_file:
        json.dump(user_properties, user_properties_file)


def is_first_usage():
    user_properties = get_user_properties()
    first_usage = user_properties.get('is_first_usage', True)
    user_properties['is_first_usage'] = False
    save_user_properties(user_properties)
    return first_usage


def is_document_locked(filename, owner_login=None):
    """
    This function checks if the document is locked by the current user. Otherwise, it takes the lock and returns False.
    This function is to be called when doing the Open command, i.e., when the user is known to be the owner of the
    document, not a collaborator.
    Note that this function has the side effect of updating the lock timestamp so that the lock doesn't expire.
    If the lock is owned by another user, an exception is raised. We use an exception instead of returning True so
    we can return additional information about the lock owner.
    owner_login, if passed, is used to help identify the package.
    """
    if not owner_login:
        owner_login = current_user.get_user_org()
    user_login = current_user.get_user_org()
    return collaborations.update_lock(user_login, filename, owner_login=owner_login)


def release_document_lock(filename):
    user_login = current_user.get_user_org()
    user_id = collaborations.get_user_id(user_login)
    # The user may be an owner or a collaborator, so we need to handle both.
    active_package = collaborations.get_active_package(user_id)
    collaborations.release_lock(user_login, active_package.package_name)


def clear_data_table_upload_filenames(user_folder_name=None):
    user_properties = get_user_properties(user_folder_name)
    user_properties['data_table_upload_filenames'] = []
    save_user_properties(user_properties, user_folder_name)


def add_data_table_upload_filename(filename, user_folder_name=None, document_name=None):
    user_properties = get_user_properties(user_folder_name)
    uploaded_files = user_properties.get('data_table_upload_filenames', [])
    if not document_name:
        document_name = get_active_document()
    this_upload = [document_name, filename.lower()]  # list rather than tuple because JSON
    if this_upload not in uploaded_files:
        uploaded_files.append(this_upload)
    user_properties['data_table_upload_filenames'] = uploaded_files
    save_user_properties(user_properties, user_folder_name)


def discard_data_table_upload_filename(filename):
    user_properties = get_user_properties()
    uploaded_files = user_properties.get('data_table_upload_filenames', [])
    this_upload = [get_active_document(), filename.lower()]  # list rather than tuple because JSON
    if this_upload in uploaded_files:
        uploaded_files.remove(this_upload)
    user_properties['data_table_upload_filenames'] = uploaded_files
    save_user_properties(user_properties)


def discard_data_table_upload_filenames_for_package(package_filename):
    user_properties = get_user_properties()
    uploaded_files = user_properties.get('data_table_upload_filenames', [])
    uploaded_files = list(filter(lambda x: x[0] != package_filename, uploaded_files))
    user_properties['data_table_upload_filenames'] = uploaded_files
    save_user_properties(user_properties)


def get_uploaded_table_properties_dict():
    user_folder = get_user_folder_name(current_user_directory_only=False)
    table_props_filename = '__uploaded_table_properties__.pkl'
    properties_file = f'{user_folder}/{table_props_filename}'
    try:
        with open(properties_file, 'rb') as f:
            properties = pickle.load(f)
            # print(properties)
            return properties
    except FileNotFoundError:
        return dict()
    except Exception as e:
        return dict()


def save_uploaded_table_properties_dict(properties):
    user_folder = get_user_folder_name()
    table_props_filename = '__uploaded_table_properties__.pkl'
    properties_file = f'{user_folder}/{table_props_filename}'
    with open(properties_file, 'wb') as f:
        pickle.dump(properties, f)


def add_uploaded_table_properties(filename, vartypes, colnames, categorical_codes):
    uploaded_table_properties = get_uploaded_table_properties_dict()
    this_upload = (get_active_document(), filename.lower())
    properties = (vartypes, colnames, categorical_codes)
    uploaded_table_properties[this_upload] = properties
    save_uploaded_table_properties_dict(uploaded_table_properties)


def discard_uploaded_table_properties(package_name, filename):
    uploaded_table_properties = get_uploaded_table_properties_dict()
    to_discard = (package_name, filename.lower())
    if to_discard in uploaded_table_properties:
        del uploaded_table_properties[to_discard]
        save_uploaded_table_properties_dict(uploaded_table_properties)


def discard_uploaded_table_properties_for_package(package_name):
    uploaded_table_properties = get_uploaded_table_properties_dict()
    tables_to_discard = list(filter(lambda x: x[0] == package_name, uploaded_table_properties.keys()))
    for table in tables_to_discard:
        del uploaded_table_properties[table]
    save_uploaded_table_properties_dict(uploaded_table_properties)


# def discard_uploaded_table_properties_for_package(package_name):
#     user_properties = get_user_properties()
#     uploaded_table_properties = user_properties.get('uploaded_table_properties', [])
#     uploaded_table_properties = list(filter(lambda x: x[0] != package_name, uploaded_table_properties))
#     user_properties['uploaded_table_properties'] = uploaded_table_properties
#     save_user_properties(user_properties)


def get_uploaded_table_column_properties(filename):
    uploaded_table_properties = get_uploaded_table_properties_dict()
    this_upload = (get_active_document(), filename.lower())
    return uploaded_table_properties.get(this_upload, (None, None, None))


def data_table_was_uploaded(filename):
    user_properties = get_user_properties()
    uploaded_files = user_properties.get('data_table_upload_filenames', [])
    return [get_active_document(), filename.lower()] in uploaded_files


def remove_file_from_collaborations(filename):
    user_login = current_user.get_user_org()
    collaborations.remove_package(user_login, filename)


def delete_package(filename:str=''):
    if filename:
        user_folder = get_user_folder_name(current_user_directory_only=True)
        discard_data_table_upload_filenames_for_package(filename)
        json_filename = f'{user_folder}/{filename}.json'
        xml_filename = f'{user_folder}/{filename}.xml'
        eval_filename = f'{user_folder}/{filename}_eval.pkl'

        # if we're deleting the current document, clear the active file
        if filename == get_active_document():
            # Careful! Make sure we're not being fooled by a collaborator's file with same filename
            active_document_owner_login = get_active_document_owner_login()
            user_login = current_user.get_user_org()
            if active_document_owner_login == user_login:
                remove_active_file()
        remove_file_from_collaborations(filename)

        try:
            os.remove(json_filename)
        except FileNotFoundError as e:
            pass

        try:
            os.remove(xml_filename)
        except FileNotFoundError as e:
            pass

        try:
            os.remove(eval_filename)
        except FileNotFoundError as e:
            pass

        try:
            uploads_path = os.path.join(user_folder, "uploads")
            if os.path.isdir(os.path.join(uploads_path, filename)):
                shutil.rmtree(os.path.join(uploads_path, filename))
        except FileNotFoundError as e:
            pass

        discard_uploaded_table_properties_for_package(filename)
        discard_data_table_upload_filenames_for_package(filename)

    else:
        msg = f'No package ID was specified'
        return msg


def download_eml(filename:str='', package_id:str=''):
    if filename:
        user_folder = get_user_folder_name(current_user_directory_only=False)
        filename_xml = f'{filename}.xml'
        pathname = f'{user_folder}/{filename_xml}'
        if os.path.exists(pathname):
            # If we have a PID, we use that for the EML filename. The idea is that an ezEML EML document can be
            #   created under a filename that differs from the data package id, but then when a data package id is
            #   set later on, if the user downloads the EML file they'll want it named using the PID, like it would
            #   be in the data repository.
            if package_id:
                filename_xml = f'{package_id}.xml'
            mimetype = 'application/xml'
            try: 
                return send_file(pathname,
                    mimetype=mimetype, 
                    as_attachment=True, 
                    download_name=filename_xml,
                    etag=True,
                    conditional=False,
                    last_modified=None)
            except Exception as e:
                return str(e)
        else:
            msg = f'Data package not found: {filename}'
            return msg
    else:
        msg = f'No package ID was specified'
        return msg


def read_active_dict(log_the_details=False):
    user_folder = get_user_folder_name(current_user_directory_only=True, log_the_details=log_the_details)
    active_file = f'{user_folder}/{Config.ACTIVE_PACKAGE}'
    if log_the_details:
        print(f'active_file: {active_file}')
    try:
        with open(active_file, 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
        return dict()


def write_active_dict(active_dict):
    user_folder = get_user_folder_name(current_user_directory_only=True)
    active_file = f'{user_folder}/{Config.ACTIVE_PACKAGE}'
    with open(active_file, 'wb') as f:
        pickle.dump(active_dict, f)


def set_active_packageid(packageid: str):
    active_dict = read_active_dict()
    if not active_dict:
        active_dict = dict()
    if packageid is not None:
        active_dict['packageid'] = packageid
    else:
        active_dict.pop('packageid', None)
    write_active_dict(active_dict)


def get_active_packageid() -> str:
    active_dict = read_active_dict()
    return active_dict.get('packageid', None)


def set_active_document(filename: str):
    if filename is not None:
        active_dict = read_active_dict()
        if not active_dict:
            active_dict = dict()
        active_dict['filename'] = filename
        write_active_dict(active_dict)
    else:
        remove_active_file()
    # It is almost always the case that the owner of the active document is the current user, so we default to
    #  case. When a package is opened by a collaborator, the owner is set to the user who created the package.
    set_active_document_owner(None)


def get_active_document(log_the_details=False) -> str:
    active_dict = read_active_dict(log_the_details=log_the_details)
    return active_dict.get('filename', None)


def set_active_document_owner(owner: str, owner_login: str = None):
    """
    Set the owner of the active document, which is the user who created the document.
    If owner is None, the owner is assumed to be the current user.
    """
    active_dict = read_active_dict()
    active_dict['owner'] = owner
    active_dict['owner_login'] = owner_login
    write_active_dict(active_dict)


def get_active_document_owner() -> str:
    active_dict = read_active_dict()
    return active_dict.get('owner', None)


def get_active_document_owner_login() -> str:
    active_dict = read_active_dict()
    owner_login = active_dict.get('owner_login', None)
    if not owner_login:
        filename = active_dict.get('filename', None)
        if filename:
            # If the owner_login is not set, we assume the owner is the current user.
            owner_login = current_user.get_user_org()
    return owner_login


def user_is_owner_of_active_document() -> bool:
    return current_user.get_user_org() == get_active_document_owner_login()


def remove_active_file():
    user_folder = get_user_folder_name(current_user_directory_only=True)
    active_file = f'{user_folder}/{Config.ACTIVE_PACKAGE}'
    if os.path.exists(active_file):
        os.remove(active_file)


def get_auth_token():
    user_properties = get_user_properties()
    return user_properties.get('auth_token', '')


##############################################
# Handle complex text element editing settings
##############################################

def set_model_has_complex_texttypes(model_has_complex_texttypes=False):
    user_properties = get_user_properties()
    user_properties['model_has_complex_texttypes'] = model_has_complex_texttypes or \
        get_enable_complex_text_element_editing_global() or \
        get_enable_complex_text_element_editing_document()
    save_user_properties(user_properties)


def get_model_has_complex_texttypes():
    user_properties = get_user_properties()
    return user_properties.get('model_has_complex_texttypes', False)


def set_enable_complex_text_element_editing_global(enable_complex_text_element_editing_global=False):
    user_properties = get_user_properties()
    user_properties['enable_complex_text_element_editing_global'] = enable_complex_text_element_editing_global
    # If the global setting is changed, we need to update the model_has_complex_texttypes setting.
    set_model_has_complex_texttypes()
    save_user_properties(user_properties)


def get_enable_complex_text_element_editing_global():
    user_properties = get_user_properties()
    return user_properties.get('enable_complex_text_element_editing_global', False)


def set_enable_complex_text_element_editing_document(filename=None, enable_complex_text_element_editing_document=False):
    user_properties = get_user_properties()
    enabled_files = user_properties.get('enable_complex_text_element_editing_documents', [])
    if filename is None:
        filename = get_active_document()
    if enable_complex_text_element_editing_document:
        if filename not in enabled_files:
            enabled_files.append(filename)
    else:
        if filename in enabled_files:
            enabled_files.remove(filename)
    user_properties['enable_complex_text_element_editing_documents'] = enabled_files
    save_user_properties(user_properties)


def get_enable_complex_text_element_editing_document(filename=None):
    user_properties = get_user_properties()
    enabled_files = user_properties.get('enable_complex_text_element_editing_documents', [])
    if filename is None:
        filename = get_active_document()
    return filename in enabled_files
