"""
Helper functions for generating lists of items for use, for example, in pages where user selects from a list of options.
"""

import collections
import html
import os
from os import listdir
from os.path import isfile, join

from flask import flash
from flask_login import current_user

from metapype.eml import names
from metapype.model.node import Node
from webapp import Config

from webapp.auth import user_data as user_data
from webapp.home.home_utils import log_info
from webapp.home.metapype_client import VariableType
from webapp.home.texttype_node_processing import excerpt_text
from webapp.home.utils.import_nodes import compose_rp_label

NO_OP = ''
UP_ARROW = html.unescape('&#x2B06;')
DOWN_ARROW = html.unescape('&#x2B07;')


def get_upval(i:int):
    """
    Return the value to be used for the "up" button in a list of items. If i is 0 (so we're at the top of a list),
    return NO_OP, which means don't display a button. Otherwise, return the up arrow.

    i is the index of the item in the list.
    """
    return NO_OP if i == 0 else UP_ARROW


def get_downval(i:int, n:int):
    """
    Return the value to be used for the "down" button in a list of items. If i >= n (so we're at the bottom of a list),
    return NO_OP, which means don't display a button. Otherwise, return the down arrow.

    i is the index of the item in the list, n is the number of items in the list.
    """
    return NO_OP if i >= n else DOWN_ARROW


def template_display_name(template_path:str):
    template_dir = Config.TEMPLATE_DIR
    if template_dir[-1] != '/':
        template_dir += '/'
    template_path = template_path.replace(template_dir, '')
    template_dir = os.path.dirname(template_path)
    template_basename = os.path.basename(template_path).replace('.json', '')
    segments = template_dir.split('/')
    segments.append(template_basename)
    return ' | '.join(segments)


def list_templates():
    template_dir = Config.TEMPLATE_DIR
    if template_dir[-1] != '/':
        template_dir += '/'
    templates = []
    for root, dirs, files in os.walk(template_dir):
        for name in files:
            if name.endswith('.json'):
                templates.append((root, name))
    choices = []
    for template in templates:
        name = template[1].replace('.json', '')
        segments = template[0].replace(template_dir, '').split('/')
        segments.append(name)
        choices.append((os.path.join(template[0], template[1]), ' | '.join(segments)))
    return sorted(choices)


def list_data_packages(flag_current=False, include_current=True, current_user_directory_only=True):
    """
    Returns a list of all data packages in the current user's account, as tuples suitable for
    use in a select options list, e.g., by Open... document selection.  If flag_current is True, the current
    package is indicated. If include_current is False, the current package is excluded from the list.

    current_user_directory_only=True means search the current user's directory and ignore collaboration
    redirection.
    """
    choices = []
    user_documents = sorted(user_data.get_user_document_list(current_user_directory_only=current_user_directory_only),
                            key=str.casefold)  # case-insensitive sort
    # Create the annotation for the current package, if requested, or else an empty string.
    current_annotation = ' (current data package)' if flag_current else ''
    # Create the list of choices
    for document in user_documents:
        choice_tuple = (document, document)
        if document == current_user.get_filename():
            if not include_current:
                # If we're not including the current package, skip it.
                continue
            # Add the (possibly empty) annotation for the current package.
            choice_tuple = (document, f'{document}{current_annotation}')
        choices.append(choice_tuple)
    return choices


def list_files_in_dir(dirpath):
    """ Return a list of files (regular files, not directories) in the directory at dirpath. """
    return [f for f in listdir(dirpath) if isfile(join(dirpath, f))]


