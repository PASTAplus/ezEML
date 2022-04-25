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
from enum import Enum
import hashlib
import os
import pickle
import time

import daiquiri
from flask import (
    Blueprint, Flask, url_for, session, current_app
)
from flask_login import (
    current_user
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

app = Flask(__name__)
home = Blueprint('home', __name__, template_folder='templates')
logger = daiquiri.getLogger('check_metadata: ' + __name__)


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
        vals = session[f'__eval__{id}']
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


def check_dataset_title(eml_node, doc_name, validation_errs=None):
    link = url_for(PAGE_TITLE, filename=doc_name)
    dataset_node = eml_node.find_child(names.DATASET)
    if validation_errs is None:
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
    if package_id:
        try:
            scope, identifier, revision = package_id.split('.')
            if scope not in scopes:
                raise ValueError
            identifier = int(identifier)
            revision = int(revision)
        except ValueError:
            return False
    return True


def check_data_package_id(eml_node, doc_name, validation_errs=None):
    link = url_for(PAGE_DATA_PACKAGE_ID, filename=doc_name)
    if validation_errs is None:
        validation_errs = validate_via_metapype(eml_node)
    if find_missing_attribute(validation_errs, 'eml', 'packageId'):
        add_to_evaluation('data_package_id_01', link)
    else:
        # check if data package ID has correct form for EDI data repository
        data_package_id = eml_node.attribute_value("packageId")
        if not check_id_for_EDI(data_package_id):
            add_to_evaluation('data_package_id_02', link)


def check_responsible_party(rp_node:Node, section:str=None, item:str=None,
                            page:str=None, doc_name:str=None, node_id:str=None,
                            related_project_node_id:str=None):
    if not related_project_node_id:
        link = url_for(page, filename=doc_name, node_id=node_id)
    else:
        link = url_for(page, filename=doc_name, node_id=node_id, project_node_id=related_project_node_id)
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


def check_creators(eml_node, doc_name, validation_errs=None):
    link = url_for(PAGE_CREATOR_SELECT, filename=doc_name)
    dataset_node = eml_node.find_child(names.DATASET)
    if validation_errs is None:
        validation_errs = validate_via_metapype(dataset_node)

    if find_min_unmet(validation_errs, names.DATASET, names.CREATOR):
        add_to_evaluation('creators_01', link)
    else:
        creator_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.CREATOR])
        for creator_node in creator_nodes:
            check_responsible_party(creator_node, 'Creators', 'Creator', PAGE_CREATOR, doc_name, creator_node.id)


def check_metadata_providers(eml_node, doc_name):
    link = url_for(PAGE_METADATA_PROVIDER_SELECT, filename=doc_name)
    metadata_provider_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.METADATAPROVIDER])
    if metadata_provider_nodes and len(metadata_provider_nodes) > 0:
        for metadata_provider_node in metadata_provider_nodes:
            check_responsible_party(metadata_provider_node, 'Metadata Providers', 'Metadata Provider',
                                    PAGE_METADATA_PROVIDER, doc_name, metadata_provider_node.id)


def check_associated_parties(eml_node, doc_name):
    link = url_for(PAGE_ASSOCIATED_PARTY_SELECT, filename=doc_name)
    associated_party_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.ASSOCIATEDPARTY])
    if associated_party_nodes and len(associated_party_nodes) > 0:
        for associated_party_node in associated_party_nodes:
            check_responsible_party(associated_party_node, 'Associated Parties', 'Associated Party',
                                    PAGE_ASSOCIATED_PARTY, doc_name, associated_party_node.id)


def check_dataset_abstract(eml_node, doc_name, evaluation_warnings=None):
    link = url_for(PAGE_ABSTRACT, filename=doc_name)
    dataset_node = eml_node.find_child(names.DATASET)
    if evaluation_warnings is None:
        evaluation_warnings = evaluate_via_metapype(dataset_node)

    if find_err_code(evaluation_warnings, EvaluationWarning.DATASET_ABSTRACT_MISSING, names.DATASET):
        add_to_evaluation('abstract_01', link)
        return

    if find_err_code(evaluation_warnings, EvaluationWarning.DATASET_ABSTRACT_TOO_SHORT, names.DATASET):
        add_to_evaluation('abstract_02', link)
        return


