"""
This module contains the routes for the geographic, temporal, and taxonomic coverage pages.

There is one gotcha regarding taxonomic coverage. The EML standard permits a variety of different ways to define
taxonomic coverage. In particular, the schema permits multiple taxonomicClassification children of a taxonomicCoverage
element.

What ezEML expects is that each taxonomicCoverage element will have one and only one taxonomicClassification child.
So, if there are multiple taxonomic coverages defined, each will have its own taxonomicCoverage element under the
dataset's coverage element. A package that was created using ezEML will adhere to ezEML's expectations, but a package
that was created using some other tool may not. So, when loading a package, ezEML will check to see if the package
conforms to ezEML's expectations. If it does not, ezEML sets a flag (and saves it in additionalMetadata) that prevents
the user from editing the taxonomic coverage. The user can still view the taxonomic coverage, but cannot edit it.
It will, however, be preserved and saved in XML output. The user can also delete the taxonomic coverage and create a
new one (which will necessarily conform to ezEML's expectations).
"""

import ast
import numpy as np
import os
import pandas as pd
import shutil

from flask import (
    Blueprint, flash, render_template, redirect, request, url_for
)
from flask_login import (
    current_user, login_required
)

import webapp.home.utils.node_utils
from webapp.home.exceptions import InvalidHeaderRow, UnexpectedDataTypes, TaxonNotFound, NodeWithGivenIdNotFound

from webapp.home.utils.hidden_buttons import handle_hidden_buttons, check_val_for_hidden_buttons
from webapp.home.utils.node_store import dump_node_store
from webapp.home.utils.load_and_save import load_eml, save_both_formats, clear_taxonomy_imported_from_xml_flag, \
    taxonomy_inconsistent_with_ezeml
from webapp.home.utils.lists import list_geographic_coverages, list_temporal_coverages, list_taxonomic_coverages
from webapp.home.utils.create_nodes import create_geographic_coverage, create_temporal_coverage, \
    create_taxonomic_coverage
from webapp.home.utils.node_utils import add_child
from webapp.home.check_metadata import init_evaluation, format_tooltip

from webapp.views.coverage.taxonomy import (
    TaxonomySourceEnum, ITISTaxonomy, NCBITaxonomy, WORMSTaxonomy,
    load_taxonomic_coverage_csv_file, process_taxonomic_coverage_file
)

from webapp.auth.user_data import (
    get_document_uploads_folder_name, get_user_folder_name
)

from webapp.home.forms import is_dirty_form, init_form_md5, LoadDataForm
from webapp.views.coverage.forms import (
    GeographicCoverageForm,
    GeographicCoverageSelectForm,
    TemporalCoverageForm,
    TemporalCoverageSelectForm,
    TaxonomicCoverageForm,
    TaxonomicCoverageSelectForm,
    LoadTaxonomicCoverageForm
)

from webapp.buttons import *
from webapp.pages import *

from webapp.home.views import (
    select_post, compare_begin_end_dates, get_help, get_helps, set_current_page,
    secure_filename, allowed_data_file, encode_for_query_string, decode_from_query_string,
    reload_metadata
)
from webapp.home.log_usage import (
    actions,
    log_usage,
)

from metapype.eml import names
from metapype.model.node import Node


cov_bp = Blueprint('cov', __name__, template_folder='templates')


@cov_bp.route('/geographic_coverage_select/<filename>', methods=['GET', 'POST'])
@login_required
def geographic_coverage_select(filename=None):
    """
    Display a list of geographic coverages. The user can select one of the coverages to edit.
    """
    form = GeographicCoverageSelectForm(filename=filename)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = select_post(filename, form, form_dict,
                          'POST', PAGE_GEOGRAPHIC_COVERAGE_SELECT,
                          PAGE_INTELLECTUAL_RIGHTS,
                          PAGE_TEMPORAL_COVERAGE_SELECT,
                          PAGE_GEOGRAPHIC_COVERAGE, import_page=PAGE_IMPORT_GEO_COVERAGE)
        return redirect(url)

    # Process GET
    gc_list = []
    title = "Geographic Coverage"

    eml_node = load_eml(filename=filename)
    if eml_node:
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            gc_list = list_geographic_coverages(eml_node, dataset_node)

    # Get the tooltip for the status badge
    init_evaluation(eml_node, filename)
    tooltip = format_tooltip(None, 'geographic_coverage')

    set_current_page('geographic_coverage')
    help = get_helps(['geographic_coverages', 'geographic_coverages_csv_file'])
    return render_template('geographic_coverage_select.html', title=title, filename=filename,
                           gc_list=gc_list, form=form, help=help, tooltip=tooltip)