def list_data_tables(eml_node:Node=None, to_skip:str=None):
    """
    Returns a list of all data tables in the current EML document, as namedtuples of type DT_Entry.

    If to_skip is not None, it is the id of a data table to skip in the list. This is used, for example,
    when cloning column attributes from one data table to another, where we don't want to clone a table
    onto itself.
    """
    dt_list = []
    if eml_node:
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            dt_nodes = dataset_node.find_all_children(names.DATATABLE)
            DT_Entry = collections.namedtuple(
                'DT_Entry',
                ["id", "label", "object_name", "was_uploaded", "upval", "downval"],
                 rename=False)
            for i, dt_node in enumerate(dt_nodes):
                id = dt_node.id
                if to_skip and id == to_skip:
                    continue
                label, object_name = compose_entity_label(dt_node)
                was_uploaded = user_data.data_table_was_uploaded(object_name)
                upval = get_upval(i)
                downval = get_downval(i+1, len(dt_nodes))
                dt_entry = DT_Entry(id=id,
                                    label=label,
                                    object_name=object_name,
                                    was_uploaded=was_uploaded,
                                    upval=upval,
                                    downval=downval)
                dt_list.append(dt_entry)
    return dt_list


def list_data_table_columns(dt_node:Node=None):
    """
    Returns a list of data column names in a data table according to the package's metadata (as opposed to column
    names found in the data file itself).
    """
    dt_columns_list = []
    if dt_node:
        attribute_name_nodes = []
        dt_node.find_all_descendants(names.ATTRIBUTENAME, attribute_name_nodes)
        for attribute_name_node in attribute_name_nodes:
            dt_columns_list.append([attribute_name_node.id, attribute_name_node.content])
    return dt_columns_list


def list_other_entities(eml_node:Node=None):
    """
    Returns a list of all other data entities in the current EML document, as namedtuples of type DE_Entry.
    """

    oe_list = []
    if eml_node:
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            oe_nodes = dataset_node.find_all_children(names.OTHERENTITY)
            OE_Entry = collections.namedtuple(
                'OE_Entry',
                ["id", "label", "object_name", "was_uploaded", "upval", "downval"],
                rename=False)
            for i, oe_node in enumerate(oe_nodes):
                id = oe_node.id
                label, object_name = compose_entity_label(oe_node)
                was_uploaded = user_data.data_table_was_uploaded(object_name)
                upval = get_upval(i)
                downval = get_downval(i+1, len(oe_nodes))
                oe_entry = OE_Entry(id=id,
                                    label=label,
                                    object_name=object_name,
                                    was_uploaded=was_uploaded,
                                    upval=upval,
                                    downval=downval)
                oe_list.append(oe_entry)
    return oe_list


def compose_entity_label(entity_node:Node=None):
    """
    Given an entity node (i.e., a data table or other entity), return a tuple of the entity's label and object name.
    """
    label = ''
    object_name = ''
    if entity_node:
        entity_name_node = entity_node.find_child(names.ENTITYNAME)
        if entity_name_node:
            label = entity_name_node.content
        object_name_node = entity_node.find_descendant(names.OBJECTNAME)
        if object_name_node:
            object_name = object_name_node.content
    return label, object_name


def mscale_from_attribute(att_node: Node = None):
    """
    Given an attribute node, return the measurement scale as a VariableType enum value.
    """
    if att_node:
        mscale_node = att_node.find_child(names.MEASUREMENTSCALE)

        if mscale_node:

            # Formerly, Categorical variables were nominal. But now that we're importing externally created XML
            #  files, they may be ordinal.
            nominal_or_ordinal_node = mscale_node.find_child(names.NOMINAL)
            if not nominal_or_ordinal_node:
                nominal_or_ordinal_node = mscale_node.find_child(names.ORDINAL)
            if nominal_or_ordinal_node:
                non_numeric_domain_node = nominal_or_ordinal_node.find_child(names.NONNUMERICDOMAIN)
                if non_numeric_domain_node:
                    enumerated_domain_node = non_numeric_domain_node.find_child(names.ENUMERATEDDOMAIN)
                    if enumerated_domain_node:
                        return VariableType.CATEGORICAL.name
                    text_domain_node = non_numeric_domain_node.find_child(names.TEXTDOMAIN)
                    if text_domain_node:
                        return VariableType.TEXT.name

            # Formerly, Numerical variables were ratio. But now that we're importing externally created XML
            #  files, they may be interval.
            ratio_or_interval_node = mscale_node.find_child(names.RATIO)
            if not ratio_or_interval_node:
                ratio_or_interval_node = mscale_node.find_child(names.INTERVAL)
            if ratio_or_interval_node:
                return VariableType.NUMERICAL.name

            date_time_node = mscale_node.find_child(names.DATETIME)
            if date_time_node:
                return VariableType.DATETIME.name

    return None


