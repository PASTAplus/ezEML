"""
Evaluate the metadata document and return a list of errors and warnings.

This uses the contents of 'webapp/static/evaluate.csv', which has already been loaded into current_app.config.
See load_eval_entries() in webapp.home.views.py. The loaded items in current_app.config are named via
current_app.config[f'__eval__{id}'] where id is the id of the entry in the csv file.

Memoizing: When the evaluation is complete, the list of errors and warnings is pickled and saved in a file. If we're
evaluating foo.JSON, the evaluation is saved in foo._eval.pkl. The pickle file also contains the MD5 hash of the JSON
file, so we can tell if the metadata has changed since the last evaluation. If not, we can just load the pickle file and
return the list of errors and warnings.
"""


from datetime import datetime
from enum import Enum
import hashlib
import os
import pickle
from urllib.parse import urlparse, urlunparse, parse_qs
from dataclasses import dataclass

from flask import (
    Blueprint, Flask, url_for, request, session, current_app, g
)

import webapp.home.utils.load_and_save
from webapp.home.home_utils import log_error, log_info
from webapp.home.standard_units import deprecated_in_favor_of
from metapype.eml import names
import metapype.eml.validate as validate
from metapype.eml.validation_errors import ValidationError
import metapype.eml.evaluate as evaluate
from metapype.eml.evaluation_warnings import EvaluationWarning
from metapype.model.node import Node
from webapp.pages import *
from webapp.home.exceptions import EMLFileNotFound
import webapp.auth.user_data as user_data
from webapp.home.check_data_table_contents import check_date_time_attribute
import webapp.home.views as views

app = Flask(__name__)
home = Blueprint('home', __name__, template_folder='templates')


class EvalSeverity(Enum):
    ERROR = 1
    WARNING = 2
    INFO = 3
    OK = 4


class EvalType(Enum):
    REQUIRED = 1
    RECOMMENDED = 2
    BEST_PRACTICE = 3
    OPTIONAL = 4


@dataclass
class EvalEntry:
    section: str
    item: str
    severity: EvalSeverity
    type: EvalType
    explanation: str
    data_table_name: str = None
    link: str = None
    ui_element_id: str = None
    node: Node = None

severities = [EvalSeverity.ERROR, EvalSeverity.WARNING, EvalSeverity.INFO]


def annotate_link(eval_entry, id=None):
    parsed = urlparse(eval_entry.link)
    level = 'error' if eval_entry.severity == EvalSeverity.ERROR else 'warning'
    if id == 'attributes_11':
        # If the error is a missing variable type, the ui_element_id needs to match the particular missing case
        # Get the node ID
        node_id = parse_qs(parsed.query).get('node_id')
        if isinstance(node_id, list) and node_id:
            node_id = node_id[0]
        if node_id:
            eval_entry.ui_element_id = f"{eval_entry.ui_element_id}_{node_id}"
    ui_element_id = f"{eval_entry.ui_element_id}|{level}"
    if not parsed.query:
        eval_entry.link = urlunparse(parsed._replace(query=f'ui_element_id={ui_element_id}'))
    else:
        # Append to existing query string
        existing_query = parsed.query
        if 'ui_element_id=' in existing_query or not eval_entry.ui_element_id:
            return
        new_query = f"{existing_query}&ui_element_id={ui_element_id}"
        eval_entry.link = urlunparse(parsed._replace(query=new_query))


def add_to_evaluation(id, link=None, section=None, item=None, data_table_name=None, node=None, replace_value=None, replace_with=None):
    """ Add an EvalEntry for an error or warning to the evaluation list that is being built up. """

    def get_eval_entry(id, link=None, section=None, item=None, data_table_name=None, node=None, replace_value=None, replace_with=None):
        """ Return the EvalEntry object for the given id. """
        try:
            vals = current_app.config.get(f'__eval__{id}')
            if section:
                vals[0] = section
            if item:
                vals[1] = item
            ui_element_id = vals[6] if 6 < len(vals) else None
            node = vals[7] if 7 < len(vals) else None
            explanation = vals[4]
            if replace_value:
                explanation = explanation.replace('"{}"', replace_value, 1)
                if replace_with:
                    explanation = explanation.replace('"{}"', replace_with, 1)
            return EvalEntry(section=vals[0], item=vals[1], severity=EvalSeverity[vals[2]], type=EvalType[vals[3]],
                             explanation=explanation, data_table_name=data_table_name, link=link,
                             ui_element_id=ui_element_id, node=node)
        except Exception as exc:
            return None

    entry = get_eval_entry(id, link, section, item, data_table_name, node, replace_value, replace_with)
    annotate_link(entry, id)
    if entry:
        evaluation.append(entry)


def find_min_unmet(errs, node_name, child_name, data_source_node_id=None):
    """
    Return True if a MIN_OCCURRENCE_UNMET error is found for the given node and child.

    E.g., if node_name is names.DATASET and child_name is names.CREATOR, then this will return True if no
    creator has been defined for the dataset.
    """
    for err_code, msg, node, *args in errs:
        if err_code == ValidationError.MIN_OCCURRENCE_UNMET:
            err_cause, min = args
            if node.name == node_name and err_cause ==  child_name:
                if data_source_node_id is None:
                    return True
                elif data_source_node_id is not None and \
                        (node.id == data_source_node_id or node.parent.id == data_source_node_id):
                        return True
    return False


def find_min_unmet_for_choice(errs, node_name):
    """
    Return True if a MIN_CHOICE_UNMET error is found for the given node.

    E.g., if node_name is names.UNIT, then this will return True if no names.STANDARDUNIT or names.CUSTOMUNIT has been
    has been defined for the unit.
    """
    for err_code, msg, node, *args in errs:
        if err_code == ValidationError.MIN_CHOICE_UNMET and node.name == node_name:
            return True
    return False


def find_content_empty(errs, node_name, data_source_node_id=None):
    """
    Return True if a CONTENT_EXPECTED_NONEMPTY error is found for the given node.

    E.g., if node_name is names.TITLE, then this will return True if the title is empty.
    """
    found = []
    for err in errs:
        err_code, _, node, *_ = err
        if err_code == ValidationError.CONTENT_EXPECTED_NONEMPTY and node.name == node_name:
            if data_source_node_id is None:
                found.append(err)
            elif data_source_node_id is not None and \
                    (node.id == data_source_node_id or node.parent.id == data_source_node_id):
                    found.append(err)
    return found


def find_content_enum(errs, node_name):
    """
    Return True if a CONTENT_EXPECTED_ENUM error is found for the given node.

    E.g., if node_name is names.ALTITUDEUNITS, then this will return True if the altitude units are not one of the
    allowed values.
    """
    found = []
    for err in errs:
        err_code, _, node, *_ = err
        if err_code == ValidationError.CONTENT_EXPECTED_ENUM and node.name == node_name:
            found.append(err)
    return found


def find_err_code(errs, err_code_to_find, node_name, data_source_node_id=None, parent_name=None):
    """
    Return True if a specified error/warning is found for the given node.

    E.g., if node_name is names.DATASET and err_code_to_find is EvaluationWarning.DATASET_ABSTRACT_TOO_SHORT, then this
    will return True if the dataset abstract is too short, as determined by metapype.eml.evaluate.py.
    """
    found = []
    for err in errs:
        err_code, _, node, *_ = err
        if err_code == err_code_to_find and node.name == node_name:
            if parent_name is not None and node.parent.name != parent_name:
                continue
            if data_source_node_id is None:
                found.append(err)
            elif data_source_node_id is not None and \
                    (node.id == data_source_node_id or node.parent.id == data_source_node_id):
                    found.append(err)
    return found


def find_missing_attribute(errs, node_name, attribute_name):
    """
    Return True if an ATTRIBUTE_REQUIRED error is found for the given node and attribute.
    "Attribute" here means an attribute in the XML element sense, not an attribute in the sense of a DataTable column.
    """
    errs_found = find_err_code(errs, ValidationError.ATTRIBUTE_REQUIRED, node_name)
    for err in errs_found:
        errcode, msg, node, attribute = err
        if attribute == attribute_name:
            return err
    return None


