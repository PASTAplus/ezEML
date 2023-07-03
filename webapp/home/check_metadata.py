#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: evaluate.py

:Synopsis:

:Author:
    ide

:Created:
    6/20/20
"""

import collections
import csv
from enum import Enum

from flask import (
    Blueprint, Flask, url_for, render_template, session, app
)

from metapype.eml import names
import metapype.eml.validate as validate
from metapype.eml.validation_errors import ValidationError
import metapype.eml.evaluate as evaluate
from metapype.eml.evaluation_warnings import EvaluationWarning
from metapype.model.node import Node
import webapp.home.metapype_client as metapype_client
from webapp.pages import *
import webapp.auth.user_data as user_data
import webapp.home.load_data_table as load_data_table
import webapp.home.motherpype_names as mdb_names

from webapp.validate import evaluate_mp
from webapp.validate.evaluation_warnings_mp import EvaluationWarningMp

app = Flask(__name__)
home = Blueprint('home', __name__, template_folder='templates')

evals = {}
rows = []
with open('webapp/static/evaluate.csv') as csv_file:
    csv_reader = csv.reader(csv_file)
    for row in csv_reader:
        rows.append(row)
for row_num in range(1, len(rows)):
    id, *vals = rows[row_num]
    evals[f'__eval__{id}'] = vals


class EvalSeverity(Enum):
    ERROR = 1
    WARNING = 2
    INFO = 3


class EvalType(Enum):
    REQUIRED = 1
    RECOMMENDED = 2
    BEST_PRACTICE = 3
    OPTIONAL = 4


scopes = [
    'ecotrends',
    'edi',
    'knb-lter-and',
    'knb-lter-arc',
    'knb-lter-bes',
    'knb-lter-ble',
    'knb-lter-bnz',
    'knb-lter-cap',
    'knb-lter-cce',
    'knb-lter-cdr',
    'knb-lter-cwt',
    'knb-lter-fce',
    'knb-lter-gce',
    'knb-lter-hbr',
    'knb-lter-hfr',
    'knb-lter-jrn',
    'knb-lter-kbs',
    'knb-lter-knz',
    'knb-lter-luq',
    'knb-lter-mcm',
    'knb-lter-mcr',
    'knb-lter-nes',
    'knb-lter-nin',
    'knb-lter-ntl',
    'knb-lter-nwk',
    'knb-lter-nwt',
    'knb-lter-pal',
    'knb-lter-pie',
    'knb-lter-sbc',
    'knb-lter-sev',
    'knb-lter-sgs',
    'knb-lter-vcr',
    'lter-landsat',
    'lter-landsat-ledaps',
    'msb-cap',
    'msb-paleon',
    'msb-tempbiodev'
]


def get_eval_entry(id, link=None, section=None, item=None):
    try:
        vals = evals[f'__eval__{id}']
        if section:
            vals[0] = section
        if item:
            vals[1] = item
        return Eval_Entry(section=vals[0], item=vals[1], severity=EvalSeverity[vals[2]], type=EvalType[vals[3]],
                          explanation=vals[4], link=link)
    except:
        return None


def add_to_evaluation(id, link=None, section=None, item=None):
    entry = get_eval_entry(id, link, section, item)
    if entry:
        evaluation.append(entry)


Eval_Entry = collections.namedtuple(
    'Evaluate_Entry', ["section", "item", "severity", "type", "explanation", "link"])
evaluation = []


def find_min_unmet(errs, node_name, child_name):
    for err_code, msg, node, *args in errs:
        if err_code == ValidationError.MIN_OCCURRENCE_UNMET:
            err_cause, min = args
            if node.name == node_name and err_cause == child_name:
                return True
    return False


def find_min_unmet_for_choice(errs, node_name):
    for err_code, msg, node, *args in errs:
        if err_code == ValidationError.MIN_CHOICE_UNMET and node.name == node_name:
            return True
    return False


def find_content_empty(errs, node_name):
    found = []
    for err in errs:
        err_code, _, node, *_ = err
        if err_code == ValidationError.CONTENT_EXPECTED_NONEMPTY and node.name == node_name:
            found.append(err)
    return found


def find_content_enum(errs, node_name):
    found = []
    for err in errs:
        err_code, _, node, *_ = err
        if err_code == ValidationError.CONTENT_EXPECTED_ENUM and node.name == node_name:
            found.append(err)
    return found


def find_err_code(errs, err_code_to_find, node_name):
    found = []
    for err in errs:
        err_code, _, node, *_ = err
        if err_code == err_code_to_find and node.name == node_name:
            found.append(err)
    return found


def find_missing_attribute(errs, node_name, attribute_name):
    errs_found = find_err_code(errs, ValidationError.ATTRIBUTE_REQUIRED, node_name)
    for err in errs_found:
        errcode, msg, node, attribute = err
        if attribute == attribute_name:
            return err
    return None


def check_dataset_title(eml_node, filename):
    link = url_for(PAGE_TITLE, filename=filename)
    dataset_node = eml_node.find_child(names.DATASET)
    validation_errs = validate_via_metapype(dataset_node)
    # Is title node missing?
    if find_min_unmet(validation_errs, names.DATASET, names.TITLE):
        add_to_evaluation('title_01', link)
        return
    # Is title node content empty?
    title_node = eml_node.find_single_node_by_path([names.DATASET, names.TITLE])
    if title_node:
        validation_errs = validate_via_metapype(title_node)
    if not title_node or find_content_empty(validation_errs, names.TITLE):
        add_to_evaluation('title_01', link)
        return

    evaluation_warnings = evaluate_via_metapype(title_node)
    # Is the title too short?
    if find_err_code(evaluation_warnings, EvaluationWarning.TITLE_TOO_SHORT, names.TITLE):
        add_to_evaluation('title_02', link)


def check_id_for_EDI(package_id):
    try:
        scope, identifier, revision = package_id.split('.')
        if scope not in scopes:
            raise ValueError
        identifier = int(identifier)
        revision = int(revision)
    except ValueError:
        return False
    return True


def check_data_package_id(eml_node, filename):
    link = url_for(PAGE_DATA_PACKAGE_ID, filename=filename)
    validation_errs = validate_via_metapype(eml_node)
    if find_missing_attribute(validation_errs, 'eml', 'packageId'):
        add_to_evaluation('data_package_id_01', link)
    else:
        # check if data package ID has correct form for EDI data repository
        data_package_id = eml_node.attribute_value("packageId")
        if not check_id_for_EDI(data_package_id):
            add_to_evaluation('data_package_id_02', link)


def check_responsible_party(rp_node:Node, section:str=None, item:str=None,
                            page:str=None, filename:str=None, node_id:str=None,
                            related_project_node_id:str=None):
    if not related_project_node_id:
        link = url_for(page, filename=filename, node_id=node_id)
    else:
        link = url_for(page, filename=filename, node_id=node_id, project_node_id=related_project_node_id)
    validation_errs = validate_via_metapype(rp_node)

    # Last name is required if other parts of name are given
    if find_min_unmet(validation_errs, names.INDIVIDUALNAME, names.SURNAME):
        add_to_evaluation('responsible_party_04', link, section, item)

    # At least one of surname, organization name, or position name is required
    if find_min_unmet_for_choice(validation_errs, rp_node.name):
        add_to_evaluation('responsible_party_01', link, section, item)

    # Organization ID requires a directory attribute
    if find_missing_attribute(validation_errs, 'userId', 'directory'):
        add_to_evaluation('responsible_party_06', link, section, item)

    # Role, if required
    if find_min_unmet(validation_errs, rp_node.name, names.ROLE) or find_content_empty(validation_errs, names.ROLE):
        add_to_evaluation('responsible_party_03', link, section, item)

    evaluation_warnings = evaluate_via_metapype(rp_node)
    # User ID is recommended
    if find_err_code(evaluation_warnings, EvaluationWarning.ORCID_ID_MISSING, rp_node.name):
        add_to_evaluation('responsible_party_02', link, section, item)

    # Email is recommended
    if find_err_code(evaluation_warnings, EvaluationWarning.EMAIL_MISSING, rp_node.name):
        add_to_evaluation('responsible_party_05', link, section, item)

def check_creators(eml_node, filename):
    link = url_for(PAGE_CREATOR_SELECT, filename=filename)
    dataset_node = eml_node.find_child(names.DATASET)
    validation_errs = validate_via_metapype(dataset_node)

    if find_min_unmet(validation_errs, names.DATASET, names.CREATOR):
        add_to_evaluation('creators_01', link)
    else:
        creator_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.CREATOR])
        for creator_node in creator_nodes:
            check_responsible_party(creator_node, 'Creators', 'Creator', PAGE_CREATOR, filename, creator_node.id)


def check_metadata_providers(eml_node, filename):
    link = url_for(PAGE_METADATA_PROVIDER_SELECT, filename=filename)
    metadata_provider_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.METADATAPROVIDER])
    if metadata_provider_nodes and len(metadata_provider_nodes) > 0:
        for metadata_provider_node in metadata_provider_nodes:
            check_responsible_party(metadata_provider_node, 'Metadata Providers', 'Metadata Provider',
                                    PAGE_METADATA_PROVIDER, filename, metadata_provider_node.id)


def check_associated_parties(eml_node, filename):
    link = url_for(PAGE_ASSOCIATED_PARTY_SELECT, filename=filename)
    associated_party_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.ASSOCIATEDPARTY])
    if associated_party_nodes and len(associated_party_nodes) > 0:
        for associated_party_node in associated_party_nodes:
            check_responsible_party(associated_party_node, 'Associated Parties', 'Associated Party',
                                    PAGE_ASSOCIATED_PARTY, filename, associated_party_node.id)


def check_dataset_abstract(eml_node, filename):
    link = url_for(PAGE_ABSTRACT, filename=filename)
    dataset_node = eml_node.find_child(names.DATASET)
    evaluation_warnings = evaluate_via_metapype(dataset_node)

    if find_err_code(evaluation_warnings, EvaluationWarning.DATASET_ABSTRACT_MISSING, names.DATASET):
        add_to_evaluation('abstract_01', link)
        return

    if find_err_code(evaluation_warnings, EvaluationWarning.DATASET_ABSTRACT_TOO_SHORT, names.DATASET):
        add_to_evaluation('abstract_02', link)
        return


def check_keywords(eml_node, filename):
    link = url_for(PAGE_KEYWORD_SELECT, filename=filename)
    dataset_node = eml_node.find_child(names.DATASET)
    evaluation_warnings = evaluate_via_metapype(dataset_node)

    if find_err_code(evaluation_warnings, EvaluationWarning.KEYWORDS_MISSING, names.DATASET):
        add_to_evaluation('keywords_01', link)
        return

    if find_err_code(evaluation_warnings, EvaluationWarning.KEYWORDS_INSUFFICIENT, names.DATASET):
        add_to_evaluation('keywords_02', link)
        return


def check_intellectual_rights(eml_node, filename):
    link = url_for(PAGE_INTELLECTUAL_RIGHTS, filename=filename)
    dataset_node = eml_node.find_child(names.DATASET)
    evaluation_warnings = evaluate_via_motherpype(dataset_node)

    if find_err_code(evaluation_warnings, EvaluationWarningMp.INTELLECTUAL_RIGHTS_MISSING, names.DATASET):
        add_to_evaluation('intellectual_rights_01', link)
        return


def check_taxonomic_coverage(node, filename):

    link = url_for(PAGE_TAXONOMIC_COVERAGE, filename=filename, node_id=node.id)

    validation_errs = validate_via_metapype(node)
    if find_content_empty(validation_errs, names.TAXONRANKNAME):
        add_to_evaluation('taxonomic_coverage_01', link)
    if find_content_empty(validation_errs, names.TAXONRANKVALUE):
        add_to_evaluation('taxonomic_coverage_02', link)


def check_coverage(eml_node, filename):
    dataset_node = eml_node.find_child(names.DATASET)

    link = url_for(PAGE_TAXONOMIC_COVERAGE_SELECT, filename=filename)

    evaluation_warnings = evaluate_via_motherpype(dataset_node)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.TAXONOMIC_COVERAGE_MISSING, names.DATASET):
        add_to_evaluation('taxonomic_coverage_03', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.TAXONOMIC_COVERAGE_GENUS_MISSING, names.DATASET):
        add_to_evaluation('taxonomic_coverage_04', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.TAXONOMIC_COVERAGE_SPECIES_MISSING, names.DATASET):
        add_to_evaluation('taxonomic_coverage_05', link)

    link = url_for(PAGE_TEMPORAL_COVERAGE_SELECT, filename=filename)

    if find_err_code(evaluation_warnings, EvaluationWarningMp.TEMPORAL_COVERAGE_MISSING, names.DATASET):
        add_to_evaluation('temporal_coverage_01', link)

    taxonomic_classification_nodes = []
    dataset_node.find_all_descendants(names.TAXONOMICCOVERAGE, taxonomic_classification_nodes)
    for taxonomic_classification_node in taxonomic_classification_nodes:
        check_taxonomic_coverage(taxonomic_classification_node, filename)

    link = url_for(PAGE_INTELLECTUAL_RIGHTS, filename=filename)

    if find_err_code(evaluation_warnings, EvaluationWarningMp.INTELLECTUAL_RIGHTS_MISSING, names.DATASET):
        add_to_evaluation('intellectual_rights_01', link)
        return


def check_geographic_coverage(eml_node, filename):
    link = url_for(PAGE_GEOGRAPHIC_COVERAGE_SELECT, filename=filename)
    geographic_coverage_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.COVERAGE, names.GEOGRAPHICCOVERAGE])
    for geographic_coverage_node in geographic_coverage_nodes:
        link = url_for(PAGE_GEOGRAPHIC_COVERAGE, filename=filename, node_id=geographic_coverage_node.id)
        validation_errs = validate_via_metapype(geographic_coverage_node)
        if find_content_empty(validation_errs, names.GEOGRAPHICDESCRIPTION):
            add_to_evaluation('geographic_coverage_01', link)
        if find_err_code(validation_errs, ValidationError.CONTENT_EXPECTED_RANGE, names.WESTBOUNDINGCOORDINATE):
            add_to_evaluation('geographic_coverage_03', link)
        if find_err_code(validation_errs, ValidationError.CONTENT_EXPECTED_RANGE, names.EASTBOUNDINGCOORDINATE):
            add_to_evaluation('geographic_coverage_04', link)
        if find_err_code(validation_errs, ValidationError.CONTENT_EXPECTED_RANGE, names.NORTHBOUNDINGCOORDINATE):
            add_to_evaluation('geographic_coverage_05', link)
        if find_err_code(validation_errs, ValidationError.CONTENT_EXPECTED_RANGE, names.SOUTHBOUNDINGCOORDINATE):
            add_to_evaluation('geographic_coverage_06', link)
        if find_content_enum(validation_errs, names.ALTITUDEUNITS):
            add_to_evaluation('geographic_coverage_08', link)
        # special case to combine missing bounding coordinates into a single error
        if find_min_unmet(validation_errs, names.BOUNDINGCOORDINATES, names.WESTBOUNDINGCOORDINATE) or \
            find_min_unmet(validation_errs, names.BOUNDINGCOORDINATES, names.EASTBOUNDINGCOORDINATE) or \
            find_min_unmet(validation_errs, names.BOUNDINGCOORDINATES, names.NORTHBOUNDINGCOORDINATE) or \
            find_min_unmet(validation_errs, names.BOUNDINGCOORDINATES, names.SOUTHBOUNDINGCOORDINATE):
            add_to_evaluation('geographic_coverage_02', link)
        # special case to cover the three bounding altitudes fields
        if find_min_unmet(validation_errs, names.BOUNDINGALTITUDES, names.ALTITUDEMINIMUM) or \
            find_min_unmet(validation_errs, names.BOUNDINGALTITUDES, names.ALTITUDEMAXIMUM) or \
            find_min_unmet(validation_errs, names.BOUNDINGALTITUDES, names.ALTITUDEUNITS) or \
            find_content_empty(validation_errs, names.ALTITUDEMINIMUM) or \
            find_content_empty(validation_errs, names.ALTITUDEMAXIMUM) or \
            find_content_empty(validation_errs, names.ALTITUDEUNITS):
            add_to_evaluation('geographic_coverage_07', link)

def get_attribute_type(attrib_node:Node):
    mscale_node = attrib_node.find_child(names.MEASUREMENTSCALE)
    nominal_node = mscale_node.find_child(names.NOMINAL)
    if nominal_node:
        enumerated_domain_node = nominal_node.find_single_node_by_path([names.NONNUMERICDOMAIN, names.ENUMERATEDDOMAIN])
        if enumerated_domain_node:
            return metapype_client.VariableType.CATEGORICAL
        text_domain_node = nominal_node.find_single_node_by_path([names.NONNUMERICDOMAIN, names.TEXTDOMAIN])
        if text_domain_node:
            return metapype_client.VariableType.TEXT
    ratio_node = mscale_node.find_child(names.RATIO)
    if ratio_node:
        return metapype_client.VariableType.NUMERICAL
    datetime_node = mscale_node.find_child(names.DATETIME)
    if datetime_node:
        return metapype_client.VariableType.DATETIME
    return None


def generate_code_definition_errs(eml_node, filename, err_code, errs_found):
    mscale = metapype_client.VariableType.CATEGORICAL
    for err in errs_found:
        err_node = err[2]
        code_definition_node = err_node.parent
        enumerated_domain_node = code_definition_node.parent
        non_numeric_domain_node = enumerated_domain_node.parent
        nominal_node = non_numeric_domain_node.parent
        mscale_node = nominal_node.parent
        attribute_node = mscale_node.parent
        attribute_list_node = attribute_node.parent
        data_table_node = attribute_list_node.parent
        link = url_for(PAGE_CODE_DEFINITION, filename=filename, dt_node_id=data_table_node.id, att_node_id=attribute_node.id,
                       nom_ord_node_id=nominal_node.id, node_id=code_definition_node.id, mscale=mscale)
        add_to_evaluation(err_code, link)


def check_attribute(eml_node, filename, data_table_node:Node, attrib_node:Node):
    attr_type = get_attribute_type(attrib_node)
    mscale = None
    if attr_type == metapype_client.VariableType.CATEGORICAL:
        page = PAGE_ATTRIBUTE_CATEGORICAL
        mscale = metapype_client.VariableType.CATEGORICAL.name
    elif attr_type == metapype_client.VariableType.NUMERICAL:
        page = PAGE_ATTRIBUTE_NUMERICAL
        mscale = metapype_client.VariableType.NUMERICAL.name
    elif attr_type == metapype_client.VariableType.TEXT:
        page = PAGE_ATTRIBUTE_TEXT
        mscale = metapype_client.VariableType.TEXT.name
    elif attr_type == metapype_client.VariableType.DATETIME:
        page = PAGE_ATTRIBUTE_DATETIME
        mscale = metapype_client.VariableType.DATETIME.name
    link = url_for(page, filename=filename, dt_node_id=data_table_node.id, node_id=attrib_node.id, mscale=mscale)

    validation_errs = validate_via_metapype(attrib_node)
    if find_content_empty(validation_errs, names.ATTRIBUTEDEFINITION):
        add_to_evaluation('attributes_01', link)
    if find_min_unmet(validation_errs, names.MISSINGVALUECODE, names.CODEEXPLANATION):
        add_to_evaluation('attributes_07', link)

    # Categorical
    if attr_type == metapype_client.VariableType.CATEGORICAL:
        if find_min_unmet(validation_errs, names.ENUMERATEDDOMAIN, names.CODEDEFINITION):
            add_to_evaluation('attributes_04', link)
        found = find_content_empty(validation_errs, names.CODE)
        if found:
            generate_code_definition_errs(eml_node, filename, 'attributes_05', found)
        found = find_content_empty(validation_errs, names.DEFINITION)
        if found:
            generate_code_definition_errs(eml_node, filename, 'attributes_06', found)

    # Numerical
    if attr_type == metapype_client.VariableType.NUMERICAL:
        if find_min_unmet(validation_errs, names.RATIO, names.UNIT):
            add_to_evaluation('attributes_02', link)
        if find_min_unmet_for_choice(validation_errs, names.UNIT):
            add_to_evaluation('attributes_02', link)

    # DateTime
    if attr_type == metapype_client.VariableType.DATETIME:
        if find_content_empty(validation_errs, names.FORMATSTRING):
            add_to_evaluation('attributes_03', link)


def check_data_table_md5_checksum(data_table_node, link):
    object_name_node = data_table_node.find_descendant(names.OBJECTNAME)
    data_file = object_name_node.content
    uploads_folder = user_data.get_document_uploads_folder_name()
    full_path = f'{uploads_folder}/{data_file}'
    try:
        computed_md5_hash = load_data_table.get_md5_hash(full_path)
    except FileNotFoundError:
        add_to_evaluation('data_table_07', link)
        return
    authentication_node = data_table_node.find_descendant(names.AUTHENTICATION)
    if authentication_node:
        found_md5_hash = authentication_node.content
        if found_md5_hash != computed_md5_hash:
            add_to_evaluation('data_table_06', link)


def check_data_table(eml_node, filename, data_table_node:Node):
    link = url_for(PAGE_DATA_TABLE, filename=filename, dt_node_id=data_table_node.id)
    validation_errs = validate_via_metapype(data_table_node)

    check_data_table_md5_checksum(data_table_node, link)

    if find_min_unmet(validation_errs, names.DATATABLE, names.ENTITYNAME):
        add_to_evaluation('data_table_01', link)
    if find_min_unmet(validation_errs, names.DATATABLE, names.ENTITYDESCRIPTION):
        add_to_evaluation('data_table_02', link)
    if find_min_unmet(validation_errs, names.PHYSICAL, names.OBJECTNAME):
        add_to_evaluation('data_table_03', link)
    if find_min_unmet(validation_errs, names.DATATABLE, names.ATTRIBUTELIST):
        add_to_evaluation('data_table_04', link)

    evaluation_warnings = evaluate_via_metapype(data_table_node)
    if find_err_code(evaluation_warnings, EvaluationWarning.DATATABLE_DESCRIPTION_MISSING, names.DATATABLE):
        add_to_evaluation('data_table_02', link)

    attribute_list_node = data_table_node.find_child(names.ATTRIBUTELIST)
    if attribute_list_node:
        attribute_nodes = attribute_list_node.find_all_children(names.ATTRIBUTE)
        for attribute_node in attribute_nodes:
            check_attribute(eml_node, filename, data_table_node, attribute_node)


def check_data_tables(eml_node, filename):
    link = url_for(PAGE_DATA_TABLE_SELECT, filename=filename)
    dataset_node = eml_node.find_child(names.DATASET)
    evaluation_warnings = evaluate_via_metapype(dataset_node)
    if find_err_code(evaluation_warnings, EvaluationWarning.DATATABLE_MISSING, names.DATASET):
        add_to_evaluation('data_table_05', link)

    data_table_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.DATATABLE])
    for data_table_node in data_table_nodes:
        check_data_table(eml_node, filename, data_table_node)


def check_maintenance(eml_node, filename):
    link = url_for(PAGE_MAINTENANCE, filename=filename)
    dataset_node = eml_node.find_child(names.DATASET)
    evaluation_warnings = evaluate_via_metapype(dataset_node)
    if find_err_code(evaluation_warnings, EvaluationWarning.MAINTENANCE_DESCRIPTION_MISSING, names.DESCRIPTION):
        add_to_evaluation('maintenance_01', link)


def check_contacts(eml_node, filename):
    link = url_for(PAGE_CONTACT_SELECT, filename=filename)
    dataset_node = eml_node.find_child(names.DATASET)
    validation_errs = validate_via_metapype(dataset_node)
    if find_min_unmet(validation_errs, names.DATASET, names.CONTACT):
        add_to_evaluation('contacts_01', link=link)
    contact_nodes = eml_node.find_all_nodes_by_path([
        names.DATASET,
        names.CONTACT
    ])
    for contact_node in contact_nodes:
        check_responsible_party(contact_node, 'Contacts', 'Contact', PAGE_CONTACT,
                                filename, contact_node.id)


def check_method_step(method_step_node, filename, node_id):
    link = url_for(PAGE_METHOD_STEP, filename=filename, node_id=node_id)
    evaluation_warnings = evaluate_via_metapype(method_step_node)
    if find_err_code(evaluation_warnings, EvaluationWarning.METHOD_STEP_DESCRIPTION_MISSING, names.DESCRIPTION):
        add_to_evaluation('methods_02', link)


def check_method_steps(eml_node, filename):
    link = url_for(PAGE_METHOD_STEP_SELECT, filename=filename)
    dataset_node = eml_node.find_child(names.DATASET)
    evaluation_warnings = evaluate_via_metapype(dataset_node)
    if find_err_code(evaluation_warnings, EvaluationWarning.DATASET_METHOD_STEPS_MISSING, names.DATASET):
        add_to_evaluation('methods_01', link)

    method_step_nodes = eml_node.find_all_nodes_by_path([
        names.DATASET,
        names.METHODS,
        names.METHODSTEP
    ])
    for method_step_node in method_step_nodes:
        check_method_step(method_step_node, filename, method_step_node.id)


def check_project_award(award_node, filename, related_project_id=None):
    if not related_project_id:
        link = url_for(PAGE_FUNDING_AWARD, filename=filename, node_id=award_node.id)
    else:
        link = url_for(PAGE_FUNDING_AWARD, filename=filename, node_id=award_node.id, project_node_id=related_project_id)
    validation_errors = validate_via_metapype(award_node)
    if find_min_unmet(validation_errors, names.AWARD, names.FUNDERNAME) or \
            find_content_empty(validation_errors, names.FUNDERNAME):
        add_to_evaluation('project_04', link)
    if find_min_unmet(validation_errors, names.AWARD, names.TITLE) or \
            find_content_empty(validation_errors, names.TITLE):
        add_to_evaluation('project_05', link)


def check_project_node(project_node, filename, related_project_id=None):
    if not related_project_id:
        link = url_for(PAGE_PROJECT, filename=filename)
    else:
        link = url_for(PAGE_PROJECT, filename=filename, node_id=related_project_id)
    validation_errors = validate_via_metapype(project_node)
    name = project_node.name
    if find_min_unmet(validation_errors, name, names.TITLE):
        add_to_evaluation('project_01', link)
    if find_content_empty(validation_errors, names.TITLE):
        # We need to distinguish between a missing title for the project itself or one of its related projects
        found = find_content_empty(validation_errors, names.TITLE)
        for err_code, msg, node, *args in found:
            if node.parent.name == name:
                add_to_evaluation('project_01', link)
    if find_min_unmet(validation_errors, name, names.PERSONNEL):
        add_to_evaluation('project_02', link)

    project_personnel_nodes = project_node.find_all_children(names.PERSONNEL)
    for project_personnel_node in project_personnel_nodes:
        check_responsible_party(project_personnel_node, "Project", "Project Personnel",
                                PAGE_PROJECT_PERSONNEL, filename, project_personnel_node.id,
                                related_project_id)

    project_award_nodes = project_node.find_all_children(names.AWARD)
    for project_award_node in project_award_nodes:
        check_project_award(project_award_node, filename, related_project_id)

    related_project_nodes = project_node.find_all_children(names.RELATED_PROJECT)
    for related_project_node in related_project_nodes:
        check_project_node(related_project_node, filename, related_project_node.id)


def check_project(eml_node, filename):
    link = url_for(PAGE_PROJECT, filename=filename)
    project_node = eml_node.find_single_node_by_path([names.DATASET, names.PROJECT])
    if project_node:
        check_project_node(project_node, filename)
    else:
        dataset_node = eml_node.find_child(names.DATASET)
        evaluation_warnings = evaluate_via_metapype(dataset_node)
        if find_err_code(evaluation_warnings, EvaluationWarning.DATASET_PROJECT_MISSING, names.DATASET):
            add_to_evaluation('project_03', link)


# def check_other_entity(entity_node, filename):
#     link = url_for(PAGE_OTHER_ENTITY, filename=filename, node_id=entity_node.id)
#
#     validation_errors = validate_via_metapype(entity_node)
#     if find_min_unmet(validation_errors, names.OTHERENTITY, names.ENTITYNAME):
#         add_to_evaluation('other_entity_01', link)
#     if find_min_unmet(validation_errors, names.OTHERENTITY, names.ENTITYTYPE):
#         add_to_evaluation('other_entity_02', link)
#
#     evaluation_warnings = evaluate_via_metapype(entity_node)
#     if find_err_code(evaluation_warnings, EvaluationWarning.OTHER_ENTITY_DESCRIPTION_MISSING, names.OTHERENTITY):
#         add_to_evaluation('other_entity_03', link)
#
#
# def check_other_entities(eml_node, filename):
#     other_entity_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.OTHERENTITY])
#     for other_entity_node in other_entity_nodes:
#         check_image(other_entity_node, filename)


def check_image(eml_node, filename):
    link = url_for(PAGE_OTHER_ENTITY, filename=filename)

    evaluation_warnings = evaluate_via_motherpype(eml_node)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.IMAGE_NAME_MISSING, names.OTHERENTITY):
        add_to_evaluation('image_01', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.IMAGE_TYPE_MISSING, names.OTHERENTITY):
        add_to_evaluation('image_02', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.IMAGE_FORMAT_MISSING, names.OTHERENTITY):
        add_to_evaluation('image_03', link)
    # if find_err_code(evaluation_warnings, EvaluationWarningMp.IMAGE_DESCRIPTION_MISSING, names.OTHERENTITY):
    #     add_to_evaluation('image_04', link)


def check_immunohistochemistry(node, filename):
    link = url_for(PAGE_IHC, filename=filename)

    evaluation_warnings = evaluate_via_motherpype(node)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.IHC_TARGET_PROTEIN_MISSING, mdb_names.IHC):
        add_to_evaluation('ihc_01', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.IHC_PRIMARY_ANTIBODY_TARGET_SPECIES_MISSING, mdb_names.IHC):
        add_to_evaluation('ihc_02', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.IHC_PRIMARY_ANTIBODY_HOST_SPECIES_MISSING, mdb_names.IHC):
        add_to_evaluation('ihc_03', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.IHC_PRIMARY_ANTIBODY_DILUTION_MISSING, mdb_names.IHC):
        add_to_evaluation('ihc_04', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.IHC_PRIMARY_ANTIBODY_LOT_NUMBER_MISSING, mdb_names.IHC):
        add_to_evaluation('ihc_05', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.IHC_PRIMARY_ANTIBODY_CAT_NUMBER_MISSING, mdb_names.IHC):
        add_to_evaluation('ihc_06', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.IHC_PRIMARY_ANTIBODY_SOURCE_NAME_MISSING, mdb_names.IHC):
        add_to_evaluation('ihc_07', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.IHC_PRIMARY_ANTIBODY_SOURCE_CITY_MISSING, mdb_names.IHC):
        add_to_evaluation('ihc_08', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.IHC_PRIMARY_ANTIBODY_SOURCE_STATE_MISSING, mdb_names.IHC):
        add_to_evaluation('ihc_09', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.IHC_SECONDARY_ANTIBODY_TARGET_SPECIES_MISSING, mdb_names.IHC):
        add_to_evaluation('ihc_10', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.IHC_SECONDARY_ANTIBODY_HOST_SPECIES_MISSING, mdb_names.IHC):
        add_to_evaluation('ihc_11', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.IHC_SECONDARY_ANTIBODY_DILUTION_MISSING, mdb_names.IHC):
        add_to_evaluation('ihc_12', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.IHC_SECONDARY_ANTIBODY_LOT_NUMBER_MISSING, mdb_names.IHC):
        add_to_evaluation('ihc_13', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.IHC_SECONDARY_ANTIBODY_CAT_NUMBER_MISSING, mdb_names.IHC):
        add_to_evaluation('ihc_14', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.IHC_SECONDARY_ANTIBODY_SOURCE_NAME_MISSING, mdb_names.IHC):
        add_to_evaluation('ihc_15', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.IHC_SECONDARY_ANTIBODY_SOURCE_CITY_MISSING, mdb_names.IHC):
        add_to_evaluation('ihc_16', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.IHC_SECONDARY_ANTIBODY_SOURCE_STATE_MISSING, mdb_names.IHC):
        add_to_evaluation('ihc_17', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.IHC_PRIMARY_ANTIBODY_CLONALITY_ENUM, mdb_names.IHC):
        add_to_evaluation('ihc_18', link)


def check_donor(eml_node, filename):
    link = url_for(PAGE_DONOR, filename=filename)

    evaluation_warnings = evaluate_via_motherpype(eml_node)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_ID_MISSING, mdb_names.MOTHER):
        add_to_evaluation('donor_01', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_SEX_MISSING, mdb_names.MOTHER):
        add_to_evaluation('donor_02', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_LIFE_STAGE_MISSING, mdb_names.MOTHER):
        add_to_evaluation('donor_03', link)
    else:
        if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_LIFE_STAGE_ENUM, mdb_names.MOTHER):
            add_to_evaluation('donor_20', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_SPEC_SEQ_NUM_MISSING, mdb_names.MOTHER):
        add_to_evaluation('donor_04', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_SPEC_TISSUE_MISSING, mdb_names.MOTHER):
        add_to_evaluation('donor_05', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_OVARY_POSITION_MISSING, mdb_names.MOTHER):
        add_to_evaluation('donor_06', link)
    else:
        if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_OVARY_POSITION_ENUM, mdb_names.MOTHER):
            add_to_evaluation('donor_21', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_SLIDE_ID_MISSING, mdb_names.MOTHER):
        add_to_evaluation('donor_07', link)
    # if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_SEC_SEQ_NUM_MISSING, mdb_names.MOTHER):
    #     add_to_evaluation('donor_08', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_SEC_THICK_MISSING, mdb_names.MOTHER):
        add_to_evaluation('donor_09', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_SEC_THICK_UNITS_MISSING, mdb_names.MOTHER):
        add_to_evaluation('donor_10', link)
    else:
        if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_SEC_THICK_UNITS_ENUM, mdb_names.MOTHER):
            add_to_evaluation('donor_22', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_FIXATION_MISSING, mdb_names.MOTHER):
        add_to_evaluation('donor_11', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_STAIN_MISSING, mdb_names.MOTHER):
        add_to_evaluation('donor_12', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_MAGNIFICATION_MISSING, mdb_names.MOTHER):
        add_to_evaluation('donor_13', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_MICRO_MAKER_MISSING, mdb_names.MOTHER):
        add_to_evaluation('donor_14', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_MICRO_MODEL_MISSING, mdb_names.MOTHER):
        add_to_evaluation('donor_15', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_SEX_FEMALE, mdb_names.MOTHER):
        add_to_evaluation('donor_16', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_SPEC_TISSUE_OVARY, mdb_names.MOTHER):
        add_to_evaluation('donor_17', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_SEC_THICK_POSITIVE_INT, mdb_names.MOTHER):
        add_to_evaluation('donor_18', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_STAGE_OF_CYCLE_ENUM, mdb_names.MOTHER):
        add_to_evaluation('donor_19', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_CORPUS_LUTEUM_ENUM, mdb_names.MOTHER):
        add_to_evaluation('donor_23', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_FOLLICULAR_ENUM, mdb_names.MOTHER):
        add_to_evaluation('donor_24', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_LUTEAL_ENUM, mdb_names.MOTHER):
        add_to_evaluation('donor_25', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_SUDAN_STAIN_ENUM, mdb_names.MOTHER):
        add_to_evaluation('donor_26', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_YEARS_NON_NEGATIVE, mdb_names.MOTHER):
        add_to_evaluation('donor_27', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_DAYS_NON_NEGATIVE, mdb_names.MOTHER):
        add_to_evaluation('donor_28', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_DAY_OF_CYCLE_NON_NEGATIVE, mdb_names.MOTHER):
        add_to_evaluation('donor_29', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_SEC_SEQ_NUM_NON_NEGATIVE, mdb_names.MOTHER):
        add_to_evaluation('donor_30', link)
    if find_err_code(evaluation_warnings, EvaluationWarningMp.DONOR_SPEC_LOCATION_CHOICE, mdb_names.MOTHER):
        add_to_evaluation('donor_31', link)


def eval_entry_to_string(eval_entry):
    return f'Section:&nbsp;{eval_entry.section}<br>Item:&nbsp;{eval_entry.item}<br>Severity:&nbsp;{eval_entry.severity.name}<br>Type:&nbsp;{eval_entry.type.name}<br>Explanation:&nbsp;{eval_entry.explanation}<br><a href="{eval_entry.link}">Link</a>'


def to_string(evaluation):
    if evaluation and len(evaluation) > 0:
        s = ''
        for eval_entry in evaluation:
            s += eval_entry_to_string(eval_entry) + '<p/>'
        return s
    else:
        return "OK!"


def collect_entries(evaluation, section):
    return [entry for entry in evaluation if entry.section == section]


def format_entry(entry:Eval_Entry):
    output = '<tr>'
    output += f'<td class="eval_table" valign="top"><a href="{entry.link}">{entry.item}</a></td>'
    output += f'<td class="eval_table" valign="top">{entry.severity.name.title()}</td>'
    output += f'<td class="eval_table" valign="top">{entry.type.name.title()}</td>'
    output += f'<td class="eval_table" valign="top">{entry.explanation}</td>'
    output += '</tr>'
    return output


def format_output(evaluation):
    sections = ['Title', 'Image', 'Data Tables', 'Creators', 'Contacts', 'Associated Parties', 'Metadata Providers', 'Abstract',
                'Keywords', 'Intellectual Rights', 'Coverage', 'Geographic Coverage', 'Temporal Coverage',
                'Taxonomic Coverage', 'Maintenance', 'Methods', 'Project', 'Donor', 'Immunohistochemistry', 'Other Entities', 'Data Package ID']

    severities = [EvalSeverity.ERROR, EvalSeverity.WARNING, EvalSeverity.INFO]

    all_ok = True
    output = '<span style="font-family: Helvetica,Arial,sans-serif;">'
    for section in sections:
        entries = collect_entries(evaluation, section)
        if not entries:
            continue
        all_ok = False
        output += f'<h3>{section}</h3><table class="eval_table" width=100% style="padding: 10px;"><tr><th class="eval_table" align="left" width=20%>Item</th>' \
                  f'<th class="eval_table" align="left" width=8%>Severity</th><th class="eval_table" align="left" width=14%>Reason</th><th align="left" width=61%>Explanation</th></tr>'
        for severity in severities:
            for entry in entries:
                if entry.severity == severity:
                    output += format_entry(entry)
        output += '</table><br>'
    if all_ok:
        output += '<h4>Everything looks good!</h4>'
    output += '</span>'
    return output


def perform_evaluation(eml_node, filename):
    global evaluation
    evaluation = []

    check_dataset_title(eml_node, filename)
    # check_data_tables(eml_node, filename)
    check_creators(eml_node, filename)
    check_contacts(eml_node, filename)
    check_associated_parties(eml_node, filename)
    check_metadata_providers(eml_node, filename)
    check_dataset_abstract(eml_node, filename)
    check_keywords(eml_node, filename)
    # check_intellectual_rights(eml_node, filename)
    check_coverage(eml_node, filename)
    # check_geographic_coverage(eml_node, filename)
    check_maintenance(eml_node, filename)
    check_method_steps(eml_node, filename)
    check_project(eml_node, filename)
    # check_other_entities(eml_node, filename)
    check_image(eml_node, filename)
    check_immunohistochemistry(eml_node, filename)
    check_donor(eml_node, filename)
    # check_data_package_id(eml_node, filename)
    
    return evaluation


def check_metadata_status(eml_node, filename):
    evaluations = perform_evaluation(eml_node, filename)
    errors = 0
    warnings = 0
    for entry in evaluations:
        _, _, severity, _, _, _ = entry
        if severity == EvalSeverity.ERROR:
            errors += 1
        if severity == EvalSeverity.WARNING:
            warnings += 1
    return errors, warnings


def check_eml(eml_node, filename):
    evaluations = perform_evaluation(eml_node, filename)
    return format_output(evaluations)


def validate_via_metapype(node):
    errs = []
    try:
        validate.tree(node, errs)
    except Exception as e:
        print(f'validate_via_metapype: node={node.name} exception={e}')
    return errs


def evaluate_via_metapype(node):
    eval = []
    try:
        evaluate.tree(node, eval)
    except Exception as e:
        print(f'evaluate_via_metapype: node={node.name} exception={e}')
    return eval


def evaluate_via_motherpype(node):
    # allows for new evaluation scripts to be added for MOTHER
    eval = []
    # try:
    evaluate_mp.tree(node, eval)
    # except Exception as e:
    #     print(f'evaluate_via_motherpype: node={node.name} exception={e}')
    return eval





