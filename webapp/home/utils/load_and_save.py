"""
Helper functions for loading and saving EML documents.
"""

import json
import os
import pickle
from datetime import date
from urllib.parse import urlencode, urlparse, quote, unquote

from flask import flash, request, session
from flask_login import current_user

import webapp.home.utils.import_nodes as import_nodes
import webapp.home.utils.node_utils as node_utils
import webapp.home.utils.qudt_annotations as qudt_annotations

from webapp import Config
from webapp.auth import user_data as user_data
from webapp.home import check_data_table_contents as check_data_table_contents
from webapp.home.home_utils import log_error, log_info, get_check_metadata_status
from webapp.home.metapype_client import VariableType
from webapp.home.utils.node_store import calculate_node_store_checksum
from webapp.home.utils.node_utils import add_node, Optionality
from webapp.utils import null_string
from webapp.views.collaborations import collaborations as collaborations

from metapype.eml import names
from metapype.model import metapype_io, mp_io
from metapype.model.node import Node
import webapp.views.data_tables.load_data as load_data

def from_json(filename):
    """
    Load an EML document from a Metapype JSON file and return the root node of the Metapype model.
    """

    def fix_nonstring_content(node):
        """ For any nodes with non-string content, convert the content to a string. """
        if node and node.content is not None:
            if not type(node.content) is str:
                node.content = str(node.content)
        if node.children:
            for child in node.children:
                fix_nonstring_content(child)

    def check_for_nonstring_content(node):
        """
        For any nodes with non-string content, raise a ValueError exception.
        Used to check for non-string content.
        """
        if node and node.content is not None:
            if not type(node.content) is str:
                raise ValueError(f"{node.name} - {type(node.content)} - {node.content}")
        if node.children:
            for child in node.children:
                check_for_nonstring_content(child)

    eml_node = None
    try:
        with open(filename, "r") as json_file:
            json_text = json_file.read()
            # The JSON may be in one of two formats
            try:
                eml_node = metapype_io.from_json(json_text)

            except KeyError as e:
                # Must be in the old format. When saved, the JSON will be written in the new format.
                try:
                    json_dict = json.loads(json_text)
                    eml_node = mp_io.from_json(json_dict)
                except KeyError as e:
                    log_error(e)

        try:
            # See if there's any non-string content in the EML that needs to be fixed.
            check_for_nonstring_content(eml_node)
        except ValueError as e:
            # There's non-string content in the EML. Fix it and save the fixed EML.
            log_error(f'Nonstring content found: {str(e)}')
            fix_nonstring_content(eml_node)
            basename, ext = os.path.splitext(os.path.basename(filename))
            save_both_formats(filename=basename, eml_node=eml_node)

    except Exception as e:
         log_error(e)
    return eml_node


def save_package_id(eml_node):
    # There are various ways of opening a new package, and we want to ensure that no matter what path we took,
    #   the package ID is updated in the current user's user_data.
    if eml_node:
        data_package_id = eml_node.attribute_value('packageId')
        if data_package_id:
            user_data.set_active_packageid(data_package_id)


def load_template(template_pathname):
    filename = os.path.basename(template_pathname)
    filename = os.path.splitext(filename)[0]
    folder_name = os.path.dirname(template_pathname)
    return load_eml(filename=filename, folder_name=folder_name, skip_metadata_check=True)


def get_pathname(filename:str=None,
                 folder_name:str=None,
                 file_extension:str=None,
                 owner_login:str=None,
                 log_the_details:bool=False):
    """
    Get the pathname of the file to load, respecting any collaboration that is in effect.
    """
    if not owner_login:
        owner_login = user_data.get_active_document_owner_login()

    if owner_login and not folder_name:
        # If we are loading a document that is owned by someone else, we need to get the document from the
        #  owner's user-data folder.
        folder_name = user_data.get_user_folder_name(owner_login=owner_login)

    if folder_name:
        # If a folder name was passed, load the file from that folder.
        user_folder = folder_name
    else:
        user_folder = None
        try:
            # Otherwise, folder_name was not passed, so load the file from the current user's folder, respecting
            #  any collaboration that is in effect.
            user_folder = user_data.get_user_folder_name(log_the_details=log_the_details)
        except Exception as e:
            log_error(f"load_eml: {e}")
    if not user_folder:
        user_folder = '.'
    pathname = f"{user_folder}/{filename}.{file_extension}"
    if log_the_details:
        log_info(f"get_pathname: pathname: {pathname}")
    return pathname


