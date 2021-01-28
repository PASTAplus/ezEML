import hashlib

from flask import (
    Blueprint, Flask, flash, render_template, redirect, request, session, url_for, app, current_app
)

from flask_login import (
    login_required
)

from webapp.config import Config

from webapp.home.views import (
    process_up_button, process_down_button,
    backup_metadata, set_current_page
)

from webapp.views.data_tables.forms import (
    AttributeDateTimeForm, AttributeIntervalRatioForm,
    AttributeMeasurementScaleForm, AttributeCategoricalForm,
    AttributeSelectForm, AttributeTextForm,
    CodeDefinitionForm, CodeDefinitionSelectForm,
    DataTableForm, DataTableSelectForm, SelectDataTableForm, SelectDataTableColumnsForm
)

from webapp.home.forms import (
    form_md5, is_dirty_form,
    ImportEMLForm, ImportEMLItemsForm
)

from webapp.home.metapype_client import (
    load_eml, save_both_formats, new_child_node, add_child, remove_child,
    create_data_table, list_data_packages, list_data_tables, list_data_table_columns, list_attributes,
    entity_name_from_data_table, attribute_name_from_attribute,
    list_codes_and_definitions, enumerated_domain_from_attribute,
    create_code_definition, mscale_from_attribute,
    create_datetime_attribute, create_numerical_attribute,
    create_categorical_or_text_attribute, VariableType,
    UP_ARROW, DOWN_ARROW, code_definition_from_attribute
)

from webapp.home.views import (
    get_back_url
)

from metapype.eml import names
from metapype.model.node import Node

from webapp.buttons import *
from webapp.pages import *

from webapp.home.views import select_post, non_breaking, get_help, get_helps

from webapp.auth.user_data import (
    data_table_was_uploaded
)

dt_bp = Blueprint('dt', __name__, template_folder='templates')


@dt_bp.route('/data_table_select/<filename>', methods=['GET', 'POST'])
def data_table_select(filename=None):
    form = DataTableSelectForm(filename=filename)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = select_post(filename, form, form_dict,
                          'POST',
                          PAGE_DATA_TABLE_SELECT,
                          PAGE_PROJECT,
                          PAGE_CREATOR_SELECT,
                          PAGE_DATA_TABLE)
        return redirect(url)

    # Process GET
    eml_node = load_eml(filename=filename)
    eml_node = load_eml(filename=filename)
    dt_list = list_data_tables(eml_node)
    title = 'Data Tables'

    set_current_page('data_table')
    help = [get_help('data_tables'), get_help('add_load_data_tables'), get_help('data_table_reupload')]
    return render_template('data_table_select.html', title=title,
                           dt_list=dt_list, form=form, help=help)


@dt_bp.route('/data_table/<filename>/<node_id>', methods=['GET', 'POST'])
def data_table(filename=None, node_id=None, delimiter=None, quote_char=None):
    form = DataTableForm(filename=filename)
    dt_node_id = node_id

    # Process POST
    if request.method == 'POST' and BTN_CANCEL in request.form:
        url = url_for(PAGE_DATA_TABLE_SELECT, filename=filename)
        return redirect(url)

    if request.method == 'POST':
        next_page = PAGE_DATA_TABLE_SELECT

        submit_type = None
        if is_dirty_form(form):
            submit_type = 'Save Changes'

        if 'Attributes' in request.form:
            next_page = PAGE_ATTRIBUTE_SELECT
        elif 'Clone' in request.form:
            next_page = PAGE_CLONE_ATTRIBUTES
        elif 'Access' in request.form:
            next_page = PAGE_ENTITY_ACCESS_SELECT
        elif 'Methods' in request.form:
            next_page = PAGE_ENTITY_METHOD_STEP_SELECT
        elif 'Geographic' in request.form:
            next_page = PAGE_ENTITY_GEOGRAPHIC_COVERAGE_SELECT
        elif 'Temporal' in request.form:
            next_page = PAGE_ENTITY_TEMPORAL_COVERAGE_SELECT
        elif 'Taxonomic' in request.form:
            next_page = PAGE_ENTITY_TAXONOMIC_COVERAGE_SELECT
        elif BTN_HIDDEN_NEW in request.form:
            next_page = PAGE_CREATE
        elif BTN_HIDDEN_OPEN in request.form:
            next_page = PAGE_OPEN
        elif BTN_HIDDEN_CLOSE in request.form:
            next_page = PAGE_CLOSE

    if form.validate_on_submit():
        eml_node = load_eml(filename=filename)

        if submit_type == 'Save Changes':
            dataset_node = eml_node.find_child(names.DATASET)
            if not dataset_node:
                dataset_node = Node(names.DATASET)

            entity_name = form.entity_name.data
            entity_description = form.entity_description.data
            object_name = form.object_name.data
            size = str(form.size.data) if form.size.data else ''
            md5_hash = form.md5_hash.data
            num_header_lines = str(form.num_header_lines.data) if form.num_header_lines.data else ''
            record_delimiter = form.record_delimiter.data
            quote_character = form.quote_character.data
            attribute_orientation = form.attribute_orientation.data
            field_delimiter = form.field_delimiter.data
            case_sensitive = form.case_sensitive.data
            number_of_records = str(form.number_of_records.data) if form.number_of_records.data else ''
            online_url = form.online_url.data

            dt_node = Node(names.DATATABLE, parent=dataset_node)

            if not entity_name:
                entity_name = ''

            create_data_table(
                dt_node,
                entity_name,
                entity_description,
                object_name,
                size,
                md5_hash,
                num_header_lines,
                record_delimiter,
                quote_character,
                attribute_orientation,
                field_delimiter,
                case_sensitive,
                number_of_records,
                online_url)

            if dt_node_id and len(dt_node_id) != 1:
                old_dt_node = Node.get_node_instance(dt_node_id)
                if old_dt_node:

                    attribute_list_node = old_dt_node.find_child(names.ATTRIBUTELIST)
                    if attribute_list_node:
                        old_dt_node.remove_child(attribute_list_node)
                        add_child(dt_node, attribute_list_node)

                    old_distribution_node = old_dt_node.find_single_node_by_path([
                        names.PHYSICAL,
                        names.DISTRIBUTION

                    ])
                    if old_distribution_node:
                        access_node = old_distribution_node.find_child(names.ACCESS)
                        if access_node:
                            distribution_node = dt_node.find_single_node_by_path([
                                names.PHYSICAL,
                                names.DISTRIBUTION
                            ])
                            old_distribution_node.remove_child(access_node)
                            add_child(distribution_node, access_node)

                    methods_node = old_dt_node.find_child(names.METHODS)
                    if methods_node:
                        old_dt_node.remove_child(methods_node)
                        add_child(dt_node, methods_node)

                    coverage_node = old_dt_node.find_child(names.COVERAGE)
                    if coverage_node:
                        old_dt_node.remove_child(coverage_node)
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

        if next_page in [
            PAGE_ENTITY_ACCESS_SELECT,
            PAGE_ENTITY_METHOD_STEP_SELECT,
            PAGE_ENTITY_GEOGRAPHIC_COVERAGE_SELECT,
            PAGE_ENTITY_TEMPORAL_COVERAGE_SELECT,
            PAGE_ENTITY_TAXONOMIC_COVERAGE_SELECT,
        ]:
            return redirect(url_for(next_page,
                                    filename=filename,
                                    dt_element_name=names.DATATABLE,
                                    dt_node_id=dt_node_id))
        else:
            return redirect(url_for(next_page,
                                    filename=filename,
                                    dt_node_id=dt_node_id))

    # Process GET
    atts = 'No data table attributes have been added'

    was_uploaded = False
    if dt_node_id == '1':
        form.init_md5()
    else:
        eml_node = load_eml(filename=filename)
        if eml_node:
            dataset_node = eml_node.find_child(names.DATASET)
            if dataset_node:
                dt_nodes = dataset_node.find_all_children(names.DATATABLE)
                if dt_nodes:
                    for dt_node in dt_nodes:
                        if dt_node_id == dt_node.id:
                            att_list = list_attributes(dt_node, 'data_table', dt_node_id)
                            if att_list:
                                atts = compose_atts(att_list)
                            populate_data_table_form(form, dt_node)

                            object_name_node = dt_node.find_single_node_by_path([names.PHYSICAL, names.OBJECTNAME])
                            if object_name_node:
                                object_name = object_name_node.content
                                if object_name:
                                    was_uploaded = data_table_was_uploaded(object_name)

        else:
            flash('eml_node is None')

    set_current_page('data_table')
    help = get_helps([
        'data_table',
        'data_table_name',
        'data_table_description',
        'data_table_object_name',
        'data_table_attribute_orientation',
        'data_table_field_delimiter',
        'data_table_size',
        'data_table_checksum',
        'data_table_header_lines',
        'data_table_record_delimiter',
        'data_table_quote_character',
        'data_table_case_sensitive',
        'data_table_number_of_records',
        'data_table_online_url',
        'clone_attributes_general'
    ])
    return render_template('data_table.html', title='Data Table', form=form,
                           atts=atts, help=help, was_uploaded=was_uploaded)


