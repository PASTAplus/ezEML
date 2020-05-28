from flask import (
    Blueprint, flash, render_template, redirect, request, url_for
)

from webapp.views.responsible_parties.forms import (
    ResponsiblePartyForm, ResponsiblePartySelectForm
)

from webapp.home.forms import (
    form_md5, is_dirty_form
)

from webapp.home.metapype_client import (
    load_eml, list_responsible_parties, save_both_formats,
    add_child, create_responsible_party
)

from metapype.eml import names
from metapype.model.node import Node

from webapp.buttons import *
from webapp.pages import *

from webapp.home.views import select_post, non_breaking, set_current_page, get_help


rp_bp = Blueprint('rp', __name__, template_folder='templates')


@rp_bp.route('/creator_select/<packageid>', methods=['GET', 'POST'])
def creator_select(packageid=None):
    form = ResponsiblePartySelectForm(packageid=packageid)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = select_post(packageid, form, form_dict,
                          'POST', PAGE_CREATOR_SELECT, PAGE_TITLE,
                          PAGE_METADATA_PROVIDER_SELECT, PAGE_CREATOR)
        return redirect(url)

    # Process GET
    set_current_page('creator')
    help = [get_help('creators')]
    return rp_select_get(packageid=packageid, form=form, rp_name=names.CREATOR,
                         rp_singular='Creator', rp_plural='Creators', help=help)


@rp_bp.route('/creator/<packageid>/<node_id>', methods=['GET', 'POST'])
def creator(packageid=None, node_id=None):
    method = request.method
    set_current_page('creator')
    return responsible_party(packageid=packageid, node_id=node_id,
                             method=method, node_name=names.CREATOR,
                             back_page=PAGE_CREATOR_SELECT, title='Creator')


def rp_select_get(packageid=None, form=None, rp_name=None,
                  rp_singular=None, rp_plural=None, help=None):
    # Process GET
    eml_node = load_eml(packageid=packageid)
    rp_list = list_responsible_parties(eml_node, rp_name)
    title = rp_name.capitalize()

    return render_template('responsible_party_select.html', title=title,
                           rp_list=rp_list, form=form,
                           rp_singular=rp_singular, rp_plural=rp_plural, help=help)


def select_new_page(back_page=None, next_page=None, edit_page=None):
    form_value = request.form
    form_dict = form_value.to_dict(flat=False)
    new_page = back_page
    if form_dict:
        for key in form_dict:
            val = form_dict[key][0]  # value is the first list element
            if val == BTN_BACK:
                new_page = back_page
                break
            elif val in (BTN_NEXT, BTN_SAVE_AND_CONTINUE):
                new_page = next_page
                break
    return new_page


