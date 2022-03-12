
import os
import shutil

import daiquiri
from flask_login import current_user

from metapype.eml import validate
from metapype.model import metapype_io
from metapype.model.node import Node
from metapype.eml.validation_errors import ValidationError

import webapp.auth.user_data as user_data

from webapp.home.metapype_client import list_files_in_dir

logger = daiquiri.getLogger('import_xml: ' + __name__)


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


def extract_eml_errors(errs):
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


def determine_package_name(package_name=None):
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

    # src_file = os.path.join(work_path, package_name) + '.zip'
    # dest_file = os.path.join(work_path, output_package_name) + '.zip'
    # shutil.move(src_file, dest_file)
    return output_package_name


def save_xml_file(file):
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

    filename = file.filename
    filepath = os.path.join(work_path, filename)
    file.save(filepath)
    return filepath


def parse_xml_file(filename, filepath):
    log_info(f"parse_xml_file: {filename}")
    eml_version = ''
    with open(filepath, "r") as f:
        lines = f.readlines()
        for line in lines:
            if 'xmlns:eml' in line:
                eml_version = line[-7:-2]
                break
        xml = "".join(lines)
    eml_node = metapype_io.from_xml(xml, clean=True, literals=['literalLayout', 'markdown'])
    assert isinstance(eml_node, Node) # TODO: error-handling
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
#         return None
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
    return eml_node, unknown_nodes, attr_errs, child_errs, other_errs, pruned_nodes