def compose_codes():
    code_list = list_codes_and_definitions()


def compose_atts(att_list: list = []):
    atts = []
    if att_list:
        for att in att_list:
            atts.append(att.label if att.label else 'unnamed')
    return ', '.join(atts)


def populate_data_table_form(form: DataTableForm, node: Node):
    entity_name_node = node.find_child(names.ENTITYNAME)
    if entity_name_node:
        form.entity_name.data = entity_name_node.content

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

            text_format_node = data_format_node.find_child(names.TEXTFORMAT)
            if text_format_node:

                num_header_lines_node = text_format_node.find_child(names.NUMHEADERLINES)
                if num_header_lines_node:
                    form.num_header_lines.data = num_header_lines_node.content

                record_delimiter_node = text_format_node.find_child(names.RECORDDELIMITER)
                if record_delimiter_node:
                    form.record_delimiter.data = record_delimiter_node.content

                attribute_orientation_node = text_format_node.find_child(names.ATTRIBUTEORIENTATION)
                if attribute_orientation_node:
                    form.attribute_orientation.data = attribute_orientation_node.content

                simple_delimited_node = text_format_node.find_child(names.SIMPLEDELIMITED)
                if simple_delimited_node:

                    quote_character_node = simple_delimited_node.find_child(names.QUOTECHARACTER)
                    if quote_character_node:
                        form.quote_character.data = quote_character_node.content

                    field_delimiter_node = simple_delimited_node.find_child(names.FIELDDELIMITER)
                    if field_delimiter_node:
                        form.field_delimiter.data = field_delimiter_node.content

        distribution_node = physical_node.find_child(names.DISTRIBUTION)
        if distribution_node:

            online_node = distribution_node.find_child(names.ONLINE)
            if online_node:

                url_node = online_node.find_child(names.URL)
                if url_node:
                    form.online_url.data = url_node.content

    case_sensitive_node = node.find_child(names.CASESENSITIVE)
    if case_sensitive_node:
        form.case_sensitive.data = case_sensitive_node.content

    number_of_records_node = node.find_child(names.NUMBEROFRECORDS)
    if number_of_records_node:
        form.number_of_records.data = number_of_records_node.content

    form.md5.data = form_md5(form)


# <dt_node_id> identifies the dataTable node that this attribute
# is a part of (within its attributeList)
#
@dt_bp.route('/attribute_select/<filename>/<dt_node_id>', methods=['GET', 'POST'])
def attribute_select(filename=None, dt_node_id=None):
    form = AttributeSelectForm(filename=filename)
    # dt_node_id = request.args.get('dt_node_id')  # alternate way to get the id

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = attribute_select_post(filename, form, form_dict,
                                    'POST', PAGE_ATTRIBUTE_SELECT, PAGE_DATA_TABLE,
                                    dt_node_id=dt_node_id)
        return redirect(url)

    # Process GET
    return attribute_select_get(filename=filename, form=form, dt_node_id=dt_node_id)


def attribute_select_get(filename=None, form=None, dt_node_id=None):
    # Process GET
    att_list = []
    title = 'Attributes'
    entity_name = ''
    was_uploaded = False
    load_eml(filename=filename)

    if dt_node_id == '1':
        form.init_md5()
    else:
        data_table_node = Node.get_node_instance(dt_node_id)
        if data_table_node:
            entity_name = entity_name_from_data_table(data_table_node)
            app = Flask(__name__)

            att_list = list_attributes(data_table_node, 'attribute_select_get', dt_node_id)
            if Config.FLASH_DEBUG:
                # check attr node ids in list
                ok = True
                for attr_entry in att_list:
                    id = attr_entry.id
                    if not Node.get_node_instance(id):
                        ok = False
                        flash('Missing attr node for {attr_entry.label}: id={id}')
                if ok:
                    flash('Attr node ids ok')
                for key, node in Node.store.items():
                    if node.id != key:
                        flash(f'Node store inconsistency for node {node.name} with id={node.id}')

            object_name_node = data_table_node.find_single_node_by_path([names.PHYSICAL, names.OBJECTNAME])
            if object_name_node:
                object_name = object_name_node.content
                if object_name:
                    was_uploaded = data_table_was_uploaded(object_name)

    set_current_page('data_table')
    help = [get_help('measurement_scale')]
    return render_template('attribute_select.html',
                           title=title,
                           entity_name=entity_name,
                           att_list=att_list,
                           was_uploaded=was_uploaded,
                           form=form,
                           help=help)


@dt_bp.route('/attribute_measurement_scale/<filename>/<dt_node_id>/<node_id>/<mscale>', methods=['GET', 'POST'])
def attribute_measurement_scale(filename=None, dt_node_id=None, node_id=None, mscale=None):
    form = AttributeMeasurementScaleForm(filename=filename)
    att_node_id = node_id

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        return attribute_measurement_scale_post(
            filename, form, form_dict, dt_node_id, att_node_id, mscale
        )

    # Process GET
    return attribute_measurement_scale_get(filename, form, att_node_id)


def attribute_measurement_scale_post(filename, form, form_dict, dt_node_id, att_node_id, mscale):
    if BTN_OK in form_dict and 'mscale_choice' in form_dict:
        eml_node = load_eml(filename=filename)
        old_mscale = mscale
        new_mscale = form_dict['mscale_choice'][0]
        att_node = Node.get_node_instance(att_node_id)
        change_measurement_scale(att_node, old_mscale, new_mscale)
        save_both_formats(filename=filename, eml_node=eml_node)
    url = url_for(PAGE_ATTRIBUTE_SELECT,
                  filename=filename,
                  dt_node_id=dt_node_id)
    return redirect(url)


def attribute_measurement_scale_get(filename, form, att_node_id):
    load_eml(filename)
    node_to_change = Node.get_node_instance(att_node_id)
    name_child = node_to_change.find_child(names.ATTRIBUTENAME)
    name = name_child.content
    if not name:
        name = 'Attribute'
    mscale = mscale_from_attribute(node_to_change)
    if mscale is not None:
        form.mscale_choice.data = mscale

    set_current_page('data_table')
    return render_template('attribute_measurement_scale.html', entity_name=name, form=form)


def change_measurement_scale(att_node, old_mscale, new_mscale):
    if not att_node:
        return
    if old_mscale == new_mscale:
        return
    # flash(f'Changing from {old_mscale} to {new_mscale}')
    mscale_node = att_node.find_child(names.MEASUREMENTSCALE)

    # clear its children
    mscale_node.remove_children()

    # construct new children
    if new_mscale == VariableType.NUMERICAL.name:
        new_scale_node = new_child_node(names.RATIO, mscale_node)
        numeric_domain_node = new_child_node(names.NUMERICDOMAIN, new_scale_node)

        number_type_ratio_node = new_child_node(names.NUMBERTYPE, numeric_domain_node)
        number_type_ratio_node.content = 'real'

    elif new_mscale == VariableType.CATEGORICAL.name:
        new_scale_node = new_child_node(names.NOMINAL, mscale_node)
        non_numeric_domain_node = new_child_node(names.NONNUMERICDOMAIN, new_scale_node)
        enumerated_domain_node = new_child_node(names.ENUMERATEDDOMAIN, non_numeric_domain_node)

    elif new_mscale == VariableType.TEXT.name:
        new_scale_node = new_child_node(names.NOMINAL, mscale_node)
        non_numeric_domain_node = new_child_node(names.NONNUMERICDOMAIN, new_scale_node)
        text_domain_node = new_child_node(names.TEXTDOMAIN, non_numeric_domain_node)
        definition_node = new_child_node(names.DEFINITION, text_domain_node)
        attribute_definition_node = att_node.find_child(names.ATTRIBUTEDEFINITION)
        if attribute_definition_node:
            definition_node.content = attribute_definition_node.content

    elif new_mscale == VariableType.DATETIME.name:
        new_scale_node = new_child_node(names.DATETIME, mscale_node)
        format_string_node = new_child_node(names.FORMATSTRING, new_scale_node)
        format_string_node.content = ''


