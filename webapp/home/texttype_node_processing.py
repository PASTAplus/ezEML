"""
Helper functions to handle TextType nodes, including checking them for valid xml, etc.

When a model contains complex text elements (e.g., ones containing sections or itemizedlists), we need to check them
for valid XML, and when we display them we need to display the tags, but in escaped form. E.g. <para>Some text</para>
should be displayed as <&lt;>para&gt;Some text&lt;/para&gt;. This module contains functions to handle that.
"""

import json
import glob
import os
import re
from urllib.parse import unquote
from xml.sax.saxutils import unescape

import webapp.home.utils.load_and_save
from webapp.auth import user_data as user_data

from webapp.home.exceptions import InvalidXMLError

from metapype.eml import export, evaluate, validate, names, rule
from metapype.model.node import Node, Shift
from metapype.model import mp_io, metapype_io
from webapp.home.home_utils import log_error

EML_FILES_PATH = '/Users/jide/git/umbra/eml_files'

TEXTTYPE_NODES = [
    names.ABSTRACT,
    names.ACKNOWLEDGEMENTS,
    names.ADDITIONALINFO,
    names.DESCRIPTION,
    names.FUNDING,
    names.GETTINGSTARTED,
    names.INTELLECTUALRIGHTS,
    names.INTRODUCTION,
    names.PURPOSE,
    names.SAMPLINGDESCRIPTION,
]

TEXTTYPE_CHILDREN = [
    # names.CITETITLE,
    names.EMPHASIS,
    names.ITEMIZEDLIST,
    names.LISTITEM,
    names.LITERALLAYOUT,
    names.MARKDOWN,
    names.ORDEREDLIST,
    names.PARA,
    names.SECTION,
    names.SUBSCRIPT,
    names.SUPERSCRIPT,
    names.TITLE,
    # names.ULINK
]


INVALID_XML_MESSAGE_1 = 'XML error: '
INVALID_XML_MESSAGE_2 = 'The XML is invalid. Please make corrections before continuing. Error details:\n'
INVALID_XML_MESSAGE_3 = ' element contains invalid XML. Please make corrections before continuing. Error details:\n'
INVALID_XML_MESSAGE_4 = 'The XML is invalid.\nError details: '


def invalid_xml_error_message(msg, reset_changes_available=True, node_name=None, is_ajax_request=False):
    """
    Return a message to display to the user when the XML is invalid.
    """
    paren = msg.rfind('(')
    if paren > 0:
        msg = msg[:msg.rfind('(')].rstrip()
    if is_ajax_request:
        return f"{msg}."
    elif reset_changes_available:
        return f"{INVALID_XML_MESSAGE_2} {msg}."
    elif not node_name:
        return f"{INVALID_XML_MESSAGE_2} {msg}."
    else:
        return f'"{node_name.capitalize()}"{INVALID_XML_MESSAGE_3} {msg}.'


def find_all_descendant_names(node, descendant_names):
    """
    Recursively find all descendant names of a node, filling in the descendant_names set.
    """
    for child_node in node.children:
        descendant_names.add(child_node.name)
        find_all_descendant_names(child_node, descendant_names)


def node_has_complex_children(texttype_node):
    """
    Determine if a node has any TextType children other than para.
    """
    if not texttype_node:
        return False
    descendant_names = set()
    simple_names = {names.PARA}
    find_all_descendant_names(texttype_node, descendant_names)
    return len(descendant_names - simple_names)


def model_has_complex_texttypes(eml_node):
    """
    Determine if a model has any TextType nodes with complex children.

    For each TextType node, check if it has any children other than para. So, for example, if Project Abstract contains
    a section, then it is complex, so the model has complex texttypes.
    """
    if user_data.get_enable_complex_text_element_editing_global():
        return True
    if user_data.get_enable_complex_text_element_editing_document():
        return True
    if not eml_node:
        log_error('**** model_has_complex_texttypes: eml_node is None ****')
        return False # This should never happen, but we don't want to raise an exception here.
        # raise ValueError
    for texttype_node_name in TEXTTYPE_NODES:
        texttype_nodes = []
        eml_node.find_all_descendants(texttype_node_name, texttype_nodes)
        for texttype_node in texttype_nodes:
            if node_has_complex_children(texttype_node):
                return True
    return False


def node_has_literal_children(texttype_node):
    """
    Determine if the node has any literal children (i.e., literalLayout or markdown). These need to be displayed with
    a monospace font.
    """
    if not texttype_node:
        return False
    literals = set([names.LITERALLAYOUT, names.MARKDOWN])
    descendant_names = set()
    find_all_descendant_names(texttype_node, descendant_names)
    return len(literals & descendant_names)