def check_keywords(eml_node, doc_name, evaluation_warnings=None):
    link = url_for(PAGE_KEYWORD_SELECT, filename=doc_name)
    dataset_node = eml_node.find_child(names.DATASET)
    if evaluation_warnings is None:
        evaluation_warnings = evaluate_via_metapype(dataset_node)

    if find_err_code(evaluation_warnings, EvaluationWarning.KEYWORDS_MISSING, names.DATASET):
        add_to_evaluation('keywords_01', link)
        return

    if find_err_code(evaluation_warnings, EvaluationWarning.KEYWORDS_INSUFFICIENT, names.DATASET):
        add_to_evaluation('keywords_02', link)
        return


def check_intellectual_rights(eml_node, doc_name, evaluation_warnings=None):
    link = url_for(PAGE_INTELLECTUAL_RIGHTS, filename=doc_name)
    dataset_node = eml_node.find_child(names.DATASET)
    if evaluation_warnings is None:
        evaluation_warnings = evaluate_via_metapype(dataset_node)

    if find_err_code(evaluation_warnings, EvaluationWarning.INTELLECTUAL_RIGHTS_MISSING, names.DATASET):
        # We need to check this case. Metapype currently thinks it's an error if intellectualRights node has no
        #  content. It may, however, have content in children. This is a case that will be ironed out when all the
        #  dust settles regarding handling of TextType nodes.
        intellectual_rights_node = eml_node.find_descendant(names.INTELLECTUALRIGHTS)
        if intellectual_rights_node and intellectual_rights_node.children:
            return
        add_to_evaluation('intellectual_rights_01', link)
        return


def check_taxonomic_coverage(node, doc_name):

    link = url_for(PAGE_TAXONOMIC_COVERAGE, filename=doc_name, node_id=node.id)

    validation_errs = validate_via_metapype(node)
    if find_content_empty(validation_errs, names.TAXONRANKNAME):
        add_to_evaluation('taxonomic_coverage_01', link)
    if find_content_empty(validation_errs, names.TAXONRANKVALUE):
        add_to_evaluation('taxonomic_coverage_02', link)


def check_coverage(eml_node, doc_name, evaluation_warnings=None):
    dataset_node = eml_node.find_child(names.DATASET)

    link = url_for(PAGE_GEOGRAPHIC_COVERAGE_SELECT, filename=doc_name)

    if evaluation_warnings is None:
        evaluation_warnings = evaluate_via_metapype(dataset_node)

    if find_err_code(evaluation_warnings, EvaluationWarning.DATASET_COVERAGE_MISSING, names.DATASET):
        add_to_evaluation('coverage_01', link)

    if not metapype_client.was_imported_from_xml(eml_node):
        taxonomic_classification_nodes = []
        dataset_node.find_all_descendants(names.TAXONOMICCOVERAGE, taxonomic_classification_nodes)
        for taxonomic_classification_node in taxonomic_classification_nodes:
            check_taxonomic_coverage(taxonomic_classification_node, doc_name)


def check_geographic_coverage(eml_node, doc_name):
    link = url_for(PAGE_GEOGRAPHIC_COVERAGE_SELECT, filename=doc_name)
    geographic_coverage_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.COVERAGE, names.GEOGRAPHICCOVERAGE])
    for geographic_coverage_node in geographic_coverage_nodes:
        link = url_for(PAGE_GEOGRAPHIC_COVERAGE, filename=doc_name, node_id=geographic_coverage_node.id)
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
    # Formerly, Categorical variables were nominal. But now that we're importing externally created XML
    #  files, they may be ordinal.
    nominal_or_ordinal_node = mscale_node.find_child(names.NOMINAL)
    if not nominal_or_ordinal_node:
        nominal_or_ordinal_node = mscale_node.find_child(names.ORDINAL)
    if nominal_or_ordinal_node:
        enumerated_domain_node = nominal_or_ordinal_node.find_single_node_by_path([names.NONNUMERICDOMAIN, names.ENUMERATEDDOMAIN])
        if enumerated_domain_node:
            return metapype_client.VariableType.CATEGORICAL
        text_domain_node = nominal_or_ordinal_node.find_single_node_by_path([names.NONNUMERICDOMAIN, names.TEXTDOMAIN])
        if text_domain_node:
            return metapype_client.VariableType.TEXT

    # Formerly, Numerical variables were ratio. But now that we're importing externally created XML
    #  files, they may be interval.
    ratio_or_interval_node = mscale_node.find_child(names.RATIO)
    if not ratio_or_interval_node:
        ratio_or_interval_node = mscale_node.find_child(names.INTERVAL)
    if ratio_or_interval_node:
        return metapype_client.VariableType.NUMERICAL

    datetime_node = mscale_node.find_child(names.DATETIME)
    if datetime_node:
        return metapype_client.VariableType.DATETIME
    return None