def eval_code(ec, is_data_source):
    """
    We need to distinguish between evaluation codes for data sources and evaluation codes for the entire document.
    This is because the data source errors/warnings are displayed separately.
    """
    if is_data_source:
        ec = f'{ec}_ds'
    return ec


def check_dataset_title(eml_node, doc_name, validation_errs=None, evaluation_warnings=None, is_data_source=False):
    """
    Check if the dataset title is missing, empty, or too short.

    This can be called for either the entire document or for a data source.
    """
    if not is_data_source:
        data_source_node = None
        link = url_for(PAGE_TITLE, filename=doc_name)
    else:
        data_source_node = eml_node
        ms_node = eml_node.parent
        link = url_for(PAGE_DATA_SOURCE,
                       filename=doc_name,
                       ms_node_id=ms_node.id,
                       data_source_node_id=data_source_node.id)
    dataset_node = eml_node.find_child(names.DATASET)
    if validation_errs is None:
        validation_errs = validate_via_metapype(dataset_node)
    # Is title node missing?
    if find_min_unmet(validation_errs, names.DATASET, names.TITLE,
                      data_source_node_id=data_source_node.id if is_data_source else None):
        add_to_evaluation(eval_code('title_01', is_data_source), link)
        return
    # Is title node content empty?
    if not is_data_source:
        title_node = eml_node.find_single_node_by_path([names.DATASET, names.TITLE])
    else:
        title_node = data_source_node.find_child(names.TITLE)
    if title_node:
        validation_errs = validate_via_metapype(title_node)
    if not title_node or find_content_empty(validation_errs, names.TITLE,
                                            data_source_node_id=data_source_node.id if is_data_source else None):
        add_to_evaluation(eval_code('title_01', is_data_source), link)
        return

    # Is the title too short? This applies only to the dataset title, not the data source title, since the data source
    # title is not something we can change.
    if not is_data_source:
        if find_err_code(evaluation_warnings, EvaluationWarning.TITLE_TOO_SHORT, names.TITLE, parent_name=names.DATASET):
            add_to_evaluation(eval_code('title_02', is_data_source), link)


def check_data_package_id(eml_node, doc_name, validation_errs=None):
    """
    Check whether the package_id is missing or not in the correct format for EDI.
    """

    def check_id_for_EDI(package_id):
        """ Check whether the package_id is in the correct format for EDI. """
        scopes = [
            'cos-spu',
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
                            related_project_node_id:str=None, is_data_source=False,
                            data_source_node_id:str=None):
    """
    Check a responsible party (creator, contact, etc.) for missing required/recommended elements.
    """
    if related_project_node_id:
        link = url_for(page, filename=doc_name, node_id=node_id, project_node_id=related_project_node_id)
    elif is_data_source:
        data_source_node = Node.get_node_instance(data_source_node_id)
        method_step_node = data_source_node.parent
        link = url_for('rp.data_source_personnel', filename=doc_name, rp_type=rp_node.name, rp_node_id=node_id,
                       method_step_node_id=method_step_node.id, data_source_node_id=data_source_node_id)
    else:
        link = url_for(page, filename=doc_name, node_id=node_id)

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

    # ORCID ID is recommended
    if find_err_code(evaluation_warnings, EvaluationWarning.ORCID_ID_MISSING, rp_node.name):
        # Make sure this is an individual, not an organization or position
        if rp_node.find_child(names.INDIVIDUALNAME):
            add_to_evaluation('responsible_party_02', link, section, item)

    # Email is recommended
    if find_err_code(evaluation_warnings, EvaluationWarning.EMAIL_MISSING, rp_node.name):
        add_to_evaluation('responsible_party_05', link, section, item)


def check_creators(eml_node, doc_name, validation_errs=None, evaluation_warnings=None,
                   is_data_source=False, data_source_node_id=None):
    """
    Check that a dataset creator is present and all dataset creators are valid.

    This can be called for either the entire document or for a data source.
    """
    if not is_data_source:
        data_source_node = None
        data_source_node_id = None
        link = url_for(PAGE_CREATOR_SELECT, filename=doc_name)
    else:
        # In the data_source case, the eml_node passed in is the data source node
        data_source_node = eml_node
        # We'll need the eml_node below, however
        eml_node = data_source_node.get_ancestry()[0]
        data_source_node_id = data_source_node.id
        ms_node = data_source_node.parent
        link = url_for(PAGE_DATA_SOURCE,
                       filename=doc_name,
                       ms_node_id=ms_node.id,
                       data_source_node_id=data_source_node.id)

    dataset_node = eml_node.find_child(names.DATASET)
    if validation_errs is None:
        if not is_data_source:
            validation_errs = validate_via_metapype(dataset_node)
        else:
            validation_errs = validate_via_metapype(data_source_node)

    if find_min_unmet(validation_errs, names.DATASET if not is_data_source else names.DATASOURCE, names.CREATOR,
                      data_source_node_id=data_source_node.id if is_data_source else None) or len(dataset_node.children) == 0:
        add_to_evaluation(eval_code('creators_01', is_data_source), link)
    if not is_data_source:
        creator_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.CREATOR])
        section = 'Creators'
        item = 'Creator'
    else:
        creator_nodes = data_source_node.find_all_children(names.CREATOR)
        section = 'Methods'
        item = 'Data Source Creator'
    for creator_node in creator_nodes:
        check_responsible_party(creator_node, section, item, PAGE_CREATOR, doc_name, creator_node.id,
                                is_data_source=is_data_source, data_source_node_id=data_source_node_id)


def check_metadata_providers(eml_node, doc_name):
    """
    Check that metadata providers are valid.
    """
    link = url_for(PAGE_METADATA_PROVIDER_SELECT, filename=doc_name)
    metadata_provider_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.METADATAPROVIDER])
    if metadata_provider_nodes and len(metadata_provider_nodes) > 0:
        for metadata_provider_node in metadata_provider_nodes:
            check_responsible_party(metadata_provider_node, 'Metadata Providers', 'Metadata Provider',
                                    PAGE_METADATA_PROVIDER, doc_name, metadata_provider_node.id)


def check_associated_parties(eml_node, doc_name):
    """
    Check that associated parties are valid.
    """
    link = url_for(PAGE_ASSOCIATED_PARTY_SELECT, filename=doc_name)
    associated_party_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.ASSOCIATEDPARTY])
    if associated_party_nodes and len(associated_party_nodes) > 0:
        for associated_party_node in associated_party_nodes:
            check_responsible_party(associated_party_node, 'Associated Parties', 'Associated Party',
                                    PAGE_ASSOCIATED_PARTY, doc_name, associated_party_node.id)


def check_dataset_abstract(eml_node, doc_name, evaluation_warnings=None):
    """
    Check that a dataset abstract is present and is not too short.
    """
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
    """
    Check that keywords are provided and the number of keywords is sufficient.
    """
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
    """
    Check that intellectual rights are provided.
    """
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
    """
    Check taxonomic coverage to ensure that taxon rank names and values are not empty.
    """
    link = url_for(PAGE_TAXONOMIC_COVERAGE, filename=doc_name, node_id=node.id)

    validation_errs = validate_via_metapype(node)
    if find_content_empty(validation_errs, names.TAXONRANKNAME):
        add_to_evaluation('taxonomic_coverage_01', link)
    if find_content_empty(validation_errs, names.TAXONRANKVALUE):
        add_to_evaluation('taxonomic_coverage_02', link)