def responsible_party(packageid=None, node_id=None, method=None,
                      node_name=None, back_page=None, title=None,
                      next_page=None, save_and_continue=False, help=None):

    if BTN_CANCEL in request.form:
        url = url_for(back_page, packageid=packageid)
        return redirect(url)

    form = ResponsiblePartyForm(packageid=packageid)
    eml_node = load_eml(packageid=packageid)
    dataset_node = eml_node.find_child(names.DATASET)
    if not dataset_node:
        dataset_node = Node(names.DATASET, parent=eml_node)
        add_child(eml_node, dataset_node)
    parent_node = dataset_node
    role = False
    new_page = select_new_page(back_page, next_page)

    form_value = request.form
    form_dict = form_value.to_dict(flat=False)
    url = select_post(packageid, form, form_dict,
                      'POST', PAGE_PUBLISHER,
                      PAGE_CONTACT_SELECT, PAGE_PUBLICATION_PLACE,
                      PAGE_PUBLISHER)
    # url = select_post(packageid, form, form_dict,
    #                   method, this_page, back_page,
    #                   next_page, edit_page)

    # def select_post(packageid=None, form=None, form_dict=None,
    #                 method=None, this_page=None, back_page=None,
    #                 next_page=None, edit_page=None):

    # If this is an associatedParty or a project personnel element,
    # set role to True so it will appear as a form field.
    if node_name == names.ASSOCIATEDPARTY or node_name == names.PERSONNEL:
        role = True

    # If this is a project personnel party, place it under the
    # project node, not under the dataset node
    if node_name == names.PERSONNEL:
        project_node = dataset_node.find_child(names.PROJECT)
        if not project_node:
            project_node = Node(names.PROJECT, parent=dataset_node)
            add_child(dataset_node, project_node)
        parent_node = project_node

    # Process POST
    save = False
    if is_dirty_form(form):
        save = True

    if form.validate_on_submit():
        if save:
            salutation = form.salutation.data
            gn = form.gn.data
            sn = form.sn.data
            user_id = form.user_id.data
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
            role = form.role.data

            rp_node = Node(node_name, parent=parent_node)

            create_responsible_party(
                rp_node,
                packageid,
                salutation,
                gn,
                sn,
                user_id,
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
                online_url,
                role)

            if node_id and len(node_id) != 1:
                old_rp_node = Node.get_node_instance(node_id)
                if old_rp_node:
                    old_rp_parent_node = old_rp_node.parent
                    old_rp_parent_node.replace_child(old_rp_node, rp_node)
                else:
                    msg = f"No node found in the node store with node id {node_id}"
                    raise Exception(msg)
            else:
                add_child(parent_node, rp_node)

            save_both_formats(packageid=packageid, eml_node=eml_node)
            # flash(f"Changes to the '{node_name}' element have been saved.")

            # There is at most only one publisher element, so we don't have a
            # list of publishers to navigate back to. Stay on this page after
            # saving changes.
            if node_name == names.PUBLISHER:
                new_page = PAGE_PUBLISHER

        return redirect(url_for(new_page, packageid=packageid))

    # Process GET
    if node_id == '1':
        form.init_md5()
    else:
        if parent_node:
            rp_nodes = parent_node.find_all_children(child_name=node_name)
            if rp_nodes:
                for rp_node in rp_nodes:
                    if node_id == rp_node.id:
                        populate_responsible_party_form(form, rp_node)

    if node_name == names.PUBLISHER:
        help = [get_help('publisher')]
    return render_template('responsible_party.html', title=title,
                           form=form, role=role, next_page=next_page, save_and_continue=save_and_continue, help=help)


@rp_bp.route('/metadata_provider_select/<packageid>', methods=['GET', 'POST'])
def metadata_provider_select(packageid=None):
    form = ResponsiblePartySelectForm(packageid=packageid)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = select_post(packageid, form, form_dict,
                          'POST', PAGE_METADATA_PROVIDER_SELECT,
                          PAGE_CREATOR_SELECT, PAGE_ASSOCIATED_PARTY_SELECT,
                          PAGE_METADATA_PROVIDER)
        return redirect(url)

    # Process GET
    set_current_page('metadata_provider')
    help = [get_help('metadata_providers')]
    return rp_select_get(packageid=packageid, form=form,
                         rp_name=names.METADATAPROVIDER,
                         rp_singular=non_breaking('Metadata Provider'),
                         rp_plural=non_breaking('Metadata Providers'), help=help)


@rp_bp.route('/metadata_provider/<packageid>/<node_id>', methods=['GET', 'POST'])
def metadata_provider(packageid=None, node_id=None):
    method = request.method
    set_current_page('metadata_provider')
    return responsible_party(packageid=packageid, node_id=node_id,
                             method=method, node_name=names.METADATAPROVIDER,
                             back_page=PAGE_METADATA_PROVIDER_SELECT,
                             title='Metadata Provider')


