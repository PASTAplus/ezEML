#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: metapype_client.py

:Synopsis:

:Author:
    costa
    ide

:Created:
    12/18/2018
"""
import json
import os
import os.path
from json import JSONDecodeError
from pathlib import Path
import pickle
import glob
from shutil import copy

import PIL.Image
import daiquiri
from flask import send_file, Flask, current_app, session
from flask_login import current_user

from webapp.config import Config
from webapp.home.motherpype import get_image_name_node, get_image_full_name_node
import webapp.home.views as views
from metapype.model.node import Node

from PIL import Image

logger = daiquiri.getLogger('user_data: ' + __name__)
USER_DATA_DIR = 'user-data'
USER_PROPERTIES_FILENAME = '__user_properties__.json'


def get_user_folder_name():
    user_folder_name = f'{USER_DATA_DIR}/anonymous-user'
    user_org = False
    if current_user.is_authenticated:
        user_org = current_user.get_user_org()
    if user_org:
        user_folder_name = f'{USER_DATA_DIR}/{user_org}'

    return user_folder_name


def get_user_uploads_folder_name():
    user_folder_name = get_user_folder_name()
    user_uploads_folder_name = f'{user_folder_name}/uploads'

    return user_uploads_folder_name


def get_document_uploads_folder_name(document_name=None):
    if not document_name:
        if get_active_document():
            document_name = get_active_document()
    if document_name:
        document_uploads_folder = os.path.join(get_user_uploads_folder_name(), document_name)
        Path(document_uploads_folder).mkdir(parents=True, exist_ok=True)
        return document_uploads_folder
    else:
        return None


def get_user_document_list():
    packageids = []
    user_folder = get_user_folder_name()
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


def initialize_user_data(cname, uid):
    user_folder_name = get_user_folder_name()
    user_uploads_folder_name = get_user_uploads_folder_name()
    if not os.path.exists(USER_DATA_DIR):
        os.mkdir(USER_DATA_DIR)
    if user_folder_name and not os.path.exists(user_folder_name):
        os.mkdir(user_folder_name)
    if (user_uploads_folder_name and
            os.path.exists(user_folder_name) and not
            os.path.exists(user_uploads_folder_name)
    ):
        os.mkdir(user_uploads_folder_name)
    user_properties = get_user_properties()
    user_properties['cname'] = cname
    user_properties['uid'] = uid
    save_user_properties(user_properties)


def get_user_properties(folder_name=None):
    if not folder_name:
        user_folder_name = get_user_folder_name()
    else:
        user_folder_name = f'{USER_DATA_DIR}/{folder_name}'
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
            views.fixup_upload_management()
    return user_properties


def save_user_properties(user_properties, user_folder_name=None):
    if not user_folder_name:
        user_folder_name = get_user_folder_name()
    else:
        user_folder_name = f'{USER_DATA_DIR}/{user_folder_name}'
    user_properties_filename = os.path.join(user_folder_name, USER_PROPERTIES_FILENAME)
    with open(user_properties_filename, 'w') as user_properties_file:
        json.dump(user_properties, user_properties_file)


def is_first_usage():
    user_properties = get_user_properties()
    is_first_usage = user_properties.get('is_first_usage', True)
    user_properties['is_first_usage'] = False
    save_user_properties(user_properties)
    return is_first_usage


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
    user_folder = get_user_folder_name()
    table_props_filename = '__uploaded_table_properties__.pkl'
    properties_file = f'{user_folder}/{table_props_filename}'
    try:
        with open(properties_file, 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
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


def discard_uploaded_table_properties_for_package(package_name):
    user_properties = get_user_properties()
    uploaded_table_properties = user_properties.get('uploaded_table_properties', {})
    uploaded_table_properties = list(filter(lambda x: x[0] != package_name, uploaded_table_properties))
    user_properties['uploaded_table_properties'] = uploaded_table_properties
    save_user_properties(user_properties)


def get_uploaded_table_column_properties(filename):
    uploaded_table_properties = get_uploaded_table_properties_dict()
    this_upload = (get_active_document(), filename.lower())
    return uploaded_table_properties.get(this_upload, (None, None, None))


def data_table_was_uploaded(filename):
    user_properties = get_user_properties()
    uploaded_files = user_properties.get('data_table_upload_filenames', [])
    return [get_active_document(), filename.lower()] in uploaded_files


def delete_eml(filename: str = ''):
    if filename:
        user_folder = get_user_folder_name()
        json_filename = f'{user_folder}/{filename}.json'
        xml_filename = f'{user_folder}/{filename}.xml'
        if os.path.exists(json_filename):
            try:
                os.remove(json_filename)
                try:
                    os.remove(xml_filename)
                except Exception as e:
                    pass
                return None
            except Exception as e:
                return str(e)
        else:
            msg = f'Data package not found: {filename}'
            return msg
    else:
        msg = f'No package ID was specified'
        return msg


def download_eml(filename: str = ''):
    if filename:
        # change XML file name to that of the image if image present
        image_name = get_image_name_node()

        user_folder = get_user_folder_name()
        filename_xml = f'{filename}.xml'
        pathname = f'{user_folder}/{filename_xml}'
        if os.path.exists(pathname):
            package_id = get_active_packageid()
            if image_name:
                filename_xml = f'{image_name}.xml'
            elif package_id:
                filename_xml = f'{package_id}.xml'
            relative_pathname = '../' + pathname
            mimetype = 'application/xml'
            try:
                return send_file(relative_pathname,
                                 mimetype=mimetype,
                                 as_attachment=True,
                                 attachment_filename=filename_xml,
                                 add_etags=True,
                                 cache_timeout=None,
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


def download_zip(filename: str = ''):
    if filename:
        user_folder = get_user_folder_name()
        filename_zip = f'{filename}.zip'
        pathname = f'{user_folder}/{filename_zip}'
        if os.path.exists(pathname):
            relative_pathname = '../' + pathname
            mimetype = 'application/zip'
            try:
                return send_file(relative_pathname,
                                 mimetype=mimetype,
                                 as_attachment=True,
                                 attachment_filename=filename_zip,
                                 add_etags=True,
                                 cache_timeout=None,
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


def read_active_dict():
    user_folder = get_user_folder_name()
    active_file = f'{user_folder}/{Config.ACTIVE_PACKAGE}'
    try:
        with open(active_file, 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
        return dict()


def write_active_dict(active_dict):
    user_folder = get_user_folder_name()
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
    set_thumb()


def get_active_document() -> str:
    active_dict = read_active_dict()
    return active_dict.get('filename', None)


def remove_active_file():
    user_folder = get_user_folder_name()
    active_file = f'{user_folder}/{Config.ACTIVE_PACKAGE}'
    if os.path.exists(active_file):
        os.remove(active_file)


def get_temp_folder() -> str:
    # make sure that temp folder exists then return its address
    temp_folder = f'{get_user_folder_name()}/temp/{current_user.get_filename()}'
    if not os.path.isdir(temp_folder):
        os.makedirs(temp_folder)
    return temp_folder


def get_temp_file_name(filename: str = None, eml_node: Node = None) -> str:
    # obtains name of image file if it matches xml
    image_name = get_image_full_name_node(filename, eml_node)
    temp_folder = get_temp_folder()
    images = glob.glob(os.path.join(temp_folder, '*'))
    for file in images:
        file_name = os.path.basename(file)
        if file_name == image_name:
            return file_name
    return None


def get_temp_file_path(filename: str = None, eml_node: Node = None) -> str:
    # return image path if image indicated in nodes is uploaded
    image_name = get_image_full_name_node(filename, eml_node)
    temp_folder = get_temp_folder()
    images = glob.glob(os.path.join(temp_folder, '*'))
    for file in images:
        file_name = os.path.basename(file)
        if file_name == image_name:
            return file
    return None


def clear_folder(folder: str):
    files = glob.glob(os.path.join(folder, '*'))

    for f in files:
        os.remove(f)


def clear_temp_folder():
    clear_folder(get_temp_folder())


def get_zip_file_path() -> str:
    return os.path.join(get_user_folder_name(), Config.ACTIVE_PACKAGE, '.zip')


def get_eval_file_name():
    user_folder_name = get_user_folder_name()
    eval_file_name = f'{user_folder_name}/eval.csv'

    return eval_file_name

thumb_size = (128,128)
thumb_format = 'png'
thumb_suffix = "_thumb." + thumb_format
PIL.Image.MAX_IMAGE_PIXELS = None
thumb_max_input = 8000000   # maximum filesize that the thumb method will accept in bytes


def create_thumb(path: str):
    # create thumbnail of image in same folder
    if path:
        im_size = os.path.getsize(path)
        im = Image.open(path)
        if im_size <= thumb_max_input:
            path_split = path.rsplit(".", 1)
            thumb_path = path_split[0] + thumb_suffix
            im.thumbnail(thumb_size)
            im.save(thumb_path, thumb_format)


def get_thumb_serve_path(filename: str = None, eml_node: Node = None) -> str:
    path = get_temp_file_path()
    if path:
        # attach thumb suffix to regular file name
        path_split = path.rsplit(".", 1)
        thumb_path = path_split[0] + thumb_suffix
        # remove "user_path" folder which is redundant because it is ent_bp's set static folder
        path_split = thumb_path.split("/", 1)
        thumb_path = path_split[1]
        return thumb_path
    return str()

def get_thumb_name() -> str:
    temp_name = get_temp_file_name()
    if temp_name:
        name_split = temp_name.rsplit(".", 1)
        thumb_name = name_split[0] + thumb_suffix
        return thumb_name
    return None


# sets image thumbnail path for session
def set_thumb(filename: str = None, eml_node: Node = None):
    session["image_name"] = get_temp_file_name(filename, eml_node)
    session["thumb_path"] = get_thumb_serve_path(filename, eml_node)