def display_simple_texttype_node(text_node: Node = None) -> str:
    """
    Return a string representation of a simple TextType node's content. The caller has already determined that the
    node is simple. For this purpose, simple means that the node has no children other than para. Para nodes are
    replaced using newlines. Escaped lt and gt chars are unescaped. This latter step is necessary because the content
    of the node may include lt and gt chars but we want to display them as < and > so they make sense to the user.
    They will be escaped again when the content is saved to XML.
    """
    # Currently, this handles simple cases with paras only (paras may be contained in sections)
    if not text_node:
        return ''
    if text_node.content and not text_node.content.isspace():
        return text_node.content
    text = ''
    para_nodes = []
    text_node.find_all_descendants(names.PARA, para_nodes)
    for para_node in para_nodes:
        if para_node.content:
            text += f'{para_node.content}\n'
    return text.replace('&lt;', '<').replace('&gt;', '>')


def display_texttype_node(texttype_node):
    """
    Return a string representation of a TextType node's content. If we're displaying a simple texttype node, then
    return the content of the node. Otherwise, build up the text from the content of the node's children, adding
    escaped tags as necessary.
    """
    def add_escapes(txt):
        """
        Take a string that includes tags and escape the tags so that they are not interpreted as HTML.
        """
        for name in TEXTTYPE_NODES + TEXTTYPE_CHILDREN:
            open_tag = f'<{name}>'
            if open_tag in txt:
                esc_open_tag = f'\\<{name}\\>'
                txt = txt.replace(open_tag, esc_open_tag)
            close_tag = f'</{name}>'
            if close_tag in txt:
                esc_close_tag = f'\\</{name}\\>'
                txt = txt.replace(close_tag, esc_close_tag)
            content_less_tag = f'<{name}/>'
            if content_less_tag in txt:
                esc_content_less_tag = f'\\<{name}/\\>'
                txt = txt.replace(content_less_tag, esc_content_less_tag)
        return txt

    if not texttype_node:
        return ''
    if texttype_node.name not in TEXTTYPE_NODES:
        return texttype_node.content
    use_complex_representation = user_data.get_model_has_complex_texttypes()
    if use_complex_representation:
        # Get the XML representation of the node and its subtree
        output = metapype_io.to_xml(texttype_node)
        # Suppress the xmlns from the opening tag. It won't make sense to users.
        lines = output.splitlines()
        if 'xmlns:' in lines[0]:
            open_tag = lines[0].split('xmlns:')[0][:-1] + '>'
        else:
            open_tag = lines[0].split('>')[0][:] + '>'
        close_tag = open_tag.replace('<', '</')
        if texttype_node.content:
            output = open_tag + texttype_node.content + close_tag
        elif 'xmlns:' in lines[0]:
            # We replace line 0 with the open_tag. This gets rid of the xmlns.
            output = open_tag + '\n' + '\n'.join(lines[1:])
        return add_escapes(output).replace('&lt;', '<').replace('&gt;', '>')
    else:
        return display_simple_texttype_node(texttype_node)


def excerpt_text(texttype_node):
    # For use, for example, in displaying a snippet of description for method step select page, where we display just
    #  an excerpt of the text, not the entire text.
    title = ''
    text = ''
    if not texttype_node:
        return title, text
    title_node = texttype_node.find_descendant(names.TITLE)
    if title_node:
        title = title_node.content
    text = display_simple_texttype_node(texttype_node)
    # if we didn't get anything, let's see if what we have is markdown
    if not text:
        markdown_nodes = []
        texttype_node.find_all_descendants(names.MARKDOWN, markdown_nodes)
        for markdown_node in markdown_nodes:
            if markdown_node.content:
                text += f'{markdown_node.content}\n'
        text = text.replace('#', '')
    return title, text


def is_valid_xml_fragment(text, parent_name=None, is_ajax_request=False):
    """
    Return True if the text is a valid XML fragment. If not, return False and an error message.
    """
    if is_ajax_request or user_data.get_model_has_complex_texttypes():
        if not text:
            return True, None
        try:
            # Raises an InvalidXMLError exception if invalid
            _, errs = construct_texttype_node(text, parent_name=parent_name)
        except InvalidXMLError as e:
            return False, str(e)
        if errs:
            # We have validation/evaluation errs. Return them as a string.
            return False, '\n'.join([x[1] for x in errs])
    return True, None