def list_attributes(data_table_node:Node=None, caller:str=None, dt_node_id:str=None):
    """
    Returns a list of all attributes (columns) in the specified data table (according to its metadata),
    as namedtuples of type ATT_Entry.
    """

    def compose_attribute_label(att_node: Node = None):
        label = ''
        if att_node:
            attribute_name_node = att_node.find_child(names.ATTRIBUTENAME)
            if attribute_name_node:
                attribute_name = attribute_name_node.content
                label = attribute_name
        return label

    def compose_attribute_mscale(att_node: Node = None):

        mscale = ''
        if att_node:
            mscale = mscale_from_attribute(att_node)
            if mscale == VariableType.CATEGORICAL.name:
                mscale = 'Categorical'
            elif mscale == VariableType.NUMERICAL.name:
                mscale = 'Numerical'
            elif mscale == VariableType.TEXT.name:
                mscale = 'Text'
            elif mscale == VariableType.DATETIME.name:
                mscale = 'DateTime'
        return mscale

    att_list = []
    if data_table_node:
        attribute_list_node = data_table_node.find_child(names.ATTRIBUTELIST)
        if attribute_list_node:
            att_nodes = attribute_list_node.find_all_children(names.ATTRIBUTE)
            ATT_Entry = collections.namedtuple(
                'ATT_Entry',
                ["id", "column_number", "label", "mscale", "upval", "downval"],
                 rename=False)
            for i, att_node in enumerate(att_nodes):
                id = att_node.id
                column_number = str(i+1)
                label = compose_attribute_label(att_node)
                mscale = compose_attribute_mscale(att_node)
                upval = get_upval(i)
                downval = get_downval(i+1, len(att_nodes))
                att_entry = ATT_Entry(id=id,
                                      column_number=column_number,
                                      label=label,
                                      mscale=mscale,
                                      upval=upval,
                                      downval=downval)
                att_list.append(att_entry)

    if Config.LOG_DEBUG:
        log_info(f'Attribute list: caller={caller} dt_node_id={dt_node_id}')
        if not data_table_node:
            log_info('*** data_table_node not found ***')
        else:
            log_info(f'data_table_node.id={data_table_node.id}')
        for entry in att_list:
            log_info(f'{entry.id} {entry.label}')

    if Config.FLASH_DEBUG:
        flash(f'Attribute list: {att_list}')

    return att_list


def list_responsible_parties(eml_node:Node=None, node_name:str=None, project_node_id:str=None):
    """
    Returns a list of all responsible parties of a particular kind (i.e., creators, project personnel, etc., according
    to the specified node name) in the specified EML document, as namedtuples of type RP_Entry.

    If node_name is "personnel", we may be listing project personnel for the dataset's project or for a related project.
    If we're listing project personnel for a related project, then the project_node_id is provided and is the ID of the
    related project node. Otherwise, if the project_node_id is None, we're listing project personnel for the dataset's
    project.
    """
    rp_list = []
    if eml_node:
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            # Usually the parent node is the dataset node, but if the node name is "personnel", then the parent node
            #  is a project node.
            parent_node = dataset_node
            if node_name == names.PERSONNEL:
                parent_node = None
                # If no project node ID is specified, then we're listing project personnel for the dataset's project.
                if not project_node_id:
                    project_node = dataset_node.find_child(names.PROJECT)
                    if project_node:
                        parent_node = project_node
                elif project_node_id != '1':
                    parent_node = Node.get_node_instance(project_node_id)
                if parent_node is None:
                    return rp_list

            rp_nodes = parent_node.find_all_children(node_name)
            RP_Entry = collections.namedtuple(
                'RP_Entry', ["id", "label", "upval", "downval"],
                 rename=False)
            for i, rp_node in enumerate(rp_nodes):
                label = compose_rp_label(rp_node)
                id = f"{rp_node.id}|{project_node_id}"
                upval = get_upval(i)
                downval = get_downval(i+1, len(rp_nodes))
                rp_entry = RP_Entry(id=id, label=label, upval=upval, downval=downval)
                rp_list.append(rp_entry)
    return rp_list


