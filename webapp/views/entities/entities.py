from flask import (
    Blueprint, flash, render_template, redirect, request, url_for, Flask, current_app
)
from flask_login import (
    current_user, login_required
)

import webapp.home.utils.node_utils
from webapp.home.views import (
    process_up_button, process_down_button, set_current_page,
    compare_begin_end_dates
)

from webapp.views.access.forms import (
    AccessForm, AccessSelectForm
)

from webapp.views.entities.forms import (
    OtherEntitySelectForm, OtherEntityForm,
)

from webapp.views.coverage.forms import (
    GeographicCoverageForm, GeographicCoverageSelectForm,
    TaxonomicCoverageForm, TaxonomicCoverageSelectForm,
    TemporalCoverageForm, TemporalCoverageSelectForm
)

from webapp.views.method_steps.forms import (
    MethodStepForm, MethodStepSelectForm
)

from webapp.views.coverage.coverage import (
    populate_geographic_coverage_form,
    populate_temporal_coverage_form
)

from webapp.views.access.access import (
    populate_access_rule_form
)

from webapp.views.method_steps.md import (
    populate_method_step_form
)

from webapp.home.forms import (
    init_form_md5, is_dirty_form
)

from webapp.views.data_tables.dt import entity_name_from_data_table
from webapp.home.utils.node_utils import remove_child, add_child
from webapp.home.utils.hidden_buttons import (
    is_hidden_button, handle_hidden_buttons, check_val_for_hidden_buttons, non_saving_hidden_buttons_decorator
)
from webapp.home.utils.load_and_save import load_eml, save_both_formats
from webapp.home.utils.lists import list_other_entities, list_geographic_coverages, list_temporal_coverages, \
    list_taxonomic_coverages, UP_ARROW, DOWN_ARROW, list_method_steps, list_access_rules
from webapp.home.utils.create_nodes import create_access, create_other_entity, create_geographic_coverage, \
    create_temporal_coverage, create_taxonomic_coverage, create_method_step, create_access_rule

from metapype.eml import names
from metapype.model.node import Node

from webapp.buttons import *
from webapp.pages import *

from webapp.home.views import select_post, non_breaking, get_help


ent_bp = Blueprint('ent', __name__, template_folder='templates')