def construct_texttype_node(text, parent_name=None):
    """
    Given the text displayed for a TextType node, construct the corresponding XML fragment so we can check it for
    validity. If the parent node is not a TextType node, then return the text as is. Check the validity of the XML
    and raise InvalidXMLError if invalid, with an error message.
    """
    def remove_escapes(s):
        lt_regex = r'(?<!\\)\<'
        gt_regex = r'(?<!\\)\>'
        s = re.sub(lt_regex, '&lt;', s)
        s = re.sub(gt_regex, '&gt;', s)
        s = s.replace(r'\<', '<').replace(r'\>', '>').replace('\r\n', '\n')
        return s

    def introduce_paras(s):
        if s:
            output = []
            paras = s.splitlines()
            for para in paras:
                output.append(f'<para>{para}</para>')
            return '\n'.join(output)
        return ''

    if parent_name and parent_name not in TEXTTYPE_NODES:
        return text
    try:
        subtree = metapype_io.from_xml(remove_escapes(text), clean=True, literals=['literalLayout', 'markdown'])
        errs = []
        validate.tree(subtree, errs)
        return subtree, errs
    except Exception as e:
        if e.__class__.__name__ == 'XMLSyntaxError':
            if str(e).startswith('Start tag expected'):
                try:
                    # We may have a naked string. Try adding the root node.
                    # First, capture paras
                    text = f"<{parent_name}>{introduce_paras(text)}</{parent_name}>"
                    subtree = metapype_io.from_xml(text, clean=True, literals=['literalLayout', 'markdown'])
                    validate.tree(subtree)
                    return subtree
                except Exception as e2:
                    raise InvalidXMLError(str(e2))
        raise InvalidXMLError(str(e))


def check_xml_validity(xml:str=None, parent_name:str=None):
    """
    Check the validity of the XML fragment. Return a response that can be displayed to the user.
    This is called from the AJAX request handler when the user clicks the checkmark button.
    """
    IS_AJAX_REQUEST = True
    xml = unquote(xml)
    valid, msg = is_valid_xml_fragment(xml, parent_name, IS_AJAX_REQUEST)
    if valid:
        response = 'Valid XML'
    else:
        response = invalid_xml_error_message(msg, is_ajax_request=IS_AJAX_REQUEST)
    return response


def post_process_texttype_node(text_node:Node=None, displayed_text:str=None):
    """
    After a text node has been edited or created, we need to post-process it to make sure it's in the correct form.

    If our model has complex TextTypes and the node is TextType node, if the user has edited it the edited text will
    be in the content of the node. We need to convert appropriately to represent the XML structure in descendants of
    the node.

    It is assumed that text_node.content has been set to the text displayed in the form, which may or may not have been
    modified by the user. If the user has modified the text, then text_node.content will be different from the
    original text in the node. If the user has not modified the text, then text_node.content will be the same as the
    original text in the node.
    """
    from webapp.home.texttype_node_processing import TEXTTYPE_NODES, construct_texttype_node

    def save_content_in_para_nodes(text_node):
        s = text_node.content
        if s:
            paras = s.splitlines()
            for para in paras:
                para_node = Node(names.PARA, parent=text_node)
                para_node.content = para
                text_node.add_child(para_node)
            text_node.content = ''

    def remove_paragraph_tags(s):
        if s:
            return unescape(s).strip().replace('</para>\n<para>', '\n').replace('<para>', '').replace('</para>',
                                                                                                      '').replace('\r','')
        else:
            return s

    if not text_node:
        return
    use_complex_representation = user_data.get_model_has_complex_texttypes()
    original_text = display_texttype_node(text_node)
    if displayed_text != original_text:
        # We're saving a node that's been modified. We remake the children.
        if use_complex_representation and text_node.name in TEXTTYPE_NODES:
            new_node, _ = construct_texttype_node(displayed_text, text_node.name)
            text_node.content = new_node.content
            text_node.tail = new_node.tail
            text_node.children = new_node.children
        else:
            # If we have para children, we're handling text that has been modified but that originally used
            #  para tags (e.g., a package imported from XML). Presumably, the user wants paras, so let's
            #  do that. We need to check for this before we remove the children.
            all_paras = False
            children = text_node.children
            if children:
                all_paras = True
                for child in children:
                    if child.name != names.PARA:
                        all_paras = False
                        break
            text_node.remove_children()
            text_node.content = displayed_text
            if all_paras or not children:  # If we have no children, we're handling simple text. Add paras there, too.
                save_content_in_para_nodes(text_node)
                # Now the content is in the children. We need to remove the content from the node.
                text_node.content = ''
