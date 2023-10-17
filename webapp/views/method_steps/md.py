import collections
from flask import (
    Blueprint, flash, render_template, redirect, request, url_for
)
from flask_login import (
    login_required, current_user
)
import os
from urllib.parse import urlencode, urlparse, quote, unquote

import webapp.home.utils.create_nodes
import webapp.home.utils.node_utils
from webapp.home.forms import (
    form_md5, is_dirty_form, EDIForm
)

from webapp.home.views import (
    process_up_button, process_down_button,
    AUTH_TOKEN_FLASH_MSG
)
from webapp.home.utils.node_utils import remove_child, new_child_node, add_child
from webapp.home.utils.hidden_buttons import check_val_for_hidden_buttons
from webapp.home.utils.load_and_save import load_eml, save_both_formats
from webapp.home.utils.import_nodes import compose_rp_label
from webapp.home.utils.lists import get_upval, get_downval, UP_ARROW, DOWN_ARROW, list_method_steps

from webapp.home.exceptions import (
    ezEMLError,
    AuthTokenExpired,
    DataTableError,
    MissingFileError,
    Unauthorized,
    UnicodeDecodeErrorInternal
)
from webapp.home.texttype_node_processing import (
    display_texttype_node,
    model_has_complex_texttypes,
    invalid_xml_error_message,
    is_valid_xml_fragment
)
from webapp.home.fetch_data import get_pasta_identifiers, get_revisions_list
from webapp.views.method_steps.forms import (
    MethodStepForm, MethodStepSelectForm, DataSourceForm
)
from webapp.home.views import (
    set_current_page, get_help, reload_metadata, get_helps, select_post
)
from webapp.buttons import *
from webapp.pages import *

from metapype.eml import names
from metapype.model.node import Node
from webapp.home.utils.create_nodes import create_method_step, create_data_source
import webapp.auth.user_data as user_data
from webapp.home.fetch_data import get_metadata_revision_from_pasta
from webapp.home.import_xml import parse_xml_file
from webapp.home.log_usage import log_usage, actions
from webapp.config import Config

md_bp = Blueprint('md', __name__, template_folder='templates')
data_sources_marker_begin = '==================== Data Sources ========================='
data_sources_marker_end = '==========================================================='


@md_bp.route('/method_step_select/<filename>', methods=['GET', 'POST'])
@login_required
def method_step_select(filename=None):
    form = MethodStepSelectForm(filename=filename)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        node_id = ''
        new_page = ''
        url = ''
        this_page = PAGE_METHOD_STEP_SELECT
        edit_page = PAGE_METHOD_STEP
        back_page = PAGE_PUBLICATION_INFO
        next_page = PAGE_PROJECT

        if form_dict:
            for key in form_dict:
                val = form_dict[key][0]  # value is the first list element
                if val == BTN_BACK:
                    new_page = back_page
                elif val in [BTN_NEXT, BTN_SAVE_AND_CONTINUE]:
                    new_page = next_page
                elif val == BTN_EDIT:
                    new_page = edit_page
                    node_id = key
                elif val == BTN_REMOVE:
                    new_page = this_page
                    node_id = key
                    eml_node = load_eml(filename=filename)
                    node = Node.get_node_instance(node_id)
                    remove_child(node)
                    save_both_formats(filename=filename, eml_node=eml_node)
                elif val == UP_ARROW:
                    new_page = this_page
                    node_id = key
                    process_up_button(filename, node_id)
                elif val == DOWN_ARROW:
                    new_page = this_page
                    node_id = key
                    process_down_button(filename, node_id)
                elif val[0:3] == 'Add':
                    new_page = edit_page
                    node_id = '1'
                elif val == '[  ]':
                    new_page = this_page
                    node_id = key
                else:
                    new_page = check_val_for_hidden_buttons(val, new_page)

        if form.validate_on_submit():
            if new_page in [edit_page, this_page]:
                url = url_for(new_page,
                              filename=filename,
                              node_id=node_id)
            else:
                url = url_for(new_page,
                              filename=filename)
            return redirect(url)

    # Process GET
    method_step_list = []
    title = 'Method Steps'
    eml_node = load_eml(filename=filename)

    if eml_node:
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            method_step_list = list_method_steps(dataset_node)

    set_current_page('method_step')
    help = [get_help('methods')]
    return render_template('method_step_select.html', title=title,
                           filename=filename,
                           method_step_list=method_step_list,
                           form=form, help=help)


