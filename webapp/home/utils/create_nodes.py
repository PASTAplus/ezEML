"""
Helper functions to create nodes in the EML document, filling them in with provided content, adding child nodes
as needed, etc.

In some cases, the node is passed in as an argument and the caller is responsible for adding it to the model, replacing
an existing node, as needed.

In some other cases, the node is created here and added to the model, which is loaded, modified, and saved.

In other cases, the parent node is passed in and the child node is created and added to the parent node or modified
if it already exists.

Which case is used is indicated in the comments for each function.
"""

from datetime import date

from flask import flash

from webapp.config import Config

from metapype.model.node import Node
from webapp.home import exceptions as exceptions
from webapp.home.intellectual_rights import INTELLECTUAL_RIGHTS_CC0, INTELLECTUAL_RIGHTS_CC_BY

from webapp.utils import null_string
from webapp.home.home_utils import RELEASE_NUMBER, log_error, log_info
from webapp.home.metapype_client import VariableType
from webapp.home.utils.node_utils import new_child_node, remove_child, add_node, Optionality

import webapp.home.utils.load_and_save as load_and_save

from metapype.eml import names


def create_access(parent_node:Node=None):
    """
    Create an access node and add it to the parent node.
    """
    access_node = new_child_node(names.ACCESS, parent=parent_node)
    access_node.add_attribute('system', Config.SYSTEM_ATTRIBUTE_VALUE)
    access_node.add_attribute('scope', Config.SCOPE_ATTRIBUTE_VALUE)
    access_node.add_attribute('order', Config.ORDER_ATTRIBUTE_VALUE)
    access_node.add_attribute('authSystem', Config.AUTH_SYSTEM_ATTRIBUTE_VALUE)
    return access_node


def create_data_table(
    data_table_node:Node=None,
    entity_name:str=None,
    entity_description:str=None,
    object_name:str=None,
    size:str=None,
    md5_hash:str=None,
    num_header_lines:str=None,
    record_delimiter:str=None,
    quote_character:str=None,
    attribute_orientation:str=None,
    field_delimiter:str=None,
    case_sensitive:str=None,
    number_of_records:str=None,
    online_url:str=None):
    """
    Populate a data table node, filling it in with the provided values and creating child nodes as needed.
    The caller is responsible for creating the node (i.e., a node is passed in as an argument), and for adding
    the data table node to the parent node, replacing an existing data table node if necessary.
    """

    try:
        if not data_table_node:
            return

        if entity_name:
            entity_name_node = new_child_node(names.ENTITYNAME, parent=data_table_node)
            entity_name_node.content = entity_name

        if entity_description:
            entity_description_node = new_child_node(names.ENTITYDESCRIPTION, parent=data_table_node)
            entity_description_node.content = entity_description

        if object_name or size or md5_hash or num_header_lines or \
           record_delimiter or attribute_orientation or \
           field_delimiter or online_url:
            physical_node = new_child_node(names.PHYSICAL, parent=data_table_node)

        if object_name:
            object_name_node = new_child_node(names.OBJECTNAME, parent=physical_node)
            object_name_node.content = object_name

        if size:
            size_node = new_child_node(names.SIZE, parent=physical_node)
            size_node.add_attribute('unit', 'byte')
            size_node.content = str(size)

        if md5_hash:
            md5_hash_node = new_child_node(names.AUTHENTICATION, parent=physical_node)
            md5_hash_node.content = md5_hash
            md5_hash_node.add_attribute('method', 'MD5')
            md5_hash_node.content = str(md5_hash)

        if num_header_lines or record_delimiter or \
               attribute_orientation or field_delimiter:
            data_format_node = new_child_node(names.DATAFORMAT, parent=physical_node)
            text_format_node = new_child_node(names.TEXTFORMAT, parent=data_format_node)

        if num_header_lines:
            num_header_lines_node = new_child_node(names.NUMHEADERLINES, parent=text_format_node)
            num_header_lines_node.content = str(num_header_lines)

        if record_delimiter:
            record_delimiter_node = new_child_node(names.RECORDDELIMITER, parent=text_format_node)
            record_delimiter_node.content = record_delimiter

        if attribute_orientation:
            attribute_orientation_node = new_child_node(names.ATTRIBUTEORIENTATION, parent=text_format_node)
            attribute_orientation_node.content = attribute_orientation

        if quote_character or field_delimiter:
            simple_delimited_node = new_child_node(names.SIMPLEDELIMITED, parent=text_format_node)

        if quote_character:
            quote_character_node = new_child_node(names.QUOTECHARACTER, parent=simple_delimited_node)
            quote_character_node.content = quote_character

        if field_delimiter:
            field_delimiter_node = new_child_node(names.FIELDDELIMITER, parent=simple_delimited_node)
            field_delimiter_node.content = field_delimiter

        if online_url:
            distribution_node = new_child_node(names.DISTRIBUTION, parent=physical_node)
            online_node = new_child_node(names.ONLINE, parent=distribution_node)
            url_node = new_child_node(names.URL, parent=online_node)
            url_node.content = online_url

        if case_sensitive:
            case_sensitive_node = new_child_node(names.CASESENSITIVE, parent=data_table_node)
            case_sensitive_node.content = case_sensitive

        if number_of_records:
            number_of_records_node = new_child_node(names.NUMBEROFRECORDS, parent=data_table_node)
            number_of_records_node.content = str(number_of_records)

        return data_table_node

    except Exception as e:
        log_error(e)


def create_missing_values(attribute_node, code_dict):
    """
    Create missing value code nodes for the given attribute node, using the given missing value code dictionary.
    """
    if code_dict:
        for key, code_explanation in code_dict.items():
            code = key
            if code is not None:
                mvc_node = new_child_node(names.MISSINGVALUECODE, parent=attribute_node)
                code_node = new_child_node(names.CODE, parent=mvc_node)
                code_node.content = code
                if code_explanation:
                    code_explanation_node = new_child_node(names.CODEEXPLANATION, parent=mvc_node)
                    code_explanation_node.content = code_explanation


