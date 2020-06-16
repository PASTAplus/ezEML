from flask import (
    Blueprint, flash, render_template, redirect, request, url_for
)

from webapp.home.metapype_client import (
    add_child, load_eml, save_both_formats,
    list_geographic_coverages, create_geographic_coverage,
    create_temporal_coverage, list_temporal_coverages,
    create_taxonomic_coverage, list_taxonomic_coverages,
)

from webapp.home.forms import is_dirty_form, form_md5
from webapp.views.coverage.forms import (
    GeographicCoverageForm,
    GeographicCoverageSelectForm,
    TemporalCoverageForm,
    TemporalCoverageSelectForm,
    TaxonomicCoverageForm,
    TaxonomicCoverageSelectForm
)

from webapp.buttons import *
from webapp.pages import *

from webapp.home.views import select_post, compare_begin_end_dates, get_help
from metapype.eml import names
from metapype.model.node import Node
from webapp.home.views import set_current_page


cov_bp = Blueprint('cov', __name__, template_folder='templates')


@cov_bp.route('/geographic_coverage_select/<packageid>', methods=['GET', 'POST'])
def geographic_coverage_select(packageid=None):
    form = GeographicCoverageSelectForm(packageid=packageid)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = select_post(packageid, form, form_dict,
                          'POST', PAGE_GEOGRAPHIC_COVERAGE_SELECT,
                          PAGE_INTELLECTUAL_RIGHTS,
                          PAGE_TEMPORAL_COVERAGE_SELECT,
                          PAGE_GEOGRAPHIC_COVERAGE)
        return redirect(url)

    # Process GET
    gc_list = []
    title = "Geographic Coverage"

    eml_node = load_eml(packageid=packageid)
    if eml_node:
        dataset_node = eml_node.find_immediate_child(names.DATASET)
        if dataset_node:
            gc_list = list_geographic_coverages(dataset_node)

    set_current_page('geographic_coverage')
    help = [get_help('geographic_coverages')]
    return render_template('geographic_coverage_select.html', title=title,
                           gc_list=gc_list, form=form, help=help)


@cov_bp.route('/geographic_coverage/<packageid>/<node_id>', methods=['GET', 'POST'])
def geographic_coverage(packageid=None, node_id=None):
    form = GeographicCoverageForm(packageid=packageid)

    # Process POST
    if request.method == 'POST' and BTN_CANCEL in request.form:
        url = url_for(PAGE_GEOGRAPHIC_COVERAGE_SELECT, packageid=packageid)
        return redirect(url)

    if request.method == 'POST' and form.validate_on_submit():
        submit_type = None
        if is_dirty_form(form):
            submit_type = 'Save Changes'

        url = url_for(PAGE_GEOGRAPHIC_COVERAGE_SELECT, packageid=packageid)

        if submit_type == 'Save Changes':
            eml_node = load_eml(packageid=packageid)

            dataset_node = eml_node.find_immediate_child(names.DATASET)
            if not dataset_node:
                dataset_node = Node(names.DATASET)

            coverage_node = dataset_node.find_immediate_child(names.COVERAGE)
            if not coverage_node:
                coverage_node = Node(names.COVERAGE, parent=dataset_node)
                add_child(dataset_node, coverage_node)

            geographic_description = form.geographic_description.data
            wbc = form.wbc.data
            ebc = form.ebc.data
            nbc = form.nbc.data
            sbc = form.sbc.data

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

            if nbc and sbc and nbc < sbc:
                flash('North should be greater than or equal to South')
                url = (url_for(PAGE_GEOGRAPHIC_COVERAGE, packageid=packageid, node_id=gc_node.id))

            if ebc and wbc and ebc < wbc:
                flash('East should be greater than or equal to West')
                url = (url_for(PAGE_GEOGRAPHIC_COVERAGE, packageid=packageid, node_id=gc_node.id))

            save_both_formats(packageid=packageid, eml_node=eml_node)

        return redirect(url)

    # Process GET
    if node_id == '1':
        form.init_md5()
    else:
        eml_node = load_eml(packageid=packageid)
        dataset_node = eml_node.find_immediate_child(names.DATASET)
        if dataset_node:
            coverage_node = dataset_node.find_immediate_child(names.COVERAGE)
            if coverage_node:
                gc_nodes = coverage_node.find_all_children(names.GEOGRAPHICCOVERAGE)
                if gc_nodes:
                    for gc_node in gc_nodes:
                        if node_id == gc_node.id:
                            populate_geographic_coverage_form(form, gc_node)

    set_current_page('geographic_coverage')
    help = [get_help('geographic_coverages'), get_help('geographic_description'), get_help('bounding_coordinates')]
    return render_template('geographic_coverage.html', title='Geographic Coverage', form=form, help=help)


def populate_geographic_coverage_form(form: GeographicCoverageForm, node: Node):
    geographic_description_node = node.find_immediate_child(names.GEOGRAPHICDESCRIPTION)
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

    form.md5.data = form_md5(form)


