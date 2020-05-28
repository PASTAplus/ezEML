from flask import (
    Blueprint, flash, render_template, redirect, request, url_for
)

from webapp.home.metapype_client import (
    add_child, create_project,
    load_eml, save_both_formats,
    add_paragraph_tags, remove_paragraph_tags
)

from webapp.home.forms import is_dirty_form, form_md5
from webapp.home.views import non_breaking

from webapp.views.project.forms import (
    ProjectForm
)

from webapp.views.responsible_parties.rp import rp_select_get
from webapp.views.responsible_parties.forms import ResponsiblePartySelectForm

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
        elif 'Hidden_Save' in request.form:
            new_page = PAGE_PROJECT
        elif 'Hidden_Download' in request.form:
            new_page = PAGE_DOWNLOAD

        if save:
            title = form.title.data
            abstract = add_paragraph_tags(form.abstract.data)
            funding = form.funding.data
            create_project(dataset_node, title, abstract, funding)
            save_both_formats(packageid=packageid, eml_node=eml_node)

        return redirect(url_for(new_page, packageid=packageid))

    # Process GET
    if dataset_node:
        project_node = dataset_node.find_child(names.PROJECT)
        if project_node:
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
    funding = ''

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

        funding_node = project_node.find_child(names.FUNDING)
        if funding_node:
            funding = funding_node.content
            if not funding:
                para_node = funding_node.find_child(names.PARA)
                if para_node:
                    funding = para_node.content
                else:
                    section_node = funding_node.find_child(names.SECTION)
                    if section_node:
                        funding = section_node.content

        form.title.data = title
        form.abstract.data = remove_paragraph_tags(abstract)
        form.funding.data = funding
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

