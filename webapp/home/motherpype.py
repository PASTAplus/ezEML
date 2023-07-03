""":Mod: motherpype.py

:Synopsis:
    This file ensures the mother xml is formatted correctly during download

:Author:
    Pierce Tyler

:Created:
    7/17/22
"""
import collections
import daiquiri
from enum import Enum
import html
import json
import math
import re
from lxml import etree  # pt7/16

import logging
from logging import Formatter
from logging.handlers import RotatingFileHandler
from xml.sax.saxutils import escape, unescape

import os
from os import listdir
from os.path import isfile, join

from flask import Flask, flash, session, current_app
from flask_login import (
    current_user
)

from webapp.config import Config

from metapype.eml import export, evaluate, validate, names, rule
from metapype.model.node import Node, Shift
from metapype.model import mp_io, metapype_io

import webapp.home.motherpype_names as mdb_names

from webapp.home.metapype_client import (
    save_both_formats, load_eml
)

from webapp.home.check_metadata import check_metadata_status

import webapp.auth.user_data as user_data

if Config.LOG_DEBUG:
    app = Flask(__name__)
    with app.app_context():
        cwd = os.path.dirname(os.path.realpath(__file__))
        logfile = cwd + '/metadata-eml-threads.log'
        file_handler = RotatingFileHandler(logfile, maxBytes=1000000000, backupCount=10)
        file_handler.setFormatter(Formatter(
            '%(asctime)s %(levelname)s [pid:%(process)d tid:%(thread)d]: %(message)s [in %(pathname)s:%(lineno)d]'))
        file_handler.setLevel(logging.INFO)
        current_app.logger.addHandler(file_handler)
        current_app.logger.setLevel(logging.INFO)
        current_app.logger.info('*** RESTART ***')

logger = daiquiri.getLogger('metapype_client: ' + __name__)

"""
if Config.LOG_DEBUG:
    app = Flask(__name__)
    with app.app_context():
        cwd = os.path.dirname(os.path.realpath(__file__))
        logfile = cwd + '/metadata-eml-threads.log'
        file_handler = RotatingFileHandler(logfile, maxBytes=1000000000, backupCount=10)
        file_handler.setFormatter(Formatter(
            '%(asctime)s %(levelname)s [pid:%(process)d tid:%(thread)d]: %(message)s [in %(pathname)s:%(lineno)d]'))
        file_handler.setLevel(logging.INFO)
        current_app.logger.addHandler(file_handler)
        current_app.logger.setLevel(logging.INFO)
        current_app.logger.info('*** RESTART ***')

logger = daiquiri.getLogger('metapype_client: ' + __name__)

RELEASE_NUMBER = '2021.10.27'

NO_OP = ''
UP_ARROW = html.unescape('&#x25B2;')
DOWN_ARROW = html.unescape('&#x25BC;')


class Optionality(Enum):
    REQUIRED = 1
    OPTIONAL = 2
    FORCE = 3


class VariableType(Enum):
    CATEGORICAL = 1
    DATETIME = 2
    NUMERICAL = 3
    TEXT = 4
"""

"""
    Function:   clean_mother_node
    Params:     eml_node : the root of the xml tree
                current_document : current document selected
    Desc:       This function pulls the mother node starting from the eml node (root)
                then uses that (if it exists) to call other functions that correctly map 
                the mother node and its children according to the .xsd 
"""


def clean_mother_node(eml_node: Node, current_document: None):
    additional_metadata_node = eml_node.find_child(names.ADDITIONALMETADATA)
    if additional_metadata_node:
        meta_node = additional_metadata_node.find_child('metadata')
        mother_node = meta_node.find_child('mother')
        if mother_node:
            remove_empty_nodes(mother_node)
            clean_mother_json(mother_node, 0)
            clean_mother_xml(mother_node, current_document)


"""
    Function:   clean_mother_xml
    Params:     mother_node : the root of the motherDb xml tree (a child of metadata)
                current_document : current document selected
    Desc:       This function calls to_xml_json and uses the result to properly update 
                the current document xml file
"""