def list_geographic_coverages(parent_node:Node=None):
    """
    Returns a list of all geographic coverages in the specified EML document, as namedtuples of type GC_Entry.
    """
    gc_list = []
    max_len = 40
    if parent_node:
        coverage_node = parent_node.find_child(names.COVERAGE)
        if coverage_node:
            gc_nodes = \
                coverage_node.find_all_children(names.GEOGRAPHICCOVERAGE)
            GC_Entry = collections.namedtuple(
                'GC_Entry',
                ["id", "geographic_description", "label", "upval", "downval"],
                rename=False)
            for i, gc_node in enumerate(gc_nodes):
                description = ''
                id = gc_node.id
                upval = get_upval(i)
                downval = get_downval(i+1, len(gc_nodes))
                geographic_description_node = \
                    gc_node.find_child(names.GEOGRAPHICDESCRIPTION)
                if geographic_description_node:
                    description = geographic_description_node.content
                    try:
                        if description and len(description) > max_len:
                            description = description[0:max_len]
                    except:
                        pass
                label = compose_gc_label(gc_node)
                gc_entry = GC_Entry(id=id,
                            geographic_description=description,
                            label=label,
                            upval=upval, downval=downval)
                gc_list.append(gc_entry)
    return gc_list


def compose_gc_label(gc_node:Node=None):
    """
    Composes a label for a geographic coverage table entry.
    """

    def massage_altitude_units(units):
        """
        Returns a more readable version of certain altitude units.
        """
        retval = units
        if units == 'Foot_US':
            retval = 'foot (US)'
        elif units == 'nauticalMile':
            retval = 'nautical mile'
        elif units == 'Foot_Gold_Coast':
            retval = 'foot (Gold Coast)'
        elif units == 'Yard_Indian':
            retval = 'yard (India)'
        elif units == 'Link_Clarke':
            retval = 'Clarke link'
        elif units == 'Yard_Sears':
            retval = 'Sears yard'
        return retval

    label = ''
    if gc_node:
        bc_node = gc_node.find_child(names.BOUNDINGCOORDINATES)
        if bc_node:
            wbc_node = bc_node.find_child(names.WESTBOUNDINGCOORDINATE)
            ebc_node = bc_node.find_child(names.EASTBOUNDINGCOORDINATE)
            nbc_node = bc_node.find_child(names.NORTHBOUNDINGCOORDINATE)
            sbc_node = bc_node.find_child(names.SOUTHBOUNDINGCOORDINATE)
            amin_node = bc_node.find_descendant(names.ALTITUDEMINIMUM)
            amax_node = bc_node.find_descendant(names.ALTITUDEMAXIMUM)
            aunits_node = bc_node.find_descendant(names.ALTITUDEUNITS)
            if wbc_node and ebc_node and nbc_node and sbc_node:
                coordinate_list = [str(wbc_node.content),
                                   str(ebc_node.content),
                                   str(nbc_node.content),
                                   str(sbc_node.content)]
                if amin_node and amax_node and aunits_node:
                    coordinate_list.extend([str(amin_node.content),
                                            str(amax_node.content),
                                            massage_altitude_units(str(aunits_node.content))])
                label = ', '.join(coordinate_list)
    return label


