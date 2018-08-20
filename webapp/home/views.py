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

from flask import (
    Blueprint, flash, render_template, redirect, request, url_for
)

from webapp.home.forms import ( 
    CreateEMLForm, TitleForm, ResponsiblePartyForm, AbstractForm, 
    KeywordsForm, MinimalEMLForm, ResponsiblePartySelectForm, PubDateForm,
    GeographicCoverageSelectForm, GeographicCoverageForm
)

from webapp.home.metapype_client import ( 
    load_eml, list_responsible_parties, save_both_formats, validate_tree,
    add_child, remove_child, create_eml, create_title, create_pubdate,
    create_abstract, add_keyword, remove_keyword, create_keywords,
    create_responsible_party, validate_minimal, list_geographic_coverages,
    create_geographic_coverage
)

from metapype.eml2_1_1 import export
from metapype.eml2_1_1 import names
from metapype.model.node import Node


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
    return render_template('create_eml.html', title='Create New EML', 
                           form=form)


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
    form = ResponsiblePartySelectForm(packageid=packageid)
    
    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = rp_select_post(packageid, form, form_dict, 
                             'POST', 'creator_select', 'title', 
                             'metadata_provider_select', 'creator')
        return redirect(url)

    # Process GET
    return rp_select_get(packageid=packageid, form=form, rp_name=names.CREATOR, 
                         rp_singular='Creator', rp_plural='Creators')


def rp_select_post(packageid=None, form=None, form_dict=None,
                   method=None, this_page=None, back_page=None, 
                   next_page=None, edit_page=None):
    node_id = ''
    new_page = ''
    if form_dict:
        for key in form_dict:
            val = form_dict[key][0]  # value is the first list element
            if val == 'Back':
                new_page = back_page
            elif val == 'Next':
                new_page = next_page
            elif val == 'Edit':
                new_page = edit_page
                node_id = key
            elif val == 'Remove':
                new_page = this_page
                node_id = key
                eml_node = load_eml(packageid=packageid)
                remove_child(node_id=node_id)
                save_both_formats(packageid=packageid, eml_node=eml_node)
            elif val[0:3] == 'Add':
                new_page = edit_page
                node_id = '1'

    if form.validate_on_submit():   
        return url_for(f'home.{new_page}', packageid=packageid, 
                       node_id=node_id)


def rp_select_get(packageid=None, form=None, rp_name=None, 
                  rp_singular=None, rp_plural=None):
    # Process GET
    eml_node = load_eml(packageid=packageid)
    rp_list = list_responsible_parties(eml_node, rp_name)
    title = rp_name.capitalize()

    return render_template('responsible_party_select.html', title=title,
                            rp_list=rp_list, form=form, 
                            rp_singular=rp_singular, rp_plural=rp_plural)


@home.route('/creator/<packageid>/<node_id>', methods=['GET', 'POST'])
def creator(packageid=None, node_id=None):
    method = request.method
    return responsible_party(packageid=packageid, node_id=node_id, 
                             method=method, node_name=names.CREATOR, 
                             new_page='creator_select', title='Creator')


