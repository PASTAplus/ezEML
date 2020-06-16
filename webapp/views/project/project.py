from flask import (
    Blueprint, flash, render_template, redirect, request, url_for
)

from webapp.home.metapype_client import (
    add_child, create_project,
    load_eml, save_both_formats,
    add_paragraph_tags, remove_paragraph_tags,
    list_funding_awards, create_funding_award,
    remove_child, UP_ARROW, DOWN_ARROW
)

from webapp.home.forms import is_dirty_form, form_md5
from webapp.home.views import non_breaking, process_up_button, process_down_button

from webapp.views.project.forms import (
    ProjectForm, AwardSelectForm, AwardForm
)

from webapp.views.responsible_parties.rp import rp_select_get
from webapp.views.responsible_parties.forms import ResponsiblePartySelectForm

from webapp.buttons import *
from webapp.pages import *
from webapp.home.views import select_post, set_current_page, get_help
from metapype.eml import names
from metapype.model.node import Node


proj_bp = Blueprint('proj', __name__, template_folder='templates')


@proj_bp.route('/project/<packageid>', methods=['GET', 'POST'])
def project(packageid=None):
    form = ProjectForm(packageid=packageid)
    eml_node = load_eml(packageid=packageid)
    if eml_node:
        dataset_node = eml_node.find_child(names.DATASET)
        if not dataset_node:
            dataset_node = Node(names.DATASET, parent=eml_node)
            add_child(eml_node, dataset_node)

    # Process POST
    if request.method == 'POST' and form.validate_on_submit():
        save = False
        if is_dirty_form(form):
            save = True
        # flash(f'save: {save}')

        if 'Back' in request.form:
            new_page = PAGE_METHOD_STEP_SELECT
        elif 'Next' in request.form:
            new_page = PAGE_DATA_TABLE_SELECT
        elif 'Edit Project Personnel' in request.form:
            new_page = PAGE_PROJECT_PERSONNEL_SELECT
        elif 'Edit Funding Awards' in request.form:
            new_page = PAGE_FUNDING_AWARD_SELECT
        elif 'Hidden_Save' in request.form:
            new_page = PAGE_PROJECT
        elif 'Hidden_Download' in request.form:
            new_page = PAGE_DOWNLOAD

        if save:
            title = form.title.data
            abstract = add_paragraph_tags(form.abstract.data)
            create_project(dataset_node, title, abstract)
            save_both_formats(packageid=packageid, eml_node=eml_node)

        return redirect(url_for(new_page, packageid=packageid))

    # Process GET
    if dataset_node:
        project_node = dataset_node.find_child(names.PROJECT)
        populate_project_form(form, project_node)

    set_current_page('project')
    help = [get_help('project'), get_help('project_title')]
    return render_template('project.html',
                           title='Project',
                           packageid=packageid,
                           form=form,
                           help=help)


def populate_project_form(form: ProjectForm, project_node: Node):
    title = ''
    abstract = ''

    if project_node:
        title_node = project_node.find_child(names.TITLE)
        if title_node:
            title = title_node.content

        abstract_node = project_node.find_child(names.ABSTRACT)
        if abstract_node:
            abstract = abstract_node.content
            if not abstract:
                para_node = abstract_node.find_child(names.PARA)
                if para_node:
                    abstract = para_node.content
                else:
                    section_node = abstract_node.find_child(names.SECTION)
                    if section_node:
                        abstract = section_node.content
            abstract = abstract

        form.title.data = title
        form.abstract.data = remove_paragraph_tags(abstract)
    form.md5.data = form_md5(form)


@proj_bp.route('/project_personnel_select/<packageid>', methods=['GET', 'POST'])
def project_personnel_select(packageid=None):
    form = ResponsiblePartySelectForm(packageid=packageid)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = select_post(packageid, form, form_dict,
                          'POST', PAGE_PROJECT_PERSONNEL_SELECT, PAGE_PROJECT,
                          PAGE_PROJECT, PAGE_PROJECT_PERSONNEL)
        return redirect(url)

    # Process GET
    return rp_select_get(packageid=packageid, form=form, rp_name='personnel',
                         rp_singular=non_breaking('Project Personnel'), rp_plural=non_breaking('Project Personnel'))