# node_id is the id of the methodStep node being edited. If the value is
# '1', it means we are adding a new methodStep node, otherwise we are
# editing an existing one.
#
@md_bp.route('/method_step/<filename>/<node_id>', methods=['GET', 'POST'])
@login_required
def method_step(filename=None, node_id=None):
    eml_node = load_eml(filename=filename)
    dataset_node = eml_node.find_child(names.DATASET)

    if dataset_node:
        methods_node = dataset_node.find_child(names.METHODS)
    else:
        dataset_node = Node(names.DATASET, parent=eml_node)
        add_child(eml_node, dataset_node)

    if not methods_node:
        methods_node = Node(names.METHODS, parent=dataset_node)
        add_child(dataset_node, methods_node)

    form = MethodStepForm(filename=filename, node_id=node_id)

    # Process POST
    if request.method == 'POST' and BTN_CANCEL in request.form:
            url = url_for(PAGE_METHOD_STEP_SELECT, filename=filename)
            return redirect(url)

    if request.method == 'POST' and form.validate_on_submit():
        new_page = PAGE_METHOD_STEP_SELECT  # Save or Back sends us back to the list of method steps

        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        if form_dict:
            for key in form_dict:
                val = form_dict[key][0]  # value is the first list element
                if val == BTN_ADD_DATA_SOURCE:
                    new_page = PAGE_DATA_SOURCE
                    break
                elif val == BTN_FETCH_DATA_SOURCE:
                    new_page = PAGE_FETCH_DATA_SOURCE
                    break
                elif val == BTN_REMOVE:
                    ms_node_id, data_source_node_id = key.split('|')
                    method_step_node = Node.get_node_instance(id=ms_node_id)
                    data_source_node = Node.get_node_instance(id=data_source_node_id)
                    webapp.home.utils.node_utils.remove_child(data_source_node)
                    save_both_formats(filename=filename, eml_node=eml_node)
                    new_page = PAGE_METHOD_STEP
                    break
                elif val == BTN_EDIT:
                    form_value = request.form
                    form_dict = form_value.to_dict(flat=False)
                    url = select_post(filename, form, form_dict,
                                      'POST', PAGE_METHOD_STEP_SELECT, PAGE_METHOD_STEP_SELECT,
                                      PAGE_PROJECT, PAGE_DATA_SOURCE)
                    return redirect(url)

                new_page = check_val_for_hidden_buttons(val, new_page)

        submit_type = None
        if is_dirty_form(form):
            submit_type = 'Save Changes'

        if submit_type == 'Save Changes':
            description = form.description.data
            valid, msg = is_valid_xml_fragment(description, names.MAINTENANCE)
            if not valid:
                flash(invalid_xml_error_message(msg, False, names.DESCRIPTION), 'error')
                return render_get_method_step_page(eml_node, form, filename)

            instrumentation = form.instrumentation.data
            data_sources = form.data_sources.data
            method_step_node = Node.get_node_instance(node_id)
            if not method_step_node:
                method_step_node = Node(names.METHODSTEP, parent=methods_node)
                add_child(methods_node, method_step_node)
                node_id = method_step_node.id
            create_method_step(method_step_node, description, instrumentation, data_sources,
                               data_sources_marker_begin, data_sources_marker_end)

            save_both_formats(filename=filename, eml_node=eml_node)

        if new_page == PAGE_DATA_SOURCE:
            url = url_for(new_page,
                          filename=filename,
                          ms_node_id=node_id,
                          data_source_node_id='1')

        elif new_page in [PAGE_FETCH_DATA_SOURCE, PAGE_METHOD_STEP]:
            url = url_for(new_page,
                          filename=filename,
                          node_id=node_id)
        else:
            url = url_for(new_page, filename=filename)
        return redirect(url)

    # Process GET
    if node_id == '1':
        form.init_md5()
    else:
        method_step_node = Node.get_node_instance(node_id)
        if method_step_node:
            populate_method_step_form(form, method_step_node)
    if form.description.data:
        deprecated_data_source = (data_sources_marker_begin in form.description.data)
    else:
        deprecated_data_source = False
    return render_get_method_step_page(eml_node, form, filename,
                                       deprecated_data_source=deprecated_data_source)