@cov_bp.route('/temporal_coverage_select/<packageid>', methods=['GET', 'POST'])
def temporal_coverage_select(packageid=None):
    form = TemporalCoverageSelectForm(packageid=packageid)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = select_post(packageid, form, form_dict,
                          'POST', PAGE_TEMPORAL_COVERAGE_SELECT,
                          PAGE_GEOGRAPHIC_COVERAGE_SELECT,
                          PAGE_TAXONOMIC_COVERAGE_SELECT,
                          PAGE_TEMPORAL_COVERAGE)
        return redirect(url)

    # Process GET
    title = "Temporal Coverage"
    tc_list = []

    eml_node = load_eml(packageid=packageid)
    if eml_node:
        dataset_node = eml_node.find_immediate_child(names.DATASET)
        if dataset_node:
            tc_list = list_temporal_coverages(dataset_node)

    set_current_page('temporal_coverage')
    help = [get_help('temporal_coverages')]
    return render_template('temporal_coverage_select.html', title=title,
                           tc_list=tc_list, form=form, help=help)


@cov_bp.route('/temporal_coverage/<packageid>/<node_id>', methods=['GET', 'POST'])
def temporal_coverage(packageid=None, node_id=None):
    form = TemporalCoverageForm(packageid=packageid)
    tc_node_id = node_id

    # Process POST
    if request.method == 'POST' and BTN_CANCEL in request.form:
        url = url_for(PAGE_TEMPORAL_COVERAGE_SELECT, packageid=packageid)
        return redirect(url)

    if request.method == 'POST' and form.validate_on_submit():
        save = False
        if is_dirty_form(form):
            save = True
        # flash(f'save: {save}')

        url = url_for(PAGE_TEMPORAL_COVERAGE_SELECT, packageid=packageid)

        if save:
            eml_node = load_eml(packageid=packageid)

            dataset_node = eml_node.find_immediate_child(names.DATASET)
            if not dataset_node:
                dataset_node = Node(names.DATASET)

            coverage_node = dataset_node.find_immediate_child(names.COVERAGE)
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
                    raise Exception(msg)
            else:
                add_child(coverage_node, tc_node)

            tc_node_id = tc_node.id

            flash_msg = compare_begin_end_dates(begin_date_str, end_date_str)
            if flash_msg:
                flash(flash_msg)
                url = (url_for(PAGE_TEMPORAL_COVERAGE, packageid=packageid, node_id=tc_node_id))

            save_both_formats(packageid=packageid, eml_node=eml_node)

        return redirect(url)

    # Process GET
    if node_id == '1':
        form.init_md5()
    else:
        eml_node = load_eml(packageid=packageid)
        dataset_node = eml_node.find_immediate_child(names.DATASET)
        if dataset_node:
            coverage_node = dataset_node.find_immediate_child(names.COVERAGE)
            if coverage_node:
                tc_nodes = coverage_node.find_all_children(names.TEMPORALCOVERAGE)
                if tc_nodes:
                    for tc_node in tc_nodes:
                        if node_id == tc_node.id:
                            populate_temporal_coverage_form(form, tc_node)

    set_current_page('temporal_coverage')
    return render_template('temporal_coverage.html', title='Temporal Coverage', form=form)


def populate_temporal_coverage_form(form: TemporalCoverageForm, node: Node):
    begin_date_node = node.find_single_node_by_path([
        names.RANGEOFDATES,
        names.BEGINDATE
    ])
    if begin_date_node:
        calendar_date_node = begin_date_node.find_immediate_child(names.CALENDARDATE)
        form.begin_date.data = calendar_date_node.content

        end_date_node = node.find_single_node_by_path([
            names.RANGEOFDATES,
            names.ENDDATE
        ])
        if end_date_node:
            calendar_date_node = end_date_node.find_immediate_child(names.CALENDARDATE)
            form.end_date.data = calendar_date_node.content
    else:
        single_date_time_node = node.find_immediate_child(names.SINGLEDATETIME)
        if single_date_time_node:
            calendar_date_node = single_date_time_node.find_immediate_child(names.CALENDARDATE)
            form.begin_date.data = calendar_date_node.content

    form.md5.data = form_md5(form)


@cov_bp.route('/taxonomic_coverage_select/<packageid>', methods=['GET', 'POST'])
def taxonomic_coverage_select(packageid=None):
    form = TaxonomicCoverageSelectForm(packageid=packageid)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = select_post(packageid, form, form_dict,
                          'POST', PAGE_TAXONOMIC_COVERAGE_SELECT,
                          PAGE_TEMPORAL_COVERAGE_SELECT,
                          PAGE_MAINTENANCE, PAGE_TAXONOMIC_COVERAGE)
        return redirect(url)

    # Process GET
    title = "Taxonomic Coverage"
    txc_list = []

    eml_node = load_eml(packageid=packageid)
    if eml_node:
        dataset_node = eml_node.find_immediate_child(names.DATASET)
        if dataset_node:
            txc_list = list_taxonomic_coverages(dataset_node)

    set_current_page('taxonomic_coverage')
    help = [get_help('taxonomic_coverages')]
    return render_template('taxonomic_coverage_select.html', title=title,
                           txc_list=txc_list, form=form, help=help)