@cov_bp.route('/load_geo_coverage/<filename>', methods=['GET', 'POST'])
@login_required
def load_geo_coverage(filename):
    """
    Route for loading a geographic coverage from a CSV file.
    """

    def load_geo_coverage_from_csv(csv_filename, filename):
        """
        Load a geographic coverage from a CSV file.
        """

        def add_geo_coverage_node(eml_node, description, north, south, east, west, amin=None, amax=None, aunits=None):
            dataset_node = eml_node.find_child(names.DATASET)
            if not dataset_node:
                dataset_node = Node(names.DATASET)

            coverage_node = dataset_node.find_child(names.COVERAGE)
            if not coverage_node:
                coverage_node = Node(names.COVERAGE, parent=dataset_node)
                add_child(dataset_node, coverage_node)

            gc_node = Node(names.GEOGRAPHICCOVERAGE, parent=coverage_node)
            add_child(coverage_node, gc_node)

            create_geographic_coverage(
                gc_node, description, west, east, north, south, amin, amax, aunits)

        eml_node = load_eml(filename=filename)

        data_frame = pd.read_csv(csv_filename, comment='#', encoding='utf8')

        required_columns = ['geographicDescription',
                            'northBoundingCoordinate',
                            'southBoundingCoordinate',
                            'eastBoundingCoordinate',
                            'westBoundingCoordinate']
        optional_columns = ['minimumAltitude',
                            'maximumAltitude',
                            'altitudeUnits']
        has_required_columns = False
        has_optional_columns = False

        if list(data_frame.columns) == required_columns:
            has_required_columns = True
        if list(data_frame.columns) == required_columns + optional_columns:
            has_required_columns = True
            has_optional_columns = True

        if not has_required_columns:
            raise InvalidHeaderRow('Geographic coverage file does not have expected column names.')

        expected_types_error_msg = 'Geographic coverage file does not have expected variable types in columns. Note that ' \
                                   'numerical values must be written with a decimal point.'
        if not has_optional_columns:
            if list(data_frame.dtypes)[1:] != [np.float64, np.float64, np.float64, np.float64]:
                raise UnexpectedDataTypes(expected_types_error_msg)
        else:
            if list(data_frame.dtypes)[1:-1] != [np.float64, np.float64, np.float64, np.float64, np.float64,
                                                 np.float64]:
                raise UnexpectedDataTypes(expected_types_error_msg)

        # Check for missing values
        for column in required_columns:
            if data_frame[column].isnull().values.any():
                raise UnexpectedDataTypes(f'Geographic coverage file contains missing values in column: {column}.')

        # List looks good. Clear the existing geo coverage nodes before adding the new ones.
        geo_coverage_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.COVERAGE, names.GEOGRAPHICCOVERAGE])
        for geo_coverage_node in geo_coverage_nodes:
            parent = geo_coverage_node.parent
            if parent:
                parent.remove_child(geo_coverage_node)

        for index, row in data_frame.iterrows():
            if has_optional_columns:
                add_geo_coverage_node(eml_node, row[0], row[1], row[2], row[3], row[4],
                                      str(row[5]) if not pd.isna(row[5]) else None,
                                      str(row[6]) if not pd.isna(row[6]) else None,
                                      str(row[7]) if not pd.isna(row[7]) else None)
            else:
                add_geo_coverage_node(eml_node, row[0], row[1], row[2], row[3], row[4])

        save_both_formats(filename=filename, eml_node=eml_node)

    form = LoadDataForm()
    document = current_user.get_filename()
    uploads_folder = get_document_uploads_folder_name()

    # Process POST
    if request.method == 'POST' and BTN_CANCEL in request.form:
        url = url_for(PAGE_GEOGRAPHIC_COVERAGE_SELECT, filename=filename)
        return redirect(url)

    if request.method == 'POST' and form.validate_on_submit():

        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        new_page = None
        if form_dict:
            for key in form_dict:
                val = form_dict[key][0]  # value is the first list element
                new_page = check_val_for_hidden_buttons(val, new_page)

        if new_page:
            url = url_for(new_page, filename=filename)
            return redirect(url)

        # Check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)

        file = request.files['file']
        if file:
            filename = secure_filename(file.filename)

            if filename is None or filename == '':
                flash('No selected file', 'error')
            elif allowed_data_file(filename):
                filepath = os.path.join(uploads_folder, filename)
                file.save(filepath)
                data_file = filename
                data_file_path = f'{uploads_folder}/{data_file}'
                try:
                    load_geo_coverage_from_csv(data_file_path, document)
                    log_usage(actions['LOAD_GEOGRAPHIC_COVERAGE'], filename)
                    flash(f'Loaded {data_file}')
                    try:
                        os.remove(data_file_path)
                    except FileNotFoundError as e:
                        pass
                except InvalidHeaderRow as e:
                    flash(f'Invalid header in {data_file}: {e}')
                except UnexpectedDataTypes as ex:
                    flash(f'Load CSV file failed. {ex.args[0]}', 'error')
                return redirect(url_for(PAGE_GEOGRAPHIC_COVERAGE_SELECT, filename=document))

    # Process GET
    reload_metadata()  # So check_metadata status is correct
    help = [get_help('geographic_coverages_csv_file')]
    return render_template('load_geo_coverage.html',
                           form=form,
                           help=help)


@cov_bp.route('/preview_all_geographic_coverage/<filename>', methods=['GET', 'POST'])
@login_required
def preview_all_geographic_coverage(filename=None):
    """
    Route for displaying a preview map showing all geographic coverages
    """
    from webapp.config import Config

    API_KEY = Config.GOOGLE_MAP_API_KEY

    # Process GET
    eml_node = load_eml(filename=filename)
    gc_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.COVERAGE, names.GEOGRAPHICCOVERAGE])
    bounding_boxes = []

    for gc_node in gc_nodes:
        bounding_coordinates = gc_node.find_child(names.BOUNDINGCOORDINATES)
        if bounding_coordinates:
            west = bounding_coordinates.find_child(names.WESTBOUNDINGCOORDINATE).content
            east = bounding_coordinates.find_child(names.EASTBOUNDINGCOORDINATE).content
            north = bounding_coordinates.find_child(names.NORTHBOUNDINGCOORDINATE).content
            south = bounding_coordinates.find_child(names.SOUTHBOUNDINGCOORDINATE).content
            bounds = { 'north': float(north), 'south': float(south), 'east': float(east), 'west': float(west) }
            bounding_boxes.append(bounds)

    return render_template('geographic_coverage_preview.html', title='Preview Geographic Coverage',
                           api_key=API_KEY, locations=bounding_boxes)