def render_get_method_step_page(eml_node, form, filename, deprecated_data_source=False):
    set_current_page('method_step')
    help = get_helps(['method_step_description',
                      'method_step_instrumentation',
                      'method_step_data_sources',
                      'deprecated_data_source'])
    return render_template('method_step.html', title='Method Step',
                           model_has_complex_texttypes=model_has_complex_texttypes(eml_node),
                           deprecated_data_source=deprecated_data_source,
                           form=form, filename=filename, help=help)


def populate_method_step_form(form: MethodStepForm, ms_node: Node):
    description = ''
    instrumentation = ''
    data_sources = ''
    data_sources_list = []

    if ms_node:
        description_node = ms_node.find_child(names.DESCRIPTION)
        if description_node:
            description = display_texttype_node(description_node)
            # The following code is now obsolete. It has been retained here for reference.
            # We now display the data sources info inline with the description in the relatively small number of
            #  data packages that entered data sources is this way. The current way is to display the data sources
            #  in a separate, structured section.
            # if data_sources_marker_begin in description and data_sources_marker_end in description:
            #     begin = description.find(data_sources_marker_begin)
            #     end = description.find(data_sources_marker_end)
            #     data_sources = description[begin+len(data_sources_marker_begin)+1:end-1]
            #     description = description[0:begin-1]

        instrumentation = ''
        instrumentation_node = ms_node.find_child(names.INSTRUMENTATION)
        if instrumentation_node:
            instrumentation = instrumentation_node.content

        ms_node_id = ms_node.id
        data_sources_nodes = ms_node.find_all_children(names.DATASOURCE)
        if data_sources_nodes:
            for ds_node in data_sources_nodes:
                title = ''  # If we have a data source with no title, we still want to list it so it can be removed
                title_node = ds_node.find_child(names.TITLE)
                if title_node:
                    title = title_node.content
                    title = (title[:67] + '...') if len(title) > 70 else title
                data_sources_list.append((title, f'{ms_node_id}|{ds_node.id}'))

        form.description.data = description
        form.instrumentation.data = instrumentation
        form.data_sources.data = data_sources
        form.data_sources_list = data_sources_list
    form.md5.data = form_md5(form)


@md_bp.route('/fetch_data_source/<node_id>', methods=['GET', 'POST'])
@login_required
def fetch_data_source(node_id=None):

    form = EDIForm()

    # Process POST

    reload_metadata()  # So check_metadata status is correct

    if request.method == 'POST' and BTN_CANCEL in request.form:
        filename = user_data.get_active_document()
        if filename and node_id:
            if node_id:
                return redirect(url_for(PAGE_METHOD_STEP, filename=filename, node_id=node_id))
            else:
                return redirect(url_for(PAGE_METHOD_STEP_SELECT, filename=filename))
        else:
            return redirect(url_for(PAGE_INDEX))

    # Process GET
    form.md5.data = form_md5(form)

    try:
        ids = get_pasta_identifiers()
    except (AuthTokenExpired, Unauthorized) as e:
        flash(AUTH_TOKEN_FLASH_MSG, 'error')
        help = get_helps(['fetch_data_source'])
        return redirect(url_for('home.fetch_data_source', node_id=node_id, form=form, help=help))

    package_links = ''
    parsed_url = urlparse(request.base_url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}/eml"
    for id in ids:
        new_link = f"{base_url}/fetch_data_source_2/{node_id}/{id}"
        new_anchor = f'<br><a href="{new_link}">{id}</a>'
        package_links = package_links + new_anchor

    help = get_helps(['fetch_data_source'])
    return render_template('fetch_data_source.html', package_links=package_links, form=form, help=help)


