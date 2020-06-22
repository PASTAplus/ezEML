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
import daiquiri
from enum import Enum
import html
import json

from flask import (
    Blueprint, Flask, url_for, render_template, session, app
)

from metapype.eml import names
from metapype.model.node import Node
from webapp.home.metapype_client import load_eml, VariableType
from webapp.pages import *


app = Flask(__name__)
home = Blueprint('home', __name__, template_folder='templates')

class EvalSeverity(Enum):
    ERROR = 1
    WARNING = 2
    INFO = 3

class EvalType(Enum):
    REQUIRED = 1
    RECOMMENDED = 2
    BEST_PRACTICE = 3


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


def child_content(parent_node:Node, child_name:str):
    child_node = parent_node.find_child(child_name)
    if child_node:
        return child_node.content
    else:
        return None


def descendant_content(parent_node:Node, path:list):
    descendant_node = parent_node.find_single_node_by_path(path)
    if descendant_node:
        return descendant_node.content
    else:
        return None


def is_float(value):
    try:
        float(value)
        return True
    except:
        return False


Eval_Entry = collections.namedtuple(
    'Evaluate_Entry', ["section", "item", "severity", "type", "explanation", "link"])
evaluation = []


def check_dataset_title(eml_node, packageid):
    link = url_for(PAGE_TITLE, packageid=packageid)
    title_node = eml_node.find_single_node_by_path([names.DATASET, names.TITLE])
    if not (title_node and title_node.content):
        add_to_evaluation('title_01', link)
    if title_node:
        content = title_node.content if title_node.content else ''
        words = content.split()
        if len(words) < 5:
            add_to_evaluation('title_02', link)


def check_responsible_party(rp_node:Node, needs_role:bool=False, section:str=None, item:str=None,
                            page:str=None, packageid:str=None, node_id:str=None):
    link = url_for(page, packageid=packageid, node_id=node_id)
    # At least one of surname, organization name, or position name is required
    surname = None
    organization_name = None
    position_name = None
    surname_node = rp_node.find_single_node_by_path([names.INDIVIDUALNAME, names.SURNAME])
    if surname_node:
        surname = surname_node.content
    organization_name_node = rp_node.find_child(names.ORGANIZATIONNAME)
    if organization_name_node:
        organization_name = organization_name_node.content
    position_name_node = rp_node.find_child(names.POSITIONNAME)
    if position_name_node:
        position_name = position_name_node.content
    if not any([surname, organization_name, position_name]):
        add_to_evaluation('responsible_party_01', link, section, item)
    # User ID is recommended
    user_id_node = rp_node.find_child(names.USERID)
    if not user_id_node or len(user_id_node.content) == 0:
        add_to_evaluation('responsible_party_02', link, section, item)
    # Role, if required
    if needs_role:
        role_node = rp_node.find_child(names.ROLE)
        if not (role_node and role_node.content):
            add_to_evaluation('responsible_party_03', link, section, item)


def check_creators(eml_node, packageid):
    link = url_for(PAGE_CREATOR_SELECT, packageid=packageid)
    creator_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.CREATOR])
    if not creator_nodes or len(creator_nodes) == 0:
        add_to_evaluation('creators_01', link)
    else:
        for creator_node in creator_nodes:
            check_responsible_party(creator_node, False, 'Creators', 'Creator', PAGE_CREATOR, packageid, creator_node.id)


def check_metadata_providers(eml_node, packageid):
    link = url_for(PAGE_METADATA_PROVIDER_SELECT, packageid=packageid)
    metadata_provider_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.METADATAPROVIDER])
    if metadata_provider_nodes and len(metadata_provider_nodes) > 0:
        for metadata_provider_node in metadata_provider_nodes:
            check_responsible_party(metadata_provider_node, False, 'Metadata Providers', 'Metadata Provider', PAGE_METADATA_PROVIDER,
                                    packageid, metadata_provider_node.id)