def clean_mother_xml(mother_node: Node, current_document):
    cleaned_mother_node = to_xml_json(mother_node, None, 6)
    user_folder = user_data.get_user_folder_name()
    filename = f'{user_folder}/{current_document}.xml'
    with open(filename, "r+") as fh:
        tree = etree.parse(fh)
        root = tree.getroot()
        additionalmetadata = root.find('additionalMetadata')
        metadata = additionalmetadata.find('metadata')
        mother = metadata.find('mother')
        metadata.remove(mother)
        mother_tree = etree.ElementTree(etree.fromstring(cleaned_mother_node))   # WB 12/09 NEED TO FIX: Pretty sure this is the point where the downloaded xml has the mother and metadata closing tags end up on the same line.
        mother_root = mother_tree.getroot()
        metadata.append(mother_root)
        # THIS OVERWRITES THE XML FILE WITH NEW MDB PREFIXES
        tree.write(f'{user_folder}/{current_document}.xml')

"""
    Function:   remove_empty_nodes
    Params:     node : a node within the motherDb xml tree
    Desc:       This function uses recursion to iterate through each node and remove any nodes that are
                optional (it relies on the motherpype_names.py file)
                
"""

def remove_empty_nodes(node: Node, parent: Node = None):
    array = []
    if node.name in mdb_names.OPTIONAL:
        if len(node.children) == 0:
            if node.content is None:
                parent.remove_child(node)
    else:
        if len(node.children) > 0:
            for child in node.children:
                remove_empty_nodes(child, node)

"""
    Function:   clean_mother_json
    Params:     node : a node within the motherDb xml tree
                level : the level within the xml tree the node stands
                Example: mother node = 0, any direct children of mother node = level 1
                        any children of those children = level 2 etc
    Desc:       This function uses recursion to iterate through each node and update it
                correctly according to the xsd (it relies on the motherpype_names.py file)
                
"""

def clean_mother_json(node: Node, level: int = 0) -> str:

    node.prefix = mdb_names.MOTHER_PREFIX
    if level == 0:
        node.add_namespace(node.prefix, "http://mother-db.org/mdb")
        node.add_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")
        node.add_extras("xsi:schemaLocation",
                        "http://mother-db.org/mdb https://resources.mother-db.org/xml/1.1/mdb.xsd")
    else:
        if node.name in mdb_names.SET_VALUE_NODES:
            if not "value" in node.attributes:    # if there is already a value= set, delete it and create a new one
                node.add_extras("value", node.content)
            node.content = ""  # if the node value is an attribute, delete the content after adding it as such
            
    if node.name in mdb_names.XSI_TYPE:
        node.add_extras("xsi:type", mdb_names.XSI_TYPE[node.name])

    if node.name in mdb_names.NILLABLE:
        if len(node.children) > 0:
            if all((c.content is None or c.content == "") and c.name != mdb_names.STAGE_OF_CYCLE for c in node.children):
                node.add_extras("xsi:nil", "true")
                node.remove_children()
            else:
                node.extras.pop('xsi:nil', None)
        elif len(node.children) == 0 and (node.content is None or node.content == ""):
            node.add_extras("xsi:nil", "true")
        elif node.content is not None:
            node.extras.pop('xsi:nil', None)

    for child in node.children:
        child_node = node.find_child(child.name)
        if child_node:
            clean_mother_json(child_node, level + 1)


"""
    Function:   to_xml_json
    Params:     node : a node within the motherDb xml tree
                level : the level within the xml tree the node stands
                Example: mother node = 0, any direct children of mother node = level 1
                        any children of those children = level 2 etc
    Desc:       This function uses recursion to iterate through each node (starting with 
                the mother node) and update it properly according to the json file
                (the json file is updated prior in the function 'clean_mother_json')
    Return:     A string in xml format
"""


