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
                              KeywordsForm, MinimalEMLForm, \
                              ResponsiblePartySelectForm

from metapype.eml2_1_1 import export
from metapype.eml2_1_1 import names
from metapype.model.node import Node
from webapp.home.metapype_client import load_eml, add_rps_to_dict, \
                              save_both_formats, validate_tree, \
                              add_child



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
        new_page = 'creator_select' if (submit_type == 'Next') else 'title'
        return redirect(url_for(f'home.{new_page}', packageid=packageid))
    # Process GET
    eml_node = load_eml(packageid=packageid)
    title_node = eml_node.find_child(child_name='title')
    if title_node:
        form.title.data = title_node.content
    return render_template('title.html', title='Title', form=form)


@home.route('/creator_select/<packageid>', methods=['GET', 'POST'])
def creator_select(packageid=None):
    # Determine POST type
    if request.method == 'POST':
        form_value = request.form
        print(form_value)
        my_dict = form_value.to_dict(flat=False)
        node_id = ''
        new_page = ''
        if my_dict:
            for key in my_dict:
                val = my_dict[key][0]  # value is the first list element
                if val == 'Back':
                    new_page = 'title'
                elif val == 'Next':
                    new_page = 'abstract'
                elif val == 'Edit':
                    new_page = 'creator'
                    node_id = key
                elif val == 'Add':
                    new_page = 'creator'
                    node_id = '1'
    form = ResponsiblePartySelectForm(packageid=packageid)

    # Process POST
    if form.validate_on_submit():   
        return redirect(url_for(f'home.{new_page}', packageid=packageid, node_id=node_id))
    # Process GET
    eml_node = load_eml(packageid=packageid)

    rp_dict = {}
    add_rps_to_dict(eml_node, names.CREATOR, rp_dict)
    rp_dict['[Add New]'] = '1'

    return render_template('responsible_party_select.html', title='Creator',
                rp_capitalized='Creator', rp_lower='creator', rp_dict=rp_dict, form=form)