@cov_bp.route('/preview_geographic_coverage/<filename>/<node_id>', methods=['GET', 'POST'])
@login_required
def preview_geographic_coverage(filename=None, node_id=None):
    """
    Route for displaying a preview map for a geographic coverage
    """
    from webapp.config import Config

    API_KEY = Config.GOOGLE_MAP_API_KEY

    # Process GET
    gc_node = None
    if node_id != '1':
        eml_node = load_eml(filename=filename)
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            coverage_node = dataset_node.find_child(names.COVERAGE)
            if coverage_node:
                gc_nodes = coverage_node.find_all_children(names.GEOGRAPHICCOVERAGE)
                if gc_nodes:
                    for gc_node in gc_nodes:
                        if node_id == gc_node.id:
                            break
    if node_id == gc_node.id:
        bounding_coordinates = gc_node.find_child(names.BOUNDINGCOORDINATES)
        if bounding_coordinates:
            west = bounding_coordinates.find_child(names.WESTBOUNDINGCOORDINATE).content
            east = bounding_coordinates.find_child(names.EASTBOUNDINGCOORDINATE).content
            north = bounding_coordinates.find_child(names.NORTHBOUNDINGCOORDINATE).content
            south = bounding_coordinates.find_child(names.SOUTHBOUNDINGCOORDINATE).content
            bounds = { 'north': float(north), 'south': float(south), 'east': float(east), 'west': float(west) }
            return render_template('geographic_coverage_preview.html', title='Preview Geographic Coverage',
                                   api_key=API_KEY, locations=[bounds])


@cov_bp.route('/geographic_coverage/<filename>/<node_id>', methods=['GET', 'POST'])
@login_required
def geographic_coverage(filename=None, node_id=None):
    """
    Route for displaying/editing a geographic coverage
    """
    form = GeographicCoverageForm(filename=filename)

    # Process POST
    if request.method == 'POST' and BTN_CANCEL in request.form:
        url = url_for(PAGE_GEOGRAPHIC_COVERAGE_SELECT, filename=filename)
        return redirect(url)

    if request.method == 'POST' and form.validate_on_submit():
        submit_type = None
        if is_dirty_form(form):
            submit_type = 'Save Changes'

        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        new_page = PAGE_GEOGRAPHIC_COVERAGE_SELECT
        this_page = PAGE_GEOGRAPHIC_COVERAGE
        if form_dict:
            for key in form_dict:
                val = form_dict[key][0]  # value is the first list element
                new_page = check_val_for_hidden_buttons(val, new_page)

        url = url_for(new_page, filename=filename)

        if submit_type == 'Save Changes':
            eml_node = load_eml(filename=filename)

            dataset_node = eml_node.find_child(names.DATASET)
            if not dataset_node:
                dataset_node = Node(names.DATASET)

            coverage_node = dataset_node.find_child(names.COVERAGE)
            if not coverage_node:
                coverage_node = Node(names.COVERAGE, parent=dataset_node)
                add_child(dataset_node, coverage_node)

            geographic_description = form.geographic_description.data
            wbc = form.wbc.data if form.wbc.data is not None else ''
            ebc = form.ebc.data if form.ebc.data is not None else ''
            nbc = form.nbc.data if form.nbc.data is not None else ''
            sbc = form.sbc.data if form.sbc.data is not None else ''
            amin = form.amin.data if form.amin.data is not None else ''
            amax = form.amax.data if form.amax.data is not None else ''
            aunits = form.aunits.data if form.aunits.data is not None else ''

            gc_node = Node(names.GEOGRAPHICCOVERAGE, parent=coverage_node)

            create_geographic_coverage(
                gc_node,
                geographic_description,
                wbc, ebc, nbc, sbc, amin, amax, aunits)

            if node_id and len(node_id) != 1:
                old_gc_node = Node.get_node_instance(node_id)
                if old_gc_node:
                    coverage_parent_node = old_gc_node.parent
                    coverage_parent_node.replace_child(old_gc_node, gc_node)
                else:
                    msg = f"No node found in the node store with node id {node_id}"
                    dump_node_store(eml_node, 'geographic_coverage')
                    raise NodeWithGivenIdNotFound(msg)
            else:
                add_child(coverage_node, gc_node)

            if nbc and sbc and nbc < sbc:
                flash('North should be greater than or equal to South', 'error')
                url = (url_for(PAGE_GEOGRAPHIC_COVERAGE, filename=filename, node_id=gc_node.id))

            if ebc and wbc and ebc < wbc:
                flash('East should be greater than or equal to West', 'error')
                url = (url_for(PAGE_GEOGRAPHIC_COVERAGE, filename=filename, node_id=gc_node.id))

            save_both_formats(filename=filename, eml_node=eml_node)

        return redirect(url)

    # Process GET
    gc_node = None
    if node_id != '1':
        eml_node = load_eml(filename=filename)
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            coverage_node = dataset_node.find_child(names.COVERAGE)
            if coverage_node:
                gc_nodes = coverage_node.find_all_children(names.GEOGRAPHICCOVERAGE)
                if gc_nodes:
                    for gc_node in gc_nodes:
                        if node_id == gc_node.id:
                            populate_geographic_coverage_form(form, gc_node)

    # Get the tooltip for the status badge
    if gc_node:
        init_evaluation(eml_node, filename)
        tooltip = format_tooltip(gc_node)
    else:
        tooltip = ''

    set_current_page('geographic_coverage')
    help = get_helps(['geographic_coverages', 'geographic_description', 'bounding_coordinates', 'bounding_altitudes'])
    return render_template('geographic_coverage.html', title='Geographic Coverage', form=form, help=help,
                           node_id=node_id, tooltip=tooltip)


