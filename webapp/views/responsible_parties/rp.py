from flask import (
    Blueprint, flash, render_template, redirect, request, url_for
)
from flask_login import (
    login_required
)

from webapp.views.responsible_parties.forms import (
    ResponsiblePartyForm, ResponsiblePartySelectForm
)

from webapp.home.forms import (
    form_md5, is_dirty_form
)

from webapp.home.metapype_client import (
    load_eml, list_responsible_parties, save_both_formats,
    add_child, create_responsible_party,
    handle_hidden_buttons, check_val_for_hidden_buttons
)

from metapype.eml import names
from metapype.model.node import Node

from webapp.buttons import *
from webapp.pages import *

from webapp.home.views import select_post, non_breaking, set_current_page, get_help, get_helps


rp_bp = Blueprint('rp', __name__, template_folder='templates')


@rp_bp.route('/creator_select/<filename>', methods=['GET', 'POST'])
@login_required
def creator_select(filename=None):
    form = ResponsiblePartySelectForm(filename=filename)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = select_post(filename, form, form_dict,
                          'POST', PAGE_CREATOR_SELECT, PAGE_TITLE,
                          PAGE_CONTACT_SELECT, PAGE_CREATOR)
        return redirect(url)

    # Process GET
    set_current_page('creator')
    help = [get_help('creators')]
    return rp_select_get(filename=filename, form=form, rp_name=names.CREATOR,
                         rp_singular='Creator', rp_plural='Creators', help=help)


@rp_bp.route('/creator/<filename>/<node_id>', methods=['GET', 'POST'])
@login_required
def creator(filename=None, node_id=None):
    method = request.method
    set_current_page('creator')
    return responsible_party(filename=filename, rp_node_id=node_id,
                             node_name=names.CREATOR,
                             back_page=PAGE_CREATOR_SELECT,
                             next_page=PAGE_CREATOR_SELECT,
                             title = 'Creator')


def get_dataset_project_node_id(filename=None):
    eml_node = load_eml(filename=filename)
    dataset_node = eml_node.find_child(names.DATASET)
    project_node = dataset_node.find_child(names.PROJECT)
    if project_node:
        return project_node.id
    else:
        return None


def rp_select_get(filename=None, form=None, rp_name=None,
                  rp_singular=None, rp_plural=None, help=None, node_id=None, project_node_id=None):
    # Process GET
    eml_node = load_eml(filename=filename)
    rp_list = list_responsible_parties(eml_node, rp_name, project_node_id=project_node_id)
    title = rp_plural # rp_name.capitalize()
    related_project = project_node_id is not None and project_node_id != get_dataset_project_node_id(filename=filename)
    if related_project:
        rp_singular = 'Related ' + rp_singular
        rp_plural = 'Related ' + rp_plural

    return render_template('responsible_party_select.html', title=title,
                           rp_list=rp_list, form=form,
                           rp_singular=rp_singular, rp_plural=rp_plural,
                           help=help, relatedProject=related_project)


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
            else:
                new_page = check_val_for_hidden_buttons(val, new_page, back_page)

    return new_page