def compose_full_gc_label(gc_node:Node=None):
    """
    Composes a full label for a geographic coverage item. This is used when importing a geographic coverage, where
    we provide a full description of the coverage in the label, rather than the shortened version used in the
    geographic coverage table.
    """
    description = ''
    if gc_node:
        description_node = gc_node.find_child(names.GEOGRAPHICDESCRIPTION)
        if description_node and description_node.content:
            description = description_node.content
    bounding_coordinates_label = compose_gc_label(gc_node)
    return ': '.join([description, bounding_coordinates_label])


def list_temporal_coverages(parent_node:Node=None):
    """
    Returns a list of all temporal coverages under the specified parent node, as namedtuples of type TC_Entry.
    """
    tc_list = []
    if parent_node:
        # Find the coverage node, if any, as child of the given parent node.
        coverage_node = parent_node.find_child(names.COVERAGE)
        if coverage_node:
            # Find all temporal coverage nodes under the coverage node.
            tc_nodes = coverage_node.find_all_children(names.TEMPORALCOVERAGE)
            TC_Entry = collections.namedtuple(
                'TC_Entry', ["id", "begin_date", "end_date", "upval", "downval"],
                    rename=False)
            for i, tc_node in enumerate(tc_nodes):
                id = tc_node.id
                upval = get_upval(i)
                downval = get_downval(i + 1, len(tc_nodes))

                # The temporal coverage node may contain either a single date/time or a range of dates/times. Handle
                # each case separately.

                single_datetime_nodes = tc_node.find_all_children(names.SINGLEDATETIME)
                if single_datetime_nodes:
                    for sd_node in single_datetime_nodes:
                        calendar_date_node = sd_node.find_child(names.CALENDARDATE)
                        if calendar_date_node:
                            begin_date = calendar_date_node.content
                            end_date = ''
                            tc_entry = TC_Entry(id=id, begin_date=begin_date, end_date=end_date, upval=upval, downval=downval)
                            tc_list.append(tc_entry)

                range_of_dates_nodes = tc_node.find_all_children(names.RANGEOFDATES)
                if range_of_dates_nodes:
                    for rod_node in range_of_dates_nodes:
                        begin_date = ''
                        end_date = ''
                        begin_date_node = rod_node.find_child(names.BEGINDATE)
                        if begin_date_node:
                            calendar_date_node = begin_date_node.find_child(names.CALENDARDATE)
                            if calendar_date_node:
                                begin_date = calendar_date_node.content
                        end_date_node = rod_node.find_child(names.ENDDATE)
                        if end_date_node:
                            calendar_date_node = end_date_node.find_child(names.CALENDARDATE)
                            if calendar_date_node:
                                end_date = calendar_date_node.content
                        tc_entry = TC_Entry(id=id, begin_date=begin_date, end_date=end_date, upval=upval, downval=downval)
                        tc_list.append(tc_entry)
    return tc_list


def list_taxonomic_coverages(parent_node:Node=None):
    """
    Returns a list of all taxonomic coverages under the specified parent node, as namedtuples of type TXC_Entry.
    """
    txc_list = []
    if parent_node:
        # Find the coverage node, if any, as child of the given parent node.
        coverage_node = parent_node.find_child(names.COVERAGE)
        if coverage_node:
            # Find all taxonomic coverage nodes under the coverage node.
            txc_nodes = coverage_node.find_all_children(names.TAXONOMICCOVERAGE)
            TXC_Entry = collections.namedtuple(
                'TXC_Entry', ["id", "label", "upval", "downval"],
                rename=False)
            for i, txc_node in enumerate(txc_nodes):
                id = txc_node.id
                upval = get_upval(i)
                downval = get_downval(i + 1, len(txc_nodes))
                label = truncate_middle(compose_taxonomic_label(txc_node, label=''), 70, ' ... ')
                txc_entry = TXC_Entry(
                    id=id, label=label, upval=upval, downval=downval)
                txc_list.append(txc_entry)

    return txc_list


