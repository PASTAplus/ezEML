"""
Routes for creating and editing data tables and their attributes.
"""

import math
import numpy as np
import os
import pandas as pd
from pathlib import Path
import uuid

from urllib.parse import unquote

from flask import (
    Blueprint, Flask, flash, render_template, redirect, request, session, url_for, current_app, send_file
)
import flask

from flask_login import (
    current_user, login_required
)

from markupsafe import Markup

import webapp.home.utils.create_nodes
import webapp.views.data_tables.load_data
from webapp.config import Config

from webapp.home import views, exceptions, check_data_table_contents, standard_units
from webapp.home.utils.hidden_buttons import is_hidden_button, handle_hidden_buttons, non_saving_hidden_buttons_decorator
from webapp.home.check_metadata import init_evaluation, format_tooltip
from webapp.home.exceptions import NodeWithGivenIdNotFound
from webapp.home.home_utils import object_name_from_data_entity
from webapp.views.data_tables.load_data import (
    cull_data_files
)

from webapp.views.data_tables.forms import (
    AttributeDateTimeForm, AttributeIntervalRatioForm,
    AttributeMeasurementScaleForm, AttributeCategoricalForm,
    AttributeSelectForm, AttributeTextForm,
    CodeDefinitionForm, CodeDefinitionSelectForm,
    DataTableForm, DataTableSelectForm, SelectDataTableForm,
    SelectDataTableColumnsForm, UploadSpreadsheetForm
)

from webapp.home.forms import (
    init_form_md5, is_dirty_form,
    LoadDataForm, OpenDocumentForm, ReloadDataForm
)

from webapp.home.metapype_client import VariableType
from webapp.home.utils.node_utils import remove_child, new_child_node, add_child, replace_node
from webapp.home.utils.hidden_buttons import is_hidden_button, handle_hidden_buttons, check_val_for_hidden_buttons
from webapp.home.utils.node_store import dump_node_store
from webapp.home.utils.load_and_save import load_eml, save_both_formats, handle_custom_unit_additional_metadata
from webapp.home.utils.lists import list_data_packages, list_data_tables, list_data_table_columns, list_attributes, \
    mscale_from_attribute, UP_ARROW, DOWN_ARROW, list_codes_and_definitions, nominal_ordinal_from_attribute
from webapp.home.utils.create_nodes import create_data_table, create_datetime_attribute, create_numerical_attribute, \
    create_categorical_or_text_attribute, create_code_definition

from webapp.home.log_usage import (
    actions,
    log_usage,
)

from metapype.eml import names
from metapype.model.node import Node

from webapp.buttons import *
from webapp.pages import *

from webapp.views.data_tables.load_data import load_data_table, sort_codes, infer_datetime_format
import webapp.views.data_tables.table_spreadsheets as table_spreadsheets

import webapp.auth.user_data as user_data
from webapp.home.views import (get_help, get_helps, reload_metadata)

dt_bp = Blueprint('dt', __name__, template_folder='templates')


def log_info(msg):
    """ Available for debugging. """
    return
    app = Flask(__name__)
    with app.app_context():
        current_app.logger.info(msg)


def log_error(msg):
    """ Available for debugging. """
    return
    app = Flask(__name__)
    with app.app_context():
        current_app.logger.error(msg)