def check_coverage(eml_node, doc_name, evaluation_warnings=None):
    """
    Check presence of geographic, temporal, and taxonomic coverage.
    """
    dataset_node = eml_node.find_child(names.DATASET)

    if evaluation_warnings is None:
        evaluation_warnings = evaluate_via_metapype(dataset_node)

    # Warn if no geographic coverage
    geographic_coverage_node = eml_node.find_single_node_by_path([names.DATASET, names.COVERAGE, names.GEOGRAPHICCOVERAGE])
    if not geographic_coverage_node:
        link = url_for(PAGE_GEOGRAPHIC_COVERAGE_SELECT, filename=doc_name)
        add_to_evaluation('geographic_coverage_00', link)

    # Warn if no temporal coverage
    temporal_coverage_node = eml_node.find_single_node_by_path([names.DATASET, names.COVERAGE, names.TEMPORALCOVERAGE])
    if not temporal_coverage_node:
        link = url_for(PAGE_TEMPORAL_COVERAGE_SELECT, filename=doc_name)
        add_to_evaluation('temporal_coverage_00', link)

    # if find_err_code(evaluation_warnings, EvaluationWarning.DATASET_COVERAGE_MISSING, names.DATASET):
    #     add_to_evaluation('coverage_01', link)

    # Check taxonomic coverage nodes for empty taxon rank names or values
    if not webapp.home.utils.load_and_save.was_imported_from_xml(eml_node):
        taxonomic_classification_nodes = []
        dataset_node.find_all_descendants(names.TAXONOMICCOVERAGE, taxonomic_classification_nodes)
        for taxonomic_classification_node in taxonomic_classification_nodes:
            check_taxonomic_coverage(taxonomic_classification_node, doc_name)


def check_bounding_box(geographic_coverage_node, link, validation_errs):
    """
    Check that the bounding box coordinates are logically reasonable. If a coordinate is missing or not a number,
    it is assumed to have been flagged elsewhere.
    """
    west = geographic_coverage_node.find_single_node_by_path([names.BOUNDINGCOORDINATES, names.WESTBOUNDINGCOORDINATE])
    east = geographic_coverage_node.find_single_node_by_path([names.BOUNDINGCOORDINATES, names.EASTBOUNDINGCOORDINATE])
    north = geographic_coverage_node.find_single_node_by_path([names.BOUNDINGCOORDINATES, names.NORTHBOUNDINGCOORDINATE])
    south = geographic_coverage_node.find_single_node_by_path([names.BOUNDINGCOORDINATES, names.SOUTHBOUNDINGCOORDINATE])
    min_alt = geographic_coverage_node.find_single_node_by_path([names.BOUNDINGCOORDINATES, names.BOUNDINGALTITUDES, names.ALTITUDEMINIMUM])
    max_alt = geographic_coverage_node.find_single_node_by_path([names.BOUNDINGCOORDINATES, names.BOUNDINGALTITUDES, names.ALTITUDEMAXIMUM])
    if west and east and float(east.content) < float(west.content):
        add_to_evaluation('geographic_coverage_09', link)
    if north and south and float(north.content) < float(south.content):
        add_to_evaluation('geographic_coverage_10', link)
    if min_alt and max_alt and float(max_alt.content) < float(min_alt.content):
        add_to_evaluation('geographic_coverage_11', link)

def check_geographic_coverage(eml_node, doc_name):
    """
    Check geographic coverage for empty geographic description, empty or invalid west/east/north/south bounding
    coordinates, etc.
    """
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
        check_bounding_box(geographic_coverage_node, link, validation_errs)

def check_attribute(eml_node, doc_name, data_table_node:Node, attrib_node:Node, data_table_name:str):
    """
    Check an attribute -- i.e., a data table column -- for missing attribute name, missing attribute label,
    missing attribute definition, missing attribute type, etc.
    """

    def get_attribute_type(attrib_node: Node):
        """ Return the attribute type (i.e., metapype_client.VariableType) of the given attribute node. """
        mscale_node = attrib_node.find_child(names.MEASUREMENTSCALE)
        # Formerly, Categorical variables were nominal. But now that we're importing externally created XML
        #  files, they may be ordinal.
        if not mscale_node:
            return None
        nominal_or_ordinal_node = mscale_node.find_child(names.NOMINAL)
        if not nominal_or_ordinal_node:
            nominal_or_ordinal_node = mscale_node.find_child(names.ORDINAL)
        if nominal_or_ordinal_node:
            enumerated_domain_node = nominal_or_ordinal_node.find_single_node_by_path(
                [names.NONNUMERICDOMAIN, names.ENUMERATEDDOMAIN])
            if enumerated_domain_node:
                return webapp.home.metapype_client.VariableType.CATEGORICAL
            text_domain_node = nominal_or_ordinal_node.find_single_node_by_path(
                [names.NONNUMERICDOMAIN, names.TEXTDOMAIN])
            if text_domain_node:
                return webapp.home.metapype_client.VariableType.TEXT

        # Formerly, Numerical variables were ratio. But now that we're importing externally created XML
        #  files, they may be interval.
        ratio_or_interval_node = mscale_node.find_child(names.RATIO)
        if not ratio_or_interval_node:
            ratio_or_interval_node = mscale_node.find_child(names.INTERVAL)
        if ratio_or_interval_node:
            return webapp.home.metapype_client.VariableType.NUMERICAL

        datetime_node = mscale_node.find_child(names.DATETIME)
        if datetime_node:
            return webapp.home.metapype_client.VariableType.DATETIME
        return None

    def generate_code_definition_errs(eml_node, doc_name, err_code, errs_found):
        """ Generate errors for code definition errors. This requires walking up the tree to get the
            various node ids needed for the code definition page that will be linked to from the
            evaluation page. I.e., the issue here is generating the link to the code definition page."""
        mscale = webapp.home.metapype_client.VariableType.CATEGORICAL
        for err in errs_found:
            err_node = err[2]
            code_definition_node = err_node.parent
            # Walk up the tree to get the various node ids needed for the code definition page that
            #  will be linked to from the evaluation page.
            enumerated_domain_node = code_definition_node.parent
            non_numeric_domain_node = enumerated_domain_node.parent
            nominal_node = non_numeric_domain_node.parent
            mscale_node = nominal_node.parent
            attribute_node = mscale_node.parent
            attribute_list_node = attribute_node.parent
            data_table_node = attribute_list_node.parent
            data_table_name = data_table_node.find_child(names.ENTITYNAME).content

            code = code_definition_node.find_child(names.CODE).content

            link = url_for(PAGE_CODE_DEFINITION, filename=doc_name, dt_node_id=data_table_node.id,
                           att_node_id=attribute_node.id,
                           nom_ord_node_id=nominal_node.id, node_id=code_definition_node.id, mscale=mscale)
            add_to_evaluation(err_code, link, data_table_name=get_data_table_name(data_table_node))

    def bad_standard_unit(attr_node):
        import webapp.views.data_tables.table_spreadsheets as table_spreadsheets
        """ Return True if the attribute node has a standard unit that is not in the standard unit list. """
        standard_unit_node = attr_node.find_descendant(names.STANDARDUNIT)
        if not standard_unit_node:
            return None, None
        standard_unit = standard_unit_node.content
        if standard_unit not in table_spreadsheets.standard_units:
            return standard_unit, deprecated_in_favor_of(standard_unit)
        return None, None

    def check_custom_units(attr_node):
        """ Check for custom units that differ only by case and/or whitespace. """
        def get_all_custom_units():
            custom_unit_nodes = eml_node.find_all_nodes_by_path([names.ADDITIONALMETADATA,
                                                            names.METADATA,
                                                            names.UNITLIST,
                                                            names.UNIT])
            custom_units = []
            for custom_unit_node in custom_unit_nodes:
                custom_units.append(custom_unit_node.attribute_value('id'))
            return custom_units

        def check_for_duplicates(custom_unit):
            normalized_custom_unit = ''.join(custom_unit.split()).lower()
            all_custom_units = get_all_custom_units()
            for unit in all_custom_units:
                if unit != custom_unit and normalized_custom_unit == ''.join(unit.split()).lower():
                    return unit
            return None

        custom_unit_node = attr_node.find_descendant(names.CUSTOMUNIT)
        if not custom_unit_node:
            return None
        return check_for_duplicates(custom_unit_node.content)

    attr_type = get_attribute_type(attrib_node)
    mscale = None
    page = None
    if attr_type == webapp.home.metapype_client.VariableType.CATEGORICAL:
        page = PAGE_ATTRIBUTE_CATEGORICAL
        mscale = webapp.home.metapype_client.VariableType.CATEGORICAL.name
        data_table_name = None
        if data_table_node:
            entity_name_node = data_table_node.find_child(names.ENTITYNAME)
            if entity_name_node:
                data_table_name = entity_name_node.content
        attrib_name = None
        if attrib_node:
            attrib_name_node = attrib_node.find_child(names.ATTRIBUTENAME)
            if attrib_name_node:
                attrib_name = attrib_name_node.content
        # log_info(f"CATEGORICAL... filename={filename}  data_table={data_table_name}  attr_name={attrib_name}  attr_type={attr_type}")
    elif attr_type == webapp.home.metapype_client.VariableType.NUMERICAL:
        page = PAGE_ATTRIBUTE_NUMERICAL
        mscale = webapp.home.metapype_client.VariableType.NUMERICAL.name
    elif attr_type == webapp.home.metapype_client.VariableType.TEXT:
        page = PAGE_ATTRIBUTE_TEXT
        mscale = webapp.home.metapype_client.VariableType.TEXT.name
    elif attr_type == webapp.home.metapype_client.VariableType.DATETIME:
        page = PAGE_ATTRIBUTE_DATETIME
        mscale = webapp.home.metapype_client.VariableType.DATETIME.name
    # This section is temporary code to track down a bug
    if not page:
        data_table_name = None
        if data_table_node:
            entity_name_node = data_table_node.find_child(names.ENTITYNAME)
            if entity_name_node:
                data_table_name = entity_name_node.content
        attrib_name = None
        if attrib_node:
            attrib_name_node = attrib_node.find_child(names.ATTRIBUTENAME)
            if attrib_name_node:
                attrib_name = attrib_name_node.content
        log_error(f"page not initialized... filename={doc_name}  data_table={data_table_name}  attr_name={attrib_name}  attr_type={attr_type}")
        link = url_for(PAGE_ATTRIBUTE_SELECT, filename=doc_name, dt_node_id=data_table_node.id, node_id=attrib_node.id, mscale=mscale)
        add_to_evaluation('attributes_12', link, data_table_name=data_table_name)
        return

    link = url_for(page, filename=doc_name, dt_node_id=data_table_node.id, node_id=attrib_node.id, mscale=mscale)

    validation_errs = validate_via_metapype(attrib_node)
    if find_content_empty(validation_errs, names.ATTRIBUTEDEFINITION) or \
        find_min_unmet(validation_errs, names.ATTRIBUTE, names.ATTRIBUTEDEFINITION):
        add_to_evaluation('attributes_01', link, data_table_name=data_table_name)
    if find_min_unmet(validation_errs, names.MISSINGVALUECODE, names.CODEEXPLANATION):
        add_to_evaluation('attributes_07', link, data_table_name=data_table_name)

    # Categorical
    if attr_type == webapp.home.metapype_client.VariableType.CATEGORICAL:
        if find_min_unmet_for_choice(validation_errs, names.ENUMERATEDDOMAIN):
            add_to_evaluation('attributes_04', link, data_table_name=data_table_name)
        found = find_content_empty(validation_errs, names.CODE)
        if found:
            generate_code_definition_errs(eml_node, doc_name, 'attributes_05', found)
        found = find_content_empty(validation_errs, names.DEFINITION)
        if found:
            generate_code_definition_errs(eml_node, doc_name, 'attributes_06', found)

    # Numerical
    if attr_type == webapp.home.metapype_client.VariableType.NUMERICAL:
        attribute_name = attrib_node.find_child(names.ATTRIBUTENAME).content
        if find_min_unmet(validation_errs, names.RATIO, names.UNIT):
            add_to_evaluation('attributes_02', link, data_table_name=data_table_name)
        if find_min_unmet_for_choice(validation_errs, names.UNIT):
            add_to_evaluation('attributes_02', link, data_table_name=data_table_name)
        if find_err_code(validation_errs, ValidationError.CONTENT_EXPECTED_FLOAT, names.PRECISION):
            add_to_evaluation('attributes_09', link, data_table_name=data_table_name)
        bad_standard_unit, deprecated_use_instead = bad_standard_unit(attrib_node)
        if bad_standard_unit:
            if not deprecated_use_instead:
                add_to_evaluation('attributes_10', link, data_table_name=data_table_name, replace_value=bad_standard_unit)
            else:
                add_to_evaluation('attributes_11', link, data_table_name=data_table_name, replace_value=bad_standard_unit, replace_with=deprecated_use_instead)
        duplicate_custom_unit = check_custom_units(attrib_node)
        if duplicate_custom_unit:
            add_to_evaluation('attributes_13', link, data_table_name=data_table_name)

    # DateTime
    if attr_type == webapp.home.metapype_client.VariableType.DATETIME:
        if find_min_unmet(validation_errs, names.DATETIME, names.FORMATSTRING):
            add_to_evaluation('attributes_03', link, data_table_name=data_table_name)
        elif find_content_empty(validation_errs, names.FORMATSTRING):
            add_to_evaluation('attributes_03', link, data_table_name=data_table_name)
        elif check_date_time_attribute(attrib_node):
            add_to_evaluation('attributes_08', link, data_table_name=data_table_name)