def load_eml(filename:str=None,
             folder_name=None,
             skip_metadata_check:bool=False,
             do_not_lock:bool=False,
             owner_login:str=None,
             log_the_details:bool=False):
    """
    Load an EML document from a Metapype JSON file and return the root node of the Metapype model.

    :param filename: The name of the file to load. Usually, this is the only parameter that is passed. The other
        parameters are overrides for special cases.
    :param folder_name: The name of the folder to load the file from. Used to force loading of a file from a specific
        folder. Usually, this is not passed, and the file is loaded from the current user's folder, respecting any
        collaboration that is in effect. If we're handling an Open link from the Collaborate page, however, we want to
        force loading of the file from the owner's folder, not the current user's folder.
    :param skip_metadata_check: If True, skip the metadata check. The metadata check is done to ensure that the badges
        on Check Metadata and Check Data Tables in the sidebar are up to date. If we're loading a document for the
        purpose of running Check Metadata, for example, we skip this check because it would be redundant. We also skip
        it when we're loading a document for the purpose of getting the package size for the Manage Packages page, for
        example -- i.e., when we're just looking at the document, not opening it for editing.
    :param do_not_lock: If True, do not lock the document. This is used when we are just looking at the document, not
        opening it for editing.
    :param owner_login: The login of the owner of the document. This is used when we are loading a document and we
        want to force loading of the file from the owner's folder, not the current user's folder. For example,
        when cloning data table column properties, if we're collaborating and have opened a document owned by someone
        else, we want to clone from a table in the owner's folder, not the current user's folder. It wouldn't make sense
        to clone properties from a table in the current user's folder into a table in the owner's folder.
    :param log_the_details: If True, log the details of the document that was loaded. For debugging purposes.
    :return: The root node of the Metapype model.
    """
    import webapp.home.texttype_node_processing as texttype_node_processing

    if not log_the_details and hasattr(Config, 'LOG_FILE_HANDLING_DETAILS'):
        log_the_details = Config.LOG_FILE_HANDLING_DETAILS

    # First, deal with locking (for collaboration).
    # Usually when we load an EML file, we want to acquire a lock on it. However, there are times when we are just
    #  looking at the file, not opening it for editing -- for example, when checking metadata or when getting the package
    #  size for manage packages page.
    # We don't nest this in the larger try/except because the exception signals that the document is already locked by
    #  someone else. That exception will be handled in webapp/errors/handler.py, which posts an informative message.
    #  If it is already locked by us, no exception is raised but the lock's timestamp is updated.
    lock = None
    if not do_not_lock:
        try:
            if not owner_login:
                owner_login = user_data.get_active_document_owner_login()
            lock = user_data.is_document_locked(filename, owner_login=owner_login)
        except Exception as e:
            # Log the exception and re-raise it to be handled in webapp/errors/handler.py.
            # Typically, the exception signals that the document is already locked by someone else, although there may
            #  be other cases that truly are error cases.
            log_error(f"load_eml: is_document_locked: {e}")
            raise

    try:

        ext_filename = get_pathname(filename,
                                    folder_name=folder_name,
                                    file_extension='json',
                                    owner_login=owner_login,
                                    log_the_details=log_the_details)
        if os.path.isfile(ext_filename):
            eml_node = from_json(ext_filename)
        else:
            log_error(f"load_eml: Could not find {ext_filename}")
            active_login = user_data.get_active_document_owner_login()
            log_error(f"filename: {filename}, folder_name: {folder_name}, owner_login: {owner_login}, active_login: {active_login}")
            return None

        if eml_node:
            if not skip_metadata_check:
                # Update the metadata and data table check badges in the sidebar.
                get_check_metadata_status(eml_node, filename)
                check_data_table_contents.set_check_data_tables_badge_status(filename, eml_node)
                # Set the model_has_complex_texttypes flag in user_data so we know whether to render TextType items
                #  with xml tags.
                user_data.set_model_has_complex_texttypes(texttype_node_processing.model_has_complex_texttypes(eml_node))
                if not user_data.get_udt_annotations_done():
                    qudt_annotations.add_qudt_annotations(eml_node)
                    save_both_formats(filename=filename, eml_node=eml_node)
                    user_data.set_qudt_annotations_done(True)
        else:
            log_error(f"load_eml: Could not load {ext_filename}")

        # Log some debug info, if configured to do so.
        from webapp.home.views import url_of_interest
        if Config.MEM_LOG_METAPYPE_STORE_ACTIONS and url_of_interest():
            store_len = len(Node.store)
            log_info(f'*** load_eml ***: store_len={store_len}     {request.url}')
            log_info(f'*** load_eml ***: node store checksum={calculate_node_store_checksum()}    {request.url}')

    except Exception as e:
        collaborations.release_acquired_lock(lock)
        log_error(f"load_eml: {e}")
        eml_node = None
        # raise exceptions.FileOpenError(e)

    return eml_node


def save_old_to_new(old_filename:str=None, new_filename:str=None, eml_node:Node=None):
    """
    Do "Save As", saving the current document under a new document name.
    """
    msg = None
    if new_filename and eml_node and new_filename != old_filename:
        # We save in the current user's folder, even if we're collaborating.
        save_both_formats(filename=new_filename, eml_node=eml_node.copy(), owner_login=current_user.get_user_login())
    elif new_filename == old_filename:
        msg = 'New package id and old package id are the same'
    else:
        msg = 'Not saved'

    return msg


def strip_elements_added_by_pasta(filename:str=None, eml_node:Node=None):
    """
    PASTA adds an alternateIdentifier element to the EML document to record the package's DOI, and it adds a distribution
    element at the dataset level to record the package's PASTA URL. We strip these elements when importing a document
    so that if the document is submitted to the repository as a revision we won't accumulate multiple such elements.
    """
    modified = False
    dataset_node = eml_node.find_child(names.DATASET)
    alternate_id_nodes = dataset_node.find_all_children(names.ALTERNATEIDENTIFIER)
    for alternate_id_node in alternate_id_nodes:
        if alternate_id_node and ('doi:10.6073/' in alternate_id_node.content or 'doi:10.0311/' in alternate_id_node.content):
            node_utils.remove_child(alternate_id_node)
            modified = True
    distribution_nodes = dataset_node.find_all_children(names.DISTRIBUTION)
    for distribution_node in distribution_nodes:
        online_nodes = distribution_node.find_all_children(names.ONLINE)
        for online_node in online_nodes:
            url_node = online_node.find_child(names.URL)
            if url_node and url_node.content and ('doi:10.6073/' in url_node.content or
                                                  'doi.org/10.6073/' in url_node.content or
                                                  'doi:10.0311/' in url_node.content):
                node_utils.remove_child(distribution_node)
                modified = True
    if modified:
        save_both_formats(filename=filename, eml_node=eml_node)
    return eml_node