def responsible_party(packageid=None, node_id=None, method=None, 
                      node_name=None, new_page=None, title=None):
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

            rp_node = Node(node_name, parent=dataset_node)

            create_responsible_party(
                dataset_node,
                rp_node,
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

            if node_id and len(node_id) != 1:
                old_rp_node = Node.get_node_instance(node_id)
                if old_rp_node:
                    dataset_parent_node = old_rp_node.parent
                    dataset_parent_node.replace_child(old_rp_node, rp_node)
                else:
                    msg = f"No node found in the node store with node id {node_id}"
                    raise Exception(msg)
            else:
                add_child(dataset_node, rp_node)

            save_both_formats(packageid=packageid, eml_node=eml_node)

        return redirect(url_for(f'home.{new_page}', packageid=packageid))

    # Process GET
    if node_id == '1':
        pass
    else:
        eml_node = load_eml(packageid=packageid)
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            rp_nodes = dataset_node.find_all_children(child_name=node_name)
            if rp_nodes:
                for rp_node in rp_nodes:
                    if node_id == rp_node.id:
                        populate_responsible_party_form(form, rp_node)
    
    return render_template('responsible_party.html', title=title, form=form)



@home.route('/metadata_provider_select/<packageid>', methods=['GET', 'POST'])
def metadata_provider_select(packageid=None):
    form = ResponsiblePartySelectForm(packageid=packageid)
    
    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = rp_select_post(packageid, form, form_dict, 
                             'POST', 'metadata_provider_select', 
                             'creator_select', 
                             'geographic_coverage_select', 
                             'metadata_provider')
        return redirect(url)

    # Process GET
    return rp_select_get(packageid=packageid, form=form, 
                         rp_name=names.METADATAPROVIDER,
                         rp_singular='Metadata Provider', 
                         rp_plural='Metadata Providers')


@home.route('/metadata_provider/<packageid>/<node_id>', methods=['GET', 'POST'])
def metadata_provider(packageid=None, node_id=None):
    method = request.method
    return responsible_party(packageid=packageid, node_id=node_id, 
                             method=method, node_name=names.METADATAPROVIDER, 
                             new_page='metadata_provider_select', 
                             title='Metadata Provider')


@home.route('/associated_party_select/<packageid>', methods=['GET', 'POST'])
def associated_party_select(packageid=None):
    form = ResponsiblePartySelectForm(packageid=packageid)
    
    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = rp_select_post(packageid, form, form_dict, 
                             'POST', 'associated_party_select', 
                             'metadata_provider_select', 
                             'pubdate', 'associated_party')
        return redirect(url)

    # Process GET
    return rp_select_get(packageid=packageid, form=form, 
                         rp_name=names.ASSOCIATEDPARTY,
                         rp_singular='Associated Party', 
                         rp_plural='Associated Parties')


@home.route('/associated_party/<packageid>/<node_id>', methods=['GET', 'POST'])
def associated_party(packageid=None, node_id=None):
    method = request.method
    return responsible_party(packageid=packageid, node_id=node_id, 
                             method=method, node_name=names.ASSOCIATEDPARTY, 
                             new_page='associated_party_select', 
                             title='Associated Party')


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


@home.route('/pubdate/<packageid>', methods=['GET', 'POST'])
def pubdate(packageid=None):
    # Determine POST type
    if request.method == 'POST':
        if 'Back' in request.form:
            submit_type = 'Back'
        elif 'Next' in request.form:
            submit_type = 'Next'
        else:
            submit_type = None
    # Process POST
    form = PubDateForm(packageid=packageid)
    if form.validate_on_submit():
        pubdate = form.pubdate.data
        create_pubdate(packageid=packageid, pubdate=pubdate)
        new_page = 'creator_select' if (submit_type == 'Back') else 'abstract'
        return redirect(url_for(f'home.{new_page}', packageid=packageid))
    # Process GET
    eml_node = load_eml(packageid=packageid)
    pubdate_node = eml_node.find_child(child_name=names.PUBDATE)
    if pubdate_node:
        form.pubdate.data = pubdate_node.content
    return render_template('pubdate.html', 
                           title='Publication Date', 
                           packageid=packageid, form=form)


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
        new_page = 'pubdate' if (submit_type == 'Back') else 'keywords'
        return redirect(url_for(f'home.{new_page}', packageid=packageid))
    # Process GET
    eml_node = load_eml(packageid=packageid)
    abstract_node = eml_node.find_child(child_name=names.ABSTRACT)
    if abstract_node:
        form.abstract.data = abstract_node.content
    return render_template('abstract.html', 
                           title='Abstract', 
                           packageid=packageid, form=form)


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
            add_keyword(packageid=packageid, 
                        keyword=user_keyword, 
                        keyword_type=user_keyword_type)
        elif submit_type == 'Remove':
            remove_keyword(packageid=packageid, keyword=user_keyword)
        elif submit_type == 'Back':
            new_page = 'abstract'
        elif submit_type == 'Next':
            new_page = 'geographic_coverage_select'

        return redirect(url_for(f'home.{new_page}', packageid=packageid))

    # Process GET
    eml_node = load_eml(packageid=packageid)
    keywordset_node = eml_node.find_child(child_name=names.KEYWORDSET)
    keyword_dict = {}
    if keywordset_node:
        for keyword_node in \
                keywordset_node.find_all_children(child_name=names.KEYWORD):
            keyword = keyword_node.content
            if keyword:
                keyword_type = keyword_node.attribute_value('keywordType')
                if keyword_type is None:
                    keyword_type = ''
                keyword_dict[keyword] = keyword_type
    return render_template('keywords.html', 
                            title='Keywords', 
                            packageid=packageid, form=form, 
                            keyword_dict=keyword_dict)


@home.route('/geographic_coverage_select/<packageid>', methods=['GET', 'POST'])
def geographic_coverage_select(packageid=None):
    form = GeographicCoverageSelectForm(packageid=packageid)
    
    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = geographic_coverage_select_post(packageid, form, form_dict, 
                             'POST', 'geographic_coverage_select',
                             'metadata_provider_select',
                             'contact_select', 'geographic_coverage')
        return redirect(url)

    # Process GET
    return geographic_coverage_select_get(packageid=packageid, form=form, rp_name='contact',
                         rp_singular='Contact', rp_plural='Contacts')


def geographic_coverage_select_post(packageid=None, form=None, form_dict=None,
                   method=None, this_page=None, back_page=None, 
                   next_page=None, edit_page=None):
    node_id = ''
    new_page = ''
    if form_dict:
        for key in form_dict:
            val = form_dict[key][0]  # value is the first list element
            if val == 'Back':
                new_page = back_page
            elif val == 'Next':
                new_page = next_page
            elif val == 'Edit':
                new_page = edit_page
                node_id = key
            elif val == 'Remove':
                new_page = this_page
                node_id = key
                eml_node = load_eml(packageid=packageid)
                remove_child(node_id=node_id)
                save_both_formats(packageid=packageid, eml_node=eml_node)
            elif val[0:3] == 'Add':
                new_page = edit_page
                node_id = '1'

    if form.validate_on_submit():   
        return url_for(f'home.{new_page}', packageid=packageid, node_id=node_id)


def geographic_coverage_select_get(packageid=None, form=None, rp_name=None, 
                  rp_singular=None, rp_plural=None):
    # Process GET
    eml_node = load_eml(packageid=packageid)
    gc_list = list_geographic_coverages(eml_node)
    title = "Geographic Coverage"

    return render_template('geographic_coverage_select.html', title=title,
                            gc_list=gc_list, form=form)


@home.route('/geographic_coverage/<packageid>/<node_id>', methods=['GET', 'POST'])
def geographic_coverage(packageid=None, node_id=None):
    # Determine POST type
    if request.method == 'POST':
        if 'Save Changes' in request.form:
            submit_type = 'Save Changes'
        elif 'Back' in request.form:
            submit_type = 'Back'
        else:
            submit_type = None
    form = GeographicCoverageForm(packageid=packageid)

    # Process POST
    if form.validate_on_submit():
        if submit_type == 'Save Changes':
            eml_node = load_eml(packageid=packageid)

            dataset_node = eml_node.find_child(names.DATASET)
            if not dataset_node:
                dataset_node = Node(names.DATASET)

            coverage_node = dataset_node.find_child(names.COVERAGE)
            if not coverage_node:
                coverage_node = Node(names.COVERAGE, parent=dataset_node)
                dataset_node.add_child(coverage_node)

            geographic_description = form.geographic_description.data
            wbc = form.wbc.data
            ebc = form.ebc.data
            nbc = form.nbc.data
            sbc = form.sbc.data

            gc_node = Node(names.GEOGRAPHICCOVERAGE, parent=coverage_node)

            create_geographic_coverage(
                gc_node,
                geographic_description,
                wbc, ebc, nbc, sbc)

            if node_id and len(node_id) != 1:
                old_gc_node = Node.get_node_instance(node_id)
                if old_gc_node:
                    coverage_parent_node = old_gc_node.parent
                    coverage_parent_node.replace_child(old_gc_node, gc_node)
                else:
                    msg = f"No node found in the node store with node id {node_id}"
                    raise Exception(msg)
            else:
                add_child(coverage_node, gc_node)

            save_both_formats(packageid=packageid, eml_node=eml_node)

        return redirect(url_for('home.geographic_coverage_select', packageid=packageid))

    # Process GET
    if node_id == '1':
        pass
    else:
        eml_node = load_eml(packageid=packageid)
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            coverage_node = dataset_node.find_child(names.COVERAGE)
            if coverage_node:
                gc_nodes = coverage_node.find_all_children(names.GEOGRAPHICCOVERAGE)
                if gc_nodes:
                    for gc_node in gc_nodes:
                        if node_id == gc_node.id:
                            populate_geographic_coverage_form(form, gc_node)
    
    return render_template('geographic_coverage.html', title='Geographic Coverage', form=form)


def populate_geographic_coverage_form(form:GeographicCoverageForm, node:Node):    
    geographic_description_node = node.find_child(names.GEOGRAPHICDESCRIPTION)
    if geographic_description_node:
        form.geographic_description.data = geographic_description_node.content
    
    wbc_node = node.find_child(names.WESTBOUNDINGCOORDINATE)
    if wbc_node:
        form.wbc.data = wbc_node.content
    ebc_node = node.find_child(names.EASTBOUNDINGCOORDINATE)
    if ebc_node:
        form.ebc.data = ebc_node.content
    nbc_node = node.find_child(names.NORTHBOUNDINGCOORDINATE)
    if nbc_node:
        form.nbc.data = nbc_node.content
    sbc_node = node.find_child(names.SOUTHBOUNDINGCOORDINATE)
    if sbc_node:
        form.sbc.data = sbc_node.content
    

@home.route('/contact_select/<packageid>', methods=['GET', 'POST'])
def contact_select(packageid=None):
    form = ResponsiblePartySelectForm(packageid=packageid)
    
    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = rp_select_post(packageid, form, form_dict, 
                             'POST', 'contact_select', 'geographic_coverage_select', 
                             'title', 'contact')
        return redirect(url)

    # Process GET
    return rp_select_get(packageid=packageid, form=form, rp_name='contact',
                         rp_singular='Contact', rp_plural='Contacts')


@home.route('/contact/<packageid>/<node_id>', methods=['GET', 'POST'])
def contact(packageid=None, node_id=None):
    method = request.method
    return responsible_party(packageid=packageid, node_id=node_id, 
                             method=method, node_name=names.CONTACT, 
                             new_page='contact_select', title='Contact')


@home.route('/minimal', methods=['GET', 'POST'])
def minimal():
    # Process POST
    form = MinimalEMLForm()
    if form.validate_on_submit():
        msg = validate_minimal(packageid=form.packageid.data,
                         title=form.title.data, 
                         creator_gn=form.creator_gn.data, 
                         creator_sn=form.creator_sn.data,
                         contact_gn=form.contact_gn.data, 
                         contact_sn=form.contact_sn.data)
        if msg:
            flash(msg)
    # Process GET
    return render_template('minimal_eml.html', title='Minimal EML', form=form)