def get_data_table_name(data_table_node:Node):
    """ Get the name of the data table, given the data table node. """
    entity_name_node = data_table_node.find_child(names.ENTITYNAME)
    if entity_name_node and entity_name_node.content:
        return entity_name_node.content
    else:
        return ''


def check_data_table(eml_node, doc_name, data_table_node:Node):
    """ Check a data table for completeness, including checking all of its columns (attributes). """

    def check_data_table_md5_checksum(data_table_node, link, data_table_name=None):
        """ Check for the existence of the data_table file. Not currently checking its MD5 checksum. """
        object_name_node = data_table_node.find_descendant(names.OBJECTNAME)
        if not object_name_node:
            return
        data_file = object_name_node.content
        uploads_folder = user_data.get_document_uploads_folder_name()
        full_path = f'{uploads_folder}/{data_file}'
        try:
            with open(full_path, 'rb') as file:
                # We'll just check for the data_table file's existence. Don't need to recompute the MD5 over and over
                pass
            # computed_md5_hash = load_data.get_md5_hash(full_path)
            # authentication_node = data_table_node.find_descendant(names.AUTHENTICATION)
            # if authentication_node:
            #     found_md5_hash = authentication_node.content
            #     if found_md5_hash != computed_md5_hash:
            #         add_to_evaluation('data_table_06', link, data_table_name=data_table_name)
        except FileNotFoundError:
            url_node = data_table_node.find_single_node_by_path([names.PHYSICAL,
                                                                 names.DISTRIBUTION,
                                                                 names.ONLINE,
                                                                 names.URL])
            if not url_node or not url_node.content:
                # If there is a URL in Online Distribution node, we don't treat a missing CSV file as an error
                add_to_evaluation('data_table_07', link, data_table_name=data_table_name)
            else:
                return

    link = url_for(PAGE_DATA_TABLE, filename=doc_name, dt_node_id=data_table_node.id)
    validation_errs = validate_via_metapype(data_table_node)
    data_table_name = get_data_table_name(data_table_node)

    check_data_table_md5_checksum(data_table_node, link, data_table_name=data_table_name)

    if find_min_unmet(validation_errs, names.DATATABLE, names.ENTITYNAME):
        add_to_evaluation('data_table_01', link, data_table_name=data_table_name)
    if find_min_unmet(validation_errs, names.DATATABLE, names.ENTITYDESCRIPTION):
        add_to_evaluation('data_table_02', link, data_table_name=data_table_name)
    if find_min_unmet(validation_errs, names.PHYSICAL, names.OBJECTNAME):
        add_to_evaluation('data_table_03', link, data_table_name=data_table_name)
    if find_min_unmet(validation_errs, names.DATATABLE, names.ATTRIBUTELIST):
        add_to_evaluation('data_table_04', link, data_table_name=data_table_name)

    evaluation_warnings = evaluate_via_metapype(data_table_node)
    if find_err_code(evaluation_warnings, EvaluationWarning.DATATABLE_DESCRIPTION_MISSING, names.DATATABLE):
        add_to_evaluation('data_table_02', link, data_table_name=data_table_name)
    if find_err_code(evaluation_warnings, EvaluationWarning.DATATABLE_RECORD_DELIMITER_MISSING, names.DATATABLE):
        add_to_evaluation('data_table_08', link, data_table_name=data_table_name)
    if find_err_code(evaluation_warnings, EvaluationWarning.DATATABLE_SIZE_MISSING, names.DATATABLE):
        add_to_evaluation('data_table_09', link, data_table_name=data_table_name)
    if find_err_code(evaluation_warnings, EvaluationWarning.DATATABLE_MD5_CHECKSUM_MISSING, names.DATATABLE):
        add_to_evaluation('data_table_10', link, data_table_name=data_table_name)
    if find_err_code(evaluation_warnings, EvaluationWarning.DATATABLE_NUMBER_OF_RECORDS_MISSING, names.DATATABLE):
        add_to_evaluation('data_table_11', link, data_table_name=data_table_name)

    attribute_list_node = data_table_node.find_child(names.ATTRIBUTELIST)
    if attribute_list_node:
        attribute_nodes = attribute_list_node.find_all_children(names.ATTRIBUTE)
        for attribute_node in attribute_nodes:
            check_attribute(eml_node, doc_name, data_table_node, attribute_node, data_table_name=data_table_name)


