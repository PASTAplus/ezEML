"""
Routes for project and related project pages.
"""

import collections
import requests

import daiquiri
from flask import (
    Blueprint, flash, render_template, redirect, request, url_for
)
from flask_login import (
    current_user, login_required
)

from webapp.home.home_utils import log_error, log_info
from webapp.home.utils.hidden_buttons import (
	is_hidden_button, handle_hidden_buttons, check_val_for_hidden_buttons, non_saving_hidden_buttons_decorator
)

from webapp.home.utils.node_utils import remove_child, add_child
from webapp.home.utils.node_store import dump_node_store
from webapp.home.utils.load_and_save import load_eml, save_both_formats
from webapp.home.utils.lists import get_upval, get_downval, UP_ARROW, DOWN_ARROW, list_funding_awards
from webapp.home.utils.create_nodes import create_project, create_related_project, create_funding_award
from webapp.home.exceptions import NodeWithGivenIdNotFound

from webapp.home.texttype_node_processing import (
    display_texttype_node,
    model_has_complex_texttypes,
    is_valid_xml_fragment,
    invalid_xml_error_message, post_process_texttype_node
)

from webapp.home.forms import is_dirty_form, init_form_md5
from webapp.home.views import (
    non_breaking, process_up_button, process_down_button, select_post, set_current_page, get_help
)
from webapp.views.project.forms import (
    ProjectForm, AwardSelectForm, AwardForm, RelatedProjectSelectForm
)

from webapp.views.responsible_parties.rp import rp_select_get
from webapp.views.responsible_parties.forms import ResponsiblePartySelectForm

from webapp.buttons import *
from webapp.pages import *
from metapype.eml import names
from metapype.model.node import Node
from webapp.home.check_metadata import init_evaluation, format_tooltip


proj_bp = Blueprint('proj', __name__, template_folder='templates')


@proj_bp.route('/project/<filename>', methods=['GET', 'POST'])
@proj_bp.route('/project/<filename>/<project_node_id>', methods=['GET', 'POST'])
@login_required
def project(filename=None, project_node_id=None):
    form = ProjectForm(filename=filename)
    eml_node = load_eml(filename=filename)
    if eml_node:
        dataset_node = eml_node.find_child(names.DATASET)
        if not dataset_node:
            dataset_node = Node(names.DATASET, parent=eml_node)
            add_child(eml_node, dataset_node)

    doing_related_project = False
    if project_node_id:
        try:
            project_node = Node.get_node_instance(project_node_id)
            doing_related_project = project_node_id == '1' or project_node.name == names.RELATED_PROJECT
        except:
            pass

    # Process POST
    if request.method == 'POST' and form.validate_on_submit():
        save = False
        if is_dirty_form(form):
            save = True

        # if not node_id:
        if not doing_related_project:
            this_page = PAGE_PROJECT
        else:
            this_page = PAGE_RELATED_PROJECT_SELECT  # FIXME?
        new_page = None

        if 'Next' in request.form:
            # if not node_id:
            if not doing_related_project:
                new_page = PAGE_OTHER_ENTITY_SELECT
            else:
                new_page = PAGE_RELATED_PROJECT_SELECT
        elif BTN_PROJECT_PERSONNEL in request.form:
            new_page = PAGE_PROJECT_PERSONNEL_SELECT
        elif BTN_FUNDING_AWARDS in request.form:
            new_page = PAGE_FUNDING_AWARD_SELECT
        elif BTN_RELATED_PROJECTS in request.form:
            new_page = PAGE_RELATED_PROJECT_SELECT
            # doing_related_project = True
        elif BTN_IMPORT in request.form:
            new_page = PAGE_IMPORT_PROJECT

        if save:
            abstract = form.abstract.data
            valid, msg = is_valid_xml_fragment(abstract, names.ABSTRACT)
            if not valid:
                flash(invalid_xml_error_message(msg, False, names.ABSTRACT), 'error')
                return render_get_project_page(eml_node, form, filename, doing_related_project, project_node_id)

            funding = form.funding.data
            valid, msg = is_valid_xml_fragment(funding, names.FUNDING)
            if not valid:
                flash(invalid_xml_error_message(msg, False, names.FUNDING), 'error')
                return render_get_project_page(eml_node, form, filename, doing_related_project, project_node_id)

            title = form.title.data

            if not doing_related_project:
                create_project(dataset_node, title, abstract, funding)
            else:
                related_project_node = create_related_project(dataset_node, title, abstract, funding, project_node_id)
                project_node_id = related_project_node.id
            save_both_formats(filename=filename, eml_node=eml_node)

        new_page = handle_hidden_buttons(new_page)
        # We need to distinguish the case where the user has clicked "Project" button in Contents menu. In this case,
        # we need to redirect to the project page, not the related project page. We can't let the presence of a project
        # node ID fool us.
        if BTN_HIDDEN_PROJECT in request.form:
            doing_related_project = False

        if not doing_related_project:
            return redirect(url_for(new_page, filename=filename))
        else:
            return redirect(url_for(new_page, filename=filename, node_id='None', project_node_id=project_node_id))

    # Process GET
    if project_node_id != '1':
        if doing_related_project:
            related_project_node = Node.get_node_instance(project_node_id)
            populate_project_form(form, related_project_node)
        elif dataset_node:
            project_node = dataset_node.find_child(names.PROJECT)
            populate_project_form(form, project_node)

    init_form_md5(form)

    # Get the tooltip for the status badge
    init_evaluation(eml_node, filename)
    if project_node_id is None:
        project_node = dataset_node.find_child(names.PROJECT)
        if project_node:
            project_node_id = project_node.id
        else:
            project_node_id = None
    tooltip = format_tooltip(project_node, section='project')

    return render_get_project_page(eml_node, form, filename, doing_related_project, project_node_id, tooltip)


