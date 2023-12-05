#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
import_xml.py

This module contains functions for importing/parsing EML XML when executing "Import EML File (XML)..." or
"Fetch a Package from EDI..." items in the Import/Export menu.
"""

import os
import shutil

from flask_login import current_user
from urllib.parse import unquote

from metapype.eml import names, validate
from metapype.model import metapype_io
from metapype.model.node import Node
from metapype.eml.validation_errors import ValidationError

import webapp.auth.user_data as user_data

from webapp.home.utils.load_and_save import fixup_eml_namespaces_on_import
from webapp.home.utils.lists import list_files_in_dir
from webapp.home.home_utils import log_error, log_info


def extract_eml_errors(errs):
    """
    Separate the errors into four sets: unknown node names, unrecognized attributes, child not allowed, and other.
    """
    attribute_unrecognized_errs = set()
    child_not_allowed_errs = set()
    other_errs = set()
    unknown_node_names = set()

    for err in errs:
        validation_err, err_text, *_ = err
        if validation_err == ValidationError.UNKNOWN_NODE:
            unknown_node_names.add(err_text.split()[-1])
        elif validation_err == ValidationError.ATTRIBUTE_UNRECOGNIZED:
            attribute_unrecognized_errs.add(err_text)
        elif validation_err == ValidationError.CHILD_NOT_ALLOWED:
            if "in this position for parent" not in err_text:
                child_not_allowed_errs.add(err_text)
        else:
            other_errs.add((err_text))

    return (sorted(unknown_node_names),
            sorted(attribute_unrecognized_errs),
            sorted(child_not_allowed_errs),
            sorted(other_errs))


def determine_package_name_for_copy(package_name):
    """
    Determine the name to use for the output package when we're making a copy.

    Package name may already be of the form foobar_COPYn. If so, replace n with 1 greater than the max copy number
    already existing. Otherwise, append _COPY.
    """

    user_path = user_data.get_user_folder_name()
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
            max_copy = max(max_copy, 1)
            i = file[name_with_copy_len:-5]  # 5 is len('.json')
            try:
                i = int(i)
                if i > max_copy:
                    max_copy = i
            except:
                pass
    suffix = ''
    if max_copy >= 1:
        suffix = str(max_copy + 1)
    output_package_name = name_with_copy + suffix

    return output_package_name


def save_xml_file_in_temp_folder(file):
    """
    Save the uploaded XML file in the user's temp folder, which is the user folder plus 'zip_temp'.
    """

    user_path = user_data.get_user_folder_name()
    work_path = os.path.join(user_path, 'zip_temp')

    try:
        shutil.rmtree(work_path, ignore_errors=True)
    except FileNotFoundError:
        pass

    try:
        os.mkdir(work_path)
    except FileExistsError:
        pass

    filename = unquote(file.filename)
    filepath = os.path.join(work_path, filename)
    file.save(filepath)
    return filepath


def fix_field_delimiters(eml_node):
    """
    If field delimiters are represented as hex values, convert them to characters. Otherwise, csv readers will fail.
    """

    field_delimiter_nodes = []
    eml_node.find_all_descendants(names.FIELDDELIMITER, field_delimiter_nodes)
    for field_delimiter_node in field_delimiter_nodes:
        delimiter = field_delimiter_node.content
        if delimiter:
            if len(delimiter) > 1:
                try:
                    # Some packages represent the field delimiter as a hex value, e.g., 0x2c for comma. This causes
                    #   csv readers to fail.
                    val = int(delimiter, 16)
                    delimiter = chr(val)
                    field_delimiter_node.content = delimiter
                except:
                    pass


def parse_xml_file(filename, filepath):
    """
    Parse the XML file and return the EML node and any errors.
    """

    log_info(f"parse_xml_file: {filename}")
    eml_version = ''
    with open(filepath, "r") as f:
        lines = f.readlines()
        for line in lines:
            if 'xmlns:eml' in line:
                eml_version = line[-7:-2]
                break
        xml = "".join(lines)
    eml_node = metapype_io.from_xml(xml,
                                    clean=True,
                                    collapse=True,
                                    literals=['literalLayout', 'markdown', 'attributeName', 'code'])
    assert isinstance(eml_node, Node) # TODO: error-handling
    eml_node, nsmap_changed = fixup_eml_namespaces_on_import(eml_node)
    pruned_nodes = set()
    errs = []
    unknown_nodes = None
    attr_errs = None
    child_errs = None
    other_errs = None
    try:
        validate.tree(eml_node, errs)
        validate.tree(eml_node)
        print(f'{filename} - {eml_version}: valid')
        log_info(f'{filename} - {eml_version}: valid')
    except Exception as e:
        print(f'{filename} - {eml_version}: ', end='')
        try:
            pruned = validate.prune(eml_node, strict=False)
            for x, _ in pruned:
                pruned_nodes.add(x.name)
            pruned_nodes = sorted(pruned_nodes)
            unknown_nodes, attr_errs, child_errs, other_errs = extract_eml_errors(errs)
            if unknown_nodes:
                print(f"Unknown nodes: {unknown_nodes}")
                log_info(f"Unknown nodes: {unknown_nodes}")
            if attr_errs:
                print(f"Attribute errors: {attr_errs}")
                log_info(f"Attribute errors: {attr_errs}")
            if child_errs:
                print(f"Child errors: {child_errs}")
                log_info(f"Child errors: {child_errs}")
            if other_errs:
                print(f"Other errors: {other_errs}")
                log_info(f"Other errors: {other_errs}")
            if pruned:
                print(f"Pruned nodes: {pruned_nodes}")
                log_info(f"Pruned nodes: {pruned_nodes}")
            else:
                err_set = set()
                for err in errs:
                    err_set.add(err[1])
                print('***', sorted(err_set))
        except Exception as e:
            print(f'validate.prune FAILED: {e}')
            log_info(f'validate.prune FAILED: {e}')
    fix_field_delimiters(eml_node)
    return eml_node, nsmap_changed, unknown_nodes, attr_errs, child_errs, other_errs, pruned_nodes


