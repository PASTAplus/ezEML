import html

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
    init_form_md5, is_dirty_form
)

from webapp.home.utils.hidden_buttons import handle_hidden_buttons, check_val_for_hidden_buttons
from webapp.home.utils.load_and_save import load_eml, save_both_formats
from webapp.home.utils.lists import list_responsible_parties
from webapp.home.utils.create_nodes import create_responsible_party
from webapp.home.utils.node_utils import add_child, new_child_node, replace_node

from metapype.eml import names
from metapype.model.node import Node

from webapp.buttons import *
from webapp.pages import *

from webapp.home.views import select_post, non_breaking, set_current_page, get_help, get_helps
from webapp.home.check_metadata import init_evaluation, format_tooltip


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
                          PAGE_CONTACT_SELECT, PAGE_CREATOR,
                          import_page=PAGE_IMPORT_PARTIES, import_target='Creators')
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

    init_form_md5(form)

    # Get the tooltip for the status badge
    init_evaluation(eml_node, filename)
    section = rp_plural.lower().replace(html.unescape('&nbsp;'), '_')
    tooltip = format_tooltip(None, section)

    return render_template('responsible_party_select.html', title=title,
                           rp_list=rp_list, form=form,
                           rp_singular=rp_singular, rp_plural=rp_plural,
                           help=help, tooltip=tooltip, section=section, relatedProject=related_project)


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
            elif val == BTN_SAVE_CHANGES:
                new_page = edit_page
                break
            else:
                new_page = check_val_for_hidden_buttons(val, new_page)

    return new_page