def populate_geographic_coverage_form(form: GeographicCoverageForm, node: Node):
    """
    Populate the geographic coverage form with values from the node
    """
    geographic_description_node = node.find_child(names.GEOGRAPHICDESCRIPTION)
    if geographic_description_node:
        form.geographic_description.data = geographic_description_node.content

    wbc_node = node.find_single_node_by_path([
        names.BOUNDINGCOORDINATES,
        names.WESTBOUNDINGCOORDINATE
    ])
    if wbc_node:
        form.wbc.data = wbc_node.content
    ebc_node = node.find_single_node_by_path([
        names.BOUNDINGCOORDINATES,
        names.EASTBOUNDINGCOORDINATE
    ])
    if ebc_node:
        form.ebc.data = ebc_node.content
    nbc_node = node.find_single_node_by_path([
        names.BOUNDINGCOORDINATES,
        names.NORTHBOUNDINGCOORDINATE
    ])
    if nbc_node:
        form.nbc.data = nbc_node.content
    sbc_node = node.find_single_node_by_path([
        names.BOUNDINGCOORDINATES,
        names.SOUTHBOUNDINGCOORDINATE
    ])
    if sbc_node:
        form.sbc.data = sbc_node.content

    amin_node = node.find_single_node_by_path([
        names.BOUNDINGCOORDINATES,
        names.BOUNDINGALTITUDES,
        names.ALTITUDEMINIMUM
    ])
    if amin_node:
        form.amin.data = amin_node.content

    amax_node = node.find_single_node_by_path([
        names.BOUNDINGCOORDINATES,
        names.BOUNDINGALTITUDES,
        names.ALTITUDEMAXIMUM
    ])
    if amax_node:
        form.amax.data = amax_node.content

    aunits_node = node.find_single_node_by_path([
        names.BOUNDINGCOORDINATES,
        names.BOUNDINGALTITUDES,
        names.ALTITUDEUNITS
    ])
    if aunits_node:
        form.aunits.data = aunits_node.content

    init_form_md5(form)


@cov_bp.route('/temporal_coverage_select/<filename>', methods=['GET', 'POST'])
@login_required
def temporal_coverage_select(filename=None):
    """
    Display a list of temporal coverages. The user can select one of the coverages to edit.
    """
    form = TemporalCoverageSelectForm(filename=filename)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = select_post(filename, form, form_dict,
                          'POST', PAGE_TEMPORAL_COVERAGE_SELECT,
                          PAGE_GEOGRAPHIC_COVERAGE_SELECT,
                          PAGE_TAXONOMIC_COVERAGE_SELECT,
                          PAGE_TEMPORAL_COVERAGE)
        return redirect(url)

    # Process GET
    title = "Temporal Coverage"
    tc_list = []

    eml_node = load_eml(filename=filename)
    if eml_node:
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            tc_list = list_temporal_coverages(eml_node, dataset_node)

    # Get the tooltip for the status badge
    init_evaluation(eml_node, filename)
    tooltip = format_tooltip(None, 'temporal_coverage')

    set_current_page('temporal_coverage')
    help = [get_help('temporal_coverages')]
    return render_template('temporal_coverage_select.html', title=title,
                           tc_list=tc_list, form=form, help=help, tooltip=tooltip)


@cov_bp.route('/temporal_coverage/<filename>/<node_id>', methods=['GET', 'POST'])
@login_required
def temporal_coverage(filename=None, node_id=None):
    """
    Display a form for editing a temporal coverage.
    """
    form = TemporalCoverageForm(filename=filename)
    tc_node_id = node_id

    # Process POST
    if request.method == 'POST' and BTN_CANCEL in request.form:
        url = url_for(PAGE_TEMPORAL_COVERAGE_SELECT, filename=filename)
        return redirect(url)

    if request.method == 'POST' and form.validate_on_submit():
        save = False
        if is_dirty_form(form):
            save = True

        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        new_page = PAGE_TEMPORAL_COVERAGE_SELECT
        if form_dict:
            for key in form_dict:
                val = form_dict[key][0]  # value is the first list element
                new_page = check_val_for_hidden_buttons(val, new_page)

        url = url_for(new_page, filename=filename)

        if save:
            eml_node = load_eml(filename=filename)

            dataset_node = eml_node.find_child(names.DATASET)
            if not dataset_node:
                dataset_node = Node(names.DATASET)

            coverage_node = dataset_node.find_child(names.COVERAGE)
            if not coverage_node:
                coverage_node = Node(names.COVERAGE, parent=dataset_node)
                add_child(dataset_node, coverage_node)

            tc_node = Node(names.TEMPORALCOVERAGE, parent=coverage_node)

            begin_date_str = form.begin_date.data
            end_date_str = form.end_date.data
            create_temporal_coverage(tc_node, begin_date_str, end_date_str)

            if node_id and len(node_id) != 1:
                old_tc_node = Node.get_node_instance(node_id)
                if old_tc_node:
                    coverage_parent_node = old_tc_node.parent
                    coverage_parent_node.replace_child(old_tc_node, tc_node)
                else:
                    msg = f"No node found in the node store with node id {node_id}"
                    dump_node_store(eml_node, 'temporal_coverage')
                    raise NodeWithGivenIdNotFound(msg)
            else:
                add_child(coverage_node, tc_node)

            tc_node_id = tc_node.id

            flash_msg = compare_begin_end_dates(begin_date_str, end_date_str)
            if flash_msg:
                flash(flash_msg, 'error')
                url = (url_for(PAGE_TEMPORAL_COVERAGE, filename=filename, node_id=tc_node_id))

            save_both_formats(filename=filename, eml_node=eml_node)

        return redirect(url)

    # Process GET
    if node_id != '1':
        eml_node = load_eml(filename=filename)
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            coverage_node = dataset_node.find_child(names.COVERAGE)
            if coverage_node:
                tc_nodes = coverage_node.find_all_children(names.TEMPORALCOVERAGE)
                if tc_nodes:
                    for tc_node in tc_nodes:
                        if node_id == tc_node.id:
                            populate_temporal_coverage_form(form, tc_node)

    init_form_md5(form)

    set_current_page('temporal_coverage')
    return render_template('temporal_coverage.html', title='Temporal Coverage', form=form)