def create_datetime_attribute(
                    attribute_node:Node=None,
                    attribute_name:str=None,
                    attribute_label:str=None,
                    attribute_definition:str=None,
                    storage_type:str=None,
                    storage_type_system:str=None,
                    format_string:str=None,
                    datetime_precision:str=None,
                    bounds_minimum:str=None,
                    bounds_minimum_exclusive:str=None,
                    bounds_maximum:str=None,
                    bounds_maximum_exclusive:str=None,
                    code_dict:dict=None):
    """
    Populate a datetime attribute node, filling it in with the provided values and creating child nodes as needed.
    The caller is responsible for creating the node (i.e., a node is passed in as an argument), and for adding
    the attribute node to the parent node, replacing an existing attribute node if necessary.
    """

    if not attribute_node:
        return
    try:
        attribute_name_node = new_child_node(names.ATTRIBUTENAME, parent=attribute_node)
        attribute_name_node.content = attribute_name

        if attribute_label:
            attribute_label_node = new_child_node(names.ATTRIBUTELABEL, parent=attribute_node)
            attribute_label_node.content = attribute_label

        attribute_definition_node = new_child_node(names.ATTRIBUTEDEFINITION, parent=attribute_node)
        attribute_definition_node.content = attribute_definition

        storage_type_node = new_child_node(names.STORAGETYPE, parent=attribute_node)
        storage_type_node.content = storage_type
        if storage_type_system:
            storage_type_node.add_attribute('typeSystem', storage_type_system)

        ms_node = new_child_node(names.MEASUREMENTSCALE, parent=attribute_node)
        datetime_node = new_child_node(names.DATETIME, parent=ms_node)
        format_string_node = new_child_node(names.FORMATSTRING, parent=datetime_node)
        format_string_node.content = format_string

        if datetime_precision:
            datetime_precision_node = new_child_node(names.DATETIMEPRECISION, parent=datetime_node)
            datetime_precision_node.content = datetime_precision

        datetime_domain_node = new_child_node(names.DATETIMEDOMAIN, parent=datetime_node)
        if bounds_minimum or bounds_maximum:
            bounds_node = new_child_node(names.BOUNDS, parent=datetime_domain_node)
        if bounds_minimum:
            bounds_minimum_node = new_child_node(names.MINIMUM, parent=bounds_node)
            bounds_minimum_node.content = bounds_minimum
            if bounds_minimum_exclusive:
                bounds_minimum_node.add_attribute('exclusive', 'true')
            else:
                bounds_minimum_node.add_attribute('exclusive', 'false')
        if bounds_maximum:
            bounds_maximum_node = new_child_node(names.MAXIMUM, parent=bounds_node)
            bounds_maximum_node.content = bounds_maximum
            if bounds_maximum_exclusive:
                bounds_maximum_node.add_attribute('exclusive', 'true')
            else:
                bounds_maximum_node.add_attribute('exclusive', 'false')

        create_missing_values(attribute_node, code_dict)

    except Exception as e:
        log_error(e)


def create_numerical_attribute(
                    eml_node:Node=None,
                    attribute_node:Node=None,
                    attribute_name:str=None,
                    attribute_label:str=None,
                    attribute_definition:str=None,
                    storage_type:str=None,
                    storage_type_system:str=None,
                    standard_unit:str=None,
                    custom_unit:str=None,
                    custom_unit_description:str=None,
                    precision:str=None,
                    number_type:str=None,
                    bounds_minimum=None,
                    bounds_minimum_exclusive:str=None,
                    bounds_maximum=None,
                    bounds_maximum_exclusive:str=None,
                    code_dict:dict=None,
                    mscale:str=None):
    """
    Populate a numerical attribute node, filling it in with the provided values and creating child nodes as needed.
    The caller is responsible for creating the node (i.e., a node is passed in as an argument), and for adding
    the attribute node to the parent node, replacing an existing attribute node if necessary.
    """

    def is_non_empty_bounds(bounds=None):
        if bounds:
            return bounds
        elif type(bounds) is str:
            return bounds in ["0.0", "0"]
        elif type(bounds) is float:
            return bounds == 0.0
        elif type(bounds) is int:
            return bounds == 0

    if not attribute_node:
        return
    try:
        add_node(attribute_node, names.ATTRIBUTENAME, attribute_name, Optionality.REQUIRED)
        add_node(attribute_node, names.ATTRIBUTELABEL, attribute_label, Optionality.OPTIONAL)
        add_node(attribute_node, names.ATTRIBUTEDEFINITION, attribute_definition, Optionality.REQUIRED)

        storage_type_node = add_node(attribute_node, names.STORAGETYPE, storage_type, Optionality.OPTIONAL)
        if storage_type_system:
            storage_type_node.add_attribute('typeSystem', storage_type_system)

        mscale_node = new_child_node(names.MEASUREMENTSCALE, attribute_node)
        ratio_node = new_child_node(names.RATIO, mscale_node)
        unit_node = new_child_node(names.UNIT, ratio_node)

        if custom_unit:
            custom_unit_node = new_child_node(names.CUSTOMUNIT, parent=unit_node)
            custom_unit_node.content = custom_unit
            # need additional nodes under additionalMetadata
            load_and_save.handle_custom_unit_additional_metadata(eml_node, custom_unit, custom_unit_description)
        elif standard_unit:
            standard_unit_node = new_child_node(names.STANDARDUNIT, parent=unit_node)
            standard_unit_node.content = standard_unit

        if precision:
            precision_node = new_child_node(names.PRECISION, parent=ratio_node)
            precision_node.content = precision

        numeric_domain_node = new_child_node(names.NUMERICDOMAIN, parent=ratio_node)
        number_type_node = new_child_node(names.NUMBERTYPE, parent=numeric_domain_node)
        number_type_node.content = number_type

        if is_non_empty_bounds(bounds_minimum) or is_non_empty_bounds(bounds_maximum):
            bounds_node = new_child_node(names.BOUNDS, parent=numeric_domain_node)

        if is_non_empty_bounds(bounds_minimum):
            bounds_minimum_node = new_child_node(names.MINIMUM, parent=bounds_node)
            bounds_minimum_node.content = bounds_minimum
            if bounds_minimum_exclusive:
                bounds_minimum_node.add_attribute('exclusive', 'true')
            else:
                bounds_minimum_node.add_attribute('exclusive', 'false')

        if is_non_empty_bounds(bounds_maximum):
            bounds_maximum_node = new_child_node(names.MAXIMUM, parent=bounds_node)
            bounds_maximum_node.content = bounds_maximum
            if bounds_maximum_exclusive:
                bounds_maximum_node.add_attribute('exclusive', 'true')
            else:
                bounds_maximum_node.add_attribute('exclusive', 'false')

        create_missing_values(attribute_node, code_dict)

    except Exception as e:
        log_error(e)