def attribute_select_post(filename=None, form=None, form_dict=None,
                          method=None, this_page=None, back_page=None,
                          dt_node_id=None):
    load_eml(filename)
    node_id = ''
    new_page = ''
    mscale = ''

    if form_dict:
        for key in form_dict:
            val = form_dict[key][0]  # value is the first list element
            if Config.FLASH_DEBUG:
                flash(f'val:{val}')
            if val.startswith(BTN_BACK):
                new_page = back_page
            elif val.startswith(BTN_EDIT):
                node_id = key
                attribute_node = Node.get_node_instance(node_id)

                # app = Flask(__name__)
                # with app.app_context():
                #     current_app.logger.info(f'dt_node_id={dt_node_id}')

                # TEMP - for debugging - this will cause logging to happen
                list_attributes(Node.get_node_instance(dt_node_id), 'attribute_select_post', dt_node_id)

                if Config.FLASH_DEBUG:
                    if not attribute_node:
                        flash('attribute_node not found')
                mscale = mscale_from_attribute(attribute_node)
                if Config.FLASH_DEBUG:
                    flash(f'val:{val} node_id:{node_id} mscale:{mscale}')
                if mscale == VariableType.DATETIME.name:
                    new_page = PAGE_ATTRIBUTE_DATETIME
                elif mscale == VariableType.NUMERICAL.name:
                    new_page = PAGE_ATTRIBUTE_NUMERICAL
                elif mscale == VariableType.CATEGORICAL.name:
                    new_page = PAGE_ATTRIBUTE_CATEGORICAL
                elif mscale == VariableType.TEXT.name:
                    new_page = PAGE_ATTRIBUTE_TEXT
            elif val == BTN_REMOVE:
                new_page = this_page
                node_id = key
                eml_node = load_eml(filename=filename)
                remove_child(node_id=node_id)
                save_both_formats(filename=filename, eml_node=eml_node)
            elif val == BTN_CHANGE_SCALE:
                node_id = key
                node_to_change = Node.get_node_instance(node_id)
                mscale = mscale_from_attribute(node_to_change)
                new_page = PAGE_ATTRIBUTE_MEASUREMENT_SCALE
            elif val == UP_ARROW:
                new_page = this_page
                node_id = key
                process_up_button(filename, node_id)
            elif val == DOWN_ARROW:
                new_page = this_page
                node_id = key
                process_down_button(filename, node_id)
            elif val == BTN_HIDDEN_CHECK:
                new_page = PAGE_CHECK
            elif val == BTN_HIDDEN_SAVE:
                new_page = this_page
            elif val == BTN_HIDDEN_DOWNLOAD:
                new_page = PAGE_DOWNLOAD
            elif val == BTN_HIDDEN_NEW:
                new_page = PAGE_CREATE
            elif val == BTN_HIDDEN_OPEN:
                new_page = PAGE_OPEN
            elif val == BTN_HIDDEN_CLOSE:
                new_page = PAGE_CLOSE
            elif val.startswith('Add Attribute'):
                if 'Numerical' in val:
                    mscale = 'NUMERICAL'
                    new_page = PAGE_ATTRIBUTE_NUMERICAL
                elif 'Categorical' in val:
                    mscale = 'CATEGORICAL'
                    new_page = PAGE_ATTRIBUTE_CATEGORICAL
                elif 'Text' in val:
                    mscale = 'TEXT'
                    new_page = PAGE_ATTRIBUTE_TEXT
                elif 'Datetime' in val:
                    new_page = PAGE_ATTRIBUTE_DATETIME
                node_id = '1'

    if form.validate_on_submit():
        if new_page == back_page:
            return url_for(new_page,
                           filename=filename,
                           node_id=dt_node_id)
        elif new_page == PAGE_ATTRIBUTE_DATETIME:
            # dateTime doesn't need to pass mscale value
            return url_for(new_page,
                           filename=filename,
                           dt_node_id=dt_node_id,
                           node_id=node_id)
        elif new_page in (
                PAGE_ATTRIBUTE_SELECT,
                PAGE_ATTRIBUTE_DATETIME,
                PAGE_ATTRIBUTE_NUMERICAL,
                PAGE_ATTRIBUTE_CATEGORICAL,
                PAGE_ATTRIBUTE_TEXT,
                PAGE_ATTRIBUTE_MEASUREMENT_SCALE
        ):
            # other attribute measurement scales need to pass mscale value
            url = url_for(new_page,
                          filename=filename,
                          dt_node_id=dt_node_id,
                          node_id=node_id,
                          mscale=mscale)
            return url
        else:
            # this_page
            return url_for(new_page,
                           filename=filename,
                           dt_node_id=dt_node_id)


@dt_bp.route('/attribute_dateTime/<filename>/<dt_node_id>/<node_id>', methods=['GET', 'POST'])
def attribute_dateTime(filename=None, dt_node_id=None, node_id=None):
    form = AttributeDateTimeForm(filename=filename, node_id=node_id)
    att_node_id = node_id

    if request.method == 'POST' and BTN_CANCEL in request.form:
        url = url_for(PAGE_ATTRIBUTE_SELECT, filename=filename, dt_node_id=dt_node_id, node_id=att_node_id)
        return redirect(url)

    # Determine POST type
    if request.method == 'POST' and form.validate_on_submit():

        if is_dirty_form(form):
            submit_type = 'Save Changes'
            # flash(f"is_dirty_form: True")
        else:
            submit_type = 'Back'
            # flash(f"is_dirty_form: False")

        # Go back to data table or go to the appropriate measurement scale page
        if BTN_DONE in request.form:
            next_page = PAGE_ATTRIBUTE_SELECT
        elif BTN_HIDDEN_NEW in request.form:
            next_page = PAGE_CREATE
        elif BTN_HIDDEN_OPEN in request.form:
            next_page = PAGE_OPEN
        elif BTN_HIDDEN_CLOSE in request.form:
            next_page = PAGE_CLOSE

        if submit_type == 'Save Changes':
            dt_node = None
            attribute_list_node = None
            eml_node = load_eml(filename=filename)
            dataset_node = eml_node.find_child(names.DATASET)
            if not dataset_node:
                dataset_node = Node(names.DATASET, parent=eml_node)
            else:
                data_table_nodes = dataset_node.find_all_children(names.DATATABLE)
                if data_table_nodes:
                    for data_table_node in data_table_nodes:
                        if data_table_node.id == dt_node_id:
                            dt_node = data_table_node
                            break

            if not dt_node:
                dt_node = Node(names.DATATABLE, parent=dataset_node)
                add_child(dataset_node, dt_node)

            attribute_list_node = dt_node.find_child(names.ATTRIBUTELIST)
            if not attribute_list_node:
                attribute_list_node = Node(names.ATTRIBUTELIST, parent=dt_node)
                add_child(dt_node, attribute_list_node)

            attribute_name = form.attribute_name.data
            attribute_label = form.attribute_label.data
            attribute_definition = form.attribute_definition.data
            storage_type = form.storage_type.data
            storage_type_system = form.storage_type_system.data
            format_string = form.format_string.data
            datetime_precision = form.datetime_precision.data
            bounds_minimum = form.bounds_minimum.data
            bounds_minimum_exclusive = form.bounds_minimum_exclusive.data
            bounds_maximum = form.bounds_maximum.data
            bounds_maximum_exclusive = form.bounds_maximum_exclusive.data

            code_dict = {}

            code_1 = form.code_1.data
            code_explanation_1 = form.code_explanation_1.data
            if code_1:
                code_dict[code_1] = code_explanation_1

            code_2 = form.code_2.data
            code_explanation_2 = form.code_explanation_2.data
            if code_2:
                code_dict[code_2] = code_explanation_2

            code_3 = form.code_3.data
            code_explanation_3 = form.code_explanation_3.data
            if code_3:
                code_dict[code_3] = code_explanation_3

            att_node = Node(names.ATTRIBUTE, parent=attribute_list_node)

            create_datetime_attribute(
                att_node,
                attribute_name,
                attribute_label,
                attribute_definition,
                storage_type,
                storage_type_system,
                format_string,
                datetime_precision,
                bounds_minimum,
                bounds_minimum_exclusive,
                bounds_maximum,
                bounds_maximum_exclusive,
                code_dict)

            if node_id and len(node_id) != 1:
                old_att_node = Node.get_node_instance(att_node_id)
                if old_att_node:
                    att_parent_node = old_att_node.parent
                    att_parent_node.replace_child(old_att_node, att_node)
                else:
                    msg = f"No node found in the node store with node id {node_id}"
                    raise Exception(msg)
            else:
                add_child(attribute_list_node, att_node)

            save_both_formats(filename=filename, eml_node=eml_node)
            att_node_id = att_node.id

        url = url_for(next_page, filename=filename,
                      dt_node_id=dt_node_id, node_id=att_node_id)

        return redirect(url)

    # Process GET
    if node_id == '1':
        form.init_md5()
        # form.md5.data = form_md5(form)
    else:
        eml_node = load_eml(filename=filename)
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            dt_nodes = dataset_node.find_all_children(names.DATATABLE)
            if dt_nodes:
                for dt_node in dt_nodes:
                    if dt_node_id == dt_node.id:
                        attribute_list_node = dt_node.find_child(names.ATTRIBUTELIST)
                        if attribute_list_node:
                            att_nodes = attribute_list_node.find_all_children(names.ATTRIBUTE)
                            if att_nodes:
                                for att_node in att_nodes:
                                    if node_id == att_node.id:
                                        populate_attribute_datetime_form(form, att_node)
                                        break

    set_current_page('data_table')
    help = get_helps(['attribute_name', 'attribute_definition', 'attribute_label', 'attribute_storage_type',
                      'attribute_datetime_precision', 'attribute_datetime_format'])
    return render_template('attribute_datetime.html', title='Attribute', form=form, help=help)