@proj_bp.route('/funding_award_select/<packageid>', methods=['GET', 'POST'])
def funding_award_select(packageid=None):
    form = AwardSelectForm(packageid=packageid)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)

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
                    eml_node = load_eml(packageid=packageid)
                    remove_child(node_id=node_id)
                    save_both_formats(packageid=packageid, eml_node=eml_node)
                elif val == BTN_HIDDEN_SAVE:
                    new_page = PAGE_FUNDING_AWARD_SELECT
                elif val == BTN_HIDDEN_DOWNLOAD:
                    new_page = PAGE_DOWNLOAD
                elif val == UP_ARROW:
                    new_page = PAGE_FUNDING_AWARD_SELECT
                    node_id = key
                    process_up_button(packageid, node_id)
                elif val == DOWN_ARROW:
                    new_page = PAGE_FUNDING_AWARD_SELECT
                    node_id = key
                    process_down_button(packageid, node_id)
                elif val[0:3] == 'Add':
                    new_page = PAGE_FUNDING_AWARD
                    node_id = '1'

        if form.validate_on_submit():
            if new_page == PAGE_FUNDING_AWARD:
                url = url_for(new_page,
                              packageid=packageid,
                              node_id=node_id)
            # elif new_page == PAGE_FUNDING_AWARD_SELECT:
            #     url = url_for(new_page,
            #                   packageid=packageid)
            else:
                url = url_for(new_page,
                              packageid=packageid)
            return redirect(url)

    # Process GET
    return funding_award_select_get(packageid=packageid, form=form)


def funding_award_select_get(packageid=None, form=None):
    # Process GET
    title = 'Funding Awards'
    # entity_name = ''
    eml_node = load_eml(packageid=packageid)

    funding_award_list = list_funding_awards(eml_node)
    set_current_page('project')
    help = [get_help('awards')]
    return render_template('award_select.html', title=title,
                           packageid=packageid,
                           award_list=funding_award_list,
                           form=form, help=help)


@proj_bp.route('/funding_award/<packageid>/<node_id>', methods=['GET', 'POST'])
def funding_award(packageid=None, node_id=None):
    form = AwardForm(packageid=packageid)

    eml_node = load_eml(packageid=packageid)
    project_node = eml_node.find_single_node_by_path([
        names.DATASET,
        names.PROJECT
    ])
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)

        if request.method == 'POST' and BTN_CANCEL in request.form:
            url = url_for(PAGE_FUNDING_AWARD_SELECT, packageid=packageid)
            return redirect(url)

        if request.method == 'POST' and form.validate_on_submit():
            next_page = PAGE_FUNDING_AWARD_SELECT  # Save or Back sends us back to the list of keywords

        submit_type = None
        if is_dirty_form(form):
            submit_type = 'Save Changes'
        # flash(f'submit_type: {submit_type}')

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
                    raise Exception(msg)
            else:
                add_child(project_node, award_node)

            save_both_formats(packageid=packageid, eml_node=eml_node)

        url = select_post(packageid, form, form_dict,
                          'POST', PAGE_FUNDING_AWARD_SELECT, PAGE_PROJECT,
                          PAGE_PROJECT, PAGE_FUNDING_AWARD)
        return redirect(url)

    # Process GET
    title = 'Funding Award'

    if node_id == '1':
        form.init_md5()
    else:
        award_nodes = project_node.find_all_children(names.AWARD)
        if award_nodes:
            for award_node in award_nodes:
                if node_id == award_node.id:
                    populate_award_form(form, award_node)
                    break

    set_current_page('project')
    help = [get_help('award'),
            get_help('funder_name'),
            get_help('award_title'),
            get_help('funder_identifiers'),
            get_help('award_number'),
            get_help('award_url')]
    return render_template('award.html',
                           title=title,
                           form=form,
                           help=help)


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