def create_categorical_or_text_attribute(
                    attribute_node:Node=None,
                    attribute_name:str=None,
                    attribute_label:str=None,
                    attribute_definition:str=None,
                    storage_type:str=None,
                    storage_type_system:str=None,
                    enforced:str=None,
                    code_dict:dict=None,
                    mscale:str=None,
                    enumerated_domain_node:Node=None):
    """
    Populate a categorical or text attribute node, filling it in with the provided values and creating child nodes as
    needed. The caller is responsible for creating the node (i.e., a node is passed in as an argument), and for adding
    the attribute node to the parent node, replacing an existing attribute node if necessary.

    Categorical and text attributes are both nonNumericDomain attributes, so they share much of the same structure.
    """

    if not attribute_node:
        return
    try:
        attribute_name_node = new_child_node(names.ATTRIBUTENAME, parent=attribute_node)
        attribute_name_node.content = attribute_name

        if attribute_label:
            attribute_label_node = new_child_node(names.ATTRIBUTELABEL, parent=attribute_node)
            attribute_label_node.content = attribute_label

        attribute_definition_node = new_child_node(names.ATTRIBUTEDEFINITION, parent=attribute_node)
        attribute_definition_node.content = attribute_definition

        storage_type_node = new_child_node(names.STORAGETYPE, parent=attribute_node)
        storage_type_node.content = storage_type
        if storage_type_system:
            storage_type_node.add_attribute('typeSystem', storage_type_system)

        mscale_node = new_child_node(names.MEASUREMENTSCALE, parent=attribute_node)

        nominal_node = new_child_node(names.NOMINAL, parent=mscale_node)
        non_numeric_domain_node = new_child_node(names.NONNUMERICDOMAIN, parent=nominal_node)

        if mscale == VariableType.CATEGORICAL.name:

            # get rid of textDomain node, if any
            text_domain_node = attribute_node.find_child(names.TEXTDOMAIN)
            if text_domain_node:
                attribute_node.remove_child(text_domain_node)

            if enumerated_domain_node:
                non_numeric_domain_node.add_child(enumerated_domain_node)
            else:
                enumerated_domain_node = new_child_node(names.ENUMERATEDDOMAIN, parent=non_numeric_domain_node)
            if enforced:
                enumerated_domain_node.add_attribute('enforced', enforced)

        elif mscale == VariableType.TEXT.name:

            text_domain_node = new_child_node(names.TEXTDOMAIN, parent=non_numeric_domain_node)
            definition_node = new_child_node(names.DEFINITION, parent=text_domain_node)
            definition_node.content = "text"

            # get rid of enumeratedDomain node, if any
            enumerated_domain_node = non_numeric_domain_node.find_child(names.ENUMERATEDDOMAIN)
            if enumerated_domain_node:
                non_numeric_domain_node.remove_child(enumerated_domain_node)

        create_missing_values(attribute_node, code_dict)

    except Exception as e:
        log_error(e)


def create_code_definition(code_definition_node:Node=None,
                           code:str='',
                           definition:str='',
                           order:str=''):
    """
    Populate a codeDefinition node, filling it in with the provided values and creating child nodes as needed.
    """
    if code_definition_node:
        code_node = new_child_node(names.CODE, parent=code_definition_node)
        code_node.content = code
        definition_node = new_child_node(names.DEFINITION, parent=code_definition_node)
        definition_node.content = definition
        if order:
            code_definition_node.add_attribute('order', order)


def create_title(title=None, filename=None):
    """
    Create a title node in the EML document, filling it in with the provided value.
    The EML document is loaded, the title node is created and added to it -- or modified if one already exists -- and
    the document is saved.
    """
    from webapp.home.utils.load_and_save import load_eml
    eml_node = load_eml(filename=filename)
    title_node = None

    dataset_node = eml_node.find_child('dataset')
    if dataset_node:
        title_node = dataset_node.find_child('title')
        if not title_node:
            title_node = new_child_node(names.TITLE, parent=dataset_node)
    else:
        dataset_node = new_child_node(names.DATASET, parent=eml_node)
        title_node = new_child_node(names.TITLE, parent=dataset_node)

    title_node.content = title

    try:
        load_and_save.save_both_formats(filename=filename, eml_node=eml_node)
    except Exception as e:
        log_error(e)

    return title_node


def create_data_package_id(data_package_id=None, filename=None):
    """
    Save the data package ID as an attribute of the EML node.
    """
    from webapp.home.utils.load_and_save import load_eml
    eml_node = load_eml(filename=filename)
    if data_package_id:
        eml_node.add_attribute('packageId', data_package_id)
    else:
        eml_node.remove_attribute('packageId')

    try:
        load_and_save.save_both_formats(filename=filename, eml_node=eml_node)
    except Exception as e:
        log_error(e)