def populate_attribute_datetime_form(form: AttributeDateTimeForm, node: Node):
    att_node = node

    attribute_name_node = node.find_child(names.ATTRIBUTENAME)
    if attribute_name_node:
        form.attribute_name.data = attribute_name_node.content

    attribute_label_node = node.find_child(names.ATTRIBUTELABEL)
    if attribute_label_node:
        form.attribute_label.data = attribute_label_node.content

    attribute_definition_node = node.find_child(names.ATTRIBUTEDEFINITION)
    if attribute_definition_node:
        form.attribute_definition.data = attribute_definition_node.content

    storage_type_node = node.find_child(names.STORAGETYPE)
    if storage_type_node:
        form.storage_type.data = storage_type_node.content
        storage_type_system_att = storage_type_node.attribute_value('typeSystem')
        if storage_type_system_att:
            form.storage_type_system.data = storage_type_system_att
    else:
        form.storage_type.data = 'dateTime'
        form.storage_type_system.data = 'XML Schema Datatypes'

    mscale_node = att_node.find_child(names.MEASUREMENTSCALE)

    if mscale_node:
        datetime_node = mscale_node.find_child(names.DATETIME)

        if datetime_node:
            format_string_node = datetime_node.find_child(names.FORMATSTRING)

            if format_string_node:
                form.format_string.data = format_string_node.content

            datetime_precision_node = datetime_node.find_child(names.DATETIMEPRECISION)
            if datetime_precision_node:
                form.datetime_precision.data = datetime_precision_node.content

            datetime_domain_node = datetime_node.find_child(names.DATETIMEDOMAIN)
            if datetime_domain_node:
                bounds_node = datetime_domain_node.find_child(names.BOUNDS)
                if bounds_node:
                    minimum_node = bounds_node.find_child(names.MINIMUM)
                    if minimum_node:
                        form.bounds_minimum.data = minimum_node.content
                        exclusive = minimum_node.attribute_value('exclusive')
                        if exclusive and exclusive.lower() == 'true':
                            form.bounds_minimum_exclusive.data = True
                        else:
                            form.bounds_minimum_exclusive.data = False
                    maximum_node = bounds_node.find_child(names.MAXIMUM)
                    if maximum_node:
                        form.bounds_maximum.data = maximum_node.content
                        exclusive = maximum_node.attribute_value('exclusive')
                        if exclusive and exclusive.lower() == 'true':
                            form.bounds_maximum_exclusive.data = True
                        else:
                            form.bounds_maximum_exclusive.data = False
    mvc_nodes = node.find_all_children(names.MISSINGVALUECODE)
    if mvc_nodes and len(mvc_nodes) > 0:
        i = 1
        for mvc_node in mvc_nodes:
            code = ''
            code_explanation = ''
            code_node = mvc_node.find_child(names.CODE)
            code_explanation_node = mvc_node.find_child(names.CODEEXPLANATION)
            if code_node:
                code = code_node.content
            if code_explanation_node:
                code_explanation = code_explanation_node.content
            if i == 1:
                form.code_1.data = code
                form.code_explanation_1.data = code_explanation
            elif i == 2:
                form.code_2.data = code
                form.code_explanation_2.data = code_explanation
            elif i == 3:
                form.code_3.data = code
                form.code_explanation_3.data = code_explanation
            i += 1

    form.md5.data = form_md5(form)


@dt_bp.route('/attribute_numerical/<filename>/<dt_node_id>/<node_id>/<mscale>', methods=['GET', 'POST'])
def attribute_numerical(filename=None, dt_node_id=None, node_id=None, mscale=None):
    form = AttributeIntervalRatioForm(filename=filename, node_id=node_id)
    att_node_id = node_id

    if request.method == 'POST' and BTN_CANCEL in request.form:
        url = url_for(PAGE_ATTRIBUTE_SELECT, filename=filename, dt_node_id=dt_node_id, node_id=att_node_id)
        return redirect(url)

    # Determine POST type
    # if request.method == 'POST' and form.validate_on_submit():
    if request.method == 'POST':

        if is_dirty_form(form):
            submit_type = 'Save Changes'
            # flash(f"is_dirty_form: True")
        else:
            submit_type = 'Back'
            # flash(f"is_dirty_form: False")

        # Go back to data table or go to the appropriate measurement scale page
        if BTN_DONE in request.form:  # FIXME
            next_page = PAGE_ATTRIBUTE_SELECT
        elif BTN_HIDDEN_NEW in request.form:
            next_page = PAGE_CREATE
        elif BTN_HIDDEN_OPEN in request.form:
            next_page = PAGE_OPEN
        elif BTN_HIDDEN_CLOSE in request.form:
            next_page = PAGE_CLOSE

        if submit_type == 'Save Changes':
            dt_node = None
            attribute_list_node = None
            eml_node = load_eml(filename=filename)
            dataset_node = eml_node.find_child(names.DATASET)
            if not dataset_node:
                dataset_node = Node(names.DATASET, parent=eml_node)
            else:
                data_table_nodes = dataset_node.find_all_children(names.DATATABLE)
                if data_table_nodes:
                    for data_table_node in data_table_nodes:
                        if data_table_node.id == dt_node_id:
                            dt_node = data_table_node
                            break

            if not dt_node:
                dt_node = Node(names.DATATABLE, parent=dataset_node)
                add_child(dataset_node, dt_node)

            attribute_list_node = dt_node.find_child(names.ATTRIBUTELIST)
            if not attribute_list_node:
                attribute_list_node = Node(names.ATTRIBUTELIST, parent=dt_node)
                add_child(dt_node, attribute_list_node)

            # mscale_choice = form.mscale_choice.data
            attribute_name = form.attribute_name.data
            attribute_label = form.attribute_label.data
            attribute_definition = form.attribute_definition.data
            storage_type = form.storage_type.data
            storage_type_system = form.storage_type_system.data
            standard_unit = form.standard_unit.data
            custom_unit = form.custom_unit.data
            custom_unit_definition = form.custom_unit_description.data
            precision = form.precision.data
            number_type = form.number_type.data
            bounds_minimum = form.bounds_minimum.data
            bounds_minimum_exclusive = form.bounds_minimum_exclusive.data
            bounds_maximum = form.bounds_maximum.data
            bounds_maximum_exclusive = form.bounds_maximum_exclusive.data

            code_dict = {}

            code_1 = form.code_1.data
            code_explanation_1 = form.code_explanation_1.data
            if code_1:
                code_dict[code_1] = code_explanation_1

            code_2 = form.code_2.data
            code_explanation_2 = form.code_explanation_2.data
            if code_2:
                code_dict[code_2] = code_explanation_2

            code_3 = form.code_3.data
            code_explanation_3 = form.code_explanation_3.data
            if code_3:
                code_dict[code_3] = code_explanation_3

            att_node = Node(names.ATTRIBUTE, parent=attribute_list_node)

            create_numerical_attribute(
                eml_node,
                att_node,
                attribute_name,
                attribute_label,
                attribute_definition,
                storage_type,
                storage_type_system,
                standard_unit,
                custom_unit,
                custom_unit_definition,
                precision,
                number_type,
                bounds_minimum,
                bounds_minimum_exclusive,
                bounds_maximum,
                bounds_maximum_exclusive,
                code_dict,
                mscale)

            if node_id and len(node_id) != 1:
                old_att_node = Node.get_node_instance(att_node_id)
                if old_att_node:
                    att_parent_node = old_att_node.parent
                    att_parent_node.replace_child(old_att_node, att_node)
                else:
                    msg = f"No node found in the node store with node id {node_id}"
                    raise Exception(msg)
            else:
                add_child(attribute_list_node, att_node)

            save_both_formats(filename=filename, eml_node=eml_node)
            att_node_id = att_node.id

        url = url_for(next_page, filename=filename,
                      dt_node_id=dt_node_id, node_id=att_node_id)

        return redirect(url)

    # Process GET
    attribute_name = ''
    if node_id == '1':
        form.init_md5()
        # form_str = mscale + form.init_str
        # form.md5.data = hashlib.md5(form_str.encode('utf-8')).hexdigest()
        # form.mscale_choice.data = mscale
    else:
        eml_node = load_eml(filename=filename)
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            dt_nodes = dataset_node.find_all_children(names.DATATABLE)
            if dt_nodes:
                for dt_node in dt_nodes:
                    if dt_node_id == dt_node.id:
                        attribute_list_node = dt_node.find_child(names.ATTRIBUTELIST)
                        if attribute_list_node:
                            att_nodes = attribute_list_node.find_all_children(names.ATTRIBUTE)
                            if att_nodes:
                                for att_node in att_nodes:
                                    if node_id == att_node.id:
                                        populate_attribute_numerical_form(form, eml_node, att_node, mscale)
                                        attribute_name = attribute_name_from_attribute(att_node)
                                        break

    set_current_page('data_table')
    custom_unit_names = []
    custom_unit_descriptions = []
    if 'custom_units' in session:
        for name, desc in session['custom_units'].items():
            custom_unit_names.append(name)
            custom_unit_descriptions.append(desc)
    help = get_helps(['attribute_name', 'attribute_definition', 'attribute_label', 'attribute_storage_type',
                      'attribute_number_type', 'attribute_numerical_precision'])
    return render_template('attribute_numerical.html',
                           title='Attribute: Numerical',
                           form=form,
                           attribute_name=attribute_name,
                           mscale=mscale,
                           custom_unit_names=custom_unit_names,
                           custom_unit_descriptions=custom_unit_descriptions,
                           help=help)