@home.route('/creator/<packageid>/<node_id>', methods=['GET', 'POST'])
def creator(packageid=None, node_id=None):
    # Determine POST type
    if request.method == 'POST':
        if 'Save Changes' in request.form:
            submit_type = 'Save Changes'
        elif 'Back' in request.form:
            submit_type = 'Back'
        else:
            submit_type = None
    form = ResponsiblePartyForm(packageid=packageid)

    # Process POST
    if form.validate_on_submit():
        if submit_type == 'Save Changes':
            eml_node = load_eml(packageid=packageid)

            dataset_node = eml_node.find_child(names.DATASET)
            if not dataset_node:
                dataset_node = Node(names.DATASET)

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

            creator_node = Node(names.CREATOR, parent=dataset_node)

            create_responsible_party(
                dataset_node,
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

            if node_id and len(node_id) > 1:
                # Better to implement this with a function call
                old_creator_node = Node.get_node_instance(node_id)
                if old_creator_node:
                    dataset_parent_node = old_creator_node.parent
                    dataset_parent_node.replace_child(old_creator_node, creator_node)
                else:
                    add_child(dataset_node, creator_node)

            save_both_formats(packageid=packageid, eml_node=eml_node)

        new_page = 'creator_select'
        return redirect(url_for(f'home.{new_page}', packageid=packageid))

    # Process GET
    if node_id == '1':
        pass
    else:
        eml_node = load_eml(packageid=packageid)
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            creator_nodes = dataset_node.find_all_children(child_name=names.CREATOR)
            if creator_nodes:
                for creator_node in creator_nodes:
                    if node_id == creator_node.id:
                        populate_responsible_party_form(form, creator_node)
    
    return render_template('responsible_party.html', title='Creator',
                rp_capitalized='Creator', rp_lower='creator',form=form)


def populate_responsible_party_form(form:ResponsiblePartyForm, node:Node):    
    salutation_node = node.find_child(names.SALUTATION)
    if salutation_node:
        form.salutation.data = salutation_node.content
    
    gn_node = node.find_child(names.GIVENNAME)
    if gn_node:
        form.gn.data = gn_node.content
    
    sn_node = node.find_child(names.SURNAME)
    if sn_node:
        form.sn.data = sn_node.content

    organization_node = node.find_child(names.ORGANIZATIONNAME)
    if organization_node:
        form.organization.data = organization_node.content

    position_name_node = node.find_child(names.POSITIONNAME)
    if position_name_node:
        form.position_name.data = position_name_node.content

    address_node = node.find_child(names.ADDRESS)

    if address_node:
        delivery_point_nodes = \
            address_node.find_all_children(names.DELIVERYPOINT)
        if len(delivery_point_nodes) > 0:
            form.address_1.data = delivery_point_nodes[0].content
        if len(delivery_point_nodes) > 1:
            form.address_2.data = delivery_point_nodes[1].content

        city_node = address_node.find_child(names.CITY)
        if city_node:
            form.city.data = city_node.content

        administrative_area_node = \
            address_node.find_child(names.ADMINISTRATIVEAREA)
        if administrative_area_node:
            form.state.data = administrative_area_node.content

        postal_code_node = address_node.find_child(names.POSTALCODE)
        if postal_code_node:
            form.postal_code.data = postal_code_node.content

        country_node = address_node.find_child(names.COUNTRY)
        if country_node:
            form.country.data = country_node.content

        phone_node = node.find_child(names.PHONE)
        if phone_node:
            form.phone.data = phone_node.content

   
    phone_nodes = node.find_all_children(names.PHONE)
    for phone_node in phone_nodes:
        phone_type = phone_node.attribute_value('phonetype')
        if phone_type == 'facsimile':
            form.fax.data = phone_node.content
        else:
            form.phone.data = phone_node.content

    email_node = node.find_child(names.ELECTRONICMAILADDRESS)
    if email_node:
        form.email.data = email_node.content

    online_url_node = node.find_child(names.ONLINEURL)
    if online_url_node:
        form.online_url.data = online_url_node.content


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
        new_page = 'creator_select' if (submit_type == 'Back') else 'keywords'
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
    submit_type = None
    if request.method == 'POST':
        if 'Back' in request.form:
            submit_type = 'Back'
        elif 'Next' in request.form:
            submit_type = 'Next'
        elif 'Add' in request.form:
            submit_type = 'Add'
        elif 'Remove' in request.form:
            submit_type = 'Remove'

    form = KeywordsForm(packageid=packageid)

    # Process POST
    if form.validate_on_submit():
        new_page = 'keywords'
        user_keyword = form.keyword.data
        user_keyword = user_keyword.strip()
        user_keyword_type = form.keyword_type.data

        if submit_type == 'Add':
            add_keyword(packageid=packageid, keyword=user_keyword, keyword_type=user_keyword_type)
        elif submit_type == 'Remove':
            remove_keyword(packageid=packageid, keyword=user_keyword)
        elif submit_type == 'Back':
            new_page = 'abstract'
        elif submit_type == 'Next':
            new_page = 'contact_select'

        return redirect(url_for(f'home.{new_page}', packageid=packageid))

    # Process GET
    eml_node = load_eml(packageid=packageid)
    keywordset_node = eml_node.find_child(child_name=names.KEYWORDSET)
    keyword_dict = {}
    if keywordset_node:
        for keyword_node in keywordset_node.find_all_children(child_name=names.KEYWORD):
            keyword = keyword_node.content
            if keyword:
                keyword_type = keyword_node.attribute_value('keywordType')
                if keyword_type is None:
                    keyword_type = ''
                keyword_dict[keyword] = keyword_type
    return render_template('keywords.html', title='Keywords', packageid=packageid, form=form, keyword_dict=keyword_dict)


@home.route('/contact_select/<packageid>', methods=['GET', 'POST'])
def contact_select(packageid=None):
    # Determine POST type
    if request.method == 'POST':
        form_value = request.form
        print(form_value)
        my_dict = form_value.to_dict(flat=False)
        node_id = ''
        new_page = ''
        if my_dict:
            for key in my_dict:
                val = my_dict[key][0]  # value is the first list element
                if val == 'Back':
                    new_page = 'keywords'
                elif val == 'Next':
                    new_page = 'contact_select'
                elif val == 'Edit':
                    new_page = 'contact'
                    node_id = key
                elif val == 'Add':
                    new_page = 'contact'
                    node_id = '1'
    form = ResponsiblePartySelectForm(packageid=packageid)

    # Process POST
    if form.validate_on_submit():   
        return redirect(url_for(f'home.{new_page}', packageid=packageid, node_id=node_id))
    # Process GET
    eml_node = load_eml(packageid=packageid)

    rp_dict = {}
    add_rps_to_dict(eml_node, names.CONTACT, rp_dict)
    rp_dict['[Add New]'] = '1'

    return render_template('responsible_party_select.html', title='Contact',
                rp_capitalized='Contact', rp_lower='contact', rp_dict=rp_dict, form=form)


@home.route('/contact/<packageid>/<node_id>', methods=['GET', 'POST'])
def contact(packageid=None, node_id=None):
    # Determine POST type
    if request.method == 'POST':
        if 'Save Changes' in request.form:
            submit_type = 'Save Changes'
        elif 'Back' in request.form:
            submit_type = 'Back'
        else:
            submit_type = None
    form = ResponsiblePartyForm(packageid=packageid)

    # Process POST
    if form.validate_on_submit():
        if submit_type == 'Save Changes':
            eml_node = load_eml(packageid=packageid)

            dataset_node = eml_node.find_child(names.DATASET)
            if not dataset_node:
                dataset_node = Node(names.DATASET)

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

            contact_node = Node(names.CONTACT, parent=dataset_node)
            add_child(dataset_node, contact_node)

            create_responsible_party(
                dataset_node,
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

            save_both_formats(packageid=packageid, eml_node=eml_node)

        new_page = 'contact_select'
        return redirect(url_for(f'home.{new_page}', packageid=packageid))

    # Process GET
    if node_id == '1':
        pass
    else:
        eml_node = load_eml(packageid=packageid)
    
        contact_nodes = eml_node.find_all_children(child_name=names.CONTACT)
        if contact_nodes:
            for contact_node in contact_nodes:
                if node_id == contact_node.id:
                    populate_responsible_party_form(form, contact_node)
    
    return render_template('responsible_party.html', title='Contact',
                rp_capitalized='Contact', rp_lower='contact',form=form)




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
    eml_node = load_eml(packageid=packageid)

    if not eml_node:
        eml_node = Node(names.EML)
        eml_node.add_attribute('packageId', packageid)
        eml_node.add_attribute('system', 'https://pasta.edirepository.org')
        dataset_node = Node(names.DATASET, parent=eml_node)
        add_child(eml_node, dataset_node)

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
            add_child(dataset_node, title_node)
    else:
        dataset_node = Node(names.DATASET, parent=eml_node)
        add_child(eml_node, dataset_node)
        title_node = Node(names.TITLE, parent=dataset_node)
        add_child(dataset_node, title_node)

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
            add_child(dataset_node, abstract_node)
    else:
        dataset_node = Node(names.DATASET, parent=eml_node)
        add_child(eml_node, dataset_node)
        abstract_node = Node(names.ABSTRACT, parent=dataset_node)
        add_child(dataset_node, abstract_node)

    abstract_node.content = abstract

    try:
        save_both_formats(packageid=packageid, eml_node=eml_node)
    except Exception as e:
        logger.error(e)


def add_keyword(packageid:str=None, keyword:str=None, keyword_type:str=None):
    if keyword:
        eml_node = load_eml(packageid=packageid)

        dataset_node = eml_node.find_child(names.DATASET)
        if not dataset_node:
            dataset_node = Node(names.DATASET, parent=eml_node)
            add_child(eml_node, dataset_node)

        keywordset_node = dataset_node.find_child(names.KEYWORDSET)
        if not keywordset_node:
            keywordset_node = Node(names.KEYWORDSET, parent=dataset_node)
            add_child(dataset_node, keywordset_node)

        keyword_node = None
        
        # Does a matching keyword node already exist?
        keyword_nodes = keywordset_node.find_all_children(names.KEYWORD)
        for child_node in keyword_nodes:
            if child_node.content == keyword:
                keyword_node = child_node
                break
        
        if not keyword_node:
            keyword_node = Node(names.KEYWORD, parent=keywordset_node)
            keyword_node.content = keyword
            add_child(keywordset_node, keyword_node)
        
        if keyword_type:
            keyword_node.add_attribute(name='keywordType', value=keyword_type)

    try:
        save_both_formats(packageid=packageid, eml_node=eml_node)
    except Exception as e:
        logger.error(e)


def remove_keyword(packageid:str=None, keyword:str=None):
    if keyword:
        eml_node = load_eml(packageid=packageid)
        keywordset_node = eml_node.find_child(names.KEYWORDSET)
        if keywordset_node:
            current_keywords = keywordset_node.find_all_children(child_name=names.KEYWORD)
            for keyword_node in current_keywords:
                if keyword_node.content == keyword:
                    keywordset_node.remove_child(keyword_node)

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
        add_child(eml_node, dataset_node)
    
    if keywords_list:
        keywordset_node = Node(names.KEYWORDSET, parent=dataset_node)
        add_child(dataset_node, keywordset_node)
        for keyword in keywords_list:
            keyword_node = Node(names.KEYWORD, parent=keywordset_node)
            keyword_node.content = keyword
            add_child(keywordset_node, keyword_node)

    try:
        save_both_formats(packageid=packageid, eml_node=eml_node)
    except Exception as e:
        logger.error(e)


def create_responsible_party(
                   parent_node:Node=None,
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

        if parent_node:
            old_responsible_party_node = parent_node.find_child(node_name)
            if old_responsible_party_node:
                pass
                # Get rid of the old node if it exists
                #dataset_node.remove_child(old_responsible_party_node)

        if salutation or gn or sn:
            individual_name_node = Node(names.INDIVIDUALNAME)
            if salutation:
                salutation_node = Node(names.SALUTATION)
                salutation_node.content = salutation
                add_child(individual_name_node, salutation_node)
            if gn:
                given_name_node = Node(names.GIVENNAME)
                given_name_node.content = gn
                add_child(individual_name_node, given_name_node)
            if sn:
                surname_node = Node(names.SURNAME)
                surname_node.content = sn
                add_child(individual_name_node, surname_node)
            add_child(responsible_party_node, individual_name_node)

        if organization:
            organization_name_node = Node(names.ORGANIZATIONNAME)
            organization_name_node.content = organization
            add_child(responsible_party_node, organization_name_node)

        if position_name:
            position_name_node = Node(names.POSITIONNAME)
            position_name_node.content = position_name
            add_child(responsible_party_node, position_name_node)

        if address_1 or address_2 or city or state or postal_code or country:
            address_node = Node(names.ADDRESS)

            if address_1:
                delivery_point_node_1 = Node(names.DELIVERYPOINT)
                delivery_point_node_1.content = address_1
                add_child(address_node, delivery_point_node_1)

            if address_2:
                delivery_point_node_2 = Node(names.DELIVERYPOINT)
                delivery_point_node_2.content = address_2
                add_child(address_node, delivery_point_node_2)

            if city:
                city_node = Node(names.CITY)
                city_node.content = city
                add_child(address_node, city_node)

            if state:
                administrative_area_node = Node(names.ADMINISTRATIVEAREA)
                administrative_area_node.content = state
                add_child(address_node, administrative_area_node)

            if postal_code:
                postal_code_node = Node(names.POSTALCODE)
                postal_code_node.content = postal_code
                add_child(address_node, postal_code_node)

            if country:
                country_node = Node(names.COUNTRY)
                country_node.content = country
                add_child(address_node,country_node)

            add_child(responsible_party_node, address_node)

        if phone:
            phone_node = Node(names.PHONE)
            phone_node.content = phone
            phone_node.add_attribute('phonetype', 'voice')
            add_child(responsible_party_node, phone_node)

        if fax:
            fax_node = Node(names.PHONE)
            fax_node.content = fax
            fax_node.add_attribute('phonetype', 'facsimile')
            add_child(responsible_party_node, fax_node)

        if email:
            email_node = Node(names.ELECTRONICMAILADDRESS)
            email_node.content = email
            add_child(responsible_party_node, email_node)

        if online_url:
            online_url_node = Node(names.ONLINEURL)
            online_url_node.content = online_url
            add_child(responsible_party_node, online_url_node)
             
        return responsible_party_node

    except Exception as e:
        logger.error(e)


def validate_minimal(packageid=None, title=None, contact_gn=None, contact_sn=None, creator_gn=None, creator_sn=None):
    eml = Node(names.EML)

    eml.add_attribute('packageId', packageid)
    eml.add_attribute('system', 'https://pasta.edirepository.org')

    dataset = Node(names.DATASET, parent=eml)
    add_child(eml, dataset)

    title_node = Node(names.TITLE)
    title_node.content = title
    add_child(dataset, title_node)
    
    creator_node = Node(names.CREATOR, parent=dataset)
    add_child(dataset, creator_node)

    individualName_creator = Node(names.INDIVIDUALNAME, parent=creator_node)
    add_child(creator_node, individualName_creator)

    givenName_creator = Node(names.GIVENNAME, parent=individualName_creator)
    givenName_creator.content = creator_gn
    add_child(individualName_creator, givenName_creator)

    surName_creator = Node(names.SURNAME, parent=individualName_creator)
    surName_creator.content = creator_sn
    add_child(individualName_creator, surName_creator)

    contact_node = Node(names.CONTACT, parent=dataset)
    add_child(dataset, contact_node)

    individualName_contact = Node(names.INDIVIDUALNAME, parent=contact_node)
    add_child(contact_node, individualName_contact)

    givenName_contact = Node(names.GIVENNAME, parent=individualName_contact)
    givenName_contact.content = contact_gn
    add_child(individualName_contact, givenName_contact)

    surName_contact = Node(names.SURNAME, parent=individualName_contact)
    surName_contact.content = contact_sn
    add_child(individualName_contact, surName_contact)

    xml_str =  export.to_xml(eml)
    print(xml_str)

    if eml:
        msg = validate_tree(eml)
        flash(msg)