def create_pubinfo(pubplace=None, pubdate=None, filename=None):
    """
    Create pubPlace and pubData nodes in the EML document, filling them in with the provided values.
    The EML document is loaded, the nodes are created and added to it -- or modified if they already exist -- and
    the document is saved.
    The nodes are returned.
    """
    from webapp.home.utils.load_and_save import load_eml
    eml_node = load_eml(filename=filename)

    dataset_node = eml_node.find_child(names.DATASET)
    if dataset_node:
        pubplace_node = dataset_node.find_child(names.PUBPLACE)
        if not pubplace_node:
            pubplace_node = new_child_node(names.PUBPLACE, parent=dataset_node)
        pubdate_node = dataset_node.find_child(names.PUBDATE)
        if not pubdate_node:
            pubdate_node = new_child_node(names.PUBDATE, parent=dataset_node)

    else:
        dataset_node = new_child_node(names.DATASET, parent=eml_node)
        pubplace_node = new_child_node(names.PUBPLACE, parent=dataset_node)
        pubdate_node = new_child_node(names.PUBDATE, parent=dataset_node)

    # We've got the nodes, now fill in their content.
    if pubplace:
        pubplace_node.content = pubplace
    else:
        dataset_node.remove_child(pubplace_node)
    if pubdate:
        pubdate_node.content = pubdate
    else:
        dataset_node.remove_child(pubdate_node)

    try:
        load_and_save.save_both_formats(filename=filename, eml_node=eml_node)
    except Exception as e:
        log_error(e)

    return pubplace_node, pubdate_node


def create_other_entity(
    entity_node:Node=None,
    entity_name:str=None,
    entity_type:str=None,
    entity_description:str=None,
    object_name:str=None,
    format_name:str=None,
    size:str=None,
    md5_hash:str=None,
    online_url:str=None):
    """
    Populate an otherEntity node, filling it in with the provided values and creating child nodes as needed.
    The caller is responsible for creating the node (i.e., a node is passed in as an argument), and for adding
    the otherEntity node to the parent node, replacing an existing otherEntity node if necessary.
    """

    try:
        if not entity_node:
            entity_node = Node(names.OTHERENTITY)

        if entity_name:
            entity_name_node = new_child_node(names.ENTITYNAME, parent=entity_node)
            entity_name_node.content = entity_name

        if entity_type:
            entity_type_node = new_child_node(names.ENTITYTYPE, parent=entity_node)
            entity_type_node.content = entity_type

        if entity_description:
            entity_description_node = new_child_node(names.ENTITYDESCRIPTION, parent=entity_node)
            entity_description_node.content = entity_description

        if object_name or format_name or online_url:

            physical_node = new_child_node(names.PHYSICAL, parent=entity_node)

            if object_name:
                object_name_node = new_child_node(names.OBJECTNAME, parent=physical_node)
                object_name_node.content = object_name

            if format_name:
                data_format_node = new_child_node(names.DATAFORMAT, parent=physical_node)
                externally_defined_format_node = new_child_node(names.EXTERNALLYDEFINEDFORMAT, parent=data_format_node)
                format_name_node = new_child_node(names.FORMATNAME, parent=externally_defined_format_node)
                format_name_node.content = format_name

            if size:
                size_node = new_child_node(names.SIZE, parent=physical_node)
                size_node.add_attribute('unit', 'byte')
                size_node.content = size

            if md5_hash:
                hash_node = new_child_node(names.AUTHENTICATION, parent=physical_node)
                hash_node.add_attribute('method', 'MD5')
                hash_node.content = str(md5_hash)

        if online_url:
            distribution_node = new_child_node(names.DISTRIBUTION, parent=physical_node)
            online_node = new_child_node(names.ONLINE, parent=distribution_node)
            url_node = new_child_node(names.URL, parent=online_node)
            url_node.content = online_url

        return entity_node

    except Exception as e:
        log_error(e)


def create_abstract(filename:str=None, abstract:str=None):
    """
    Create an abstract node in the EML document, filling it in with the provided value.
    The EML document is loaded, the abstract node is created and added to it -- or modified if one already exists -- and
    the document is saved.
    """
    from webapp.home.utils.load_and_save import load_eml
    import webapp.home.texttype_node_processing as texttype_node_processing

    eml_node = load_eml(filename=filename)

    dataset_node = eml_node.find_child(names.DATASET)
    if dataset_node:
        abstract_node = dataset_node.find_child(names.ABSTRACT)
        if not abstract_node:
            abstract_node = new_child_node(names.ABSTRACT, parent=dataset_node)
    else:
        dataset_node = new_child_node(names.DATASET, parent=eml_node)
        abstract_node = new_child_node(names.ABSTRACT, parent=dataset_node)

    # We've got the node, now fill in its content.
    displayed_text = abstract
    # The abstract node is one that supports TextType content, so we need to check its validity and post-process it
    #  to handle para tags properly, etc.
    valid, msg = texttype_node_processing.is_valid_xml_fragment(abstract, names.ABSTRACT)
    if valid:
        try:
            texttype_node_processing.post_process_texttype_node(abstract_node, displayed_text)
            try:
                load_and_save.save_both_formats(filename=filename, eml_node=eml_node)
            except Exception as e:
                log_error(e)
        except exceptions.InvalidXMLError as e:
            log_error(e)
            flash(texttype_node_processing.invalid_xml_error_message(str(e)), 'error')
            return
    else:
        flash(texttype_node_processing.invalid_xml_error_message(msg), 'error')


def create_intellectual_rights(filename:str=None, intellectual_rights:str=None):
    """
    Create an intellectualRights node in the EML document, filling it in with the provided value.
    The EML document is loaded, the intellectualRights node is created and added to it -- or modified if one already
    exists -- and the document is saved.
    """
    from webapp.home.utils.load_and_save import load_eml
    import webapp.home.texttype_node_processing as texttype_node_processing

    eml_node = load_eml(filename=filename)

    dataset_node = eml_node.find_child(names.DATASET)
    if dataset_node:
        intellectual_rights_node = dataset_node.find_child(names.INTELLECTUALRIGHTS)
        if not intellectual_rights_node:
            intellectual_rights_node = new_child_node(names.INTELLECTUALRIGHTS, parent=dataset_node)
    else:
        dataset_node = new_child_node(names.DATASET, parent=eml_node)
        intellectual_rights_node = new_child_node(names.INTELLECTUALRIGHTS, parent=dataset_node)

    # We've got the node, now fill in its content.
    displayed_text = intellectual_rights
    # The intellectualRights node is one that supports TextType content, so we need to check its validity and
    # post-process it to handle para tags properly, etc.
    intellectual_rights_node.children = []
    valid, msg = texttype_node_processing.is_valid_xml_fragment(intellectual_rights, names.INTELLECTUALRIGHTS)
    if valid:
        try:
            texttype_node_processing.post_process_texttype_node(intellectual_rights_node, displayed_text)
        except exceptions.InvalidXMLError as e:
            log_error(e)
            flash(texttype_node_processing.invalid_xml_error_message(str(e)), 'error')
            return
    else:
        flash(texttype_node_processing.invalid_xml_error_message(msg), 'error')
    try:
        load_and_save.save_both_formats(filename=filename, eml_node=eml_node)
    except Exception as e:
        log_error(e)