def truncate_middle(s, n, mid='...'):
    """
    Truncates a string to a maximum length, inserting a middle string to indicate that the string has been
    truncated. The middle string is optional, and defaults to '...'.

    s is the string to truncate. n is the max length allowed. mid is the middle string to insert.
    """
    if len(s) <= n:
        # string is already short-enough
        return s
    # half of the size, minus the middle
    n_2 = int(n / 2) - len(mid)
    # whatever is left
    n_1 = n - n_2 - len(mid)
    return f'{s[:n_1]}{mid}{s[-n_2:]}'


def compose_taxonomic_label(txc_node:Node=None, label:str=''):
    """
    Given a taxonomic coverage node, compose a label for the coverage. There may be a nested hierarchy of taxonomic
    classification nodes, so this function is recursive. The most specific taxonomic rank value is used as the label.
    E.g., if the taxonomic classification is "kingdom, phylum, class, order, family, genus, species", then the label
    will be the species name.
    """
    if not txc_node:
        return label
    tc_node = txc_node.find_child(names.TAXONOMICCLASSIFICATION)
    if tc_node:
        val = ''
        trv_node = tc_node.find_child(names.TAXONRANKVALUE)
        if trv_node:
            val = trv_node.content
        new_label = val
        return compose_taxonomic_label(tc_node, new_label)
    else:
        return label


def nominal_ordinal_from_attribute(att_node:Node=None):
    """
    If attribute has nominal or ordinal measurementScale, return its nominal or ordinal node. Otherwise return None.
    """
    if att_node:
        nominal_node = att_node.find_single_node_by_path([
            names.MEASUREMENTSCALE, names.NOMINAL
        ])
        if nominal_node:
            return nominal_node
        return att_node.find_single_node_by_path([
            names.MEASUREMENTSCALE, names.ORDINAL
        ])
    return None


def list_codes_and_definitions(att_node:Node=None):
    """
    Returns a list of namedtuples of type Code_Definition_Entry, each containing a code and its definition.
    """
    def compose_code_definition(code_definition_node: Node = None):
        """
        Given a code definition node, return a tuple of the code and its definition.
        """
        code = ''
        definition = ''

        if code_definition_node:
            code_node = code_definition_node.find_child(names.CODE)
            if code_node:
                code = code_node.content
            definition_node = code_definition_node.find_child(names.DEFINITION)
            if definition_node and definition_node.content:
                definition = definition_node.content
            else:
                definition = ''

        return code, definition

    codes_list = []
    # If the attribute has a nominal or ordinal measurementScale, then it may have code definitions.
    nominal_ordinal_node = nominal_ordinal_from_attribute(att_node)

    if nominal_ordinal_node:
        # Get the code definition nodes, if any.
        code_definition_nodes = nominal_ordinal_node.find_all_nodes_by_path([
            names.NONNUMERICDOMAIN,
            names.ENUMERATEDDOMAIN,
            names.CODEDEFINITION
        ])
        # Generate the Code_Definition_Entry namedtuples.
        if code_definition_nodes:
            Code_Definition_Entry = collections.namedtuple(
                            'Code_Definition_Entry',
                            ["id", "code", "definition", "upval", "downval"],
                            rename=False)

            for i, cd_node in enumerate(code_definition_nodes):
                id = cd_node.id
                code, definition = compose_code_definition(cd_node)
                upval = get_upval(i)
                downval = get_downval(i + 1, len(code_definition_nodes))
                cd_entry = Code_Definition_Entry(
                                id=id,
                                code=code,
                                definition=definition,
                                upval=upval,
                                downval=downval)
                codes_list.append(cd_entry)
        return codes_list


