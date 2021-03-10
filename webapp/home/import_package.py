import os
import shutil
from zipfile import ZipFile

import webapp.auth.user_data as user_data

from webapp.home.load_data_table import get_md5_hash

from webapp.home.metapype_client import list_files_in_dir


def check_ezeml_manifest(zipfile_name):
    zip_object = ZipFile(zipfile_name, 'r')

    # Get list of files in the archive
    files = zip_object.namelist()

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
        if checksum != get_md5_hash(f'{user_path}/{filename}'):
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
    work_path = os.path.join(user_path, 'zip_temp')

    try:
        shutil.rmtree(work_path)
    except FileNotFoundError:
        pass

    try:
        os.mkdir(work_path)
    except FileExistsError:
        pass

    dest = os.path.join(work_path, package_name) + '.zip'
    file.save(dest)

    # Get the package name
    try:
        zip_object = ZipFile(dest, 'r')
    except FileNotFoundError:
        raise FileNotFoundError(dest)

    # Get list of files in the archive
    files = zip_object.namelist()

    unversioned_package_name = None
    renamed_zip = None
    for filename in files:
        if filename.lower().endswith('.json'):
            unversioned_package_name = filename.replace('.json', '')
            renamed_zip = os.path.join(work_path, unversioned_package_name) + '.zip'
            shutil.move(dest, renamed_zip)
            break

    if not renamed_zip:
        raise FileNotFoundError
    check_ezeml_manifest(renamed_zip)

    return unversioned_package_name


def copy_ezeml_package(package_name=None):
    user_path = user_data.get_user_folder_name() # os.path.join(current_path, USER_DATA_DIR)
    work_path = os.path.join(user_path, 'zip_temp')

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

    # index = package_name.rfind('_COPY')
    # if index > -1:
    #     base_package_name = package_name[:index]
    # i = 1
    # while True:
    #     if i == 1:
    #         output_package_name = base_package_name + '_COPY'
    #     else:
    #         output_package_name = base_package_name + '_COPY' + str(i)
    #     if not os.path.isfile(os.path.join(user_path, output_package_name) + '.json'):
    #         break
    #     i += 1

    src_file = os.path.join(work_path, package_name) + '.zip'
    dest_file = os.path.join(work_path, output_package_name) + '.zip'
    shutil.move(src_file, dest_file)
    return output_package_name


def import_ezeml_package(output_package_name=None):
    user_path = user_data.get_user_folder_name() # os.path.join(current_path, USER_DATA_DIR)
    work_path = os.path.join(user_path, 'zip_temp')
    dest = os.path.join(work_path, output_package_name) + '.zip'

    try:
        zip_object = ZipFile(dest, 'r')
    except FileNotFoundError:
        raise FileNotFoundError

    zip_object.extractall(path=work_path)

    # Remove the data package zip file
    os.remove(dest)

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
    files = zip_object.namelist()

    # Copy the files to their proper destinations
    for filename in files:
        src_file = os.path.join(work_path, filename)
        if filename.startswith('data/'):
            dest_file = os.path.join(upload_folder, filename[5:])
        else:
            if filename.endswith('.json'):
                # Use the output package name
                dest_file = os.path.join(user_path, output_package_name) + '.json'
            else:
                dest_file = os.path.join(user_path, filename)
        shutil.copyfile(src_file, dest_file)