def create_maintenance(dataset_node:Node=None, description:str=None, update_frequency:str=None):
    """
    Create a maintenance node in the EML document, filling it in with the provided values. Or, if the node already
    exists, update its values.
    """
    import webapp.home.texttype_node_processing as texttype_node_processing

    try:
        if dataset_node:
            if not description and not update_frequency:
                # Remove the maintenance node if it exists and no values are provided
                maintenance_node = dataset_node.find_child(names.MAINTENANCE)
                if maintenance_node:
                    dataset_node.children.remove(maintenance_node)
                    return

            # add_node either creates a new node or returns an existing one, so we don't need to check for existence
            #  or remove the old one.
            maintenance_node = add_node(dataset_node, names.MAINTENANCE)
            description_node = add_node(maintenance_node, names.DESCRIPTION)
            texttype_node_processing.post_process_texttype_node(description_node, description)

            if update_frequency:
                update_frequency_node = add_node(maintenance_node, names.MAINTENANCEUPDATEFREQUENCY, update_frequency)

    except Exception as e:
        log_error(e)


def create_project(dataset_node:Node=None, title:str=None, abstract:str=None, funding:str=None):
    """
    Create a project node in the EML document, filling it in with the provided values. Or, if the node already
    exists, update its values.
    The parent node is the dataset node, which is assumed to have already been created and is passed in as an argument.
    """
    import webapp.home.texttype_node_processing as texttype_node_processing

    try:
        project_node = dataset_node.find_child(names.PROJECT)
        if not project_node:
            project_node = new_child_node(names.PROJECT, parent=dataset_node)

        title_node = project_node.find_child(names.TITLE)
        if not title_node:
            title_node = new_child_node(names.TITLE, parent=project_node)
        title_node.content = title

        abstract_node = project_node.find_child(names.ABSTRACT)
        if not abstract_node:
            abstract_node = new_child_node(names.ABSTRACT, parent=project_node)
        if abstract:
            texttype_node_processing.post_process_texttype_node(abstract_node, abstract)
        else:
            project_node.remove_child(abstract_node)

        funding_node = project_node.find_child(names.FUNDING)
        if not funding_node:
            funding_node = new_child_node(names.FUNDING, parent=project_node)
        if funding:
            texttype_node_processing.post_process_texttype_node(funding_node, funding)
        else:
            project_node.remove_child(funding_node)

        # If project node is now empty, remove it.
        if not project_node.children:
            dataset_node.remove_child(project_node)

    except Exception as e:
        log_error(e)


def create_related_project(dataset_node:Node=None,
                           title:str=None,
                           abstract:str=None,
                           funding:str=None,
                           related_project_node_id:str=None):
    """
    Create a related project node in the EML document, filling it in with the provided values. Or, if the node already
    exists, update its values.
    If the related_project_node_id == '1', we're creating a new related project node. Otherwise, we're updating an
     existing one, identified by the related_project_node_id.
    The dataset node is assumed to have already been created and is passed in as an argument.
    """
    import webapp.home.texttype_node_processing as texttype_node_processing

    try:
        if related_project_node_id != '1':
            related_project_node = Node.get_node_instance(related_project_node_id)
        else:
            project_node = dataset_node.find_child(names.PROJECT)
            if not project_node:
                project_node = new_child_node(names.PROJECT, parent=dataset_node)
            related_project_node = new_child_node(names.RELATED_PROJECT, parent=project_node)

        # Create or update the child nodes: title, abstract, funding

        title_node = related_project_node.find_child(names.TITLE)
        if not title_node:
            title_node = new_child_node(names.TITLE, parent=related_project_node)
        title_node.content = title

        abstract_node = related_project_node.find_child(names.ABSTRACT)
        if not abstract_node:
            abstract_node = new_child_node(names.ABSTRACT, parent=related_project_node)
        if abstract:
            texttype_node_processing.post_process_texttype_node(abstract_node, abstract)
        else:
            related_project_node.remove_child(abstract_node)

        funding_node = related_project_node.find_child(names.FUNDING)
        if not funding_node:
            funding_node = new_child_node(names.FUNDING, parent=related_project_node)
        if funding:
            texttype_node_processing.post_process_texttype_node(funding_node, funding)
        else:
            related_project_node.remove_child(funding_node)

        return related_project_node

    except Exception as e:
        log_error(e)


def create_funding_award(
        award_node:Node=None,
        funder_name:str=None,
        award_title:str=None,
        funder_identifier:str=None,
        award_number:str=None,
        award_url:str=None):
    """
    Populate a funding award node with the provided values, creating child nodes as needed.
    The award node is assumed to have already been created and is passed in as an argument.
    """
    try:
        funder_name_node = new_child_node(names.FUNDERNAME, parent=award_node)
        funder_name_node.content = funder_name

        if funder_identifier:
            ids = funder_identifier.split(',')
            for id in ids:
                funder_identifier_node = new_child_node(names.FUNDERIDENTIFIER, parent=award_node)
                funder_identifier_node.content = id

        if award_number:
            award_number_node = new_child_node(names.AWARDNUMBER, parent=award_node)
            award_number_node.content = award_number

        award_title_node = new_child_node(names.TITLE, parent=award_node)
        award_title_node.content = award_title

        if award_url:
            award_url_node = new_child_node(names.AWARDURL, parent=award_node)
            award_url_node.content = award_url

    except Exception as e:
        log_error(e)