def package_contains_elements_unhandled_by_ezeml(filename:str=None, eml_node:Node=None):
    """
    There are a number of elements in EML that are not exposed by the ezEML user interface. We preserve such elements
    in the model, but we want to warn the user if the document contains such elements.
    If the package contains element(s) unhandled by ezEML, this function returns a sorted list of the unique element
    names.

    Note: We don't want to include the alternateIdentifier and distribution elements that PASTA adds to the document,
    so we strip those elements before checking for unhandled elements.
    """
    unhandled = [
        names.ALTERNATEIDENTIFIER,
        names.SHORTNAME,
        names.LANGUAGE,
        names.SERIES,
        names.ADDITIONALINFO,
        names.LICENSED,
        names.DISTRIBUTION,
        names.ANNOTATION,
        names.PURPOSE,
        names.INTRODUCTION,
        names.GETTINGSTARTED,
        names.ACKNOWLEDGEMENTS,
        # names.REFERENCEPUBLICATION,
        # names.USAGECITATION,
        # names.LITERATURECITED,
        # names.ANNOTATIONS
    ]
    found = set()

    if eml_node:
        eml_node = strip_elements_added_by_pasta(filename, eml_node)
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            for child in dataset_node.children:
                if child.name in unhandled:
                    if child.name != names.DISTRIBUTION:
                        found.add(child.name)
                    else:
                        found.add('distribution (at dataset level)')
        # annotations_node = eml_node.find_child(names.ANNOTATIONS)
        # if annotations_node:
        #     found.add(names.ANNOTATIONS)
    return sorted(found)


def enforce_dataset_sequence(eml_node:Node=None):
    """
    The EML standard expects various nodes to be in a particular sequence. This function enforces that sequence.

    When nodes are added as the user fills out the wizard, they are added in the correct sequence. However, if the
    user jumps around between sections, the sequence can be violated. This function fixes that.
    """
    def collect_children(parent_node: Node, child_name: str, children: list):
        children.extend(parent_node.find_all_children(child_name))

    # Children of dataset node need to be in sequence. This happens "naturally" when ezEML is used as a
    #  wizard, but not when jumping around between sections
    if eml_node:
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            new_children = []
            sequence = (
                names.ALTERNATEIDENTIFIER,
                names.SHORTNAME,
                names.TITLE,
                names.CREATOR,
                names.METADATAPROVIDER,
                names.ASSOCIATEDPARTY,
                names.PUBDATE,
                names.LANGUAGE,
                names.SERIES,
                names.ABSTRACT,
                names.KEYWORDSET,
                names.ADDITIONALINFO,
                names.INTELLECTUALRIGHTS,
                names.LICENSED,
                names.DISTRIBUTION,
                names.COVERAGE,
                names.ANNOTATION,
                names.PURPOSE,
                names.INTRODUCTION,
                names.GETTINGSTARTED,
                names.ACKNOWLEDGEMENTS,
                names.MAINTENANCE,
                names.CONTACT,
                names.PUBLISHER,
                names.PUBPLACE,
                names.METHODS,
                names.PROJECT,
                names.DATATABLE,
                names.OTHERENTITY
            )
            for name in sequence:
                collect_children(dataset_node, name, new_children)
            dataset_node._children = new_children


def enforce_public_read_access(eml_node:Node=None):
    # If no access node, add it as first child of eml node
    if eml_node:
        access_node = eml_node.find_child(names.ACCESS)
        if not access_node:
            access_node = Node(names.ACCESS)
            access_node.parent = eml_node
            eml_node.add_child(access_node, 0)
            access_node.add_attribute('system', Config.SYSTEM_ATTRIBUTE_VALUE)
            access_node.add_attribute('scope', Config.SCOPE_ATTRIBUTE_VALUE)
            access_node.add_attribute('order', Config.ORDER_ATTRIBUTE_VALUE)
            access_node.add_attribute('authSystem', Config.AUTH_SYSTEM_ATTRIBUTE_VALUE)
        allow_nodes = access_node.find_all_children(names.ALLOW)
        for allow_node in allow_nodes:
            principal_node = allow_node.find_child(names.PRINCIPAL)
            permission_node = allow_node.find_child(names.PERMISSION)
            if principal_node and principal_node.content == 'public' and permission_node and permission_node.content == 'read':
                return
        public_allow_node = node_utils.new_child_node(names.ALLOW, parent=access_node)
        public_principal_node = node_utils.new_child_node(names.PRINCIPAL, parent=public_allow_node)
        public_principal_node.content = 'public'
        public_permission_node = node_utils.new_child_node(names.PERMISSION, parent=public_allow_node)
        public_permission_node.content = 'read'


