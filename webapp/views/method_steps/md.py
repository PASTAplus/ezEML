from flask import (
    Blueprint, flash, render_template, redirect, request, url_for
)

from webapp.home.forms import (
    form_md5, is_dirty_form
)

from webapp.home.views import process_up_button, process_down_button

from webapp.home.metapype_client import (
    load_eml, save_both_formats,
    add_child, remove_child,
    UP_ARROW, DOWN_ARROW,
)

from webapp.views.method_steps.forms import (
    MethodStepForm, MethodStepSelectForm
)

from webapp.buttons import *
from webapp.pages import *

from metapype.eml import names
from metapype.model.node import Node
from webapp.home.metapype_client import (
    create_method_step,
    list_method_steps
)


md_bp = Blueprint('md', __name__, template_folder='templates')


@md_bp.route('/method_step_select/<packageid>', methods=['GET', 'POST'])
def method_step_select(packageid=None):
    form = MethodStepSelectForm(packageid=packageid)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        node_id = ''
        new_page = ''
        url = ''
        this_page = PAGE_METHOD_STEP_SELECT
        edit_page = PAGE_METHOD_STEP
        back_page = PAGE_PUBLICATION_PLACE
        next_page = PAGE_PROJECT

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
                elif val == UP_ARROW:
                    new_page = this_page
                    node_id = key
                    process_up_button(packageid, node_id)
                elif val == DOWN_ARROW:
                    new_page = this_page
                    node_id = key
                    process_down_button(packageid, node_id)
                elif val[0:3] == 'Add':
                    new_page = edit_page
                    node_id = '1'
                elif val == '[  ]':
                    new_page = this_page
                    node_id = key

        if form.validate_on_submit():
            if new_page == edit_page:
                url = url_for(new_page,
                              packageid=packageid,
                              node_id=node_id)
            elif new_page == this_page:
                url = url_for(new_page,
                              packageid=packageid,
                              node_id=node_id)
            elif new_page == back_page or new_page == next_page:
                url = url_for(new_page,
                              packageid=packageid)
            return redirect(url)

    # Process GET
    method_step_list = []
    title = 'Method Steps'
    eml_node = load_eml(packageid=packageid)

    if eml_node:
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            method_step_list = list_method_steps(dataset_node)

    return render_template('method_step_select.html', title=title,
                           packageid=packageid,
                           method_step_list=method_step_list,
                           form=form)


# node_id is the id of the methodStep node being edited. If the value is
# '1', it means we are adding a new methodStep node, otherwise we are
# editing an existing one.
#
@md_bp.route('/method_step/<packageid>/<node_id>', methods=['GET', 'POST'])
def method_step(packageid=None, node_id=None):
    eml_node = load_eml(packageid=packageid)
    dataset_node = eml_node.find_child(names.DATASET)

    if dataset_node:
        methods_node = dataset_node.find_child(names.METHODS)
    else:
        dataset_node = Node(names.DATASET, parent=eml_node)
        add_child(eml_node, dataset_node)

    if not methods_node:
        methods_node = Node(names.METHODS, parent=dataset_node)
        add_child(dataset_node, methods_node)

    form = MethodStepForm(packageid=packageid, node_id=node_id)

    # Process POST
    if request.method == 'POST' and BTN_CANCEL in request.form:
            url = url_for(PAGE_METHOD_STEP_SELECT, packageid=packageid)
            return redirect(url)

    if request.method == 'POST' and form.validate_on_submit():
        next_page = PAGE_METHOD_STEP_SELECT  # Save or Back sends us back to the list of method steps

        submit_type = None
        if is_dirty_form(form):
            submit_type = 'Save Changes'
        flash(f'submit_type: {submit_type}')

        if submit_type == 'Save Changes':
            description = form.description.data
            instrumentation = form.instrumentation.data
            method_step_node = Node(names.METHODSTEP, parent=methods_node)
            create_method_step(method_step_node, description, instrumentation)

            if node_id and len(node_id) != 1:
                old_method_step_node = Node.get_node_instance(node_id)

                if old_method_step_node:
                    method_step_parent_node = old_method_step_node.parent
                    method_step_parent_node.replace_child(old_method_step_node,
                                                          method_step_node)
                else:
                    msg = f"No methodStep node found in the node store with node id {node_id}"
                    raise Exception(msg)
            else:
                add_child(methods_node, method_step_node)

            save_both_formats(packageid=packageid, eml_node=eml_node)

        url = url_for(next_page, packageid=packageid)
        return redirect(url)

    # Process GET
    if node_id == '1':
        form.init_md5()
    else:
        method_step_nodes = methods_node.find_all_children(names.METHODSTEP)
        if method_step_nodes:
            for ms_node in method_step_nodes:
                if node_id == ms_node.id:
                    populate_method_step_form(form, ms_node)
                    break

    return render_template('method_step.html', title='Method Step', form=form, packageid=packageid)


def populate_method_step_form(form: MethodStepForm, ms_node: Node):
    description = ''
    instrumentation = ''

    if ms_node:
        description_node = ms_node.find_child(names.DESCRIPTION)
        if description_node:
            section_node = description_node.find_child(names.SECTION)
            if section_node:
                description = section_node.content
            else:
                para_node = description_node.find_child(names.PARA)
                if para_node:
                    description = para_node.content

        instrumentation_node = ms_node.find_child(names.INSTRUMENTATION)
        if instrumentation_node:
            instrumentation = instrumentation_node.content

        form.description.data = description
        form.instrumentation.data = instrumentation
    form.md5.data = form_md5(form)

