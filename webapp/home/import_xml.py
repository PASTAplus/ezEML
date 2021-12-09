
import os
import shutil

from metapype.eml import validate
from metapype.model import metapype_io
from metapype.model.node import Node
from metapype.eml.validation_errors import ValidationError

import webapp.auth.user_data as user_data


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


def upload_xml_file(file, filename, package_name):
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

    dest = os.path.join(work_path, package_name) + '.xml'
    file.save(dest)

    eml_version = ''
    with open(dest, "r") as f:
        lines = f.readlines()
        for line in lines:
            if 'xmlns:eml' in line:
                eml_version = line[-7:-2]
                break
        xml = "".join(lines)
    eml = metapype_io.from_xml(xml, clean=True)
#     print(eml)
    assert isinstance(eml, Node) # TODO: error-handling
    pruned_nodes = set()
    errs = []
    try:
        validate.tree(eml, errs)
        validate.tree(eml)
        print(f'{filename} - {eml_version}: valid')
#         return None
    except Exception as e:
        print(f'{filename} - {eml_version}: ', end='')
        try:
            pruned = validate.prune(eml, strict=True)
            for x in pruned:
                pruned_nodes.add(x.name)
            unknown_nodes, attr_errs, child_errs, other_errs = extract_eml_errors(errs)
            if unknown_nodes:
                print(f"Unknown nodes: {unknown_nodes}")
            if attr_errs:
                print(f"Attribute errors: {attr_errs}")
            if child_errs:
                print(f"Child errors: {child_errs}")
            if other_errs:
                print(f"Other errors: {other_errs}")
            if pruned:
                print(f"Pruned nodes: {sorted(pruned_nodes)}")
            else:
                err_set = set()
                for err in errs:
                    err_set.add(err[1])
                print('***', sorted(err_set))
        except Exception as e:
            print(f'validate.prune FAILED: {e}')
    return eml, sorted(pruned_nodes)