def populate_attribute_numerical_form(form: AttributeIntervalRatioForm = None, eml_node: Node = None, att_node: Node = None,
                                           mscale: str = None):
    # if mscale is not None:
    #     if mscale == names.INTERVAL:
    #         form.mscale_choice.data = names.INTERVAL
    #     elif mscale == names.RATIO:
    #         form.mscale_choice.data = names.RATIO

    attribute_name_node = att_node.find_child(names.ATTRIBUTENAME)
    if attribute_name_node:
        form.attribute_name.data = attribute_name_node.content

    attribute_label_node = att_node.find_child(names.ATTRIBUTELABEL)
    if attribute_label_node:
        form.attribute_label.data = attribute_label_node.content

    attribute_definition_node = att_node.find_child(names.ATTRIBUTEDEFINITION)
    if attribute_definition_node:
        form.attribute_definition.data = attribute_definition_node.content

    storage_type_node = att_node.find_child(names.STORAGETYPE)
    if storage_type_node:
        form.storage_type.data = storage_type_node.content
        storage_type_system_att = storage_type_node.attribute_value('typeSystem')
        if storage_type_system_att:
            form.storage_type_system.data = storage_type_system_att
    else:
        form.storage_type.data = 'float'
        form.storage_type_system.data = 'XML Schema Datatypes'

    if mscale:
        form.mscale.data = mscale

    mscale_node = att_node.find_child(names.MEASUREMENTSCALE)
    if mscale_node:
        ratio_node = mscale_node.find_child(names.RATIO)
        interval_node = mscale_node.find_child(names.INTERVAL)

        ir_node = ratio_node
        if not ir_node:
            ir_node = interval_node

        if ir_node:
            unit_node = ir_node.find_child(names.UNIT)

            if unit_node:
                standard_unit_node = unit_node.find_child(names.STANDARDUNIT)
                if standard_unit_node:
                    form.standard_unit.data = standard_unit_node.content
                custom_unit_node = unit_node.find_child(names.CUSTOMUNIT)
                if custom_unit_node:
                    custom_unit_name = custom_unit_node.content
                    form.custom_unit.data = custom_unit_name
                    # get description, if any, from the additionaMetadata section
                    additional_metadata_node = eml_node.find_child(names.ADDITIONALMETADATA)
                    if additional_metadata_node:
                        metadata_node = additional_metadata_node.find_child(names.METADATA)
                        if metadata_node:
                            unit_list_node = metadata_node.find_child(names.UNITLIST)
                            if unit_list_node:
                                unit_nodes = unit_list_node.find_all_children(names.UNIT)
                                unit_node = None
                                for node in unit_nodes:
                                    if node.attribute_value('name') == custom_unit_name:
                                        unit_node = node
                                        break
                                if unit_node:
                                    description_node = unit_node.find_child(names.DESCRIPTION)
                                    if description_node:
                                        form.custom_unit_description.data = description_node.content

            precision_node = ir_node.find_child(names.PRECISION)
            if precision_node:
                form.precision.data = precision_node.content

            numeric_domain_node = ir_node.find_child(names.NUMERICDOMAIN)
            if numeric_domain_node:
                number_type_node = numeric_domain_node.find_child(names.NUMBERTYPE)
                if number_type_node:
                    form.number_type.data = number_type_node.content
                bounds_node = numeric_domain_node.find_child(names.BOUNDS)
                if bounds_node:
                    minimum_node = bounds_node.find_child(names.MINIMUM)
                    if minimum_node:
                        form.bounds_minimum.data = minimum_node.content
                        exclusive = minimum_node.attribute_value('exclusive')
                        if exclusive and exclusive.lower() == 'true':
                            form.bounds_minimum_exclusive.data = True
                        else:
                            form.bounds_minimum_exclusive.data = False
                    maximum_node = bounds_node.find_child(names.MAXIMUM)
                    if maximum_node:
                        form.bounds_maximum.data = maximum_node.content
                        exclusive = maximum_node.attribute_value('exclusive')
                        if exclusive and exclusive.lower() == 'true':
                            form.bounds_maximum_exclusive.data = True
                        else:
                            form.bounds_maximum_exclusive.data = False
    mvc_nodes = att_node.find_all_children(names.MISSINGVALUECODE)
    if mvc_nodes and len(mvc_nodes) > 0:
        i = 1
        for mvc_node in mvc_nodes:
            code = ''
            code_explanation = ''
            code_node = mvc_node.find_child(names.CODE)
            code_explanation_node = mvc_node.find_child(names.CODEEXPLANATION)
            if code_node:
                code = code_node.content
            if code_explanation_node:
                code_explanation = code_explanation_node.content
            if i == 1:
                form.code_1.data = code
                form.code_explanation_1.data = code_explanation
            elif i == 2:
                form.code_2.data = code
                form.code_explanation_2.data = code_explanation
            elif i == 3:
                form.code_3.data = code
                form.code_explanation_3.data = code_explanation
            i += 1

    form.md5.data = form_md5(form)


@dt_bp.route('/attribute_text/<filename>/<dt_node_id>/<node_id>/<mscale>', methods=['GET', 'POST'])
def attribute_text(filename: str = None, dt_node_id: str = None, node_id: str = None, mscale: str = None):
    return attribute_categorical(filename, dt_node_id, node_id, mscale)


