#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: views.py

:Synopsis:

:Author:
    costa
    servilla

:Created:
    7/23/18
"""
import daiquiri
import html
import json
import os.path
from datetime import date

from flask import (
    Blueprint, flash, render_template, redirect, request, 
    url_for, session
)

from flask_login import (
    current_user, login_required
)

from webapp.auth.user_data import (
    delete_eml, download_eml, get_active_packageid, get_user_document_list
)

from webapp.home.forms import ( 
    CreateEMLForm, TitleForm, ResponsiblePartyForm, AbstractForm, 
    KeywordSelectForm, KeywordForm, ResponsiblePartySelectForm, PubDateForm,
    GeographicCoverageSelectForm, GeographicCoverageForm,
    TemporalCoverageSelectForm, TemporalCoverageForm,
    TaxonomicCoverageSelectForm, TaxonomicCoverageForm,
    DataTableSelectForm, DataTableForm, AttributeSelectForm, AttributeForm,
    MscaleNominalOrdinalForm, MscaleIntervalRatioForm, MscaleDateTimeForm,
    CodeDefinitionSelectForm, CodeDefinitionForm, DownloadEMLForm,
    OpenEMLDocumentForm, DeleteEMLForm, SaveAsForm,
    MethodStepSelectForm, MethodStepForm, ProjectForm,
    AccessSelectForm, AccessForm, IntellectualRightsForm,
    OtherEntitySelectForm, OtherEntityForm, PublicationPlaceForm
)

from webapp.home.intellectual_rights import (
    INTELLECTUAL_RIGHTS_CC0, INTELLECTUAL_RIGHTS_CC_BY
)


from webapp.home.metapype_client import ( 
    load_eml, list_responsible_parties, save_both_formats, 
    evaluate_node, validate_tree, add_child, remove_child, create_eml, 
    create_title, create_pubdate, create_abstract, create_intellectual_rights,
    add_keyword, remove_keyword, create_keywords, create_project, create_keyword,
    create_responsible_party, create_method_step, list_method_steps,
    list_geographic_coverages, create_geographic_coverage, 
    create_temporal_coverage, list_temporal_coverages, 
    create_taxonomic_coverage, list_taxonomic_coverages,
    create_data_table, list_data_tables, 
    create_attribute, list_attributes, list_keywords,
    entity_name_from_data_table, attribute_name_from_attribute,
    list_codes_and_definitions, enumerated_domain_from_attribute,
    create_code_definition, mscale_from_attribute,
    create_interval_ratio, create_datetime,
    move_up, move_down, UP_ARROW, DOWN_ARROW,
    save_old_to_new, list_access_rules, create_access_rule,
    list_other_entities, create_other_entity, create_pubplace,
    create_access
)

from metapype.eml2_1_1 import export
from metapype.eml2_1_1 import names
from metapype.model.node import Node


logger = daiquiri.getLogger('views: ' + __name__)
home = Blueprint('home', __name__, template_folder='templates')


@home.route('/')
def index():
    if current_user.is_authenticated:
        current_packageid = get_active_packageid()
        if current_packageid:
            eml_node = load_eml(packageid=current_packageid)
            if eml_node:
                new_page = 'title'
            else:
                new_page = 'file_error'
            return redirect(url_for(f'home.{new_page}', packageid=current_packageid))
    return render_template('index.html')


@home.route('/edit/<page>')
def edit(page:str=None):
    '''
    The edit page allows for direct editing of a top-level element such as
    title, abstract, creators, etc. This function simply redirects to the
    specified page, passing the packageid as the only parameter.
    '''
    if current_user.is_authenticated and page:
        current_packageid = get_active_packageid()
        if current_packageid:
            eml_node = load_eml(packageid=current_packageid)
            if eml_node:
                new_page = page
            else:
                new_page = 'file_error'
            return redirect(url_for(f'home.{new_page}', packageid=current_packageid))
    return render_template('index.html')


@home.route('/about')
def about():
    return render_template('about.html')


@home.route('/file_error/<packageid>')
def file_error(packageid=None):
    return render_template('file_error.html', packageid=packageid)


@home.route('/delete', methods=['GET', 'POST'])
@login_required
def delete():
    form = DeleteEMLForm()
    choices = []
    packageids = get_user_document_list()
    for packageid in packageids:
        pid_tuple = (packageid, packageid)
        choices.append(pid_tuple)
    form.packageid.choices = choices
    # Process POST
    if form.validate_on_submit():
        packageid = form.packageid.data
        return_value = delete_eml(packageid=packageid)
        if isinstance(return_value, str):
            flash(return_value)
        else:
            flash(f'Deleted {packageid}')
        new_page = 'delete'   # Return the Response object
        return redirect(url_for(f'home.{new_page}'))
    # Process GET
    return render_template('delete_eml.html', title='Delete EML', 
                           form=form)


@home.route('/save', methods=['GET', 'POST'])
@login_required
def save():
    current_packageid = current_user.get_packageid()
    
    if not current_packageid:
        flash('No document currently open')
        return render_template('index.html')

    eml_node = load_eml(packageid=current_packageid)
    if not eml_node:
        flash(f'Unable to open {current_packageid}')
        return render_template('index.html')

    save_both_formats(packageid=current_packageid, eml_node=eml_node)
    flash(f'Saved {current_packageid}')
         
    return redirect(url_for(f'home.title', packageid=current_packageid))


@home.route('/save_as', methods=['GET', 'POST'])
@login_required
def save_as():
    # Determine POST type
    if request.method == 'POST':
        if 'Save' in request.form:
            submit_type = 'Save'
        elif 'Cancel' in request.form:
            submit_type = 'Cancel'
        else:
            submit_type = None
    form = SaveAsForm()
    current_packageid = current_user.get_packageid()

    # Process POST
    if form.validate_on_submit():
        if submit_type == 'Cancel':
            if current_packageid:
                new_packageid = current_packageid  # Revert back to the old packageid
                new_page = 'title'
            else:
                return render_template('index.html')
        elif submit_type == 'Save':
            if not current_packageid:
                flash('No document currently open')
                return render_template('index.html')

            eml_node = load_eml(packageid=current_packageid)
            if not eml_node:
                flash(f'Unable to open {current_packageid}')
                return render_template('index.html')

            new_packageid = form.packageid.data
            return_value = save_old_to_new(
                            old_packageid=current_packageid, 
                            new_packageid=new_packageid,
                            eml_node=eml_node)
            if isinstance(return_value, str):
                flash(return_value)
                new_packageid = current_packageid  # Revert back to the old packageid
            else:
                current_user.set_packageid(packageid=new_packageid)
                flash(f'Saved as {new_packageid}')
            new_page = 'title'   # Return the Response object
        
        return redirect(url_for(f'home.{new_page}', packageid=new_packageid))

     # Process GET
    if current_packageid:
        form.packageid.data = current_packageid
        return render_template('save_as.html',
                           packageid=current_packageid, 
                           title='Save As', 
                           form=form)
    else:
        flash("No document currently open")
        return render_template('index.html')



@home.route('/download', methods=['GET', 'POST'])
@login_required
def download():
    form = DownloadEMLForm()
    choices = []
    packageids = get_user_document_list()
    for packageid in packageids:
        pid_tuple = (packageid, packageid)
        choices.append(pid_tuple)
    form.packageid.choices = choices
    # Process POST
    if form.validate_on_submit():
        packageid = form.packageid.data
        return_value = download_eml(packageid=packageid)
        if isinstance(return_value, str):
            flash(return_value)
        else:
            return return_value
    # Process GET
    return render_template('download_eml.html', title='Download EML', 
                           form=form)


@home.route('/download_current', methods=['GET', 'POST'])
@login_required
def download_current():
    current_packageid = get_active_packageid()
    if current_packageid:
        return_value = download_eml(packageid=current_packageid)
        if isinstance(return_value, str):
            flash(return_value)
        else:
            return return_value


@home.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    form = CreateEMLForm()

    # Process POST
    if form.validate_on_submit():
        packageid = form.packageid.data
        user_packageids = get_user_document_list()
        if user_packageids and packageid and packageid in user_packageids:
            flash(f'{packageid} already exists')
            return render_template('create_eml.html', title='Create New EML', 
                            form=form)
        create_eml(packageid=packageid)
        current_user.set_packageid(packageid)
        return redirect(url_for(f'home.title', packageid=packageid))
    # Process GET
    return render_template('create_eml.html', title='Create New EML', 
                           form=form)


@home.route('/open', methods=['GET', 'POST'])
@login_required
def open():
    form = OpenEMLDocumentForm()

    choices = []
    user_packageids = get_user_document_list()
    for packageid in user_packageids:
        pid_tuple = (packageid, packageid)
        choices.append(pid_tuple)
    form.packageid.choices = choices

    # Process POST
    if form.validate_on_submit():
        packageid = form.packageid.data
        eml_node = load_eml(packageid)
        if eml_node:
            current_user.set_packageid(packageid)
            create_eml(packageid=packageid)
            new_page = 'title'
        else:
            new_page = 'file_error'
        return redirect(url_for(f'home.{new_page}', packageid=packageid))
    
    # Process GET
    return render_template('open_eml_document.html', title='Open EML Document', 
                           form=form)



@home.route('/close', methods=['GET', 'POST'])
@login_required
def close():
    current_packageid = current_user.get_packageid()
    
    if current_packageid:
        current_user.set_packageid(None)
        flash(f'Closed {current_packageid}')
    else:
        flash("There was no package open")
        
    return render_template('index.html')


@home.route('/data_table_select/<packageid>', methods=['GET', 'POST'])
def data_table_select(packageid=None):
    form = DataTableSelectForm(packageid=packageid)
    
    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = select_post(packageid, form, form_dict, 
                             'POST', 'data_table_select', 'project', 
                             'other_entity_select', 'data_table')
        return redirect(url)

    # Process GET
    eml_node = load_eml(packageid=packageid)
    dt_list = list_data_tables(eml_node)
    title = 'Data Tables'

    return render_template('data_table_select.html', title=title,
                            dt_list=dt_list, form=form)


@home.route('/data_table/<packageid>/<node_id>', methods=['GET', 'POST'])
def data_table(packageid=None, node_id=None):
    dt_node_id = node_id
    # Determine POST type
    if request.method == 'POST':
        next_page = 'home.data_table_select'

        if 'Save Changes' in request.form:
            submit_type = 'Save Changes'
        elif 'Attributes' in request.form:
            next_page = 'home.attribute_select'
            submit_type = 'Save Changes'
        elif 'Access' in request.form:
            next_page = 'home.entity_access_select'
            submit_type = 'Save Changes'
        elif 'Methods' in request.form:
            next_page = 'home.entity_method_step_select'
            submit_type = 'Save Changes'
        elif 'Geographic' in request.form:
            next_page = 'home.entity_geographic_coverage_select'
            submit_type = 'Save Changes'
        elif 'Temporal' in request.form:
            next_page = 'home.entity_temporal_coverage_select'
            submit_type = 'Save Changes'
        elif 'Taxonomic' in request.form:
            next_page = 'home.entity_taxonomic_coverage_select'
            submit_type = 'Save Changes'
        elif 'Back' in request.form:
            submit_type = 'Back'
        else:
            submit_type = None
    form = DataTableForm(packageid=packageid)

    # Process POST
    if form.validate_on_submit():
        eml_node = load_eml(packageid=packageid)
        
        if submit_type == 'Save Changes':
            dataset_node = eml_node.find_child(names.DATASET)
            if not dataset_node:
                dataset_node = Node(names.DATASET)

            entity_name = form.entity_name.data
            entity_description = form.entity_description.data
            object_name = form.object_name.data
            size = form.size.data
            num_header_lines = form.num_header_lines.data
            record_delimiter = form.record_delimiter.data
            attribute_orientation = form.attribute_orientation.data
            field_delimiter = form.field_delimiter.data
            case_sensitive = form.case_sensitive.data
            number_of_records = form.number_of_records.data
            online_url = form.online_url.data

            dt_node = Node(names.DATATABLE, parent=dataset_node)

            create_data_table(
                dt_node, 
                entity_name,
                entity_description,
                object_name,
                size,
                num_header_lines,
                record_delimiter,
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

            save_both_formats(packageid=packageid, eml_node=eml_node)

        if (next_page == 'home.entity_access_select' or 
            next_page == 'home.entity_method_step_select' or
            next_page == 'home.entity_geographic_coverage_select' or
            next_page == 'home.entity_temporal_coverage_select' or
            next_page == 'home.entity_taxonomic_coverage_select'
            ):
            return redirect(url_for(next_page, 
                                    packageid=packageid,
                                    dt_element_name=names.DATATABLE,
                                    dt_node_id=dt_node_id))
        else:
            return redirect(url_for(next_page, 
                                    packageid=packageid, 
                                    dt_node_id=dt_node_id))

    # Process GET
    atts = 'No data table attributes have been added'

    if dt_node_id == '1':
        pass
    else:
        eml_node = load_eml(packageid=packageid)
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            dt_nodes = dataset_node.find_all_children(names.DATATABLE)
            if dt_nodes:
                for dt_node in dt_nodes:
                    if dt_node_id == dt_node.id:
                        att_list = list_attributes(dt_node)
                        if att_list:
                            atts = compose_atts(att_list)
                        populate_data_table_form(form, dt_node)
    
    return render_template('data_table.html', title='Data Table', form=form,
                           atts=atts)


def compose_atts(att_list:list=[]):
    atts = ''
    if att_list:
        atts = ''
        for att_entry in att_list:
            att_name = att_entry.label
            atts = atts + att_name + ', '
        atts = atts[:-2]
    
    return atts


def populate_data_table_form(form:DataTableForm, node:Node):    
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


# <dt_node_id> identifies the dataTable node that this attribute
# is a part of (within its attributeList)
#
@home.route('/attribute_select/<packageid>/<dt_node_id>', methods=['GET', 'POST'])
def attribute_select(packageid=None, dt_node_id=None):
    form = AttributeSelectForm(packageid=packageid)
    #dt_node_id = request.args.get('dt_node_id')  # alternate way to get the id

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = attribute_select_post(packageid, form, form_dict, 
                             'POST', 'attribute_select', 'data_table', 
                             'data_table', 'attribute', dt_node_id=dt_node_id)
        return redirect(url)

    # Process GET
    return attribute_select_get(packageid=packageid, form=form, dt_node_id=dt_node_id)


def attribute_select_get(packageid=None, form=None, dt_node_id=None):
    # Process GET
    att_list = []
    title = 'Attributes'
    entity_name = ''
    load_eml(packageid=packageid)

    if dt_node_id == '1':
        pass
    else:
        data_table_node = Node.get_node_instance(dt_node_id)
        if data_table_node:
            entity_name = entity_name_from_data_table(data_table_node)
            att_list = list_attributes(data_table_node)

    return render_template('attribute_select.html', 
                           title=title, 
                           entity_name=entity_name, 
                           att_list=att_list, 
                           form=form)


def attribute_select_post(packageid=None, form=None, form_dict=None,
                          method=None, this_page=None, back_page=None, 
                          next_page=None, edit_page=None,
                          dt_node_id=None):
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
            return url_for(f'home.{new_page}', 
                            packageid=packageid, 
                            dt_node_id=dt_node_id, 
                            node_id=node_id)
        elif new_page == this_page: 
            return url_for(f'home.{new_page}', 
                            packageid=packageid, 
                            dt_node_id=dt_node_id)
        else:
            return url_for(f'home.{new_page}', 
                           packageid=packageid,
                           node_id=dt_node_id)


@home.route('/attribute/<packageid>/<dt_node_id>/<node_id>', methods=['GET', 'POST'])
def attribute(packageid=None, dt_node_id=None, node_id=None):
    form = AttributeForm(packageid=packageid, node_id=node_id)
    att_node_id = node_id

    # Determine POST type
    if request.method == 'POST':
        next_page = 'home.attribute_select' # Save or Back sends us back to the list of attributes

        if 'Save Changes' in request.form:
            submit_type = 'Save Changes'
        elif 'Back' in request.form:
            submit_type = 'Back'
        else:
            submit_type = 'Save Changes'
            mscale = form.mscale.data

            if mscale == 'nominal or ordinal':
                next_page = 'home.mscaleNominalOrdinal'
            elif mscale == 'ratio or interval':
                next_page = 'home.mscaleIntervalRatio'
            elif mscale == 'dateTime':
                next_page = 'home.mscaleDateTime'

            #url = url_for(next_page, packageid=packageid, dt_node_id=dt_node_id, node_id=node_id)
            #return redirect(url)

    # Process POST
        if submit_type == 'Save Changes':
            dt_node = None
            attribute_list_node = None
            eml_node = load_eml(packageid=packageid)
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

            if dt_node:
                attribute_list_node = dt_node.find_child(names.ATTRIBUTELIST)
            else:
                dt_node = Node(names.DATATABLE, parent=dataset_node)
                add_child(dataset_node, dt_node)

            if not attribute_list_node:
                attribute_list_node = Node(names.ATTRIBUTELIST, parent=dt_node)
                add_child(dt_node, attribute_list_node)

            att_node = Node(names.ATTRIBUTE, parent=attribute_list_node)
            attribute_name = form.attribute_name.data
            attribute_label = form.attribute_label.data
            attribute_definition = form.attribute_definition.data
            storage_type = form.storage_type.data
            storage_type_system = form.storage_type_system.data

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


            create_attribute(att_node, 
                             attribute_name,
                             attribute_label,
                             attribute_definition,
                             storage_type,
                             storage_type_system,
                             code_dict)

            if node_id and len(node_id) != 1:
                old_att_node = Node.get_node_instance(node_id)
                if old_att_node:
                    att_parent_node = old_att_node.parent
                    att_parent_node.replace_child(old_att_node, att_node)
                    mscale_node = old_att_node.find_child(names.MEASUREMENTSCALE)
                    if mscale_node:
                        add_child(att_node, mscale_node)
                else:
                    msg = f"No node found in the node store with node id {node_id}"
                    raise Exception(msg)
            else:
                add_child(attribute_list_node, att_node)

            save_both_formats(packageid=packageid, eml_node=eml_node)
            att_node_id = att_node.id

        url = url_for(next_page, packageid=packageid, 
                      dt_node_id=dt_node_id, node_id=att_node_id)
        return redirect(url)

    # Process GET
    if node_id == '1':
        pass
    else:
        eml_node = load_eml(packageid=packageid)
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
                                        populate_attribute_form(form, att_node)
                                        break
    
    return render_template('attribute.html', title='Attribute', form=form)


def populate_attribute_form(form:AttributeForm, node:Node):    
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

    mscale = mscale_from_attribute(node)
    if mscale:
        if mscale == 'nominal' or mscale == 'ordinal':
            form.mscale.data = 'nominal or ordinal'
        elif mscale == 'interval' or mscale == 'ratio':
            form.mscale.data = 'ratio or interval'
        elif mscale == 'dateTime':
            form.mscale.data = 'dateTime'
    
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
            i = i + 1
            

@home.route('/mscaleNominalOrdinal/<packageid>/<dt_node_id>/<node_id>', methods=['GET', 'POST'])
def mscaleNominalOrdinal(packageid=None, dt_node_id=None, node_id=None):
    form = MscaleNominalOrdinalForm(packageid=packageid, dt_node_id=dt_node_id, node_id=node_id)

    # Determine POST type
    if request.method == 'POST':
        next_page = 'home.attribute' # Save or Back sends us back to the list of attributes

        if 'Edit' in request.form:
            # Edit codes and definitions
            next_page = 'home.code_definition_select'
            submit_type = 'Edit'
        elif 'Save Changes' in request.form:
            submit_type = 'Save Changes'
        elif 'Back' in request.form:
            submit_type = 'Back'

        if submit_type == 'Edit':
            url = url_for(next_page, packageid=packageid, dt_node_id=dt_node_id, node_id=node_id)
            return redirect(url)

        elif submit_type == 'Save Changes':
            eml_node = load_eml(packageid=packageid)
            att_node = Node.get_node_instance(node_id)
            mscale_node = att_node.find_child(names.MEASUREMENTSCALE)
            if mscale_node:
                current_mscale = mscale_from_attribute(att_node)
                new_mscale = form.mscale.data
                enforced = form.enforced.data
                nominal_node = mscale_node.find_child(names.NOMINAL)
                ordinal_node = mscale_node.find_child(names.ORDINAL)
                nnd_node = None
                if nominal_node:
                    nnd_node = nominal_node.find_child(names.NONNUMERICDOMAIN)
                elif ordinal_node:
                    nnd_node = ordinal_node.find_child(names.NONNUMERICDOMAIN)
                if nnd_node:
                    enumerated_domain_node = nnd_node.find_child(names.ENUMERATEDDOMAIN)
                    if enumerated_domain_node:
                        if enforced:
                            enumerated_domain_node.add_attribute('enforced', enforced)
                if current_mscale == 'nominal' and new_mscale == 'ordinal':
                    if nominal_node:
                        ordinal_node = Node(names.ORDINAL, parent=mscale_node)
                        add_child(mscale_node, ordinal_node)
                        if nnd_node:
                            add_child(ordinal_node, nnd_node)
                        mscale_node.remove_child(nominal_node)
                elif current_mscale == 'ordinal' and new_mscale == 'nominal':
                    if ordinal_node:
                        nominal_node = Node(names.NOMINAL, parent=mscale_node)
                        add_child(mscale_node, nominal_node)
                        if nnd_node:
                            add_child(nominal_node, nnd_node)
                        mscale_node.remove_child(ordinal_node)
            save_both_formats(packageid=packageid, eml_node=eml_node)
 
            url = url_for(next_page, packageid=packageid, dt_node_id=dt_node_id, node_id=node_id)
            return redirect(url)

        elif submit_type == 'Back':
            url = url_for(next_page, packageid=packageid, dt_node_id=dt_node_id, node_id=node_id)
            return redirect(url)

    # Process GET
    attribute_name = 'Nominal/Ordinal Attribute'
    if node_id == '1':
        pass
    else:
        eml_node = load_eml(packageid=packageid)
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
                                        populate_nominal_ordinal(form, att_node)
                                        attribute_name = attribute_name_from_attribute(att_node)
    
    return render_template('mscale_nominal_ordinal.html', 
                           title='Measurement Scale', 
                           form=form,
                           attribute_name=attribute_name)


@home.route('/mscaleIntervalRatio/<packageid>/<dt_node_id>/<node_id>', methods=['GET', 'POST'])
def mscaleIntervalRatio(packageid=None, dt_node_id=None, node_id=None):
    form = MscaleIntervalRatioForm(packageid=packageid, dt_node_id=dt_node_id, node_id=node_id)

    # Determine POST type
    if request.method == 'POST':
        next_page = 'home.attribute' # Save or Back sends us back to the list of attributes

        if 'Save Changes' in request.form:
            submit_type = 'Save Changes'
        elif 'Back' in request.form:
            submit_type = 'Back'

        if submit_type == 'Save Changes':
            eml_node = load_eml(packageid=packageid)
            att_node = Node.get_node_instance(node_id)
            mscale_node = att_node.find_child(names.MEASUREMENTSCALE)
            if mscale_node:
                att_node.remove_child(mscale_node)
            mscale_node = Node(names.MEASUREMENTSCALE, parent=att_node)
            add_child(att_node, mscale_node)
            mscale = form.mscale.data
            interval_ratio_node = None
            if mscale == 'interval':
                interval_ratio_node = Node(names.INTERVAL, parent=mscale_node)
            else:
                interval_ratio_node = Node(names.RATIO, parent=mscale_node)
            add_child(mscale_node, interval_ratio_node)
            standard_unit = form.standard_unit.data
            cusmtom_unit = form.custom_unit.data
            precision = form.precision.data
            number_type = form.number_type.data
            bounds_minimum = form.bounds_minimum.data
            bounds_minimum_exclusive = form.bounds_minimum_exclusive.data
            bounds_maximum = form.bounds_maximum.data
            bounds_maximum_exclusive = form.bounds_maximum_exclusive.data
            create_interval_ratio(interval_ratio_node, standard_unit, cusmtom_unit, 
                                  precision, number_type, bounds_minimum,
                                  bounds_minimum_exclusive, bounds_maximum,
                                  bounds_maximum_exclusive)
            save_both_formats(packageid=packageid, eml_node=eml_node)
 
            url = url_for(next_page, packageid=packageid, dt_node_id=dt_node_id, node_id=node_id)
            return redirect(url)

        elif submit_type == 'Back':
            url = url_for(next_page, packageid=packageid, dt_node_id=dt_node_id, node_id=node_id)
            return redirect(url)

    # Process GET
    attribute_name = 'Interval/Ratio Attribute'
    if node_id == '1':
        pass
    else:
        eml_node = load_eml(packageid=packageid)
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
                                        populate_interval_ratio(form, att_node)
                                        attribute_name = attribute_name_from_attribute(att_node)
    
    return render_template('mscale_interval_ratio.html', 
                           title='Measurement Scale', 
                           form=form,
                           attribute_name=attribute_name)



@home.route('/mscaleDateTime/<packageid>/<dt_node_id>/<node_id>', methods=['GET', 'POST'])
def mscaleDateTime(packageid=None, dt_node_id=None, node_id=None):
    form = MscaleDateTimeForm(packageid=packageid, dt_node_id=dt_node_id, node_id=node_id)

    # Determine POST type
    if request.method == 'POST':
        next_page = 'home.attribute' # Save or Back sends us back to the list of attributes

        if 'Save Changes' in request.form:
            submit_type = 'Save Changes'
        elif 'Back' in request.form:
            submit_type = 'Back'

        if submit_type == 'Save Changes':
            eml_node = load_eml(packageid=packageid)
            att_node = Node.get_node_instance(node_id)
            mscale_node = att_node.find_child(names.MEASUREMENTSCALE)
            if mscale_node:
                att_node.remove_child(mscale_node)
            mscale_node = Node(names.MEASUREMENTSCALE, parent=att_node)
            add_child(att_node, mscale_node)
            datetime_node = Node(names.DATETIME, parent=mscale_node)
            add_child(mscale_node, datetime_node)
            format_string = form.format_string.data
            datetime_precision = form.datetime_precision.data
            bounds_minimum = form.bounds_minimum.data
            bounds_minimum_exclusive = form.bounds_minimum_exclusive.data
            bounds_maximum = form.bounds_maximum.data
            bounds_maximum_exclusive = form.bounds_maximum_exclusive.data
            create_datetime(datetime_node, format_string, datetime_precision, 
                            bounds_minimum, bounds_minimum_exclusive, 
                            bounds_maximum, bounds_maximum_exclusive)
            save_both_formats(packageid=packageid, eml_node=eml_node)
 
            url = url_for(next_page, packageid=packageid, dt_node_id=dt_node_id, node_id=node_id)
            return redirect(url)

        elif submit_type == 'Back':
            url = url_for(next_page, packageid=packageid, dt_node_id=dt_node_id, node_id=node_id)
            return redirect(url)

    # Process GET
    attribute_name = 'DateTime Attribute'
    if node_id == '1':
        pass
    else:
        eml_node = load_eml(packageid=packageid)
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
                                        populate_datetime(form, att_node)
                                        attribute_name = attribute_name_from_attribute(att_node)
    
    return render_template('mscale_datetime.html', 
                           title='Measurement Scale', 
                           form=form,
                           attribute_name=attribute_name)


def populate_nominal_ordinal(form:MscaleNominalOrdinalForm, att_node):
    mscale = 'nominal' 
    mscale_node = att_node.find_child(names.MEASUREMENTSCALE)
    if mscale_node:
        node = mscale_node.find_child(names.NOMINAL)
        if not node:
            node = mscale_node.find_child(names.ORDINAL)
            if node:
                mscale = 'ordinal'
                form.mscale.data = mscale

        if node:
            enumerated_domain_node = node.find_child(names.ENUMERATEDDOMAIN)

            if enumerated_domain_node:
                enforced = enumerated_domain_node.attribute_value('enforced')
                if enforced and enforced.upper() == 'NO':
                    form.enforced.data = 'no'
                else:
                    form.enforced.data = 'yes'
    

def populate_interval_ratio(form:MscaleIntervalRatioForm, att_node):
    mscale = 'ratio' 
    mscale_node = att_node.find_child(names.MEASUREMENTSCALE)
    if mscale_node:
        ratio_node = mscale_node.find_child(names.RATIO)
        interval_node = mscale_node.find_child(names.INTERVAL)

        node = ratio_node
        if not node:
            node = interval_node
            mscale = 'interval'

        if node:
            form.mscale.data = mscale
            unit_node = node.find_child(names.UNIT)

            if unit_node:
                standard_unit_node = unit_node.find_child(names.STANDARDUNIT)
                if standard_unit_node:
                    form.standard_unit.data = standard_unit_node.content 
                custom_unit_node = unit_node.find_child(names.CUSTOMUNIT)
                if custom_unit_node:
                    form.custom_unit.data = custom_unit_node.content

            precision_node = node.find_child(names.PRECISION)
            if precision_node:
                form.precision.data = precision_node.content

            numeric_domain_node = node.find_child(names.NUMERICDOMAIN)
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
                        if exclusive:
                            if exclusive.lower() == 'true':
                                form.bounds_minimum_exclusive.data = True
                            else:
                                form.bounds_minimum_exclusive.data = False
                        else:
                            form.bounds_minimum_exclusive.data = False
                    maximum_node = bounds_node.find_child(names.MAXIMUM)
                    if maximum_node:
                        form.bounds_maximum.data = maximum_node.content
                        exclusive = maximum_node.attribute_value('exclusive')
                        if exclusive:
                            if exclusive.lower() == 'true':
                                form.bounds_maximum_exclusive.data = True
                            else:
                                form.bounds_maximum_exclusive.data = False
                        else:
                            form.bounds_maximum_exclusive.data = False


def populate_datetime(form:MscaleDateTimeForm, att_node):
    mscale_node = att_node.find_child(names.MEASUREMENTSCALE)
    if mscale_node:
        node = mscale_node.find_child(names.DATETIME)

        if node:
            format_string_node = node.find_child(names.FORMATSTRING)

            if format_string_node:
                form.format_string.data = format_string_node.content

            datetime_precision_node = node.find_child(names.DATETIMEPRECISION)
            if datetime_precision_node:
                form.datetime_precision.data = datetime_precision_node.content

            datetime_domain_node = node.find_child(names.DATETIMEDOMAIN)
            if datetime_domain_node:
                bounds_node = datetime_domain_node.find_child(names.BOUNDS)
                if bounds_node:
                    minimum_node = bounds_node.find_child(names.MINIMUM)
                    if minimum_node:
                        form.bounds_minimum.data = minimum_node.content
                        exclusive = minimum_node.attribute_value('exclusive')
                        if exclusive:
                            if exclusive.lower() == 'true':
                                form.bounds_minimum_exclusive.data = True
                            else:
                                form.bounds_minimum_exclusive.data = False
                        else:
                            form.bounds_minimum_exclusive.data = False
                    maximum_node = bounds_node.find_child(names.MAXIMUM)
                    if maximum_node:
                        form.bounds_maximum.data = maximum_node.content
                        exclusive = maximum_node.attribute_value('exclusive')
                        if exclusive:
                            if exclusive.lower() == 'true':
                                form.bounds_maximum_exclusive.data = True
                            else:
                                form.bounds_maximum_exclusive.data = False
                        else:
                            form.bounds_maximum_exclusive.data = False


# <node_id> identifies the attribute node that this code definition
# is a part of (within its measurementScale)
#
@home.route('/code_definition_select/<packageid>/<dt_node_id>/<node_id>', methods=['GET', 'POST'])
def code_definition_select(packageid=None, dt_node_id=None, node_id=None):
    form = CodeDefinitionSelectForm(packageid=packageid)
    #dt_node_id = request.args.get('dt_node_id')  # alternate way to get the id

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = code_definition_select_post(packageid, form, form_dict, 
                             'POST', 'code_definition_select', 'mscaleNominalOrdinal', 
                             'mscaleNominalOrdinal', 'code_definition', dt_node_id, node_id)
        return redirect(url)

    # Process GET
    return code_definition_select_get(packageid=packageid, form=form, att_node_id=node_id)


def code_definition_select_get(packageid=None, form=None, att_node_id=None):
    # Process GET
    codes_list = []
    title = 'Code Definitions'
    attribute_name = ''
    load_eml(packageid=packageid)

    att_node = Node.get_node_instance(att_node_id)
    if att_node:
        attribute_name = attribute_name_from_attribute(att_node)
        codes_list = list_codes_and_definitions(att_node)
    return render_template('code_definition_select.html', title=title, 
                           attribute_name=attribute_name, codes_list=codes_list, 
                           form=form)


def code_definition_select_post(packageid=None, form=None, form_dict=None,
                          method=None, this_page=None, back_page=None, 
                          next_page=None, edit_page=None, dt_node_id=None,
                          att_node_id=None):
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
            return url_for(f'home.{new_page}', 
                            packageid=packageid, 
                            dt_node_id=dt_node_id,
                            att_node_id=att_node_id,
                            node_id=node_id)
        elif new_page == this_page: 
            return url_for(f'home.{new_page}', 
                            packageid=packageid, 
                            dt_node_id=dt_node_id,
                            node_id=att_node_id)
        elif new_page == back_page:
            att_node = Node.get_node_instance(att_node_id)
            mscale = mscale_from_attribute(att_node)
            return url_for(f'home.{new_page}', 
                           packageid=packageid,
                           dt_node_id=dt_node_id,
                           node_id=att_node_id,
                           mscale=mscale)


# node_id is the id of the codeDefinition node being edited. If the value
# '1', it means we are adding a new codeDefinition node, otherwise we are
# editing an existing one.
#
@home.route('/code_definition/<packageid>/<dt_node_id>/<att_node_id>/<node_id>', methods=['GET', 'POST'])
def code_definition(packageid=None, dt_node_id=None, att_node_id=None, node_id=None):
    eml_node = load_eml(packageid=packageid)
    att_node = Node.get_node_instance(att_node_id)
    attribute_name = 'Attribute Name'
    if att_node:
        attribute_name = attribute_name_from_attribute(att_node)
    form = CodeDefinitionForm(packageid=packageid, node_id=node_id, attribute_name=attribute_name)

    # Determine POST type
    if request.method == 'POST':
        next_page = 'home.code_definition_select' # Save or Back sends us back to the list of attributes

        if 'Save Changes' in request.form:
            submit_type = 'Save Changes'
        elif 'Back' in request.form:
            submit_type = 'Back'

    # Process POST
        if submit_type == 'Save Changes':
            if att_node:
                enumerated_domain_node = enumerated_domain_from_attribute(att_node)

                if not enumerated_domain_node:
                    mscale_node = Node(names.MEASUREMENTSCALE, parent=att_node)
                    add_child(att_node, mscale_node)
                    nominal_node = Node(names.NOMINAL, parent=mscale_node)
                    add_child(mscale_node, nominal_node)
                    non_numeric_domain_node = Node(names.NONNUMERICDOMAIN, parent=nominal_node)
                    add_child(nominal_node, non_numeric_domain_node)
                    enumerated_domain_node = Node(names.ENUMERATEDDOMAIN, parent=non_numeric_domain_node)
                    enumerated_domain_node.add_attribute('enforced', 'yes')  # 'yes' is default value
                    add_child(non_numeric_domain_node, enumerated_domain_node)

                code = form.code.data
                definition = form.definition.data
                order = form.order.data
                code_definition_node = Node(names.CODEDEFINITION, parent=enumerated_domain_node)
                create_code_definition(code_definition_node, code, definition, order)

                if node_id and len(node_id) != 1:
                    old_code_definition_node = Node.get_node_instance(node_id)

                    if old_code_definition_node:
                        code_definition_parent_node = old_code_definition_node.parent
                        code_definition_parent_node.replace_child(old_code_definition_node, 
                                                                    code_definition_node)
                    else:
                        msg = f"No codeDefinition node found in the node store with node id {node_id}"
                        raise Exception(msg)
                else:
                    add_child(enumerated_domain_node, code_definition_node)

                save_both_formats(packageid=packageid, eml_node=eml_node)

        url = url_for(next_page, packageid=packageid, dt_node_id=dt_node_id, node_id=att_node_id)
        return redirect(url)

    # Process GET
    if node_id == '1':
        pass
    else:
        enumerated_domain_node = enumerated_domain_from_attribute(att_node)
        if enumerated_domain_node:
            cd_nodes = enumerated_domain_node.find_all_children(names.CODEDEFINITION)
            if cd_nodes:
                for cd_node in cd_nodes:
                    if node_id == cd_node.id:
                        populate_code_definition_form(form, cd_node)
                        break
    
    return render_template('code_definition.html', title='Code Definition', form=form, attribute_name=attribute_name)


def populate_code_definition_form(form:CodeDefinitionForm, cd_node:Node):  
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


@home.route('/title/<packageid>', methods=['GET', 'POST'])
def title(packageid=None):
    # Determine POST type
    if request.method == 'POST':
        if 'Next' in request.form:
            submit_type = 'Next'
        elif 'Evaluate' in request.form:
            submit_type = 'Evaluate'
        else:
            submit_type = None
    form = TitleForm()
    # Process POST
    if form.validate_on_submit():
        title_node = create_title(title=form.title.data, packageid=packageid)
        if submit_type == 'Evaluate':
            evaluate_text = evaluate_node(title_node)
            if evaluate_text:
                flash(evaluate_text)
        new_page = 'access_select' if (submit_type == 'Next') else 'title'
        return redirect(url_for(f'home.{new_page}', packageid=packageid))
    # Process GET
    eml_node = load_eml(packageid=packageid)
    title_node = eml_node.find_child(child_name='title')
    if title_node:
        form.title.data = title_node.content
    return render_template('title.html', title='Title', form=form)


@home.route('/publication_place/<packageid>', methods=['GET', 'POST'])
def publication_place(packageid=None):
    # Determine POST type
    if request.method == 'POST':
        if 'Next' in request.form:
            submit_type = 'Next'
        else:
            submit_type = None
    form = PublicationPlaceForm()
    # Process POST
    if form.validate_on_submit():
        pubplace_node = create_pubplace(pubplace=form.pubplace.data, packageid=packageid)
        new_page = 'method_step_select' if (submit_type == 'Next') else 'publisher'
        return redirect(url_for(f'home.{new_page}', packageid=packageid))
    # Process GET
    eml_node = load_eml(packageid=packageid)
    pubplace_node = eml_node.find_child(child_name='pubPlace')
    if pubplace_node:
        form.pubplace.data = pubplace_node.content
    return render_template('publication_place.html', title='Publication Place', form=form)


@home.route('/creator_select/<packageid>', methods=['GET', 'POST'])
def creator_select(packageid=None):
    form = ResponsiblePartySelectForm(packageid=packageid)
    
    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = select_post(packageid, form, form_dict, 
                             'POST', 'creator_select', 'access_select', 
                             'metadata_provider_select', 'creator')
        return redirect(url)

    # Process GET
    return rp_select_get(packageid=packageid, form=form, rp_name=names.CREATOR, 
                         rp_singular='Creator', rp_plural='Creators')


@home.route('/creator/<packageid>/<node_id>', methods=['GET', 'POST'])
def creator(packageid=None, node_id=None):
    method = request.method
    return responsible_party(packageid=packageid, node_id=node_id, 
                             method=method, node_name=names.CREATOR, 
                             back_page='creator_select', title='Creator')


def rp_select_get(packageid=None, form=None, rp_name=None, 
                  rp_singular=None, rp_plural=None):
    # Process GET
    eml_node = load_eml(packageid=packageid)
    rp_list = list_responsible_parties(eml_node, rp_name)
    title = rp_name.capitalize()

    return render_template('responsible_party_select.html', title=title,
                            rp_list=rp_list, form=form, 
                            rp_singular=rp_singular, rp_plural=rp_plural)


def responsible_party(packageid=None, node_id=None, method=None, 
                      node_name=None, back_page=None, title=None,
                      next_page=None):
    eml_node = load_eml(packageid=packageid)
    dataset_node = eml_node.find_child(names.DATASET)
    if not dataset_node:
        dataset_node = Node(names.DATASET, parent=eml_node)
        add_child(eml_node, dataset_node)
    parent_node = dataset_node
    role = False
    submit_type = 'Navigate'  # Two of three cases: Back and Next
    new_page = back_page      # Two of three cases: Back and Save Changes

    # If this is an associatedParty or a project personnel element, 
    # set role to True so it will appear as a form field.
    if node_name == names.ASSOCIATEDPARTY or node_name == names.PERSONNEL:
        role = True

    # If this is a project personnel party, place it under the
    # project node, not under the dataset node
    if node_name == names.PERSONNEL:
        project_node = dataset_node.find_child(names.PROJECT)
        if not project_node:
            project_node = Node(names.PROJECT, parent=dataset_node)
            add_child(dataset_node, project_node)
        parent_node = project_node

    # Determine POST type
    if request.method == 'POST':
        if 'Save Changes' in request.form:
            submit_type = 'Save Changes'
        elif 'Next' in request.form:
            new_page = next_page
    form = ResponsiblePartyForm(packageid=packageid)

    # Process POST
    if form.validate_on_submit():
        if submit_type == 'Save Changes':
            salutation = form.salutation.data
            gn = form.gn.data
            sn = form.sn.data
            organization = form.organization.data
            position_name = form.position_name.data
            address_1 = form.address_1.data
            address_2 = form.address_2.data
            city = form.city.data
            state = form.state.data
            postal_code = form.postal_code.data
            country = form.country.data
            phone = form.phone.data
            fax = form.fax.data
            email = form.email.data
            online_url = form.online_url.data
            role = form.role.data

            rp_node = Node(node_name, parent=parent_node)

            create_responsible_party(
                rp_node,
                packageid,   
                salutation,
                gn,
                sn,
                organization,
                position_name,
                address_1,
                address_2,
                city,
                state,
                postal_code,
                country,
                phone,
                fax,
                email,
                online_url,
                role)

            if node_id and len(node_id) != 1:
                old_rp_node = Node.get_node_instance(node_id)
                if old_rp_node:
                    old_rp_parent_node = old_rp_node.parent
                    old_rp_parent_node.replace_child(old_rp_node, rp_node)
                else:
                    msg = f"No node found in the node store with node id {node_id}"
                    raise Exception(msg)
            else:
                add_child(parent_node, rp_node)

            save_both_formats(packageid=packageid, eml_node=eml_node)
            flash(f"Changes to the '{node_name}' element have been saved.")

            # There is at most only one publisher element, so we don't have a 
            # list of publishers to navigate back to. Stay on this page after
            # saving changes.
            if node_name == names.PUBLISHER:
                new_page = 'publisher'

        return redirect(url_for(f'home.{new_page}', packageid=packageid))

    # Process GET
    if node_id == '1':
        pass
    else:
        if parent_node:
            rp_nodes = parent_node.find_all_children(child_name=node_name)
            if rp_nodes:
                for rp_node in rp_nodes:
                    if node_id == rp_node.id:
                        populate_responsible_party_form(form, rp_node)
    
    return render_template('responsible_party.html', title=title, 
                           form=form, role=role, next_page=next_page)


@home.route('/metadata_provider_select/<packageid>', methods=['GET', 'POST'])
def metadata_provider_select(packageid=None):
    form = ResponsiblePartySelectForm(packageid=packageid)
    
    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = select_post(packageid, form, form_dict, 
                             'POST', 'metadata_provider_select', 
                             'creator_select', 
                             'associated_party_select', 
                             'metadata_provider')
        return redirect(url)

    # Process GET
    return rp_select_get(packageid=packageid, form=form, 
                         rp_name=names.METADATAPROVIDER,
                         rp_singular='Metadata Provider', 
                         rp_plural='Metadata Providers')


@home.route('/metadata_provider/<packageid>/<node_id>', methods=['GET', 'POST'])
def metadata_provider(packageid=None, node_id=None):
    method = request.method
    return responsible_party(packageid=packageid, node_id=node_id, 
                             method=method, node_name=names.METADATAPROVIDER, 
                             back_page='metadata_provider_select', 
                             title='Metadata Provider')


@home.route('/associated_party_select/<packageid>', methods=['GET', 'POST'])
def associated_party_select(packageid=None):
    form = ResponsiblePartySelectForm(packageid=packageid)
    
    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = select_post(packageid, form, form_dict, 
                             'POST', 'associated_party_select', 
                             'metadata_provider_select', 
                             'pubdate', 
                             'associated_party')
        return redirect(url)

    # Process GET
    return rp_select_get(packageid=packageid, form=form, 
                         rp_name=names.ASSOCIATEDPARTY,
                         rp_singular='Associated Party', 
                         rp_plural='Associated Parties')


@home.route('/associated_party/<packageid>/<node_id>', methods=['GET', 'POST'])
def associated_party(packageid=None, node_id=None):
    method = request.method
    return responsible_party(packageid=packageid, node_id=node_id, 
                             method=method, node_name=names.ASSOCIATEDPARTY, 
                             back_page='associated_party_select', 
                             title='Associated Party')


def populate_responsible_party_form(form:ResponsiblePartyForm, node:Node):    
    salutation_node = node.find_child(names.SALUTATION)
    if salutation_node:
        form.salutation.data = salutation_node.content
    
    gn_node = node.find_child(names.GIVENNAME)
    if gn_node:
        form.gn.data = gn_node.content
    
    sn_node = node.find_child(names.SURNAME)
    if sn_node:
        form.sn.data = sn_node.content

    organization_node = node.find_child(names.ORGANIZATIONNAME)
    if organization_node:
        form.organization.data = organization_node.content

    position_name_node = node.find_child(names.POSITIONNAME)
    if position_name_node:
        form.position_name.data = position_name_node.content

    address_node = node.find_child(names.ADDRESS)

    if address_node:
        delivery_point_nodes = \
            address_node.find_all_children(names.DELIVERYPOINT)
        if len(delivery_point_nodes) > 0:
            form.address_1.data = delivery_point_nodes[0].content
        if len(delivery_point_nodes) > 1:
            form.address_2.data = delivery_point_nodes[1].content

        city_node = address_node.find_child(names.CITY)
        if city_node:
            form.city.data = city_node.content

        administrative_area_node = \
            address_node.find_child(names.ADMINISTRATIVEAREA)
        if administrative_area_node:
            form.state.data = administrative_area_node.content

        postal_code_node = address_node.find_child(names.POSTALCODE)
        if postal_code_node:
            form.postal_code.data = postal_code_node.content

        country_node = address_node.find_child(names.COUNTRY)
        if country_node:
            form.country.data = country_node.content

        phone_node = node.find_child(names.PHONE)
        if phone_node:
            form.phone.data = phone_node.content

   
    phone_nodes = node.find_all_children(names.PHONE)
    for phone_node in phone_nodes:
        phone_type = phone_node.attribute_value('phonetype')
        if phone_type == 'facsimile':
            form.fax.data = phone_node.content
        else:
            form.phone.data = phone_node.content

    email_node = node.find_child(names.ELECTRONICMAILADDRESS)
    if email_node:
        form.email.data = email_node.content

    online_url_node = node.find_child(names.ONLINEURL)
    if online_url_node:
        form.online_url.data = online_url_node.content

    role_node = node.find_child(names.ROLE)
    if role_node:
        form.role.data = role_node.content


@home.route('/pubdate/<packageid>', methods=['GET', 'POST'])
def pubdate(packageid=None):
    # Determine POST type
    if request.method == 'POST':
        if 'Back' in request.form:
            submit_type = 'Back'
        elif 'Next' in request.form:
            submit_type = 'Next'
        else:
            submit_type = None
    # Process POST
    form = PubDateForm(packageid=packageid)
    if form.validate_on_submit():
        pubdate = form.pubdate.data
        create_pubdate(packageid=packageid, pubdate=pubdate)
        new_page = 'associated_party_select' if (submit_type == 'Back') else 'abstract'
        return redirect(url_for(f'home.{new_page}', packageid=packageid))
    # Process GET
    eml_node = load_eml(packageid=packageid)
    pubdate_node = eml_node.find_child(child_name=names.PUBDATE)
    if pubdate_node:
        form.pubdate.data = pubdate_node.content
    return render_template('pubdate.html', 
                           title='Publication Date', 
                           packageid=packageid, form=form)


@home.route('/abstract/<packageid>', methods=['GET', 'POST'])
def abstract(packageid=None):
    # Determine POST type
    if request.method == 'POST':
        if 'Back' in request.form:
            submit_type = 'Back'
        elif 'Next' in request.form:
            submit_type = 'Next'
        else:
            submit_type = None
    # Process POST
    form = AbstractForm(packageid=packageid)
    if form.validate_on_submit():
        abstract = form.abstract.data
        create_abstract(packageid=packageid, abstract=abstract)
        new_page = 'pubdate' if (submit_type == 'Back') else 'keyword_select'
        return redirect(url_for(f'home.{new_page}', packageid=packageid))
    # Process GET
    eml_node = load_eml(packageid=packageid)
    abstract_node = eml_node.find_child(child_name=names.ABSTRACT)
    if abstract_node:
        form.abstract.data = abstract_node.content
    return render_template('abstract.html', 
                           title='Abstract', 
                           packageid=packageid, form=form)


@home.route('/intellectual_rights/<packageid>', methods=['GET', 'POST'])
def intellectual_rights(packageid=None):
    # Determine POST type
    if request.method == 'POST':
        if 'Back' in request.form:
            submit_type = 'Back'
        elif 'Next' in request.form:
            submit_type = 'Next'
        else:
            submit_type = None
    # Process POST
    form = IntellectualRightsForm(packageid=packageid)
    if form.validate_on_submit():
        if form.intellectual_rights_radio.data == 'CC0':
            intellectual_rights = INTELLECTUAL_RIGHTS_CC0
        elif form.intellectual_rights_radio.data == 'CCBY':
            intellectual_rights = INTELLECTUAL_RIGHTS_CC_BY
        else:
            intellectual_rights = form.intellectual_rights.data

        create_intellectual_rights(packageid=packageid, intellectual_rights=intellectual_rights)

        new_page = 'keyword_select' if (submit_type == 'Back') else 'geographic_coverage_select'
        return redirect(url_for(f'home.{new_page}', packageid=packageid))

    # Process GET
    eml_node = load_eml(packageid=packageid)
    intellectual_rights_node = eml_node.find_child(child_name=names.INTELLECTUALRIGHTS)
    if intellectual_rights_node:
        ir_content = intellectual_rights_node.content
        if ir_content == INTELLECTUAL_RIGHTS_CC0:
            form.intellectual_rights_radio.data = 'CC0'
            form.intellectual_rights.data = ''
        elif ir_content ==  INTELLECTUAL_RIGHTS_CC_BY:
            form.intellectual_rights_radio.data = 'CCBY'
            form.intellectual_rights.data = ''
        else:
            form.intellectual_rights_radio.data = "Other"
            form.intellectual_rights.data = intellectual_rights_node.content
    return render_template('intellectual_rights.html', 
                           title='Intellectual Rights', 
                           packageid=packageid, form=form)


@home.route('/geographic_coverage_select/<packageid>', methods=['GET', 'POST'])
def geographic_coverage_select(packageid=None):
    form = GeographicCoverageSelectForm(packageid=packageid)
    
    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = select_post(packageid, form, form_dict, 
                          'POST', 'geographic_coverage_select',
                          'intellectual_rights',
                          'temporal_coverage_select', 'geographic_coverage')
        return redirect(url)

    # Process GET
    gc_list = []
    title = "Geographic Coverage"

    eml_node = load_eml(packageid=packageid)
    if eml_node:
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            gc_list = list_geographic_coverages(dataset_node)

    return render_template('geographic_coverage_select.html', title=title,
                            gc_list=gc_list, form=form)


@home.route('/geographic_coverage/<packageid>/<node_id>', methods=['GET', 'POST'])
def geographic_coverage(packageid=None, node_id=None):
    # Determine POST type
    if request.method == 'POST':
        if 'Save Changes' in request.form:
            submit_type = 'Save Changes'
        elif 'Back' in request.form:
            submit_type = 'Back'
        else:
            submit_type = None
    form = GeographicCoverageForm(packageid=packageid)

    # Process POST
    if form.validate_on_submit():
        url = url_for('home.geographic_coverage_select', packageid=packageid)

        if submit_type == 'Save Changes':
            eml_node = load_eml(packageid=packageid)

            dataset_node = eml_node.find_child(names.DATASET)
            if not dataset_node:
                dataset_node = Node(names.DATASET)

            coverage_node = dataset_node.find_child(names.COVERAGE)
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
                url = (url_for('home.geographic_coverage', packageid=packageid, node_id=gc_node.id))

            if ebc and wbc and ebc < wbc:
                flash('East should be greater than or equal to West')
                url = (url_for('home.geographic_coverage', packageid=packageid, node_id=gc_node.id))

            save_both_formats(packageid=packageid, eml_node=eml_node)

        return redirect(url)

    # Process GET
    if node_id == '1':
        pass
    else:
        eml_node = load_eml(packageid=packageid)
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            coverage_node = dataset_node.find_child(names.COVERAGE)
            if coverage_node:
                gc_nodes = coverage_node.find_all_children(names.GEOGRAPHICCOVERAGE)
                if gc_nodes:
                    for gc_node in gc_nodes:
                        if node_id == gc_node.id:
                            populate_geographic_coverage_form(form, gc_node)
    
    return render_template('geographic_coverage.html', title='Geographic Coverage', form=form)


def populate_geographic_coverage_form(form:GeographicCoverageForm, node:Node):    
    geographic_description_node = node.find_child(names.GEOGRAPHICDESCRIPTION)
    if geographic_description_node:
        form.geographic_description.data = geographic_description_node.content
    
    wbc_node = node.find_child(names.WESTBOUNDINGCOORDINATE)
    if wbc_node:
        form.wbc.data = wbc_node.content
    ebc_node = node.find_child(names.EASTBOUNDINGCOORDINATE)
    if ebc_node:
        form.ebc.data = ebc_node.content
    nbc_node = node.find_child(names.NORTHBOUNDINGCOORDINATE)
    if nbc_node:
        form.nbc.data = nbc_node.content
    sbc_node = node.find_child(names.SOUTHBOUNDINGCOORDINATE)
    if sbc_node:
        form.sbc.data = sbc_node.content
    

def select_post(packageid=None, form=None, form_dict=None,
                method=None, this_page=None, back_page=None, 
                next_page=None, edit_page=None):
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
       return url_for(f'home.{new_page}', packageid=packageid, node_id=node_id)


@home.route('/temporal_coverage_select/<packageid>', methods=['GET', 'POST'])
def temporal_coverage_select(packageid=None):
    form = TemporalCoverageSelectForm(packageid=packageid)
    
    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = select_post(packageid, form, form_dict, 
                          'POST', 'temporal_coverage_select',
                          'geographic_coverage_select',
                          'taxonomic_coverage_select', 'temporal_coverage')
        return redirect(url)

    # Process GET
    title = "Temporal Coverage"
    tc_list = []

    eml_node = load_eml(packageid=packageid)
    if eml_node:
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            tc_list = list_temporal_coverages(dataset_node)

    return render_template('temporal_coverage_select.html', title=title,
                            tc_list=tc_list, form=form)


@home.route('/temporal_coverage/<packageid>/<node_id>', methods=['GET', 'POST'])
def temporal_coverage(packageid=None, node_id=None):
    tc_node_id = node_id

    # Determine POST type
    if request.method == 'POST':
        if 'Save Changes' in request.form:
            submit_type = 'Save Changes'
        elif 'Back' in request.form:
            submit_type = 'Back'
        else:
            submit_type = None
    form = TemporalCoverageForm(packageid=packageid)

    # Process POST
    if form.validate_on_submit():
        url = url_for('home.temporal_coverage_select', packageid=packageid)

        if submit_type == 'Save Changes':
            eml_node = load_eml(packageid=packageid)

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
                url = (url_for('home.temporal_coverage', packageid=packageid, node_id=tc_node_id))

            save_both_formats(packageid=packageid, eml_node=eml_node)

        return redirect(url)

    # Process GET
    if node_id == '1':
        pass
    else:
        eml_node = load_eml(packageid=packageid)
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            coverage_node = dataset_node.find_child(names.COVERAGE)
            if coverage_node:
                tc_nodes = coverage_node.find_all_children(names.TEMPORALCOVERAGE)
                if tc_nodes:
                    for tc_node in tc_nodes:
                        if node_id == tc_node.id:
                            populate_temporal_coverage_form(form, tc_node)
    
    return render_template('temporal_coverage.html', title='Temporal Coverage', form=form)


def populate_temporal_coverage_form(form:TemporalCoverageForm, node:Node):    
    begin_date_node = node.find_child(names.BEGINDATE)
    if begin_date_node:
        calendar_date_node = begin_date_node.find_child(names.CALENDARDATE)
        form.begin_date.data = calendar_date_node.content
    
        end_date_node = node.find_child(names.ENDDATE)
        if end_date_node:
            calendar_date_node = end_date_node.find_child(names.CALENDARDATE)
            form.end_date.data = calendar_date_node.content
    else:
        single_date_time_node = node.find_child(names.SINGLEDATETIME)
        if single_date_time_node:
            calendar_date_node = single_date_time_node.find_child(names.CALENDARDATE)
            form.begin_date.data = calendar_date_node.content
    

@home.route('/taxonomic_coverage_select/<packageid>', methods=['GET', 'POST'])
def taxonomic_coverage_select(packageid=None):
    form = TaxonomicCoverageSelectForm(packageid=packageid)
    
    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = select_post(packageid, form, form_dict, 
                          'POST', 'taxonomic_coverage_select',
                          'temporal_coverage_select',
                          'contact_select', 'taxonomic_coverage')
        return redirect(url)

    # Process GET
    title = "Taxonomic Coverage"
    txc_list = []

    eml_node = load_eml(packageid=packageid)
    if eml_node:
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            txc_list = list_taxonomic_coverages(dataset_node)

    return render_template('taxonomic_coverage_select.html', title=title,
                            txc_list=txc_list, form=form)


@home.route('/taxonomic_coverage/<packageid>/<node_id>', methods=['GET', 'POST'])
def taxonomic_coverage(packageid=None, node_id=None):
    # Determine POST type
    if request.method == 'POST':
        if 'Save Changes' in request.form:
            submit_type = 'Save Changes'
        elif 'Back' in request.form:
            submit_type = 'Back'
        else:
            submit_type = None
    form = TaxonomicCoverageForm(packageid=packageid)

    # Process POST
    if form.validate_on_submit():
        if submit_type == 'Save Changes':
            eml_node = load_eml(packageid=packageid)

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

        return redirect(url_for('home.taxonomic_coverage_select', packageid=packageid))

    # Process GET
    if node_id == '1':
        pass
    else:
        eml_node = load_eml(packageid=packageid)
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            coverage_node = dataset_node.find_child(names.COVERAGE)
            if coverage_node:
                txc_nodes = coverage_node.find_all_children(names.TAXONOMICCOVERAGE)
                if txc_nodes:
                    for txc_node in txc_nodes:
                        if node_id == txc_node.id:
                            populate_taxonomic_coverage_form(form, txc_node)
    
    return render_template('taxonomic_coverage.html', title='Taxonomic Coverage', form=form)


def populate_taxonomic_coverage_form(form:TaxonomicCoverageForm, node:Node):
    general_taxonomic_coverage_node = node.find_child(names.GENERALTAXONOMICCOVERAGE)
    if general_taxonomic_coverage_node:
        form.general_taxonomic_coverage.data = general_taxonomic_coverage_node.content
    
    taxonomic_classification_node = node.find_child(names.TAXONOMICCLASSIFICATION)
    populate_taxonomic_coverage_form_aux(form, taxonomic_classification_node)


def populate_taxonomic_coverage_form_aux(form:TaxonomicCoverageForm, node:Node=None):
    if node:
        taxon_rank_name_node = node.find_child(names.TAXONRANKNAME)
        taxon_rank_value_node = node.find_child(names.TAXONRANKVALUE)
        taxon_common_name_node = node.find_child(names.COMMONNAME)

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

        taxonomic_classification_node = node.find_child(names.TAXONOMICCLASSIFICATION)
        if taxonomic_classification_node:
            populate_taxonomic_coverage_form_aux(form, taxonomic_classification_node)
        

@home.route('/contact_select/<packageid>', methods=['GET', 'POST'])
def contact_select(packageid=None):
    form = ResponsiblePartySelectForm(packageid=packageid)
    
    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = select_post(packageid, form, form_dict, 
                             'POST', 'contact_select', 'taxonomic_coverage_select', 
                             'publisher', 'contact')
        return redirect(url)

    # Process GET
    return rp_select_get(packageid=packageid, form=form, rp_name='contact',
                         rp_singular='Contact', rp_plural='Contacts')


@home.route('/contact/<packageid>/<node_id>', methods=['GET', 'POST'])
def contact(packageid=None, node_id=None):
    method = request.method
    return responsible_party(packageid=packageid, node_id=node_id, 
                             method=method, node_name=names.CONTACT, 
                             back_page='contact_select', title='Contact')


@home.route('/publisher/<packageid>', methods=['GET', 'POST'])
def publisher(packageid=None):
    method = request.method
    node_id = '1'
    if packageid:
        eml_node = load_eml(packageid=packageid)
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            publisher_node = dataset_node.find_child(names.PUBLISHER)
            if publisher_node:
                node_id = publisher_node.id
    return responsible_party(packageid=packageid, node_id=node_id, 
                             method=method, node_name=names.PUBLISHER, 
                             back_page='contact_select', title='Publisher',
                             next_page='publication_place')


def process_up_button(packageid:str=None, node_id:str=None):
    process_updown_button(packageid, node_id, move_up)


def process_down_button(packageid:str=None, node_id:str=None):
    process_updown_button(packageid, node_id, move_down)


def process_updown_button(packageid:str=None, node_id:str=None, move_function=None):
    if packageid and node_id and move_function:
        eml_node = load_eml(packageid=packageid)
        child_node = Node.get_node_instance(node_id)
        if child_node:
            parent_node = child_node.parent
            if parent_node:
                move_function(parent_node, child_node)
                save_both_formats(packageid=packageid, eml_node=eml_node)


@home.route('/method_step_select/<packageid>', methods=['GET', 'POST'])
def method_step_select(packageid=None):
    form = MethodStepSelectForm(packageid=packageid)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        node_id = ''
        new_page = ''
        url = ''
        this_page = 'method_step_select'
        edit_page = 'method_step'
        back_page = 'publication_place'
        next_page = 'project'

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
                url = url_for(f'home.{new_page}', 
                                packageid=packageid, 
                                node_id=node_id)
            elif new_page == this_page: 
                url = url_for(f'home.{new_page}', 
                                packageid=packageid, 
                                node_id=node_id)
            elif new_page == back_page or new_page == next_page:
                url = url_for(f'home.{new_page}', 
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
@home.route('/method_step/<packageid>/<node_id>', methods=['GET', 'POST'])
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

    # Determine POST type
    if request.method == 'POST':
        next_page = 'home.method_step_select' # Save or Back sends us back to the list of method steps

        if 'Save Changes' in request.form:
            submit_type = 'Save Changes'
        elif 'Back' in request.form:
            submit_type = 'Back'

    # Process POST
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
        pass
    else:
        method_step_nodes = methods_node.find_all_children(names.METHODSTEP)
        if method_step_nodes:
            for ms_node in method_step_nodes:
                if node_id == ms_node.id:
                    populate_method_step_form(form, ms_node)
                    break
    
    return render_template('method_step.html', title='Method Step', form=form, packageid=packageid)


def populate_method_step_form(form:MethodStepForm, ms_node:Node):  
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


@home.route('/project/<packageid>', methods=['GET', 'POST'])
def project(packageid=None):
    form = ProjectForm(packageid=packageid)
    eml_node = load_eml(packageid=packageid)
    if eml_node:
        dataset_node = eml_node.find_child(names.DATASET)
        if not dataset_node:
            dataset_node = Node(names.DATASET, parent=eml_node)
            add_child(eml_node, dataset_node)

    # Determine POST type
    if request.method == 'POST':
        save = False
        if 'Back' in request.form:
            new_page = 'method_step_select'
        elif 'Next' in request.form:
            new_page = 'data_table_select'
        elif 'Save Changes' in request.form:
            new_page = 'project'
            save = True
        elif 'Edit Project Personnel' in request.form:
            new_page = 'project_personnel_select'
            save = True
            
    # Process POST
    if form.validate_on_submit():
        if save:
            title = form.title.data
            abstract = form.abstract.data
            funding = form.funding.data
            create_project(dataset_node, title, abstract, funding)
            save_both_formats(packageid=packageid, eml_node=eml_node)
        return redirect(url_for(f'home.{new_page}', packageid=packageid))

    # Process GET
    if dataset_node:
        project_node = dataset_node.find_child(names.PROJECT)
        if project_node:
            populate_project_form(form, project_node)

    return render_template('project.html', 
                        title='Project', 
                        packageid=packageid, 
                        form=form)


def populate_project_form(form:ProjectForm, project_node:Node):  
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
        form.abstract.data = abstract
        form.funding.data = funding


@home.route('/project_personnel_select/<packageid>', methods=['GET', 'POST'])
def project_personnel_select(packageid=None):
    form = ResponsiblePartySelectForm(packageid=packageid)
    
    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = select_post(packageid, form, form_dict, 
                             'POST', 'project_personnel_select', 'project', 
                             'project', 'project_personnel')
        return redirect(url)

    # Process GET
    return rp_select_get(packageid=packageid, form=form, rp_name='personnel',
                         rp_singular='Project Personnel', rp_plural='Project Personnel')


@home.route('/project_personnel/<packageid>/<node_id>', methods=['GET', 'POST'])
def project_personnel(packageid=None, node_id=None):
    method = request.method
    return responsible_party(packageid=packageid, node_id=node_id, 
                             method=method, node_name=names.PERSONNEL, 
                             back_page='project_personnel_select', title='Project Personnel')


@home.route('/access_select/<packageid>', methods=['GET', 'POST'])
def access_select(packageid=None, node_id=None):
    form = AccessSelectForm(packageid=packageid)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = access_select_post(packageid, form, form_dict, 
                                'POST', 'access_select', 'title', 
                                'creator_select', 'access')
        return redirect(url)

    # Process GET
    return access_select_get(packageid=packageid, form=form)


def access_select_get(packageid=None, form=None):
    # Process GET
    access_rules_list = []
    title = 'Access Rules'
    eml_node = load_eml(packageid=packageid)

    if eml_node:
        access_rules_list = list_access_rules(eml_node)
    
    return render_template('access_select.html', title=title,
                           packageid=packageid,
                           ar_list=access_rules_list, 
                           form=form)


def access_select_post(packageid=None, form=None, form_dict=None,
                          method=None, this_page=None, back_page=None, 
                          next_page=None, edit_page=None):
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
            return url_for(f'home.{new_page}', 
                            packageid=packageid, 
                            node_id=node_id)
        elif new_page == this_page: 
            return url_for(f'home.{new_page}', 
                            packageid=packageid, 
                            node_id=node_id)
        elif new_page == back_page or new_page == next_page:
            return url_for(f'home.{new_page}', 
                           packageid=packageid)


# node_id is the id of the access node being edited. If the value is
# '1', it means we are adding a new access node, otherwise we are
# editing an existing access node.
#
@home.route('/access/<packageid>/<node_id>', methods=['GET', 'POST'])
def access(packageid=None, node_id=None):
    eml_node = load_eml(packageid=packageid)

    if eml_node:
        access_node = eml_node.find_child(names.ACCESS)
    else:
        return

    if not access_node:
        access_node = Node(names.ACCESS, parent=eml_node)
        add_child(eml_node, access_node)

    form = AccessForm(packageid=packageid, node_id=node_id)

    # Determine POST type
    if request.method == 'POST':
        next_page = 'home.access_select' # Save or Back sends us back to the list of access rules

        if 'Save Changes' in request.form:
            submit_type = 'Save Changes'
        elif 'Back' in request.form:
            submit_type = 'Back'

    # Process POST
        if submit_type == 'Save Changes':
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

            save_both_formats(packageid=packageid, eml_node=eml_node)

        url = url_for(next_page, packageid=packageid)
        return redirect(url)

    # Process GET
    if node_id == '1':
        pass
    else:
        allow_nodes = access_node.find_all_children(names.ALLOW)
        if allow_nodes:
            for allow_node in allow_nodes:
                if node_id == allow_node.id:
                    populate_access_rule_form(form, allow_node)
                    break
    
    return render_template('access.html', title='Access Rule', form=form, packageid=packageid)


def populate_access_rule_form(form:AccessForm, allow_node:Node):  
    userid = ''
    permission = ''
    
    if allow_node:  
        principal_node = allow_node.find_child(names.PRINCIPAL)
        if principal_node:
            userid = principal_node.content

        permission_node = allow_node.find_child(names.PERMISSION)
        if permission_node:
            permission = permission_node.content 
         
        form.userid.data = userid
        form.permission.data = permission


@home.route('/keyword_select/<packageid>', methods=['GET', 'POST'])
def keyword_select(packageid=None, node_id=None):
    form = KeywordSelectForm(packageid=packageid)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = keyword_select_post(packageid, form, form_dict, 
                                      'POST', 'keyword_select', 'abstract', 
                                      'intellectual_rights', 'keyword')
        return redirect(url)

    # Process GET
    return keyword_select_get(packageid=packageid, form=form)


def keyword_select_get(packageid=None, form=None):
    # Process GET
    kw_list = []
    title = 'Keywords'
    eml_node = load_eml(packageid=packageid)

    if eml_node:
        kw_list = list_keywords(eml_node)
    
    return render_template('keyword_select.html', title=title,
                           packageid=packageid,
                           kw_list=kw_list, 
                           form=form)


def keyword_select_post(packageid=None, form=None, form_dict=None,
                          method=None, this_page=None, back_page=None, 
                          next_page=None, edit_page=None):
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
            return url_for(f'home.{new_page}', 
                            packageid=packageid, 
                            node_id=node_id)
        elif new_page == this_page: 
            return url_for(f'home.{new_page}', 
                            packageid=packageid, 
                            node_id=node_id)
        elif new_page == back_page or new_page == next_page:
            return url_for(f'home.{new_page}', 
                           packageid=packageid)


# node_id is the id of the keyword node being edited. If the value is
# '1', it means we are adding a new keyword node, otherwise we are
# editing an existing one.
#
@home.route('/keyword/<packageid>/<node_id>', methods=['GET', 'POST'])
def keyword(packageid=None, node_id=None):
    eml_node = load_eml(packageid=packageid)
    dataset_node = eml_node.find_child(names.DATASET)

    if dataset_node:
        keyword_set_node = dataset_node.find_child(names.KEYWORDSET)
    else:
        dataset_node = Node(names.DATASET, parent=eml_node)
        add_child(eml_node, dataset_node)

    if not keyword_set_node:
        keyword_set_node = Node(names.KEYWORDSET, parent=dataset_node)
        add_child(dataset_node, keyword_set_node)

    form = KeywordForm(packageid=packageid, node_id=node_id)

    # Determine POST type
    if request.method == 'POST':
        next_page = 'home.keyword_select' # Save or Back sends us back to the list of keywords

        if 'Save Changes' in request.form:
            submit_type = 'Save Changes'
        elif 'Back' in request.form:
            submit_type = 'Back'

    # Process POST
        if submit_type == 'Save Changes':
            keyword = form.keyword.data
            keyword_type = form.keyword_type.data
            keyword_node = Node(names.KEYWORD, parent=keyword_set_node)
            create_keyword(keyword_node, keyword, keyword_type)

            if node_id and len(node_id) != 1:
                old_keyword_node = Node.get_node_instance(node_id)

                if old_keyword_node:
                    keyword_parent_node = old_keyword_node.parent
                    keyword_parent_node.replace_child(old_keyword_node, 
                                                          keyword_node)
                else:
                    msg = f"No keyword node found in the node store with node id {node_id}"
                    raise Exception(msg)
            else:
                add_child(keyword_set_node, keyword_node)

            save_both_formats(packageid=packageid, eml_node=eml_node)

        url = url_for(next_page, packageid=packageid)
        return redirect(url)

    # Process GET
    if node_id == '1':
        pass
    else:
        keyword_nodes = keyword_set_node.find_all_children(names.KEYWORD)
        if keyword_nodes:
            for kw_node in keyword_nodes:
                if node_id == kw_node.id:
                    populate_keyword_form(form, kw_node)
                    break
    
    return render_template('keyword.html', title='Keyword', form=form, packageid=packageid)


def populate_keyword_form(form:KeywordForm, kw_node:Node):  
    keyword = ''
    keyword_type = ''
    
    if kw_node:  
        keyword = kw_node.content if kw_node.content else ''
        kw_type = kw_node.attribute_value('keywordType')
        keyword_type = kw_type if kw_type else ''

    form.keyword.data = keyword
    form.keyword_type.data = keyword_type


@home.route('/other_entity_select/<packageid>', methods=['GET', 'POST'])
def other_entity_select(packageid=None):
    form = OtherEntitySelectForm(packageid=packageid)
    
    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = select_post(packageid, form, form_dict, 
                             'POST', 'other_entity_select', 'data_table_select', 
                             'title', 'other_entity')
        return redirect(url)

    # Process GET
    eml_node = load_eml(packageid=packageid)
    oe_list = list_other_entities(eml_node)
    title = 'Other Entities'

    return render_template('other_entity_select.html', title=title,
                            oe_list=oe_list, form=form)


@home.route('/other_entity/<packageid>/<node_id>', methods=['GET', 'POST'])
def other_entity(packageid=None, node_id=None):
    dt_node_id = node_id
    # Determine POST type
    if request.method == 'POST':
        next_page = 'home.other_entity_select'

        if 'Save Changes' in request.form:
            submit_type = 'Save Changes'
        elif 'Access' in request.form:
            next_page = 'home.entity_access_select'
            submit_type = 'Save Changes'
        elif 'Methods' in request.form:
            next_page = 'home.entity_method_step_select'
            submit_type = 'Save Changes'
        elif 'Geographic' in request.form:
            next_page = 'home.entity_geographic_coverage_select'
            submit_type = 'Save Changes'
        elif 'Temporal' in request.form:
            next_page = 'home.entity_temporal_coverage_select'
            submit_type = 'Save Changes'
        elif 'Taxonomic' in request.form:
            next_page = 'home.entity_taxonomic_coverage_select'
            submit_type = 'Save Changes'
        elif 'Back' in request.form:
            submit_type = 'Back'
        else:
            submit_type = None
    form = OtherEntityForm(packageid=packageid)

    # Process POST
    if form.validate_on_submit():
        eml_node = load_eml(packageid=packageid)
        
        if submit_type == 'Save Changes':
            dataset_node = eml_node.find_child(names.DATASET)
            if not dataset_node:
                dataset_node = Node(names.DATASET)

            entity_name = form.entity_name.data
            entity_type = form.entity_type.data
            entity_description = form.entity_description.data
            object_name = form.object_name.data
            size = form.size.data
            num_header_lines = form.num_header_lines.data
            record_delimiter = form.record_delimiter.data
            attribute_orientation = form.attribute_orientation.data
            field_delimiter = form.field_delimiter.data
            online_url = form.online_url.data

            dt_node = Node(names.OTHERENTITY, parent=dataset_node)

            create_other_entity(
                dt_node, 
                entity_name,
                entity_type,
                entity_description,
                object_name,
                size,
                num_header_lines,
                record_delimiter,
                attribute_orientation,
                field_delimiter,
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

            save_both_formats(packageid=packageid, eml_node=eml_node)

        if (next_page == 'home.entity_access_select' or 
            next_page == 'home.entity_method_step_select' or
            next_page == 'home.entity_geographic_coverage_select' or
            next_page == 'home.entity_temporal_coverage_select' or
            next_page == 'home.entity_taxonomic_coverage_select'
            ):
            return redirect(url_for(next_page, 
                                    packageid=packageid,
                                    dt_element_name=names.OTHERENTITY,
                                    dt_node_id=dt_node_id))
        else:
            return redirect(url_for(next_page, 
                                    packageid=packageid, 
                                    dt_node_id=dt_node_id))

    # Process GET
    if dt_node_id == '1':
        pass
    else:
        eml_node = load_eml(packageid=packageid)
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            dt_nodes = dataset_node.find_all_children(names.OTHERENTITY)
            if dt_nodes:
                for dt_node in dt_nodes:
                    if dt_node_id == dt_node.id:
                        populate_other_entity_form(form, dt_node)
    
    return render_template('other_entity.html', title='Other Entity', form=form)


def populate_other_entity_form(form:OtherEntityForm, node:Node):    
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


@home.route('/entity_access_select/<packageid>/<dt_element_name>/<dt_node_id>', 
            methods=['GET', 'POST'])
def entity_access_select(packageid:str=None, dt_element_name:str=None, dt_node_id:str=None):
    form = AccessSelectForm(packageid=packageid)

    parent_page = 'data_table'
    if dt_element_name == names.OTHERENTITY:
        parent_page = 'other_entity'

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = entity_access_select_post(packageid, form, form_dict, 
                                'POST', 'entity_access_select', parent_page, 
                                parent_page, 'entity_access',
                                dt_element_name=dt_element_name,
                                dt_node_id=dt_node_id)
        return redirect(url)

    # Process GET
    return entity_access_select_get(packageid=packageid, form=form, dt_node_id=dt_node_id)


def entity_access_select_get(packageid=None, form=None, dt_node_id=None):
    # Process GET
    access_rules_list = []
    title = 'Access Rules'
    entity_name = ''
    load_eml(packageid=packageid)

    if dt_node_id == '1':
        pass
    else:
        data_table_node = Node.get_node_instance(dt_node_id)
        if data_table_node:
            entity_name = entity_name_from_data_table(data_table_node)
            physical_node = data_table_node.find_child(names.PHYSICAL)
            if physical_node:
                distribution_node = physical_node.find_child(names.DISTRIBUTION)
                if distribution_node:
                    access_rules_list = list_access_rules(distribution_node)

    return render_template('access_select.html', 
                           title=title,
                           entity_name=entity_name, 
                           ar_list=access_rules_list, 
                           form=form)


def entity_access_select_post(packageid=None, form=None, form_dict=None,
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
            return url_for(f'home.{new_page}', 
                            packageid=packageid,
                            dt_element_name=dt_element_name,
                            dt_node_id=dt_node_id, 
                            node_id=node_id)
        elif new_page == this_page: 
            return url_for(f'home.{new_page}', 
                            packageid=packageid, 
                            dt_element_name=dt_element_name,
                            dt_node_id=dt_node_id)
        else:
            return url_for(f'home.{new_page}', 
                           packageid=packageid,
                           node_id=dt_node_id)



# node_id is the id of the access allow node being edited. If the value is
# '1', it means we are adding a new access node, otherwise we are
# editing an existing access node.
#
# dt_element_name will be either names.DATATABLE or names.OTHERENTITY
#
@home.route('/entity_access/<packageid>/<dt_element_name>/<dt_node_id>/<node_id>', methods=['GET', 'POST'])
def entity_access(packageid=None, dt_element_name=None, dt_node_id=None, node_id=None):
    form = AccessForm(packageid=packageid, node_id=node_id)
    allow_node_id = node_id

    # Determine POST type
    if request.method == 'POST':
        next_page = 'home.entity_access_select' # Save or Back sends us back to the list of access rules

        if 'Save Changes' in request.form:
            submit_type = 'Save Changes'
        elif 'Back' in request.form:
            submit_type = 'Back'

    # Process POST
        if submit_type == 'Save Changes':
            dt_node = None
            distribution_node = None
            eml_node = load_eml(packageid=packageid)
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

            save_both_formats(packageid=packageid, eml_node=eml_node)
            allow_node_id = allow_node.id

        url = url_for(next_page, 
                      packageid=packageid, 
                      dt_element_name=dt_element_name,
                      dt_node_id=dt_node_id, 
                      node_id=allow_node_id)
        return redirect(url)

    # Process GET
    if node_id == '1':
        pass
    else:
        eml_node = load_eml(packageid=packageid)
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
    
    return render_template('access.html', title='Access Rule', form=form, packageid=packageid)


@home.route('/entity_method_step_select/<packageid>/<dt_element_name>/<dt_node_id>', 
            methods=['GET', 'POST'])
def entity_method_step_select(packageid=None, dt_element_name:str=None, dt_node_id:str=None):
    form = MethodStepSelectForm(packageid=packageid)

    parent_page = 'data_table'
    if dt_element_name == names.OTHERENTITY:
        parent_page = 'other_entity'

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)

        url = entity_select_post(packageid, form, form_dict, 
                          'POST', 'entity_method_step_select',
                          parent_page, parent_page, 'entity_method_step',
                          dt_element_name, dt_node_id)
        return redirect(url)

    # Process GET
    method_step_list = []
    title = 'Method Steps'
    entity_name = ''
    load_eml(packageid=packageid)

    if dt_node_id == '1':
        pass
    else:
        data_table_node = Node.get_node_instance(dt_node_id)
        if data_table_node:
            entity_name = entity_name_from_data_table(data_table_node)
            method_step_list = list_method_steps(data_table_node)
    
    return render_template('method_step_select.html', 
                           title=title,
                           entity_name=entity_name,
                           method_step_list=method_step_list, 
                           form=form)


# node_id is the id of the methodStep node being edited. If the value is
# '1', it means we are adding a new methodStep node, otherwise we are
# editing an existing one.
#
# dt_element_name will be either names.DATATABLE or names.OTHERENTITY
#
@home.route('/entity_method_step/<packageid>/<dt_element_name>/<dt_node_id>/<node_id>', 
            methods=['GET', 'POST'])
def entity_method_step(packageid=None, dt_element_name=None, dt_node_id=None, node_id=None):
    form = MethodStepForm(packageid=packageid, node_id=node_id)
    ms_node_id = node_id

    # Determine POST type
    if request.method == 'POST':
        next_page = 'home.entity_method_step_select' # Save or Back sends us back to the list of method steps

        if 'Save Changes' in request.form:
            submit_type = 'Save Changes'
        elif 'Back' in request.form:
            submit_type = 'Back'

    # Process POST
    if form.validate_on_submit():
        if submit_type == 'Save Changes':
            dt_node = None
            eml_node = load_eml(packageid=packageid)
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

            save_both_formats(packageid=packageid, eml_node=eml_node)
            ms_node_id = method_step_node.id

        url = url_for(next_page, 
                      packageid=packageid, 
                      dt_element_name=dt_element_name,
                      dt_node_id=dt_node_id, 
                      node_id=ms_node_id)
        return redirect(url)


    # Process GET
    if node_id == '1':
        pass
    else:
        eml_node = load_eml(packageid=packageid)
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
    
    return render_template('method_step.html', title='Method Step', form=form, packageid=packageid)


@home.route('/entity_geographic_coverage_select/<packageid>/<dt_element_name>/<dt_node_id>',
            methods=['GET', 'POST'])
def entity_geographic_coverage_select(packageid=None, dt_element_name:str=None, dt_node_id:str=None):
    form = GeographicCoverageSelectForm(packageid=packageid)
    
    parent_page = 'data_table'
    if dt_element_name == names.OTHERENTITY:
        parent_page = 'other_entity'

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = entity_select_post(packageid, form, form_dict, 
                          'POST', 'entity_geographic_coverage_select',
                          parent_page, parent_page, 'entity_geographic_coverage',
                          dt_element_name, dt_node_id)
        return redirect(url)

    # Process GET
    gc_list = []
    title = "Geographic Coverage"
    entity_name = ''
    load_eml(packageid=packageid)

    if dt_node_id == '1':
        pass
    else:
        data_table_node = Node.get_node_instance(dt_node_id)
        if data_table_node:
            entity_name = entity_name_from_data_table(data_table_node)
            gc_list = list_geographic_coverages(data_table_node)

    return render_template('geographic_coverage_select.html', 
                            title=title,
                            entity_name=entity_name,
                            gc_list=gc_list, 
                            form=form)


@home.route('/entity_geographic_coverage/<packageid>/<dt_element_name>/<dt_node_id>/<node_id>', 
            methods=['GET', 'POST'])
def entity_geographic_coverage(packageid=None, dt_element_name=None, dt_node_id=None, node_id=None):
    form = GeographicCoverageForm(packageid=packageid)
    gc_node_id = node_id

    # Determine POST type
    if request.method == 'POST':
        next_page = 'home.entity_geographic_coverage_select' # Save or Back sends us back to the list of method steps

        if 'Save Changes' in request.form:
            submit_type = 'Save Changes'
        elif 'Back' in request.form:
            submit_type = 'Back'

    # Process POST
    if form.validate_on_submit():
        if submit_type == 'Save Changes':
            dt_node = None
            eml_node = load_eml(packageid=packageid)

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
                next_page = 'home.entity_geographic_coverage'

            if ebc and wbc and ebc < wbc:
                flash('East should be greater than or equal to West')
                next_page = 'home.entity_geographic_coverage'

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

            save_both_formats(packageid=packageid, eml_node=eml_node)
            gc_node_id = gc_node.id

        url = url_for(next_page, 
                      packageid=packageid, 
                      dt_element_name=dt_element_name,
                      dt_node_id=dt_node_id, 
                      node_id=gc_node_id)

        return redirect(url)

    # Process GET
    if node_id == '1':
        pass
    else:
        eml_node = load_eml(packageid=packageid)
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
    
    return render_template('geographic_coverage.html', title='Geographic Coverage', form=form, packageid=packageid)


def entity_select_post(packageid=None, form=None, form_dict=None,
                method=None, this_page=None, back_page=None, 
                next_page=None, edit_page=None, 
                dt_element_name:str=None, dt_node_id:str=None,):
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
            url = url_for(f'home.{new_page}', 
                          packageid=packageid,
                          dt_element_name=dt_element_name,
                          dt_node_id=dt_node_id, 
                          node_id=node_id)
        elif new_page == this_page: 
            url = url_for(f'home.{new_page}', 
                          packageid=packageid, 
                          dt_element_name=dt_element_name,
                          dt_node_id=dt_node_id)
        else:
            url = url_for(f'home.{new_page}', 
                          packageid=packageid,
                          node_id=dt_node_id)
        return url


@home.route('/entity_temporal_coverage_select/<packageid>/<dt_element_name>/<dt_node_id>', 
            methods=['GET', 'POST'])
def entity_temporal_coverage_select(packageid=None, dt_element_name:str=None, dt_node_id:str=None):
    form = TemporalCoverageSelectForm(packageid=packageid)
    
    parent_page = 'data_table'
    if dt_element_name == names.OTHERENTITY:
        parent_page = 'other_entity'

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = entity_select_post(packageid, form, form_dict, 
                          'POST', 'entity_temporal_coverage_select',
                          parent_page, parent_page, 'entity_temporal_coverage',
                          dt_element_name, dt_node_id)
        return redirect(url)

    # Process GET
    tc_list = []
    title = "Temporal Coverage"
    entity_name = ''
    load_eml(packageid=packageid)

    if dt_node_id == '1':
        pass
    else:
        data_table_node = Node.get_node_instance(dt_node_id)
        if data_table_node:
            entity_name = entity_name_from_data_table(data_table_node)
            tc_list = list_temporal_coverages(data_table_node)

    return render_template('temporal_coverage_select.html', 
                            title=title,
                            entity_name=entity_name,
                            tc_list=tc_list, 
                            form=form)


@home.route('/entity_temporal_coverage/<packageid>/<dt_element_name>/<dt_node_id>/<node_id>',
            methods=['GET', 'POST'])
def entity_temporal_coverage(packageid=None, dt_element_name=None, dt_node_id=None, node_id=None):
    form = TemporalCoverageForm(packageid=packageid)
    tc_node_id = node_id

    # Determine POST type
    if request.method == 'POST':
        next_page = 'home.entity_temporal_coverage_select' # Save or Back sends us back to the list of method steps

        if 'Save Changes' in request.form:
            submit_type = 'Save Changes'
        elif 'Back' in request.form:
            submit_type = 'Back'

    # Process POST
    if form.validate_on_submit():
        if submit_type == 'Save Changes':
            dt_node = None
            eml_node = load_eml(packageid=packageid)

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
                next_page = 'home.entity_temporal_coverage'

            save_both_formats(packageid=packageid, eml_node=eml_node)

        url = url_for(next_page, 
                      packageid=packageid, 
                      dt_element_name=dt_element_name,
                      dt_node_id=dt_node_id, 
                      node_id=tc_node_id)
        return redirect(url)

    # Process GET
    if node_id == '1':
        pass
    else:
        eml_node = load_eml(packageid=packageid)
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
    
    return render_template('temporal_coverage.html', title='Temporal Coverage', form=form, packageid=packageid)


@home.route('/entity_taxonomic_coverage_select/<packageid>/<dt_element_name>/<dt_node_id>', 
            methods=['GET', 'POST'])
def entity_taxonomic_coverage_select(packageid=None, dt_element_name:str=None, dt_node_id:str=None):
    form = TaxonomicCoverageSelectForm(packageid=packageid)
    
    parent_page = 'data_table'
    if dt_element_name == names.OTHERENTITY:
        parent_page = 'other_entity'

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = entity_select_post(packageid, form, form_dict, 
                          'POST', 'entity_taxonomic_coverage_select',
                          parent_page, parent_page, 'entity_taxonomic_coverage',
                          dt_element_name, dt_node_id)
        return redirect(url)

    # Process GET
    txc_list = []
    title = "Taxonomic Coverage"
    entity_name = ''
    load_eml(packageid=packageid)

    if dt_node_id == '1':
        pass
    else:
        data_table_node = Node.get_node_instance(dt_node_id)
        if data_table_node:
            entity_name = entity_name_from_data_table(data_table_node)
            txc_list = list_taxonomic_coverages(data_table_node)

    return render_template('taxonomic_coverage_select.html', 
                            title=title,
                            entity_name=entity_name,
                            txc_list=txc_list, 
                            form=form)


@home.route('/entity_taxonomic_coverage/<packageid>/<dt_element_name>/<dt_node_id>/<node_id>',
            methods=['GET', 'POST'])
def entity_taxonomic_coverage(packageid=None, dt_element_name=None, dt_node_id=None, node_id=None):
    form = TaxonomicCoverageForm(packageid=packageid)
    txc_node_id = node_id

    # Determine POST type
    if request.method == 'POST':
        next_page = 'home.entity_taxonomic_coverage_select' # Save or Back sends us back to the list of method steps

        if 'Save Changes' in request.form:
            submit_type = 'Save Changes'
        elif 'Back' in request.form:
            submit_type = 'Back'

    # Process POST
    if form.validate_on_submit():
        if submit_type == 'Save Changes':
            dt_node = None
            eml_node = load_eml(packageid=packageid)

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

            save_both_formats(packageid=packageid, eml_node=eml_node)
            txc_node_id = txc_node.id

        url = url_for(next_page, 
                      packageid=packageid, 
                      dt_element_name=dt_element_name,
                      dt_node_id=dt_node_id, 
                      node_id=txc_node_id)
        return redirect(url)

    # Process GET
    if node_id == '1':
        pass
    else:
        eml_node = load_eml(packageid=packageid)
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
                                        populate_temporal_coverage_form(form, txc_node)
                                        break
    
    return render_template('taxonomic_coverage.html', title='Taxonomic Coverage', form=form, packageid=packageid)


def compare_begin_end_dates(begin_date_str:str=None, end_date_str:str=None):
    begin_date = None
    end_date = None
    flash_msg = None

    if len(begin_date_str) == 4:
        begin_date_str += '-01-01'

    if len(end_date_str) == 4:
        end_date_str += '-01-01'

    if begin_date_str and end_date_str:
        begin_date = date.fromisoformat(begin_date_str)
        end_date = date.fromisoformat(end_date_str)

    if begin_date and end_date and begin_date > end_date:
        flash_msg = 'Begin date should be less than or equal to end date'

    return flash_msg