def check_associated_parties(eml_node, packageid):
    link = url_for(PAGE_ASSOCIATED_PARTY_SELECT, packageid=packageid)
    associated_party_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.ASSOCIATEDPARTY])
    if associated_party_nodes and len(associated_party_nodes) > 0:
        for associated_party_node in associated_party_nodes:
            check_responsible_party(associated_party_node, True, 'Associated Parties', 'Associated Party', PAGE_ASSOCIATED_PARTY,
                                    packageid, associated_party_node.id)


def check_dataset_abstract(eml_node, packageid):
    link = url_for(PAGE_ABSTRACT, packageid=packageid)
    abstract_node = eml_node.find_single_node_by_path([names.DATASET, names.ABSTRACT])
    if abstract_node:
        content = abstract_node.content if abstract_node.content else ''
        if not content:
            add_to_evaluation('abstract_01', link)
        else:
            words = content.split()
            if len(words) < 20:
                add_to_evaluation('abstract_02', link)
    else:
        add_to_evaluation('abstract_01', link)


def check_keywords(eml_node, packageid):
    link = url_for(PAGE_KEYWORD_SELECT, packageid=packageid)
    keyword_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.KEYWORDSET, names.KEYWORD])
    if not keyword_nodes:
        add_to_evaluation('keywords_01', link)
    elif len(keyword_nodes) < 5:
        add_to_evaluation('keywords_02', link)


def check_intellectual_rights(eml_node, packageid):
    link = url_for(PAGE_INTELLECTUAL_RIGHTS, packageid=packageid)
    intellectual_rights_node = eml_node.find_single_node_by_path([names.DATASET, names.INTELLECTUALRIGHTS])
    if not (intellectual_rights_node and intellectual_rights_node.content):
        add_to_evaluation('intellectual_rights_01', link)


def check_coverage(eml_node, packageid):
    link = url_for(PAGE_GEOGRAPHIC_COVERAGE_SELECT, packageid=packageid)
    # At least one of geographicCoverage, temporalCoverage, or taxonomicCoverage is recommended
    geographic_coverage_nodes = eml_node.find_single_node_by_path([names.DATASET, names.COVERAGE, names.GEOGRAPHICCOVERAGE])
    temporal_coverage_nodes = eml_node.find_single_node_by_path([names.DATASET, names.COVERAGE, names.TEMPORALCOVERAGE])
    taxonomic_coverage_nodes = eml_node.find_single_node_by_path([names.DATASET, names.COVERAGE, names.TAXONOMICCOVERAGE])
    if not any([geographic_coverage_nodes, temporal_coverage_nodes, taxonomic_coverage_nodes]):
        add_to_evaluation('coverage_01', link)


def check_geographic_coverage(eml_node, packageid):
    link = url_for(PAGE_GEOGRAPHIC_COVERAGE_SELECT, packageid=packageid)
    geographic_coverage_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.COVERAGE, names.GEOGRAPHICCOVERAGE])
    for geographic_coverage_node in geographic_coverage_nodes:
        link = url_for(PAGE_GEOGRAPHIC_COVERAGE, packageid=packageid, node_id=geographic_coverage_node.id)
        if not child_content(geographic_coverage_node, names.GEOGRAPHICDESCRIPTION):
            add_to_evaluation('geographic_coverage_01', link)
        wbc = is_float(descendant_content(geographic_coverage_node, [names.BOUNDINGCOORDINATES, names.WESTBOUNDINGCOORDINATE]))
        ebc = is_float(descendant_content(geographic_coverage_node, [names.BOUNDINGCOORDINATES, names.EASTBOUNDINGCOORDINATE]))
        nbc = is_float(descendant_content(geographic_coverage_node, [names.BOUNDINGCOORDINATES, names.NORTHBOUNDINGCOORDINATE]))
        sbc = is_float(descendant_content(geographic_coverage_node, [names.BOUNDINGCOORDINATES, names.SOUTHBOUNDINGCOORDINATE]))
        if not all((wbc, ebc, nbc, sbc)):
            add_to_evaluation('geographic_coverage_02', link)


