
"""
fetch_data.py

Functions for fetching data entities from PASTA, and functions for fetching PASTA scopes, identifiers, etc.
"""

import base64
import os
import time

from flask import flash
import requests
from urllib.request import urlretrieve

import webapp.home.utils.load_and_save
from metapype.eml import names

import webapp.auth.user_data as user_data
from webapp.config import Config
import webapp.home.exceptions as exceptions

import webapp.views.data_tables.load_data as load_data
from webapp.home.home_utils import log_error, log_info

def extract_data_entities_from_eml(eml_node, entity_type):
    """
    Return a list of tuples of data entities, where each tuple contains the data entity node, the entity type,
    the object name, and the URL.

    The entity_type argument is either 'dataTable' or 'otherEntity'.
    """
    data_entities = []
    data_entity_nodes = []
    eml_node.find_all_descendants(entity_type, data_entity_nodes)
    for data_entity_node in data_entity_nodes:
        object_name_node = data_entity_node.find_descendant(names.OBJECTNAME)
        if object_name_node:
            object_name = object_name_node.content
        else:
            object_name = None
        url_node = data_entity_node.find_descendant(names.URL)
        if url_node:
            url = url_node.content
        if object_name and url_node and url:
            data_entities.append((data_entity_node, entity_type, object_name, url))
    return data_entities


def send_authorized_pasta_request(url):
    """
    Send a request to PASTA, using the auth token if needed.
    """
    response = requests.get(url)
    if response.status_code == 401:
        # PASTA needs an auth token for this request. try again with the auth_token.
        # We don't default to sending the auth token because most requests don't need it and it's often the case
        #  that the user has remained logged in long enough that the token has expired. No point in bothering the
        #  user about an expired token when a token isn't needed.
        auth_token = user_data.get_auth_token()
        # see if auth_token has expired
        auth_decoded = base64.b64decode(auth_token.split('-')[0]).decode('utf-8')
        expiry = int(auth_decoded.split('*')[2])
        current_time = int(time.time()) * 1000
        if expiry < current_time:
            raise exceptions.AuthTokenExpired('')
        # auth_token should be good. try it.
        response = requests.get(url, cookies={'auth-token': auth_token})
        if response.status_code == 401:
            raise exceptions.Unauthorized('')
    return response


def get_data_entity_size(url):
    """
    For PASTA data entities, return the size of the data entity in bytes. For non-PASTA data entities, return 0.
    """
    if Config.PASTA_URL in url:
        get_data_entity_size_url = url.replace('data/eml', 'data/size/eml')
        response = send_authorized_pasta_request(get_data_entity_size_url)
        response.raise_for_status()
        return response.text
    else:
        # raise exceptions.ezEMLAttemptToAccessNonPASTAData
        return '0'


def get_data_entity(upload_dir, object_name, url):
    """
    Get a data entity via a PASTA URL and save it to the upload_dir.
    """
    if Config.PASTA_URL in url:
        response = send_authorized_pasta_request(url)
        response.raise_for_status()

        file_path = os.path.join(upload_dir, object_name)
        with open(file_path, "wb") as file:
            file.write(response.content)
    else:
        pass


def convert_file_size(size):
    """
    Convert the file size from bytes to a human-readable format. Return a tuple of (size in kilobytes, size in
    megabytes, size in gigabytes).
    """
    # number of bytes in a kilobyte
    KBFACTOR = float(1 << 10)
    # number of bytes in a megabyte
    MBFACTOR = float(1 << 20)
    # number of bytes in a gigabyte
    GBFACTOR = float(1 << 30)
    size = int(size)
    return size / KBFACTOR, size / MBFACTOR, size / GBFACTOR,


def get_data_entity_sizes(scope, identifier, revision):
    """
    Get the sizes of the PASTA data entities in the specified scope, identifier, and revision. Return a tuple of
    (list of sizes, total size).
    """
    get_sizes_url = f"{Config.PASTA_URL}/data/size/eml/{scope}/{identifier}/{revision}"
    response = send_authorized_pasta_request(get_sizes_url)
    response.raise_for_status()
    lines = response.text.splitlines()
    total = 0
    sizes = []
    for line in lines:
        if len(line) == 0:
            continue
        entity_id, size = line.split(',')
        sizes.append(int(size))
        total += int(size)
    return sizes, total