def render_get_project_page(eml_node, form, filename, doing_related_project, project_node_id, tooltip):
    set_current_page('project')
    if not doing_related_project:
        help = [get_help('project'), get_help('project_title'), get_help('project_funding')]
        page_title = 'Project'
    else:
        help = [get_help('related_project'), get_help('project_title'), get_help('project_funding')]
        page_title = 'Related Project'

    return render_template('project.html',
                           title=page_title,
                           filename=filename,
                           model_has_complex_texttypes=model_has_complex_texttypes(eml_node),
                           form=form,
                           help=help,
                           project_node_id=project_node_id,
                           tooltip=tooltip)


def populate_project_form(form: ProjectForm, project_node: Node):
    title = ''
    abstract = ''

    if project_node:
        title_node = project_node.find_child(names.TITLE)
        if title_node:
            title = title_node.content

        abstract_node = project_node.find_child(names.ABSTRACT)
        # post_process_texttype_node(abstract_node)

        funding_node = project_node.find_child(names.FUNDING)
        # post_process_texttype_node(funding_node)

        form.title.data = title
        form.abstract.data = display_texttype_node(abstract_node)
        form.funding.data = display_texttype_node(funding_node)
    init_form_md5(form)


@proj_bp.route('/project_personnel_select/<filename>', methods=['GET', 'POST'])
@proj_bp.route('/project_personnel_select/<filename>/<node_id>', methods=['GET', 'POST'])
@proj_bp.route('/project_personnel_select/<filename>/<node_id>/<project_node_id>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def project_personnel_select(filename=None, node_id=None, project_node_id=None):
    form = ResponsiblePartySelectForm(filename=filename)

    eml_node = load_eml(filename)

    # If the request has a project_node_id and no node_id, url_for puts the project_node_id in
    #  a query string
    if request.args.get('node_id'):
        node_id = request.args.get('node_id')
    if request.args.get('project_node_id'):
        project_node_id = request.args.get('project_node_id')

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        # Figure out the import target
        import_target = 'Project Personnel'
        project_node = Node.get_node_instance(project_node_id)
        if project_node:
            if project_node.parent.name == names.DATASET:
                # This is the primary project
                import_target = 'Project Personnel'
            elif project_node.parent.name == names.PROJECT:
                # This is a related project
                title_node = project_node.find_child(names.TITLE)
                if title_node:
                    import_target = 'Related Project Personnel for ' + title_node.content
        url = select_post(filename, form, form_dict,
                          'POST', PAGE_PROJECT_PERSONNEL_SELECT, PAGE_PROJECT,
                          PAGE_PROJECT, PAGE_PROJECT_PERSONNEL, project_node_id=project_node_id,
                          import_page=PAGE_IMPORT_PARTIES, import_target=import_target)
        return redirect(url)

    # Process GET
    help = [get_help('project_personnel')]
    return rp_select_get(filename=filename, form=form, rp_name='personnel',
                         rp_singular=non_breaking('Project Personnel'), rp_plural=non_breaking('Project Personnel'),
                         node_id=node_id, project_node_id=project_node_id, help=help)


@proj_bp.route('/funding_award_select/<filename>', methods=['GET', 'POST'])
@proj_bp.route('/funding_award_select/<filename>/<project_node_id>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def funding_award_select(filename=None, project_node_id=None):
    form = AwardSelectForm(filename=filename)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        node_id = None

        new_page = PAGE_FUNDING_AWARD_SELECT
        if form_dict:
            for key in form_dict:
                val = form_dict[key][0]  # value is the first list element
                if val == BTN_SAVE_AND_CONTINUE:
                    new_page = PAGE_PROJECT
                elif val[0:4] == 'Back':
                    new_page = PAGE_PROJECT
                elif val == BTN_EDIT:
                    new_page = PAGE_FUNDING_AWARD
                    node_id = key
                elif val == BTN_REMOVE:
                    new_page = PAGE_FUNDING_AWARD_SELECT
                    node_id = key
                    eml_node = load_eml(filename=filename)
                    node = Node.get_node_instance(node_id)
                    remove_child(node)
                    save_both_formats(filename=filename, eml_node=eml_node)
                elif val == UP_ARROW:
                    new_page = PAGE_FUNDING_AWARD_SELECT
                    node_id = key
                    process_up_button(filename, node_id)
                elif val == DOWN_ARROW:
                    new_page = PAGE_FUNDING_AWARD_SELECT
                    node_id = key
                    process_down_button(filename, node_id)
                elif val[0:3] == 'Add':
                    new_page = PAGE_FUNDING_AWARD
                    node_id = '1'
                elif val[0:6] == BTN_IMPORT:
                    new_page = PAGE_IMPORT_FUNDING_AWARDS
                    if node_id is None:
                        node_id = '1'

        if form.validate_on_submit():
            if node_id and project_node_id:
                url = url_for(new_page,
                              filename=filename,
                              node_id=node_id,
                              project_node_id=project_node_id)
            elif project_node_id:
                url = url_for(new_page,
                              filename=filename,
                              project_node_id=project_node_id)
            else:
                url = url_for(new_page,
                              filename=filename,
                              node_id=node_id)
            return redirect(url)

    # Process GET
    return funding_award_select_get(filename=filename, form=form, project_node_id=project_node_id)


def funding_award_select_get(filename=None, form=None, project_node_id=None):
    # Process GET
    title = 'Funding Awards'
    # entity_name = ''
    eml_node = load_eml(filename=filename)

    funding_award_list = list_funding_awards(eml_node, project_node_id)
    set_current_page('project')
    related_project = project_node_id is not None
    help = [get_help('awards')]
    return render_template('award_select.html', title=title,
                           filename=filename,
                           award_list=funding_award_list,
                           form=form, help=help, related_project=related_project)


def get_award_title(award_number):
    """
    Fetch the title of an NSF award given its award number.

    Args:
        award_number (str): The NSF award number

    Returns:
        str: The title of the award

    Raises:
        requests.RequestException: If the API request fails
        KeyError: If the response doesn't contain the expected data structure
    """
    award_number = award_number.strip()
    if not award_number or not award_number.isdigit():
        raise ValueError(f'Not a valid award number: "{award_number}"')

    url = f"http://api.nsf.gov/services/v1/awards/{award_number}.json"

    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes

        data = response.json()
        if not data["response"]["award"]:
            raise ValueError(f'No award data found for award number "{award_number}"')
        title = data["response"]["award"][0]["title"]
        return title

    except requests.RequestException as e:
        raise requests.RequestException(f"Failed to fetch award data: {e}")
    except (KeyError, IndexError) as e:
        raise KeyError(f"Failed to extract title from response: {e}")


@proj_bp.route('/funding_award/<filename>/<node_id>', methods=['GET', 'POST'])
@proj_bp.route('/funding_award/<filename>/<node_id>/<project_node_id>', methods=['GET', 'POST'])
@login_required
def funding_award(filename=None, node_id=None, project_node_id=None):
    form = AwardForm(filename=filename)

    eml_node = load_eml(filename=filename)
    if not project_node_id:
        project_node = eml_node.find_single_node_by_path([
            names.DATASET,
            names.PROJECT
        ])
        if not project_node:
            dataset_node = eml_node.find_child(names.DATASET)
            project_node = Node(names.PROJECT, parent=dataset_node)
            dataset_node.add_child(project_node)
    else:
        project_node = Node.get_node_instance(project_node_id)

    submit_type = None

    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)

        if request.method == 'POST' and BTN_CANCEL in request.form:
            url = url_for(PAGE_FUNDING_AWARD_SELECT, filename=filename, project_node_id=project_node_id)
            return redirect(url)

        # if request.method == 'POST' and form.validate_on_submit():
        if request.method == 'POST':
            next_page = handle_hidden_buttons(PAGE_FUNDING_AWARD_SELECT)

        if 'Lookup' in form_dict:
            submit_type = 'Lookup'
        elif 'OK' in form_dict or is_hidden_button():
            submit_type = 'Save Changes'

        if submit_type == 'Save Changes':
            funder_name = form.funder_name.data
            award_title = form.award_title.data
            funder_identifier = form.funder_identifier.data
            award_number = form.award_number.data
            award_url = form.award_url.data

            award_node = Node(names.AWARD, parent=project_node)

            create_funding_award(award_node, funder_name, award_title, funder_identifier, award_number, award_url)

            if node_id and len(node_id) != 1:
                old_award_node = Node.get_node_instance(node_id)

                if old_award_node:
                    award_parent_node = old_award_node.parent
                    award_parent_node.replace_child(old_award_node, award_node)
                else:
                    msg = f"No funding award node found in the node store with node id {node_id}"
                    dump_node_store(eml_node, 'funding_award')
                    raise NodeWithGivenIdNotFound(msg)
            else:
                add_child(project_node, award_node)

            save_both_formats(filename=filename, eml_node=eml_node)

            url = select_post(filename, form, form_dict,
                              'POST', PAGE_FUNDING_AWARD_SELECT, PAGE_PROJECT,
                              next_page, PAGE_FUNDING_AWARD,
                              project_node_id=project_node_id, import_page=PAGE_IMPORT_PARTIES)
            return redirect(url)

        if submit_type == 'Lookup':
            award_number = form.award_number.data
            try:
                award_title = get_award_title(award_number)
                form.award_title.data = award_title
                form.award_url.data = f"https://www.nsf.gov/awardsearch/showAward?AWD_ID={award_number}"
                form.funder_name.data = 'National Science Foundation (NSF)'
                form.funder_identifier.data = 'https://ror.org/021nxhr62'

            except requests.RequestException as e:
                flash(e, 'error')
            except ValueError as e:
                flash(e, 'error')
            except KeyError as e:
                flash(f"Failed to extract title from response: {e}", 'error')

    # Process GET
    if not project_node_id:
        title = 'Project Funding Award'
        related_project = False
    else:
        title = 'Related Project Funding Award'
        related_project = True

    if node_id != '1' and submit_type != 'Lookup':
        award_nodes = project_node.find_all_children(names.AWARD)
        if award_nodes:
            for award_node in award_nodes:
                if node_id == award_node.id:
                    populate_award_form(form, award_node)
                    break

    init_form_md5(form)

    if form.award_title.data and form.funder_name.data:
        lookup_confirm = 'If the lookup succeeds, the Funder Name and Award Title fields will be overwritten. OK to continue?'
    elif form.award_title.data:
        lookup_confirm = 'If the lookup succeeds, the Award Title field will be overwritten. OK to continue?'
    else:
        lookup_confirm = None
    set_current_page('project')
    help = [get_help('award'),
            get_help('funder_name'),
            get_help('award_title'),
            get_help('award_number'),
            get_help('award_lookup'),
            get_help('funder_identifiers'),
            get_help('award_url')]
    return render_template('award.html',
                           title=title,
                           form=form,
                           help=help,
                           related_project=related_project,
                           lookup_confirm=lookup_confirm)


def populate_award_form(form: AwardForm, award_node: Node):
    funder_name = ''
    award_title = ''
    funder_identifier = ''  # FIX ME - should be list
    award_number = ''
    award_url = ''

    if award_node:
        funder_name_node = award_node.find_child(names.FUNDERNAME)
        if funder_name_node and funder_name_node.content:
            funder_name = funder_name_node.content

        award_title_node = award_node.find_child(names.TITLE)
        if award_title_node and award_title_node.content:
            award_title = award_title_node.content

        funder_identifiers = []
        funder_identifier_nodes = award_node.find_all_children(names.FUNDERIDENTIFIER)
        for funder_identifier_node in funder_identifier_nodes:
            if funder_identifier_node.content:
                funder_identifiers.append(funder_identifier_node.content)
        funder_identifier = ','.join(funder_identifiers)

        award_number_node = award_node.find_child(names.AWARDNUMBER)
        if award_number_node and award_number_node.content:
            award_number = award_number_node.content

        award_url_node = award_node.find_child(names.AWARDURL)
        if award_url_node and award_url_node.content:
            award_url = award_url_node.content

    form.funder_name.data = funder_name
    form.award_title.data = award_title
    form.funder_identifier.data = funder_identifier
    form.award_number.data = award_number
    form.award_url.data = award_url


@proj_bp.route('/related_project_select/<filename>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def related_project_select(filename=None):
    form = RelatedProjectSelectForm(filename=filename)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = related_project_select_post(filename, form, form_dict,
                                  'POST', PAGE_RELATED_PROJECT_SELECT, PAGE_METHOD_STEP_SELECT,
                                  PAGE_OTHER_ENTITY_SELECT, PAGE_PROJECT)
        return redirect(url)

    # Process GET
    return related_project_select_get(filename=filename, form=form)


def related_project_select_get(filename=None, form=None):
    # Process GET
    project_list = []
    title = 'Related Projects'
    eml_node = load_eml(filename=filename)

    if eml_node:
        project_list = list_related_projects(eml_node)

    set_current_page('project')
    help = [get_help('related_project')]
    return render_template('related_project_select.html', title=title,
                           filename=filename,
                           project_list=project_list,
                           form=form, help=help)


def remove_related_project(filename:str=None, node_id:str=None):
    eml_node = load_eml(filename=filename)
    related_project_node = Node.get_node_instance(node_id)
    if related_project_node:
        parent_node = related_project_node.parent
        if parent_node:
            parent_node.remove_child(related_project_node)
            try:
                if eml_node:
                    save_both_formats(filename=filename, eml_node=eml_node)
            except Exception as e:
                log_error(e)



def related_project_select_post(filename=None, form=None, form_dict=None,
                        method=None, this_page=None, back_page=None,
                        next_page=None, edit_page=None):
    project_node_id = None
    new_page = None
    if form_dict:
        for key in form_dict:
            val = form_dict[key][0]  # value is the first list element
            if val == BTN_BACK:
                new_page = back_page
            elif val == BTN_NEXT or val == BTN_SAVE_AND_CONTINUE:
                new_page = next_page
            elif val == BTN_EDIT:
                new_page = edit_page
                project_node_id = key
            elif val == BTN_REMOVE:
                new_page = this_page
                project_node_id = key
                remove_related_project(filename, project_node_id)
            elif val == UP_ARROW:
                new_page = this_page
                node_id = key
                process_up_button(filename, node_id)
            elif val == DOWN_ARROW:
                new_page = this_page
                node_id = key
                process_down_button(filename, node_id)
            elif val[0:3] == BTN_ADD:
                new_page = edit_page
                project_node_id = '1'
            elif val[0:6] == BTN_IMPORT:
                new_page = PAGE_IMPORT_RELATED_PROJECTS
                if project_node_id is None:
                    project_node_id = '1'
            elif val[0:4] == BTN_BACK:
                new_page = edit_page
                project_node_id = None

    if form.validate_on_submit():
        if new_page == edit_page:
            return url_for(new_page,
                           filename=filename,
                           project_node_id=project_node_id,
                           title='Related Project')
        else:
            return url_for(new_page,
                           filename=filename)


def list_related_projects(eml_node):
    related_projects = []
    project_node = eml_node.find_single_node_by_path([names.DATASET, names.PROJECT])
    if project_node:
        related_projects_nodes = project_node.find_all_children(names.RELATED_PROJECT)
        if related_projects_nodes:
            RP_Entry = collections.namedtuple(
                'RP_Entry', ["id", "label", "upval", "downval", "tooltip"],
                rename=False)

            current_document = current_user.get_filename()
            init_evaluation(eml_node, current_document)

            for i, rp_node in enumerate(related_projects_nodes):
                title_node = rp_node.find_child(names.TITLE)
                if not title_node:
                    continue
                label = title_node.content
                id = rp_node.id
                upval = get_upval(i)
                downval = get_downval(i + 1, len(related_projects_nodes))
                tooltip = format_tooltip(rp_node)
                rp_entry = RP_Entry(id=id, label=label, upval=upval, downval=downval, tooltip=tooltip)
                related_projects.append(rp_entry)
    return related_projects
