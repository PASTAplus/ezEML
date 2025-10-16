"""
Certain users are authorized to manage templates for certain sites.

The configuration is a dictionary with site names as keys and lists of tuples as values. Each tuple contains a user ID and an email address.
The user ID is the user's login name followed by a hyphen and a unique identifier. The email address is the user's email address.

This module contains functions related to template management.
"""
import os
from flask import (
    session
)
from flask_login import (
    current_user, login_required
)
from shutil import copyfile
from webapp.config import Config
import webapp.auth.user_data as user_data

user_lookup = {}


def init_template_management():
    authorized_sites = []
    try:
        user_login = current_user.get_user_login()
        if user_login:
            if current_user.is_edi_curator():
                authorized_sites.append("__ALL__")
            template_managers = Config.TEMPLATE_MANAGERS
            for key, val in template_managers.items():
                for user in val:
                    if user[0] == user_login:
                        authorized_sites.append(key)
    except AttributeError as ex:
        pass
    session["authorized_to_manage_templates"] = authorized_sites


def init_user_lookup():
    global user_lookup
    if user_lookup:
        return
    template_managers = Config.TEMPLATE_MANAGERS
    for key, val in template_managers.items():
        for user in val:
            sites = user_lookup.get(user[0], [])
            sites.append(key)
            user_lookup[user[0]] = sites


def check_overwrite_user_data(template_pathname):
    # Check if a file with the given name already exists in the user's data directory and is different from the template
    user_base = user_data.get_user_folder_name(current_user_directory_only=True)
    filename = os.path.basename(template_pathname)
    user_path = os.path.join(user_base, filename)

    if os.path.exists(user_path):
        with open(template_pathname, 'r') as f:
            template_content = f.read()
        with open(user_path, 'r') as f:
            user_content = f.read()
        if template_content == user_content:
            return False
        return True

    return False


def copy_template_to_user_data(template_pathname):
    # Copy the template to the user's data directory
    user_base = user_data.get_user_folder_name(current_user_directory_only=True)
    filename = os.path.basename(template_pathname)
    to_path = os.path.join(user_base, filename)
    copyfile(template_pathname, to_path)
    return os.path.splitext(filename)[0]


def copy_document_to_template_folder(filename, template_folder, save_to_name):
    user_base = user_data.get_user_folder_name(current_user_directory_only=True)
    from_path = os.path.join(user_base, filename + '.json')

    template_base = Config.TEMPLATE_DIR
    if template_base[-1] != '/':
        template_base += '/'
    to_path = os.path.join(template_base, template_folder, save_to_name + '.json')

    copyfile(from_path, to_path)
    # We remove the version in the user's data directory to avoid confusion between the versions
    os.remove(from_path)


def is_authorized_to_manage_templates(site):
    init_user_lookup()
    try:
        user_login = current_user.get_user_login()
        if user_login:
            sites = user_lookup.get(user_login, [])
            return site in sites or '__ALL__' in sites
    except AttributeError as ex:
        pass
    return False


def template_folders_for_user(user_login=None):
    def get_template_folders():
        template_base = Config.TEMPLATE_DIR
        if template_base[-1] != '/':
            template_base += '/'
        template_folders = []
        for root, dirs, files in os.walk(template_base):
            if not dirs: # Only include leaf directories
                template_folders.append(root.removeprefix(template_base))
        return sorted(template_folders)

    init_user_lookup()
    try:
        if not user_login:
            user_login = current_user.get_user_login()
        if user_login:
            templates = user_lookup.get(user_login, [])
            if '__ALL__' in templates:
                return get_template_folders()
            else:
                return templates
    except AttributeError as ex:
        pass
    return []


def templates_for_user(user_login=None):
    def get_template_folders():
        template_base = Config.TEMPLATE_DIR
        if template_base[-1] != '/':
            template_base += '/'
        template_folders = []
        for root, dirs, files in os.walk(template_base):
            if not dirs: # Only include leaf directories
                template_folders.append(root.removeprefix(template_base))
        return sorted(template_folders)

    init_user_lookup()
    try:
        if not user_login:
            user_login = current_user.get_user_login()
        if user_login:
            template_folders = user_lookup.get(user_login, [])
            if '__ALL__' in template_folders:
                template_folders = get_template_folders()
            template_files = []
            for template_folder in template_folders:
                for root, dirs, files in os.walk(os.path.join(Config.TEMPLATE_DIR, template_folder)):
                    for file in files:
                        if file.endswith('.json'):
                            template_files.append(os.path.join(template_folder, file.removesuffix('.json')))
            return sorted(template_files)
    except AttributeError as ex:
        pass
    return []


def delete_template_file(filename):
    pathname = os.path.join(Config.TEMPLATE_DIR, filename + '.json')
    if os.path.exists(pathname):
        os.remove(pathname)
        return True
    return False