@ent_bp.route('/other_entity_select/<filename>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def other_entity_select(filename=None):
    form = OtherEntitySelectForm(filename=filename)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = select_post(filename, form, form_dict,
                          'POST', PAGE_OTHER_ENTITY_SELECT, PAGE_PROJECT,
                          PAGE_DATA_PACKAGE_ID, PAGE_OTHER_ENTITY, reupload_page=PAGE_REUPLOAD_OTHER_ENTITY)
        return redirect(url)

    # Process GET
    eml_node = load_eml(filename=filename)
    oe_list = list_other_entities(eml_node)
    title = 'Other Entities'

    set_current_page('other_entity')
    help = [get_help('other_entities'), get_help('add_load_other_entities'), get_help('other_entity_reupload')]
    return render_template('other_entity_select.html', title=title,
                           oe_list=oe_list, form=form, help=help)


@ent_bp.route('/other_entity/<filename>/<node_id>', methods=['GET', 'POST'])
@login_required
def other_entity(filename=None, node_id=None):
    dt_node_id = node_id
    form = OtherEntityForm(filename=filename)

    if request.method == 'POST' and BTN_CANCEL in request.form:
            url = url_for(PAGE_OTHER_ENTITY_SELECT, filename=filename, dt_node_id=dt_node_id)
            return redirect(url)

    # Process POST
    if request.method == 'POST' and form.validate_on_submit():
        next_page = PAGE_OTHER_ENTITY_SELECT

        # If we have a hidden button, we note that fact but we may need to save changes before going there.
        next_page = handle_hidden_buttons(next_page)

        auto_save = False  # if user clicked to edit, we need to save other entity first
        if 'Access' in request.form:
            next_page = PAGE_ENTITY_ACCESS_SELECT
        elif 'Methods' in request.form:
            next_page = PAGE_ENTITY_METHOD_STEP_SELECT
            auto_save = True
        elif 'Geographic' in request.form:
            next_page = PAGE_ENTITY_GEOGRAPHIC_COVERAGE_SELECT
            auto_save = True
        elif 'Temporal' in request.form:
            next_page = PAGE_ENTITY_TEMPORAL_COVERAGE_SELECT
            auto_save = True
        elif 'Taxonomic' in request.form:
            next_page = PAGE_ENTITY_TAXONOMIC_COVERAGE_SELECT
            auto_save = True

        eml_node = load_eml(filename=filename)

        submit_type = None

        # app = Flask(__name__)
        # with app.app_context():
        #     current_app.logger.info(f'other_entity is_dirty_form={is_dirty_form(form)} auto_save={auto_save}')

        if is_dirty_form(form) or auto_save:
            submit_type = 'Save Changes'
        # flash(f'submit_type: {submit_type}')

        if submit_type == 'Save Changes':
            dataset_node = eml_node.find_child(names.DATASET)
            if not dataset_node:
                dataset_node = Node(names.DATASET)

            entity_name = form.entity_name.data
            entity_type = form.entity_type.data
            entity_description = form.entity_description.data
            object_name = form.object_name.data
            format_name = form.format_name.data
            size = str(form.size.data) if form.size.data else ''
            md5_hash = form.md5_hash.data
            online_url = form.online_url.data

            dt_node = Node(names.OTHERENTITY, parent=dataset_node)

            if not entity_name:
                entity_name = ''

            create_other_entity(
                dt_node,
                entity_name,
                entity_type,
                entity_description,
                object_name,
                format_name,
                size,
                md5_hash,
                online_url)

            if dt_node_id and len(dt_node_id) != 1:
                old_dt_node = Node.get_node_instance(dt_node_id)
                if old_dt_node:

                    old_physical_node = old_dt_node.find_child(names.PHYSICAL)
                    if old_physical_node:
                        old_distribution_node = old_physical_node.find_child(names.DISTRIBUTION)
                        if old_distribution_node:
                            access_node = old_distribution_node.find_child(names.ACCESS)
                            if access_node:
                                physical_node = dt_node.find_child(names.PHYSICAL)
                                if physical_node:
                                    distribution_node = dt_node.find_child(names.DISTRIBUTION)
                                    if distribution_node:
                                        webapp.home.utils.node_utils.remove_child(access_node)
                                        add_child(distribution_node, access_node)

                    methods_node = old_dt_node.find_child(names.METHODS)
                    if methods_node:
                        webapp.home.utils.node_utils.remove_child(methods_node)
                        add_child(dt_node, methods_node)

                    coverage_node = old_dt_node.find_child(names.COVERAGE)
                    if coverage_node:
                        webapp.home.utils.node_utils.remove_child(coverage_node)
                        add_child(dt_node, coverage_node)

                    dataset_parent_node = old_dt_node.parent
                    dataset_parent_node.replace_child(old_dt_node, dt_node)
                    dt_node_id = dt_node.id
                else:
                    msg = f"No node found in the node store with node id {dt_node_id}"
                    raise Exception(msg)
            else:
                add_child(dataset_node, dt_node)
                dt_node_id = dt_node.id

            save_both_formats(filename=filename, eml_node=eml_node)

        if (next_page == PAGE_ENTITY_ACCESS_SELECT or
                next_page == PAGE_ENTITY_METHOD_STEP_SELECT or
                next_page == PAGE_ENTITY_GEOGRAPHIC_COVERAGE_SELECT or
                next_page == PAGE_ENTITY_TEMPORAL_COVERAGE_SELECT or
                next_page == PAGE_ENTITY_TAXONOMIC_COVERAGE_SELECT
        ):
            return redirect(url_for(next_page,
                                    filename=filename,
                                    dt_element_name=names.OTHERENTITY,
                                    dt_node_id=dt_node_id))
        else:
            return redirect(url_for(next_page,
                                    filename=filename,
                                    dt_node_id=dt_node_id))

    # Process GET
    if dt_node_id != '1':
        eml_node = load_eml(filename=filename)
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            dt_nodes = dataset_node.find_all_children(names.OTHERENTITY)
            if dt_nodes:
                for dt_node in dt_nodes:
                    if dt_node_id == dt_node.id:
                        populate_other_entity_form(form, dt_node)

    init_form_md5(form)

    set_current_page('other_entity')
    help = [get_help('other_entity')]
    return render_template('other_entity.html', title='Other Entity', form=form, help=help)


def populate_other_entity_form(form: OtherEntityForm, node: Node):
    entity_name_node = node.find_child(names.ENTITYNAME)
    if entity_name_node:
        form.entity_name.data = entity_name_node.content

    entity_type_node = node.find_child(names.ENTITYTYPE)
    if entity_type_node:
        form.entity_type.data = entity_type_node.content

    entity_description_node = node.find_child(names.ENTITYDESCRIPTION)
    if entity_description_node:
        form.entity_description.data = entity_description_node.content

    physical_node = node.find_child(names.PHYSICAL)
    if physical_node:

        object_name_node = physical_node.find_child(names.OBJECTNAME)
        if object_name_node:
            form.object_name.data = object_name_node.content

        size_node = physical_node.find_child(names.SIZE)
        if size_node:
            form.size.data = size_node.content

        md5_hash_node = physical_node.find_child(names.AUTHENTICATION)
        if md5_hash_node:
            form.md5_hash.data = md5_hash_node.content

        data_format_node = physical_node.find_child(names.DATAFORMAT)
        if data_format_node:

            externally_defined_format_node = data_format_node.find_child(names.EXTERNALLYDEFINEDFORMAT)
            if externally_defined_format_node:
                format_name_node = externally_defined_format_node.find_child(names.FORMATNAME)

                if format_name_node:
                    form.format_name.data = format_name_node.content

        distribution_node = physical_node.find_child(names.DISTRIBUTION)
        if distribution_node:

            online_node = distribution_node.find_child(names.ONLINE)
            if online_node:

                url_node = online_node.find_child(names.URL)
                if url_node:
                    form.online_url.data = url_node.content
    init_form_md5(form)


@ent_bp.route('/entity_access_select/<filename>/<dt_element_name>/<dt_node_id>',
            methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def entity_access_select(filename: str = None, dt_element_name: str = None, dt_node_id: str = None):
    form = AccessSelectForm(filename=filename)

    parent_page = PAGE_DATA_TABLE
    if dt_element_name == names.OTHERENTITY:
        parent_page = PAGE_OTHER_ENTITY

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = entity_access_select_post(filename, form, form_dict,
                                        'POST', PAGE_ENTITY_ACCESS_SELECT, parent_page,
                                        parent_page, PAGE_ENTITY_ACCESS,
                                        dt_element_name=dt_element_name,
                                        dt_node_id=dt_node_id)
        return redirect(url)

    # Process GET
    return entity_access_select_get(filename=filename, form=form, dt_node_id=dt_node_id)


def entity_access_select_get(filename=None, form=None, dt_node_id=None):
    # Process GET
    access_rules_list = []
    title = 'Access Rules'
    entity_name = ''
    load_eml(filename=filename)

    if dt_node_id != '1':
        data_table_node = Node.get_node_instance(dt_node_id)
        if data_table_node:
            entity_name = entity_name_from_data_table(data_table_node)
            physical_node = data_table_node.find_child(names.PHYSICAL)
            if physical_node:
                distribution_node = physical_node.find_child(names.DISTRIBUTION)
                if distribution_node:
                    access_rules_list = list_access_rules(distribution_node)

    init_form_md5(form)

    set_current_page('other_entity')
    return render_template('access_select.html',
                           title=title,
                           entity_name=entity_name,
                           ar_list=access_rules_list,
                           form=form,
                           suppress_next_btn=True)


def entity_access_select_post(filename=None, form=None, form_dict=None,
                              method=None, this_page=None, back_page=None,
                              next_page=None, edit_page=None,
                              dt_element_name=None, dt_node_id=None):
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

    if form.validate_on_submit():
        if new_page == edit_page:
            return url_for(new_page,
                           filename=filename,
                           dt_element_name=dt_element_name,
                           dt_node_id=dt_node_id,
                           node_id=node_id)
        elif new_page == this_page:
            return url_for(new_page,
                           filename=filename,
                           dt_element_name=dt_element_name,
                           dt_node_id=dt_node_id)
        else:
            return url_for(new_page,
                           filename=filename,
                           node_id=dt_node_id)


# node_id is the id of the access allow node being edited. If the value is
# '1', it means we are adding a new access node, otherwise we are
# editing an existing access node.
#
# dt_element_name will be either names.DATATABLE or names.OTHERENTITY
#
@ent_bp.route('/entity_access/<filename>/<dt_element_name>/<dt_node_id>/<node_id>', methods=['GET', 'POST'])
@login_required
def entity_access(filename=None, dt_element_name=None, dt_node_id=None, node_id=None):
    form = AccessForm(filename=filename, node_id=node_id)
    allow_node_id = node_id

    if request.method == 'POST' and BTN_CANCEL in request.form:
            url = url_for(PAGE_ENTITY_ACCESS_SELECT,
                      filename=filename,
                      dt_element_name=dt_element_name,
                      dt_node_id=dt_node_id,
                      node_id=allow_node_id)
            return redirect(url)

    # Determine POST type
    if request.method == 'POST':
        next_page = PAGE_ENTITY_ACCESS_SELECT  # Save or Back sends us back to the list of access rules

        # If we have a hidden button, we note that fact but we may need to save changes before going there.
        next_page = handle_hidden_buttons(next_page)

        if is_dirty_form(form):
            submit_type = 'Save Changes'
        else:
            submit_type = 'Back'

        # Process POST
        if submit_type == 'Save Changes':
            dt_node = None
            distribution_node = None
            eml_node = load_eml(filename=filename)
            dataset_node = eml_node.find_child(names.DATASET)
            if not dataset_node:
                dataset_node = Node(names.DATASET, parent=eml_node)
            else:
                data_table_nodes = dataset_node.find_all_children(dt_element_name)
                if data_table_nodes:
                    for data_table_node in data_table_nodes:
                        if data_table_node.id == dt_node_id:
                            dt_node = data_table_node
                            break

            if not dt_node:
                dt_node = Node(dt_element_name, parent=dataset_node)
                add_child(dataset_node, dt_node)

            physical_node = dt_node.find_child(names.PHYSICAL)
            if not physical_node:
                physical_node = Node(names.PHYSICAL, parent=dt_node)
                add_child(dt_node, physical_node)

            distribution_node = physical_node.find_child(names.DISTRIBUTION)
            if not distribution_node:
                distribution_node = Node(names.DISTRIBUTION, parent=physical_node)
                add_child(physical_node, distribution_node)

            access_node = distribution_node.find_child(names.ACCESS)
            if not access_node:
                access_node = create_access(parent_node=distribution_node)

            userid = form.userid.data
            permission = form.permission.data
            allow_node = Node(names.ALLOW, parent=access_node)
            create_access_rule(allow_node, userid, permission)

            if node_id and len(node_id) != 1:
                old_allow_node = Node.get_node_instance(node_id)

                if old_allow_node:
                    access_parent_node = old_allow_node.parent
                    access_parent_node.replace_child(old_allow_node,
                                                     allow_node)
                else:
                    msg = f"No 'allow' node found in the node store with node id {node_id}"
                    raise Exception(msg)
            else:
                add_child(access_node, allow_node)

            save_both_formats(filename=filename, eml_node=eml_node)
            allow_node_id = allow_node.id

        url = url_for(next_page,
                      filename=filename,
                      dt_element_name=dt_element_name,
                      dt_node_id=dt_node_id,
                      node_id=allow_node_id)
        return redirect(url)

    # Process GET
    if node_id != '1':
        eml_node = load_eml(filename=filename)
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            dt_nodes = dataset_node.find_all_children(dt_element_name)
            if dt_nodes:
                for dt_node in dt_nodes:
                    if dt_node_id == dt_node.id:
                        physical_node = dt_node.find_child(names.PHYSICAL)
                        if physical_node:
                            distribution_node = physical_node.find_child(names.DISTRIBUTION)
                            if distribution_node:
                                access_node = distribution_node.find_child(names.ACCESS)
                                if access_node:
                                    allow_nodes = access_node.find_all_children(names.ALLOW)
                                    if allow_nodes:
                                        for allow_node in allow_nodes:
                                            if node_id == allow_node.id:
                                                populate_access_rule_form(form, allow_node)
                                                break

    init_form_md5(form)

    set_current_page('other_entity')
    return render_template('access.html', title='Access Rule', form=form, filename=filename)


@ent_bp.route('/entity_method_step_select/<filename>/<dt_element_name>/<dt_node_id>',
            methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def entity_method_step_select(filename=None, dt_element_name: str = None, dt_node_id: str = None):
    form = MethodStepSelectForm(filename=filename)

    parent_page = PAGE_DATA_TABLE
    if dt_element_name == names.OTHERENTITY:
        parent_page = PAGE_OTHER_ENTITY

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)

        url = entity_select_post(filename, form, form_dict,
                                 'POST', PAGE_ENTITY_METHOD_STEP_SELECT,
                                 parent_page, parent_page, PAGE_ENTITY_METHOD_STEP,
                                 dt_element_name, dt_node_id)
        return redirect(url)

    # Process GET
    method_step_list = []
    title = 'Method Steps'
    entity_name = ''
    load_eml(filename=filename)

    if dt_node_id != '1':
        data_table_node = Node.get_node_instance(dt_node_id)
        if data_table_node:
            entity_name = entity_name_from_data_table(data_table_node)
            method_step_list = list_method_steps(eml_node, data_table_node)

    init_form_md5(form)

    if dt_element_name == 'dataTable':
        set_current_page('data_table')
    else:
        set_current_page('other_entity')
    help = [get_help('methods')]
    return render_template('method_step_select.html',
                           title=title,
                           entity_name=entity_name,
                           method_step_list=method_step_list,
                           form=form,
                           suppress_next_btn=True,
                           element_name=dt_element_name,
                           help=help)


# node_id is the id of the methodStep node being edited. If the value is
# '1', it means we are adding a new methodStep node, otherwise we are
# editing an existing one.
#
# dt_element_name will be either names.DATATABLE or names.OTHERENTITY
#
@ent_bp.route('/entity_method_step/<filename>/<dt_element_name>/<dt_node_id>/<node_id>',
            methods=['GET', 'POST'])
@login_required
def entity_method_step(filename=None, dt_element_name=None, dt_node_id=None, node_id=None):
    form = MethodStepForm(filename=filename, node_id=node_id)
    ms_node_id = node_id

    if request.method == 'POST' and BTN_CANCEL in request.form:
            url = url_for(PAGE_ENTITY_METHOD_STEP_SELECT,
                      filename=filename,
                      dt_element_name=dt_element_name,
                      dt_node_id=dt_node_id,
                      node_id=ms_node_id)
            return redirect(url)

    # Determine POST type
    if request.method == 'POST':
        next_page = PAGE_ENTITY_METHOD_STEP_SELECT  # Save or Back sends us back to the list of method steps

        # If we have a hidden button, we note that fact but we may need to save changes before going there.
        next_page = handle_hidden_buttons(next_page)

        if is_dirty_form(form):
            submit_type = 'Save Changes'
        else:
            submit_type = 'Back'

    # Process POST
    if form.validate_on_submit():
        if submit_type == 'Save Changes':
            dt_node = None
            eml_node = load_eml(filename=filename)
            dataset_node = eml_node.find_child(names.DATASET)
            if not dataset_node:
                dataset_node = Node(names.DATASET, parent=eml_node)
                add_child(eml_node, dataset_node)
            else:
                data_table_nodes = dataset_node.find_all_children(dt_element_name)
                if data_table_nodes:
                    for data_table_node in data_table_nodes:
                        if data_table_node.id == dt_node_id:
                            dt_node = data_table_node
                            break

            if not dt_node:
                dt_node = Node(dt_element_name, parent=dataset_node)
                add_child(dataset_node, dt_node)

            methods_node = dt_node.find_child(names.METHODS)
            if not methods_node:
                methods_node = Node(names.METHODS, parent=dt_node)
                add_child(dt_node, methods_node)

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
                    msg = f"No 'methodStep' node found in the node store with node id {node_id}"
                    raise Exception(msg)
            else:
                add_child(methods_node, method_step_node)

            save_both_formats(filename=filename, eml_node=eml_node)
            ms_node_id = method_step_node.id

        url = url_for(next_page,
                      filename=filename,
                      dt_element_name=dt_element_name,
                      dt_node_id=dt_node_id,
                      node_id=ms_node_id)
        return redirect(url)

    # Process GET
    if node_id != '1':
        eml_node = load_eml(filename=filename)
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            dt_nodes = dataset_node.find_all_children(dt_element_name)
            if dt_nodes:
                for dt_node in dt_nodes:
                    if dt_node_id == dt_node.id:
                        methods_node = dt_node.find_child(names.METHODS)
                        if methods_node:
                            method_step_nodes = methods_node.find_all_children(names.METHODSTEP)
                            if method_step_nodes:
                                for ms_node in method_step_nodes:
                                    if node_id == ms_node.id:
                                        populate_method_step_form(form, ms_node)
                                        break

    init_form_md5(form)

    if dt_element_name == 'dataTable':
        set_current_page('data_table')
    else:
        set_current_page('other_entity')
    help = [get_help('method_step_description'), get_help('method_step_instrumentation')]
    return render_template('method_step.html', title='Method Step', form=form, filename=filename, help=help)


@ent_bp.route('/entity_geographic_coverage_select/<filename>/<dt_element_name>/<dt_node_id>',
            methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def entity_geographic_coverage_select(filename=None, dt_element_name: str = None, dt_node_id: str = None):
    form = GeographicCoverageSelectForm(filename=filename)

    parent_page = PAGE_DATA_TABLE
    if dt_element_name == names.OTHERENTITY:
        parent_page = PAGE_OTHER_ENTITY

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = entity_select_post(filename, form, form_dict,
                                 'POST', PAGE_ENTITY_GEOGRAPHIC_COVERAGE_SELECT,
                                 parent_page, parent_page, PAGE_ENTITY_GEOGRAPHIC_COVERAGE,
                                 dt_element_name, dt_node_id)
        return redirect(url)

    # Process GET
    gc_list = []
    title = "Geographic Coverage"
    entity_name = ''
    eml_node = load_eml(filename=filename)

    if dt_node_id != '1':
        data_table_node = Node.get_node_instance(dt_node_id)
        if data_table_node:
            entity_name = entity_name_from_data_table(data_table_node)
            gc_list = list_geographic_coverages(eml_node, data_table_node)

    init_form_md5(form)

    if dt_element_name == 'dataTable':
        set_current_page('data_table')
    else:
        set_current_page('other_entity')
    help = [get_help('geographic_coverages')]
    return render_template('geographic_coverage_select.html',
                           title=title,
                           entity_name=entity_name,
                           gc_list=gc_list,
                           form=form,
                           suppress_next_btn=True,
                           element_name=dt_element_name,
                           help=help)


@ent_bp.route('/entity_geographic_coverage/<filename>/<dt_element_name>/<dt_node_id>/<node_id>',
            methods=['GET', 'POST'])
@login_required
def entity_geographic_coverage(filename=None, dt_element_name=None, dt_node_id=None, node_id=None):
    form = GeographicCoverageForm(filename=filename)
    gc_node_id = node_id

    if request.method == 'POST' and BTN_CANCEL in request.form:
            url = url_for(PAGE_ENTITY_GEOGRAPHIC_COVERAGE_SELECT,
                      filename=filename,
                      dt_element_name=dt_element_name,
                      dt_node_id=dt_node_id,
                      node_id=gc_node_id)
            return redirect(url)

    # Determine POST type
    if request.method == 'POST':
        next_page = PAGE_ENTITY_GEOGRAPHIC_COVERAGE_SELECT  # Save or Back sends us back to the list of method steps

        # If we have a hidden button, we note that fact but we may need to save changes before going there.
        next_page = handle_hidden_buttons(next_page)

        if is_dirty_form(form):
            submit_type = 'Save Changes'
        else:
            submit_type = 'Back'

    # Process POST
    if form.validate_on_submit():
        if submit_type == 'Save Changes':
            dt_node = None
            eml_node = load_eml(filename=filename)

            dataset_node = eml_node.find_child(names.DATASET)
            if not dataset_node:
                dataset_node = Node(names.DATASET, parent=eml_node)
                add_child(eml_node, dataset_node)
            else:
                data_table_nodes = dataset_node.find_all_children(dt_element_name)
                if data_table_nodes:
                    for data_table_node in data_table_nodes:
                        if data_table_node.id == dt_node_id:
                            dt_node = data_table_node
                            break

            if not dt_node:
                dt_node = Node(dt_element_name, parent=dataset_node)
                add_child(dataset_node, dt_node)

            coverage_node = dt_node.find_child(names.COVERAGE)
            if not coverage_node:
                coverage_node = Node(names.COVERAGE, parent=dt_node)
                add_child(dt_node, coverage_node)

            geographic_description = form.geographic_description.data
            wbc = form.wbc.data
            ebc = form.ebc.data
            nbc = form.nbc.data
            sbc = form.sbc.data

            if nbc and sbc and nbc < sbc:
                flash('North should be greater than or equal to South')
                next_page = PAGE_ENTITY_GEOGRAPHIC_COVERAGE

            if ebc and wbc and ebc < wbc:
                flash('East should be greater than or equal to West')
                next_page = PAGE_ENTITY_GEOGRAPHIC_COVERAGE

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

            save_both_formats(filename=filename, eml_node=eml_node)
            gc_node_id = gc_node.id

        url = url_for(next_page,
                      filename=filename,
                      dt_element_name=dt_element_name,
                      dt_node_id=dt_node_id,
                      node_id=gc_node_id)

        return redirect(url)

    # Process GET
    if node_id != '1':
        eml_node = load_eml(filename=filename)
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            dt_nodes = dataset_node.find_all_children(dt_element_name)
            if dt_nodes:
                for dt_node in dt_nodes:
                    if dt_node_id == dt_node.id:
                        coverage_node = dt_node.find_child(names.COVERAGE)
                        if coverage_node:
                            gc_nodes = coverage_node.find_all_children(names.GEOGRAPHICCOVERAGE)
                            if gc_nodes:
                                for gc_node in gc_nodes:
                                    if node_id == gc_node.id:
                                        populate_geographic_coverage_form(form, gc_node)
                                        break

    init_form_md5(form)

    if dt_element_name == 'dataTable':
        set_current_page('data_table')
    else:
        set_current_page('other_entity')
    help = [get_help('geographic_coverages'), get_help('geographic_description'), get_help('bounding_coordinates')]
    return render_template('geographic_coverage.html', title='Geographic Coverage', form=form, filename=filename, help=help)


def entity_select_post(filename=None, form=None, form_dict=None,
                       method=None, this_page=None, back_page=None,
                       next_page=None, edit_page=None,
                       dt_element_name: str = None, dt_node_id: str = None, ):
    node_id = ''
    new_page = ''

    if form_dict:
        for key in form_dict:
            val = form_dict[key][0]  # value is the first list element
            if val.startswith(BTN_BACK):
                new_page = back_page
            elif val == BTN_NEXT:
                new_page = next_page
            elif val.startswith(BTN_EDIT):
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
            new_page = check_val_for_hidden_buttons(val, new_page)
            if val == BTN_HIDDEN_SAVE:
                node_id = key

    if form.validate_on_submit():
        if new_page == edit_page:
            url = url_for(new_page,
                          filename=filename,
                          dt_element_name=dt_element_name,
                          dt_node_id=dt_node_id,
                          node_id=node_id)
        elif new_page == this_page:
            url = url_for(new_page,
                          filename=filename,
                          dt_element_name=dt_element_name,
                          dt_node_id=dt_node_id)
        else:
            url = url_for(new_page,
                          filename=filename,
                          node_id=dt_node_id)
        return url


@ent_bp.route('/entity_temporal_coverage_select/<filename>/<dt_element_name>/<dt_node_id>',
            methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def entity_temporal_coverage_select(filename=None, dt_element_name: str = None, dt_node_id: str = None):
    form = TemporalCoverageSelectForm(filename=filename)

    parent_page = PAGE_DATA_TABLE
    if dt_element_name == names.OTHERENTITY:
        parent_page = PAGE_OTHER_ENTITY

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = entity_select_post(filename, form, form_dict,
                                 'POST', PAGE_ENTITY_GEOGRAPHIC_COVERAGE_SELECT,
                                 parent_page, parent_page, PAGE_ENTITY_TEMPORAL_COVERAGE,
                                 dt_element_name, dt_node_id)
        return redirect(url)

    # Process GET
    tc_list = []
    title = "Temporal Coverage"
    entity_name = ''
    eml_node = load_eml(filename=filename)

    if dt_node_id != '1':
        data_table_node = Node.get_node_instance(dt_node_id)
        if data_table_node:
            entity_name = entity_name_from_data_table(data_table_node)
            tc_list = list_temporal_coverages(eml_node, data_table_node)

    init_form_md5(form)

    if dt_element_name == 'dataTable':
        set_current_page('data_table')
    else:
        set_current_page('other_entity')
    help = [get_help('temporal_coverages')]
    return render_template('temporal_coverage_select.html',
                           title=title,
                           entity_name=entity_name,
                           tc_list=tc_list,
                           form=form,
                           suppress_next_btn=True,
                           element_name=dt_element_name,
                           help=help)


@ent_bp.route('/entity_temporal_coverage/<filename>/<dt_element_name>/<dt_node_id>/<node_id>',
            methods=['GET', 'POST'])
@login_required
def entity_temporal_coverage(filename=None, dt_element_name=None, dt_node_id=None, node_id=None):
    form = TemporalCoverageForm(filename=filename)
    tc_node_id = node_id

    if request.method == 'POST' and BTN_CANCEL in request.form:
            url = url_for(PAGE_ENTITY_TEMPORAL_COVERAGE_SELECT,
                      filename=filename,
                      dt_element_name=dt_element_name,
                      dt_node_id=dt_node_id,
                      node_id=tc_node_id)
            return redirect(url)

    # Determine POST type
    if request.method == 'POST':
        next_page = PAGE_ENTITY_TEMPORAL_COVERAGE_SELECT  # Save or Back sends us back to the list of method steps

        # If we have a hidden button, we note that fact but we may need to save changes before going there.
        next_page = handle_hidden_buttons(next_page)

        if is_dirty_form(form):
            submit_type = 'Save Changes'
        else:
            submit_type = 'Back'

    # Process POST
    if form.validate_on_submit():
        if submit_type == 'Save Changes':
            dt_node = None
            eml_node = load_eml(filename=filename)

            dataset_node = eml_node.find_child(names.DATASET)
            if not dataset_node:
                dataset_node = Node(names.DATASET)
                add_child(eml_node, dataset_node)
            else:
                data_table_nodes = dataset_node.find_all_children(dt_element_name)
                if data_table_nodes:
                    for data_table_node in data_table_nodes:
                        if data_table_node.id == dt_node_id:
                            dt_node = data_table_node
                            break

            if not dt_node:
                dt_node = Node(dt_element_name, parent=dataset_node)
                add_child(dataset_node, dt_node)

            coverage_node = dt_node.find_child(names.COVERAGE)
            if not coverage_node:
                coverage_node = Node(names.COVERAGE, parent=dt_node)
                add_child(dt_node, coverage_node)

            begin_date_str = form.begin_date.data
            end_date_str = form.end_date.data
            tc_node = Node(names.TEMPORALCOVERAGE, parent=coverage_node)
            create_temporal_coverage(tc_node, begin_date_str, end_date_str)

            if node_id and len(node_id) != 1:
                old_tc_node = Node.get_node_instance(node_id)

                if old_tc_node:
                    coverage_parent_node = old_tc_node.parent
                    coverage_parent_node.replace_child(old_tc_node, tc_node)
                else:
                    msg = f"No node found in the node store with node id {node_id}"
                    raise Exception(msg)
            else:
                add_child(coverage_node, tc_node)

            tc_node_id = tc_node.id

            flash_msg = compare_begin_end_dates(begin_date_str, end_date_str)
            if flash_msg:
                flash(flash_msg)
                next_page = PAGE_ENTITY_TEMPORAL_COVERAGE

            save_both_formats(filename=filename, eml_node=eml_node)

        url = url_for(next_page,
                      filename=filename,
                      dt_element_name=dt_element_name,
                      dt_node_id=dt_node_id,
                      node_id=tc_node_id)
        return redirect(url)

    # Process GET
    if node_id != '1':
        eml_node = load_eml(filename=filename)
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            dt_nodes = dataset_node.find_all_children(dt_element_name)
            if dt_nodes:
                for dt_node in dt_nodes:
                    if dt_node_id == dt_node.id:
                        coverage_node = dt_node.find_child(names.COVERAGE)
                        if coverage_node:
                            tc_nodes = coverage_node.find_all_children(names.TEMPORALCOVERAGE)
                            if tc_nodes:
                                for tc_node in tc_nodes:
                                    if node_id == tc_node.id:
                                        populate_temporal_coverage_form(form, tc_node)
                                        break

    init_form_md5(form)

    if dt_element_name == 'dataTable':
        set_current_page('data_table')
    else:
        set_current_page('other_entity')
    return render_template('temporal_coverage.html', title='Temporal Coverage', form=form, filename=filename)


@ent_bp.route('/entity_taxonomic_coverage_select/<filename>/<dt_element_name>/<dt_node_id>',
            methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def entity_taxonomic_coverage_select(filename=None, dt_element_name: str = None, dt_node_id: str = None):
    form = TaxonomicCoverageSelectForm(filename=filename)

    parent_page = PAGE_DATA_TABLE
    if dt_element_name == names.OTHERENTITY:
        parent_page = PAGE_OTHER_ENTITY

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = entity_select_post(filename, form, form_dict,
                                 'POST', PAGE_ENTITY_TAXONOMIC_COVERAGE_SELECT,
                                 parent_page, parent_page, PAGE_ENTITY_TAXONOMIC_COVERAGE,
                                 dt_element_name, dt_node_id)
        return redirect(url)

    # Process GET
    txc_list = []
    title = "Taxonomic Coverage"
    entity_name = ''
    eml_node = load_eml(filename=filename)

    if dt_node_id != '1':
        data_table_node = Node.get_node_instance(dt_node_id)
        if data_table_node:
            entity_name = entity_name_from_data_table(data_table_node)
            txc_list = list_taxonomic_coverages(eml_node, data_table_node)

    init_form_md5(form)

    if dt_element_name == 'dataTable':
        set_current_page('data_table')
    else:
        set_current_page('other_entity')
    help = [get_help('taxonomic_coverages')]
    return render_template('taxonomic_coverage_select.html',
                           title=title,
                           entity_name=entity_name,
                           txc_list=txc_list,
                           form=form,
                           suppress_next_btn=True,
                           element_name=dt_element_name,
                           help=help)


@ent_bp.route('/entity_taxonomic_coverage/<filename>/<dt_element_name>/<dt_node_id>/<node_id>',
            methods=['GET', 'POST'])
@login_required
def entity_taxonomic_coverage(filename=None, dt_element_name=None, dt_node_id=None, node_id=None):
    form = TaxonomicCoverageForm(filename=filename)
    txc_node_id = node_id

    if request.method == 'POST' and BTN_CANCEL in request.form:
            url = url_for(PAGE_ENTITY_TAXONOMIC_COVERAGE_SELECT,
                      filename=filename,
                      dt_element_name=dt_element_name,
                      dt_node_id=dt_node_id,
                      node_id=txc_node_id)
            return redirect(url)

    # Determine POST type
    if request.method == 'POST':
        next_page = PAGE_ENTITY_TAXONOMIC_COVERAGE_SELECT  # Save or Back sends us back to the list of method steps

        # If we have a hidden button, we note that fact but we may need to save changes before going there.
        next_page = handle_hidden_buttons(next_page)

        if is_dirty_form(form):
            submit_type = 'Save Changes'
        else:
            submit_type = 'Back'

    # Process POST
    if form.validate_on_submit():
        if submit_type == 'Save Changes':
            dt_node = None
            eml_node = load_eml(filename=filename)

            dataset_node = eml_node.find_child(names.DATASET)
            if not dataset_node:
                dataset_node = Node(names.DATASET)
                add_child(eml_node, dataset_node)
            else:
                data_table_nodes = dataset_node.find_all_children(dt_element_name)
                if data_table_nodes:
                    for data_table_node in data_table_nodes:
                        if data_table_node.id == dt_node_id:
                            dt_node = data_table_node
                            break

            if not dt_node:
                dt_node = Node(dt_element_name, parent=dataset_node)
                add_child(dataset_node, dt_node)

            coverage_node = dt_node.find_child(names.COVERAGE)
            if not coverage_node:
                coverage_node = Node(names.COVERAGE, parent=dt_node)
                add_child(dt_node, coverage_node)

            txc_node = Node(names.TAXONOMICCOVERAGE, parent=coverage_node)

            create_taxonomic_coverage(
                txc_node,
                form.general_taxonomic_coverage.data,
                form.kingdom_value.data,
                form.kingdom_common_name.data,
                form.phylum_value.data,
                form.phylum_common_name.data,
                form.class_value.data,
                form.class_common_name.data,
                form.order_value.data,
                form.order_common_name.data,
                form.family_value.data,
                form.family_common_name.data,
                form.genus_value.data,
                form.genus_common_name.data,
                form.species_value.data,
                form.species_common_name.data)

            if node_id and len(node_id) != 1:
                old_txc_node = Node.get_node_instance(node_id)

                if old_txc_node:
                    coverage_parent_node = old_txc_node.parent
                    coverage_parent_node.replace_child(old_txc_node, txc_node)
                else:
                    msg = f"No node found in the node store with node id {node_id}"
                    raise Exception(msg)
            else:
                add_child(coverage_node, txc_node)

            save_both_formats(filename=filename, eml_node=eml_node)
            txc_node_id = txc_node.id

        url = url_for(next_page,
                      filename=filename,
                      dt_element_name=dt_element_name,
                      dt_node_id=dt_node_id,
                      node_id=txc_node_id)
        return redirect(url)

    # Process GET
    if node_id != '1':
        eml_node = load_eml(filename=filename)
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            dt_nodes = dataset_node.find_all_children(dt_element_name)
            if dt_nodes:
                for dt_node in dt_nodes:
                    if dt_node_id == dt_node.id:
                        coverage_node = dt_node.find_child(names.COVERAGE)
                        if coverage_node:
                            txc_nodes = coverage_node.find_all_children(names.TAXONOMICCOVERAGE)
                            if txc_nodes:
                                for txc_node in txc_nodes:
                                    if node_id == txc_node.id:
                                        populate_temporal_coverage_form(form, txc_node)  # FIXME - is this right??
                                        break

    init_form_md5(form)

    if dt_element_name == 'dataTable':
        set_current_page('data_table')
    else:
        set_current_page('other_entity')
    return render_template('taxonomic_coverage.html', title='Taxonomic Coverage', form=form, filename=filename)