@dt_bp.route('/attribute_categorical/<filename>/<dt_node_id>/<node_id>/<mscale>', methods=['GET', 'POST'])
def attribute_categorical(filename: str = None, dt_node_id: str = None, node_id: str = None, mscale: str = None):
    if mscale == 'TEXT':
        form = AttributeTextForm(filename=filename, node_id=node_id)
    else:
        form = AttributeCategoricalForm(filename=filename, node_id=node_id)
    att_node_id = node_id

    if request.method == 'POST' and BTN_CANCEL in request.form:
        url = url_for(PAGE_ATTRIBUTE_SELECT, filename=filename, dt_node_id=dt_node_id, node_id=att_node_id)
        return redirect(url)

    # Determine POST type
    # if request.method == 'POST' and form.validate_on_submit():
    if request.method == 'POST':

        if is_dirty_form(form):
            submit_type = 'Save Changes'
            # flash(f"is_dirty_form: True")
        else:
            submit_type = 'Back'
            # flash(f"is_dirty_form: False")

        # Go back to data table or go to the appropriate measurement scale page
        if BTN_DONE in request.form:
            next_page = PAGE_ATTRIBUTE_SELECT  # FIXME
        elif 'Codes' in request.form:
            next_page = PAGE_CODE_DEFINITION_SELECT
        elif BTN_HIDDEN_NEW in request.form:
            next_page = PAGE_CREATE
        elif BTN_HIDDEN_OPEN in request.form:
            next_page = PAGE_OPEN
        elif BTN_HIDDEN_CLOSE in request.form:
            next_page = PAGE_CLOSE

        if submit_type == 'Save Changes':
            dt_node = None
            attribute_list_node = None
            eml_node = load_eml(filename=filename)
            dataset_node = eml_node.find_child(names.DATASET)
            if not dataset_node:
                dataset_node = Node(names.DATASET, parent=eml_node)
            else:
                data_table_nodes = dataset_node.find_all_children(names.DATATABLE)
                if data_table_nodes:
                    for data_table_node in data_table_nodes:
                        if data_table_node.id == dt_node_id:
                            dt_node = data_table_node
                            break

            if not dt_node:
                dt_node = Node(names.DATATABLE, parent=dataset_node)
                add_child(dataset_node, dt_node)

            attribute_list_node = dt_node.find_child(names.ATTRIBUTELIST)
            if not attribute_list_node:
                attribute_list_node = Node(names.ATTRIBUTELIST, parent=dt_node)
                add_child(dt_node, attribute_list_node)

            attribute_name = form.attribute_name.data
            attribute_label = form.attribute_label.data
            attribute_definition = form.attribute_definition.data
            storage_type = form.storage_type.data
            storage_type_system = form.storage_type_system.data
            enumerated_domain_node = None
            if mscale == VariableType.CATEGORICAL.name:
                # we need to hang onto the categorical codes
                att_node = Node.get_node_instance(att_node_id)
                if att_node:
                    enumerated_domain_node = att_node.find_descendant(names.ENUMERATEDDOMAIN)

                enforced = form.enforced.data
            else:
                enforced = None

            code_dict = {}

            code_1 = form.code_1.data
            code_explanation_1 = form.code_explanation_1.data
            if code_1:
                code_dict[code_1] = code_explanation_1

            code_2 = form.code_2.data
            code_explanation_2 = form.code_explanation_2.data
            if code_2:
                code_dict[code_2] = code_explanation_2

            code_3 = form.code_3.data
            code_explanation_3 = form.code_explanation_3.data
            if code_3:
                code_dict[code_3] = code_explanation_3

            att_node = Node(names.ATTRIBUTE, parent=attribute_list_node)

            create_categorical_or_text_attribute(
                att_node,
                attribute_name,
                attribute_label,
                attribute_definition,
                storage_type,
                storage_type_system,
                enforced,
                code_dict,
                mscale,
                enumerated_domain_node)

            if node_id and len(node_id) != 1:
                old_att_node = Node.get_node_instance(att_node_id)
                if old_att_node:
                    att_parent_node = old_att_node.parent
                    att_parent_node.replace_child(old_att_node, att_node)
                else:
                    msg = f"No node found in the node store with node id {node_id}"
                    raise Exception(msg)
            else:
                add_child(attribute_list_node, att_node)

            save_both_formats(filename=filename, eml_node=eml_node)
            att_node_id = att_node.id

        if next_page == PAGE_CODE_DEFINITION_SELECT:
            cd_node = None
            if att_node_id != '1':
                att_node = Node.get_node_instance(att_node_id)
                cd_node = code_definition_from_attribute(att_node)  # FIXME - What's going on here??? Only one node returned...

            if not cd_node:
                cd_node = Node(names.CODEDEFINITION, parent=None)

            cd_node_id = cd_node.id
            url = url_for(next_page, filename=filename, dt_node_id=dt_node_id, att_node_id=att_node_id,
                          node_id=cd_node_id, mscale=mscale)
        else:
            url = url_for(next_page, filename=filename, dt_node_id=dt_node_id, node_id=att_node_id)

        return redirect(url)

    # Process GET
    attribute_name = ''
    codes = 'No codes have been defined yet'
    if node_id == '1':
        form.init_md5()
        # form_str = mscale + form.init_str
        # form.md5.data = hashlib.md5(form_str.encode('utf-8')).hexdigest()
        # form.mscale_choice.data = mscale
    else:
        eml_node = load_eml(filename=filename)
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            dt_nodes = dataset_node.find_all_children(names.DATATABLE)
            if dt_nodes:
                for dt_node in dt_nodes:
                    if dt_node_id == dt_node.id:
                        attribute_list_node = dt_node.find_child(names.ATTRIBUTELIST)
                        if attribute_list_node:
                            att_nodes = attribute_list_node.find_all_children(names.ATTRIBUTE)
                            if att_nodes:
                                for att_node in att_nodes:
                                    if node_id == att_node.id:
                                        codes = populate_attribute_categorical_form(form, att_node, mscale)
                                        attribute_name = attribute_name_from_attribute(att_node)
                                        break

    # if mscale
    set_current_page('data_table')
    help = get_helps(['attribute_name', 'attribute_definition', 'attribute_label', 'attribute_storage_type'])
    if mscale == VariableType.CATEGORICAL.name:
        return render_template('attribute_categorical.html',
                               title='Categorical Attribute',
                               form=form,
                               attribute_name=attribute_name,
                               mscale=mscale,
                               codes=codes,
                               help=help)
    else:
        return render_template('attribute_text.html',
                               title='Text Attribute',
                               form=form,
                               attribute_name=attribute_name,
                               mscale=mscale,
                               help=help)


def populate_attribute_categorical_form(form: AttributeCategoricalForm, att_node: Node = None,
                                            mscale: str = None):
    # if mscale is not None:
    #     if mscale == names.NOMINAL:
    #         form.mscale_choice.data = names.NOMINAL
    #     elif mscale == names.ORDINAL:
    #         form.mscale_choice.data = names.ORDINAL

    attribute_name_node = att_node.find_child(names.ATTRIBUTENAME)
    if attribute_name_node:
        form.attribute_name.data = attribute_name_node.content

    attribute_label_node = att_node.find_child(names.ATTRIBUTELABEL)
    if attribute_label_node:
        form.attribute_label.data = attribute_label_node.content

    attribute_definition_node = att_node.find_child(names.ATTRIBUTEDEFINITION)
    if attribute_definition_node:
        form.attribute_definition.data = attribute_definition_node.content

    storage_type_node = att_node.find_child(names.STORAGETYPE)
    if storage_type_node:
        form.storage_type.data = storage_type_node.content
        storage_type_system_att = storage_type_node.attribute_value('typeSystem')
        if storage_type_system_att:
            form.storage_type_system.data = storage_type_system_att
    else:
        form.storage_type.data = 'string'
        form.storage_type_system.data = 'XML Schema Datatypes'

    if mscale:
        form.mscale.data = mscale

    mscale_node = att_node.find_child(names.MEASUREMENTSCALE)

    codes = ''
    if mscale_node:
        node = mscale_node.find_child(names.NOMINAL)
        if not node:
            node = mscale_node.find_child(names.ORDINAL)

        if node:
            if mscale == VariableType.CATEGORICAL.name:
                code_entries = list_codes_and_definitions(att_node)
                if code_entries and len(code_entries) > 0:
                    code_list = []
                    for code_entry in code_entries:
                        code_list.append(str(code_entry.code))
                    codes = ', '.join(code_list)
                else:
                    codes = 'No codes have been defined yet'
                enumerated_domain_node = node.find_single_node_by_path([
                    names.NONNUMERICDOMAIN,
                    names.ENUMERATEDDOMAIN
                ])
                if enumerated_domain_node:
                    enforced = enumerated_domain_node.attribute_value('enforced')
                    if enforced and enforced.upper() == 'NO':
                        form.enforced.data = 'no'
                    else:
                        form.enforced.data = 'yes'
            # elif mscale == VariableType.TEXT.name:
            #     text_domain_node = node.find_child(names.TEXTDOMAIN)

    mvc_nodes = att_node.find_all_children(names.MISSINGVALUECODE)
    if mvc_nodes and len(mvc_nodes) > 0:
        i = 1
        for mvc_node in mvc_nodes:
            code = ''
            code_explanation = ''
            code_node = mvc_node.find_child(names.CODE)
            code_explanation_node = mvc_node.find_child(names.CODEEXPLANATION)
            if code_node:
                code = code_node.content
            if code_explanation_node:
                code_explanation = code_explanation_node.content
            if i == 1:
                form.code_1.data = code
                form.code_explanation_1.data = code_explanation
            elif i == 2:
                form.code_2.data = code
                form.code_explanation_2.data = code_explanation
            elif i == 3:
                form.code_3.data = code
                form.code_explanation_3.data = code_explanation
            i = i + 1

    form.md5.data = form_md5(form)
    return codes


# <node_id> identifies the nominal or ordinal node that this code definition
# is a part of
#
@dt_bp.route('/code_definition_select/<filename>/<dt_node_id>/<att_node_id>/<node_id>/<mscale>',
             methods=['GET', 'POST'])