@md_bp.route('/fetch_data_source_2/<node_id>/<scope>', methods=['GET', 'POST'])
@login_required
def fetch_data_source_2(node_id=None, scope=''):

    form = EDIForm()

    # Process POST

    reload_metadata()  # So check_metadata status is correct

    if request.method == 'POST' and BTN_CANCEL in request.form:
        filename = user_data.get_active_document()
        if filename and node_id:
            if node_id:
                return redirect(url_for(PAGE_METHOD_STEP, filename=filename, node_id=node_id))
            else:
                return redirect(url_for(PAGE_METHOD_STEP_SELECT, filename=filename))
        else:
            return redirect(url_for(PAGE_INDEX))

    # Process GET
    form.md5.data = form_md5(form)

    ids = get_pasta_identifiers(scope)
    package_links = ''
    parsed_url = urlparse(request.base_url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}/eml"
    for id in ids:
        new_link = f"{base_url}/fetch_data_source_2a/{node_id}/{scope}.{id}"
        new_anchor = f'<br><a href="{new_link}">{scope}.{id}</a>'
        package_links = package_links + new_anchor

    help = get_helps(['fetch_data_source_2'])
    return render_template('fetch_data_source_2.html', node_id=node_id, scope=scope,
                           package_links=package_links, form=form, help=help)


@md_bp.route('/fetch_data_source_2a/<node_id>/<scope_identifier>', methods=['GET', 'POST'])
@login_required
def fetch_data_source_2a(node_id=None, scope_identifier=''):

    form = EDIForm()

    # Process POST

    reload_metadata()  # So check_metadata status is correct

    if request.method == 'POST' and BTN_CANCEL in request.form:
        filename = user_data.get_active_document()
        if filename and node_id:
            if node_id:
                return redirect(url_for(PAGE_METHOD_STEP, filename=filename, node_id=node_id))
            else:
                return redirect(url_for(PAGE_METHOD_STEP_SELECT, filename=filename))
        else:
            return redirect(url_for(PAGE_INDEX))

    # Process GET
    form.md5.data = form_md5(form)

    scope, identifier = scope_identifier.split('.')

    revisions = get_revisions_list(scope, identifier)
    if len(revisions) == 1:
        return redirect(url_for('md.fetch_data_source_3', method_step_node_id=node_id,
                                scope_identifier=scope_identifier, revision=revisions[0]))
    else:
        package_links = ''
        parsed_url = urlparse(request.base_url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}/eml"
        for revision in revisions:
            new_link = f"{base_url}/fetch_data_source_3/{node_id}/{scope}.{identifier}/{revision}"
            new_anchor = f'<br><a href="{new_link}">{revision}</a>'
            package_links = package_links + new_anchor

        help = get_helps(['fetch_data_source_2a'])
        return render_template('fetch_data_source_2a.html', method_step_node_id=node_id, scope_identifier=scope_identifier,
                               package_links=package_links, form=form, help=help)


@md_bp.route('/fetch_data_source_3/<method_step_node_id>/<scope_identifier>/<revision>', methods=['GET', 'POST'])
@login_required
def fetch_data_source_3(method_step_node_id=None, scope_identifier='', revision=''):

    form = EDIForm()

    # Process POST

    reload_metadata()  # So check_metadata status is correct

    if request.method == 'POST' and BTN_CANCEL in request.form:
        filename = user_data.get_active_document()
        if filename and method_step_node_id:
            if method_step_node_id:
                return redirect(url_for(PAGE_METHOD_STEP, filename=filename, node_id=method_step_node_id))
            else:
                return redirect(url_for(PAGE_METHOD_STEP_SELECT, filename=filename))
        else:
            return redirect(url_for(PAGE_INDEX))

    # Process GET
    form.md5.data = form_md5(form)

    scope, identifier = scope_identifier.split('.')

    try:
        fetch_provenance_info_from_edi(method_step_node_id, scope, identifier, revision)
        return redirect(url_for(PAGE_METHOD_STEP, filename=user_data.get_active_document(), node_id=method_step_node_id))
        # log_usage(actions['FETCH_FROM_EDI'], f"{scope}.{identifier}.{revision}")
    except (AuthTokenExpired, Unauthorized) as e:
        flash(AUTH_TOKEN_FLASH_MSG, 'error')
        help = get_helps(['fetch_data_source'])
        return redirect(url_for('home.fetch_data_source', form=form, help=help))
    except Exception as e:
        flash(f'Unable to fetch package {scope}.{identifier}: {str(e)}', 'error')
        help = get_helps(['fetch_data_source'])
        return redirect(url_for('home.fetch_data_source', form=form, help=help))

    help = get_helps(['fetch_data_source'])
    return render_template('fetch_xml_3.html', node_id=node_id, scope_identifier=scope_identifier, revision=revision,
                           form=form, help=help)