def clean_model(eml_node):
    """
    Perform various cleanups on the model. This is called when a model is saved. Its purpose is to deal with
    cases where an existing model has glitches due to earlier bugs or because we've changed how we're doing things.
    """
    if not eml_node:
        return
    try:
        # There are some documents that have a spurious filename attribute, which gets propagated if the
        #  document is copied via Save As. Clean it up.
        eml_node.remove_attribute('filename')
    except:
        pass
    enforce_public_read_access(eml_node)
    # Some documents have, due to earlier bugs, empty publisher, pubPlace, or pubDate nodes
    publisher_nodes = []
    eml_node.find_all_descendants(names.PUBLISHER, publisher_nodes)
    for publisher_node in publisher_nodes:
        if len(publisher_node.children) == 0:
            node_utils.remove_child(publisher_node)
    pubplace_nodes = []
    eml_node.find_all_descendants(names.PUBPLACE, pubplace_nodes)
    for pubplace_node in pubplace_nodes:
        if not pubplace_node.content:
            node_utils.remove_child(pubplace_node)
    pubdate_nodes = []
    eml_node.find_all_descendants(names.PUBDATE, pubdate_nodes)
    for pubdate_node in pubdate_nodes:
        if not pubdate_node.content:
            node_utils.remove_child(pubdate_node)
    # Some documents have, due to earlier bugs, keywordSets that contain no keywords
    keyword_sets = []
    eml_node.find_all_descendants(names.KEYWORDSET, keyword_sets)
    for keyword_set in keyword_sets:
        keywords = keyword_set.find_all_children(names.KEYWORD)
        if len(keywords) == 0:
            node_utils.remove_child(keyword_set)
    # Some documents have, due to earlier bugs, taxonomicCoverage nodes that contain no taxonomicClassification nodes
    taxonomic_coverage_nodes = []
    eml_node.find_all_descendants(names.TAXONOMICCOVERAGE, taxonomic_coverage_nodes)
    for taxonomic_coverage_node in taxonomic_coverage_nodes:
        taxonomic_classification_nodes = taxonomic_coverage_node.find_all_children(names.TAXONOMICCLASSIFICATION)
        if len(taxonomic_classification_nodes) == 0:
            node_utils.remove_child(taxonomic_coverage_node)
    # Some documents lack the 'unit' attribute for the names.SIZE node
    size_nodes = []
    eml_node.find_all_descendants(names.SIZE, size_nodes)
    for size_node in size_nodes:
        size_node.add_attribute('unit', 'byte')
    # Some documents have codes for categorical attributes that are ints, not strings
    code_nodes = []
    eml_node.find_all_descendants(names.CODE, code_nodes)
    for code_node in code_nodes:
        code = code_node.content
        if isinstance(code, int):
            code_node.content = str(code)
    # Some documents have taxonIds that are ints, not strings
    taxonid_nodes = []
    eml_node.find_all_descendants(names.TAXONID, taxonid_nodes)
    for taxonid_node in taxonid_nodes:
        taxonid = taxonid_node.content
        if isinstance(taxonid, int):
            taxonid_node.content = str(taxonid)
    # Some documents have an empty <funding> node. Remove it.
    funding_nodes = []
    to_remove = []
    eml_node.find_all_descendants(names.FUNDING, funding_nodes)
    for funding_node in funding_nodes:
        if not funding_node.content and len(funding_node.children) == 0:
            to_remove.append(funding_node)
    for node in to_remove:
        node_utils.remove_child(node)
    # Some documents have a <distribution> node that contains only an empty <online> node. Remove it.
    distribution_nodes = []
    to_remove = []
    eml_node.find_all_descendants(names.DISTRIBUTION, distribution_nodes)
    for distribution_node in distribution_nodes:
        online_nodes = distribution_node.find_all_children(names.ONLINE)
        if len(online_nodes) == 1 and not online_nodes[0].content and len(online_nodes[0].children) == 0:
            to_remove.append(distribution_node)
    for node in to_remove:
        node_utils.remove_child(node)

    # Make sure all url elements for dataTable and otherEntity have the function="download" attribute
    data_table_nodes = []
    eml_node.find_all_descendants(names.DATATABLE, data_table_nodes)
    for data_table_node in data_table_nodes:
        url_nodes = []
        data_table_node.find_all_descendants(names.URL, url_nodes)
        for url_node in url_nodes:
            url_node.add_attribute('function', 'download')
    other_entity_nodes = []
    eml_node.find_all_descendants(names.OTHERENTITY, other_entity_nodes)
    for other_entity_node in other_entity_nodes:
        url_nodes = []
        other_entity_node.find_all_descendants(names.URL, url_nodes)
        for url_node in url_nodes:
            url_node.add_attribute('function', 'download')

    # The EML standard permits multiple instrumentation nodes, but the ezEML UI does not.
    # If there are multiple instrumentation nodes, we will compromise by putting the
    # instrumentation content in a single node, separated by newlines. The other
    # instrumentation nodes will be deleted.
    method_step_nodes = []
    eml_node.find_all_descendants(names.METHODSTEP, method_step_nodes)
    for method_step_node in method_step_nodes:
        instrumentation = ''
        instrumentation_nodes = method_step_node.find_all_children(names.INSTRUMENTATION)
        index = 0
        for instrumentation_node in instrumentation_nodes:
            if not null_string(instrumentation_node.content):
                instrumentation += f"{instrumentation_node.content}\n"
            if index > 0:
                node_utils.remove_child(instrumentation_node)
            index += 1
        if instrumentation:
            instrumentation_node = method_step_node.find_child(names.INSTRUMENTATION)
            if instrumentation_node:
                if instrumentation.endswith('\n'):
                    instrumentation = instrumentation[:-1]
                instrumentation_node.content = instrumentation

    # ezEML and EAL both had a bug that caused the attributeDefinition value to be copied into the definition node that
    #  is a child of the textDomain node. They should instead put "text" in that definition node.
    text_domain_nodes = []
    eml_node.find_all_descendants(names.TEXTDOMAIN, text_domain_nodes)
    for text_domain_node in text_domain_nodes:
        definition_node = text_domain_node.find_child(names.DEFINITION)
        if definition_node:
            definition_node.content = 'text'

    # If a project node no longer has any children, remove it.
    project_nodes = []
    eml_node.find_all_descendants(names.PROJECT, project_nodes)
    for project_node in project_nodes:
        if not project_node.children:
            project_node.parent.remove_child(project_node)

    # Fixup formatName fields to use mime types instead of file extensions.
    # If we make a change, flash a message to the user.
    other_entity_nodes = []
    changed = False
    eml_node.find_all_descendants(names.OTHERENTITY, other_entity_nodes)
    for other_entity_node in other_entity_nodes:
        format_name_node = other_entity_node.find_descendant(names.FORMATNAME)
        if format_name_node:
            object_name_node = other_entity_node.find_descendant(names.OBJECTNAME)
            if object_name_node:
                object_name = object_name_node.content
                if object_name:
                    old_content = format_name_node.content
                    new_content = load_data.format_name_from_data_file(object_name)
                    if new_content:
                        format_name_node.content = new_content
                    if old_content != format_name_node.content:
                        changed = True
    if changed:
        flash("In one or more Other Entities, the Data Format field has been modified to use mime types.")

    # Collect keywords for a given thesaurus into a single keywordSet node.
    import_nodes.consolidate_keyword_sets(eml_node)

    fixup_namespaces(eml_node)

    fixup_distribution_urls(eml_node)