def responsible_party(filename=None, rp_node_id=None,
                      node_name=None, title=None, back_page=None,
                      next_page=None, save_and_continue=False, help=None,
                      parent_node_id=None):
    '''
    Create or edit a responsible party node. This is called in a variety of settings, and the input
    parameters are used to determine the context and the behavior of the function.

    node_name: The name of the responsible party node. In some cases, e.g., project personnel, the node name
    establishes the context of the responsible party node.

    parent_node_id: The id of the parent node of the responsible party node. This is used to determine
    the context of the responsible party node. If the parent node is a project, then the responsible
    party is a project personnel. If the parent node is a data source, then the responsible party is
    a data source personnel. If the parent node is a dataset, then the responsible party is a creator, contact, etc.


    '''
    eml_node = load_eml(filename=filename)
    form = ResponsiblePartyForm(filename=filename)

    if node_name == names.PERSONNEL:
        # Personnel nodes are children of project or data source nodes.
        # Get the parent node id so we can tell which case we're in.
        if parent_node_id is None:
            parent_node = eml_node.find_single_node_by_path(['dataset', 'project'])
            if not parent_node:
                dataset_node = eml_node.find_child(names.DATASET)
                project_node = new_child_node(names.PROJECT, dataset_node)
                parent_node = project_node

            parent_node_id = parent_node.id

    # Set up some flags that will indicate the context of the responsible party node
    is_project = False
    is_data_source = False
    project_node_id = None
    data_source_node_id = None
    parent_node = None
    if parent_node_id:
        parent_node = Node.get_node_instance(parent_node_id)
        if parent_node:
            is_project = parent_node.name in [names.PROJECT, names.RELATED_PROJECT]
            is_data_source = parent_node.name == names.DATASOURCE
    if not parent_node:
        dataset_node = eml_node.find_child(names.DATASET)
        parent_node_id = dataset_node.id
        parent_node = dataset_node

    if is_project:
        project_node_id = parent_node_id
    if is_data_source:
        data_source_node_id = parent_node_id

    role = False
    # If this is an associatedParty or a project personnel element,
    #   set role to True so it will appear as a form field.
    if node_name == names.ASSOCIATEDPARTY or node_name == names.PERSONNEL:
        role = True

    # Process POST
    if request.method == 'POST':

        if BTN_CANCEL in request.form:
            # Where we go back to and what parameters are required after a cancel depends on the context
            if is_project:
                url = url_for(back_page, filename=filename, project_node_id=parent_node_id)
            elif is_data_source:
                data_source_node = Node.get_node_instance(parent_node_id)
                method_step_node = data_source_node.parent
                url = url_for(back_page, filename=filename, ms_node_id=method_step_node.id, data_source_node_id=parent_node_id)
            else:
                url = url_for(back_page, filename=filename)
            return redirect(url)

        # Use the request endpoint to determine the page we're on. This is used to determine where to go on Save Changes.
        endpoint = request.endpoint
        if endpoint == 'rp.creator':
            this_page = PAGE_CREATOR
        elif endpoint == 'rp.contact':
            this_page = PAGE_CONTACT
        elif endpoint == 'rp.metadata_provider':
            this_page = PAGE_METADATA_PROVIDER
        elif endpoint == 'rp.associated_party':
            this_page = PAGE_ASSOCIATED_PARTY
        elif endpoint == 'rp.publisher':
            this_page = PAGE_PUBLISHER
        elif endpoint == 'rp.personnel':
            this_page = PAGE_PROJECT_PERSONNEL
        elif endpoint == 'rp.project_personnel':
            this_page = PAGE_PROJECT_PERSONNEL
        elif endpoint == 'rp.data_source_personnel':
            this_page = PAGE_DATA_SOURCE_PERSONNEL

        # role = False
        new_page = select_new_page(back_page, next_page, this_page)

        old_rp_node_id = rp_node_id

        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = select_post(filename, form, form_dict,
                          'POST', this_page,
                          PAGE_MAINTENANCE, PAGE_PUBLICATION_INFO,
                          PAGE_PUBLISHER, project_node_id=project_node_id,
                          import_page=PAGE_IMPORT_PARTIES, rp_node_id=rp_node_id)

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

                """
                If a responsibleParty node already exists, we still create a new one and pass it in as an argument to
                create_responsible_party. Upon return, we need to replace the existing responsibleParty node with the 
                new one. The reason for doing it this way is that the responsibleParty node is a complex node with many 
                child nodes, and it is easier to create a new one from scratch than to try to modify an existing one. 
                The responsibleParty node has a number of child nodes that have cardinality 0..infinity, which makes 
                it a lot more complicated to find and modify the appropriate children to modify.
                """
                rp_node = Node(node_name, parent=parent_node)

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
                        replace_node(rp_node, old_rp_node.id)
                    else:
                        msg = f"No node found in the node store with node id {rp_node_id}"
                        raise Exception(msg)
                else:
                    add_child(parent_node, rp_node)

                # We want generated URLs, below, to point to the new responsibleParty node, but we have
                #  given the new node the same node ID as the old node. So, we just leave the node ID as is.

                save_both_formats(filename=filename, eml_node=eml_node)
                # flash(f"Changes to the '{node_name}' element have been saved.")

                # There is at most only one publisher element, so we don't have a
                # list of publishers to navigate back to. Stay on this page after
                # saving changes.
                # FIXME
                if node_name == names.PUBLISHER:
                    new_page = PAGE_PUBLICATION_INFO

            if 'eml/data_source_personnel' in url:
                # Handle case of SAVE CHANGES on the Data Source Personnel page
                # We bracket the node IDs with slashes to handle the case when old_rp_node_id is '1'. In that case,
                #  we may end up replacing a '1' in the filename with the new node ID. Not the intended result.
                return redirect(url.replace(f'/{old_rp_node_id}/', f'/{rp_node_id}/'))

            if node_name == names.PUBLISHER:
                return redirect(url)
            elif is_project:
                return redirect(url_for(PAGE_PROJECT_PERSONNEL_SELECT, filename=filename, project_node_id=project_node_id))
            elif is_data_source:
                data_source_node = Node.get_node_instance(data_source_node_id)
                method_step_node = data_source_node.parent
                return redirect(url_for(PAGE_DATA_SOURCE, filename=filename, ms_node_id=method_step_node.id, data_source_node_id=data_source_node_id))
            else:
                return redirect(url_for(new_page, filename=filename, node_id=rp_node_id)) # node_id=parent_node_id))

    # Process GET
    if rp_node_id != '1':
        rp_node = Node.get_node_instance(rp_node_id)
        populate_responsible_party_form(form, rp_node)

        # Get the tooltip for the status badge
        init_evaluation(eml_node, filename)
        tooltip = format_tooltip(rp_node)

    else:
        init_form_md5(form)
        tooltip = ''

    if parent_node and parent_node.name == names.RELATED_PROJECT:
        title = 'Related ' + title
    help = get_helps([node_name, 'save_changes'])
    return render_template('responsible_party.html', title=title, node_name=node_name, rp_node_id=rp_node_id,
                           form=form, role=role, next_page=next_page, save_and_continue=save_and_continue,
                           tooltip=tooltip, help=help)


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
                          PAGE_METADATA_PROVIDER,
                          import_page=PAGE_IMPORT_PARTIES,
                          import_target='Metadata Providers')
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
                          PAGE_ASSOCIATED_PARTY,
                          import_page=PAGE_IMPORT_PARTIES,
                          import_target='Associated Parties')
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
                          PAGE_ASSOCIATED_PARTY_SELECT, PAGE_CONTACT,
                          import_page=PAGE_IMPORT_PARTIES, import_target='Contacts')
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

    # Get the tooltip for the status badge
    # init_evaluation(eml_node, filename)
    # tooltip = format_tooltip(None, 'publisher')

    set_current_page('publisher')
    help = [get_help('publisher')]
    return responsible_party(filename=filename, rp_node_id=node_id,
                             node_name=names.PUBLISHER,
                             back_page=PAGE_CONTACT_SELECT,
                             next_page=PAGE_PUBLICATION_INFO,
                             title='Publisher',
                             save_and_continue=True,
                             help=help)