def to_xml_json(node: Node, parent: Node = None, level: int = 0) -> str:
    
    #Need to add structure to skip nodes with no content such as lightmicroscopystain
    #Add data structure to catch nil nodes
    
    xml = ""
    spacing = "  "
    indent = spacing * level

    tag = f"{node.name}" if node.prefix is None else f"{node.prefix}:{node.name}"

    attributes = ""
    if len(node.attributes) > 0:
        attributes += " ".join([f"{k}=\"{v}\"" for k, v in node.attributes.items()])

    if parent is None:
        if len(node.nsmap) > 0:
            attributes += " " + " ".join([f"xmlns:{k}=\"{v}\"" for k, v in node.nsmap.items()])
    elif node.nsmap != parent.nsmap:
        nsmap = _nsp_unique(node.nsmap, parent.nsmap)
        if len(nsmap) > 0:
            attributes += " " + " ".join([f"xmlns:{k}=\"{v}\"" for k, v in nsmap.items()])

    if len(node.extras) > 0:
        attributes += " " + " ".join([f"{k}=\"{v}\"" for k, v in node.extras.items()])

    if len(attributes) > 0:
        # Add final prefix-space to attribute string
        attributes = " " + attributes.lstrip()

    if node.content is None and len(node.children) == 0:
        open_tag = f"{indent}<{tag}{attributes}/>\n"
        close_tag = ""
    elif node.content is None:
        open_tag = f"{indent}<{tag}{attributes}>\n"
        close_tag = f"{indent}</{tag}>\n"
    else:
        content = escape(node.content)
        open_tag = f"{indent}<{tag}{attributes}>{content}"
        close_tag = f"</{tag}>\n"

    if node.tail is not None:
        tail = escape(node.tail)
        close_tag += tail

    xml += open_tag
    for child in node.children:
        xml += to_xml_json(child, node, level + 1)
    xml += close_tag
    return xml


def _nsp_unique(child_nsmap: dict, parent_nsmap: dict) -> dict:
    nsmap = dict()
    for child_nsp in child_nsmap:
        if child_nsp in parent_nsmap:
            if child_nsmap[child_nsp] != parent_nsmap[child_nsp]:
                nsmap[child_nsp] = child_nsmap[child_nsp]
        else:
            nsmap[child_nsp] = child_nsmap[child_nsp]
    return nsmap


"""
    Function:       add_mother_metadata
    Params:         eml_node : root of the eml xml tree
    Description:    creates the mother node and donor nodes 
                    (and metadata nodes if none exists)
"""



def add_mother_metadata(eml_node: Node = None, filename=None):
    additional_metadata_node = eml_node.find_child(names.ADDITIONALMETADATA)
    if additional_metadata_node:
        metadata_node = additional_metadata_node.find_child(names.METADATA)
        mother_node = Node("mother", parent=additional_metadata_node)
        create_donor(mother_node)
        metadata_node.add_child(mother_node)
    else:
        additional_metadata_node = Node(names.ADDITIONALMETADATA, parent=eml_node)
        eml_node.add_child(additional_metadata_node)
        metadata_node = Node(names.METADATA, parent=additional_metadata_node)
        additional_metadata_node.add_child(metadata_node)
        mother_node = Node("mother", parent=additional_metadata_node)
        create_donor(mother_node)
        metadata_node.add_child(mother_node)

    try:
        save_both_formats(filename=filename, eml_node=eml_node)
    except Exception as e:
        logger.error(e)


"""
    Function:       create_donor
    Params:         the values of all elements of the donor html form page
    Description:    creates and populates the values of the donor nodes
"""