def populate_temporal_coverage_form(form: TemporalCoverageForm, node: Node):
    """
    Populate the temporal coverage form with values from the given node.
    """
    begin_date_node = node.find_single_node_by_path([
        names.RANGEOFDATES,
        names.BEGINDATE
    ])
    if begin_date_node:
        calendar_date_node = begin_date_node.find_child(names.CALENDARDATE)
        form.begin_date.data = calendar_date_node.content

        end_date_node = node.find_single_node_by_path([
            names.RANGEOFDATES,
            names.ENDDATE
        ])
        if end_date_node:
            calendar_date_node = end_date_node.find_child(names.CALENDARDATE)
            form.end_date.data = calendar_date_node.content
    else:
        single_date_time_node = node.find_child(names.SINGLEDATETIME)
        if single_date_time_node:
            calendar_date_node = single_date_time_node.find_child(names.CALENDARDATE)
            form.begin_date.data = calendar_date_node.content

    init_form_md5(form)


@cov_bp.route('/taxonomic_coverage_select/<filename>', methods=['GET', 'POST'])
@login_required
def taxonomic_coverage_select(filename=None):
    """
    Display a form for selecting a taxonomic coverage.
    """
    form = TaxonomicCoverageSelectForm(filename=filename)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        if BTN_CLEAR in form_dict:
            clear_taxonomic_coverage(filename)
            # Fall through to GET
        else:
            url = select_post(filename, form, form_dict,
                              'POST', PAGE_TAXONOMIC_COVERAGE_SELECT,
                              PAGE_TEMPORAL_COVERAGE_SELECT,
                              PAGE_MAINTENANCE, PAGE_TAXONOMIC_COVERAGE,
                              import_page=PAGE_IMPORT_TAXONOMIC_COVERAGE)
            return redirect(url)

    # Process GET
    title = "Taxonomic Coverage"
    txc_list = []

    eml_node = load_eml(filename=filename)
    if eml_node:
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            if not taxonomy_inconsistent_with_ezeml(eml_node, filename):
                txc_list = list_taxonomic_coverages(eml_node, dataset_node)

    # Get the tooltip for the status badge
    init_evaluation(eml_node, filename)
    tooltip = format_tooltip(None, section='taxonomic_coverage')

    set_current_page('taxonomic_coverage')
    help = [get_help('taxonomic_coverages'), get_help('taxonomy_imported_from_xml')]
    return render_template('taxonomic_coverage_select.html', title=title,
                           txc_list=txc_list,
                           imported_from_xml=taxonomy_inconsistent_with_ezeml(eml_node, filename),
                           form=form, help=help, tooltip=tooltip)


def clear_taxonomic_coverage(package_name):
    # When user selects Clear Taxonomic Coverage to get rid of coverage imported from XML, we delete it and
    #  set the flag that says its OK for ezEML to handle even though the package was imported from XML.
    eml_node = load_eml(filename=package_name)
    coverage_node = eml_node.find_single_node_by_path([names.DATASET, names.COVERAGE])
    if coverage_node:
        taxonomic_coverage_nodes = coverage_node.find_all_children(names.TAXONOMICCOVERAGE)
        for taxonomic_coverage_node in taxonomic_coverage_nodes:
            webapp.home.utils.node_utils.remove_child(taxonomic_coverage_node)
            Node.delete_node_instance(taxonomic_coverage_node.id)
        clear_taxonomy_imported_from_xml_flag(eml_node, package_name)
        save_both_formats(filename=package_name, eml_node=eml_node)


def fill_taxonomic_coverage(taxon, source_type, source_name, row=None, processing_csv_file=False):
    """
    Fill out the taxonomic hierarchy for the given taxon using the specified taxonomic authority (source_type).

    Raise a TaxonNotFound exception if the hierarchy cannot be filled. The TaxonNotFound exception is includes
    relevant error message text.
    """
    # taxon = form.taxon_value.data
    hierarchy = []
    if not taxon:
        return hierarchy

    if source_type == TaxonomySourceEnum.ITIS:
        source = ITISTaxonomy()
        source.name = 'ITIS'
    elif source_type == TaxonomySourceEnum.NCBI:
        source = NCBITaxonomy()
        source.name = 'NCBI'
    elif source_type == TaxonomySourceEnum.WORMS:
        source = WORMSTaxonomy()
        source.name = 'WORMS'
    if not source:
        raise ValueError('No source specified')
    try:
        hierarchy = source.fill_common_names(source.fill_hierarchy(taxon))
    except Exception as err:
        err_msg = 'A network error occurred. Please try again, or try a different taxonomic authority.'
        if source.name == 'ITIS':
            err_msg += ' ITIS seems especially prone to network timeout errors.'
        raise ValueError(err_msg) from err
    if not hierarchy:
        if processing_csv_file:
            raise TaxonNotFound(f'Row {row}: Taxon "{taxon}" - Not found in authority {source.name}. Please check that you'
                                f' have used the taxon\'s scientific name. To include "{taxon}" in your metadata without'
                                f' querying {source.name}, specify a taxon rank for "{taxon}" in the CSV file.')
        else:
            raise TaxonNotFound(f'Taxon "{taxon}" was not found in authority {source.name}. Please check that you'
                                f' have used the taxon\'s scientific name. To include "{taxon}" in your metadata'
                                f' without querying {source.name}, specify a taxon rank and click "Save and Continue".'
                                f' Alternatively, try again using a different taxonomic authority.')
    return hierarchy