def check_data_tables(eml_node, doc_name, evaluation_warnings=None):
    """ Check all data tables in the EML document. """
    link = url_for(PAGE_DATA_TABLE_SELECT, filename=doc_name)
    dataset_node = eml_node.find_child(names.DATASET)
    if evaluation_warnings is None:
        evaluation_warnings = evaluate_via_metapype(dataset_node)
    # Warning if no data tables - removed 2/5/2025. The case of a dataset with no data tables is
    #  not terribly uncommon.
    # if find_err_code(evaluation_warnings, EvaluationWarning.DATATABLE_MISSING, names.DATASET):
    #     add_to_evaluation('data_table_05', link)

    data_table_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.DATATABLE])
    for data_table_node in data_table_nodes:
        check_data_table(eml_node, doc_name, data_table_node)


def check_maintenance(eml_node, doc_name, evaluation_warnings=None):
    """ Check the maintenance node for completeness. """
    link = url_for(PAGE_MAINTENANCE, filename=doc_name)
    dataset_node = eml_node.find_child(names.DATASET)
    if evaluation_warnings is None:
        evaluation_warnings = evaluate_via_metapype(dataset_node)
    if find_err_code(evaluation_warnings, EvaluationWarning.MAINTENANCE_DESCRIPTION_MISSING, names.DESCRIPTION):
        add_to_evaluation('maintenance_01', link)


def check_contacts(eml_node, doc_name, validation_errs=None, evaluation_warnings=None, is_data_source=False):
    """ Check the contacts in the EML document. """
    if not is_data_source:
        data_source_node = None
        data_source_node_id = None
        link = url_for(PAGE_CONTACT_SELECT, filename=doc_name)
    else:
        # In the data_source case, the eml_node passed in is the data source node
        data_source_node = eml_node
        # We'll need the eml_node below, however
        eml_node = data_source_node.get_ancestry()[0]
        data_source_node_id = data_source_node.id
        ms_node = data_source_node.parent
        link = url_for(PAGE_DATA_SOURCE,
                       filename=doc_name,
                       ms_node_id=ms_node.id,
                       data_source_node_id=data_source_node.id)

    dataset_node = eml_node.find_child(names.DATASET)
    if validation_errs is None:
        validation_errs = validate_via_metapype(dataset_node)
    if find_min_unmet(validation_errs, names.DATASET if not is_data_source else names.DATASOURCE, names.CONTACT,
                      data_source_node_id=data_source_node.id if is_data_source else None) or len(dataset_node.children) == 0:
        add_to_evaluation(eval_code('contacts_01', is_data_source), link=link)
    if not is_data_source:
        contact_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.CONTACT])
        section = 'Contacts'
        item = 'Contact'
    else:
        contact_nodes = data_source_node.find_all_children(names.CONTACT)
        section = 'Methods'
        item = 'Data Source Contact'

    for contact_node in contact_nodes:
        check_responsible_party(contact_node, section, item, PAGE_CONTACT, doc_name, contact_node.id,
                                is_data_source=is_data_source, data_source_node_id=data_source_node_id)


def check_publisher(eml_node, doc_name):
    """
    Check that publisher is valid.
    """
    link = url_for(PAGE_PUBLISHER, filename=doc_name)
    publisher_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.PUBLISHER])
    if publisher_nodes and len(publisher_nodes) > 0:
        for publisher_node in publisher_nodes:
            check_responsible_party(publisher_node, 'Publisher', 'Publisher',
                                    PAGE_PUBLISHER, doc_name, publisher_node.id)


def check_data_source(doc_name, data_source_node):
    """ Check a data source node for completeness and correctness. A data source node is essentially another
        EML document, so we can use some of the same functions to check it as we use to check the top-level EML
        document, just keeping track of the fact that we're looking at a data source. """

    def check_distribution_element(distribution_node, doc_name):
        """
        This assumes the distribution node is a child of a dataSource node, which is a child of a methodStep node.
        """
        data_source_node = distribution_node.parent
        ms_node = data_source_node.parent
        link = url_for(PAGE_DATA_SOURCE,
                       filename=doc_name,
                       ms_node_id=ms_node.id,
                       data_source_node_id=data_source_node.id)
        # We do ad hoc checking here because what ezEML requires is not what the EML schema requires.
        # For ezEML, if a distribution element is present it must have an online element child, and the
        # online element must have both an onlineDescription element child and a url element child, both
        # of which must have nonempty text content.
        error = False
        online_node = distribution_node.find_child(names.ONLINE)
        if online_node:
            online_description_node = online_node.find_child(names.ONLINEDESCRIPTION)
            if online_description_node:
                online_description = online_description_node.content
                if not online_description:
                    error = True
            url_node = online_node.find_child(names.URL)
            if url_node:
                url = url_node.content
                if not url:
                    error = True
            if not online_description_node or not url_node:
                error = True
        else:
            error = True
        if error:
            add_to_evaluation('methods_04', link)

    validation_errs = validate_via_metapype(data_source_node)
    evaluation_warnings = evaluate_via_metapype(data_source_node)
    check_dataset_title(data_source_node, doc_name,
                        validation_errs=validation_errs,
                        evaluation_warnings=evaluation_warnings,
                        is_data_source=True)
    check_creators(data_source_node, doc_name,
                   validation_errs=validation_errs,
                   evaluation_warnings=evaluation_warnings,
                   is_data_source=True)
    check_contacts(data_source_node, doc_name,
                   validation_errs=validation_errs,
                   evaluation_warnings=evaluation_warnings,
                   is_data_source=True)
    distribution_node = data_source_node.find_descendant(names.DISTRIBUTION)
    if distribution_node:
        check_distribution_element(distribution_node, doc_name)


def check_method_steps(eml_node, doc_name, validation_errs=None, evaluation_warnings=None):
    """ Check all method steps in the EML document. """

    def check_method_step(method_step_node, doc_name, node_id):
        """ Check a method step node for completeness and correctness. """
        link = url_for(PAGE_METHOD_STEP, filename=doc_name, node_id=node_id)

        validation_errs = validate_via_metapype(method_step_node)
        evaluation_warnings = evaluate_via_metapype(method_step_node)

        data_source_nodes = method_step_node.find_all_children(names.DATASOURCE)
        for data_source_node in data_source_nodes:
            check_data_source(doc_name, data_source_node)

        if find_err_code(evaluation_warnings, EvaluationWarning.METHOD_STEP_DESCRIPTION_MISSING, names.DESCRIPTION):
            add_to_evaluation('methods_02', link)

        if find_min_unmet(validation_errs, names.METHODSTEP, names.DESCRIPTION):
            add_to_evaluation('methods_02', link)

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