# # Some documents have both a <funding> node and an <award> node. Remove the <funding> node.
    # funding_nodes = []
    # to_remove = []
    # eml_node.find_all_descendants(names.FUNDING, funding_nodes)
    # for funding_node in funding_nodes:
    #     award_nodes = funding_node.parent.find_all_children(names.AWARD)
    #     if len(award_nodes) > 0:
    #         to_remove.append(funding_node)
    # for node in to_remove:
    #     node.parent.remove_child(node)
    # # Some documents have extra tags under intellectualRights that confuse metapype's evaluation function.
    # intellectual_rights_nodes = []
    # eml_node.find_all_descendants(names.INTELLECTUALRIGHTS, intellectual_rights_nodes)
    # for intellectual_rights_node in intellectual_rights_nodes:
    #     ir_content = display_texttype_node(intellectual_rights_node)
    #     if INTELLECTUAL_RIGHTS_CC0 in ir_content:
    #         intellectual_rights_node.content = INTELLECTUAL_RIGHTS_CC0
    #         intellectual_rights_node.remove_children()
    #     elif INTELLECTUAL_RIGHTS_CC_BY in ir_content:
    #         intellectual_rights_node.content = INTELLECTUAL_RIGHTS_CC_BY
    #         intellectual_rights_node.remove_children()


# Namespaces for the EML document
NSMAP = {
    "eml": "https://eml.ecoinformatics.org/eml-2.2.0",
    "stmml": "http://www.xml-cml.org/schema/stmml-1.2",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance"
}


def create_full_xml(eml_node):
    """
    Create the full XML document from the Metapype model, including the XML declaration and namespaces.
    """
    eml_node.nsmap = NSMAP
    eml_node.prefix = 'eml'
    eml_node.extras = {
        "xsi:schemaLocation": "https://eml.ecoinformatics.org/eml-2.2.0 https://eml.ecoinformatics.org/eml-2.2.0/eml.xsd"
    }
    return metapype_io.to_xml(eml_node)


def fixup_eml_namespaces_on_import(eml_node):
    """
    In case we have fetched an EML document created using an older version of the EML schema, we
      recursively fix up the namespaces.
    """

    def fix_node(node, nsmap):
        for prefix, uri in nsmap.items():
            if prefix in ['eml', 'stmml'] and prefix in nsmap:
                node.nsmap[prefix] = nsmap[prefix]
        for child in node.children:
            fix_node(child, nsmap)
        return node

    initial_nsmap = eml_node.nsmap
    eml_node = fix_node(eml_node, NSMAP)
    final_nsmap = eml_node.nsmap
    nsmap_changed = \
        initial_nsmap.get('eml') != final_nsmap.get('eml') or initial_nsmap.get('stmml') != final_nsmap.get('stmml')
    return eml_node, nsmap_changed


def fixup_categorical_variables(eml_node):
    """
    There was a bug that caused some Categorical variables to have None as variable type.
    Existing ezEML documents may still contain such variables. Here we fix them.
    """
    # Importing here to sidestep circular import problem.
    from webapp.views.data_tables.dt import change_measurement_scale
    data_table_nodes = []
    file_name = ''
    eml_node.find_all_descendants(names.DATATABLE, data_table_nodes)
    for data_table_node in data_table_nodes:
        attributes_to_fix = []
        non_numeric_domain_nodes = []
        data_table_node.find_all_descendants(names.NONNUMERICDOMAIN, non_numeric_domain_nodes)
        for non_numeric_domain_node in non_numeric_domain_nodes:
            if not non_numeric_domain_node.children:
                # Have an error case. Walk back up the tree to find the containing attribute node.
                nominal_node = non_numeric_domain_node.parent
                if nominal_node:
                    measurement_scale_node = nominal_node.parent
                    if measurement_scale_node:
                        attribute_node = measurement_scale_node.parent
                        if attribute_node:
                            attributes_to_fix.append(attribute_node)
        if attributes_to_fix:
            physical_node = data_table_node.find_child(names.PHYSICAL)
            if physical_node:
                object_name_node = physical_node.find_child(names.OBJECTNAME)
                if object_name_node:
                    file_name = object_name_node.content
            for attribute_node in attributes_to_fix:
                attribute_name_node = attribute_node.find_child(names.ATTRIBUTENAME)
                if attribute_name_node:
                    attribute_name = attribute_name_node.content
                    if file_name and attribute_name:
                        log_info(f'fixup_categorical_variables: fixing "{attribute_name}" in {file_name}')
                    change_measurement_scale(attribute_node, None, VariableType.CATEGORICAL.name)


def fixup_numerical_variables(eml_node):
    """
    There was a bug that caused some Numerical variables to be missing the numericDomain element.
    Existing ezEML documents may still contain such variables. Here we fix them.
    """
    data_table_nodes = []
    eml_node.find_all_descendants(names.DATATABLE, data_table_nodes)
    for data_table_node in data_table_nodes:
        # Look for ratio elements that have no numericDomain child.
        ratio_nodes = []
        data_table_node.find_all_descendants(names.RATIO, ratio_nodes)
        for ratio_node in ratio_nodes:
            if not ratio_node.find_child(names.NUMERICDOMAIN):
                # Create a numericDomain element and add it to the ratio element.
                numeric_domain_node = Node(names.NUMERICDOMAIN)
                ratio_node.add_child(numeric_domain_node)
                # Create a numberType element and add it to the numericDomain element.
                number_type_node = Node(names.NUMBERTYPE)
                numeric_domain_node.add_child(number_type_node)
                number_type_node.content = 'real'


def fixup_field_delimiters(eml_node):
    """
    There was a bug that caused the field delimiter to be saved as '\t' for tab-delimited data tables.
    This was then interpreted as an actual tab char in the XML. We need to escape it as '\\t' so we see
    the field delimiter as '\t' in the XML. dex, for example, expects to see '\t' in the XML.
    """
    field_delimiter_nodes = []
    eml_node.find_all_descendants(names.FIELDDELIMITER, field_delimiter_nodes)
    for field_delimiter_node in field_delimiter_nodes:
        if field_delimiter_node.content and field_delimiter_node.content == '\t':
            field_delimiter_node.content = '\\t'