def generate_code_definition_errs(eml_node, doc_name, err_code, errs_found):
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
        link = url_for(PAGE_CODE_DEFINITION, filename=doc_name, dt_node_id=data_table_node.id, att_node_id=attribute_node.id,
                       nom_ord_node_id=nominal_node.id, node_id=code_definition_node.id, mscale=mscale)
        add_to_evaluation(err_code, link)


def check_attribute(eml_node, doc_name, data_table_node:Node, attrib_node:Node):
    attr_type = get_attribute_type(attrib_node)
    mscale = None
    page = None
    if attr_type == metapype_client.VariableType.CATEGORICAL:
        page = PAGE_ATTRIBUTE_CATEGORICAL
        mscale = metapype_client.VariableType.CATEGORICAL.name
        data_table_name = None
        if data_table_node:
            data_table_name = data_table_node.find_child(names.ENTITYNAME).content
        attrib_name = None
        if attrib_node:
            attrib_name_node = attrib_node.find_child(names.ATTRIBUTENAME)
            if attrib_name_node:
                attrib_name = attrib_name_node.content
        # log_info(f"CATEGORICAL... filename={filename}  data_table={data_table_name}  attr_name={attrib_name}  attr_type={attr_type}")
    elif attr_type == metapype_client.VariableType.NUMERICAL:
        page = PAGE_ATTRIBUTE_NUMERICAL
        mscale = metapype_client.VariableType.NUMERICAL.name
    elif attr_type == metapype_client.VariableType.TEXT:
        page = PAGE_ATTRIBUTE_TEXT
        mscale = metapype_client.VariableType.TEXT.name
    elif attr_type == metapype_client.VariableType.DATETIME:
        page = PAGE_ATTRIBUTE_DATETIME
        mscale = metapype_client.VariableType.DATETIME.name
    # This section is temporary code to track down a bug
    if not page:
        data_table_name = None
        if data_table_node:
            data_table_name = data_table_node.find_child(names.ENTITYNAME).content
        attrib_name = None
        if attrib_node:
            attrib_name_node = attrib_node.find_child(names.ATTRIBUTENAME)
            if attrib_name_node:
                attrib_name = attrib_name_node.content
        log_error(f"page not initialized... filename={doc_name}  data_table={data_table_name}  attr_name={attrib_name}  attr_type={attr_type}")
        return
    link = url_for(page, filename=doc_name, dt_node_id=data_table_node.id, node_id=attrib_node.id, mscale=mscale)

    validation_errs = validate_via_metapype(attrib_node)
    if find_content_empty(validation_errs, names.ATTRIBUTEDEFINITION):
        add_to_evaluation('attributes_01', link)
    if find_min_unmet(validation_errs, names.MISSINGVALUECODE, names.CODEEXPLANATION):
        add_to_evaluation('attributes_07', link)

    # Categorical
    if attr_type == metapype_client.VariableType.CATEGORICAL:
        if find_min_unmet_for_choice(validation_errs, names.ENUMERATEDDOMAIN):
            add_to_evaluation('attributes_04', link)
        found = find_content_empty(validation_errs, names.CODE)
        if found:
            generate_code_definition_errs(eml_node, doc_name, 'attributes_05', found)
        found = find_content_empty(validation_errs, names.DEFINITION)
        if found:
            generate_code_definition_errs(eml_node, doc_name, 'attributes_06', found)

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
        authentication_node = data_table_node.find_descendant(names.AUTHENTICATION)
        if authentication_node:
            found_md5_hash = authentication_node.content
            if found_md5_hash != computed_md5_hash:
                add_to_evaluation('data_table_06', link)
    except FileNotFoundError:
        # If there is a URL in Online Distribution node, we don't treat a missing CSV file as an error
        url_node = data_table_node.find_single_node_by_path([names.PHYSICAL,
                                                             names.DISTRIBUTION,
                                                             names.ONLINE,
                                                             names.URL])
        if not url_node or not url_node.content:
            add_to_evaluation('data_table_07', link)
        else:
            return