def get_attribute_type(attrib_node:Node):
    mscale_node = attrib_node.find_child(names.MEASUREMENTSCALE)
    nominal_node = mscale_node.find_child(names.NOMINAL)
    if nominal_node:
        enumerated_domain_node = nominal_node.find_single_node_by_path([names.NONNUMERICDOMAIN, names.ENUMERATEDDOMAIN])
        if enumerated_domain_node:
            return VariableType.CATEGORICAL
        text_domain_node = nominal_node.find_single_node_by_path([names.NONNUMERICDOMAIN, names.TEXTDOMAIN])
        if text_domain_node:
            return VariableType.TEXT
    ratio_node = mscale_node.find_child(names.RATIO)
    if ratio_node:
        return VariableType.NUMERICAL
    datetime_node = mscale_node.find_child(names.DATETIME)
    if datetime_node:
        return VariableType.DATETIME
    return None


def check_categorical_codes(eml_node, packageid, data_table_node:Node, attrib_node:Node):
    code_definition_nodes = attrib_node.find_all_nodes_by_path([
        names.MEASUREMENTSCALE,
        names.NOMINAL,
        names.NONNUMERICDOMAIN,
        names.ENUMERATEDDOMAIN,
        names.CODEDEFINITION
    ])
    if not code_definition_nodes:
        link = url_for(PAGE_ATTRIBUTE_CATEGORICAL, packageid=packageid, dt_node_id=data_table_node.id, node_id=attrib_node.id,
                       mscale=VariableType.CATEGORICAL.name)
        add_to_evaluation('attributes_04', link)
    else:
        nominal_node = attrib_node.find_single_node_by_path([
            names.MEASUREMENTSCALE,
            names.NOMINAL])

        for code_definition_node in code_definition_nodes:
            link = url_for(PAGE_CODE_DEFINITION, packageid=packageid,
                           dt_node_id=data_table_node.id,
                           att_node_id=attrib_node.id,
                           nom_ord_node_id=nominal_node.id,
                           node_id=code_definition_node.id,
                           mscale=VariableType.CATEGORICAL.name)
            code_node = code_definition_node.find_child(names.CODE)
            if not (code_node and code_node.content):
                add_to_evaluation('attributes_05', link)
            definition_node = code_definition_node.find_child(names.DEFINITION)
            if not (definition_node and definition_node.content):
                add_to_evaluation('attributes_06', link)


def check_datetime_attribute(eml_node, packageid, data_table_node:Node, attrib_node:Node):
    link = url_for(PAGE_ATTRIBUTE_DATETIME, packageid=packageid, dt_node_id=data_table_node.id, node_id=attrib_node.id,
                   mscale=VariableType.NUMERICAL.name)
    format_node = attrib_node.find_single_node_by_path([
        names.MEASUREMENTSCALE,
        names.DATETIME,
        names.FORMATSTRING
    ])
    if not (format_node and format_node.content):
        add_to_evaluation('attributes_03', link)


def check_numerical_attribute(eml_node, packageid, data_table_node:Node, attrib_node:Node):
    link = url_for(PAGE_ATTRIBUTE_NUMERICAL, packageid=packageid, dt_node_id=data_table_node.id, node_id=attrib_node.id,
                   mscale=VariableType.NUMERICAL.name)
    standard_unit_node = attrib_node.find_single_node_by_path([
        names.MEASUREMENTSCALE,
        names.RATIO,
        names.UNIT,
        names.STANDARDUNIT
    ])
    custom_unit_node = None
    if not standard_unit_node:
        custom_unit_node = attrib_node.find_single_node_by_path([
            names.MEASUREMENTSCALE,
            names.RATIO,
            names.UNIT,
            names.CUSTOMUNIT
        ])
    if not (
        (custom_unit_node and custom_unit_node.content) or standard_unit_node
    ):
        add_to_evaluation('attributes_02', link)