def code_definition_select(filename=None, dt_node_id=None, att_node_id=None, node_id=None, mscale=None):
    nom_ord_node_id = node_id
    form = CodeDefinitionSelectForm(filename=filename)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = code_definition_select_post(filename=filename,
                                          form=form,
                                          form_dict=form_dict,
                                          method='POST',
                                          this_page=PAGE_CODE_DEFINITION_SELECT,
                                          back_page=PAGE_ATTRIBUTE_CATEGORICAL,
                                          edit_page=PAGE_CODE_DEFINITION,
                                          dt_node_id=dt_node_id,
                                          att_node_id=att_node_id,
                                          nom_ord_node_id=nom_ord_node_id,
                                          mscale=mscale)
        return redirect(url)

    # Process GET
    codes_list = []
    title = 'Code Definitions'
    attribute_name = ''
    load_eml(filename=filename)

    att_node = Node.get_node_instance(att_node_id)
    if att_node:
        attribute_name = attribute_name_from_attribute(att_node)
        codes_list = list_codes_and_definitions(att_node)
    set_current_page('data_table')
    return render_template('code_definition_select.html', title=title,
                           attribute_name=attribute_name, codes_list=codes_list,
                           form=form)


def code_definition_select_post(filename=None,
                                form=None,
                                form_dict=None,
                                method=None,
                                this_page=None,
                                back_page=None,
                                edit_page=None,
                                dt_node_id=None,
                                att_node_id=None,
                                nom_ord_node_id=None,
                                mscale=None):
    node_id = ''
    new_page = ''

    if not mscale:
        att_node = Node.get_node_instance(att_node_id)
        if att_node:
            mscale = mscale_from_attribute(att_node)

    if form_dict:
        for key in form_dict:
            val = form_dict[key][0]  # value is the first list element
            if val[0:4] == 'Back':
                new_page = back_page
            elif val == 'Edit':
                new_page = edit_page
                node_id = key
            elif val == 'Remove':
                new_page = this_page
                node_id = key
                eml_node = load_eml(filename=filename)
                remove_child(node_id=node_id)
                save_both_formats(filename=filename, eml_node=eml_node)
            elif val == UP_ARROW:
                new_page = this_page
                node_id = key
                process_up_button(filename, node_id)
            elif val == DOWN_ARROW:
                new_page = this_page
                node_id = key
                process_down_button(filename, node_id)
            elif val == BTN_HIDDEN_CHECK:
                new_page = PAGE_CHECK
            elif val == BTN_HIDDEN_SAVE:
                new_page = this_page
            elif val == BTN_HIDDEN_DOWNLOAD:
                new_page = PAGE_DOWNLOAD
            elif val == BTN_HIDDEN_NEW:
                new_page = PAGE_CREATE
            elif val == BTN_HIDDEN_OPEN:
                new_page = PAGE_OPEN
            elif val == BTN_HIDDEN_CLOSE:
                new_page = PAGE_CLOSE
            elif val[0:3] == 'Add':
                new_page = edit_page
                node_id = '1'
            elif val == '[  ]':
                new_page = this_page
                node_id = key

    if form.validate_on_submit():
        if new_page == back_page:  # attribute_nominal_ordinal
            return url_for(new_page, filename=filename, dt_node_id=dt_node_id, node_id=att_node_id, mscale=mscale)
        elif new_page == this_page:  # code_definition_select_post
            return url_for(new_page,
                           filename=filename,
                           dt_node_id=dt_node_id,
                           att_node_id=att_node_id,
                           node_id=node_id,
                           mscale=mscale)
        elif new_page == edit_page:  # code_definition
            return url_for(new_page,
                           filename=filename,
                           dt_node_id=dt_node_id,
                           att_node_id=att_node_id,
                           nom_ord_node_id=nom_ord_node_id,
                           node_id=node_id,
                           mscale=mscale)
        else:
            return url_for(new_page,
                           filename=filename,
                           dt_node_id=dt_node_id)


# node_id is the id of the codeDefinition node being edited. If the value
# '1', it means we are adding a new codeDefinition node, otherwise we are
# editing an existing one.
#
@dt_bp.route('/code_definition/<filename>/<dt_node_id>/<att_node_id>/<nom_ord_node_id>/<node_id>/<mscale>',
             methods=['GET', 'POST'])
def code_definition(filename=None, dt_node_id=None, att_node_id=None, nom_ord_node_id=None, node_id=None, mscale=None):
    eml_node = load_eml(filename=filename)
    att_node = Node.get_node_instance(att_node_id)
    cd_node_id = node_id
    attribute_name = 'Attribute Name'
    if att_node:
        attribute_name = attribute_name_from_attribute(att_node)
        if not mscale:
            mscale = mscale_from_attribute(att_node)
    form = CodeDefinitionForm(filename=filename, node_id=node_id, attribute_name=attribute_name)

    # Process POST
    if request.method == 'POST' and BTN_CANCEL in request.form:
        url = url_for(PAGE_CODE_DEFINITION_SELECT,
                      filename=filename,
                      dt_node_id=dt_node_id,
                      att_node_id=att_node_id,
                      node_id=nom_ord_node_id,
                      mscale=mscale)
        return redirect(url)

    if request.method == 'POST' and form.validate_on_submit():
        next_page = PAGE_CODE_DEFINITION_SELECT  # Save or Back sends us back to the list of attributes

        if BTN_HIDDEN_NEW in request.form:
            next_page = PAGE_CREATE
        elif BTN_HIDDEN_OPEN in request.form:
            next_page = PAGE_OPEN
        elif BTN_HIDDEN_CLOSE in request.form:
            next_page = PAGE_CLOSE

        # if 'Back' in request.form:
        if is_dirty_form(form):
            submit_type = 'Save Changes'
        else:
            submit_type = 'Back'
        # flash(f'submit_type: {submit_type}')

        if submit_type == 'Save Changes':
            if att_node:
                measurement_scale_node = att_node.find_child(names.MEASUREMENTSCALE)
                if not measurement_scale_node:
                    measurement_scale_node = Node(names.MEASUREMENTSCALE, parent=att_node)
                    add_child(att_node, measurement_scale_node)

                nominal_ordinal_node = measurement_scale_node.find_child(names.NOMINAL)
                if not nominal_ordinal_node:
                    nominal_ordinal_node = measurement_scale_node.find_child(names.ORDINAL)
                    if not nominal_ordinal_node:
                        if mscale == names.NOMINAL:
                            nominal_ordinal_node = Node(names.NOMINAL, parent=measurement_scale_node)
                            add_child(measurement_scale_node, nominal_ordinal_node)
                        elif mscale == names.ORDINAL:
                            nominal_ordinal_node = Node(names.ORDINAL, parent=measurement_scale_node)
                            add_child(measurement_scale_node, nominal_ordinal_node)

                nnd_node = nominal_ordinal_node.find_child(names.NONNUMERICDOMAIN)
                if not nnd_node:
                    nnd_node = Node(names.NONNUMERICDOMAIN, parent=nominal_ordinal_node)
                    add_child(nominal_ordinal_node, nnd_node)

                ed_node = nnd_node.find_child(names.ENUMERATEDDOMAIN)
                if not ed_node:
                    ed_node = Node(names.ENUMERATEDDOMAIN, parent=nnd_node)
                    add_child(nnd_node, ed_node)

                code = form.code.data
                definition = form.definition.data
                order = form.order.data
                code_definition_node = Node(names.CODEDEFINITION, parent=ed_node)
                create_code_definition(code_definition_node, code, definition, order)

                # get rid of textDomain node, if any
                text_domain_node = nnd_node.find_child(names.TEXTDOMAIN)
                if text_domain_node:
                    nnd_node.remove_child(text_domain_node)

                if cd_node_id and len(cd_node_id) != 1:
                    old_code_definition_node = Node.get_node_instance(cd_node_id)

                    if old_code_definition_node:
                        code_definition_parent_node = old_code_definition_node.parent
                        code_definition_parent_node.replace_child(old_code_definition_node,
                                                                  code_definition_node)
                    else:
                        msg = f"No codeDefinition node found in the node store with node id {node_id}"
                        raise Exception(msg)
                else:
                    add_child(ed_node, code_definition_node)
                    cd_node_id = code_definition_node.id

                save_both_formats(filename=filename, eml_node=eml_node)

        url = url_for(next_page,
                      filename=filename,
                      dt_node_id=dt_node_id,
                      att_node_id=att_node_id,
                      node_id=nom_ord_node_id,
                      mscale=mscale)
        return redirect(url)

    # Process GET
    if node_id == '1':
        form.init_md5()
    else:
        enumerated_domain_node = enumerated_domain_from_attribute(att_node)  # FIXME - Question: schema allows multiple of these
        if enumerated_domain_node:
            cd_nodes = enumerated_domain_node.find_all_children(names.CODEDEFINITION)
            if cd_nodes:
                for cd_node in cd_nodes:
                    if node_id == cd_node.id:
                        populate_code_definition_form(form, cd_node)
                        break

    set_current_page('data_table')
    return render_template('code_definition.html', title='Code Definition', form=form, attribute_name=attribute_name)