def responsible_party(filename=None, rp_node_id=None,
                      node_name=None, title=None, back_page=None,
                      next_page=None, save_and_continue=False, help=None,
                      parent_node_id=None):

    eml_node = load_eml(filename=filename)

    if node_name == names.PERSONNEL:
        if parent_node_id is None:
            parent_node = eml_node.find_single_node_by_path(['dataset', 'project'])
            parent_node_id = parent_node.id

    is_project = False
    is_data_source = False
    project_node_id = None
    data_source_node_id = None
    if parent_node_id:
        parent_node = Node.get_node_instance(parent_node_id)
        is_project = parent_node.name in [names.PROJECT, names.RELATED_PROJECT]
        is_data_source = parent_node.name == names.DATASOURCE
    if is_project:
        project_node_id = parent_node_id
    if is_data_source:
        data_source_node_id = parent_node_id

    if BTN_CANCEL in request.form:
        if is_project:
            url = url_for(back_page, filename=filename, project_node_id=parent_node_id)
        elif is_data_source:
            data_source_node = Node.get_node_instance(parent_node_id)
            method_step_node = data_source_node.parent
            url = url_for(back_page, filename=filename, ms_node_id=method_step_node.id, data_source_node_id=parent_node_id)
        else:
            url = url_for(back_page, filename=filename)
        return redirect(url)

    form = ResponsiblePartyForm(filename=filename)
    if not parent_node_id:
        dataset_node = eml_node.find_child(names.DATASET)
        parent_node_id = dataset_node.id
        parent_node = dataset_node

    role = False
    new_page = select_new_page(back_page, next_page)

    form_value = request.form
    form_dict = form_value.to_dict(flat=False)
    url = select_post(filename, form, form_dict,
                      'POST', PAGE_PUBLISHER,
                      PAGE_MAINTENANCE, PAGE_PUBLICATION_INFO,
                      PAGE_PUBLISHER, project_node_id=project_node_id)

    # If this is an associatedParty or a project personnel element,
    # set role to True so it will appear as a form field.
    if node_name == names.ASSOCIATEDPARTY or node_name == names.PERSONNEL:
        role = True

    # Process POST
    save = False
    if is_dirty_form(form):
        save = True

    if form.validate_on_submit():
        if save:
            salutation = form.salutation.data
            gn = form.gn.data
            mn = form.mn.data
            sn = form.sn.data
            user_id = form.user_id.data
            organization = form.organization.data
            org_id = form.org_id.data
            org_id_type = form.org_id_type.data
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

            if not rp_node_id or rp_node_id == '1':
                rp_node = Node(node_name, parent=parent_node)
            else:
                rp_node = Node.get_node_instance(rp_node_id)

            create_responsible_party(
                rp_node,
                filename,
                salutation,
                gn,
                mn,
                sn,
                user_id,
                organization,
                org_id,
                org_id_type,
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

            if rp_node_id and len(rp_node_id) != 1:
                old_rp_node = Node.get_node_instance(rp_node_id)
                if old_rp_node:
                    old_rp_parent_node = old_rp_node.parent
                    old_rp_parent_node.replace_child(old_rp_node, rp_node)
                else:
                    msg = f"No node found in the node store with node id {rp_node_id}"
                    raise Exception(msg)
            else:
                add_child(parent_node, rp_node)

            save_both_formats(filename=filename, eml_node=eml_node)
            # flash(f"Changes to the '{node_name}' element have been saved.")

            # There is at most only one publisher element, so we don't have a
            # list of publishers to navigate back to. Stay on this page after
            # saving changes.
            # FIXME
            if node_name == names.PUBLISHER:
                new_page = PAGE_PUBLICATION_INFO

        if node_name == names.PUBLISHER:
            return redirect(url)
        elif is_project:
            return redirect(url_for(PAGE_PROJECT_PERSONNEL_SELECT, filename=filename, project_node_id=project_node_id))
        elif is_data_source:
            data_source_node = Node.get_node_instance(data_source_node_id)
            method_step_node = data_source_node.parent
            return redirect(url_for(PAGE_DATA_SOURCE, filename=filename, ms_node_id=method_step_node.id, data_source_node_id=data_source_node_id))
        else:
            return redirect(url_for(new_page, filename=filename, node_id=parent_node_id))

    # Process GET
    if rp_node_id == '1':
        form.init_md5()
    else:
        rp_node = Node.get_node_instance(rp_node_id)
        populate_responsible_party_form(form, rp_node)

    if project_node_id:
        title = 'Related ' + title
    help = get_helps([node_name])
    return render_template('responsible_party.html', title=title, node_name=node_name,
                           form=form, role=role, next_page=next_page, save_and_continue=save_and_continue, help=help)

#
# def responsible_party(filename=None, node_id=None, method=None,
#                       node_name=None, back_page=None, title=None,
#                       next_page=None, save_and_continue=False, help=None,
#                       project_node_id=None, data_source_node_id=None):
#
#     if BTN_CANCEL in request.form:
#         if project_node_id:
#             url = url_for(back_page, filename=filename, project_node_id=project_node_id)
#         if data_source_node_id:
#             url = url_for(back_page, filename=filename, ms_node_id=node_id, data_source_node_id=data_source_node_id)
#         else:
#             url = url_for(back_page, filename=filename)
#         return redirect(url)
#
#     form = ResponsiblePartyForm(filename=filename)
#     eml_node = load_eml(filename=filename)
#     dataset_node = eml_node.find_child(names.DATASET)
#     if not dataset_node:
#         dataset_node = Node(names.DATASET, parent=eml_node)
#         add_child(eml_node, dataset_node)
#     parent_node = dataset_node
#     role = False
#     new_page = select_new_page(back_page, next_page)
#
#     form_value = request.form
#     form_dict = form_value.to_dict(flat=False)
#     url = select_post(filename, form, form_dict,
#                       'POST', PAGE_PUBLISHER,
#                       PAGE_MAINTENANCE, PAGE_PUBLICATION_INFO,
#                       PAGE_PUBLISHER, project_node_id=project_node_id)
#
#     # If this is an associatedParty or a project personnel element,
#     # set role to True so it will appear as a form field.
#     if node_name == names.ASSOCIATEDPARTY or node_name == names.PERSONNEL:
#         role = True
#
#     # If this is a project personnel party, place it under the
#     # project node, not under the dataset node
#     if node_name == names.PERSONNEL:
#         if not project_node_id:
#             project_node = dataset_node.find_child(names.PROJECT)
#             if not project_node:
#                 project_node = Node(names.PROJECT, parent=dataset_node)
#                 add_child(dataset_node, project_node)
#             parent_node = project_node
#         else:
#             parent_node = Node.get_node_instance(project_node_id)
#
#     if data_source_node_id:
#         parent_node = Node.get_node_instance(data_source_node_id)
#         new_page = PAGE_METHOD_STEP
#
#     # Process POST
#     save = False
#     if is_dirty_form(form):
#         save = True
#
#     if form.validate_on_submit():
#         if save:
#             salutation = form.salutation.data
#             gn = form.gn.data
#             mn = form.mn.data
#             sn = form.sn.data
#             user_id = form.user_id.data
#             organization = form.organization.data
#             org_id = form.org_id.data
#             org_id_type = form.org_id_type.data
#             position_name = form.position_name.data
#             address_1 = form.address_1.data
#             address_2 = form.address_2.data
#             city = form.city.data
#             state = form.state.data
#             postal_code = form.postal_code.data
#             country = form.country.data
#             phone = form.phone.data
#             fax = form.fax.data
#             email = form.email.data
#             online_url = form.online_url.data
#             role = form.role.data
#
#             rp_node = Node(node_name, parent=parent_node)
#
#             create_responsible_party(
#                 rp_node,
#                 filename,
#                 salutation,
#                 gn,
#                 mn,
#                 sn,
#                 user_id,
#                 organization,
#                 org_id,
#                 org_id_type,
#                 position_name,
#                 address_1,
#                 address_2,
#                 city,
#                 state,
#                 postal_code,
#                 country,
#                 phone,
#                 fax,
#                 email,
#                 online_url,
#                 role)
#
#             if node_id and len(node_id) != 1:
#                 old_rp_node = Node.get_node_instance(node_id)
#                 if old_rp_node:
#                     old_rp_parent_node = old_rp_node.parent
#                     old_rp_parent_node.replace_child(old_rp_node, rp_node)
#                 else:
#                     msg = f"No node found in the node store with node id {node_id}"
#                     raise Exception(msg)
#             else:
#                 add_child(parent_node, rp_node)
#
#             save_both_formats(filename=filename, eml_node=eml_node)
#             # flash(f"Changes to the '{node_name}' element have been saved.")
#
#             # There is at most only one publisher element, so we don't have a
#             # list of publishers to navigate back to. Stay on this page after
#             # saving changes.
#             # FIXME
#             if node_name == names.PUBLISHER:
#                 new_page = PAGE_PUBLICATION_INFO
#
#         if node_name == names.PUBLISHER:
#             return redirect(url)
#         elif new_page == PAGE_PROJECT_PERSONNEL_SELECT:
#             return redirect(url_for(new_page, filename=filename, project_node_id=project_node_id))
#         elif new_page == PAGE_DATA_SOURCE:
#             return redirect(url_for(new_page, filename=filename, ms_node_id=node_id, data_source_node_id=data_source_node_id))
#         else:
#             return redirect(url_for(new_page, filename=filename, node_id=project_node_id))
#
#     # Process GET
#     if node_id == '1':
#         form.init_md5()
#     else:
#         if parent_node:
#             rp_nodes = parent_node.find_all_children(child_name=node_name)
#             if rp_nodes:
#                 for rp_node in rp_nodes:
#                     if node_id == rp_node.id:
#                         populate_responsible_party_form(form, rp_node)
#
#     if project_node_id:
#         title = 'Related ' + title
#     help = get_helps([node_name])
#     return render_template('responsible_party.html', title=title, node_name=node_name,
#                            form=form, role=role, next_page=next_page, save_and_continue=save_and_continue, help=help)


@rp_bp.route('/metadata_provider_select/<filename>', methods=['GET', 'POST'])
@login_required
def metadata_provider_select(filename=None):
    form = ResponsiblePartySelectForm(filename=filename)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = select_post(filename, form, form_dict,
                          'POST', PAGE_METADATA_PROVIDER_SELECT,
                          PAGE_ASSOCIATED_PARTY_SELECT, PAGE_ABSTRACT,
                          PAGE_METADATA_PROVIDER)
        return redirect(url)

    # Process GET
    set_current_page('metadata_provider')
    help = [get_help('metadata_providers')]
    return rp_select_get(filename=filename, form=form,
                         rp_name=names.METADATAPROVIDER,
                         rp_singular=non_breaking('Metadata Provider'),
                         rp_plural=non_breaking('Metadata Providers'), help=help)


@rp_bp.route('/metadata_provider/<filename>/<node_id>', methods=['GET', 'POST'])
@login_required
def metadata_provider(filename=None, node_id=None):
    method = request.method
    set_current_page('metadata_provider')
    return responsible_party(filename=filename, rp_node_id=node_id,
                             node_name=names.METADATAPROVIDER,
                             back_page=PAGE_METADATA_PROVIDER_SELECT,
                             next_page=PAGE_METADATA_PROVIDER_SELECT,
                             title='Metadata Provider')


@rp_bp.route('/associated_party_select/<filename>', methods=['GET', 'POST'])
@login_required
def associated_party_select(filename=None):
    form = ResponsiblePartySelectForm(filename=filename)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = select_post(filename, form, form_dict,
                          'POST', PAGE_ASSOCIATED_PARTY_SELECT,
                          PAGE_CONTACT_SELECT,
                          PAGE_METADATA_PROVIDER_SELECT,
                          PAGE_ASSOCIATED_PARTY)
        return redirect(url)

    # Process GET
    set_current_page('associated_party')
    help = [get_help('associated_parties')]
    return rp_select_get(filename=filename, form=form,
                         rp_name=names.ASSOCIATEDPARTY,
                         rp_singular=non_breaking('Associated Party'),
                         rp_plural=non_breaking('Associated Parties'), help=help)


@rp_bp.route('/associated_party/<filename>/<node_id>', methods=['GET', 'POST'])
@login_required
def associated_party(filename=None, node_id=None):
    method = request.method
    set_current_page('associated_party')
    return responsible_party(filename=filename, rp_node_id=node_id,
                             node_name=names.ASSOCIATEDPARTY,
                             back_page=PAGE_ASSOCIATED_PARTY_SELECT,
                             next_page=PAGE_ASSOCIATED_PARTY_SELECT,
                             title='Associated Party')


@rp_bp.route('/contact_select/<filename>', methods=['GET', 'POST'])
@login_required
def contact_select(filename=None):
    form = ResponsiblePartySelectForm(filename=filename)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = select_post(filename, form, form_dict,
                          'POST', PAGE_CONTACT_SELECT, PAGE_CREATOR_SELECT,
                          PAGE_ASSOCIATED_PARTY_SELECT, PAGE_CONTACT)
        return redirect(url)

    # Process GET
    set_current_page('contact')
    help = [get_help('contacts')]
    return rp_select_get(filename=filename, form=form, rp_name='contact',
                         rp_singular='Contact', rp_plural='Contacts', help=help)


@rp_bp.route('/contact/<filename>/<node_id>', methods=['GET', 'POST'])
@login_required
def contact(filename=None, node_id=None):
    method = request.method
    set_current_page('contact')
    return responsible_party(filename=filename, rp_node_id=node_id,
                             node_name=names.CONTACT,
                             back_page=PAGE_CONTACT_SELECT,
                             next_page=PAGE_CONTACT_SELECT,
                             title='Contact')


@rp_bp.route('/publisher/<filename>', methods=['GET', 'POST'])
@login_required
def publisher(filename=None):
    method = request.method
    node_id = '1'
    if filename:
        eml_node = load_eml(filename=filename)
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            publisher_node = dataset_node.find_child(names.PUBLISHER)
            if publisher_node:
                node_id = publisher_node.id
    set_current_page('publisher')
    help = [get_help('publisher')]
    return responsible_party(filename=filename, rp_node_id=node_id,
                             node_name=names.PUBLISHER,
                             back_page=PAGE_CONTACT_SELECT,
                             next_page=PAGE_PUBLICATION_INFO,
                             title='Publisher',
                             save_and_continue=True, help=help)


def populate_responsible_party_form(form: ResponsiblePartyForm, node: Node):
    in_node = node.find_child(names.INDIVIDUALNAME)
    if in_node:
        salutation_node = in_node.find_child(names.SALUTATION)
        if salutation_node:
            form.salutation.data = salutation_node.content

        gn_nodes = in_node.find_all_children(names.GIVENNAME)
        if gn_nodes:
            form.gn.data = gn_nodes[0].content
            if len(gn_nodes) > 1:
                form.mn.data = gn_nodes[1].content

        sn_node = in_node.find_child(names.SURNAME)
        if sn_node:
            form.sn.data = sn_node.content

    user_id_nodes = node.find_all_children(names.USERID)
    for user_id_node in user_id_nodes:
        directory = user_id_node.attribute_value('directory')
        if 'orcid.org' in directory:
            form.user_id.data = user_id_node.content
        else:
            form.org_id.data = user_id_node.content
            form.org_id_type.data = directory

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


@rp_bp.route('/project_personnel/<filename>/<node_id>', methods=['GET', 'POST'])
@rp_bp.route('/project_personnel/<filename>/<node_id>/<project_node_id>', methods=['GET', 'POST'])
@login_required
def project_personnel(filename=None, node_id=None, project_node_id=None):
    method = request.method
    set_current_page('project')
    return responsible_party(filename=filename, rp_node_id=node_id,
                             node_name=names.PERSONNEL,
                             back_page=PAGE_PROJECT_PERSONNEL_SELECT,
                             next_page=PAGE_PROJECT_PERSONNEL_SELECT,
                             title='Project Personnel',
                             parent_node_id=project_node_id)


@rp_bp.route('/data_source_personnel/<filename>/<rp_type>/<rp_node_id>/<data_source_node_id>', methods=['GET', 'POST'])
@login_required
def data_source_personnel(filename=None, rp_type=None, rp_node_id=None, data_source_node_id=None):
    method = request.method
    set_current_page('data_source')
    return responsible_party(filename=filename, rp_node_id=rp_node_id,
                             node_name=rp_type,
                             back_page=PAGE_DATA_SOURCE,
                             next_page=PAGE_DATA_SOURCE,
                             title=f'Data Source {rp_type.capitalize()}',
                             parent_node_id=data_source_node_id)


# @rp_bp.route('/data_source_contact/<filename>/<rp_node_id>/<data_source_node_id>', methods=['GET', 'POST'])
# @login_required
# def data_source_contact(filename=None, rp_node_id=None, data_source_node_id=None):
#     method = request.method
#     set_current_page('data_source')
#     return responsible_party(filename=filename, node_id=rp_node_id,
#                              method=method, node_name=names.CONTACT,
#                              back_page=PAGE_DATA_SOURCE,
#                              next_page=PAGE_DATA_SOURCE,
#                              title='Contact',
#                              data_source_node_id=data_source_node_id)