def check_attribute(eml_node, packageid, data_table_node:Node, attrib_node:Node):
    attr_type = get_attribute_type(attrib_node)
    mscale = None
    if attr_type == VariableType.CATEGORICAL:
        page = PAGE_ATTRIBUTE_CATEGORICAL
        mscale = VariableType.CATEGORICAL.name
    elif attr_type == VariableType.NUMERICAL:
        page = PAGE_ATTRIBUTE_NUMERICAL
        mscale = VariableType.NUMERICAL.name
    elif attr_type == VariableType.TEXT:
        page = PAGE_ATTRIBUTE_TEXT
        mscale = VariableType.TEXT.name
    elif attr_type == VariableType.DATETIME:
        page = PAGE_ATTRIBUTE_DATETIME
        mscale = VariableType.DATETIME.name
    link = url_for(page, packageid=packageid, dt_node_id=data_table_node.id, node_id=attrib_node.id, mscale=mscale)
    attribute_definition_node = attrib_node.find_child(names.ATTRIBUTEDEFINITION)
    if not (attribute_definition_node and attribute_definition_node.content):
        add_to_evaluation('attributes_01', link)
    if mscale == VariableType.CATEGORICAL.name:
        check_categorical_codes(eml_node, packageid, data_table_node, attrib_node)
    elif mscale == VariableType.DATETIME.name:
        check_datetime_attribute(eml_node, packageid, data_table_node, attrib_node)
    elif mscale == VariableType.NUMERICAL.name:
        check_numerical_attribute(eml_node, packageid, data_table_node, attrib_node)


def check_data_table(eml_node, packageid, data_table_node:Node):
    link = url_for(PAGE_DATA_TABLE, packageid=packageid, node_id=data_table_node.id)
    if not child_content(data_table_node, names.ENTITYNAME):
        add_to_evaluation('data_table_01', link)
    if not child_content(data_table_node, names.ENTITYDESCRIPTION):
        add_to_evaluation('data_table_02', link)
    if not descendant_content(data_table_node, [names.PHYSICAL, names.OBJECTNAME]):
        add_to_evaluation('data_table_03', link)
    attribute_list_node = data_table_node.find_child(names.ATTRIBUTELIST)
    if not attribute_list_node:
        add_to_evaluation('data_table_04', link)
    attribute_nodes = attribute_list_node.find_all_children(names.ATTRIBUTE)
    for attribute_node in attribute_nodes:
        check_attribute(eml_node, packageid, data_table_node, attribute_node)


def check_data_tables(eml_node, packageid):
    link = url_for(PAGE_DATA_TABLE_SELECT, packageid=packageid)
    data_table_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.DATATABLE])
    if not data_table_nodes:
        add_to_evaluation('data_table_05', link)
    else:
        for data_table_node in data_table_nodes:
            check_data_table(eml_node, packageid, data_table_node)


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
    sections = ['Title', 'Creators', 'Metadata Providers', 'Associated Parties', 'Abstract', 'Keywords',
                'Intellectual Rights', 'Coverage', 'Geographic Coverage', 'Temporal Coverage',
                'Taxonomic Coverage', 'Maintenance', 'Contacts', 'Methods', 'Project', 'Data Tables',
                'Other Entities']

    severities = [EvalSeverity.ERROR, EvalSeverity.WARNING, EvalSeverity.INFO]

    all_ok = True
    output = '<span style="font-family: Helvetica,Arial,sans-serif;">'
    for section in sections:
        entries = collect_entries(evaluation, section)
        if not entries:
            continue
        all_ok = False
        output += f'<h3>{section}</h3><table class="eval_table" width=100% style="padding: 10px;"><tr><th class="eval_table" align="left" width=17%>Item</th>' \
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


def check_eml(packageid:str):
    global evaluation
    evaluation = []
    eml_node = load_eml(packageid)
    check_dataset_title(eml_node, packageid)
    check_creators(eml_node, packageid)
    check_metadata_providers(eml_node, packageid)
    check_associated_parties(eml_node, packageid)
    check_dataset_abstract(eml_node, packageid)
    check_keywords(eml_node, packageid)
    check_intellectual_rights(eml_node, packageid)
    check_coverage(eml_node, packageid)
    check_geographic_coverage(eml_node, packageid)
    check_data_tables(eml_node, packageid)
    return format_output(evaluation)