def check_project_node(project_node, doc_name, related_project_id=None):
    """
    Check a project node for completeness and correctness. It may be a project or a related project.
    In the latter case, a related_project_id is given.
    """

    def check_project_award(award_node, doc_name, related_project_id=None):
        """ Check a project funding award node for completeness and correctness. """

        if not related_project_id:
            link = url_for(PAGE_FUNDING_AWARD, filename=doc_name, node_id=award_node.id)
        else:
            link = url_for(PAGE_FUNDING_AWARD, filename=doc_name, node_id=award_node.id,
                           project_node_id=related_project_id)
        validation_errors = validate_via_metapype(award_node)
        if find_min_unmet(validation_errors, names.AWARD, names.FUNDERNAME) or \
                find_content_empty(validation_errors, names.FUNDERNAME):
            add_to_evaluation('project_04', link)
        if find_min_unmet(validation_errors, names.AWARD, names.TITLE) or \
                find_content_empty(validation_errors, names.TITLE):
            add_to_evaluation('project_05', link)

    if not related_project_id:
        link = url_for(PAGE_PROJECT, filename=doc_name)
    else:
        link = url_for(PAGE_PROJECT, filename=doc_name, project_node_id=related_project_id)
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
    if not project_award_nodes:
        add_to_evaluation('project_06', link)
    else:
        for project_award_node in project_award_nodes:
            check_project_award(project_award_node, doc_name, related_project_id)

    related_project_nodes = project_node.find_all_children(names.RELATED_PROJECT)
    for related_project_node in related_project_nodes:
        check_project_node(related_project_node, doc_name, related_project_node.id)


def check_project(eml_node, doc_name, evaluation_warnings=None):
    """ Check that a project is present. If so, check it for completeness and correctness. Otherwise, warn. """
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


def check_other_entities(eml_node, doc_name):
    """ Check all other entity nodes for completeness and correctness. """

    def check_other_entity(entity_node, doc_name):
        """ Check an other entity node for completeness and correctness. """

        link = url_for(PAGE_OTHER_ENTITY, filename=doc_name, node_id=entity_node.id)

        validation_errors = validate_via_metapype(entity_node)
        if find_min_unmet(validation_errors, names.OTHERENTITY, names.ENTITYNAME):
            add_to_evaluation('other_entity_01', link)
        if find_min_unmet(validation_errors, names.OTHERENTITY, names.ENTITYTYPE):
            add_to_evaluation('other_entity_02', link)
        if find_min_unmet(validation_errs, names.PHYSICAL, names.OBJECTNAME):
            add_to_evaluation('other_entity_04', link)
        if find_min_unmet(validation_errs, names.PHYSICAL, names.DATAFORMAT):
            add_to_evaluation('other_entity_05', link)

        evaluation_warnings = evaluate_via_metapype(entity_node)
        if find_err_code(evaluation_warnings, EvaluationWarning.OTHER_ENTITY_DESCRIPTION_MISSING, names.OTHERENTITY):
            add_to_evaluation('other_entity_03', link)

    other_entity_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.OTHERENTITY])
    for other_entity_node in other_entity_nodes:
        check_other_entity(other_entity_node, doc_name)


def to_string(evaluation):
    def eval_entry_to_string(eval_entry):
        return f'Section:&nbsp;{eval_entry.section}<br>Item:&nbsp;{eval_entry.item}<br>Severity:&nbsp;{eval_entry.severity.name}<br>Type:&nbsp;{eval_entry.type.name}<br>Explanation:&nbsp;{eval_entry.explanation}<br><a href="{eval_entry.link}">Link</a>'

    if evaluation and len(evaluation) > 0:
        s = ''
        for eval_entry in evaluation:
            s += eval_entry_to_string(eval_entry) + '<p/>'
        return s
    else:
        return "OK!"


def format_entry(entry: EvalEntry):
    """ Format a single evaluation entry as HTML. """
    def severity_explanation(entry):
        if entry.severity == EvalSeverity.ERROR:
            badge = f'<a href="{entry.link}"><span class="red_circle" title="Error"></span></a>'
        else:
            badge = f'<a href="{entry.link}"><span class="yellow_circle" title="Warning"></span></a>'
        return f"{badge}&nbsp;&nbsp;{entry.explanation}"

    output = '<tr>'
    # if entry.ui_element_id:
    #     entry.link = f'{entry.link}?ui_element_id={entry.ui_element_id}'
    output += f'<td class="eval_table" valign="top"><a href="{entry.link}">{entry.item}</a></td>'
    output += f'<td class="eval_table" valign="top">{severity_explanation(entry)}</td>'
    # output += f'<td class="eval_table" valign="top">{entry.type.name.title()}</td>'
    # output += f'<td class="eval_table" valign="top">{entry.explanation}</td>'
    output += '</tr>'
    return output


evaluations = []
def init_evaluation(eml_node, doc_name):
    """ Initialize the evaluation process. """
    global evaluations, parse_errs, unicode_errs
    evaluations, parse_errs, unicode_errs = perform_evaluation(eml_node, doc_name)


def format_tooltip(node, section=None):
    """ Format the evaluation output pertaining to a node as a tooltip. """
    def get_route_from_link(link):
        """ Parse a link to extract the route being referenced. """
        if link:
            parts = link.split('/')
            for part in parts:
                if part == 'eml':
                    route = parts[parts.index(part) + 1]
                    if route == 'data_table_select':
                        return 'data_tables'
                    return route
        return ''

    tooltip = f'<table width=100% style="padding: 30px;"><tr><td colspan=3><i>Click any item to edit:</i></td></tr>'
    all_ok = True
    for severity in severities:
        for entry in evaluations:
            if entry.severity == severity:
                if (node and node.id in entry.link) or (section and
                                                        (section in get_route_from_link(entry.link) or
                                                         section in get_section_from_link(entry.link))):
                    tooltip += f'<tr><td class="'
                    if severity == EvalSeverity.ERROR:
                        tooltip += 'red'
                    else:
                        tooltip += 'yellow'
                    # if entry.ui_element_id:
                    #     entry.link = f'{entry.link}?ui_element_id={entry.ui_element_id}'
                    tooltip += f'_circle"></td><td>&nbsp;&nbsp;</td><td><a class="popup link" href="{entry.link}">{entry.explanation.replace(" ", " ")}</a></td></tr>\n'
                    all_ok = False
    if all_ok:
        tooltip = ''
    else:
        tooltip += '</table>'
    return tooltip


def format_output(evaluation, parse_errs, unicode_errs, eml_node):
    """ Format the evaluation output for display. """

    def get_data_table_names(eml_node):
        """ Get the names of all data tables in the EML document. """
        data_table_names = []
        data_table_name_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.DATATABLE, names.ENTITYNAME])
        for data_table_name_node in data_table_name_nodes:
            data_table_names.append(data_table_name_node.content)
        return data_table_names

    def format_data_table_output(entries, output, eml_node):
        """ Format the evaluation output for data tables. Data tables are handled specially because errors for a given
        data table are grouped together. I.e., within the section for data tables, there are individual sections for
        each data table. """

        previous_data_table_name = None
        entries = sorted(entries, key=lambda entry: (entry.data_table_name, repr(entry.severity)))
        data_table_names = get_data_table_names(eml_node)
        if not data_table_names:
            return ''
        offset = get_query_string()
        if offset == 'data_tables':
            section_output = f'<mark style="background-color:#ffffa0;">Data Tables</mark>'
        else:
            section_output = 'Data Tables'
        output = f'<h3 id="data_tables">{section_output}</h3>'
        for data_table_name in data_table_names:
            for entry in entries:
                if entry.data_table_name != data_table_name:
                    continue
                if entry.data_table_name != previous_data_table_name:
                    if previous_data_table_name:
                        output += '</table><p>&nbsp;</p>'
                    else:
                        output += '<br>'
                    output += f'<table class="eval_table" width=100% style="padding: 10px;"><tr><b id="data_table:{data_table_name}">Data Table: </b>{entry.data_table_name}</tr><tr><th class="eval_table" align="left" width=20%>Item</th>' \
                              f'<th class="eval_table" align="left" width=80%>Issue</th></tr>'
                    previous_data_table_name = entry.data_table_name
                output += format_entry(entry)
        return output + '</table><p>&nbsp;</p>'

    def collect_entries(evaluation, section):
        """ Collect the entries in the evaluation that are in the given section. """
        """ Data Sources are a special case. We want to lump them in with Methods."""
        if section == 'Data Sources':
            return []
        elif section == 'Methods':
            return [entry for entry in evaluation if entry.section == section or entry.section == 'Data Sources']
        else:
            return [entry for entry in evaluation if entry.section == section]

    sections = {
        'Title': 'title',
        'Data Tables': 'data_tables',
        'Creators': 'creators',
        'Contacts': 'contacts',
        'Associated Parties': 'associated_parties',
        'Metadata Providers': 'metadata_providers',
        'Abstract': 'abstract',
        'Keywords': 'keywords',
        'Intellectual Rights': 'intellectual_rights',
        'Coverage': 'coverage',
        'Geographic Coverage': 'geographic_coverage',
        'Temporal Coverage': 'temporal_coverage',
        'Taxonomic Coverage': 'taxonomic_coverage',
        'Maintenance': 'maintenance',
        'Publisher': 'publisher',
        'Methods': 'methods',
        'Data Sources': 'data_sources',
        'Project': 'project',
        'Other Entities': 'other_entities',
        'Data Package ID': 'data_package_id'}

    def get_query_string():
        return request.query_string.decode('utf-8')

    all_ok = True
    # See if we're following a link to a specific section in the check_metadata page
    offset = get_query_string()
    output = '<span style="font-family: Helvetica,Arial,sans-serif;">'
    """ Format the sections, with headings, in order. """
    for section in sections:
        if section == 'Data Sources':
            continue
        anchor = sections[section]
        if offset == anchor:
            section_output = f'<mark style="background-color:#ffffa0;">{section}</mark>'
        else:
            section_output = f'{section}'

        entries = collect_entries(evaluation, section)
        if not entries:
            continue
        all_ok = False
        if section == 'Data Tables':
            data_table_names = get_data_table_names(eml_node)
            if data_table_names:
                # If there is at least one data table, we format the data table output specially, since we want to
                #  aggregate errors/warnings by data table
                output += format_data_table_output(entries, output, eml_node)
                continue
        """ Data Sources are a special case. We want to lump them in with Methods."""
        output += f'<h3 id="{anchor}">{section_output}</h3><table class="eval_table" width=100% style="padding: 10px;"><tr><th class="eval_table" align="left" width=20%>Item</th>' \
                  f'<th class="eval_table" align="left" width=80%>Issue</th></tr>'
        for severity in severities:
            for entry in entries:
                if entry.severity == severity:
                    output += format_entry(entry)
        output += '</table><br>'
    if all_ok and not parse_errs and not unicode_errs:
        output += '<h4>No errors or warnings found!</h4>'
    output += '</span>'
    return output