def populate_code_definition_form(form: CodeDefinitionForm, cd_node: Node):
    code = ''
    definition = ''

    if cd_node:
        code_node = cd_node.find_child(names.CODE)
        if code_node:
            code = code_node.content
        definition_node = cd_node.find_child(names.DEFINITION)
        if definition_node:
            definition = definition_node.content
        order = cd_node.attribute_value('order')
        form.code.data = code
        form.definition.data = definition
        if order:
            form.order.data = order

    form.md5.data = form_md5(form)


@dt_bp.route('/clone_attributes/<filename>/<dt_node_id>/', methods=['GET', 'POST'])
@login_required
def clone_attributes(filename, dt_node_id):
    eml_node = load_eml(filename=filename)

    target_filename = filename
    target_dt_id = dt_node_id

    form = ImportEMLForm()
    form.filename.choices = list_data_packages(True, True)

    # Process POST
    if request.method == 'POST':
        if BTN_CANCEL in request.form:
            return redirect(get_back_url())

        if form.validate_on_submit():
            source_filename = form.filename.data
            return redirect(url_for('dt.clone_attributes_2', target_filename=target_filename, target_dt_id=target_dt_id, source_filename=source_filename))

    # Process GET
    help = get_helps(['clone_attributes_1'])
    return render_template('clone_attributes.html', filename=filename, dt_id=dt_node_id, help=help, form=form)


@dt_bp.route('/clone_attributes_2/<target_filename>/<target_dt_id>/<source_filename>/', methods=['GET', 'POST'])
@login_required
def clone_attributes_2(target_filename, target_dt_id, source_filename):
    form = SelectDataTableForm()

    eml_node = load_eml(filename=target_filename)
    target_dt_node = Node.get_node_instance(target_dt_id)
    target_object_name = target_dt_node.find_descendant(names.OBJECTNAME).content

    source_eml_node = load_eml(source_filename)
    source_data_tables = list_data_tables(source_eml_node, to_skip=target_object_name)

    choices = [[data_table[0], data_table[1]] for data_table in source_data_tables]
    form.source.choices = choices
    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    if request.method == 'POST' and form.validate_on_submit():

        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        source_dt_id = form_dict['source'][0]
        help = get_helps(['clone_attributes_3'])

        source_dt_node = Node.get_node_instance(source_dt_id)
        source_dt_name_node = source_dt_node.find_descendant(names.ENTITYNAME)
        table_name_in = source_dt_name_node.content

        target_dt_node = Node.get_node_instance(target_dt_id)
        target_dt_name_node = target_dt_node.find_descendant(names.ENTITYNAME)
        table_name_out = target_dt_name_node.content

        return redirect(url_for('dt.clone_attributes_3', target_filename=target_filename, target_dt_id=target_dt_id,
                                source_filename=source_filename, source_dt_id=source_dt_id,
                                table_name_in=table_name_in, table_name_out=table_name_out,
                                help=help, form=form))

    # Process GET
    help = get_helps(['clone_attributes_2'])
    return render_template('clone_attributes_2.html', target_filename=target_filename, target_dt_id=target_dt_id, source_filename=source_filename, help=help, form=form)


@dt_bp.route('/clone_attributes_3/<target_filename>/<target_dt_id>/<source_filename>/<source_dt_id>/<table_name_in>/<table_name_out>', methods=['GET', 'POST'])
@login_required
def clone_attributes_3(target_filename, target_dt_id, source_filename, source_dt_id, table_name_in, table_name_out):
    form = SelectDataTableColumnsForm()

    source_eml_node = load_eml(source_filename)
    source_dt_node = Node.get_node_instance(source_dt_id)

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(get_back_url())

    # if request.method == 'POST' and form.validate_on_submit():
    if request.method == 'POST':

        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        source_attr_ids = form_dict.get('source', None)

        if source_attr_ids: # If no option was selected, we'll fall thru and go the GET again

            help = get_helps(['import_responsible_parties_2'])  # FIX_ME
            return redirect(url_for('dt.clone_attributes_4', target_filename=target_filename, target_dt_id=target_dt_id,
                                    source_filename=source_filename, source_dt_id=source_dt_id,
                                    table_name_in=table_name_in, table_name_out=table_name_out,
                                    source_attr_ids=source_attr_ids,
                                    help=help, form=form))

    # Process GET
    help = get_helps(['clone_attributes_3'])

    source_dt_node = Node.get_node_instance(source_dt_id)
    source_data_table_columns = list_data_table_columns(source_dt_node)

    choices = [[source_data_table_column[0], source_data_table_column[1]] for source_data_table_column in source_data_table_columns]
    form.source.choices = choices

    return render_template('clone_attributes_3.html', target_filename=target_filename, target_dt_id=target_dt_id,
                           source_filename=source_filename, source_dt_id=source_dt_id,
                           table_name_in=table_name_in, table_name_out=table_name_out,
                           help=help, form=form)


def clone_column_properties(source_table_id, source_attr_ids, target_table_id, target_attr_ids):
    for source_attr_id, target_attr_id in zip(source_attr_ids, target_attr_ids):
        source_node = Node.get_node_instance(source_attr_id)
        source_node_copy = source_node.copy()
        target_node = Node.get_node_instance(target_attr_id)
        # We want to preserve the column name
        target_name = target_node.find_descendant(names.ATTRIBUTENAME).content
        target_parent = target_node.parent
        target_parent.replace_child(target_node, source_node_copy, False)  # don't delete the target_node yet because we may need it again
        source_copy_name_node = source_node_copy.find_descendant(names.ATTRIBUTENAME)
        source_copy_name_node.content = target_name
    # Now that we're done, we can delete the nodes we've replaced
    for target_attr_id in target_attr_ids:
        Node.delete_node_instance(target_attr_id, True)


@dt_bp.route('/clone_attributes_4/<target_filename>/<target_dt_id>/<source_filename>/<source_dt_id>/<table_name_in>/<table_name_out>/<source_attr_ids>',
             methods=['GET', 'POST'])
@login_required
def clone_attributes_4(target_filename, target_dt_id, source_filename, source_dt_id, table_name_in, table_name_out, source_attr_ids):
    form = SelectDataTableColumnsForm()

    source_eml_node = load_eml(source_filename)
    source_attr_ids_list = source_attr_ids.strip('][').split(', ')
    source_attrs = []
    for source_attr_id in source_attr_ids_list:
        id = source_attr_id.replace("'", "")
        source_attr_name_node = Node.get_node_instance(id)
        source_attr_name = source_attr_name_node.content
        source_attr_node = source_attr_name_node.parent
        source_attrs.append((source_attr_name, source_attr_node.id))

    target_eml_node = load_eml(target_filename)
    target_dt_node = Node.get_node_instance(target_dt_id)
    target_attrs = []
    target_dt_attr_nodes = []
    target_dt_node.find_all_descendants(names.ATTRIBUTE, target_dt_attr_nodes)
    for target_dt_attr_node in target_dt_attr_nodes:
        target_attr_name_node = target_dt_attr_node.find_descendant(names.ATTRIBUTENAME)
        target_attrs.append((target_attr_name_node.content, target_dt_attr_node.id))

    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        # Save a backup of metadata
        backup_metadata(target_filename)
        source_attr_ids = [x[1] for x in source_attrs]
        target_attr_ids = []
        for key, val in form_dict.items():
            if key.startswith('##') and key.endswith('##') and val[0]:
                target_attr_ids.append(val[0])
        target_eml_node = load_eml(target_filename)
        clone_column_properties(source_dt_id, source_attr_ids, target_dt_id, target_attr_ids)
        save_both_formats(target_filename, target_eml_node)
        help = get_helps(['import_responsible_parties_2'])  # FIX_ME
        return redirect(url_for('dt.data_table_select', filename=target_filename))


    help = get_helps(['clone_attributes_4'])

    return render_template('clone_attributes_4.html', target_filename=target_filename, target_dt_id=target_dt_id,
                           source_filename=source_filename, source_dt_id=source_dt_id,
                           table_name_in=table_name_in, table_name_out=table_name_out,
                           source_attrs=source_attrs, target_attrs=target_attrs,
                           help=help, form=form)