def list_funding_awards(eml_node:Node=None, node_id=None):
    """
    Returns a list of namedtuples of type Awards_Entry for the funding awards for a project. If node_id is provided,
    the project is a related_project pointed to by the node_id. If node_id is not provided, the project is the
    dataset's project, if any.
    """
    award_list = []
    if eml_node:
        if node_id:
            project_node = Node.get_node_instance(node_id)
        else:
            project_node = eml_node.find_single_node_by_path([
                names.DATASET, names.PROJECT
            ])
        if not project_node:
            return []
        award_nodes = project_node.find_all_children(names.AWARD)
        if award_nodes:
            for i, award_node in enumerate(award_nodes):
                Awards_Entry = collections.namedtuple(
                    "AwardEntry",
                    ["id", "funder_name", "funder_identifier", "award_number", "award_title", "award_url", "upval", "downval"],
                    rename=False)
                id = award_node.id
                funder_name = ''
                funder_identifier = ''  # FIX ME - list of ids
                award_number = ''
                award_title = ''
                award_url = ''
                funder_name_node = award_node.find_child(names.FUNDERNAME)
                if funder_name_node:
                    funder_name = funder_name_node.content
                funder_identifier_node = award_node.find_child(names.FUNDERIDENTIFIER)
                if funder_identifier_node:
                    funder_identifier = funder_identifier_node.content
                award_number_node = award_node.find_child(names.AWARDNUMBER)
                if award_number_node:
                    award_number = award_number_node.content
                award_title_node = award_node.find_child(names.TITLE)
                if award_title_node:
                    award_title = award_title_node.content
                award_url_node = award_node.find_child(names.AWARDURL)
                if award_url_node:
                    award_url = award_url_node.content
                upval = get_upval(i)
                downval = get_downval(i + 1, len(award_nodes))
                award_entry = Awards_Entry(id=id,
                                        funder_name=funder_name,
                                        funder_identifier=funder_identifier,
                                        award_number=award_number,
                                        award_title=award_title,
                                        award_url=award_url,
                                        upval=upval,
                                        downval=downval)
                award_list.append(award_entry)

    return award_list


def list_method_steps(parent_node:Node=None):
    """
    Returns a list of namedtuples of type MS_Entry for the method steps for a dataset or data entity.
    Currently, we expose only the method steps for a dataset, not for a data entity, but the code is written
    to handle either case, which is why the parent_node parameter is provided. I.e., in practice, the parent_node
    will be the dataset node.
    """

    def compose_method_step_description(method_step_node: Node = None):
        description = ''
        MAX_LEN = 80

        if method_step_node:
            description_node = method_step_node.find_child(names.DESCRIPTION)
            if description_node:
                title, text = excerpt_text(description_node)
                if title:
                    description = title
                else:
                    description = text

                if description and len(description) > MAX_LEN:
                    description = f'{description[0:MAX_LEN]}...'
        return description

    def compose_method_step_instrumentation(method_step_node: Node = None):
        instrumentation = ''
        MAX_LEN = 40

        if method_step_node:
            instrumentation_node = method_step_node.find_child(names.INSTRUMENTATION)
            if instrumentation_node:
                instrumentation = instrumentation_node.content
                if instrumentation and len(instrumentation) > MAX_LEN:
                    instrumentation = instrumentation[0:MAX_LEN]

        return instrumentation

    ms_list = []
    if parent_node:
        methods_node = parent_node.find_child(names.METHODS)
        if methods_node:
            method_step_nodes = methods_node.find_all_children(names.METHODSTEP)
            MS_Entry = collections.namedtuple(
                'MS_Entry',
                ["id", "description", "instrumentation", "upval", "downval"],
                rename=False)
            for i, method_step_node in enumerate(method_step_nodes):
                id = method_step_node.id
                method_step_description = compose_method_step_description(method_step_node)
                method_step_instrumentation = compose_method_step_instrumentation(method_step_node)
                upval = get_upval(i)
                downval = get_downval(i + 1, len(method_step_nodes))
                ms_entry = MS_Entry(id=id,
                                    description=method_step_description,
                                    instrumentation=method_step_instrumentation,
                                    upval=upval,
                                    downval=downval)
                ms_list.append(ms_entry)
    return ms_list