def check_evaluation_memo(json_filename, eml_node):
    """
    We memoize validation results in a pickle file and only recompute them when the json file's content has changed,
    as indicated by a change in the MD5 hash. Check to see if memoizing is needed. If not, return the memoized results.
    The caller will know if memoizing is needed if the memoized results are None.
    """
    eval_filename = json_filename.replace('.json', '_eval.pkl')
    try:
        # start = datetime.now()
        # Get the memoized results
        old_md5, validation_errs, evaluation_warnings, evaluation, parse_errs, unicode_errs = pickle.load(open(eval_filename, 'rb'))
        # Compute the current MD5 hash to see if it has changed
        with open(json_filename, 'rt') as json_file:
            json = json_file.read()
        new_md5 = hashlib.md5(json.encode('utf-8')).hexdigest()
        # end = datetime.now()
        # elapsed = (end - start).total_seconds()
        # print('**** check_evaluation_memo', elapsed)
        if new_md5 == old_md5:
            # print(f'**** new_md5={new_md5}')
            return old_md5, validation_errs, evaluation_warnings, evaluation, parse_errs, unicode_errs
        else:
            # print(f'**** new_md5={new_md5}, old_md5={old_md5}')
            return new_md5, None, None, None, None, None
    except ValueError:
        # Memo files used to contain fewer objects. I.e., this memo file must be obsolete. Delete it.
        try:
            os.remove(eval_filename)
        except:
            pass
    except:
        pass

    return None, None, None, None, None, None


def memoize_evaluation(json_filename, eml_node, md5, validation_errs, evaluation_warnings, evaluation, parse_errs, unicode_errs):
    """ Memoize the evaluation results in a pickle file, together with the MD5 hash. """
    eval_filename = json_filename.replace('.json', '_eval.pkl')
    try:
        if md5 == None:
            with open(json_filename, 'rt') as json_file:
                json = json_file.read()
            md5 = hashlib.md5(json.encode('utf-8')).hexdigest()
        with open(eval_filename, 'wb') as f:
            pickle.dump((md5, validation_errs, evaluation_warnings, evaluation, parse_errs, unicode_errs), f)
    except Exception as e:
        if os.path.exists(eval_filename):
            os.remove(eval_filename)


def perform_evaluation(eml_node, doc_name):
    """
    Perform the evaluation of the EML document. If the evaluation has already been performed and memoized, return the
    memoized results. Otherwise, perform the evaluation, memoize the results, and return them.
    """
    def display_elapsed(start, msg):
        end = datetime.now()
        elapsed = (end - start).total_seconds()
        # print(f"**** {msg} {elapsed}")

    global evaluation, validation_errs, evaluation_warnings, parse_errs, unicode_errs

    if not eml_node:
        # If the user uses the browser's back button after deleting the current package, for example, the eml_node will be None
        # We'll redirect to the index page
        raise EMLFileNotFound(doc_name)

    evaluation = []
    start = datetime.now()

    user_folder = user_data.get_user_folder_name()
    xml_filename = f'{user_folder}/{doc_name}.xml'
    json_filename = f'{user_folder}/{doc_name}.json'

    md5, validation_errs, evaluation_warnings, evaluation, parse_errs, unicode_errs = check_evaluation_memo(json_filename, eml_node)
    need_to_memoize = False
    if evaluation is None:
        evaluation = []
        need_to_memoize = True
        validation_errs = validate_via_metapype(eml_node)
        evaluation_warnings = evaluate_via_metapype(eml_node)

    if not need_to_memoize:
        display_elapsed(start, '**** perform_evaluation')
        set_session_info(evaluation, eml_node)
        return evaluation, parse_errs, unicode_errs

    display_elapsed(start, '**** starting checks')
    check_dataset_title(eml_node, doc_name, validation_errs, evaluation_warnings)
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
    check_publisher(eml_node, doc_name)
    check_method_steps(eml_node, doc_name, validation_errs, evaluation_warnings)
    check_project(eml_node, doc_name)
    check_other_entities(eml_node, doc_name)
    check_data_package_id(eml_node, doc_name, validation_errs)

    _, parse_errs, unicode_errs = views.parse_and_validate(pathname=xml_filename, parse_only=True)

    if need_to_memoize:
        memoize_evaluation(json_filename, eml_node, md5,
                           validation_errs, evaluation_warnings, evaluation,
                           parse_errs, unicode_errs)

    display_elapsed(start, '**** perform_evaluation')

    set_session_info(evaluation, eml_node)

    return evaluation, parse_errs, unicode_errs


def check_metadata_status(eml_node, doc_name):
    """
    Return the number of errors and warnings for the metadata status. This is used to set the badge color for the
    Check Metadata menu item. Most of the time the evaluation is memoized, so this is fast.
    """
    evaluations, parse_errs, unicode_errs = perform_evaluation(eml_node, doc_name)
    errors = 0
    warnings = 0
    for entry in evaluations:
        severity = entry.severity
        if severity == EvalSeverity.ERROR:
            errors += 1
        if severity == EvalSeverity.WARNING:
            warnings += 1
    if parse_errs:
        errors += 1
    # if unicode_errs:
    #     warnings += 1
    return errors, warnings


def check_eml(eml_node, doc_name):
    """ Evaluate the EML document and return the results as HTML. """
    evaluations, parse_errs, unicode_errs = perform_evaluation(eml_node, doc_name)
    return format_output(evaluations, parse_errs, unicode_errs, eml_node), parse_errs, unicode_errs


def validate_via_metapype(node):
    """ Validate a subtree of the EML document using Metapype. This looks for schema violations. """
    errs = []
    try:
        # start = time.perf_counter()
        validate.tree(node, errs)
        # end = time.perf_counter()
        # elapsed = end - start
        # if elapsed > 0.05:
        #     print(f"validate: {node.name}  {elapsed}")
    except Exception as e:
        name = node.name if node is not None else 'None'
        log_error(f'validate_via_metapype: node={name} exception={e}')
    return errs