def create_geographic_coverage(
        geographic_coverage_node:Node=None,
        geographic_description:str=None,
        wbc:str=None,
        ebc:str=None,
        nbc:str=None,
        sbc:str=None,
        amin:str=None,
        amax:str=None,
        aunits:str=None
    ):
    """
    Populate a geographicCoverage node, filling it in with the provided values and creating child nodes as needed.
    The caller is responsible for creating the node (i.e., a node is passed in as an argument), and for adding
    the created geographicCoverage node to the parent node, replacing an existing geographicCoverage node if necessary.
    """

    def is_float(val):
        try:
            float(val)
            return True
        except Exception as e:
            return False

    try:
        geographic_description_node = new_child_node(names.GEOGRAPHICDESCRIPTION, parent=geographic_coverage_node)
        geographic_description_node.content = geographic_description

        bounding_coordinates_node = new_child_node(names.BOUNDINGCOORDINATES, parent=geographic_coverage_node)

        wbc_node = new_child_node(names.WESTBOUNDINGCOORDINATE, parent=bounding_coordinates_node)
        wbc_node.content = wbc

        ebc_node = new_child_node(names.EASTBOUNDINGCOORDINATE, parent=bounding_coordinates_node)
        ebc_node.content = ebc

        nbc_node = new_child_node(names.NORTHBOUNDINGCOORDINATE, parent=bounding_coordinates_node)
        nbc_node.content = nbc

        sbc_node = new_child_node(names.SOUTHBOUNDINGCOORDINATE, parent=bounding_coordinates_node)
        sbc_node.content = sbc

        if is_float(amin) or is_float(amax) or aunits:
            bounding_altitudes_node = new_child_node(names.BOUNDINGALTITUDES, parent=bounding_coordinates_node)

        if is_float(amin):
            amin_node = new_child_node(names.ALTITUDEMINIMUM, parent=bounding_altitudes_node)
            amin_node.content = amin

        if is_float(amax):
            amax_node = new_child_node(names.ALTITUDEMAXIMUM, parent=bounding_altitudes_node)
            amax_node.content = amax

        if aunits:
            aunits_node = new_child_node(names.ALTITUDEUNITS, parent=bounding_altitudes_node)
            aunits_node.content = aunits

        return geographic_coverage_node

    except Exception as e:
        log_error(e)


def create_temporal_coverage(
                   temporal_coverage_node:Node=None,
                   begin_date:str=None,
                   end_date:str=None):
    """
    Populate a temporalCoverage node, filling it in with the provided values and creating child nodes as needed.
    The caller is responsible for creating the node (i.e., a node is passed in as an argument), and for adding
    the created temporalCoverage node to the parent node, replacing an existing temporalCoverage node if necessary.
    """

    try:
        if begin_date and end_date:
            range_of_dates_node = new_child_node(names.RANGEOFDATES, parent=temporal_coverage_node)

            begin_date_node = new_child_node(names.BEGINDATE, parent=range_of_dates_node)
            begin_calendar_date_node = new_child_node(names.CALENDARDATE, parent=begin_date_node)
            begin_calendar_date_node.content = begin_date

            end_date_node = new_child_node(names.ENDDATE, parent=range_of_dates_node)
            end_calendar_date_node = new_child_node(names.CALENDARDATE, parent=end_date_node)
            end_calendar_date_node.content = end_date

        elif begin_date:
            single_datetime_node = new_child_node(names.SINGLEDATETIME, parent=temporal_coverage_node)
            calendar_date_node = new_child_node(names.CALENDARDATE, parent=single_datetime_node)
            calendar_date_node.content = begin_date

        return temporal_coverage_node

    except Exception as e:
        log_error(e)


def create_taxonomic_coverage(
                taxonomic_coverage_node:Node,
                general_taxonomic_coverage:str,
                hierarchy,
                global_authority):
    """
    Populate a taxonomicCoverage node, filling it in with the provided values and creating child nodes as needed.
    The caller is responsible for creating the node (i.e., a node is passed in as an argument), and for adding
    the created taxonomicCoverage node to the parent node, replacing an existing taxonomicCoverage node if necessary.
    """

    try:
        if taxonomic_coverage_node:
            if general_taxonomic_coverage:
                general_taxonomic_coverage_node = new_child_node(names.GENERALTAXONOMICCOVERAGE,
                                                                 parent=taxonomic_coverage_node)
                general_taxonomic_coverage_node.content = general_taxonomic_coverage

            taxonomic_classification_parent_node = taxonomic_coverage_node
            for entry in hierarchy[::-1]:
                if len(entry) == 4:
                    taxon_rank, taxon_name, common_name, taxon_id = entry
                if len(entry) == 6:
                    taxon_rank, taxon_name, common_name, taxon_id, _, authority = entry
                taxonomic_classification_node = new_child_node(names.TAXONOMICCLASSIFICATION, parent=taxonomic_classification_parent_node)
                taxon_rank_name_node = new_child_node(names.TAXONRANKNAME, parent=taxonomic_classification_node)
                taxon_rank_name_node.content = taxon_rank
                taxon_rank_value_node = new_child_node(names.TAXONRANKVALUE, parent=taxonomic_classification_node)
                taxon_rank_value_node.content = taxon_name.strip()
                if common_name:
                    common_name_node = new_child_node(names.COMMONNAME, parent=taxonomic_classification_node)
                    common_name_node.content = common_name
                if not authority:
                    authority = global_authority
                if taxon_id and authority:
                    taxon_id_node = new_child_node(names.TAXONID, parent=taxonomic_classification_node)
                    taxon_id_node.content = taxon_id
                    if authority == 'EOL':
                        provider_uri = "https://eol.org"
                    elif authority == 'ITIS':
                        provider_uri = "https://www.itis.gov"
                    elif authority == 'NCBI':
                        provider_uri = "https://www.ncbi.nlm.nih.gov/taxonomy"
                    elif authority == "PLANTS":
                        provider_uri = "https://plants.usda.gov"
                    elif authority == 'WORMS':
                        provider_uri = "http://www.marinespecies.org"
                    taxon_id_node.add_attribute(names.PROVIDER, provider_uri)
                taxonomic_classification_parent_node = taxonomic_classification_node

        return taxonomic_coverage_node

    except Exception as e:
        log_error(e)