def list_keywords(eml_node:Node=None):
    def get_upval(kw_node):
        # If the keyword is the first one in the keyword set, return NO_OP. Otherwise, return UP_ARROW.
        upval = UP_ARROW
        if kw_node:
            keyword_set_node = kw_node.parent
            kw_nodes = keyword_set_node.find_all_children(names.KEYWORD)
            if kw_nodes:
                if kw_nodes[0] == kw_node:
                    upval = NO_OP
        return upval

    def get_downval(kw_node):
        # If the keyword is the last one in the keyword set, return NO_OP. Otherwise, return DOWN_ARROW.
        downval = DOWN_ARROW
        if kw_node:
            keyword_set_node = kw_node.parent
            kw_nodes = keyword_set_node.find_all_children(names.KEYWORD)
            if kw_nodes:
                if kw_nodes[-1] == kw_node:
                    downval = NO_OP
        return downval

    """
    Returns a list of namedtuples of type KW_Entry for the keywords for a dataset, across all keywordSets.
    """
    kw_list = []
    if eml_node:
        kw_nodes = eml_node.find_all_nodes_by_path([
            names.DATASET, names.KEYWORDSET, names.KEYWORD
        ])
        if kw_nodes:
            KW_Entry = collections.namedtuple(
                'KW_Entry',
                ["id", "keyword", "keyword_type", "upval", "downval"],
                rename=False)
            for i, kw_node in enumerate(kw_nodes):
                id = kw_node.id
                keyword = kw_node.content
                keyword_set_node = kw_node.parent
                thesaurus_node = keyword_set_node.find_child(names.KEYWORDTHESAURUS)
                thesaurus = ''
                if thesaurus_node:
                    thesaurus = thesaurus_node.content
                    if thesaurus:
                        thesaurus = ' [' + thesaurus + ']'
                kt = kw_node.attribute_value('keywordType')
                keyword_type = kt if kt else ''
                upval = get_upval(kw_node)
                downval = get_downval(kw_node)
                kw_entry = KW_Entry(id=id,
                                    keyword=keyword + thesaurus,
                                    keyword_type=keyword_type,
                                    upval=upval,
                                    downval=downval)
                kw_list.append(kw_entry)
    return kw_list


def list_access_rules(parent_node:Node=None):
    """
    Returns a list of namedtuples of type AR_Entry for the access rules for a dataset or data entity.
    Not currently used.
    """

    def get_child_content(parent_node: Node = None, child_name: str = None):
        content = ''

        if parent_node and child_name:
            child_node = parent_node.find_child(child_name)
            if child_node:
                content = child_node.content

        return content

    ar_list = []
    if parent_node:
        access_node = parent_node.find_child(names.ACCESS)
        if access_node:
            allow_nodes = access_node.find_all_children(names.ALLOW)
            AR_Entry = collections.namedtuple(
                    'AR_Entry',
                    ["id", "userid", "permission", "upval", "downval"],
                    rename=False)
            for i, allow_node in enumerate(allow_nodes):
                id = allow_node.id
                userid = get_child_content(allow_node, names.PRINCIPAL)
                permission = get_child_content(allow_node, names.PERMISSION)
                upval = get_upval(i)
                downval = get_downval(i + 1, len(allow_nodes))
                ar_entry = AR_Entry(id=id,
                                    userid=userid,
                                    permission=permission,
                                    upval=upval,
                                    downval=downval)
                ar_list.append(ar_entry)
    return ar_list


def sort_package_ids(packages):
    """ Sort a list of package IDs in the form 'scope.identifier.revision' by scope, identifier, and revision. """

    def parse_package_id(package_id: str):
        """
        Takes a package_id in the form 'scope.identifier.revision' and returns a
        triple (scope, identifier, revision) where the identifier and revision are
        ints, suitable for sorting.
        """
        *_, scope, identifier, revision = package_id.split('.')
        return scope, int(identifier), int(revision)

    return sorted(packages, key=lambda x: parse_package_id(x))