def check_data_table(eml_node, doc_name, data_table_node:Node):
    link = url_for(PAGE_DATA_TABLE, filename=doc_name, dt_node_id=data_table_node.id)
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
            check_attribute(eml_node, doc_name, data_table_node, attribute_node)


def check_data_tables(eml_node, doc_name, evaluation_warnings=None):
    link = url_for(PAGE_DATA_TABLE_SELECT, filename=doc_name)
    dataset_node = eml_node.find_child(names.DATASET)
    if evaluation_warnings is None:
        evaluation_warnings = evaluate_via_metapype(dataset_node)
    if find_err_code(evaluation_warnings, EvaluationWarning.DATATABLE_MISSING, names.DATASET):
        add_to_evaluation('data_table_05', link)

    data_table_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.DATATABLE])
    for data_table_node in data_table_nodes:
        check_data_table(eml_node, doc_name, data_table_node)


def check_maintenance(eml_node, doc_name, evaluation_warnings=None):
    link = url_for(PAGE_MAINTENANCE, filename=doc_name)
    dataset_node = eml_node.find_child(names.DATASET)
    if evaluation_warnings is None:
        evaluation_warnings = evaluate_via_metapype(dataset_node)
    if find_err_code(evaluation_warnings, EvaluationWarning.MAINTENANCE_DESCRIPTION_MISSING, names.DESCRIPTION):
        add_to_evaluation('maintenance_01', link)


def check_contacts(eml_node, doc_name, validation_errs=None):
    link = url_for(PAGE_CONTACT_SELECT, filename=doc_name)
    dataset_node = eml_node.find_child(names.DATASET)
    if validation_errs is None:
        validation_errs = validate_via_metapype(dataset_node)
    if find_min_unmet(validation_errs, names.DATASET, names.CONTACT):
        add_to_evaluation('contacts_01', link=link)
    contact_nodes = eml_node.find_all_nodes_by_path([
        names.DATASET,
        names.CONTACT
    ])
    for contact_node in contact_nodes:
        check_responsible_party(contact_node, 'Contacts', 'Contact', PAGE_CONTACT,
                                doc_name, contact_node.id)


def check_method_step(method_step_node, doc_name, node_id):
    link = url_for(PAGE_METHOD_STEP, filename=doc_name, node_id=node_id)
    evaluation_warnings = evaluate_via_metapype(method_step_node)
    if find_err_code(evaluation_warnings, EvaluationWarning.METHOD_STEP_DESCRIPTION_MISSING, names.DESCRIPTION):
        add_to_evaluation('methods_02', link)


def check_method_steps(eml_node, doc_name, evaluation_warnings=None, validation_errs=None):
    link = url_for(PAGE_METHOD_STEP_SELECT, filename=doc_name)
    dataset_node = eml_node.find_child(names.DATASET)
    if evaluation_warnings is None:
        evaluation_warnings = evaluate_via_metapype(dataset_node)
    if find_err_code(evaluation_warnings, EvaluationWarning.DATASET_METHOD_STEPS_MISSING, names.DATASET):
        add_to_evaluation('methods_01', link)
    else:
        if validation_errs is None:
            validation_errs = validate_via_metapype(dataset_node)
        if find_min_unmet(validation_errs, names.METHODS, names.METHODSTEP):
            add_to_evaluation('methods_03', link)

    method_step_nodes = eml_node.find_all_nodes_by_path([
        names.DATASET,
        names.METHODS,
        names.METHODSTEP
    ])
    for method_step_node in method_step_nodes:
        check_method_step(method_step_node, doc_name, method_step_node.id)


