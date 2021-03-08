import glob
import os
import shutil
from zipfile import ZipFile

import webapp.auth.user_data as user_data


def upload_ezeml_package(file, package_name=None):
    user_path = user_data.get_user_folder_name() # os.path.join(current_path, USER_DATA_DIR)
    work_path = os.path.join(user_path, 'zip_temp')

    try:
        shutil.rmtree(work_path)
    except FileNotFoundError:
        pass

    try:
        os.mkdir(work_path)
    except FileExistsError:
        pass

    dest = os.path.join(work_path, package_name) + '.ezeml.zip'
    file.save(dest)


def copy_ezeml_package(package_name=None):
    user_path = user_data.get_user_folder_name() # os.path.join(current_path, USER_DATA_DIR)
    work_path = os.path.join(user_path, 'zip_temp')

    # Determine the output package name to use
    # package_name may already be of the form foobar_COPYn
    base_package_name = package_name
    index = package_name.rfind('_COPY')
    if index > -1:
        base_package_name = package_name[:index]
    i = 1
    while True:
        if i == 1:
            output_package_name = base_package_name + '_COPY'
        else:
            output_package_name = base_package_name + '_COPY' + str(i)
        if not os.path.isfile(os.path.join(user_path, output_package_name) + '.json'):
            break
        i += 1

    src_file = os.path.join(work_path, package_name) + '.ezeml.zip'
    dest_file = os.path.join(work_path, output_package_name) + '.ezeml.zip'
    shutil.move(src_file, dest_file)
    return output_package_name


def import_ezeml_package(output_package_name=None):
    user_path = user_data.get_user_folder_name() # os.path.join(current_path, USER_DATA_DIR)
    work_path = os.path.join(user_path, 'zip_temp')
    dest = os.path.join(work_path, output_package_name) + '.ezeml.zip'

    try:
        zip_object = ZipFile(dest, 'r')
    except FileNotFoundError:
        raise FileNotFoundError

    zip_object.extractall(path=work_path)

    # Remove the data package file
    os.remove(dest)

    # Create the uploads folder
    upload_folder = os.path.join(user_path, 'uploads', output_package_name)
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




