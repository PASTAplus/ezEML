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
from lxml import etree #pt7/16

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


def clean_mother_node(eml_node: Node, current_document: None):
    additional_metadata_node = eml_node.find_child(names.ADDITIONALMETADATA)
    if additional_metadata_node:
        meta_node = additional_metadata_node.find_child('metadata')
        mother_node = meta_node.find_child('mother')
        if mother_node:
            cleaned_mother_node = local_to_xml(mother_node, 0)
            user_folder = user_data.get_user_folder_name()
            test_filename = f'{user_folder}/{current_document}.xml'
            with open(test_filename, "r+") as fh:
                tree = etree.parse(fh)
                root = tree.getroot()
                additionalmetadata = root.find('additionalMetadata')
                metadata = additionalmetadata.find('metadata')
                mother = metadata.find('mother')
                metadata.remove(mother)
                my_tree = etree.ElementTree(etree.fromstring(cleaned_mother_node))
                my_root = my_tree.getroot()
                metadata.append(my_root)
                # THIS OVERWRITES THE XML FILE WITH NEW MDB PREFIXES
                tree.write(f'{user_folder}/{current_document}.xml')




def local_to_xml(node: Node, level: int = 0) -> str:
    space = "            "
    xml = ""
    closed = False
    boiler = (
        'xmlns:mdb="http://mother-db.org/mdb" ' 
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" ' 
        'xsi:schemaLocation="http://mother-db.org/mdb https://raw.githubusercontent.com/mother-db/public/main/mdb.xsd"'
    )
    name = node.name
    attributes = ""
    for attribute in node.attributes:
        attributes += ' {0}="{1}"'.format(
            attribute, node.attributes[attribute]
        )
    if level == 0:
        attributes += " " + boiler
#    indent = ""
#PT7/10        if name == "mother":
    name = "mdb" + ":" + node.name
#    else:
    indent = space * level
    if level == 2:
        indent = space + "    "
    if level == 3:
        indent = space + "        "
    open_tag = "<" + name + attributes + ">"
    close_tag = "</" + name + ">"
    xml += indent + open_tag
    if node.content is not None:
        if isinstance(node.content, str):
            # if it hasn't been escaped already, escape it
            if all (x not in node.content for x in ('&amp;', '&lt;', '&gt;')):
                node.content = escape(node.content)
                # Hopefully, this is a temporary hack. Need to figure out a better way...
                # The problem is that <para> tags are treated idiosyncratically because their rules aren't fully
                #  supported. They appear within node content, unlike other tags.
                node.content = node.content.replace('&lt;para&gt;', '<para>').replace('&lt;/para&gt;', '</para>')
        xml += str(node.content) + close_tag + "\n"
        closed = True
    elif len(node.children) > 0:
        xml += "\n"
    for child in node.children:
        xml += local_to_xml(child, level + 1)
    if not closed:
        if len(node.children) > 0:
            xml += indent
        xml += close_tag + "\n"
    return xml