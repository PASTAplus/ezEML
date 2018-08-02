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

from metapype.eml2_1_1 import export, validate
from metapype.model.node import Node
from metapype.model import io


logger = daiquiri.getLogger('metapyp_client: ' + __name__)

def load_eml(packageid:str=None):
    eml_node = None
    filename = f"{packageid}.json"
    with open(filename, "r") as json_file:
        json_obj = json.load(json_file)
        eml_node = io.from_json(json_obj)
    if eml_node is not None:
        log_as_xml(eml_node)
    else:
        raise Exception(f"Error loading package ID: {packageid} from file {filename}")
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