def fixup_namespaces(eml_node):
    """
    When a package is fetched, all of the generated nodes have nsmap set to values inherited from the root node.

    Formerly, we had situations like the following: e.g., in consolidate_keyword_sets, we create a new keywordSet node
    and add, as children to the keywordSet node, existing keyword nodes from the fetched package. The existing keyword
    nodes have nsmap set to the root node's nsmap, but the new keywordSet node had an empty nsmap. When the XML was
    generated, the keyword elements were explicitly showing the namespaces. We don't want this. We want the inserted
    keywordSet node to have the same namespaces as the other nodes in the tree.

    This function fixes up such cases in existing packages.
    """
    def fix_node(node):
        if node.parent:
            if not node.nsmap:
                node.nsmap = node.parent.nsmap
        for child in node.children:
            fix_node(child)
        return node

    return fix_node(eml_node)


def fixup_distribution_urls(eml_node):
    """
    If the user has changed the document name via "Save As..." after creating the document, the distribution URLs need to
    be updated to reflect the new document name. We do this by scanning all documents because we want to fix up existing
    documents that have this problem. I.e., we don't rely on correcting the document names at the point that Save As is done.
    """
    from webapp.home.views import encode_distribution_url

    def parse_upload_url(url):
        """
        Given a URL, parse it into three parts: the part up to and including the rightmost occurrence of '/uploads/',
        the path after '/uploads/', and the filename.
        For example, given 'https://ezeml.edirepository.org/user-data/cvpia-9db0588ee81e2040e14807c59aafc537/uploads/edi.1365.8/catch.csv'
        return ('https://ezeml.edirepository.org/user-data/cvpia-9db0588ee81e2040e14807c59aafc537/uploads/', 'edi.1365.8', 'catch.csv')
        """
        index = url.rfind('/uploads/')
        if index != -1:
            # Split the string into before and after the rightmost occurrence of '/uploads/'.
            part1 = url[:index + len('/uploads/')]
            part2 = url[index + len('/uploads/'):]
            # Split the second string into head and tail.
            head, tail = os.path.split(part2)
            return part1, head, tail
        else:
            return None, None, None

    url_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.DATATABLE, names.PHYSICAL, names.DISTRIBUTION, names.ONLINE, names.URL])
    url_nodes = url_nodes + eml_node.find_all_nodes_by_path([names.DATASET, names.OTHERENTITY, names.PHYSICAL, names.DISTRIBUTION, names.ONLINE, names.URL])

    # Get the current server. We only want to fix up URLs that point to the current server.
    current_netloc = urlparse(request.base_url).netloc
    # Get the desired uploads subdirectory based on the user's active document.
    document_uploads_folder = user_data.get_document_uploads_folder_name()
    if not document_uploads_folder:
        return
    _, desired_subdir = os.path.split(document_uploads_folder)

    for url_node in url_nodes:
        if url_node.content:
            parsed_url = urlparse(url_node.content)
            if parsed_url.netloc == current_netloc and 'uploads' in parsed_url.path:
                found_base, found_subdir, found_filename = parse_upload_url(url_node.content)
                if found_subdir and found_subdir != desired_subdir:
                    url_node.content = f'{found_base}{desired_subdir}/{found_filename}'
                    encode_distribution_url(url_node)


def save_both_formats(filename:str=None, eml_node:Node=None, owner_login:str=None):
    """
    Save the Metapype model as both JSON and XML, after doing some cleanup.
    """
    import webapp.home.utils.create_nodes as create_nodes

    if not owner_login:
        owner_login = user_data.get_active_document_owner_login()
    clean_model(eml_node)
    enforce_dataset_sequence(eml_node)
    fix_up_custom_units(eml_node)
    fixup_categorical_variables(eml_node)
    fixup_numerical_variables(eml_node)
    fixup_field_delimiters(eml_node)
    create_nodes.add_eml_editor_metadata(eml_node)

    qudt_annotations.add_attribute_ids(eml_node)
    qudt_annotations.add_qudt_annotations(eml_node)

    if not owner_login:
        owner_login = user_data.get_active_document_owner_login()
    save_eml(filename=filename, eml_node=eml_node, format='json', owner_login=owner_login)
    save_eml(filename=filename, eml_node=eml_node, format='xml', owner_login=owner_login)

    get_check_metadata_status(eml_node, filename) # To keep badge up-to-date in UI


def save_eml(filename:str=None, eml_node:Node=None, format:str='json', owner_login:str=None):
    """
    Save the Metapype model as either JSON or XML.
    """

    if filename:
        if eml_node is not None:
            from webapp.home.views import url_of_interest
            if Config.MEM_LOG_METAPYPE_STORE_ACTIONS and url_of_interest():
                    log_info(f'*** save_eml ***: node store checksum={calculate_node_store_checksum()}    {filename}')

            output_str = None

            if format == 'json':
                output_str = metapype_io.to_json(eml_node)
            elif format == 'xml':
                xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
                xml_str = create_full_xml(eml_node)
                output_str = xml_declaration + xml_str

            if output_str:
                user_folder = user_data.get_user_folder_name(owner_login=owner_login) or '.'
                filename = f'{user_folder}/{filename}.{format}'
                with open(filename, "w") as fh:
                    fh.write(output_str)
                    fh.flush()
        else:
            raise ValueError(f"No EML node was supplied for saving EML.")
    else:
        raise ValueError(f"No filename value was supplied for saving EML.")