def create_donor(mother_node: Node,
                 filename: str = None,
                 donorId: str = None,
                 donorSex: str = None,
                 ageType: Node = None,
                 ageYears: int = None,
                 ageDays: int = None,
                 lifeStage: str = None,
                 specimenSeqNum: int = None,
                 specimenTissue: str = None,
                 ovaryPosition: str = None,
                 specimenLocation: str = None,
                 dayOfCycle: str = None,
                 stageOfCycle: str = None,
                 follicularType: str = None,
                 lutealType: str = None,
                 slideID: str = None,
                 sectionSeqNum: int = None,
                 sectionThicknessType: Node = None,
                 sectionThickness: int = None,
                 sectionThicknessUnit: str = None,
                 sampleProcessingType: Node = None,
                 fixation: str = None,
                 fixationOther: str = None,
                 stain: str = None,
                 stainType: Node = None,
                 stainLightType: str = None,
                 sudanStainType: str = None,
                 stainLightOther: str = None,
                 stainFluorescentType: str = None,
                 stainFluorescentOther: str = None,
                 stainElectronType: str = None,
                 stainElectronOther: str = None,
                 magnification: str = None,
                 microscopeType: Node = None,
                 maker: str = None,
                 model: str = None,
                 notes: str = None):
    try:
        ihc_original = mother_node.find_child(mdb_names.IHC)
        ihc_node = Node(mdb_names.IHC, parent=mother_node)
        if ihc_original:
            ihc_node = ihc_original.copy()
        mother_node.remove_children()

        # if donorId:
        donorId_node = Node(mdb_names.DONOR_ID, parent=mother_node)
        mother_node.add_child(donorId_node)
        donorId_node.content = donorId
        # if donorSex:
        donorSex_node = Node(mdb_names.DONOR_SEX, parent=mother_node)
        mother_node.add_child(donorSex_node)
        donorSex_node.content = donorSex
        # if ageType:
        ageType_node = Node(mdb_names.DONOR_AGE, parent=mother_node)
        mother_node.add_child(ageType_node)
        # if ageYears:
        ageYears_node = Node(mdb_names.DONOR_YEARS, parent=ageType_node)
        ageType_node.add_child(ageYears_node)
        ageYears_node.content = ageYears
        # if ageDays:
        ageDays_node = Node(mdb_names.DONOR_DAYS, parent=ageType_node)
        ageType_node.add_child(ageDays_node)
        ageDays_node.content = ageDays
        # if lifeStage:
        lifeStage_node = Node(mdb_names.DONOR_LIFE_STAGE, parent=mother_node)
        mother_node.add_child(lifeStage_node)
        lifeStage_node.content = lifeStage
        # if specimenSeqNum:
        specimenSeqNum_node = Node(mdb_names.SPEC_SEQ_NUM, parent=mother_node)
        mother_node.add_child(specimenSeqNum_node)
        specimenSeqNum_node.content = specimenSeqNum
        # if specimenTissue:
        specimenTissue_node = Node(mdb_names.SPEC_TISSUE, parent=mother_node)
        mother_node.add_child(specimenTissue_node)
        specimenTissue_node.content = specimenTissue
        # if ovaryPosition:
        ovaryPosition_node = Node(mdb_names.OVARY_POSITION, parent=mother_node)
        mother_node.add_child(ovaryPosition_node)
        ovaryPosition_node.content = ovaryPosition
        # if specimenLocation:
        specimenLocation_node = Node(mdb_names.SPEC_LOCATION, parent=mother_node)
        mother_node.add_child(specimenLocation_node)
        cycleType_node = Node(mdb_names.SPEC_CYCLE, parent=mother_node)
        mother_node.add_child(cycleType_node)
        # if dayOfCycle:
        dayOfCycle_node = Node(mdb_names.DAY_OF_CYCLE, parent=cycleType_node)
        cycleType_node.add_child(dayOfCycle_node)
        dayOfCycle_node.content = dayOfCycle
        # if stageOfCycle:
        stageOfCycle_node = Node(mdb_names.STAGE_OF_CYCLE, parent=cycleType_node)
        cycleType_node.add_child(stageOfCycle_node)
        slideID_node = Node(mdb_names.SLIDE_ID, parent=mother_node)
        mother_node.add_child(slideID_node)
        slideID_node.content = slideID
        # if sectionSeqNum:
        sectionSeqNum_node = Node(mdb_names.SEC_SEQ_NUM, parent=mother_node)
        mother_node.add_child(sectionSeqNum_node)
        sectionSeqNum_node.content = sectionSeqNum
        # if sectionThicknessType:
        sectionThicknessType_node = Node(mdb_names.SECTION_THICKNESS, parent=mother_node)
        mother_node.add_child(sectionThicknessType_node)
        # if sectionThickness:
        sectionThickness_node = Node(mdb_names.THICKNESS, parent=sectionThicknessType_node)
        sectionThicknessType_node.add_child(sectionThickness_node)
        sectionThickness_node.content = sectionThickness
        # if sectionThicknessUnit:
        sectionThicknessUnit_node = Node(mdb_names.UNIT, parent=sectionThicknessType_node)
        sectionThicknessType_node.add_child(sectionThicknessUnit_node)
        sectionThicknessUnit_node.content = sectionThicknessUnit
        # if sampleProcessingType:
        sampleProcessingType_node = Node(mdb_names.SAMPLE_PROCESS, parent=mother_node)
        mother_node.add_child(sampleProcessingType_node)
        # if fixation:
        fixation_node = Node(mdb_names.FIXATION, parent=sampleProcessingType_node)
        sampleProcessingType_node.add_child(fixation_node)
        stain_node = Node(mdb_names.STAIN, parent=sampleProcessingType_node)
        sampleProcessingType_node.add_child(stain_node)
        magnification_node = Node(mdb_names.MAGNIFICATION, parent=mother_node)
        mother_node.add_child(magnification_node)
        magnification_node.content = magnification

        mother_node.add_child(ihc_node)
        # if microscopeType:
        microscopeType_node = Node(mdb_names.MICROSCOPE, parent=mother_node)
        mother_node.add_child(microscopeType_node)
        # if maker:
        maker_node = Node(mdb_names.MICRO_MAKER, parent=microscopeType_node)
        microscopeType_node.add_child(maker_node)
        maker_node.content = maker
        # if model:
        model_node = Node(mdb_names.MICRO_MODEL, parent=microscopeType_node)
        microscopeType_node.add_child(model_node)
        model_node.content = model
        # if notes:
        notes_node = Node(mdb_names.MICRO_NOTES, parent=microscopeType_node)
        microscopeType_node.add_child(notes_node)
        notes_node.content = notes

        return mother_node

    except Exception as e:
        logger.error(e)