def normalize_directory_for_user_id(directory):
    # The directory associated with an userId may not have the exact form that ezEML expects.
    # When ezEML was only handling packages that had been created in ezEML, this wouldn't happen,
    #  but of course now we are handling packages that have been created in other ways.
    # This function normalizes the directory to the form that ezEML expects.
    if directory is not None:
        directory = directory.lower().replace('http:', 'https:')
        if not directory.endswith('/'):
            directory += '/'
    else:
        directory = ''
    return directory


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
        directory = normalize_directory_for_user_id(user_id_node.attribute_value('directory'))
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

    phone_nodes = node.find_all_children(names.PHONE)
    have_voice = False
    have_fax = False
    for phone_node in phone_nodes:
        phone_type = phone_node.attribute_value('phonetype')
        if phone_type:
            phone_type = phone_type.lower()
        if phone_type == 'facsimile' or phone_type == 'fax':
            if have_fax:
                # We already have a fax number, so skip this one. We can only display one fax number.
                # Cases of multiple fax numbers will only occur if the EML was created by another tool.
                continue
            have_fax = True
            form.fax.data = phone_node.content
        elif phone_type == 'voice' or phone_type == 'telephone' or phone_type is None:
            if have_voice:
                # We already have a voice number, so skip this one. We can only display one voice number.
                # Cases of multiple voice numbers will only occur if the EML was created by another tool.
                continue
            have_voice = True
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

    init_form_md5(form)


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


@rp_bp.route('/data_source_personnel/<filename>/<rp_type>/<rp_node_id>/<method_step_node_id>/<data_source_node_id>', methods=['GET', 'POST'])
@login_required
def data_source_personnel(filename=None, rp_type=None, rp_node_id=None, method_step_node_id=None, data_source_node_id=None):
    # The reason we need the method_step_node_id in the route is so that when we look at the error links produced by check_metadata,
    #  we can recognize the error as pertaining to that method step. rp_type is creator or contact.
    set_current_page('data_source')
    return responsible_party(filename=filename, rp_node_id=rp_node_id,
                             node_name=rp_type,
                             back_page=PAGE_DATA_SOURCE,
                             next_page=PAGE_DATA_SOURCE,
                             title=f'Data Source {rp_type.capitalize()}',
                             parent_node_id=data_source_node_id)