def create_eml(filename=None):
    """
    Create a minimal Metapype model consisting of access rules and an empty dataset, and save it.
    """
    import webapp.home.utils.create_nodes as create_nodes

    user_data.set_active_document(None)

    eml_node = Node(names.EML)
    eml_node.add_attribute('system', Config.SYSTEM_ATTRIBUTE_VALUE)

    access_node = create_nodes.create_access(parent_node=eml_node)
    initialize_access_rules(access_node)

    _ = node_utils.new_child_node(names.DATASET, parent=eml_node)

    try:
        save_both_formats(filename=filename, eml_node=eml_node)
    except Exception as e:
        log_error(e)


def initialize_access_rules(access_node:Node):
    """
    Initialize the access element with default access rules for user and public
    """
    if current_user.is_authenticated:
        user_allow_node = node_utils.new_child_node(names.ALLOW, parent=access_node)

        user_principal_node = node_utils.new_child_node(names.PRINCIPAL, parent=user_allow_node)
        userid = current_user.get_dn()
        user_principal_node.content = userid

        user_permission_node = node_utils.new_child_node(names.PERMISSION, parent=user_allow_node)
        user_permission_node.content = 'all'

    public_allow_node = node_utils.new_child_node(names.ALLOW, parent=access_node)

    public_principal_node = node_utils.new_child_node(names.PRINCIPAL, parent=public_allow_node)
    public_principal_node.content = 'public'

    public_permission_node = node_utils.new_child_node(names.PERMISSION, parent=public_allow_node)
    public_permission_node.content = 'read'


def check_taxonomic_coverage_consistency_with_ezeml(eml_node, package_name):
    """
    Some models created outside of ezEML have taxonomic coverage that does not adhere to the pattern expected by ezEML.
    This function checks for that condition and if it is True, sets a flag in the package to indicate that the model
    has taxonomic coverage that is not consistent with ezEML. This flag is used to block access to editing of taxonomic
    coverage.

    What ezEML expects is that each taxonomicCoverage element will have one and only one taxonomicClassification child.
    So, if there are multiple taxonomic coverages defined, each will have its own taxonomicCoverage element. The schema
    permits multiple taxonomicClassification children, but ezEML does not.
    """
    # If there is no taxonomicCoverage in the package, or if there is taxonomicCoverage but it adheres to the pattern
    #  expected by ezEML, we don't want to block access to editing of taxonomic coverage
    taxonomic_coverage_nodes = eml_node.find_all_nodes_by_path([names.DATASET, names.COVERAGE, names.TAXONOMICCOVERAGE])
    if not taxonomic_coverage_nodes:
        clear_taxonomy_imported_from_xml_flag(eml_node, package_name)
        return True
    else:
        ezeml_valid = True
        for taxonomic_coverage_node in taxonomic_coverage_nodes:
            taxonomic_classification_nodes = taxonomic_coverage_node.find_all_children(names.TAXONOMICCLASSIFICATION)
            if len(taxonomic_classification_nodes) > 1:
                ezeml_valid = False
                break
        if ezeml_valid:
            clear_taxonomy_imported_from_xml_flag(eml_node, package_name)
        return ezeml_valid


def add_imported_from_xml_metadata(eml_node:Node=None, xml_filename:str=None, package_name:str=None):
    """
    If the model was imported from an XML file, we add additonalMetadata to the EML node to indicate that fact,
    including the XML filename and the date of importation.
    """
    imported_from_xml_node = eml_node.find_descendant('importedFromXML')
    if imported_from_xml_node:
        metadata_node = imported_from_xml_node.parent
        additional_metadata_node = metadata_node.parent
        eml_node.remove_child(additional_metadata_node)
    additional_metadata_node = node_utils.new_child_node(names.ADDITIONALMETADATA, parent=eml_node)
    metadata_node = node_utils.new_child_node(names.METADATA, parent=additional_metadata_node)
    # For the importedFromXML node, we need to bypass Metapype validity checking
    imported_from_xml_node = Node('importedFromXML', parent=metadata_node)
    metadata_node.add_child(imported_from_xml_node)
    imported_from_xml_node.attributes.clear()
    imported_from_xml_node.add_attribute('filename', xml_filename)
    imported_from_xml_node.add_attribute('dateImported', str(date.today()))
    check_taxonomic_coverage_consistency_with_ezeml(eml_node, package_name)


def get_imported_from_xml_metadata(eml_node:Node=None):
    """
    If the model was imported from an XML file, return a string saying so, including the XML filename and the date of
    importation. This string is used to inform data curators of the source of the model.
    """
    imported_from_xml_node = eml_node.find_descendant('importedFromXML')
    msg = ''
    if imported_from_xml_node:
        filename = imported_from_xml_node.attribute_value('filename')
        date = imported_from_xml_node.attribute_value('dateImported')
        if filename and date:
            msg = f'\n\n\nThis data package is based on EML XML imported from {filename} on {date}.'
    return msg


def was_imported_from_xml(eml_node):
    """
    Return True if the model was imported from an XML file, False otherwise.
    """
    imported_from_xml_node = eml_node.find_descendant('importedFromXML')
    if imported_from_xml_node:
        return True
    else:
        return False


def clear_taxonomy_imported_from_xml_flag(eml_node, package_name=None):
    """
    If the package was imported from XML but the taxonomic coverage is consistent with ezEML's expectations,
    we add a flag indicating that the taxonomic coverage is OK for ezEML.

    This flag is set if the package is imported from XML and the taxonomic coverage is consistent with ezEML's
    expectations, and it is also set when taxonomic coverage is imported from another ezEML package or when the
    taxonomic coverage is cleared in ezEML.
    """
    imported_from_xml_node = eml_node.find_descendant('importedFromXML')
    if imported_from_xml_node:
        imported_from_xml_node.add_attribute('taxonomicCoverageExempt', True)
        if package_name:
            save_both_formats(package_name, eml_node)


