from flask import (
    Blueprint, flash, render_template, redirect, request, url_for
)

from webapp.home.metapype_client import (
    add_child, create_maintenance,
    load_eml, save_both_formats,
    add_paragraph_tags, remove_paragraph_tags,
    handle_hidden_buttons,
    post_process_text_type_node, display_text_type_node
)

from webapp.home.forms import is_dirty_form, form_md5
from webapp.home.views import non_breaking, process_up_button, process_down_button

from webapp.views.maintenance.forms import (
    MaintenanceForm
)

from webapp.buttons import *
from webapp.pages import *
from webapp.home.views import select_post, set_current_page, get_help
from metapype.eml import names
from metapype.model.node import Node


maint_bp = Blueprint('maint', __name__, template_folder='templates')


@maint_bp.route('/maintenance/<filename>', methods=['GET', 'POST'])
def maintenance(filename=None):
    form = MaintenanceForm(filename=filename)
    eml_node = load_eml(filename=filename)
    if eml_node:
        dataset_node = eml_node.find_child(names.DATASET)
        if not dataset_node:
            dataset_node = Node(names.DATASET, parent=eml_node)
            add_child(eml_node, dataset_node)

    # Process POST
    if request.method == 'POST' and BTN_CANCEL in request.form:
        url = url_for(PAGE_MAINTENANCE, filename=filename)
        return redirect(url)

    if request.method == 'POST' and form.validate_on_submit():
        save = False
        if is_dirty_form(form):
            save = True
        # flash(f'save: {save}')

        if save:
            update_frequency = form.update_frequency.data
            create_maintenance(dataset_node, form.description.data, update_frequency)
            save_both_formats(filename=filename, eml_node=eml_node)

        form_value = request.form
        form_dict = form_value.to_dict(flat=False)

        new_page = PAGE_MAINTENANCE
        if form_dict:
            for key in form_dict:
                val = form_dict[key][0]  # value is the first list element
                if val == BTN_SAVE_AND_CONTINUE:
                    new_page = PAGE_PUBLISHER
                else:
                    new_page = handle_hidden_buttons(new_page, PAGE_MAINTENANCE)

        return redirect(url_for(new_page, filename=filename))


    # Process GET
    if dataset_node:
        maintenance_node = dataset_node.find_child(names.MAINTENANCE)
        if maintenance_node:
            populate_maintenance_form(form, maintenance_node)

    set_current_page('maintenance')
    help = [get_help('maintenance'), get_help('maintenance_description'), get_help('maintenance_freq')]
    return render_template('maintenance.html',
                           title='Maintenance',
                           filename=filename,
                           form=form,
                           help=help)


def populate_maintenance_form(form: MaintenanceForm, maintenance_node: Node):
    description = ''
    update_frequency = ''

    if maintenance_node:
        description_node = maintenance_node.find_child(names.DESCRIPTION)
        if description_node:
            description = display_text_type_node(description_node)

        update_frequency_node = maintenance_node.find_child(names.MAINTENANCEUPDATEFREQUENCY)
        if update_frequency_node:
            update_frequency = update_frequency_node.content

        form.description.data = description
        form.update_frequency.data = update_frequency
    form.md5.data = form_md5(form)