def evaluate_via_metapype(node):
    """ Evaluate a subtree of the EML document using Metapype. This looks for evaluation errors and warnings that
     are part of EDI's standards but not schema violations. """
    eval = []
    try:
        # start = time.perf_counter()
        evaluate.tree(node, eval)
        # end = time.perf_counter()
        # elapsed = end - start
        # if elapsed > 0.05:
        #     print(f"evaluate: {node.name}  {elapsed}")
    except Exception as e:
        name = node.name if node is not None else 'None'
        log_error(f'evaluate_via_metapype: node={name} exception={e}')
    return eval


########### Remainder of file is support for badges ###########

import re
uuid_regex = r"^[0-9a-fA-F]{8}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{12}$"

def is_valid_uuid(string):
    """
    Checks if a string is a valid UUID based on RFC 4122.

    Args:
      string: The string to validate.

    Returns:
      True if the string is a valid UUID, False otherwise.
    """
    return re.match(uuid_regex, string) is not None


def section_to_name(section):
    if section == 'title':
        return names.TITLE
    if section == 'data_tables':
        return names.DATATABLE
    if section == 'creators':
        return names.CREATOR
    if section == 'contacts':
        return names.CONTACT
    if section == 'associated_parties':
        return names.ASSOCIATEDPARTY
    if section == 'metadata_providers':
        return names.METADATAPROVIDER
    if section == 'abstract':
        return names.ABSTRACT
    if section == 'keywords':
        return names.KEYWORD
    if section == 'intellectual_rights':
        return names.INTELLECTUALRIGHTS
    if section == 'geographic_coverage':
        return names.GEOGRAPHICCOVERAGE
    if section == 'temporal_coverage':
        return names.TEMPORALCOVERAGE
    if section == 'taxonomic_coverage':
        return names.TAXONOMICCOVERAGE
    if section == 'maintenance':
        return names.MAINTENANCE
    if section == 'publisher':
        return names.PUBLISHER
    if section == 'publication_info':
        return names.PUBPLACE
    if section == 'methods':
        return names.METHODS
    if section == 'project':
        return names.PROJECT
    if section == 'other_entities':
        return names.OTHERENTITY
    # if section == 'data_package_id':
    #     return names.DATAPACKAGEID
    return None


def empty_subtree(eml_node, subtree_name):
    if eml_node is None:
        return True
    subtree = eml_node.find_descendant(subtree_name)
    if subtree is None:
        return True
    if (subtree.content is None or len(subtree.content) == 0) and len(subtree.attributes) == 0 and len(subtree.children) == 0:
        return True
    return False


def get_section_from_link(link):
    if '/eml/title/' in link:
        return 'title'
    if '/eml/data_table_select/' in link or \
        '/eml/data_table/' in link or \
        '/eml/attribute_categorical/' in link or \
        '/eml/attribute_dateTime/' in link or \
        '/eml/attribute_numerical/' in link or \
        '/eml/attribute_select' in link or \
        '/eml/attribute_text/' in link or \
        '/eml/code_definition' in link:
        return 'data_tables'
    if '/eml/creator_select/' in link or '/eml/creator/' in link:
        return 'creators'
    if '/eml/contact_select/' in link or '/eml/contact/' in link:
        return 'contacts'
    if '/eml/associated_party/' in link:
        return 'associated_parties'
    if '/eml/metadata_provider/' in link:
        return 'metadata_providers'
    if '/eml/abstract/' in link:
        return 'abstract'
    if '/eml/keyword_select/' in link:
        return 'keywords'
    if '/eml/intellectual_rights/' in link:
        return 'intellectual_rights'
    if '/eml/geographic_coverage_select/' in link or '/eml/geographic_coverage/' in link:
        return 'geographic_coverage'
    if '/eml/temporal_coverage_select/' in link or '/eml/temporal_coverage/' in link:
        return 'temporal_coverage'
    if '/eml/taxonomic_coverage_select/' in link or '/eml/taxonomic_coverage/' in link:
        return 'taxonomic_coverage'
    if '/eml/maintenance/' in link:
        return 'maintenance'
    if '/eml/publisher/' in link:
        return 'publisher'
    if '/eml/publication_info/' in link:
        return 'publication_info'
    if '/eml/method_step_select/' in link or '/eml/method_step/' in link or '/eml/data_source' in link:
        return 'methods'
    if '/eml/project_select/' in link or '/eml/project/' in link or '/eml/project_personnel/' in link or '/eml/funding_award/' in link:
        return 'project'
    if '/eml/other_entity_select/' in link or '/eml/other_entity/' in link:
        return 'other_entities'
    if '/eml/data_package_id/' in link:
        return 'data_package_id'
    log_info(f'get_section_from_link: link={link} not recognized')
    return []


def set_session_info(evaluation, eml_node):
    def init_section_links_found(section_links_found):
        section_links_found['title'] = EvalSeverity.OK
        section_links_found['data_tables'] = EvalSeverity.OK
        section_links_found['creators'] = EvalSeverity.OK
        section_links_found['contacts'] = EvalSeverity.OK
        section_links_found['associated_parties'] = EvalSeverity.OK
        section_links_found['metadata_providers'] = EvalSeverity.OK
        section_links_found['abstract'] = EvalSeverity.OK
        section_links_found['keywords'] = EvalSeverity.OK
        section_links_found['intellectual_rights'] = EvalSeverity.OK
        section_links_found['geographic_coverage'] = EvalSeverity.OK
        section_links_found['temporal_coverage'] = EvalSeverity.OK
        section_links_found['taxonomic_coverage'] = EvalSeverity.OK
        section_links_found['maintenance'] = EvalSeverity.OK
        section_links_found['publisher'] = EvalSeverity.OK
        section_links_found['publication_info'] = EvalSeverity.OK
        section_links_found['methods'] = EvalSeverity.OK
        section_links_found['project'] = EvalSeverity.OK
        section_links_found['other_entities'] = EvalSeverity.OK
        section_links_found['data_package_id'] = EvalSeverity.OK

        for key, value in section_links_found.items():
            name = section_to_name(key)
            if name and not empty_subtree(eml_node, name):
                views.badge_data[key + '_status'] = 'green'
            else:
                views.badge_data[key + '_status'] = 'white'

    def severity_to_status(severity):
        if severity == EvalSeverity.OK:
            return 'green'
        if severity == EvalSeverity.WARNING:
            return 'yellow'
        if severity == EvalSeverity.ERROR:
            return 'red'
        return 'green'

    def find_node_ids(link):
        """
        Finds the node ids in a link.

        Args:
          link: The link to search for node ids.

        Returns:
          A list of node ids found in the link.
        """
         # Get rid of any query string
        parsed = urlparse(link)
        link = urlunparse(parsed._replace(query=''))
        substrs = link.split('/')
        node_ids = []
        for substr in substrs:
            if is_valid_uuid(substr):
                node_ids.append(substr)
        # Now look at the query string
        query_string = parsed.query
        query_params = parse_qs(query_string)
        for key, value in query_params.items():
            for val in value:
                if is_valid_uuid(val):
                    node_ids.append(val)
        return node_ids

    section_links_found = {}
    node_links_found = {}
    init_section_links_found(section_links_found)
    views.badge_data = {}

    for entry in evaluation:
        severity = entry.severity
        if entry.link:
            which = get_section_from_link(entry.link)
            if which:
                current_severity = section_links_found.get(which, EvalSeverity.OK)
                if severity.value < current_severity.value:
                    section_links_found[which] = severity
            node_ids = find_node_ids(entry.link)
            for node_id in node_ids:
                current_severity = node_links_found.get(node_id, EvalSeverity.OK)
                if severity.value < current_severity.value:
                    node_links_found[node_id] = severity

    for key, value in section_links_found.items():
        color = severity_to_status(value)
        if color == 'green':
            name = section_to_name(key)
            if name and empty_subtree(eml_node, name):
                color = 'white'
        views.badge_data[key + '_status'] = color

    for key, value in node_links_found.items():
        views.badge_data[key + '_status'] = severity_to_status(value)

    g.badge_data = views.badge_data