def taxonomy_inconsistent_with_ezeml(eml_node, package_name):
    """
    Return True if the package was imported from XML and the taxonomic coverage is not consistent with ezEML's
    expectations, False otherwise.
    """
    imported_from_xml_node = eml_node.find_descendant('importedFromXML')
    if imported_from_xml_node:
        if imported_from_xml_node.attribute_value('taxonomicCoverageExempt'):
            # The taxonomic coverage was previously checked for consistency with ezEML and found to be OK
            return False
        else:
            # There exist packages that were imported from XML before we checked the taxonomic coverage
            #  for consistency with ezEML, so we'll do it here, possibly redundantly.
            return not check_taxonomic_coverage_consistency_with_ezeml(eml_node, package_name)
    else:
        return False


def fix_up_custom_units(eml_node:Node=None, new_custom_unit=None, new_description=None):
    """
    Fix up the handling of custom units in the additionalMetadata node.

    The additionalMetadata nodes are handled differently from how they were handled initially.
    Pre-existing data packages need to be fixed up. Newly-created data packages will be correct, but
      since we have this code, we'll also use it to add new custom units to the additionalMetadata node.

    What should result is a single additionalMetadata node with all the custom units in it.
    There may be other additionalMetadata nodes that do not contain custom units, and they will be left alone.
    """
    def collect_custom_units_from_attributes(eml_node):
        custom_unit_nodes = []
        eml_node.find_all_descendants(names.CUSTOMUNIT, custom_unit_nodes)
        custom_units = set()
        for custom_unit_node in custom_unit_nodes:
            custom_units.add(custom_unit_node.content)
        return list(custom_units)

    def collect_custom_units_from_additional_metadata(eml_node):
        unit_list_nodes = []
        unit_nodes = []
        eml_node.find_all_descendants(names.UNITLIST, unit_list_nodes)
        for unit_list_node in unit_list_nodes:
            unit_nodes.extend(unit_list_node.children)
        custom_units = {}
        for unit_node in unit_nodes:
            if unit_node.attribute_value('name'):
                custom_unit_name = unit_node.attribute_value('name')
                description_node = unit_node.find_child(names.DESCRIPTION)
                if description_node:
                    description = description_node.content
                else:
                    description = ''
                # We capture the attributes of the unit node so that we can restore them when we write the
                #  custom unit back out. Packages that have been fetched from the repository may contain
                #  additional attributes besides the id and name, and we don't want to lose them.
                custom_units[custom_unit_name] = (description, unit_node.attributes)
        return custom_units

    custom_units_from_attributes = collect_custom_units_from_attributes(eml_node)
    custom_units_from_additional_metadata = collect_custom_units_from_additional_metadata(eml_node)

    # Remove any custom units from the additionalMetadata node that are not in the attributes, i.e., that are no longer
    #  needed.
    current_keys = list(custom_units_from_additional_metadata.keys())
    for key in current_keys:
        if key not in custom_units_from_attributes:
            del custom_units_from_additional_metadata[key]

    # Add any custom units from the attributes that are not in the additionalMetadata node.
    for custom_unit in custom_units_from_attributes:
        if custom_unit not in custom_units_from_additional_metadata:
            custom_units_from_additional_metadata[custom_unit] = ('', { 'id': custom_unit, 'name': custom_unit})

    if new_custom_unit:
        custom_units_from_additional_metadata[new_custom_unit] = (new_description, { 'id': custom_unit, 'name': custom_unit})

    # Remove any additionalMetadata nodes that contain custom units. We're going to recreate one.
    # First, remove unitList nodes.
    unit_list_nodes = []
    eml_node.find_all_descendants(names.UNITLIST, unit_list_nodes)
    for unit_list_node in unit_list_nodes:
        parent_node = unit_list_node.parent
        parent_node.remove_child(unit_list_node)
    # Now remove additionalMetadata nodes that contain only a metadata node.
    # We do it this way on the off chance that an additionalMetadata node that contained a unitList node also contains
    #  some other stuff. This is not expected, but it's legal EML.
    additional_metadata_nodes = []
    eml_node.find_all_descendants(names.ADDITIONALMETADATA, additional_metadata_nodes)
    for additional_metadata_node in additional_metadata_nodes:
        if len(additional_metadata_node.children) == 1 and \
                additional_metadata_node.children[0].name == names.METADATA and \
                len(additional_metadata_node.children[0].children) == 0:
            parent_node = additional_metadata_node.parent
            parent_node.remove_child(additional_metadata_node)

    # If needed, create a new additionalMetadata node with the custom units.
    if custom_units_from_additional_metadata:
        additional_metadata_node = node_utils.new_child_node(names.ADDITIONALMETADATA, eml_node)
        metadata_node = node_utils.new_child_node(names.METADATA, additional_metadata_node, force=True)
        unitlist_node = node_utils.new_child_node(names.UNITLIST, metadata_node, force=True)
        unitlist_node.prefix = 'stmml'
        for custom_unit_name, custom_unit_details in custom_units_from_additional_metadata.items():
            unit_node = node_utils.new_child_node(names.UNIT, unitlist_node, force=True)
            unit_node.add_attribute('id', custom_unit_name)
            unit_node.add_attribute('name', custom_unit_name)
            custom_unit_description, custom_unit_attributes = custom_unit_details
            for key, value in custom_unit_attributes.items():
                if key not in ['id', 'name']:
                    unit_node.add_attribute(key, value)
            unit_node.prefix = 'stmml'
            description_node = node_utils.new_child_node(names.DESCRIPTION, unit_node, custom_unit_description, force=True)
            description_node.prefix = 'stmml'


def handle_custom_unit_additional_metadata(eml_node:Node=None,
                                           custom_unit_name:str=None,
                                           custom_unit_description:str=None):
    """
    Add a custom unit name and description to the additionalMetadata node if it's not already there.
    """
    fix_up_custom_units(eml_node, custom_unit_name, custom_unit_description)

    # save custom unit names and descriptions in session so we can do some javascript magic
    custom_units = session.get("custom_units", {})
    custom_units[custom_unit_name] = custom_unit_description
    session["custom_units"] = custom_units