def create_responsible_party(responsible_party_node:Node=None,
                             filename:str=None,
                             salutation:str=None,
                             gn:str=None,
                             mn:str=None,
                             sn:str=None,
                             user_id:str=None,
                             organization:str=None,
                             org_id:str=None,
                             org_id_type:str=None,
                             position_name:str=None,
                             address_1:str=None,
                             address_2:str=None,
                             city:str=None,
                             state:str=None,
                             postal_code:str=None,
                             country:str=None,
                             phone:str=None,
                             fax:str=None,
                             email:str=None,
                             online_url:str=None,
                             role:str=None):
    """
    Populate a responsibleParty node, filling it in with the provided values and creating child nodes as needed.
    The caller is responsible for creating the node (i.e., a node is passed in as an argument), and for adding
    the created responsibleParty node to the parent node, replacing an existing responsibleParty node if necessary.

    If a responsibleParty node already exists, the caller should still create a new one and pass it in as an argument,
    and upon return, the caller should replace the existing responsibleParty node with the new one. The reason for doing
    it this way is that the responsibleParty node is a complex node with many child nodes, and it is easier to create a
    new one from scratch than to try to modify an existing one. The responsibleParty node has a number of child nodes
    that have cardinality 0..infinity, which makes it a lot more complicated to find and modify the appropriate children
    to modify.
    """
    try:
        if salutation or gn or mn or sn:
            individual_name_node = new_child_node(names.INDIVIDUALNAME, parent=responsible_party_node)
        if salutation:
            salutation_node = new_child_node(names.SALUTATION, parent=individual_name_node)
            salutation_node.content = salutation
        if gn:
            given_name_node = new_child_node(names.GIVENNAME, parent=individual_name_node)
            given_name_node.content = gn
        if mn:
            given_name_node = new_child_node(names.GIVENNAME, parent=individual_name_node)
            given_name_node.content = mn
        if sn:
            surname_node = new_child_node(names.SURNAME, parent=individual_name_node)
            surname_node.content = sn

        if user_id:
            user_id_node = new_child_node(names.USERID, parent=responsible_party_node)
            user_id_node.content = user_id
            user_id_node.add_attribute('directory', 'https://orcid.org')

        if organization:
            organization_name_node = new_child_node(names.ORGANIZATIONNAME, parent=responsible_party_node)
            organization_name_node.content = organization

        if org_id:
            user_id_node = new_child_node(names.USERID, parent=responsible_party_node)
            user_id_node.content = org_id
            if org_id_type:
                user_id_node.add_attribute('directory', org_id_type)

        if position_name:
            position_name_node = new_child_node(names.POSITIONNAME, parent=responsible_party_node)
            position_name_node.content = position_name

        if address_1 or address_2 or city or state or postal_code or country:
            address_node = new_child_node(names.ADDRESS, parent=responsible_party_node)

        if address_1:
            delivery_point_node_1 = new_child_node(names.DELIVERYPOINT, parent=address_node)
            delivery_point_node_1.content = address_1

        if address_2:
            delivery_point_node_2 = new_child_node(names.DELIVERYPOINT, parent=address_node)
            delivery_point_node_2.content = address_2

        if city:
            city_node = new_child_node(names.CITY, parent=address_node)
            city_node.content = city

        if state:
            administrative_area_node = new_child_node(names.ADMINISTRATIVEAREA, parent=address_node)
            administrative_area_node.content = state

        if postal_code:
            postal_code_node = new_child_node(names.POSTALCODE, parent=address_node)
            postal_code_node.content = postal_code

        if country:
            country_node = new_child_node(names.COUNTRY, parent=address_node)
            country_node.content = country

        if phone:
            phone_node = new_child_node(names.PHONE, parent=responsible_party_node)
            phone_node.content = phone
            phone_node.add_attribute('phonetype', 'voice')

        if fax:
            fax_node = new_child_node(names.PHONE, parent=responsible_party_node)
            fax_node.content = fax
            fax_node.add_attribute('phonetype', 'facsimile')

        if email:
            email_node = new_child_node(names.ELECTRONICMAILADDRESS, parent=responsible_party_node)
            email_node.content = email

        if online_url:
            online_url_node = new_child_node(names.ONLINEURL, parent=responsible_party_node)
            online_url_node.content = online_url

        if role:
            role_node = new_child_node(names.ROLE, parent=responsible_party_node)
            role_node.content = role

        return responsible_party_node

    except Exception as e:
        log_error(e)


def create_method_step(method_step_node:Node=None, description:str=None, instrumentation:str=None, data_sources:str=None,
                       data_sources_marker_begin:str='', data_sources_marker_end:str=''):
    """
    Populate a methodStep node, filling it in with the provided values and creating child nodes as needed.
    The caller is responsible for creating the node (i.e., a node is passed in as an argument), and for adding
    the created methodStep node to the parent node, replacing an existing methodStep node if necessary.
    """
    import webapp.home.texttype_node_processing as texttype_node_processing

    if method_step_node:
        description_node = method_step_node.find_child(names.DESCRIPTION)
        if not description_node:
            description_node = new_child_node(names.DESCRIPTION, parent=method_step_node)

        if data_sources:
            if not description:
                description = ''  # TODO: Handle cases with empty description but non-empty data_sources
            description = f"{description}\n{data_sources_marker_begin}\n{data_sources}\n{data_sources_marker_end}"

        texttype_node_processing.post_process_texttype_node(description_node, description)


        instrumentation_nodes = method_step_node.find_all_children(names.INSTRUMENTATION)
        if instrumentation:
            if len(instrumentation_nodes) > 1:
                # The EML standard permits multiple instrumentation nodes, but the ezEML UI does not.
                # If there are multiple instrumentation nodes, we will compromise by putting the
                # instrumentation content in a single node, separated by newlines. The other
                # instrumentation nodes will be deleted.
                content = ''
                index = 0
                for instrumentation_node in instrumentation_nodes:
                    if not null_string(instrumentation_node.content):
                        content += f"{instrumentation_node.content}\n"
                    if index > 0:
                        method_step_node.remove_child(instrumentation_node)
                    index += 1
                instrumentation = f"{content}{instrumentation}"
            instrumentation_node = method_step_node.find_child(names.INSTRUMENTATION)
            if not instrumentation_node:
                instrumentation_node = new_child_node(names.INSTRUMENTATION, parent=method_step_node)

            instrumentation_node.content = instrumentation
        else:
            for instrumentation_node in instrumentation_nodes:
                method_step_node.remove_child(instrumentation_node)