def check_project_award(award_node, doc_name, related_project_id=None):
    if not related_project_id:
        link = url_for(PAGE_FUNDING_AWARD, filename=doc_name, node_id=award_node.id)
    else:
        link = url_for(PAGE_FUNDING_AWARD, filename=doc_name, node_id=award_node.id, project_node_id=related_project_id)
    validation_errors = validate_via_metapype(award_node)
    if find_min_unmet(validation_errors, names.AWARD, names.FUNDERNAME) or \
            find_content_empty(validation_errors, names.FUNDERNAME):
        add_to_evaluation('project_04', link)
    if find_min_unmet(validation_errors, names.AWARD, names.TITLE) or \
            find_content_empty(validation_errors, names.TITLE):
        add_to_evaluation('project_05', link)


def check_project_node(project_node, doc_name, related_project_id=None):
    if not related_project_id:
        link = url_for(PAGE_PROJECT, filename=doc_name)
    else:
        link = url_for(PAGE_PROJECT, filename=doc_name, node_id=related_project_id)
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
                                PAGE_PROJECT_PERSONNEL, doc_name, project_personnel_node.id,
                                related_project_id)

    project_award_nodes = project_node.find_all_children(names.AWARD)
    for project_award_node in project_award_nodes:
        check_project_award(project_award_node, doc_name, related_project_id)

    related_project_nodes = project_node.find_all_children(names.RELATED_PROJECT)
    for related_project_node in related_project_nodes:
        check_project_node(related_project_node, doc_name, related_project_node.id)


def check_project(eml_node, doc_name, evaluation_warnings=None):
    link = url_for(PAGE_PROJECT, filename=doc_name)
    project_node = eml_node.find_single_node_by_path([names.DATASET, names.PROJECT])
    if project_node:
        check_project_node(project_node, doc_name)
    else:
        dataset_node = eml_node.find_child(names.DATASET)
        if evaluation_warnings is None:
            evaluation_warnings = evaluate_via_metapype(dataset_node)
        if find_err_code(evaluation_warnings, EvaluationWarning.DATASET_PROJECT_MISSING, names.DATASET):
            add_to_evaluation('project_03', link)


def check_other_entity(entity_node, doc_name):
    link = url_for(PAGE_OTHER_ENTITY, filename=doc_name, node_id=entity_node.id)

    validation_errors = validate_via_metapype(entity_node)
    if find_min_unmet(validation_errors, names.OTHERENTITY, names.ENTITYNAME):
        add_to_evaluation('other_entity_01', link)
    if find_min_unmet(validation_errors, names.OTHERENTITY, names.ENTITYTYPE):
        add_to_evaluation('other_entity_02', link)

    evaluation_warnings = evaluate_via_metapype(entity_node)
    if find_err_code(evaluation_warnings, EvaluationWarning.OTHER_ENTITY_DESCRIPTION_MISSING, names.OTHERENTITY):
        add_to_evaluation('other_entity_03', link)


def check_other_entities(eml_node, doc_name):
    other_entity_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.OTHERENTITY])
    for other_entity_node in other_entity_nodes:
        check_other_entity(other_entity_node, doc_name)


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
    sections = ['Title', 'Data Tables', 'Creators', 'Contacts', 'Associated Parties', 'Metadata Providers', 'Abstract',
                'Keywords', 'Intellectual Rights', 'Coverage', 'Geographic Coverage', 'Temporal Coverage',
                'Taxonomic Coverage', 'Maintenance', 'Methods', 'Project', 'Other Entities', 'Data Package ID']

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