@cov_bp.route('/load_taxonomic_coverage/<filename>', methods=['GET', 'POST'])
@login_required
def load_taxonomic_coverage(filename):
    """
    Route for loading taxonomic coverage from a CSV file.
    """

    def save_uploaded_taxonomic_coverage(eml_node, hierarchies, general_coverages, global_authority):
        """
        Save the taxonomic coverage imported from a CSV file in the EML document.
        """
        dataset_node = eml_node.find_child(names.DATASET)
        if not dataset_node:
            dataset_node = Node(names.DATASET)

        coverage_node = dataset_node.find_child(names.COVERAGE)
        if not coverage_node:
            coverage_node = Node(names.COVERAGE, parent=dataset_node)
            add_child(dataset_node, coverage_node)

        for hierarchy, general_coverage in zip(hierarchies, general_coverages):
            if hierarchy is None:
                continue

            # Each hierarchy gets its own taxonomic coverage node. There are other ways to do this, but this is how ezEML does it.
            taxonomic_coverage_node = Node(names.TAXONOMICCOVERAGE, parent=coverage_node)
            add_child(coverage_node, taxonomic_coverage_node)

            create_taxonomic_coverage(
                taxonomic_coverage_node,
                general_coverage,
                hierarchy,
                global_authority)

    form = LoadTaxonomicCoverageForm()
    document, eml_node = reload_metadata()
    uploads_folder = get_document_uploads_folder_name()

    # Process POST
    if request.method == 'POST' and BTN_CANCEL in request.form:
        url = url_for(PAGE_TAXONOMIC_COVERAGE_SELECT, filename=filename)
        return redirect(url)

    if request.method == 'POST' and form.validate_on_submit():

        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        new_page = None
        if form_dict:
            for key in form_dict:
                val = form_dict[key][0]  # value is the first list element
                new_page = check_val_for_hidden_buttons(val, new_page)

        if new_page:
            url = url_for(new_page, filename=filename)
            return redirect(url)

        # Check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)

        delimiter = form.delimiter.data
        quote_char = form.quote.data
        source = form.taxonomic_authority.data

        file = request.files['file']
        if file:
            filename = secure_filename(file.filename)

            if filename is None or filename == '':
                flash('No selected file', 'error')
            elif allowed_data_file(filename):
                filepath = os.path.join(uploads_folder, filename)
                file.save(filepath)
                data_file = filename
                data_file_path = f'{uploads_folder}/{data_file}'
                try:
                    errors = None
                    log_usage(actions['LOAD_TAXONOMIC_COVERAGE'], filename)
                    global_authority = source
                    taxa = load_taxonomic_coverage_csv_file(data_file_path, delimiter, quote_char)
                    hierarchies, general_coverages, errors = process_taxonomic_coverage_file(taxa, global_authority)
                    flash(f'Loaded {data_file}')
                    if hierarchies:
                        eml_node = load_eml(filename=document)
                        save_uploaded_taxonomic_coverage(eml_node, hierarchies, general_coverages, global_authority)
                        save_both_formats(filename=document, eml_node=eml_node)

                except InvalidHeaderRow as err:
                    flash(f'CSV file does not have the expected header row.', 'error')
                except ValueError as ex:
                    flash(f'Load CSV file failed. {ex.args[0]}', 'error')

                try:
                    os.remove(data_file_path)
                except FileNotFoundError as e:
                    pass

                if errors:
                    # Save errors to a file
                    user_path = get_user_folder_name()
                    work_path = os.path.join(user_path, 'zip_temp')
                    if not os.path.exists(work_path):
                        os.makedirs(work_path)
                    filepath = os.path.join(work_path, "taxonomic_coverage_errors.txt")
                    with open(filepath, 'w') as f:
                        for error in errors:
                            f.write(f'{error}\r')

                    return redirect(url_for(PAGE_LOAD_TAXONOMIC_COVERAGE_2))
                else:
                    return redirect(url_for(PAGE_TAXONOMIC_COVERAGE_SELECT, filename=document))

    # Process GET
    help = [get_help('load_taxonomic_coverage')]
    return render_template('load_taxonomic_coverage.html',
                           form=form,
                           help=help)


@cov_bp.route('/load_taxonomic_coverage_2/', methods=['GET', 'POST'])
@login_required
def load_taxonomic_coverage_2():
    """
    Route to display errors from loading taxonomic coverage from a CSV file.
    """
    # Read errors from file
    user_path = get_user_folder_name()
    work_path = os.path.join(user_path, 'zip_temp')
    filepath = os.path.join(work_path, "taxonomic_coverage_errors.txt")
    errors = ''
    try:
        with open(filepath, 'r') as f:
            errors = f.readlines()
    except FileNotFoundError:
        pass
    shutil.rmtree(work_path, ignore_errors=True)

    reload_metadata()
    return render_template('load_taxonomic_coverage_2.html',
                           errors=errors)