@dt_bp.route('/data_table_download/<filename>/<dtnode_id>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def data_table_download(filename=None, dtnode_id=None):
    _ = load_eml(filename=filename)
    dtnode = Node.get_node_instance(dtnode_id)
    if not filename or not dtnode:
        return
    object_name = object_name_from_data_entity(dtnode)
    uploads_folder = user_data.get_document_uploads_folder_name()
    filepath = os.path.join(uploads_folder, object_name)
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    else:
        return redirect(url_for(PAGE_DATA_TABLE_SELECT, filename=filename))


@dt_bp.route('/data_table_select/<filename>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def data_table_select(filename=None):
    """
    Display a list of data tables in the EML document.  The user can select a data table to edit or create a new one.
    """
    form = DataTableSelectForm(filename=filename)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = views.select_post(filename, form, form_dict,
                          'POST',
                          PAGE_DATA_TABLE_SELECT,
                          PAGE_PROJECT,
                          PAGE_CREATOR_SELECT,
                          PAGE_DATA_TABLE)
        return redirect(url)

    # Process GET
    eml_node = load_eml(filename=filename)
    dt_list = list_data_tables(eml_node)
    title = 'Data Tables'

    # Get the tooltip for the status badge
    init_evaluation(eml_node, filename)
    tooltip = format_tooltip(None, 'data_tables')

    views.set_current_page('data_table')
    help = [views.get_help('data_tables'), views.get_help('add_load_data_tables'), views.get_help('data_table_reupload')]
    return render_template('data_table_select.html', title=title,
                           dt_list=dt_list, form=form, help=help, tooltip=tooltip)


@dt_bp.route('/data_table/<filename>/<dt_node_id>', methods=['GET', 'POST'])
@login_required
def data_table(filename=None, dt_node_id=None, delimiter=None, quote_char=None):
    """
    Display a data table and its attributes.  The user can edit the data table and its attributes.
    """

    def compose_atts(att_list: list = []):
        # Compose a string of attribute names for display on the data table page.
        atts = []
        if att_list:
            for att in att_list:
                atts.append(att.label if att.label else 'unnamed')
        return ', '.join(atts)

    form = DataTableForm(filename=filename)
    eml_node = load_eml(filename=filename)

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
        elif 'Save Changes' in request.form:
            next_page = PAGE_DATA_TABLE
        elif 'Temporal' in request.form:
            next_page = PAGE_ENTITY_TEMPORAL_COVERAGE_SELECT
        elif 'Taxonomic' in request.form:
            next_page = PAGE_ENTITY_TAXONOMIC_COVERAGE_SELECT

        # If we have a hidden button, we note that fact but we may need to save changes before going there.
        next_page = handle_hidden_buttons(next_page)

    if form.validate_on_submit():
        if submit_type == 'Save Changes':
            # Make sure we have a dataset node
            dataset_node = eml_node.find_child(names.DATASET)
            if not dataset_node:
                dataset_node = Node(names.DATASET)

            # Collect the form values for saving in the metadata
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

            # Allocate a new data table node
            dt_node = Node(names.DATATABLE, parent=dataset_node)

            if not entity_name:
                entity_name = ''

            # Save the form values in the metadata
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

            # If we're editing an existing data table, the dt_node_id will have been passed in.
            # In that case, we need to replace the old data table node with the new one, preserving
            # the old data table's children.
            if dt_node_id and len(dt_node_id) != 1:
                old_dt_node = Node.get_node_instance(dt_node_id)
                if old_dt_node:

                    attribute_list_node = old_dt_node.find_child(names.ATTRIBUTELIST)
                    if attribute_list_node:
                        # Remove the attribute list as a child of the old data table node and add it
                        # as a child of the new data table node.
                        webapp.home.utils.node_utils.remove_child(attribute_list_node)
                        add_child(dt_node, attribute_list_node)

                    # Similarly handle other children

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

                    # If we're modifying an existing data table, we need to replace the old data table node with the
                    # new one.
                    replace_node(dt_node, old_dt_node.id)
                else:
                    msg = f"No node found in the node store with node id {dt_node_id}"
                    dump_node_store(eml_node, 'data_table')
                    raise NodeWithGivenIdNotFound(msg)
            else:
                # Not modifying an existing data table, so just add the new data table node to the dataset node.
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
    init_evaluation(eml_node, filename)
    tooltip = ''
    if dt_node_id != '1':
        # Editing an existing data table, so we need to populate the form with the existing values.
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
                                # Capture the list of column names
                                atts = compose_atts(att_list)
                            # Fill in the form with the data table's existing values
                            populate_data_table_form(form, dt_node)

                            # Get the tooltip for the status badge
                            tooltip = format_tooltip(dt_node)

                            object_name_node = dt_node.find_single_node_by_path([names.PHYSICAL, names.OBJECTNAME])
                            if object_name_node:
                                object_name = object_name_node.content
                                if object_name:
                                    # Determine if the data table was uploaded so we know whether to display the
                                    #  Re-upload button
                                    was_uploaded = user_data.data_table_was_uploaded(object_name)

        else:
            flash('eml_node is None')
    # else:
    #     dataset_node = eml_node.find_child(names.DATASET)
    #     if not dataset_node:
    #         dataset_node = Node(names.DATASET)
    #     # Allocate a new data table node
    #     dt_node = Node(names.DATATABLE, parent=dataset_node)
    #     dt_node_id = dt_node.id

    init_form_md5(form)

    views.set_current_page('data_table')
    help = views.get_helps([
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
        'clone_attributes_general',
        'save_changes'
    ])
    return render_template('data_table.html', title='Data Table', form=form,
                           atts=atts, help=help, was_uploaded=was_uploaded, dt_node_id=dt_node_id, tooltip=tooltip)


def populate_data_table_form(form: DataTableForm, node: Node):
    """
    Populate the data table form with values from the given data table node.
    Logically, this is a helper function for the data_table() view function, but we don't nest it because it would
      make the code harder to read.
    """
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

    init_form_md5(form)


@dt_bp.route('/load_data/<filename>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def load_data(filename=None):
    """
    Route to handle loading a data table from a CSV file.
    """

    # filename that's passed in is actually the document name, for historical reasons.
    # We'll clear it to avoid misunderstandings...
    filename = None

    form = LoadDataForm()
    document, eml_node = views.reload_metadata()  # So check_metadata status is correct
    uploads_folder = user_data.get_document_uploads_folder_name()

    # Process POST

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(views.get_back_url())

    if request.method == 'POST' and form.validate_on_submit():

        # if is_hidden_button():
        #     current_document = current_user.get_filename()
        #     return redirect(url_for(handle_hidden_buttons(), filename=current_document))

        # Check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)

        eml_node = load_eml(filename=document)
        dataset_node = eml_node.find_child(names.DATASET)
        if not dataset_node:
            dataset_node = new_child_node(names.DATASET, eml_node)

        file = request.files['file']
        if file:
            filename = unquote(file.filename)

        if filename:
            if filename is None or filename == '':
                flash('No selected file', 'error')
            elif views.allowed_data_file(filename):
                # Make sure we don't already have a data table or other entity with this name
                if not webapp.views.data_tables.load_data.data_filename_is_unique(eml_node, filename):
                    flash('The selected name has already been used in this data package. Names of data tables and other entities must be unique within a data package.', 'error')
                    return redirect(request.url)

                # Make sure the user's uploads directory exists
                Path(uploads_folder).mkdir(parents=True, exist_ok=True)
                filepath = os.path.join(uploads_folder, filename)
                if file:
                    # Upload the file to the uploads directory
                    file.save(filepath)

                num_header_rows = '1'
                delimiter = form.delimiter.data
                quote_char = form.quote.data

                try:
                    dt_node, new_column_vartypes, new_column_names, new_column_categorical_codes, *_ = \
                        load_data_table(uploads_folder, filename, num_header_rows, delimiter, quote_char,
                                        check_column_names=True)

                except UnicodeDecodeError as err:
                    errors = views.display_decode_error_lines(filepath)
                    return render_template('encoding_error.html', filename=filename, errors=errors)
                except exceptions.UnicodeDecodeErrorInternal as err:
                    filepath = err.message
                    errors = views.display_decode_error_lines(filepath)
                    return render_template('encoding_error.html', filename=os.path.basename(filepath), errors=errors)
                except exceptions.DataTableError as err:
                    flash(f'Data table has an error: {err.message}', 'error')
                    return redirect(request.url)
                except exceptions.ExtraWhitespaceInColumnNames as err:
                    bad_names = ', '.join('"' + name + '"' for name in err.message)
                    if len(err.message) == 1:
                        msg = "The following column name has leading or trailing spaces: "
                        msg2 = "that column name"
                    else:
                        msg = "The following column names have leading or trailing spaces: "
                        msg2 = "those column names"
                    msg = f"{msg} {bad_names}.<br>" + \
                            "Such extra spaces are not permitted. Please edit the header row of your data table to remove leading or trailing spaces from " + \
                            f"{msg2} and try again."
                    flash(Markup(msg), 'error')
                    return redirect(request.url)

                flash(f"Loaded {filename}")

                dt_node.parent = dataset_node
                dataset_node.add_child(dt_node)

                user_data.add_data_table_upload_filename(filename)
                if new_column_vartypes:
                    user_data.add_uploaded_table_properties(filename,
                                                  new_column_vartypes,
                                                  new_column_names,
                                                  new_column_categorical_codes)

                # Remove data files that are too large to keep or are temp files
                cull_data_files(uploads_folder)

                # Clear the distribution URL, if any, and insert the upload URL
                views.clear_distribution_url(dt_node)
                views.insert_upload_urls(document, eml_node)
                log_usage(actions['LOAD_DATA_TABLE'], filename)

                check_data_table_contents.set_check_data_tables_badge_status(document, eml_node)
                save_both_formats(filename=document, eml_node=eml_node)

                return redirect(url_for(PAGE_DATA_TABLE, filename=document, dt_node_id=dt_node.id, delimiter=delimiter, quote_char=quote_char))

            else:
                flash(f'{filename} is not a supported data file type')
                return redirect(request.url)

    # Process GET
    return render_template('load_data.html', title='Load Data',
                           form=form)


@dt_bp.route('/reupload_data/<filename>/<dt_node_id>', methods=['GET', 'POST'])
@dt_bp.route('/reupload_data/<filename>/<dt_node_id>/<saved_filename>/<name_chg_ok>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def reupload_data(dt_node_id=None, filename=None, saved_filename=None, name_chg_ok=False):
    """
    Route to handle re-uploading a data table from a CSV file.
    """

    # filename that's passed in is actually the document name, for historical reasons.
    # We'll clear it to avoid misunderstandings...
    filename = None

    form = ReloadDataForm()
    document = current_user.get_filename()
    uploads_folder = user_data.get_document_uploads_folder_name()
    eml_node = load_eml(filename=document)

    data_table_name = ''
    dt_node = Node.get_node_instance(dt_node_id)
    if dt_node:
        entity_name_node = dt_node.find_child(names.ENTITYNAME)
        if entity_name_node:
            data_table_name = entity_name_node.content
            if not data_table_name:
                flash(f'Data table name not found in the metadata.', 'error')
                return redirect(request.url)

    if request.method == 'POST' and BTN_CANCEL in request.form:
        url = url_for(PAGE_DATA_TABLE_SELECT, filename=document)
        return redirect(url)

    # if is_hidden_button():
    #     return redirect(url_for(handle_hidden_buttons(), filename=document))

    if request.method == 'POST':
        if dt_node:
            if saved_filename:
                filename = saved_filename
                unmodified_filename = filename
            else:
                file = request.files['file']
                if file:
                    filename = f"{file.filename}"
                    unmodified_filename = filename
                    if views.allowed_data_file(filename):
                        # We upload the new version of the CSV file under a temp name so we have both files to inspect.
                        filename = f"{filename}.ezeml_tmp"
                        filepath = os.path.join(uploads_folder, filename)
                        file.save(filepath)
                    else:
                        flash(f'{filename} is not a supported data file type', 'error')
                        return redirect(request.url)

            delimiter = form.delimiter.data
            quote_char = form.quote.data
            update_codes = form.update_codes.data == 'yes'

            try:
                goto = webapp.views.data_tables.load_data.handle_reupload(dt_node_id=dt_node_id, saved_filename=filename,
                                                                          document=document, eml_node=eml_node,
                                                                          uploads_folder=uploads_folder, name_chg_ok=name_chg_ok,
                                                                          delimiter=delimiter, quote_char=quote_char, update_codes=update_codes)
                log_usage(actions['RE_UPLOAD_DATA_TABLE'], unmodified_filename)
                return goto

            except exceptions.MissingFileError as err:
                flash(err.message, 'error')
                return redirect(request.url)

            except Exception as err:
                return redirect(request.url)

    # Process GET
    help = views.get_helps(['data_table_reupload_full'])
    return render_template('reupload_data.html', title='Re-upload Data Table',
                           form=form, name=data_table_name, help=help)


@dt_bp.route('/upload_spreadsheet/<filename>/<dt_node_id>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def upload_spreadsheet(filename=None, dt_node_id=None):
    form = UploadSpreadsheetForm()
    uploads_folder = user_data.get_document_uploads_folder_name()
    document_name = filename
    load_eml(document_name)

    # Process POST

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(views.get_back_url())

    if request.method == 'POST':

        # Check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)

        file = request.files['file']
        if file:
            filename = unquote(file.filename)

        if filename:
            if filename is None or filename == '':
                flash('No selected file', 'error')

            # Make sure the user's uploads directory exists
            Path(uploads_folder).mkdir(parents=True, exist_ok=True)
            filepath = os.path.join(uploads_folder, filename)
            if file:
                # Upload the file to the uploads directory
                file.save(filepath)
                # Process the uploaded spreadsheet
                try:
                    log_usage(actions['UPLOAD_COLUMN_PROPERTIES_SPREADSHEET'], document_name)
                    table_spreadsheets.ingest_data_table_spreadsheet(filepath, dt_node_id)
                    try:
                        os.remove(filepath)
                    except FileNotFoundError as e:
                        pass
                except exceptions.DataTableSpreadsheetError as e:
                    flash(f'Error uploading the spreadsheet:\n {e}', 'error')
                return redirect(url_for(PAGE_ATTRIBUTE_SELECT, filename=document_name, dt_node_id=dt_node_id))

    # Process GET
    data_table_node = Node.get_node_instance(dt_node_id)
    if data_table_node:
        data_table_name = data_table_node.find_child(names.ENTITYNAME).content
    reload_metadata()  # So check_metadata status is correct
    help = [get_help('geographic_coverages_csv_file')] # FIXME
    return render_template('upload_spreadsheet.html', data_table_name=data_table_name, form=form, help=help)


# <dt_node_id> identifies the dataTable node that this attribute is a part of (within its attributeList)
@dt_bp.route('/attribute_select/<filename>/<dt_node_id>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def attribute_select(filename=None, dt_node_id=None):
    """
    Route to display a list of attributes (columns) in a data table and allow the user to select one to edit.
    """

    def download_spreadsheet(data_table_node_id, filename):
        load_eml(filename=filename)
        data_table_node = Node.get_node_instance(data_table_node_id)
        data_table_name_node = data_table_node.find_child(names.ENTITYNAME)
        data_table_name = data_table_name_node.content
        log_usage(actions['DOWNLOAD_COLUMN_PROPERTIES_SPREADSHEET'], filename)
        return table_spreadsheets.generate_data_entry_spreadsheet(data_table_node, filename, data_table_name)

    def attribute_select_post(filename=None, form=None, form_dict=None,
                              method=None, this_page=None, back_page=None,
                              dt_node_id=None):
        """
        Helper function to handle selection of an attribute to edit or change variable type.
        """
        eml_node = load_eml(filename)
        init_evaluation(eml_node, filename)

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
                    else:
                        # We had a bug that makes some Categorical variables have None type
                        # This is a temporary bandaid.
                        mscale = VariableType.CATEGORICAL.name
                        new_page = PAGE_ATTRIBUTE_CATEGORICAL
                elif val == BTN_REMOVE:
                    new_page = this_page
                    node_id = key
                    eml_node = load_eml(filename=filename)
                    node = Node.get_node_instance(node_id)
                    remove_child(node)
                    save_both_formats(filename=filename, eml_node=eml_node)
                elif val == BTN_CHANGE_SCALE:
                    node_id = key
                    node_to_change = Node.get_node_instance(node_id)
                    mscale = mscale_from_attribute(node_to_change)
                    if not mscale:
                        # We had bug that makes some Categorical variables have None type
                        # This is a temporary bandaid.
                        mscale = 'CATEGORICAL'
                    new_page = PAGE_ATTRIBUTE_MEASUREMENT_SCALE
                elif val == BTN_DOWNLOAD_COLUMN_PROPERTIES_SPREADSHEET:
                    try:
                        outfile = download_spreadsheet(dt_node_id, filename)
                    except Exception as e:
                        log_error(f"Error generating data entry spreadsheet: {str(e)}")
                        flash(f"Error generating data entry spreadsheet: {str(e)}", 'error')
                        outfile = None
                    if outfile:
                        return send_file(outfile, as_attachment=True, download_name=os.path.basename(outfile))
                    else:
                        return redirect(url_for(PAGE_ATTRIBUTE_SELECT, filename=filename, dt_node_id=dt_node_id))
                elif val == BTN_UPLOAD_COLUMN_PROPERTIES_SPREADSHEET:
                    return redirect(url_for(PAGE_UPLOAD_SPREADSHEET, filename=filename, dt_node_id=dt_node_id))
                elif val == UP_ARROW:
                    new_page = this_page
                    node_id = key
                    views.process_up_button(filename, node_id)
                elif val == DOWN_ARROW:
                    new_page = this_page
                    node_id = key
                    views.process_down_button(filename, node_id)
                elif val.startswith('Add Column'):
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
                    else:
                        # We had bug that makes some Categorical variables have None type
                        # This is a temporary bandaid.
                        mscale = 'CATEGORICAL'
                        new_page = PAGE_ATTRIBUTE_CATEGORICAL
                    node_id = '1'
                else:
                    new_page = check_val_for_hidden_buttons(val, new_page)

        if form.validate_on_submit():
            if new_page == back_page:
                return url_for(new_page,
                               filename=filename,
                               dt_node_id=dt_node_id)
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

    def attribute_select_get(filename=None, form=None, dt_node_id=None):
        """
        Helper function to display a list of attributes (columns) in a data table and allow the user to select one to edit.
        """
        # Process GET
        att_list = []
        title = 'Attributes'
        entity_name = ''
        was_uploaded = False
        eml_node = load_eml(filename=filename)
        init_evaluation(eml_node, filename)

        if dt_node_id != '1':
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
                        was_uploaded = user_data.data_table_was_uploaded(object_name)

        init_form_md5(form)

        views.set_current_page('data_table')
        help = views.get_helps(['measurement_scale', 'spreadsheets'])
        return render_template('attribute_select.html',
                               title=title,
                               entity_name=entity_name,
                               att_list=att_list,
                               was_uploaded=was_uploaded,
                               form=form,
                               help=help)

    form = AttributeSelectForm(filename=filename)
    # dt_node_id = request.args.get('dt_node_id')  # alternate way to get the id

    # if is_hidden_button():
    #     current_document = current_user.get_filename()
    #     return redirect(url_for(handle_hidden_buttons(), filename=current_document))

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = attribute_select_post(filename, form, form_dict,
                                    'POST', PAGE_ATTRIBUTE_SELECT, PAGE_DATA_TABLE,
                                    dt_node_id=dt_node_id)
        # If we're doing download spreadsheet, what we get back is the Response object. In that case, we just want to
        #  return it.
        if not isinstance(url, flask.wrappers.Response):
            return redirect(url)
        else:
            return url

    # Process GET
    return attribute_select_get(filename=filename, form=form, dt_node_id=dt_node_id)


@dt_bp.route('/attribute_measurement_scale/<filename>/<dt_node_id>/<node_id>/<mscale>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def attribute_measurement_scale(filename=None, dt_node_id=None, node_id=None, mscale=None):
    """
    Route to handle Change Type for a data table attribute (column).
    """
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

        views.set_current_page('data_table')
        return render_template('attribute_measurement_scale.html', entity_name=name, form=form)

    form = AttributeMeasurementScaleForm(filename=filename)
    att_node_id = node_id

    # if is_hidden_button():
    #     current_document = current_user.get_filename()
    #     return redirect(url_for(handle_hidden_buttons(), filename=current_document))

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        return attribute_measurement_scale_post(
            filename, form, form_dict, dt_node_id, att_node_id, mscale
        )

    # Process GET
    return attribute_measurement_scale_get(filename, form, att_node_id)


def load_df(attribute_node, usecols=None):
    """
    Helper function to load the data table into a Pandas DataFrame.

    usecols is either a "list" of one column name, in which case that column is loaded, or it is None, in which
     case all columns are loaded. Currently, only the former case is used.
    """
    attribute_list_node = attribute_node.parent
    data_table_node = attribute_list_node.parent
    object_name_node = data_table_node.find_descendant(names.OBJECTNAME)
    if not object_name_node:
        return None
    data_file = data_table_node.find_descendant(names.OBJECTNAME).content

    uploads_folder = user_data.get_document_uploads_folder_name()
    full_path = f'{uploads_folder}/{data_file}'

    field_delimiter_node = data_table_node.find_descendant(names.FIELDDELIMITER)
    if field_delimiter_node:
        delimiter = field_delimiter_node.content
    else:
        delimiter = ','
    quote_char_node = data_table_node.find_descendant(names.QUOTECHARACTER)
    if quote_char_node:
        quote_char = quote_char_node.content
    else:
        quote_char = '"'

    try:
        if len(usecols) == 1 and usecols[0] is not None:
            return pd.read_csv(full_path, encoding='utf8', sep=delimiter, quotechar=quote_char,
                               usecols=usecols)
        else:
            return pd.read_csv(full_path, encoding='utf8', sep=delimiter, quotechar=quote_char)
    except FileNotFoundError as e:
        raise webapp.home.exceptions.DataFileNotFound(f"Data file {data_file} not found.")


def force_datetime_type(attribute_node):
    # If we are changing a column to datetime type, go to the data table file and pick up the datetime format
    column_name = attribute_node.find_child(names.ATTRIBUTENAME).content
    data_frame = load_df(attribute_node, usecols=[column_name])
    if data_frame is None:
        raise webapp.home.exceptions.DataFileNotFound("Data file not found.")
    if data_frame[column_name].size > 0:
        return infer_datetime_format(data_frame[column_name][0])
    else:
        return ''

def force_categorical_codes(attribute_node):
    # If we are changing a column to categorical type, go to the data table file and pick up the categorical codes

    def force_missing_value_codes(attribute_node, codes):
        """
        Replace nan values with the missing value code, if any. This will apply the first missing value code.
        """
        missing_value_code_node = attribute_node.find_descendant(names.CODE)
        if missing_value_code_node:
            missing_value = missing_value_code_node.content
            for index, item in enumerate(codes):
                try:
                    # isnan requires item to be a number. It may not be.
                    if math.isnan(item):
                        codes[index] = missing_value
                except TypeError as e:
                    pass

    column_name = attribute_node.find_child(names.ATTRIBUTENAME).content
    data_frame = load_df(attribute_node, usecols=[column_name])
    if data_frame is None:
        return None

    codes = data_frame[column_name].unique().tolist()
    if data_frame.dtypes[column_name] == np.float64:
        # See if the codes can be treated as ints
        ok = True
        int_codes = []
        for code in codes:
            if not math.isnan(code):
                try:
                    int_code = int(code)
                    if int_code != code:
                        ok = False
                        break
                    int_codes.append(int(code))
                except:
                    ok = False
                    break
            else:
                int_codes.append(code)
        if ok:
            codes = int_codes

    # Apply the missing value code, if any. This will apply the first missing value code.
    force_missing_value_codes(attribute_node, codes)

    return sort_codes(codes)

def set_storage_type(attribute_node, storage_type):
    # Set the storage type of the attribute node if storage type is present in the model.
    # In the case of attributes created in ezEML, we usually don't have a storage type node. But a storage type node
    #  may be present if the user edited the storage type or if the EML file was created outside of ezEML and imported.
    # In such cases, when we change the attribute measurement scale, we need to change the storage type as well.
    storage_type_node = attribute_node.find_descendant(names.STORAGETYPE)
    if storage_type_node:
        storage_type_node.content = storage_type
        storage_type_node.add_attribute('typeSystem', 'XML Schema Datatypes')


def change_measurement_scale(attribute_node, old_mscale, new_mscale):
    """
    Change the measurement scale (variable type) of an attribute (column).
    """
    if not attribute_node:
        return
    mscale_node = attribute_node.find_child(names.MEASUREMENTSCALE)

    # if changing to Categorical, make sure it won't result in more than 100 codes
    if new_mscale == VariableType.CATEGORICAL.name:
        column_name = attribute_node.find_child(names.ATTRIBUTENAME).content
        data_frame = load_df(attribute_node, usecols=[column_name])
        if not data_frame.empty:
            codes = data_frame[column_name].unique().tolist()
            if len(codes) > 100:
                flash(f'Column {column_name} contains more than 100 distinct values, so it is not an appropriate candidate for conversion to a Categorical column.\n\nezEML has left its type unchanged.', 'error')
                return

    # clear its children
    if mscale_node:
        mscale_node.remove_children()
    else:
        mscale_node = new_child_node(names.MEASUREMENTSCALE, attribute_node)

    # construct new children
    if new_mscale == VariableType.NUMERICAL.name:
        set_storage_type(attribute_node, 'float')
        new_scale_node = new_child_node(names.RATIO, mscale_node)
        numeric_domain_node = new_child_node(names.NUMERICDOMAIN, new_scale_node)

        number_type_ratio_node = new_child_node(names.NUMBERTYPE, numeric_domain_node)
        number_type_ratio_node.content = 'real'

    elif new_mscale == VariableType.CATEGORICAL.name:
        set_storage_type(attribute_node, 'string')
        new_scale_node = new_child_node(names.NOMINAL, mscale_node)
        non_numeric_domain_node = new_child_node(names.NONNUMERICDOMAIN, new_scale_node)
        enumerated_domain_node = new_child_node(names.ENUMERATEDDOMAIN, non_numeric_domain_node)

        try:
            sorted_codes = force_categorical_codes(attribute_node)
        except webapp.home.exceptions.DataFileNotFound as e:
            flash(e.message, 'warning')
            flash("ezEML changed the variable type to Categorical but cannot automatically detect the categorical codes when the data file is absent.", 'warning')
            return
        if not sorted_codes:
            return

        for child in enumerated_domain_node.children:
            webapp.home.utils.node_utils.remove_child(child)

        for code in sorted_codes:
            code_definition_node = new_child_node(names.CODEDEFINITION, enumerated_domain_node)
            code_node = new_child_node(names.CODE, code_definition_node)
            code_node.content = code
            definition_node = new_child_node(names.DEFINITION, code_definition_node)

    elif new_mscale == VariableType.TEXT.name:
        set_storage_type(attribute_node, 'string')
        new_scale_node = new_child_node(names.NOMINAL, mscale_node)
        non_numeric_domain_node = new_child_node(names.NONNUMERICDOMAIN, new_scale_node)
        text_domain_node = new_child_node(names.TEXTDOMAIN, non_numeric_domain_node)
        definition_node = new_child_node(names.DEFINITION, text_domain_node)
        attribute_definition_node = attribute_node.find_child(names.ATTRIBUTEDEFINITION)
        if attribute_definition_node:
            definition_node.content = attribute_definition_node.content

    elif new_mscale == VariableType.DATETIME.name:
        set_storage_type(attribute_node, 'dateTime')
        new_scale_node = new_child_node(names.DATETIME, mscale_node)
        format_string_node = new_child_node(names.FORMATSTRING, new_scale_node)
        try:
            format_string = force_datetime_type(attribute_node)
        except webapp.home.exceptions.DataFileNotFound as e:
            flash(e.message, 'warning')
            flash("ezEML changed the variable type to DateTime but cannot automatically detect the datetime format when the data file is absent.", 'warning')
            return
        if format_string:
            format_string_node.content = format_string


def retrieve_missing_value_codes_from_form(form):
    # Helper function to pick up missing value codes and definitions from the form and return a dictionary.
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

    return code_dict


def populate_missing_value_codes_in_form(form, node):
    """
    Helper function to populate missing value codes and their definitions in the form.
    """
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


@dt_bp.route('/attribute_dateTime/<filename>/<dt_node_id>/<node_id>', methods=['GET', 'POST'])
@login_required
def attribute_dateTime(filename=None, dt_node_id=None, node_id=None):
    """
    Route to handle Edit Properties for a DateTime attribute.
    """
    form = AttributeDateTimeForm(filename=filename, node_id=node_id)
    att_node_id = node_id
    eml_node = load_eml(filename=filename)

    if request.method == 'POST' and BTN_CANCEL in request.form:
        url = url_for(PAGE_ATTRIBUTE_SELECT, filename=filename, dt_node_id=dt_node_id, node_id=att_node_id)
        return redirect(url)

    # Determine POST type
    if request.method == 'POST' and form.validate_on_submit():

        if is_dirty_form(form):
            submit_type = 'Save Changes'
        else:
            submit_type = 'Back'

        if submit_type == 'Save Changes':
            dt_node = None
            attribute_list_node = None
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

            # Collect form values
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

            # Handle missing value codes
            code_dict = retrieve_missing_value_codes_from_form(form)

            att_node = Node(names.ATTRIBUTE, parent=attribute_list_node)

            # Create the attribute node using the form data
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

            # If the attribute node already exists, replace it with the new one. This is indicated by the
            #  node_id being present and not equal to 1.
            if node_id and len(node_id) != 1:
                old_att_node = Node.get_node_instance(att_node_id)
                if old_att_node:
                    replace_node(att_node, old_att_node.id)
                else:
                    msg = f"No node found in the node store with node id {node_id}"
                    dump_node_store(eml_node, 'attribute_dateTime')
                    raise NodeWithGivenIdNotFound(msg)
            else:
                add_child(attribute_list_node, att_node)

            save_both_formats(filename=filename, eml_node=eml_node)
            att_node_id = att_node.id

        if BTN_DONE in request.form:
            next_page = PAGE_ATTRIBUTE_SELECT
        else:
            next_page = PAGE_ATTRIBUTE_DATETIME

        next_page = handle_hidden_buttons(next_page)

        url = url_for(next_page, filename=filename, dt_node_id=dt_node_id, node_id=att_node_id)

        return redirect(url)

    # Process GET
    if node_id != '1':
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

    data_table_name = ''
    attribute_name = ''
    dt_node = Node.get_node_instance(dt_node_id)
    if dt_node:
        entity_name_node = dt_node.find_child(names.ENTITYNAME)
        if entity_name_node:
            data_table_name = entity_name_node.content
    if att_node_id:
        att_node = Node.get_node_instance(att_node_id)
        if att_node:
            attribute_name_node = att_node.find_child(names.ATTRIBUTENAME)
            if attribute_name_node:
                attribute_name = attribute_name_node.content

    init_form_md5(form)

    # Get the tooltip for the status badge
    init_evaluation(eml_node, filename)
    tooltip = format_tooltip(att_node)

    views.set_current_page('data_table')
    help = views.get_helps(['attribute_name', 'attribute_definition', 'attribute_label', 'attribute_storage_type',
                      'attribute_datetime_precision', 'attribute_datetime_format', 'save_changes'])
    return render_template('attribute_datetime.html', title='Attribute', form=form,
                           column_name=attribute_name,
                           att_node_id=att_node_id,
                           table_name=data_table_name,
                           help=help, tooltip=tooltip)


def populate_attribute_datetime_form(form: AttributeDateTimeForm, node: Node):
    """
    Populate the attribute form with values from the given DateTime attribute.
    Logically, this is nested in attribute_datetime(), but it's a separate function to make it more readable.
    """
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

    populate_missing_value_codes_in_form(form, att_node)

    init_form_md5(form)


@dt_bp.route('/attribute_numerical/<filename>/<dt_node_id>/<node_id>/<mscale>', methods=['GET', 'POST'])
@login_required
def attribute_numerical(filename=None, dt_node_id=None, node_id=None, mscale=None):
    """
    Route to handle Edit Properties for a Numerical attribute.
    """
    form = AttributeIntervalRatioForm(filename=filename, node_id=node_id)
    att_node_id = node_id
    att_node = None

    if request.method == 'POST' and BTN_CANCEL in request.form:
        url = url_for(PAGE_ATTRIBUTE_SELECT, filename=filename, dt_node_id=dt_node_id, node_id=att_node_id)
        return redirect(url)

    if request.method == 'POST':

        if is_dirty_form(form):
            submit_type = 'Save Changes'
            # flash(f"is_dirty_form: True")
        else:
            submit_type = 'Back'
            # flash(f"is_dirty_form: False")

        # If we have a hidden button, we note that fact but we may need to save changes before going there.
        next_page = handle_hidden_buttons(PAGE_ATTRIBUTE_SELECT)

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

            # Collect the form values.
            attribute_name = form.attribute_name.data
            attribute_label = form.attribute_label.data
            attribute_definition = form.attribute_definition.data
            storage_type = form.storage_type.data
            storage_type_system = form.storage_type_system.data
            standard_unit = form.standard_unit.data
            custom_unit = form.custom_unit.data
            if '"' in custom_unit:
                flash('The custom unit cannot contain a double quote ("). Please try again.', 'error')
                url = url_for(PAGE_ATTRIBUTE_NUMERICAL, filename=filename, dt_node_id=dt_node_id, node_id=att_node_id, mscale=mscale)
                return redirect(url)
            custom_unit_definition = form.custom_unit_description.data
            precision = form.precision.data
            number_type = form.number_type.data
            bounds_minimum = form.bounds_minimum.data
            bounds_minimum_exclusive = form.bounds_minimum_exclusive.data
            bounds_maximum = form.bounds_maximum.data
            bounds_maximum_exclusive = form.bounds_maximum_exclusive.data

            # Handle missing value codes
            code_dict = retrieve_missing_value_codes_from_form(form)

            att_node = Node(names.ATTRIBUTE, parent=attribute_list_node)

            if node_id and len(node_id) != 1:
                old_att_node = Node.get_node_instance(att_node_id)
                if old_att_node:
                    if standard_unit and custom_unit:
                        # User is changing from one unit type to another. We need to decide which one is the new one.
                        if old_att_node.find_descendant(names.STANDARDUNIT):
                            # The old unit was a standard unit. We must be switching to a custom unit.
                            standard_unit = None
                        elif old_att_node.find_descendant(names.CUSTOMUNIT):
                            # The old unit was a custom unit. We must be switching to a standard unit.
                            custom_unit = None

            """ Create the attribute node using the form values """
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
                    replace_node(att_node, old_att_node.id)
                else:
                    msg = f"No node found in the node store with node id {node_id}"
                    dump_node_store(eml_node, 'attribute_numerical')
                    raise NodeWithGivenIdNotFound(msg)
            else:
                add_child(attribute_list_node, att_node)

            save_both_formats(filename=filename, eml_node=eml_node)
            att_node_id = att_node.id

        if BTN_DONE in request.form:
            next_page = PAGE_ATTRIBUTE_SELECT
            url = url_for(next_page, filename=filename, dt_node_id=dt_node_id, node_id=att_node_id)
        else:
            if next_page == PAGE_ATTRIBUTE_SELECT: # We didn't have a hidden button
                next_page = PAGE_ATTRIBUTE_NUMERICAL
            url = url_for(next_page, filename=filename, dt_node_id=dt_node_id, node_id=att_node_id, mscale=mscale)

        return redirect(url)

    # Process GET
    attribute_name = ''
    eml_node = load_eml(filename=filename)
    if node_id != '1':
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

    data_table_name = ''
    dt_node = Node.get_node_instance(dt_node_id)
    if dt_node:
        entity_name_node = dt_node.find_child(names.ENTITYNAME)
        if entity_name_node:
            data_table_name = entity_name_node.content
    views.set_current_page('data_table')
    custom_unit_names = []
    custom_unit_descriptions = []
    if 'custom_units' in session:
        for name, desc in session['custom_units'].items():
            custom_unit_names.append(name)
            custom_unit_descriptions.append(desc)

    init_form_md5(form)

    # Get the tooltip for the status badge
    init_evaluation(eml_node, filename)
    if att_node:
        tooltip = format_tooltip(att_node)
    else:
        tooltip = ''

    help = views.get_helps(['attribute_name', 'attribute_definition', 'attribute_label', 'attribute_storage_type',
                      'attribute_number_type', 'attribute_numerical_precision', 'save_changes'])
    return render_template('attribute_numerical.html',
                           title='Attribute: Numerical',
                           form=form,
                           attribute_name=attribute_name,
                           att_node_id=att_node_id,
                           mscale=mscale,
                           custom_unit_names=custom_unit_names,
                           custom_unit_descriptions=custom_unit_descriptions,
                           column_name=attribute_name,
                           table_name=data_table_name,
                           help=help, tooltip=tooltip)


def populate_attribute_numerical_form(form: AttributeIntervalRatioForm = None, eml_node: Node = None, att_node: Node = None,
                                           mscale: str = None):
    """
    Populate the attribute form with values from the given Numerical attribute.
    Logically, this is nested in attribute_numerical(), but it's a separate function to make it more readable.
    """

    form.standard_unit.choices = [('', '')] + [(x, x) for x in standard_units.standard_units]

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
                    # If the standard unit is not in the list of standard units, add it so that the value will display.
                    # An error will be generated as well.
                    if form.standard_unit.data not in standard_units.standard_units:
                        unit_choices = sorted(standard_units.standard_units + [form.standard_unit.data], key=lambda x: x.lower())
                        form.standard_unit.choices = [('', '')] + [(x, x) for x in unit_choices]
                custom_unit_node = unit_node.find_child(names.CUSTOMUNIT)
                if custom_unit_node:
                    custom_unit_name = custom_unit_node.content
                    form.custom_unit.data = custom_unit_name
                    # get description, if any, from an additionalMetadata section
                    additional_metadata_nodes = eml_node.find_all_children(names.ADDITIONALMETADATA)
                    for additional_metadata_node in additional_metadata_nodes:
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
                                    break

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

    populate_missing_value_codes_in_form(form, att_node)

    init_form_md5(form)


@dt_bp.route('/attribute_text/<filename>/<dt_node_id>/<node_id>/<mscale>', methods=['GET', 'POST'])
@login_required
def attribute_text(filename: str = None, dt_node_id: str = None, node_id: str = None, mscale: str = None):
    """
    Route to create or edit a Text attribute. We treat it as a case of a Categorical attribute in order to reuse code.
    """
    return attribute_categorical(filename, dt_node_id, node_id, mscale)


@dt_bp.route('/attribute_categorical/<filename>/<dt_node_id>/<node_id>/<mscale>', methods=['GET', 'POST'])
@login_required
def attribute_categorical(filename: str = None, dt_node_id: str = None, node_id: str = None, mscale: str = None):
    """
    Route to create or edit a Categorical attribute or Text attribute (which is treated as a special case of a
    Categorical attribute).
    """

    def code_definition_from_attribute(att_node: Node = None):
        """ Helper function to return a codeDefinition node from an attribute node. """
        nominal_ordinal_node = nominal_ordinal_from_attribute(att_node)
        if nominal_ordinal_node:
            return nominal_ordinal_node.find_single_node_by_path([
                names.NONNUMERICDOMAIN,
                names.ENUMERATEDDOMAIN,
                names.CODEDEFINITION
            ])
        else:
            return None

    if mscale == 'TEXT':
        form = AttributeTextForm(filename=filename, node_id=node_id)
    else:
        form = AttributeCategoricalForm(filename=filename, node_id=node_id)
    att_node_id = node_id

    if request.method == 'POST' and BTN_CANCEL in request.form:
        url = url_for(PAGE_ATTRIBUTE_SELECT, filename=filename, dt_node_id=dt_node_id, node_id=att_node_id)
        return redirect(url)

    # Determine POST type
    if request.method == 'POST':

        if is_dirty_form(form):
            submit_type = 'Save Changes'
        else:
            submit_type = 'Back'

        # Go back to data table or go to the appropriate measurement scale page
        next_page = None
        if BTN_DONE in request.form:
            next_page = PAGE_ATTRIBUTE_SELECT
        elif 'Codes' in request.form:
            next_page = PAGE_CODE_DEFINITION_SELECT
        else:
            next_page = PAGE_ATTRIBUTE_CATEGORICAL

        # If we have a hidden button, we note that fact but we may need to save changes before going there.
        next_page = handle_hidden_buttons(next_page)

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

            # Handle missing value codes
            code_dict = retrieve_missing_value_codes_from_form(form)

            att_node = Node(names.ATTRIBUTE, parent=attribute_list_node)

            # Create the attribute node using values from the form.
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
                    replace_node(att_node, old_att_node.id)
                else:
                    msg = f"No node found in the node store with node id {node_id}"
                    dump_node_store(eml_node, 'attribute_categorical')
                    raise NodeWithGivenIdNotFound(msg)
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
            url = url_for(next_page, filename=filename, dt_node_id=dt_node_id, node_id=att_node_id, mscale=mscale)

        return redirect(url)

    # Process GET
    eml_node = load_eml(filename=filename)
    attribute_name = ''
    codes = 'No codes have been defined yet'
    if node_id != '1':
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

    data_table_name = ''
    dt_node = Node.get_node_instance(dt_node_id)
    if dt_node:
        entity_name_node = dt_node.find_child(names.ENTITYNAME)
        if entity_name_node:
            data_table_name = entity_name_node.content
    if att_node_id:
        att_node = Node.get_node_instance(att_node_id)
        if att_node:
            attribute_name_node = att_node.find_child(names.ATTRIBUTENAME)
            if attribute_name_node:
                attribute_name = attribute_name_node.content

    init_form_md5(form)

    # Get the tooltip for the status badge
    init_evaluation(eml_node, filename)
    tooltip = format_tooltip(att_node)

    views.set_current_page('data_table')
    help = views.get_helps(['attribute_name', 'attribute_definition', 'attribute_label', 'attribute_storage_type', 'save_changes'])
    if mscale == VariableType.CATEGORICAL.name:
        return render_template('attribute_categorical.html',
                               title='Categorical Attribute',
                               form=form,
                               attribute_name=attribute_name,
                               att_node_id=att_node_id,
                               mscale=mscale,
                               codes=codes,
                               column_name=attribute_name,
                               table_name=data_table_name,
                               help=help,
                               tooltip=tooltip)
    else:
        return render_template('attribute_text.html',
                               title='Text Attribute',
                               form=form,
                               attribute_name=attribute_name,
                               att_node_id=att_node_id,
                               mscale=mscale,
                               column_name=attribute_name,
                               table_name=data_table_name,
                               help=help,
                               tooltip=tooltip)


def populate_attribute_categorical_form(form: AttributeCategoricalForm, att_node: Node = None,
                                            mscale: str = None):
    """
    Populate the attribute form with values from the given Categorical or Text attribute.
    Logically, this is nested in attribute_categorical(), but it's a separate function to make it more readable.
    """

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

    populate_missing_value_codes_in_form(form, att_node)

    init_form_md5(form)
    return codes


# <node_id> identifies the nominal or ordinal node that this code definition
# is a part of
#
@dt_bp.route('/code_definition_select/<filename>/<dt_node_id>/<att_node_id>/<node_id>/<mscale>',
             methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def code_definition_select(filename=None, dt_node_id=None, att_node_id=None, node_id=None, mscale=None):
    """
    Route to handle the selection of a categorical code definition for editing.
    """

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
                    node = Node.get_node_instance(node_id)
                    remove_child(node)
                    save_both_formats(filename=filename, eml_node=eml_node)
                elif val == UP_ARROW:
                    new_page = this_page
                    node_id = key
                    views.process_up_button(filename, node_id)
                elif val == DOWN_ARROW:
                    new_page = this_page
                    node_id = key
                    views.process_down_button(filename, node_id)
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

    nom_ord_node_id = node_id
    form = CodeDefinitionSelectForm(filename=filename)

    # if is_hidden_button():
    #     current_document = current_user.get_filename()
    #     return redirect(url_for(handle_hidden_buttons(), filename=current_document))

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
                                          mscale=mscale.replace('VariableType.', ''))
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

    data_table_name = ''
    if dt_node_id:
        dt_node = Node.get_node_instance(dt_node_id)
        entity_name_node = dt_node.find_child(names.ENTITYNAME)
        if entity_name_node:
            data_table_name = entity_name_node.content

    views.set_current_page('data_table')
    return render_template('code_definition_select.html',
                           title=title,
                           attribute_name=attribute_name,
                           codes_list=codes_list,
                           column_name=attribute_name,
                           table_name=data_table_name,
                           form=form)


# node_id is the id of the codeDefinition node being edited. If the value
# '1', it means we are adding a new codeDefinition node, otherwise we are
# editing an existing one.
#
@dt_bp.route('/code_definition/<filename>/<dt_node_id>/<att_node_id>/<nom_ord_node_id>/<node_id>/<mscale>',
             methods=['GET', 'POST'])
@login_required
def code_definition(filename=None, dt_node_id=None, att_node_id=None, nom_ord_node_id=None, node_id=None, mscale=None):
    """
    Route to edit a categorical code definition
    """

    def enumerated_domain_from_attribute(att_node: Node = None):
        nominal_ordinal_node = nominal_ordinal_from_attribute(att_node)
        if nominal_ordinal_node:
            return nominal_ordinal_node.find_single_node_by_path([
                names.NONNUMERICDOMAIN, names.ENUMERATEDDOMAIN
            ])
        else:
            return None

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

        init_form_md5(form)

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

        # If we have a hidden button, we note that fact but we may need to save changes before going there.
        next_page = handle_hidden_buttons(PAGE_CODE_DEFINITION_SELECT)

        if is_dirty_form(form):
            submit_type = 'Save Changes'
        else:
            submit_type = 'Back'

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
                        msg = f"No node found in the node store with node id {node_id}"
                        dump_node_store(eml_node, 'code_definition')
                        raise NodeWithGivenIdNotFound(msg)
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
    if node_id != '1':
        enumerated_domain_node = enumerated_domain_from_attribute(att_node)  # FIXME - Question: schema allows multiple of these
        if enumerated_domain_node:
            cd_nodes = enumerated_domain_node.find_all_children(names.CODEDEFINITION)
            if cd_nodes:
                for cd_node in cd_nodes:
                    if node_id == cd_node.id:
                        populate_code_definition_form(form, cd_node)
                        break

    att_node = Node.get_node_instance(att_node_id)
    if att_node:
        attribute_name = attribute_name_from_attribute(att_node)

    data_table_name = ''
    if dt_node_id:
        dt_node = Node.get_node_instance(dt_node_id)
        entity_name_node = dt_node.find_child(names.ENTITYNAME)
        if entity_name_node:
            data_table_name = entity_name_node.content

    init_form_md5(form)

    views.set_current_page('data_table')
    return render_template('code_definition.html', title='Code Definition',
                           form=form, attribute_name=attribute_name,
                           column_name=attribute_name,
                           table_name=data_table_name)


@dt_bp.route('/clone_attributes/<filename>/<dt_node_id>/', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def clone_attributes(filename, dt_node_id):
    """
    Initial page for Clone attributes from another data table. We ask the user to select the source package/document.
    """
    eml_node = load_eml(filename=filename)

    target_filename = filename
    target_dt_id = dt_node_id

    form = OpenDocumentForm()
    form.filename.choices = list_data_packages(True, True, current_user_directory_only=False)

    # if is_hidden_button():
    #     current_document = current_user.get_filename()
    #     return redirect(url_for(handle_hidden_buttons(), filename=current_document))

    # Process POST
    if request.method == 'POST':
        if BTN_CANCEL in request.form:
            return redirect(views.get_back_url())

        if form.validate_on_submit():
            source_filename = form.filename.data
            return redirect(url_for('dt.clone_attributes_2', target_filename=target_filename, target_dt_id=target_dt_id, source_filename=source_filename))

    # Process GET
    help = views.get_helps(['clone_attributes_1'])
    return render_template('clone_attributes.html', filename=filename, dt_id=dt_node_id, help=help, form=form)


@dt_bp.route('/clone_attributes_2/<target_filename>/<target_dt_id>/<source_filename>/', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def clone_attributes_2(target_filename, target_dt_id, source_filename):
    """
    Second page for Clone attributes from another data table. We ask the user to select the source data table.
    """
    form = SelectDataTableForm()

    # When cloning, we know the source and target have the same owner. We get the login for that owner and
    # pass it along to load_eml() to make sure we're pulling in the right package.
    owner_login = None
    try:
        owner_login = user_data.get_active_document_owner_login()
    except Exception as e:
        log_error(f"load_eml: {e}")

    eml_node = load_eml(filename=target_filename, owner_login=owner_login)
    target_dt_node = Node.get_node_instance(target_dt_id)
    target_object_name = target_dt_node.find_descendant(names.OBJECTNAME).content

    source_eml_node = load_eml(source_filename, do_not_lock=True, owner_login=owner_login)
    source_data_tables = list_data_tables(source_eml_node, to_skip=target_dt_id) # we don't want to clone a DT onto itself

    choices = [[data_table[0], data_table[1]] for data_table in source_data_tables]
    form.source.choices = choices
    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(views.get_back_url())

    if request.method == 'POST' and form.validate_on_submit():

        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        source_dt_id = form_dict['source'][0]
        help = views.get_helps(['clone_attributes_3'])

        source_dt_node = Node.get_node_instance(source_dt_id)
        source_dt_name_node = source_dt_node.find_descendant(names.ENTITYNAME)
        table_name_in = source_dt_name_node.content

        target_dt_node = Node.get_node_instance(target_dt_id)
        target_dt_name_node = target_dt_node.find_descendant(names.ENTITYNAME)
        table_name_out = target_dt_name_node.content

        return redirect(url_for('dt.clone_attributes_3', target_filename=target_filename, target_dt_id=target_dt_id,
                                source_filename=source_filename, source_dt_id=source_dt_id,
                                table_name_in=table_name_in, table_name_out=table_name_out,
                                owner_login=owner_login, help=help, form=form))

    # Process GET
    help = views.get_helps(['clone_attributes_2'])
    return render_template('clone_attributes_2.html', target_filename=target_filename, target_dt_id=target_dt_id, source_filename=source_filename, help=help, form=form)


@dt_bp.route('/clone_attributes_3/<target_filename>/<target_dt_id>/<source_filename>/<source_dt_id>/<table_name_in>/<table_name_out>/<owner_login>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def clone_attributes_3(target_filename, target_dt_id, source_filename, source_dt_id, table_name_in, table_name_out, owner_login):
    """
    Third page for Clone attributes from another data table. We ask the user to select the source columns in the source data table.
    """
    form = SelectDataTableColumnsForm()

    source_eml_node = load_eml(source_filename, owner_login=owner_login)
    source_dt_node = Node.get_node_instance(source_dt_id)

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(views.get_back_url())

    # if request.method == 'POST' and form.validate_on_submit():
    if request.method == 'POST':

        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        source_attr_ids = form_dict.get('source', None)

        if source_attr_ids: # If no option was selected, we'll fall thru and do the GET again

            help = views.get_helps(['import_responsible_parties_2'])  # FIX_ME
            return redirect(url_for('dt.clone_attributes_4', target_filename=target_filename, target_dt_id=target_dt_id,
                                    source_filename=source_filename, source_dt_id=source_dt_id,
                                    table_name_in=table_name_in, table_name_out=table_name_out,
                                    source_attr_ids=source_attr_ids, owner_login=owner_login,
                                    help=help, form=form))

    # Process GET
    help = views.get_helps(['clone_attributes_3'])

    source_dt_node = Node.get_node_instance(source_dt_id)
    source_data_table_columns = list_data_table_columns(source_dt_node)

    choices = [[source_data_table_column[0], source_data_table_column[1]] for source_data_table_column in source_data_table_columns]
    form.source.choices = choices

    return render_template('clone_attributes_3.html', target_filename=target_filename, target_dt_id=target_dt_id,
                           source_filename=source_filename, source_dt_id=source_dt_id,
                           table_name_in=table_name_in, table_name_out=table_name_out, owner_login=owner_login,
                           help=help, form=form)


@dt_bp.route('/clone_attributes_4/<target_filename>/<target_dt_id>/<source_filename>/<source_dt_id>/<table_name_in>/<table_name_out>/<source_attr_ids>/<owner_login>',
             methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def clone_attributes_4(target_filename, target_dt_id, source_filename, source_dt_id, table_name_in, table_name_out, source_attr_ids, owner_login):
    """
    Fourth page for Clone attributes from another data table. We ask the user to map the source columns to the target columns.
    Then, we're ready to clone.
    """
    form = SelectDataTableColumnsForm()

    source_eml_node = load_eml(source_filename, do_not_lock=True, owner_login=owner_login)
    source_attr_ids_list = source_attr_ids.strip('][').split(', ')
    source_attrs = []
    for source_attr_id in source_attr_ids_list:
        id = source_attr_id.replace("'", "")
        source_attr_name_node = Node.get_node_instance(id)
        source_attr_name = source_attr_name_node.content
        source_attr_node = source_attr_name_node.parent
        source_attrs.append((source_attr_name, source_attr_node.id))

    target_eml_node = load_eml(target_filename, owner_login=owner_login)
    target_dt_node = Node.get_node_instance(target_dt_id)
    target_attrs = []
    target_dt_attr_nodes = []
    target_dt_node.find_all_descendants(names.ATTRIBUTE, target_dt_attr_nodes)
    for target_dt_attr_node in target_dt_attr_nodes:
        target_attr_name_node = target_dt_attr_node.find_descendant(names.ATTRIBUTENAME)
        target_attrs.append((target_attr_name_node.content, target_dt_attr_node.id))

    if request.method == 'POST' and BTN_CANCEL in request.form:
        return redirect(views.get_back_url())

    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        # Save a backup of metadata
        views.backup_metadata(target_filename)
        source_attr_ids = [x[1] for x in source_attrs]
        target_attr_ids = []
        for key, val in form_dict.items():
            if key.startswith('SELECT__') and key.endswith('__SELECT'):
                # This builds a list of the target attributes that were selected
                # In cases where no target was selected, an empty string will go in the list. This serves as a placeholder
                #  so the source and target lists will match up. The clone_column_properties function will ignore the
                #  attributes for which no target was selected.
                target_attr_ids.append(val[0])

        clone_column_properties(source_dt_id, source_attr_ids, target_dt_id, target_attr_ids)

        # If column has a custom unit, we need to add the additionalMetadata for it
        if source_eml_node and source_attr_node:
            custom_unit_node = source_attr_node.find_descendant(names.CUSTOMUNIT)
            if custom_unit_node:
                custom_unit = custom_unit_node.content
                custom_unit_description = None
                if custom_unit:
                    # We need to look in the source eml's additionalMetadata for the custom unit description, if any
                    unit_nodes = source_eml_node.find_all_nodes_by_path([names.ADDITIONALMETADATA,
                                                                         names.METADATA,
                                                                         names.UNITLIST,
                                                                         names.UNIT])
                    for unit_node in unit_nodes:
                        id = unit_node.attribute_value('id')
                        name = unit_node.attribute_value('name')
                        if id == custom_unit or name == custom_unit:
                            custom_unit_description_node = unit_node.find_child(names.DESCRIPTION)
                            if custom_unit_description_node:
                                custom_unit_description = custom_unit_description_node.content
                            handle_custom_unit_additional_metadata(target_eml_node,
                                                                   custom_unit,
                                                                   custom_unit_description)
                            break

        log_usage(actions['CLONE_COLUMN_PROPERTIES'], source_filename, table_name_in, target_filename, table_name_out)
        save_both_formats(target_filename, target_eml_node)
        return redirect(url_for('dt.data_table_select', filename=target_filename))

    help = views.get_helps(['clone_attributes_4', 'clone_attributes_targets'])

    return render_template('clone_attributes_4.html', target_filename=target_filename, target_dt_id=target_dt_id,
                           source_filename=source_filename, source_dt_id=source_dt_id,
                           table_name_in=table_name_in, table_name_out=table_name_out,
                           source_attrs=source_attrs, target_attrs=target_attrs, owner_login=owner_login,
                           help=help, form=form)


def clone_column_properties(source_table_id, source_attr_ids, target_table_id, target_attr_ids):
    """
    Helper function to clone the properties of a column.

    Logically, nested in clone_attributes_4, but it's a separate function to aid readability.
    """

    # Capture source's missing value codes and definitions
    # Copy target's missing value code nodes
    # Replace target with copy of source
    # Replace missing value code nodes with the copies we made
    # Go thru the missing value code nodes and fix the definitions
    def clone_categorical_attribute(source_node_copy, target_node):
        enumerated_domain_source_node = source_node_copy.find_descendant(names.ENUMERATEDDOMAIN)
        enumerated_domain_target_node = target_node.find_descendant(names.ENUMERATEDDOMAIN)
        if enumerated_domain_source_node and enumerated_domain_target_node:
            # Both are categorical; so far, so good
            # Collect the source's codes and definitions
            source_codes_and_definitions = {}
            for code_definition_source_node in enumerated_domain_source_node.find_all_children(names.CODEDEFINITION):
                code_source_node = code_definition_source_node.find_child(names.CODE)
                definition_source_node = code_definition_source_node.find_child(names.DEFINITION)
                code = str(code_source_node.content)
                definition = definition_source_node.content
                source_codes_and_definitions[code] = definition

            # We want to preserve the column name
            target_name = target_node.find_descendant(names.ATTRIBUTENAME).content

            # Capture the target's code nodes
            # target_code_definition_nodes = enumerated_domain_target_node.find_all_children(names.CODEDEFINITION)

            # Replace the target with copy of the source
            target_parent = target_node.parent
            target_parent.replace_child(target_node, source_node_copy,
                                        False)  # don't delete the target_node yet because we may need it again

            # But preserve the original name for the target attribute
            source_copy_name_node = source_node_copy.find_descendant(names.ATTRIBUTENAME)
            source_copy_name_node.content = target_name

            '''
            We used to handle categorical columns as described in the User Guide:
                "For Categorical columns, the codes in the target data table are not changed, but their
                definitions are filled in by using the definitions for the corresponding codes in the source
                data table. This way, the lists of codes will match what’s in the target data table’s CSV
                file, but the code definitions won’t all have to be re-entered for codes that are in
                common between the two tables.

            We have since decided to remove this restriction and now just replace the target's codes and definitions
            with the source's codes and definitions. This is because the user may have added codes to the source
            that are not in the target, and we want to pick up those codes as well.
            '''

            return True
        else:
            return False

    def display_children_nodes(parent_node, level='info'):
        """ Log the children of the given node for diagnosis purposes """
        i = 0
        for child_node in parent_node.children:
            attr_name = None
            attr_name_node = child_node.find_child(names.ATTRIBUTENAME)
            if attr_name_node:
                attr_name = attr_name_node.content
            outstr = f"{i}: {child_node.id}  {attr_name}"
            if level == 'error':
                log_error(outstr)
            else:
                log_info(outstr)
            i = i + 1

    for source_attr_id, target_attr_id in zip(source_attr_ids, target_attr_ids):
        # Skip if no target was selected
        if not target_attr_id:
            continue
        source_node = Node.get_node_instance(source_attr_id)
        source_node_copy = source_node.copy()
        # If source_node has an 'id' attribute, give it a new one so we don't wind up with duplicate ids
        if source_node_copy.attribute_value('id'):
            source_node_copy.attributes['id'] = str(uuid.uuid4())
        target_node = Node.get_node_instance(target_attr_id)
        # We want to preserve the column name
        target_name = target_node.find_descendant(names.ATTRIBUTENAME).content
        target_parent = target_node.parent
        # If we're doing a Categorical variable, it gets special handling

        if not clone_categorical_attribute(source_node_copy, target_node):
            try:
                target_parent.replace_child(target_node, source_node_copy, False)  # don't delete the target_node yet because we may need it again
            except:
                log_error(f"\ntarget: {target_node.id}  {target_name}")
                display_children_nodes(target_parent, level='error')
                raise Exception("Missing child in clone_column_properties")
            source_copy_name_node = source_node_copy.find_descendant(names.ATTRIBUTENAME)
            source_copy_name_node.content = target_name
        else:
            pass
    # Now that we're done, we can delete the nodes we've replaced
    for target_attr_id in target_attr_ids:
        # log_info(f"deleting Node {target_attr_id}")
        if target_attr_id:
            Node.delete_node_instance(target_attr_id, True)


def attribute_name_from_attribute(att_node:Node=None):
    """ Helper function to return an attribute name given its node. """
    attribute_name = ''

    if att_node:
        attribute_name_node = att_node.find_child(names.ATTRIBUTENAME)
        if attribute_name_node:
            attribute_name = attribute_name_node.content

    return attribute_name


def entity_name_from_data_table(dt_node:Node=None):
    """ Helper function to return an entity name given its node. """
    entity_name = ''

    if dt_node:
        entity_name_node = dt_node.find_child(names.ENTITYNAME)
        if entity_name_node:
            entity_name = entity_name_node.content

    return entity_name