def add_child(parent_node, child_node):
    webapp.home.utils.node_utils.add_child(parent_node, child_node)
    child_node.parent = parent_node


def fetch_provenance_info_from_edi(method_step_node_id, scope, identifier, revision=None):
    """Fetch provenance info from EDI."""

    active_eml_node = load_eml(filename=user_data.get_active_document())
    method_step_node = Node.get_node_instance(method_step_node_id)

    # This may raise exceptions AuthTokenExpired, Unauthorized, or some other
    revision, metadata = get_metadata_revision_from_pasta(scope, identifier, revision)
    log_usage(actions['FETCH_PROVENANCE_INFO'], f"{scope}.{identifier}.{revision}")
    # except (AuthTokenExpired, Unauthorized) as e:
    #     flash(AUTH_TOKEN_FLASH_MSG, 'error')
    #     help = get_helps(['import_xml_3'])
    #     return redirect(url_for('home.fetch_xml', form=form, help=help))
    # except Exception as e:
    #     flash(f'Unable to fetch package {scope}.{identifier}: {str(e)}', 'error')
    #     help = get_helps(['import_xml_3'])
    #     return redirect(url_for('home.fetch_xml', form=form, help=help))

    filename = f"{scope}.{identifier}.{revision}.xml"
    if current_user:
        user_data_dir = user_data.get_user_folder_name()
    else:  # TEMP for debugging
        user_data_dir = '/Users/jide/Downloads'
    work_path = os.path.join(user_data_dir, 'zip_temp')
    try:
        os.mkdir(work_path)
    except FileExistsError:
        pass
    work_path = os.path.join(work_path, filename)
    with open(work_path, 'wb') as metadata_file:
        metadata_file.write(metadata)

    ds_eml_node, *_ = parse_xml_file(filename, work_path)

    # Delete the file
    os.remove(work_path)

    # Get the dataset title
    dataset_node = ds_eml_node.find_child(names.DATASET)
    dataset_title_node = dataset_node.find_child(names.TITLE)
    creator_nodes = dataset_node.find_all_children(names.CREATOR)
    contact_nodes = dataset_node.find_all_children(names.CONTACT)

    data_source_node = new_child_node(names.DATASOURCE, parent=method_step_node)
    add_child(data_source_node, dataset_title_node)

    for creator_node in creator_nodes:
        add_child(data_source_node, creator_node)
    for contact_node in contact_nodes:
        add_child(data_source_node, contact_node)

    distribution_node = new_child_node(names.DISTRIBUTION, parent=data_source_node)
    online_node = new_child_node(names.ONLINE, parent=distribution_node)
    online_description_node = new_child_node(names.ONLINEDESCRIPTION, parent=online_node)
    online_description_node.content = 'This online link references an EML document that describes data used in the creation of this derivative data package.'
    url_node = new_child_node(names.URL, parent=online_node)
    url_node.content = f"{Config.PASTA_URL}/metadata/eml/{scope}/{identifier}/{revision}"

    # Save the EML
    save_both_formats(filename=user_data.get_active_document(), eml_node=active_eml_node)


def guarantee_data_source_existence(form, filename, ms_node_id=None, data_source_node_id=None):
    # If user clicks Add Creator or Add Contact, we need to make sure the data source exists first
    # before going to the add creator or add contact page
    eml_node = load_eml(filename=filename)
    if data_source_node_id != '1':
        data_source_node = Node.get_node_instance(data_source_node_id)
    else:
        ms_node = Node.get_node_instance(ms_node_id)
        data_source_node = Node(names.DATASOURCE)
        add_child(ms_node, data_source_node)
    create_data_source(data_source_node,
                       form.title.data,
                       form.online_description.data,
                       form.url.data)
    save_both_formats(filename=filename, eml_node=eml_node)
    return data_source_node.id


