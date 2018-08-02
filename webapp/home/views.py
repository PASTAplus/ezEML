#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: views.py

:Synopsis:

:Author:
    costa
    servilla

:Created:
    7/23/18
"""
import daiquiri
import json
from flask import Blueprint, flash, render_template, \
                  redirect, request, url_for
from webapp.home.forms import CreateEMLForm, TitleForm, \
                              ResponsiblePartyForm, AbstractForm, \
                              KeywordsForm, MinimalEMLForm

from metapype.eml2_1_1 import export
from metapype.eml2_1_1 import names
from metapype.model.node import Node

from webapp.home.metapype_client import load_eml, save_both_formats, \
                                        validate_tree


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
    # Determine POST type
    if request.method == 'POST':
        if 'Back' in request.form:
            submit_type = 'Back'
        elif 'Next' in request.form:
            submit_type = 'Next'
        else:
            submit_type = None
    form = CreateEMLForm()
    # Process POST
    if form.validate_on_submit():
        packageid = form.packageid.data
        create_eml(packageid=packageid)
        new_page = 'title' if (submit_type == 'Next') else 'create'
        return redirect(url_for(f'home.{new_page}', packageid=packageid))
    # Process GET
    return render_template('create_eml.html', title='Create New EML', form=form)


@home.route('/title/<packageid>', methods=['GET', 'POST'])
def title(packageid=None):
    # Determine POST type
    if request.method == 'POST':
        if 'Back' in request.form:
            submit_type = 'Back'
        elif 'Next' in request.form:
            submit_type = 'Next'
        else:
            submit_type = None
    form = TitleForm()
    # Process POST
    if form.validate_on_submit():
        create_title(title=form.title.data, packageid=packageid)
        new_page = 'creator' if (submit_type == 'Next') else 'title'
        return redirect(url_for(f'home.{new_page}', packageid=packageid))
    # Process GET
    eml_node = load_eml(packageid=packageid)
    title_node = eml_node.find_child(child_name='title')
    if title_node:
        form.title.data = title_node.content
    return render_template('title.html', title='Title', form=form)


@home.route('/creator/<packageid>', methods=['GET', 'POST'])
def creator(packageid=None):
    # Determine POST type
    if request.method == 'POST':
        if 'Back' in request.form:
            submit_type = 'Back'
        elif 'Next' in request.form:
            submit_type = 'Next'
        else:
            submit_type = None
    form = ResponsiblePartyForm(responsible_party="Creator", packageid=packageid)

    # Process POST
    if form.validate_on_submit():   
        salutation = form.salutation.data
        gn = form.gn.data
        sn = form.sn.data
        organization = form.organization.data
        position_name = form.position_name.data
        address_1 = form.address_1.data
        address_2 = form.address_2.data
        city = form.city.data
        state = form.state.data
        postal_code = form.postal_code.data
        country = form.country.data
        phone = form.phone.data
        fax = form.fax.data
        email = form.email.data
        online_url = form.online_url.data

        creator_node = Node(names.CREATOR)

        create_responsible_party(
            creator_node,
            packageid,   
            salutation,
            gn,
            sn,
            organization,
            position_name,
            address_1,
            address_2,
            city,
            state,
            postal_code,
            country,
            phone,
            fax,
            email,
            online_url)

        new_page = 'title' if (submit_type == 'Back') else 'abstract'
        return redirect(url_for(f'home.{new_page}', packageid=packageid))
    # Process GET
    eml_node = load_eml(packageid=packageid)
    creator_node = eml_node.find_child(child_name=names.CREATOR)
    if creator_node:
        populate_responsible_party_form(form, creator_node)
    return render_template('responsible_party.html', title='Creator', form=form)


def populate_responsible_party_form(form:ResponsiblePartyForm, node:Node):
    pass


@home.route('/abstract/<packageid>', methods=['GET', 'POST'])
def abstract(packageid=None):
    # Determine POST type
    if request.method == 'POST':
        if 'Back' in request.form:
            submit_type = 'Back'
        elif 'Next' in request.form:
            submit_type = 'Next'
        else:
            submit_type = None
    # Process POST
    form = AbstractForm(packageid=packageid)
    if form.validate_on_submit():
        abstract = form.abstract.data
        create_abstract(packageid=packageid, abstract=abstract)
        new_page = 'creator' if (submit_type == 'Back') else 'keywords'
        return redirect(url_for(f'home.{new_page}', packageid=packageid))
    # Process GET
    eml_node = load_eml(packageid=packageid)
    abstract_node = eml_node.find_child(child_name=names.ABSTRACT)
    if abstract_node:
        form.abstract.data = abstract_node.content
    return render_template('abstract.html', title='Abstract', packageid=packageid, form=form)


@home.route('/keywords/<packageid>', methods=['GET', 'POST'])
def keywords(packageid=None):
    # Determine POST type
    if request.method == 'POST':
        if 'Back' in request.form:
            submit_type = 'Back'
        elif 'Next' in request.form:
            submit_type = 'Next'
        else:
            submit_type = None

    form = KeywordsForm(packageid=packageid)
    form_fields = [form.k01, form.k02, form.k03, form.k04, \
                   form.k05, form.k06, form.k07, form.k08]

    # Process POST
    if form.validate_on_submit():
        keywords_list = []
        for form_field in form_fields:
            append_if_non_empty(keywords_list, form_field.data)
        create_keywords(packageid=packageid, keywords_list=keywords_list)
        new_page = 'abstract' if (submit_type == 'Back') else 'contact'
        responsible_party = 'Contact' if (submit_type == 'Next') else ''
        return redirect(url_for(f'home.{new_page}', packageid=packageid, responsible_party=responsible_party))

    # Process GET
    eml_node = load_eml(packageid=packageid)
    keywordset_node = eml_node.find_child(child_name=names.KEYWORDSET)
    if keywordset_node:
        i = 0
        for keyword_node in keywordset_node.children:
            form_fields[i].data = keyword_node.content
            i = i + 1
    return render_template('keywords.html', title='Keywords', packageid=packageid, form=form)


@home.route('/contact/<packageid>', methods=['GET', 'POST'])
def contact(packageid=None):
    # Determine POST type
    if request.method == 'POST':
        if 'Back' in request.form:
            submit_type = 'Back'
        elif 'Next' in request.form:
            submit_type = 'Next'
        else:
            submit_type = None
    form = ResponsiblePartyForm(responsible_party="Contact", packageid=packageid)

    # Process POST
    if form.validate_on_submit():   
        salutation = form.salutation.data
        gn = form.gn.data
        sn = form.sn.data
        organization = form.organization.data
        position_name = form.position_name.data
        address_1 = form.address_1.data
        address_2 = form.address_2.data
        city = form.city.data
        state = form.state.data
        postal_code = form.postal_code.data
        country = form.country.data
        phone = form.phone.data
        fax = form.fax.data
        email = form.email.data
        online_url = form.online_url.data
        contact_node = Node(names.CONTACT)

        create_responsible_party(
            contact_node,
            packageid,   
            salutation,
            gn,
            sn,
            organization,
            position_name,
            address_1,
            address_2,
            city,
            state,
            postal_code,
            country,
            phone,
            fax,
            email,
            online_url)

        new_page = 'keywords' if (submit_type == 'Back') else 'contact'
        responsible_party = 'Contact' if (submit_type == 'Next') else ''
        return redirect(url_for(f'home.{new_page}', packageid=packageid, responsible_party=responsible_party))
    # Process GET
    return render_template('responsible_party.html', title='Contact', form=form)


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


def append_if_non_empty(some_list: list, value: str):
    if value:
        some_list.append(value)


def create_eml(packageid=None):
    eml_node = Node(names.EML)

    eml_node.add_attribute('packageId', packageid)
    eml_node.add_attribute('system', 'https://pasta.edirepository.org')

    dataset_node = Node(names.DATASET, parent=eml_node)
    eml_node.add_child(dataset_node)

    try:
        save_both_formats(packageid=packageid, eml_node=eml_node)
    except Exception as e:
        logger.error(e)


def create_title(title=None, packageid=None):
    eml_node = load_eml(packageid=packageid)

    dataset_node = eml_node.find_child('dataset')
    if dataset_node:
        title_node = dataset_node.find_child('title')
        if not title_node:
            title_node = Node(names.TITLE, parent=dataset_node)
            dataset_node.add_child(title_node)
    else:
        dataset_node = Node(names.DATASET, parent=eml_node)
        eml_node.add_child(dataset_node)
        title_node = Node(names.TITLE, parent=dataset_node)
        dataset_node.add_child(title_node)

    title_node.content = title

    try:
        save_both_formats(packageid=packageid, eml_node=eml_node)
    except Exception as e:
        logger.error(e)


def create_abstract(packageid=None, abstract=None):
    eml_node = load_eml(packageid=packageid)

    dataset_node = eml_node.find_child(names.DATASET)
    if dataset_node:
        abstract_node = dataset_node.find_child(names.ABSTRACT)
        if not abstract_node:
            abstract_node = Node(names.ABSTRACT, parent=dataset_node)
            dataset_node.add_child(abstract_node)
    else:
        dataset_node = Node(names.DATASET, parent=eml_node)
        eml_node.add_child(dataset_node)
        abstract_node = Node(names.ABSTRACT, parent=dataset_node)
        dataset_node.add_child(abstract_node)

    abstract_node.content = abstract

    try:
        save_both_formats(packageid=packageid, eml_node=eml_node)
    except Exception as e:
        logger.error(e)


def create_keywords(packageid:str=None, keywords_list:list=[]):
    eml_node = load_eml(packageid=packageid)

    dataset_node = eml_node.find_child(names.DATASET)
    if dataset_node:
        keywordset_node = dataset_node.find_child(names.KEYWORDSET)
        if keywordset_node:
            # Get rid of the old keyword set if it exists
            dataset_node.remove_child(keywordset_node)
    else:
        dataset_node = Node(names.DATASET, parent=eml_node)
        eml_node.add_child(dataset_node)
    
    if keywords_list:
        keywordset_node = Node(names.KEYWORDSET, parent=dataset_node)
        dataset_node.add_child(keywordset_node)
        for keyword in keywords_list:
            keyword_node = Node(names.KEYWORD, parent=keywordset_node)
            keyword_node.content = keyword
            keywordset_node.add_child(keyword_node)

    try:
        save_both_formats(packageid=packageid, eml_node=eml_node)
    except Exception as e:
        logger.error(e)


def create_responsible_party(
                   responsible_party_node:Node=None,
                   packageid:str=None, 
                   salutation:str=None,
                   gn:str=None,
                   sn:str=None,
                   organization:str=None,
                   position_name:str=None,
                   address_1:str=None,
                   address_2:str=None,
                   city:str=None,
                   state:str=None,
                   postal_code:str=None,
                   country:str=None,
                   phone:str=None,
                   fax:str=None,
                   email:str=None,
                   online_url:str=None):
    try:
        node_name = responsible_party_node.name
        eml_node = load_eml(packageid=packageid)
        dataset_node = eml_node.find_child(names.DATASET)

        if dataset_node:
            old_responsible_party_node = dataset_node.find_child(node_name)
            if old_responsible_party_node:
                # Get rid of the old node if it exists
                dataset_node.remove_child(old_responsible_party_node)
        else:
            dataset_node = Node(names.DATASET, parent=eml_node)
            eml_node.add_child(dataset_node)

        dataset_node.add_child(responsible_party_node)

        if salutation or gn or sn:
            individual_name_node = Node(names.INDIVIDUALNAME)
            if salutation:
                salutation_node = Node(names.SALUTATION)
                salutation_node.content = salutation
                individual_name_node.add_child(salutation_node)
            if gn:
                given_name_node = Node(names.GIVENNAME)
                given_name_node.content = gn
                individual_name_node.add_child(given_name_node)
            if sn:
                surname_node = Node(names.SURNAME)
                surname_node.content = sn
                individual_name_node.add_child(surname_node)
            responsible_party_node.add_child(individual_name_node)

        if organization:
            organization_name_node = Node(names.ORGANIZATIONNAME)
            organization_name_node.content = organization
            responsible_party_node.add_child(organization_name_node)

        if position_name:
            position_name_node = Node(names.POSITIONNAME)
            position_name_node.content = position_name
            responsible_party_node.add_child(position_name_node)

        if address_1 or address_2 or city or state or postal_code or country:
            address_node = Node(names.ADDRESS)

            if address_1:
                delivery_point_node_1 = Node(names.DELIVERYPOINT)
                delivery_point_node_1.content = address_1
                address_node.add_child(delivery_point_node_1)

            if address_2:
                delivery_point_node_2 = Node(names.DELIVERYPOINT)
                delivery_point_node_2.content = address_2
                address_node.add_child(delivery_point_node_2)

            if city:
                city_node = Node(names.CITY)
                city_node.content = city
                address_node.add_child(city_node)

            if state:
                administrative_area_node = Node(names.ADMINISTRATIVEAREA)
                administrative_area_node.content = state
                address_node.add_child(administrative_area_node)

            if postal_code:
                postal_code_node = Node(names.POSTALCODE)
                postal_code_node.content = postal_code
                address_node.add_child(postal_code_node)

            if country:
                country_node = Node(names.COUNTRY)
                country_node.content = country
                address_node.add_child(country_node)

            responsible_party_node.add_child(address_node)

        if phone:
            phone_node = Node(names.PHONE)
            phone_node.content = phone
            phone_node.add_attribute('phonetype', 'voice')
            responsible_party_node.add_child(phone_node)

        if fax:
            fax_node = Node(names.PHONE)
            fax_node.content = fax
            fax_node.add_attribute('phonetype', 'facsimile')
            responsible_party_node.add_child(fax_node)

        if email:
            email_node = Node(names.ELECTRONICMAILADDRESS)
            email_node.content = email
            responsible_party_node.add_child(email_node)

        if online_url:
            online_url_node = Node(names.ONLINEURL)
            online_url_node.content = online_url
            responsible_party_node.add_child(online_url_node)
             
        save_both_formats(packageid=packageid, eml_node=eml_node)

    except Exception as e:
        logger.error(e)


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
    validate(eml)


def validate(node:Node):
    if node:
        msg = validate_tree(node)
        flash(msg)
