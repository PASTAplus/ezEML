import os
import shutil
import uuid

import daiquiri
from flask import flash
from flask_login import current_user
import requests

from metapype.eml import names

import webapp.auth.user_data as user_data
from webapp.config import Config
import webapp.exceptions as exceptions

from webapp.home.load_data_table import load_data_table, load_other_entity
from webapp.home.metapype_client import save_both_formats
import webapp.home.views as views

logger = daiquiri.getLogger('import_data: ' + __name__)


def log_error(msg):
    if current_user and hasattr(current_user, 'get_username'):
        logger.error(msg, USER=current_user.get_username())
    else:
        logger.error(msg)


def log_info(msg):
    if current_user and hasattr(current_user, 'get_username'):
        logger.info(msg, USER=current_user.get_username())
    else:
        logger.info(msg)


# def get_metadata_from_pasta(scope, identifier, revision, dest_directory, file_name):
#     auth_token = user_data.get_auth_token()
#     read_metadata_url = f"{Config.PASTA_URL}/metadata/eml/{scope}/{identifier}/{revision}"
#     response = requests.get(read_metadata_url, cookies={'auth-token': auth_token})
#     response.raise_for_status()
#
#     file_path = os.path.join(dest_directory, file_name)
#     with open(file_path, "wb") as file:
#         file.write(response.content)


def extract_data_entities_from_eml(eml_node, entity_name):
    data_entities = []
    data_entity_nodes = []
    eml_node.find_all_descendants(entity_name, data_entity_nodes)
    for data_entity_node in data_entity_nodes:
        object_name_node = data_entity_node.find_descendant(names.OBJECTNAME)
        if object_name_node:
            object_name = object_name_node.content
        url_node = data_entity_node.find_descendant(names.URL)
        if url_node:
            url = url_node.content
        if object_name and url_node and url:
            data_entities.append((data_entity_node, entity_name, object_name, url))
        # else:
        #     raise ValueError # TODO - use a custom exception
    return data_entities


# def extract_entity_id(url):
#     # Assumes url points to a PASTA data entity
#     return url.split('/')[-1]


def get_data_entity_size(url):
    if Config.PASTA_URL in url:
        auth_token = user_data.get_auth_token()
        get_data_entity_size_url = url.replace('data/eml', 'data/size/eml')
        response = requests.get(get_data_entity_size_url, cookies={'auth-token': auth_token})
        response.raise_for_status()
        return response.text
    else:
        # raise exceptions.ezEMLAttemptToAccessNonPASTAData
        return '0'


def get_data_entity(upload_dir, object_name, url):
    if Config.PASTA_URL in url:
        auth_token = user_data.get_auth_token()
        response = requests.get(url, cookies={'auth-token': auth_token})
        response.raise_for_status()

        file_path = os.path.join(upload_dir, object_name)
        with open(file_path, "wb") as file:
            file.write(response.content)
    else:
        pass


def convert_file_size(size):
    # number of bytes in a kilobyte
    KBFACTOR = float(1 << 10)
    # number of bytes in a megabyte
    MBFACTOR = float(1 << 20)
    # number of bytes in a gigabyte
    GBFACTOR = float(1 << 30)
    size = int(size)
    if size > 0:
        return size / KBFACTOR, size / MBFACTOR, size / GBFACTOR,


def get_data_entity_sizes(scope, identifier, revision):
    get_sizes_url = f"{Config.PASTA_URL}/data/size/eml/{scope}/{identifier}/{revision}"
    auth_token = user_data.get_auth_token()
    response = requests.get(get_sizes_url, cookies={'auth-token': auth_token})
    response.raise_for_status()
    lines = response.text.split('\n')
    total = 0
    sizes = []
    for line in lines:
        if len(line) == 0:
            continue
        entity_id, size = line.split(',')
        sizes.append(int(size))
        total += int(size)
    return sizes, total


def move_metadata_files(metadata_file_name, upload_dir):
    src_dir = upload_dir
    dest_dir = user_data.get_user_folder_name()
    src_file = os.path.join(src_dir, metadata_file_name)
    dest_file = os.path.join(dest_dir, metadata_file_name)
    shutil.move(src_file, dest_file)
    json_file_name = metadata_file_name[:-4] + ".json"
    src_file = os.path.join(src_dir, json_file_name)
    dest_file = os.path.join(dest_dir, json_file_name)
    shutil.move(src_file, dest_file)


