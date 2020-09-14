import ast

from flask import (
    Blueprint, flash, render_template, redirect, request, url_for
)

from webapp.home.metapype_client import (
    add_child, load_eml, save_both_formats,
    list_geographic_coverages, create_geographic_coverage,
    create_temporal_coverage, list_temporal_coverages,
    create_taxonomic_coverage, list_taxonomic_coverages,
)

from webapp.views.coverage.taxonomy import (
    TaxonomySourceEnum, TaxonomySource, ITISTaxonomy, WORMSTaxonomy
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


@cov_bp.route('/geographic_coverage_select/<filename>', methods=['GET', 'POST'])
def geographic_coverage_select(filename=None):
    form = GeographicCoverageSelectForm(filename=filename)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = select_post(filename, form, form_dict,
                          'POST', PAGE_GEOGRAPHIC_COVERAGE_SELECT,
                          PAGE_INTELLECTUAL_RIGHTS,
                          PAGE_TEMPORAL_COVERAGE_SELECT,
                          PAGE_GEOGRAPHIC_COVERAGE)
        return redirect(url)

    # Process GET
    gc_list = []
    title = "Geographic Coverage"

    eml_node = load_eml(filename=filename)
    if eml_node:
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            gc_list = list_geographic_coverages(dataset_node)

    set_current_page('geographic_coverage')
    help = [get_help('geographic_coverages')]
    return render_template('geographic_coverage_select.html', title=title,
                           gc_list=gc_list, form=form, help=help)


@cov_bp.route('/geographic_coverage/<filename>/<node_id>', methods=['GET', 'POST'])
def geographic_coverage(filename=None, node_id=None):
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
        if form_dict:
            for key in form_dict:
                val = form_dict[key][0]  # value is the first list element

                if val == BTN_HIDDEN_NEW:
                    new_page = PAGE_CREATE
                    break
                elif val == BTN_HIDDEN_OPEN:
                    new_page = PAGE_OPEN
                    break
                elif val == BTN_HIDDEN_CLOSE:
                    new_page = PAGE_CLOSE
                    break

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
                url = (url_for(PAGE_GEOGRAPHIC_COVERAGE, filename=filename, node_id=gc_node.id))

            if ebc and wbc and ebc < wbc:
                flash('East should be greater than or equal to West')
                url = (url_for(PAGE_GEOGRAPHIC_COVERAGE, filename=filename, node_id=gc_node.id))

            save_both_formats(filename=filename, eml_node=eml_node)

        return redirect(url)

    # Process GET
    if node_id == '1':
        form.init_md5()
    else:
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

    set_current_page('geographic_coverage')
    help = [get_help('geographic_coverages'), get_help('geographic_description'), get_help('bounding_coordinates')]
    return render_template('geographic_coverage.html', title='Geographic Coverage', form=form, help=help)


def populate_geographic_coverage_form(form: GeographicCoverageForm, node: Node):
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

    form.md5.data = form_md5(form)


@cov_bp.route('/temporal_coverage_select/<filename>', methods=['GET', 'POST'])
def temporal_coverage_select(filename=None):
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
            tc_list = list_temporal_coverages(dataset_node)

    set_current_page('temporal_coverage')
    help = [get_help('temporal_coverages')]
    return render_template('temporal_coverage_select.html', title=title,
                           tc_list=tc_list, form=form, help=help)


@cov_bp.route('/temporal_coverage/<filename>/<node_id>', methods=['GET', 'POST'])
def temporal_coverage(filename=None, node_id=None):
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

                if val == BTN_HIDDEN_NEW:
                    new_page = PAGE_CREATE
                    break
                elif val == BTN_HIDDEN_OPEN:
                    new_page = PAGE_OPEN
                    break
                elif val == BTN_HIDDEN_CLOSE:
                    new_page = PAGE_CLOSE
                    break
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
                    raise Exception(msg)
            else:
                add_child(coverage_node, tc_node)

            tc_node_id = tc_node.id

            flash_msg = compare_begin_end_dates(begin_date_str, end_date_str)
            if flash_msg:
                flash(flash_msg)
                url = (url_for(PAGE_TEMPORAL_COVERAGE, filename=filename, node_id=tc_node_id))

            save_both_formats(filename=filename, eml_node=eml_node)

        return redirect(url)

    # Process GET
    if node_id == '1':
        form.init_md5()
    else:
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

    set_current_page('temporal_coverage')
    return render_template('temporal_coverage.html', title='Temporal Coverage', form=form)


def populate_temporal_coverage_form(form: TemporalCoverageForm, node: Node):
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

    form.md5.data = form_md5(form)


@cov_bp.route('/taxonomic_coverage_select/<filename>', methods=['GET', 'POST'])
def taxonomic_coverage_select(filename=None):
    form = TaxonomicCoverageSelectForm(filename=filename)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = select_post(filename, form, form_dict,
                          'POST', PAGE_TAXONOMIC_COVERAGE_SELECT,
                          PAGE_TEMPORAL_COVERAGE_SELECT,
                          PAGE_MAINTENANCE, PAGE_TAXONOMIC_COVERAGE)
        return redirect(url)

    # Process GET
    title = "Taxonomic Coverage"
    txc_list = []

    eml_node = load_eml(filename=filename)
    if eml_node:
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            txc_list = list_taxonomic_coverages(dataset_node)

    set_current_page('taxonomic_coverage')
    help = [get_help('taxonomic_coverages')]
    return render_template('taxonomic_coverage_select.html', title=title,
                           txc_list=txc_list, form=form, help=help)


def fill_taxonomic_coverage(taxon, source_type):
    # taxon = form.taxon_value.data
    hierarchy = []
    if not taxon:
        return hierarchy

    if source_type == TaxonomySourceEnum.ITIS:
        source = ITISTaxonomy()
    elif source_type == TaxonomySourceEnum.WORMS:
        source = WORMSTaxonomy()
    if not source:
        raise ValueError('No source specified')
    hierarchy = source.fill_common_names(source.fill_hierarchy(taxon))
    if not hierarchy:
        raise ValueError(f'Taxon {taxon} not found')
    return hierarchy


@cov_bp.route('/taxonomic_coverage/<filename>/<node_id>', methods=['GET', 'POST'])
def taxonomic_coverage(filename=None, node_id=None):
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

        if 'Fill' in form_value:
            source = form.taxonomic_authority.data
            if source == 'ITIS':
                source_type = TaxonomySourceEnum.ITIS
            elif source == "WORMS":
                source_type = TaxonomySourceEnum.WORMS
            try:
                hierarchy = fill_taxonomic_coverage(form.taxon_value.data, source_type)
                # set the taxon rank dropdown appropriately
                if hierarchy:
                    rank = hierarchy[0][0]
                    if (rank, rank) in form.taxon_rank.choices:
                        form.taxon_rank.data = rank
            except ValueError as e:
                flash(str(e))
                hierarchy = [(form.taxon_rank.data, form.taxon_value.data, '', '')]
            form.hierarchy.data = hierarchy
            form.hidden_taxon_rank.data = form.taxon_rank.data
            form.hidden_taxon_value.data = form.taxon_value.data
            form.hidden_taxonomic_authority.data = form.taxonomic_authority.data

            return render_template('taxonomic_coverage_3.html', title='Taxonomic Coverage', form=form,
                                   hierarchy=hierarchy,
                                   taxon_rank=form.taxon_rank.data,
                                   taxon_value=form.taxon_value.data,
                                   taxonomic_authority=form.taxonomic_authority.data)

        form_dict = form_value.to_dict(flat=False)
        new_page = PAGE_TAXONOMIC_COVERAGE_SELECT
        if form_dict:
            for key in form_dict:
                val = form_dict[key][0]  # value is the first list element

                if val == BTN_HIDDEN_NEW:
                    new_page = PAGE_CREATE
                    break
                elif val == BTN_HIDDEN_OPEN:
                    new_page = PAGE_OPEN
                    break
                elif val == BTN_HIDDEN_CLOSE:
                    new_page = PAGE_CLOSE
                    break

        if save:
            submitted_hierarchy = form_value.get('hierarchy')
            if isinstance(form_value.get('hierarchy'), str) and form_value.get('hierarchy'):
                # convert hierarchy string to list
                submitted_hierarchy = ast.literal_eval(form_value.get('hierarchy'))
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
                    raise Exception(msg)
            else:
                add_child(coverage_node, txc_node)

            save_both_formats(filename=filename, eml_node=eml_node)

        return redirect(url_for(new_page, filename=filename))

    # Process GET
    have_links = False
    if node_id == '1':
        form.init_md5()
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

    set_current_page('taxonomic_coverage')
    return render_template('taxonomic_coverage_3.html', title='Taxonomic Coverage', form=form,
                           hierarchy=form.hierarchy.data, have_links=have_links)


def populate_taxonomic_coverage_form(form: TaxonomicCoverageForm, node: Node):
    general_taxonomic_coverage_node = node.find_child(names.GENERALTAXONOMICCOVERAGE)
    if general_taxonomic_coverage_node:
        form.general_taxonomic_coverage.data = general_taxonomic_coverage_node.content

    hierarchy = []
    taxonomic_classification_node = node.find_child(names.TAXONOMICCLASSIFICATION)
    populate_taxonomic_coverage_form_aux(hierarchy, taxonomic_classification_node)
    form.hierarchy.data = hierarchy[::-1]

    first_taxon = hierarchy[-1]
    form.taxon_value.data = first_taxon[1]
    if (first_taxon[0], first_taxon[0]) in form.taxon_rank.choices:
        form.taxon_rank.data = first_taxon[0]
    if first_taxon[5]:
        form.taxonomic_authority.data = first_taxon[5]
    have_links = False
    for taxon in hierarchy:
        if taxon[4]:
            have_links = True
            break
    form.md5.data = form_md5(form)
    return have_links


def populate_taxonomic_coverage_form_aux(hierarchy, node: Node = None):
    if node:
        taxon_rank_name_node = node.find_child(names.TAXONRANKNAME)
        taxon_rank_value_node = node.find_child(names.TAXONRANKVALUE)
        taxon_common_name_node = node.find_child(names.COMMONNAME)
        taxon_id_node = node.find_child(names.TAXONID)

        if taxon_rank_name_node:
            taxon_rank_name = taxon_rank_name_node.content
        else:
            taxon_rank_name = None
        if taxon_rank_value_node:
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

        if taxon_rank_name and taxon_rank_value:
            link = None
            provider = None
            if taxon_id:
                if provider_uri == "https://www.itis.gov":
                    link = f'https://itis.gov/servlet/SingleRpt/SingleRpt?search_topic=TSN&search_value={taxon_id}'
                    provider = 'ITIS'
                elif provider_uri == "http://www.marinespecies.org":
                    link = f'http://marinespecies.org/aphia.php?p=taxdetails&id={taxon_id}'
                    provider = 'WORMS'
            hierarchy.append((taxon_rank_name, taxon_rank_value, taxon_common_name, taxon_id, link, provider))

        taxonomic_classification_node = node.find_child(names.TAXONOMICCLASSIFICATION)
        if taxonomic_classification_node:
            populate_taxonomic_coverage_form_aux(hierarchy, taxonomic_classification_node)