@rp_bp.route('/associated_party_select/<packageid>', methods=['GET', 'POST'])
def associated_party_select(packageid=None):
    form = ResponsiblePartySelectForm(packageid=packageid)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = select_post(packageid, form, form_dict,
                          'POST', PAGE_ASSOCIATED_PARTY_SELECT,
                          PAGE_METADATA_PROVIDER_SELECT,
                          PAGE_PUBDATE,
                          PAGE_ASSOCIATED_PARTY)
        return redirect(url)

    # Process GET
    set_current_page('associated_party')
    help = [get_help('associated_parties')]
    return rp_select_get(packageid=packageid, form=form,
                         rp_name=names.ASSOCIATEDPARTY,
                         rp_singular=non_breaking('Associated Party'),
                         rp_plural=non_breaking('Associated Parties'), help=help)


@rp_bp.route('/associated_party/<packageid>/<node_id>', methods=['GET', 'POST'])
def associated_party(packageid=None, node_id=None):
    method = request.method
    set_current_page('associated_party')
    return responsible_party(packageid=packageid, node_id=node_id,
                             method=method, node_name=names.ASSOCIATEDPARTY,
                             back_page=PAGE_ASSOCIATED_PARTY_SELECT,
                             title='Associated Party')


@rp_bp.route('/contact_select/<packageid>', methods=['GET', 'POST'])
def contact_select(packageid=None):
    form = ResponsiblePartySelectForm(packageid=packageid)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = select_post(packageid, form, form_dict,
                          'POST', PAGE_CONTACT_SELECT, PAGE_TAXONOMIC_COVERAGE_SELECT,
                          PAGE_PUBLISHER, PAGE_CONTACT)
        return redirect(url)

    # Process GET
    set_current_page('contact')
    help = [get_help('contacts')]
    return rp_select_get(packageid=packageid, form=form, rp_name='contact',
                         rp_singular='Contact', rp_plural='Contacts', help=help)


@rp_bp.route('/contact/<packageid>/<node_id>', methods=['GET', 'POST'])
def contact(packageid=None, node_id=None):
    method = request.method
    set_current_page('contact')
    return responsible_party(packageid=packageid, node_id=node_id,
                             method=method, node_name=names.CONTACT,
                             back_page=PAGE_CONTACT_SELECT, title='Contact')


@rp_bp.route('/publisher/<packageid>', methods=['GET', 'POST'])
def publisher(packageid=None):
    method = request.method
    node_id = '1'
    if packageid:
        eml_node = load_eml(packageid=packageid)
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            publisher_node = dataset_node.find_child(names.PUBLISHER)
            if publisher_node:
                node_id = publisher_node.id
    set_current_page('publisher')
    help = [get_help('publisher')]
    return responsible_party(packageid=packageid, node_id=node_id,
                             method=method, node_name=names.PUBLISHER,
                             back_page=PAGE_CONTACT_SELECT, title='Publisher',
                             next_page=PAGE_PUBLICATION_PLACE,
                             save_and_continue=True, help=help)


def populate_responsible_party_form(form :ResponsiblePartyForm, node :Node):
    salutation_node = node.find_child(names.SALUTATION)
    if salutation_node:
        form.salutation.data = salutation_node.content

    gn_node = node.find_child(names.GIVENNAME)
    if gn_node:
        form.gn.data = gn_node.content

    sn_node = node.find_child(names.SURNAME)
    if sn_node:
        form.sn.data = sn_node.content

    user_id_node = node.find_child(names.USERID)
    if user_id_node:
        form.user_id.data = user_id_node.content

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

    role_node = node.find_child(names.ROLE)
    if role_node:
        form.role.data = role_node.content

    form.md5.data = form_md5(form)


@rp_bp.route('/project_personnel/<packageid>/<node_id>', methods=['GET', 'POST'])
def project_personnel(packageid=None, node_id=None):
    method = request.method
    set_current_page('project')
    return responsible_party(packageid=packageid, node_id=node_id,
                             method=method, node_name=names.PERSONNEL,
                             back_page=PAGE_PROJECT_PERSONNEL_SELECT, title='Project Personnel')
