import json
import glob
import os
import re
from urllib.parse import unquote

import webapp.auth.user_data as user_data

from webapp.home.exceptions import InvalidXMLError

from metapype.eml import export, evaluate, validate, names, rule
from metapype.model.node import Node, Shift
from metapype.model import mp_io, metapype_io

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
INVALID_XML_MESSAGE_2 = 'The XML is invalid. Please make corrections before continuing.\nError details: '
INVALID_XML_MESSAGE_3 = ' element contains invalid XML. Please make corrections before continuing.\nError details: '
INVALID_XML_MESSAGE_4 = 'The XML is invalid.\nError details: '


def invalid_xml_error_message(msg, reset_changes_available=True, node_name=None, is_ajax_request=False):
    paren = msg.rfind('(')
    if paren > 0:
        msg = msg[:msg.rfind('(')].rstrip()
    if is_ajax_request:
        return f"{msg}."
    elif reset_changes_available:
        return f"{INVALID_XML_MESSAGE_1} {msg}."
    elif not node_name:
        return f"{INVALID_XML_MESSAGE_2} {msg}."
    else:
        return f'"{node_name.capitalize()}"{INVALID_XML_MESSAGE_3} {msg}.'


def find_all_descendant_names(node, descendant_names):
    for child_node in node.children:
        descendant_names.add(child_node.name)
        find_all_descendant_names(child_node, descendant_names)


def node_has_complex_children(texttype_node):
    if not texttype_node:
        return False
    descendant_names = set()
    simple_names = {names.PARA}
    find_all_descendant_names(texttype_node, descendant_names)
    return len(descendant_names - simple_names)


def model_has_complex_texttypes(eml_node):
    if not eml_node:
        raise ValueError
    for texttype_node_name in TEXTTYPE_NODES:
        texttype_nodes = []
        eml_node.find_all_descendants(texttype_node_name, texttype_nodes)
        for texttype_node in texttype_nodes:
            if node_has_complex_children(texttype_node):
                return True
    return False


def node_has_literal_children(texttype_node):
    if not texttype_node:
        return False
    literals = set([names.LITERALLAYOUT, names.MARKDOWN])
    descendant_names = set()
    find_all_descendant_names(texttype_node, descendant_names)
    return len(literals & descendant_names)


def add_escapes(txt):
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


def remove_escapes(s):
    lt_regex = r'(?<!\\)\<'
    gt_regex = r'(?<!\\)\>'
    s = re.sub(lt_regex, '&lt;', s)
    s = re.sub(gt_regex, '&gt;', s)
    s = s.replace(r'\<', '<').replace(r'\>', '>').replace('\r\n', '\n')
    return s


def display_simple_texttype_node(text_node: Node = None) -> str:
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
    if not texttype_node:
        return ''
    if texttype_node.name not in TEXTTYPE_NODES:
        return texttype_node.content
    use_complex_representation = user_data.get_model_has_complex_texttypes()
    if use_complex_representation:
        output = metapype_io.to_xml(texttype_node)
        # Suppress the xmlns from the opening tag. It won't make sense to users.
        lines = output.split('\n')
        if 'xmlns:' in lines[0]:
            open_tag = lines[0].split('xmlns:')[0][:-1] + '>'
        else:
            open_tag = lines[0].split('>')[0][:] + '>'
        close_tag = open_tag.replace('<', '</')
        if texttype_node.content:
            output = open_tag + texttype_node.content + close_tag
        else:
            output = open_tag + '\n' + '\n'.join(lines[1:-1])
        return add_escapes(output).replace('&lt;', '<').replace('&gt;', '>')
    else:
        return display_simple_texttype_node(texttype_node)


def sample_text(texttype_node):
    # For use, for example, in displaying a snippet of description for method step select page
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
    if is_ajax_request or user_data.get_model_has_complex_texttypes():
        if not text:
            return True, None
        try:
            # Raises an InvalidXMLError exception if invalid
            construct_texttype_node(text, parent_name=parent_name)
        except InvalidXMLError as e:
            return False, str(e)
    return True, None


def construct_texttype_node(text, parent_name=None):
    if parent_name and parent_name not in TEXTTYPE_NODES:
        return text
    try:
        subtree = metapype_io.from_xml(remove_escapes(text), clean=True, literals=['literalLayout', 'markdown'])
        errs = []
        validate.tree(subtree, errs)
        return subtree
    except Exception as e:
        if e.__class__.__name__ == 'XMLSyntaxError':
            if str(e).startswith('Start tag expected'):
                try:
                    # We may have a naked string. Try adding the root node.
                    text = f"<{parent_name}>{text}</{parent_name}>"
                    subtree = metapype_io.from_xml(text, clean=True, literals=['literalLayout', 'markdown'])
                    validate.tree(subtree)
                    return subtree
                except Exception as e2:
                    raise InvalidXMLError(str(e2))
        raise InvalidXMLError(str(e))


def check_xml_validity(xml:str=None, parent_name:str=None):
    IS_AJAX_REQUEST = True
    xml = unquote(xml)
    valid, msg = is_valid_xml_fragment(xml, parent_name, IS_AJAX_REQUEST)
    if valid:
        response = 'Valid XML'
    else:
        response = invalid_xml_error_message(msg, is_ajax_request=IS_AJAX_REQUEST)
    return response


def try_it():
    def get_existing_eml_files():
        filelist = glob.glob(f'{EML_FILES_PATH}/*.xml')
        return sorted([os.path.basename(x) for x in filelist])

    def load_xml(filename):
        with open(f"{filename}", "r") as f:
            xml = "".join(f.readlines())
        eml_node = metapype_io.from_xml(xml, clean=True, literals=['literalLayout', 'markdown'])
        assert isinstance(eml_node, Node)
        return eml_node

    def json_from_xml(filename):
        eml_node = load_xml(filename)
        _json = metapype_io.to_json(eml_node)
        parsed = json.loads(_json)
        return json.dumps(parsed, indent=1, sort_keys=False)

    def scan_files():
        i = 0
        for filename in get_existing_eml_files():
            eml_node = load_xml(os.path.join(EML_FILES_PATH, filename))
            if model_has_complex_texttypes(eml_node):
                print(f"{filename}")
                i += 1
            if i > 100:
                break

    test_file = '/Users/jide/git/ezEML/tests/eml.xml'
    eml_node = load_xml(test_file)
    use_complex_representation = model_has_complex_texttypes(eml_node)
    # user_data.set_model_has_complex_texttypes(use_complex_representation)
    abstract_node = eml_node.find_descendant(names.ABSTRACT)
    output = display_texttype_node(abstract_node)
    print(output)
    print('------')
    print(remove_escapes(output))
    subtree = construct_texttype_node(output, names.ABSTRACT)

    title_node = eml_node.find_descendant(names.TITLE)
    output = display_texttype_node(title_node)
    print(output)
    print('------')
    print(remove_escapes(output))
    subtree = construct_texttype_node(output, names.TITLE)

    sampling_description_node = eml_node.find_descendant(names.SAMPLINGDESCRIPTION)
    output = display_texttype_node(sampling_description_node)
    print(output)
    print('------')
    print(remove_escapes(output))
    subtree = construct_texttype_node(output, names.SAMPLINGDESCRIPTION)


if __name__ == "__main__":
    try_it()