def ingest_data_table(data_entity_node, upload_dir, object_name):
    # Get the number of header rows, delimiter, and quote char
    num_header_lines_node = data_entity_node.find_descendant(names.NUMHEADERLINES)
    if num_header_lines_node:
        num_header_lines = num_header_lines_node.content
    else:
        num_header_lines = '1'
    field_delimiter_node = data_entity_node.find_descendant(names.FIELDDELIMITER)
    if field_delimiter_node:
        field_delimiter = field_delimiter_node.content
    else:
        field_delimiter = ','
    quote_char_node = data_entity_node.find_descendant(names.QUOTECHARACTER)
    if quote_char_node:
        quote_char = quote_char_node.content
    else:
        quote_char = '"'

    try:
        new_data_entity_node, new_column_vartypes, new_column_names, new_column_categorical_codes, *_ = load_data_table(
            upload_dir, object_name, num_header_lines, field_delimiter, quote_char)
    except FileNotFoundError as e:
        return None

    # use the existing dt_node, but update objectName, size, rows, MD5, etc.
    # also, update column names and categorical codes, as needed
    views.update_data_table(data_entity_node, new_data_entity_node, new_column_names, new_column_categorical_codes,
                            doing_xml_import=True)

    user_data.add_data_table_upload_filename(object_name)
    return data_entity_node


def ingest_other_entity(dataset_node, upload_dir, object_name):
    return load_other_entity(dataset_node, upload_dir, object_name)


def ingest_data_entities(eml_node, upload_dir, entities_with_sizes):
    # Go thru and do the "uploads"
    dataset_node = eml_node.find_descendant(names.DATASET)
    for data_entity_node, data_entity_type, object_name, *_ in entities_with_sizes:
        if data_entity_type == names.DATATABLE:
            # upload the data table
            new_data_entity_node = ingest_data_table(data_entity_node, upload_dir, object_name)
            if not new_data_entity_node:
                flash(f'Data entity "{object_name}" file not found. Please check its Online Distribution URL in the metadata.', 'error')
                continue
            dataset_node.replace_child(data_entity_node, new_data_entity_node)
        if data_entity_type == names.OTHERENTITY:
            # upload the other_entity
            new_data_entity_node = ingest_other_entity(dataset_node, upload_dir, object_name)
            dataset_node.replace_child(data_entity_node, new_data_entity_node)


def retrieve_data_entity(upload_dir, object_name, url):
    if Config.PASTA_URL in url:
        auth_token = user_data.get_auth_token()
        response = requests.get(url, cookies={'auth-token': auth_token})
        response.raise_for_status()

        file_path = os.path.join(upload_dir, object_name)
        with open(file_path, "wb") as file:
            file.write(response.content)
    else:
        pass


def retrieve_data_entities(upload_dir, entities_wth_sizes):
    for _, _, object_name, url, _ in entities_wth_sizes:
        retrieve_data_entity(upload_dir, object_name, url)


def list_data_entities_and_sizes(eml_node):
    data_tables = extract_data_entities_from_eml(eml_node, names.DATATABLE)
    other_entities = extract_data_entities_from_eml(eml_node, names.OTHERENTITY)
    data_entities = data_tables
    data_entities.extend(other_entities)
    entities_with_sizes = []
    total_size = 0
    for data_entity_node, entity_type, object_name, url in data_entities:
        size = get_data_entity_size(url)
        total_size += int(size)
        entities_with_sizes.append((data_entity_node, entity_type, object_name, url, int(size)))
    return entities_with_sizes, total_size


def import_data(filename, eml_node):
    entities_with_sizes, total_size = list_data_entities_and_sizes(eml_node)
    upload_dir = user_data.get_document_uploads_folder_name()
    retrieve_data_entities(upload_dir, entities_with_sizes)
    ingest_data_entities(eml_node, upload_dir, entities_with_sizes)
    save_both_formats(filename, eml_node)
    return total_size


def get_newest_metadata_revision_from_pasta(scope, identifier):
    get_pasta_newest_revision_url = f"{Config.PASTA_URL}/eml/{scope}/{identifier}?filter=newest"
    auth_token = user_data.get_auth_token()
    response = requests.get(get_pasta_newest_revision_url, cookies={'auth-token': auth_token})
    response.raise_for_status()
    revision = response.text

    get_pasta_metadata_url = f"{Config.PASTA_URL}/metadata/eml/{scope}/{identifier}/{revision}"
    auth_token = user_data.get_auth_token()
    response = requests.get(get_pasta_metadata_url, cookies={'auth-token': auth_token})
    response.raise_for_status()

    return revision, response.content


def get_pasta_identifiers(scope=''):
    get_pasta_identifiers_url = f"{Config.PASTA_URL}/eml/{scope}"
    auth_token = user_data.get_auth_token()
    response = requests.get(get_pasta_identifiers_url, cookies={'auth-token': auth_token})
    response.raise_for_status()
    ids = []
    lines = response.text.split('\n')
    for line in lines:
        ids.append(line)
    return lines


# if __name__ == '__main__':
#     retrieve_package_from_edi('edi', '1', '1')
#     pass