@cov_bp.route('/taxonomic_coverage/<packageid>/<node_id>', methods=['GET', 'POST'])
def taxonomic_coverage(packageid=None, node_id=None):
    form = TaxonomicCoverageForm(packageid=packageid)

    # Process POST
    if request.method == 'POST' and BTN_CANCEL in request.form:
        url = url_for(PAGE_TAXONOMIC_COVERAGE_SELECT, packageid=packageid)
        return redirect(url)

    if request.method == 'POST' and form.validate_on_submit():
        save = False
        if is_dirty_form(form):
            save = True
        flash(f'save: {save}')

        if save:
            eml_node = load_eml(packageid=packageid)

            dataset_node = eml_node.find_immediate_child(names.DATASET)
            if not dataset_node:
                dataset_node = Node(names.DATASET)

            coverage_node = dataset_node.find_immediate_child(names.COVERAGE)
            if not coverage_node:
                coverage_node = Node(names.COVERAGE, parent=dataset_node)
                add_child(dataset_node, coverage_node)

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

            save_both_formats(packageid=packageid, eml_node=eml_node)

        return redirect(url_for(PAGE_TAXONOMIC_COVERAGE_SELECT, packageid=packageid))

    # Process GET
    if node_id == '1':
        form.init_md5()
    else:
        eml_node = load_eml(packageid=packageid)
        dataset_node = eml_node.find_immediate_child(names.DATASET)
        if dataset_node:
            coverage_node = dataset_node.find_immediate_child(names.COVERAGE)
            if coverage_node:
                txc_nodes = coverage_node.find_all_children(names.TAXONOMICCOVERAGE)
                if txc_nodes:
                    for txc_node in txc_nodes:
                        if node_id == txc_node.id:
                            populate_taxonomic_coverage_form(form, txc_node)

    set_current_page('taxonomic_coverage')
    return render_template('taxonomic_coverage.html', title='Taxonomic Coverage', form=form)


def populate_taxonomic_coverage_form(form: TaxonomicCoverageForm, node: Node):
    general_taxonomic_coverage_node = node.find_immediate_child(names.GENERALTAXONOMICCOVERAGE)
    if general_taxonomic_coverage_node:
        form.general_taxonomic_coverage.data = general_taxonomic_coverage_node.content

    taxonomic_classification_node = node.find_immediate_child(names.TAXONOMICCLASSIFICATION)
    populate_taxonomic_coverage_form_aux(form, taxonomic_classification_node)

    form.md5.data = form_md5(form)


def populate_taxonomic_coverage_form_aux(form: TaxonomicCoverageForm, node: Node = None):
    if node:
        taxon_rank_name_node = node.find_immediate_child(names.TAXONRANKNAME)
        taxon_rank_value_node = node.find_immediate_child(names.TAXONRANKVALUE)
        taxon_common_name_node = node.find_immediate_child(names.COMMONNAME)

        if taxon_rank_name_node.content == 'Kingdom':
            form.kingdom_value.data = taxon_rank_value_node.content
            if taxon_common_name_node:
                form.kingdom_common_name.data = taxon_common_name_node.content
        elif taxon_rank_name_node.content == 'Phylum':
            form.phylum_value.data = taxon_rank_value_node.content
            if taxon_common_name_node:
                form.phylum_common_name.data = taxon_common_name_node.content
        elif taxon_rank_name_node.content == 'Class':
            form.class_value.data = taxon_rank_value_node.content
            if taxon_common_name_node:
                form.class_common_name.data = taxon_common_name_node.content
        elif taxon_rank_name_node.content == 'Order':
            form.order_value.data = taxon_rank_value_node.content
            if taxon_common_name_node:
                form.order_common_name.data = taxon_common_name_node.content
        elif taxon_rank_name_node.content == 'Family':
            form.family_value.data = taxon_rank_value_node.content
            if taxon_common_name_node:
                form.family_common_name.data = taxon_common_name_node.content
        elif taxon_rank_name_node.content == 'Genus':
            form.genus_value.data = taxon_rank_value_node.content
            if taxon_common_name_node:
                form.genus_common_name.data = taxon_common_name_node.content
        elif taxon_rank_name_node.content == 'Species':
            form.species_value.data = taxon_rank_value_node.content
            if taxon_common_name_node:
                form.species_common_name.data = taxon_common_name_node.content

        taxonomic_classification_node = node.find_immediate_child(names.TAXONOMICCLASSIFICATION)
        if taxonomic_classification_node:
            populate_taxonomic_coverage_form_aux(form, taxonomic_classification_node)