def create_data_source(data_source_node:Node=None, title:str=None, online_description:str=None, online_url:str=None):
    """
    Populate a dataSource node, filling it in with the provided values and creating child nodes as needed.
    The caller is responsible for creating the node (i.e., a node is passed in as an argument), and for adding
    the created dataSource node to the parent node, replacing an existing dataSource node if necessary.
    """

    if data_source_node:
        if title is None:
            title = ''
        title_node = data_source_node.find_child(names.TITLE)
        if not title_node:
            title_node = new_child_node(names.TITLE, parent=data_source_node)
        title_node.content = title

        if online_description is None:
            online_description = ''
        if online_url is None:
            online_url = ''

        distribution_node = data_source_node.find_child(names.DISTRIBUTION)
        if not distribution_node:
            distribution_node = new_child_node(names.DISTRIBUTION, parent=data_source_node)

        # We do not support the full EML schema here. The schema allows offline and inline elements, but ezEML
        #  only supports online. In addition, the schema allows connection and connectionDefinition elements as
        #  children of the online element, but ezEML supports only the url element.
        online_node = distribution_node.find_child(names.ONLINE)
        if not online_node:
            online_node = new_child_node(names.ONLINE, parent=distribution_node)

        online_description_node = online_node.find_child(names.ONLINEDESCRIPTION)
        if online_description:
            if not online_description_node:
                online_description_node = new_child_node(names.ONLINEDESCRIPTION, parent=online_node)
            online_description_node.content = online_description
        else:
            # We don't allow an empty online description, so we will delete the node if it exists
            if online_description_node:
                online_node.remove_child(online_description_node)

        online_url_node = online_node.find_child(names.URL)
        if online_url:
            if not online_url_node:
                online_url_node = new_child_node(names.URL, parent=online_node)
            online_url_node.content = online_url
        else:
            # We don't allow an empty online URL, so we will delete the node if it exists
            if online_url_node:
                online_node.remove_child(online_url_node)

        # If online node was created and now there is no online description nor url, delete the distribution node
        # The user may have just cleared the online description and url fields.
        if len(online_node.children) == 0:
            data_source_node.remove_child(distribution_node)


def create_keyword(keyword_node:Node=None, keyword:str=None, keyword_type:str=None):
    """
    Populate a keyword node, filling it in with the provided content and attribute.
    The caller is responsible for creating the node (i.e., a node is passed in as an argument), and for adding
    the created keyword node to the parent node, replacing an existing keyword node if necessary.
    """
    if keyword_node:
        keyword_node.content = keyword
        if keyword_type:
            keyword_node.add_attribute(name='keywordType', value=keyword_type)


def create_access_rule(allow_node:Node=None, userid:str=None, permission:str=None):
    """ Not currently used. """
    if allow_node:
        if userid:
            principal_node = new_child_node(names.PRINCIPAL, parent=allow_node)
            principal_node.content = userid

        if permission:
            permission_node = new_child_node(names.PERMISSION, parent=allow_node)
            permission_node.content = permission


def add_fetched_from_edi_metadata(eml_node:Node=None, pid:str=None):
    """
    When a package is fetched from EDI, we add a fetchedFromEDI node to the additional metadata section.

    This documents what package was fetched from EDI (the packageID may be changed after the package is
    fetched from EDI) and the date it was fetched. This lets data curators know that the package was
    based on a fetched package.
    """
    fetched_from_edi_node = eml_node.find_descendant('fetchedFromEDI')
    if fetched_from_edi_node:
        metadata_node = fetched_from_edi_node.parent
        additional_metadata_node = metadata_node.parent
        eml_node.remove_child(additional_metadata_node)
    additional_metadata_node = new_child_node(names.ADDITIONALMETADATA, parent=eml_node)
    metadata_node = new_child_node(names.METADATA, parent=additional_metadata_node)
    # For the fetchedFromEDI node, we need to bypass Metapype validity checking
    fetched_from_edi_node = Node('fetchedFromEDI', parent=metadata_node)
    metadata_node.add_child(fetched_from_edi_node)
    fetched_from_edi_node.attributes.clear()
    fetched_from_edi_node.add_attribute('packageID', pid)
    fetched_from_edi_node.add_attribute('dateFetched', str(date.today()))


def get_fetched_from_edi_metadata(eml_node:Node=None):
    """
    See if the package is based on one fetched from EDI. If so, return a message to that effect.
    """
    fetched_from_edi_node = eml_node.find_descendant('fetchedFromEDI')
    msg = ''
    if fetched_from_edi_node:
        pid = fetched_from_edi_node.attribute_value('packageID')
        date = fetched_from_edi_node.attribute_value('dateFetched')
        if pid and date:
            msg = f'\n\n\nThis data package is based on package {pid} fetched from EDI on {date}.'
    return msg


def add_eml_editor_metadata(eml_node:Node=None):
    """
    When a package is created or edited in ezEML, we add an emlEditor node to the additional metadata section.
    This documents the fact that the package was created or edited in ezEML, and the version of ezEML used.
    """
    eml_editor_node = eml_node.find_descendant('emlEditor')
    if eml_editor_node:
        metadata_node = eml_editor_node.parent
        additional_metadata_node = metadata_node.parent
        eml_node.remove_child(additional_metadata_node)
    additional_metadata_node = new_child_node(names.ADDITIONALMETADATA, parent=eml_node)
    metadata_node = new_child_node(names.METADATA, parent=additional_metadata_node)
    # For the emlEditor node, we need to bypass Metapype validity checking
    eml_editor_node = Node('emlEditor', parent=metadata_node)
    metadata_node.add_child(eml_editor_node)
    eml_editor_node.attributes.clear()
    eml_editor_node.add_attribute('app', 'ezEML')
    eml_editor_node.add_attribute('release', RELEASE_NUMBER)