@cov_bp.route('/taxonomic_coverage/<filename>/<node_id>', methods=['GET', 'POST'])
@cov_bp.route('/taxonomic_coverage/<filename>/<node_id>/<taxon>', methods=['GET', 'POST'])
@login_required
def taxonomic_coverage(filename=None, node_id=None, taxon=None):
    """
    Route for editing a taxonomic coverage element.
    """
    form = TaxonomicCoverageForm(filename=filename)

    # Process POST
    if request.method == 'POST' and BTN_CANCEL in request.form:
        url = url_for(PAGE_TAXONOMIC_COVERAGE_SELECT, filename=filename)
        return redirect(url)

    if request.method == 'POST' and form.validate_on_submit():
        save = False
        if is_dirty_form(form):
            save = True
        # flash(f'save: {save}')

        form_value = request.form
        have_links = False

        if 'Fill' in form_value:
            source = form.taxonomic_authority.data
            if source == 'ITIS':
                source_type = TaxonomySourceEnum.ITIS
            elif source == 'NCBI':
                    source_type = TaxonomySourceEnum.NCBI
            elif source == "WORMS":
                source_type = TaxonomySourceEnum.WORMS
            try:
                source_name = ''
                for choice in form.taxonomic_authority.choices:
                    if choice[0] == source:
                        source_name = choice[1]
                        break
                hierarchy = fill_taxonomic_coverage(form.taxon_value.data, source_type, source_name)
                if hierarchy:
                    log_usage(actions['FILL_TAXONOMIC_HIERARCHY'], form.taxon_value.data, source_name)
                    # set the taxon rank dropdown appropriately
                    rank = hierarchy[0][0].capitalize()
                    if (rank, rank) in form.taxon_rank.choices:
                        form.taxon_rank.data = rank
                    # see if we should display a Links column
                    for taxon in hierarchy:
                        if taxon[4]:
                            have_links = True
                            break
            except ValueError as e:
                flash(str(e), 'error')
                hierarchy = [(form.taxon_rank.data, form.taxon_value.data, '', '')]
            except TaxonNotFound as e:
                flash(str(e), 'error')
                hierarchy = [(form.taxon_rank.data, form.taxon_value.data, '', '')]
            form.hierarchy.data = hierarchy
            form.hidden_taxon_rank.data = form.taxon_rank.data
            form.hidden_taxon_value.data = form.taxon_value.data
            form.hidden_taxonomic_authority.data = form.taxonomic_authority.data
            help = get_helps(['taxonomic_coverage_fill_hierarchy'])

            return render_template('taxonomic_coverage.html', title='Taxonomic Coverage', form=form,
                                   hierarchy=hierarchy,
                                   taxon_rank=form.taxon_rank.data,
                                   taxon_value=form.taxon_value.data,
                                   taxonomic_authority=form.taxonomic_authority.data,
                                   node_id=node_id,
                                   help=help,
                                   have_links=have_links)

        form_dict = form_value.to_dict(flat=False)
        new_page = PAGE_TAXONOMIC_COVERAGE_SELECT
        if form_dict:
            for key in form_dict:
                val = form_dict[key][0]  # value is the first list element
                new_page = check_val_for_hidden_buttons(val, new_page)

        if save:
            if not form.taxon_value.data and not form.taxon_rank.data:
                return redirect(url_for(new_page, filename=filename))

            submitted_hierarchy = form_value.get('hierarchy')
            if isinstance(form_value.get('hierarchy'), str) and form_value.get('hierarchy'):
                # convert hierarchy string to list
                submitted_hierarchy = ast.literal_eval(form_value.get('hierarchy'))

                # if we're fixing up a failed hierarchy, we take the entered values as gospel
                if len(submitted_hierarchy) == 1:
                    hierarchy = list(submitted_hierarchy[0])
                    if form.taxon_rank.data:
                        hierarchy[0] = form.taxon_rank.data
                    if form.taxon_value.data:
                        hierarchy[1] = form.taxon_value.data
                    submitted_hierarchy = [tuple(hierarchy)]

                form.hierarchy.data = submitted_hierarchy

            # if we're saving after doing 'Fill Hierarchy', fill in the values we've been passed
            if form_value.get('hidden_taxon_rank'):
                form.taxon_rank.data = form_value.get('hidden_taxon_rank')
                form.taxon_value.data = form_value.get('hidden_taxon_value')
                form.taxonomic_authority.data = form_value.get('hidden_taxonomic_authority')
            elif not submitted_hierarchy:
                # we don't have a hierarchy, so construct a fake hierarchy to be used by create_taxonomic_coverage()
                form.hierarchy.data = [(
                    form_value.get('taxon_rank'),
                    form_value.get('taxon_value'),
                    '',
                    '',
                    '',
                    ''
                )]

            if not form_value.get('taxon_rank'):
                flash('Taxon Rank is required.', 'error')
                return redirect(url_for(PAGE_TAXONOMIC_COVERAGE, filename=filename, node_id=node_id, taxon=form.taxon_value.data))

            eml_node = load_eml(filename=filename)

            dataset_node = eml_node.find_child(names.DATASET)
            if not dataset_node:
                dataset_node = Node(names.DATASET)

            coverage_node = dataset_node.find_child(names.COVERAGE)
            if not coverage_node:
                coverage_node = Node(names.COVERAGE, parent=dataset_node)
                add_child(dataset_node, coverage_node)

            txc_node = Node(names.TAXONOMICCOVERAGE, parent=coverage_node)

            create_taxonomic_coverage(
                txc_node,
                form.general_taxonomic_coverage.data,
                form.hierarchy.data,
                form.taxonomic_authority.data)

            if node_id and len(node_id) != 1:
                old_txc_node = Node.get_node_instance(node_id)
                if old_txc_node:
                    coverage_parent_node = old_txc_node.parent
                    coverage_parent_node.replace_child(old_txc_node, txc_node)
                else:
                    msg = f"No node found in the node store with node id {node_id}"
                    dump_node_store(eml_node, 'taxonomic_coverage')
                    raise NodeWithGivenIdNotFound(msg)
            else:
                add_child(coverage_node, txc_node)

            save_both_formats(filename=filename, eml_node=eml_node)

        return redirect(url_for(new_page, filename=filename))

    # Process GET
    have_links = False
    txc_node = None
    if node_id == '1':
        if taxon:
            form.taxon_value.data = taxon
    else:
        eml_node = load_eml(filename=filename)
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            coverage_node = dataset_node.find_child(names.COVERAGE)
            if coverage_node:
                txc_nodes = coverage_node.find_all_children(names.TAXONOMICCOVERAGE)
                if txc_nodes:
                    for txc_node in txc_nodes:
                        if node_id == txc_node.id:
                            have_links = populate_taxonomic_coverage_form(form, txc_node)

    init_form_md5(form)

    # Get the tooltip for the status badge
    if txc_node:
        init_evaluation(eml_node, filename)
        tooltip = format_tooltip(txc_node)
    else:
        tooltip = ''

    help = get_helps(['taxonomic_coverage_fill_hierarchy'])

    set_current_page('taxonomic_coverage')
    return render_template('taxonomic_coverage.html', title='Taxonomic Coverage', form=form,
                           hierarchy=form.hierarchy.data, have_links=have_links, help=help,
                           node_id=node_id, tooltip=tooltip)


