#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: metapype_client.py

:Synopsis:

:Author:
    costa

:Created:
    12/18/2018
"""
import daiquiri
import os

from flask import (
    send_file
)

from flask_login import (
    current_user
)

from webapp.config import Config


logger = daiquiri.getLogger('user_data: ' + __name__)
USER_DATA_DIR = 'user-data'


def get_user_org():
    user_org = None
    try:
        username = current_user.get_username()
        organization = current_user.get_organization()
        user_org = f'{username}-{organization}'
    except AttributeError:
        pass
    return user_org
    

def get_user_folder_name():
    user_folder_name = f'{USER_DATA_DIR}/anonymous-user'
    
    user_org = current_user.get_user_org()
    if user_org:
        user_folder_name = f'{USER_DATA_DIR}/{user_org}'

    return user_folder_name


def get_user_uploads_folder_name():
    user_folder_name = get_user_folder_name()
    user_uploads_folder_name = f'{user_folder_name}/uploads'

    return user_uploads_folder_name


def get_user_document_list():
    packageids = []
    user_folder = get_user_folder_name()
    try:
        folder_contents = os.listdir(user_folder)
        onlyfiles = [f for f in folder_contents if os.path.isfile(os.path.join(user_folder, f))]
        if onlyfiles:
            for filename in onlyfiles:
                if filename and filename.endswith('.json'):
                    packageid = os.path.splitext(filename)[0]
                    packageids.append(packageid)
    except:
        pass
    return packageids


def get_user_uploads():
    data_files = []
    user_uploads_folder = get_user_uploads_folder_name()
    try:
        folder_contents = os.listdir(user_uploads_folder)
        onlyfiles = [f for f in folder_contents if os.path.isfile(os.path.join(user_uploads_folder, f))]
        if onlyfiles:
            for filename in onlyfiles:
                data_files.append(filename)
    except:
        pass
        
    return data_files


def initialize_user_data():
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


def delete_eml(packageid:str=''):
    if packageid:
        user_folder = get_user_folder_name()
        json_filename = f'{user_folder}/{packageid}.json'
        xml_filename = f'{user_folder}/{packageid}.xml'
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
            msg = f'Data package not found: {packageid}'
            return msg
    else:
        msg = f'No package ID was specified'
        return msg


def download_eml(packageid:str=''):
    if packageid:
        user_folder = get_user_folder_name()
        filename = f'{packageid}.xml'
        pathname = f'{user_folder}/{filename}'
        if os.path.exists(pathname):
            relative_pathname = '../' + pathname
            mimetype = 'application/xml'
            try: 
                return send_file(relative_pathname, 
                    mimetype=mimetype, 
                    as_attachment=True, 
                    attachment_filename=filename, 
                    add_etags=True, 
                    cache_timeout=None, 
                    conditional=False, 
                    last_modified=None)
            except Exception as e:
                return str(e)
        else:
            msg = f'Data package not found: {packageid}'
            return msg
    else:
        msg = f'No package ID was specified'
        return msg


def set_active_packageid(packageid: str):
    if packageid is not None:
        user_folder = get_user_folder_name()
        active_packageid_file = f'{user_folder}/{Config.ACTIVE_PACKAGE}'
        with open(active_packageid_file, 'w') as f:
            f.write(packageid)
    else:
        remove_active_packageid()


def get_active_packageid() -> str:
    package_id = None
    user_folder = get_user_folder_name()
    active_packageid_file = f'{user_folder}/{Config.ACTIVE_PACKAGE}'
    if os.path.exists(active_packageid_file):
        with open(active_packageid_file, 'r') as f:
            package_id = f.readline().strip()
    return package_id


def remove_active_packageid():
    user_folder = get_user_folder_name()
    active_packageid_file = f'{user_folder}/{Config.ACTIVE_PACKAGE}'
    if os.path.exists(active_packageid_file):
        os.remove(active_packageid_file)