def check_evaluation_memo(json_filename, eml_node):
    # We save validation results in a pickle file and only recompute them when the json file's content has changed.
    eval_filename = json_filename.replace('.json', '_eval.pkl')
    try:
        old_md5, validation_errs, evaluation_warnings = pickle.load(open(eval_filename, 'rb'))
        with open(json_filename, 'rt') as json_file:
            json = json_file.read()
        new_md5 = hashlib.md5(json.encode('utf-8')).hexdigest()
        if new_md5 == old_md5:
            return new_md5, validation_errs, evaluation_warnings
        else:
            return new_md5, None, None
    except:
        return None, None, None


def memoize_evaluation(json_filename, eml_node, md5, validation_errs, evaluation_warnings):
    eval_filename = json_filename.replace('.json', '_eval.pkl')
    try:
        if md5 == None:
            with open(json_filename, 'rt') as json_file:
                json = json_file.read()
            md5 = hashlib.md5(json.encode('utf-8')).hexdigest()
        with open(eval_filename, 'wb') as f:
            pickle.dump((md5, validation_errs, evaluation_warnings), f)
    except:
        if os.path.exists(eval_filename):
            os.remove(eval_filename)


def perform_evaluation(eml_node, doc_name):
    global evaluation
    evaluation = []
    # print('\nEntering perform_evaluation')
    start = time.perf_counter()

    user_folder = user_data.get_user_folder_name()
    json_filename = f'{user_folder}/{doc_name}.json'

    md5, validation_errs, evaluation_warnings = check_evaluation_memo(json_filename, eml_node)
    need_to_memoize = False
    if validation_errs == None or evaluation_warnings == None:
        # print('memoize')
        need_to_memoize = True
        validation_errs = validate_via_metapype(eml_node)
        evaluation_warnings = evaluate_via_metapype(eml_node)

    check_dataset_title(eml_node, doc_name, validation_errs)
    check_data_tables(eml_node, doc_name, evaluation_warnings)
    check_creators(eml_node, doc_name, validation_errs)
    check_contacts(eml_node, doc_name, validation_errs)
    check_associated_parties(eml_node, doc_name)
    check_metadata_providers(eml_node, doc_name)
    check_dataset_abstract(eml_node, doc_name, evaluation_warnings)
    check_keywords(eml_node, doc_name, evaluation_warnings)
    check_intellectual_rights(eml_node, doc_name, evaluation_warnings)
    check_coverage(eml_node, doc_name, evaluation_warnings)
    check_geographic_coverage(eml_node, doc_name)
    check_maintenance(eml_node, doc_name, evaluation_warnings)
    check_method_steps(eml_node, doc_name, evaluation_warnings, validation_errs)
    check_project(eml_node, doc_name)
    check_other_entities(eml_node, doc_name)
    check_data_package_id(eml_node, doc_name, validation_errs)

    if need_to_memoize:
        memoize_evaluation(json_filename, eml_node, md5, validation_errs, evaluation_warnings)

    end = time.perf_counter()
    # print(f"Leaving perform_evaluation: {end - start}")

    return evaluation


def check_metadata_status(eml_node, doc_name):
    evaluations = perform_evaluation(eml_node, doc_name)
    errors = 0
    warnings = 0
    for entry in evaluations:
        _, _, severity, _, _, _ = entry
        if severity == EvalSeverity.ERROR:
            errors += 1
        if severity == EvalSeverity.WARNING:
            warnings += 1
    return errors, warnings


def check_eml(eml_node, doc_name):
    evaluations = perform_evaluation(eml_node, doc_name)
    return format_output(evaluations)


def validate_via_metapype(node):
    errs = []
    try:
        start = time.perf_counter()
        validate.tree(node, errs)
        end = time.perf_counter()
        elapsed = end - start
        # if elapsed > 0.05:
        #     print(f"validate: {node.name}  {elapsed}")
    except Exception as e:
        print(f'validate_via_metapype: node={node.name} exception={e}')
    return errs


def evaluate_via_metapype(node):
    eval = []
    try:
        start = time.perf_counter()
        evaluate.tree(node, eval)
        end = time.perf_counter()
        elapsed = end - start
        # if elapsed > 0.05:
        #     print(f"evaluate: {node.name}  {elapsed}")
    except Exception as e:
        print(f'evaluate_via_metapype: node={node.name} exception={e}')
    return eval





