import collections
from datetime import datetime
import os
from flask import (
    url_for
)

from webapp.home.metapype_client import load_eml
import webapp.auth.user_data as user_data
from webapp.config import Config
from webapp.pages import *


Data_Package = collections.namedtuple(
    'Data_Package', ["package_name", "package_link", "date_modified", "size", "remove_link"])

Data_Usage = collections.namedtuple(
    'Data_Usage', ["user_name", "date_modified", "size", "uploads_size", "exports_size", "zip_temp_size", "dir_name"])


def get_dir_size(path='.'):
    total = 0
    if os.path.exists(path):
        with os.scandir(path) as it:
            for entry in it:
                if entry.is_file():
                    total += entry.stat().st_size
                elif entry.is_dir():
                    total += get_dir_size(entry.path)
    return total


def get_package_size(package_name):
    """Get the size of a package in bytes. We will only count the size of the XML file and the
    size of the data files. We will not count the size of the JSON files or PKL files since these
    are not seen by users."""

    # See if an XML file exists using the package name
    user_dir = user_data.get_user_folder_name()
    xml_file = os.path.join(user_dir, package_name + '.xml')
    xml_size = 0
    if not os.path.isfile(xml_file):
        # Load the JSON model to find the package ID
        json_file = os.path.join(user_dir, package_name + '.json')
        eml_node = load_eml(package_name, folder_name=user_dir, skip_metadata_check=True)
        package_id = eml_node.attribute_value('packageId')
        if package_id:
            xml_file = os.path.join(user_dir, package_id + '.xml')
            if os.path.isfile(xml_file):
                xml_size = os.path.getsize(xml_file)
    else:
        xml_size = os.path.getsize(xml_file)

    # Get the size of the data files
    uploads_dir = os.path.join(user_dir, 'uploads', package_name)
    if os.path.isdir(uploads_dir):
        data_size = get_dir_size(uploads_dir)
    else:
        data_size = 0

    size = xml_size + data_size
    return size


def get_data_packages(sort_by='date_modified', reverse=True):
    """Get a list of data packages from the user's data directory."""
    user_dir = user_data.get_user_folder_name()
    packages = []
    for filename in os.listdir(user_dir):
        package_name, file_ext = os.path.splitext(filename)
        if file_ext.lower() != '.json' or package_name == '__user_properties__':
            continue
        package_link = f'<a href="{url_for(PAGE_OPEN_PACKAGE, package_name=package_name)}">{package_name}</a>'
        date_modified = datetime.fromtimestamp(os.path.getmtime(os.path.join(user_dir, filename))).strftime('%Y-%m-%d %H:%M:%S')
        size = f"{get_package_size(package_name):,}"
        are_you_sure = "'Are you sure? This action cannot be undone.');"
        endpoint = url_for(PAGE_MANAGE_PACKAGES, to_delete=package_name)
        remove_link = f'<a onclick="return confirm({are_you_sure}" href="{endpoint}">Delete</a>'
        data_package = Data_Package(package_name, package_link, date_modified, size, remove_link)
        packages.append(data_package)
    return sorted(packages, key=lambda x: getattr(x, sort_by), reverse=reverse)


def get_data_usage(sort_by='user_name', reverse=False):
    """Returns a list of data usages by each ezEML user."""
    data_usages = []
    user_dirs = user_data.get_all_user_dirs()
    for dir_name in user_dirs:
        user_name = dir_name.split('-')[0]
        path = os.path.join(Config.USER_DATA_DIR, dir_name)
        date_modified = datetime.fromtimestamp(os.path.getmtime(path)).strftime('%Y-%m-%d %H:%M:%S')
        size = f"{get_dir_size(path):,}"
        uploads_size = f"{get_dir_size(os.path.join(path, 'uploads')):,}"
        exports_size = f"{get_dir_size(os.path.join(path, 'exports')):,}"
        zip_temp_size = f"{get_dir_size(os.path.join(path, 'zip_temp')):,}"
        data_usage = Data_Usage(user_name, date_modified, size, uploads_size, exports_size, zip_temp_size, dir_name)
        data_usages.append(data_usage)
    total_usage = get_dir_size(Config.USER_DATA_DIR)
    return total_usage, sorted(data_usages, key=lambda x: getattr(x, sort_by), reverse=reverse)


if __name__=="__main__":
    # l = get_data_usage()
    # for p in l:
    #     print(p)
    pass