"""
    Function:       create_immunohistochemistry
    Params:         the values of all elements of the ihc html form page
    Description:    creates and populates the values of the ihc nodes
"""


def create_immunohistochemistry(ihc_node: Node,
                                filename: str = None,
                                targetProtein: str = None,
                                primaryAntibody: Node = None,
                                clonality: str = None,
                                targetSpecies: str = None,
                                hostSpecies: str = None,
                                dilution: str = None,
                                lotNumber: str = None,
                                catNumber: str = None,
                                source: Node = None,
                                sourceName: str = None,
                                sourceCity: str = None,
                                sourceState: str = None,
                                rrid: str = None,
                                secondaryAntibody: Node = None,
                                targetSpecies_2: str = None,
                                hostSpecies_2: str = None,
                                dilution_2: str = None,
                                lotNumber_2: str = None,
                                catNumber_2: str = None,
                                source_2: Node = None,
                                sourceName_2: str = None,
                                sourceCity_2: str = None,
                                sourceState_2: str = None,
                                rrid_2: str = None,
                                detectionMethod: str = None):
    try:
        ihc_node.remove_children()
        if targetProtein:
            targetProtein_node = Node(mdb_names.TARGET_PROTEIN, parent=ihc_node)
            ihc_node.add_child(targetProtein_node)
            targetProtein_node.content = targetProtein
        if primaryAntibody:
            primaryAntibody_node = Node(mdb_names.PRIMARY_ANTIBODY, parent=ihc_node)
            ihc_node.add_child(primaryAntibody_node)
        if clonality:
            clonality_node = Node(mdb_names.CLONALITY, parent=primaryAntibody_node)
            primaryAntibody_node.add_child(clonality_node)
            clonality_node.content = clonality
        if targetSpecies:
            targetSpecies_node = Node(mdb_names.TARGET_SPECIES, parent=primaryAntibody_node)
            primaryAntibody_node.add_child(targetSpecies_node)
            targetSpecies_node.content = targetSpecies
        if hostSpecies:
            hostSpecies_node = Node(mdb_names.HOST_SPECIES, parent=primaryAntibody_node)
            primaryAntibody_node.add_child(hostSpecies_node)
            hostSpecies_node.content = hostSpecies
        if dilution:
            dilution_node = Node(mdb_names.DILUTION, parent=primaryAntibody_node)
            primaryAntibody_node.add_child(dilution_node)
            dilution_node.content = dilution
        if lotNumber:
            lotNumber_node = Node(mdb_names.LOT_NUMBER, parent=primaryAntibody_node)
            primaryAntibody_node.add_child(lotNumber_node)
            lotNumber_node.content = lotNumber
        if catNumber:
            catNumber_node = Node(mdb_names.CAT_NUMBER, parent=primaryAntibody_node)
            primaryAntibody_node.add_child(catNumber_node)
            catNumber_node.content = catNumber
        if source:
            source_node = Node(mdb_names.SOURCE, parent=primaryAntibody_node)
            primaryAntibody_node.add_child(source_node)
        if sourceName:
            sourceName_node = Node(mdb_names.SOURCE_NAME, parent=source_node)
            source_node.add_child(sourceName_node)
            sourceName_node.content = sourceName
        if sourceCity:
            sourceCity_node = Node(mdb_names.SOURCE_CITY, parent=source_node)
            source_node.add_child(sourceCity_node)
            sourceCity_node.content = sourceCity
        if sourceState:
            sourceState_node = Node(mdb_names.SOURCE_STATE, parent= source_node)
            source_node.add_child(sourceState_node)
            sourceState_node.content = sourceState
        if rrid:
            rrid_node = Node(mdb_names.RRID, parent=primaryAntibody_node)
            primaryAntibody_node.add_child(rrid_node)
            rrid_node.content = rrid
        if secondaryAntibody:
            secondaryAntibody_node = Node(mdb_names.SECONDARY_ANTIBODY, parent=ihc_node)
            ihc_node.add_child(secondaryAntibody_node)
        if targetSpecies_2:
            targetSpecies_node_2 = Node(mdb_names.TARGET_SPECIES, parent=secondaryAntibody_node)
            secondaryAntibody_node.add_child(targetSpecies_node_2)
            targetSpecies_node_2.content = targetSpecies_2
        if hostSpecies_2:
            hostSpecies_node_2 = Node(mdb_names.HOST_SPECIES, parent=secondaryAntibody_node)
            secondaryAntibody_node.add_child(hostSpecies_node_2)
            hostSpecies_node_2.content = hostSpecies_2
        if dilution_2:
            dilution_node_2 = Node(mdb_names.DILUTION, parent=secondaryAntibody_node)
            secondaryAntibody_node.add_child(dilution_node_2)
            dilution_node_2.content = dilution_2
        if lotNumber_2:
            lotNumber_node_2 = Node(mdb_names.LOT_NUMBER, parent=secondaryAntibody_node)
            secondaryAntibody_node.add_child(lotNumber_node_2)
            lotNumber_node_2.content = lotNumber_2
        if catNumber_2:
            catNumber_node_2 = Node(mdb_names.CAT_NUMBER, parent=secondaryAntibody_node)
            secondaryAntibody_node.add_child(catNumber_node_2)
            catNumber_node_2.content = catNumber_2
        if source_2:
            source_node_2 = Node(mdb_names.SOURCE, parent=secondaryAntibody_node)
            secondaryAntibody_node.add_child(source_node_2)
        if sourceName_2:
            sourceName_node_2 = Node(mdb_names.SOURCE_NAME, parent=source_node_2)
            source_node_2.add_child(sourceName_node_2)
            sourceName_node_2.content = sourceName_2
        if sourceCity_2:
            sourceCity_node_2 = Node(mdb_names.SOURCE_CITY, parent=source_node_2)
            source_node_2.add_child(sourceCity_node_2)
            sourceCity_node_2.content = sourceCity_2
        if sourceState_2:
            sourceState_node_2 = Node(mdb_names.SOURCE_STATE, parent=source_node_2)
            source_node_2.add_child(sourceState_node_2)
            sourceState_node_2.content = sourceState_2
        if rrid_2:
            rrid_node_2 = Node(mdb_names.RRID, parent=secondaryAntibody_node)
            secondaryAntibody_node.add_child(rrid_node_2)
            rrid_node_2.content = rrid
        if detectionMethod:
            detectionMethod_node = Node(mdb_names.DETECTION_METHOD, parent=ihc_node)
            ihc_node.add_child(detectionMethod_node)
            detectionMethod_node.content = detectionMethod

        return ihc_node

    except Exception as e:
        logger.error(e)

def get_image_name_node(filename: str = None, eml_node: Node = None) -> str:
    if not filename:
        filename = user_data.get_active_document()
    if not eml_node:
        eml_node = load_eml(filename)
    entity_name_node = eml_node.find_single_node_by_path([names.DATASET, names.OTHERENTITY, names.ENTITYNAME])
    if entity_name_node:
        return entity_name_node.content
    return None

def get_image_full_name_node(filename: str = None, eml_node: Node = None) -> str:
    if not filename:
        filename = user_data.get_active_document()
    if not eml_node:
        eml_node = load_eml(filename)
    if eml_node:
        object_name_node = eml_node.find_single_node_by_path([names.DATASET, names.OTHERENTITY, names.PHYSICAL, names.OBJECTNAME])
        if object_name_node:
            return object_name_node.content
    return None