def populate_taxonomic_coverage_form(form: TaxonomicCoverageForm, node: Node):
    """
    Populate the form with values from the given node.
    """

    def populate_taxonomic_coverage_form_aux(hierarchy, node: Node = None):
        """
        Auxiliary function to handle the recursion needed to populate the form with values from the given node.
        """
        if node:
            taxon_rank_name_node = node.find_child(names.TAXONRANKNAME)
            taxon_rank_value_node = node.find_child(names.TAXONRANKVALUE)
            taxon_common_name_node = node.find_child(names.COMMONNAME)
            taxon_id_node = node.find_child(names.TAXONID)

            if taxon_rank_name_node and taxon_rank_name_node.content:
                taxon_rank_name = taxon_rank_name_node.content
            else:
                taxon_rank_name = None
            if taxon_rank_value_node and taxon_rank_value_node.content:
                taxon_rank_value = taxon_rank_value_node.content
            else:
                taxon_rank_value = None
            if taxon_common_name_node:
                taxon_common_name = taxon_common_name_node.content
            else:
                taxon_common_name = ''
            if taxon_id_node:
                taxon_id = taxon_id_node.content
                provider_uri = taxon_id_node.attribute_value(names.PROVIDER)
            else:
                taxon_id = None
                provider_uri = None

            link = None
            provider = None
            if taxon_rank_name and taxon_rank_value:
                if taxon_id:
                    if provider_uri == "https://www.itis.gov":
                        link = f'https://itis.gov/servlet/SingleRpt/SingleRpt?search_topic=TSN&search_value={taxon_id}'
                        provider = 'ITIS'
                    elif provider_uri == "https://www.ncbi.nlm.nih.gov/taxonomy":
                        link = f'https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id={taxon_id}'
                        provider = 'NCBI'
                    elif provider_uri == "http://www.marinespecies.org":
                        link = f'http://marinespecies.org/aphia.php?p=taxdetails&id={taxon_id}'
                        provider = 'WORMS'
            hierarchy.append((taxon_rank_name, taxon_rank_value, taxon_common_name, taxon_id, link, provider))

            taxonomic_classification_node = node.find_child(names.TAXONOMICCLASSIFICATION)
            if taxonomic_classification_node:
                populate_taxonomic_coverage_form_aux(hierarchy, taxonomic_classification_node)

    general_taxonomic_coverage_node = node.find_child(names.GENERALTAXONOMICCOVERAGE)
    if general_taxonomic_coverage_node:
        form.general_taxonomic_coverage.data = general_taxonomic_coverage_node.content

    hierarchy = []
    taxonomic_classification_node = node.find_child(names.TAXONOMICCLASSIFICATION)
    populate_taxonomic_coverage_form_aux(hierarchy, taxonomic_classification_node)
    form.hierarchy.data = hierarchy[::-1]

    have_links = False
    if hierarchy:
        taxon_rank, taxon_value, _, _, link, authority = hierarchy[-1]
        # first_taxon = hierarchy[-1]
        form.taxon_value.data = taxon_value
        if taxon_rank:
            taxon_rank = taxon_rank.capitalize()
        if (taxon_rank, taxon_rank) in form.taxon_rank.choices:
            form.taxon_rank.data = taxon_rank
        if authority:
            form.taxonomic_authority.data = authority
        for *_, link, _ in hierarchy:
            if link:
                have_links = True
                break
    init_form_md5(form)
    return have_links
