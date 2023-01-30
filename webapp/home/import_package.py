import os
import shutil
from zipfile import ZipFile


from flask import flash

import webapp.auth.user_data as user_data

from webapp.home.load_data_table import get_md5_hash

from webapp.home.metapype_client import list_files_in_dir


def check_ezeml_manifest(zipfile_name):
    zip_object = ZipFile(zipfile_name, 'r')

    # Get list of files in the archive
    files = zip_object.namelist()

    # Unzip into the work path
    user_path = user_data.get_user_folder_name() # os.path.join(current_path, USER_DATA_DIR)
    work_path = os.path.join(user_path, 'zip_temp')
    zip_object.extractall(path=work_path)

    MANIFEST = 'ezEML_manifest.txt'
    if MANIFEST not in files:
        raise FileNotFoundError(MANIFEST)

    manifest_data = zip_object.read(MANIFEST)
    manifest = manifest_data.decode('utf-8').split('\n')
    user_path = user_data.get_user_folder_name()
    i = 3
    while True:
        # Each group of three lines will have the form:
        # file type (e.g., JSON)
        # filename
        # checksum
        filename = manifest[i+1]
        checksum = manifest[i+2]
        found = get_md5_hash(f'{work_path}/{filename}')
        if checksum != found:
            raise ValueError(filename)
        i += 3
        if i + 2 >= len(manifest):
            break


def upload_ezeml_package(file, package_name=None):
    # Determines the name of the data package by looking at the JSON file in the zip archive.
    # The filename for the archive may have had a version number appended by the file system,
    # and we need to know what the actual package name is, so the caller can determine if
    # the package already exists in the user's account. Besides returning that unversioned
    # package name, this function renames the zip file to the unversioned name.
    # Also checks the ezEML manifest. If the manifest is missing or indicates that files have
    # been changed outside of ezEML, this function raises ValueError.
    user_path = user_data.get_user_folder_name()
    work_path = os.path.join(user_path, 'xml_temp')

    try:
        shutil.rmtree(work_path)
    except FileNotFoundError:
        pass

    try:
        os.mkdir(work_path)
    except FileExistsError:
        pass

    #Changed dest to just work_path -NM 3/1/2022
    dest = os.path.join(work_path, package_name)

    file.save(dest)

    unversioned_package_name = os.path.basename(dest)


    return unversioned_package_name


def copy_ezeml_package(package_name=None):
    user_path = user_data.get_user_folder_name() # os.path.join(current_path, USER_DATA_DIR)
    #Changed zip_temp to xml_temp -NM 3/1/2022
    work_path = os.path.join(user_path, 'xml_temp')

    # Determine the output package name to use
    # package_name may already be of the form foobar_COPYn
    files = list_files_in_dir(user_path)
    base_package_name = package_name
    name_with_copy = base_package_name + '_COPY'
    name_with_copy_len = len(name_with_copy)
    max_copy = 0
    for file in files:
        if file.startswith(name_with_copy) and file.lower().endswith('.json'):
            i = file[name_with_copy_len:-5]  # 5 is len('.json')
            try:
                i = int(i)
                if i > max_copy:
                    max_copy = i
            except:
                pass
    suffix = ''
    if max_copy > 1:
        suffix = str(max_copy + 1)
    output_package_name = name_with_copy + suffix


    src_file = os.path.join(work_path, package_name)
    dest_file = os.path.join(work_path, output_package_name)
    shutil.move(src_file, dest_file)
    return output_package_name


def import_ezeml_package(output_package_name=None):
    user_path = user_data.get_user_folder_name()
    work_path = os.path.join(user_path, 'xml_temp')

    # Create the uploads folder
    # If it already exists, remove it first so we get a clean folder
    upload_folder = os.path.join(user_path, 'uploads', output_package_name)
    try:
        shutil.rmtree(upload_folder)
    except FileNotFoundError:
        pass
    try:
        os.mkdir(upload_folder)
    except FileExistsError:
        pass

    # Get list of files
    files = os.listdir(work_path)

    # Copy the files to their proper destinations
    for filename in files:
        src_file = os.path.join(work_path, filename)
        dest_file = os.path.join(user_path, user_data.get_active_document() + ".xml")

    shutil.copyfile(src_file, dest_file)




