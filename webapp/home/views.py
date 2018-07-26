#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: views.py

:Synopsis:

:Author:
    servilla

:Created:
    3/6/18
"""
import daiquiri
import json
from flask import Blueprint, flash, render_template, redirect, url_for
from webapp.home.forms import CreateEMLForm, KeywordsForm, MinimalEMLForm
from metapype.eml2_1_1.exceptions import MetapypeRuleError
from metapype.eml2_1_1 import export
from metapype.eml2_1_1 import evaluate
from metapype.eml2_1_1 import names
from metapype.eml2_1_1 import rule
from metapype.eml2_1_1 import validate
from metapype.model.node import Node
from metapype.model import io


logger = daiquiri.getLogger('views: ' + __name__)
home = Blueprint('home', __name__, template_folder='templates')


@home.route('/')
def index():
    return render_template('index.html')


@home.route('/about')
def about():
    return render_template('about.html')


@home.route('/create', methods=['GET', 'POST'])
def create():
    # Process POST
    form = CreateEMLForm()
    if form.validate_on_submit():
        packageid = form.packageid.data
        create_eml(packageid=packageid,
                   title=form.title.data,
                   abstract=form.abstract.data)
        return redirect(url_for('home.keywords', packageid=packageid))
    # Process GET
    return render_template('create_eml.html', title='Create New EML', form=form)


@home.route('/keywords/<packageid>', methods=['GET', 'POST'])
def keywords(packageid=None):
    # Process POST
    form = KeywordsForm(packageid=packageid)
    if form.validate_on_submit():
        keywords_list = []
        append_if_non_empty(keywords_list, form.k01.data)
        append_if_non_empty(keywords_list, form.k02.data)
        append_if_non_empty(keywords_list, form.k03.data)
        append_if_non_empty(keywords_list, form.k04.data)
        append_if_non_empty(keywords_list, form.k05.data)
        append_if_non_empty(keywords_list, form.k06.data)
        append_if_non_empty(keywords_list, form.k07.data)
        append_if_non_empty(keywords_list, form.k08.data)
        create_keywords(packageid=packageid, keywords_list=keywords_list)
        return redirect(url_for('home.keywords', packageid=packageid))
    # Process GET
    return render_template('keywords.html', title='Keywords', packageid=packageid, form=form)


def append_if_non_empty(some_list: list, value: str):
    if (value is not None and len(value) > 0):
        some_list.append(value)


@home.route('/minimal', methods=['GET', 'POST'])
def minimal():
    # Process POST
    form = MinimalEMLForm()
    if form.validate_on_submit():
        validate_minimal(packageid=form.packageid.data,
                         title=form.title.data, 
                         creator_gn=form.creator_gn.data, 
                         creator_sn=form.creator_sn.data,
                         contact_gn=form.contact_gn.data, 
                         contact_sn=form.contact_sn.data)
    # Process GET
    return render_template('minimal_eml.html', title='Minimal EML', form=form)


def create_eml(packageid=None, title=None, abstract=None):
    eml_node = Node(names.EML)

    eml_node.add_attribute('packageId', packageid)
    eml_node.add_attribute('system', 'https://pasta.edirepository.org')

    dataset_node = Node(names.DATASET, parent=eml_node)
    eml_node.add_child(dataset_node)

    title_node = Node(names.TITLE)
    title_node.content = title
    dataset_node.add_child(title_node)

    abstract_node = Node(names.ABSTRACT)
    abstract_node.content = abstract
    dataset_node.add_child(abstract_node)

    validate_node(eml_node)

    try:
        save_eml(packageid=packageid, eml_node=eml_node)
    except Exception as e:
        logger.error(e)


def create_keywords(packageid:str=None, keywords_list:list=[]):
    logger.info(f"The keywords are: {keywords_list}")
    if len(keywords_list) > 0:
        try:
            eml_node = load_eml(packageid=packageid)
            logger.info(f"loaded the following package: {packageid} containing eml node: {eml_node}")
            dataset_node = eml_node.find_child('dataset')
            keywordset_node = Node(names.KEYWORDSET)
            dataset_node.add_child(keywordset_node)

            for keyword in keywords_list:
                keyword_node = Node(names.KEYWORD)
                keyword_node.content = keyword
                keywordset_node.add_child(keyword_node)

            validate_node(eml_node)
            log_as_xml(eml_node)
            save_eml(packageid=packageid, eml_node=eml_node)

        except Exception as e:
            logger.error(e)


def log_as_xml(node: Node):
    xml_str = export.to_xml(node)
    logger.info("\n\n" + xml_str)


def save_eml(packageid:str=None, eml_node:Node=None):
    if packageid is not None:
        if eml_node is not None:
            json_str = io.to_json(eml_node)
            filename = f"{packageid}.json"
            with open(filename, "w") as fh:
                fh.write(json_str)
        else:
            raise Exception(f"No EML node was supplied for saving EML.")
    else:
        raise Exception(f"No packageid value was supplied for saving EML.")


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


def validate_minimal(packageid=None, title=None, contact_gn=None, contact_sn=None, creator_gn=None, creator_sn=None):
    eml = Node(names.EML)

    eml.add_attribute('packageId', packageid)
    eml.add_attribute('system', 'https://pasta.edirepository.org')

    dataset = Node(names.DATASET, parent=eml)
    eml.add_child(dataset)

    title_node = Node(names.TITLE)
    title_node.content = title
    dataset.add_child(title_node)
    
    creator_node = Node(names.CREATOR, parent=dataset)
    dataset.add_child(creator_node)

    individualName_creator = Node(names.INDIVIDUALNAME, parent=creator_node)
    creator_node.add_child(individualName_creator)

    givenName_creator = Node(names.GIVENNAME, parent=individualName_creator)
    givenName_creator.content = creator_gn
    individualName_creator.add_child(givenName_creator)

    surName_creator = Node(names.SURNAME, parent=individualName_creator)
    surName_creator.content = creator_sn
    individualName_creator.add_child(surName_creator)

    contact_node = Node(names.CONTACT, parent=dataset)
    dataset.add_child(contact_node)

    individualName_contact = Node(names.INDIVIDUALNAME, parent=contact_node)
    contact_node.add_child(individualName_contact)

    givenName_contact = Node(names.GIVENNAME, parent=individualName_contact)
    givenName_contact.content = contact_gn
    individualName_contact.add_child(givenName_contact)

    surName_contact = Node(names.SURNAME, parent=individualName_contact)
    surName_contact.content = contact_sn
    individualName_contact.add_child(surName_contact)

    xml_str =  export.to_xml(eml)
    print(xml_str)
    validate_node(eml)


def validate_node(node:Node):
    if (node is not None):
        try:
            validate.tree(node)
            flash(f"{node.name} node is valid")
        except Exception as e:
            flash(str(e))
