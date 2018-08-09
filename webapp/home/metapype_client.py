#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: metapype_client.py

:Synopsis:

:Author:
    costa

:Created:
    7/27/18
"""
import daiquiri
import json
import os.path

from metapype.eml2_1_1 import export, validate, names
from metapype.model.node import Node
from metapype.model import io


logger = daiquiri.getLogger('metapyp_client: ' + __name__)

def add_rps_to_dict(eml_node:Node=None, node_name:str=None, rp_dict:dict=None):
    if eml_node:
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            rp_nodes = dataset_node.find_all_children(node_name)
            for rp_node in rp_nodes:
                rp_label = compose_rp_label(rp_node)
                rp_dict[rp_label] = rp_node.id


def compose_rp_label(rp_node:Node=None):
    label = ''
    if rp_node:
        individual_name_node = rp_node.find_child(names.INDIVIDUALNAME)
        individual_name_label = compose_individual_name_label(individual_name_node)
        organization_name_label = compose_simple_label(rp_node, names.ORGANIZATIONNAME)
        position_name_label = compose_simple_label(rp_node, names.POSITIONNAME)
        
        if individual_name_label:
            label = individual_name_label
        if position_name_label:
            label = label + ', ' + position_name_label
        if organization_name_label:
            label = label + ', ' + organization_name_label
    return label


def compose_individual_name_label(rp_node:Node=None):
    label = ''
    if rp_node:
        salutation_nodes = rp_node.find_all_children(names.SALUTATION)
        if salutation_nodes:
            for salutation_node in salutation_nodes:
                if salutation_node and salutation_node.content:
                    label = label + " " + salutation_node.content
        
        given_name_nodes = rp_node.find_all_children(names.GIVENNAME)
        if given_name_nodes:
            for given_name_node in given_name_nodes:
                if given_name_node and given_name_node.content:
                    label = label + " " + given_name_node.content
        
        surname_node = rp_node.find_child(names.SURNAME)
        if surname_node and surname_node.content:
            label = label + " " + surname_node.content

    return label


def compose_simple_label(rp_node:Node=None, child_node_name:str=''):
    label = ''
    if rp_node and child_node_name:
        child_node = rp_node.find_child(child_node_name)
        if child_node and child_node.content:
            label = child_node.content
    return label


def load_eml(packageid:str=None):
    eml_node = None
    filename = f"{packageid}.json"
    if os.path.isfile(filename):
        with open(filename, "r") as json_file:
            json_obj = json.load(json_file)
            eml_node = io.from_json(json_obj)
    return eml_node


def store_eml(packageid:str=None, eml_node:Node=None):
    if packageid and eml_node:
        pass
        #session[packageid] = eml_node


def retrieve_eml(packageid:str=None):
    eml_node = None
    if packageid:
        pass
        #eml_node = session[packageid]
    return eml_node


def log_as_xml(node: Node):
    xml_str = export.to_xml(node)
    logger.info("\n\n" + xml_str)


def save_both_formats(packageid:str=None, eml_node:Node=None):
    save_eml(packageid=packageid, eml_node=eml_node, format='json')
    save_eml(packageid=packageid, eml_node=eml_node, format='xml')


def save_eml(packageid:str=None, eml_node:Node=None, format:str='json'):
    if packageid:
        if eml_node is not None:
            metadata_str = None

            if format == 'json':
                metadata_str = io.to_json(eml_node)
            elif format == 'xml':
                xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
                xml_str = export.to_xml(eml_node)
                metadata_str = xml_declaration + xml_str
            
            if metadata_str:
                filename = f"{packageid}.{format}"
                with open(filename, "w") as fh:
                    fh.write(metadata_str)
        else:
            raise Exception(f"No EML node was supplied for saving EML.")
    else:
        raise Exception(f"No packageid value was supplied for saving EML.")


def validate_tree(node:Node):
    msg = ''
    if node:
        try:
            validate.tree(node)
            msg = f"{node.name} node is valid"
        except Exception as e:
            msg = str(e)

    return msg