@md_bp.route('/data_source/<filename>/<ms_node_id>/<data_source_node_id>', methods=['GET', 'POST'])
@login_required
def data_source(filename, ms_node_id, data_source_node_id):
    form = DataSourceForm()

    # Process POST

    reload_metadata()  # So check_metadata status is correct

    if request.method == 'POST' and BTN_CANCEL in request.form:
        filename = user_data.get_active_document()
        return redirect(url_for(PAGE_METHOD_STEP, filename=filename, node_id=ms_node_id))

    if request.method == 'POST':
        if form.validate_on_submit():

            if BTN_EDIT in request.form.values():
                for key, val in request.form.items():
                    if val == BTN_EDIT:
                        rp_type, rp_node_id, data_source_node_id = key.split('|')
                        return redirect(url_for(PAGE_DATA_SOURCE_PERSONNEL, filename=filename, rp_type=rp_type, rp_node_id=rp_node_id, data_source_node_id=data_source_node_id))
            if BTN_REMOVE in request.form.values():
                for key, val in request.form.items():
                    if val == BTN_REMOVE:
                        _, rp_node_id, _ = key.split('|')
                        eml_node = load_eml(filename=filename)
                        node = Node.get_node_instance(rp_node_id)
                        remove_child(node)
                        save_both_formats(filename=filename, eml_node=eml_node)
                        # drop through to reload the page
            if BTN_ADD_CREATOR in request.form.values():
                data_source_node_id = guarantee_data_source_existence(form, filename, ms_node_id, data_source_node_id)
                return redirect(
                    url_for(PAGE_DATA_SOURCE_PERSONNEL, filename=filename, rp_type='creator', rp_node_id=1,
                            data_source_node_id=data_source_node_id))
            if BTN_ADD_CONTACT in request.form.values():
                data_source_node_id = guarantee_data_source_existence(form, filename, ms_node_id, data_source_node_id)
                return redirect(
                    url_for(PAGE_DATA_SOURCE_PERSONNEL, filename=filename, rp_type='contact', rp_node_id=1,
                            data_source_node_id=data_source_node_id))
            if BTN_SAVE_AND_CONTINUE in request.form.values():
                guarantee_data_source_existence(form, filename, ms_node_id, data_source_node_id)
                return redirect(url_for(PAGE_METHOD_STEP, filename=filename, node_id=ms_node_id))

    # Process GET
    form.md5.data = form_md5(form)
    help = get_helps(['data_source', 'data_source_title', 'data_source_online_description', 'data_source_url',
                      'data_source_creators', 'data_source_contacts'])

    creator_list, contact_list = populate_data_source(form, data_source_node_id)

    return render_template('data_source.html', data_source_node_id=data_source_node_id,
                           creator_list=creator_list, contact_list=contact_list,
                           form=form, help=help)


def list_responsible_parties(rp_nodes, node_name:str=None):
    rp_list = []

    RP_Entry = collections.namedtuple(
        'RP_Entry', ["rp_node_id", "data_source_node_id", "label", "upval", "downval"],
         rename=False)
    for i, rp_node in enumerate(rp_nodes):
        label = compose_rp_label(rp_node)
        rp_node_id = f"{rp_node.id}"
        data_source_node_id = f"{rp_node.parent.id}"
        upval = get_upval(i)
        downval = get_downval(i+1, len(rp_nodes))
        rp_entry = RP_Entry(rp_node_id=rp_node_id, data_source_node_id=data_source_node_id, label=label, upval=upval, downval=downval)
        rp_list.append(rp_entry)
    return rp_list


def populate_data_source(form: DataSourceForm, data_source_node_id: str):
    title = ''
    online_description = ''
    url = ''

    if data_source_node_id == '1':
        return [], []

    data_source_node = Node.get_node_instance(data_source_node_id)
    title_node = data_source_node.find_child(names.TITLE)
    if title_node:
        title = title_node.content
    creator_nodes = data_source_node.find_all_children(names.CREATOR)
    contact_nodes = data_source_node.find_all_children(names.CONTACT)
    online_description_node = data_source_node.find_single_node_by_path([names.DISTRIBUTION, names.ONLINE, names.ONLINEDESCRIPTION])
    if online_description_node:
        online_description = online_description_node.content
    url_node = data_source_node.find_single_node_by_path([names.DISTRIBUTION, names.ONLINE, names.URL])
    if url_node:
        url = url_node.content

    form.title.data = title
    form.online_description.data = online_description
    form.url.data = url

    creator_list = list_responsible_parties(creator_nodes)
    contact_list = list_responsible_parties(contact_nodes)

    return creator_list, contact_list