def ingest_data_table(data_entity_node, upload_dir, object_name):
    """
    Ingest a data table.

    Get the delimiter, quote character, and number of header lines from the data entity node.
    Load the data table into the user's upload directory. Update the existing data entity node with the new
    objectName, size, rows, MD5, etc. Also, update column names and categorical codes, as needed.

    Logically, this function could be nested within the ingest_data_entities function, but it's a separate function
    to make the code more readable.
    """
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
        new_data_entity_node, new_column_vartypes, new_column_names, new_column_categorical_codes, *_ = \
            load_data.load_data_table(upload_dir, object_name, num_header_lines, field_delimiter, quote_char)
    except FileNotFoundError as e:
        return None

    # Use the existing dt_node, but update objectName, size, rows, MD5, etc.
    # Also, update column names and categorical codes, as needed
    load_data.update_data_table(data_entity_node, new_data_entity_node, new_column_names, new_column_categorical_codes,
                                                         doing_xml_import=True)

    user_data.add_data_table_upload_filename(object_name)
    return data_entity_node


def ingest_other_entity(dataset_node, upload_dir, object_name, node_id):
    """
    Ingest an other entity.

    Logically, this function could be nested within the ingest_data_entities function, but it's a separate function
    to make the code more readable.
    """
    return load_data.load_other_entity(dataset_node, upload_dir, object_name, node_id)


def ingest_data_entities(eml_node, upload_dir, entities_with_sizes):
    """
    Ingest all of the data entities in the EML document.

    First we retrieve, then we ingest. See retrieve_data_entities(), below.
    """
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
            new_data_entity_node = ingest_other_entity(dataset_node, upload_dir, object_name, data_entity_node.id)
            dataset_node.replace_child(data_entity_node, new_data_entity_node)


def retrieve_data_entity(upload_dir, object_name, url):
    """
    Retrieve the data entity from PASTA and save it in the upload directory.
    """
    file_path = os.path.join(upload_dir, object_name)
    if Config.PASTA_URL in url:
        response = send_authorized_pasta_request(url)
        response.raise_for_status()
        with open(file_path, "wb") as file:
            file.write(response.content)
    else:
        try:
            urlretrieve(url, file_path)
        except Exception:
            pass


def retrieve_data_entities(upload_dir, entities_wth_sizes):
    """
    Retrieve the data entities from PASTA and save them in the upload directory.

    First we retrieve, then we ingest.
    """
    for _, _, object_name, url, _ in entities_wth_sizes:
        retrieve_data_entity(upload_dir, object_name, url)


def list_data_entities_and_sizes(eml_node):
    """
    Construct a list of data entities and their sizes.
    Data entities include both data tables and other entities.

    Returns a list of tuples of the form (data_entity_node, entity_type, object_name, url, size) and the total size.
    entity_type is either 'dataTable' or 'otherEntity'.
    """
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
    """
    Fetch all of the data entities for a package and ingest their metadata into the EML document.

    Data entities include both data tables and other entities.
    """
    entities_with_sizes, total_size = list_data_entities_and_sizes(eml_node)
    upload_dir = user_data.get_document_uploads_folder_name()
    retrieve_data_entities(upload_dir, entities_with_sizes)
    ingest_data_entities(eml_node, upload_dir, entities_with_sizes)
    webapp.home.utils.load_and_save.save_both_formats(filename, eml_node)
    return total_size


def get_metadata_revision_from_pasta(scope, identifier, revision=None):
    """
    Get the metadata for a revision from PASTA. If no revision is specified, get the newest revision.
    """
    if not revision:
        get_pasta_newest_revision_url = f"{Config.PASTA_URL}/eml/{scope}/{identifier}?filter=newest"
        response = requests.get(get_pasta_newest_revision_url)
        response.raise_for_status()
        revision = response.text

    get_pasta_metadata_url = f"{Config.PASTA_URL}/metadata/eml/{scope}/{identifier}/{revision}"
    response = requests.get(get_pasta_metadata_url)
    response.raise_for_status()

    return revision, response.content


def get_pasta_identifiers(scope=''):
    """
    Return a list of all identifiers for a given PASTA scope, or if no scope is specified, return a list of scopes.
    """
    get_pasta_identifiers_url = f"{Config.PASTA_URL}/eml/{scope}"
    response = requests.get(get_pasta_identifiers_url)
    response.raise_for_status()
    ids = []
    lines = response.text.splitlines()
    for line in lines:
        ids.append(line)
    return lines


def get_revisions_list(scope, identifier):
    """
    Return a list of all revisions for a given PASTA scope and identifier.
    """
    url = f"{Config.PASTA_URL}/eml/{scope}/{identifier}"

    response = requests.get(url)
    response.raise_for_status()
    revisions = response.text.splitlines()
    return revisions

