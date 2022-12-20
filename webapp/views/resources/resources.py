import daiquiri
from flask import (
    Blueprint, flash, render_template, redirect, request, url_for, session
)
from flask_login import (
    current_user, login_required
)

from webapp.auth.user_data import (
    is_first_usage, set_active_packageid, get_user_folder_name
)

from webapp.home.metapype_client import (
    add_child, create_abstract, create_intellectual_rights,
    create_keyword, create_pubinfo, create_data_package_id,
    create_title, list_keywords, load_eml, remove_child,
    save_both_formats, DOWN_ARROW, UP_ARROW,
    handle_hidden_buttons, check_val_for_hidden_buttons
)

from webapp.home.forms import is_dirty_form, form_md5
from webapp.views.resources.forms import (
    AbstractForm,
    DataPackageIDForm,
    IntellectualRightsForm,
    KeywordForm,
    KeywordSelectForm,
    PublicationInfoForm,
    TitleForm
)
from webapp.home.texttype_node_processing import (
    display_texttype_node,
    node_has_literal_children,
    is_valid_xml_fragment,
    invalid_xml_error_message,
    model_has_complex_texttypes
)

from webapp.buttons import *
from webapp.home.exceptions import *
from webapp.pages import *

from webapp.home.views import process_up_button, process_down_button, get_help, get_helps
from metapype.eml import names
from metapype.model.node import Node

from webapp.home.intellectual_rights import (
    INTELLECTUAL_RIGHTS_CC0, INTELLECTUAL_RIGHTS_CC_BY
)

from webapp.home.views import set_current_page, get_keywords

logger = daiquiri.getLogger('views: ' + __name__)
res_bp = Blueprint('res', __name__, template_folder='templates')


def log_error(msg):
    if current_user and hasattr(current_user, 'get_username'):
        logger.error(msg, USER=current_user.get_username())
    else:
        logger.error(msg)


def log_info(msg):
    if current_user and hasattr(current_user, 'get_username'):
        logger.info(msg, USER=current_user.get_username())
    else:
        logger.info(msg)


@res_bp.route('/title/<filename>', methods=['GET', 'POST'])
@login_required
def title(filename=None):
    metapype_store_size = len(Node.store)
    log_info(f'Title    metapype_store_size={metapype_store_size}')

    form = TitleForm()

    # Process POST
    if request.method == 'POST' and form.validate_on_submit():
        save = False
        if is_dirty_form(form):
            save = True

        if save:
            create_title(title=form.title.data, filename=filename)
            form.md5.data = form_md5(form)

        new_page = PAGE_DATA_TABLE_SELECT
        this_page = PAGE_TITLE
        new_page = handle_hidden_buttons(new_page, this_page)

        return redirect(url_for(new_page, filename=filename))

    # Process GET
    try:
        eml_node = load_eml(filename=filename)
        dataset_node = eml_node.find_child(child_name=names.DATASET)
        title_node = dataset_node.find_child(names.TITLE)
        if title_node:
            form.title.data = title_node.content

    except Exception as err:
        log_error(f'Exception in title route. filename={filename}')
        log_error(err)
        raise err

    form.md5.data = form_md5(form)

    set_current_page('title')
    help = get_helps(['title', 'nav', 'welcome'])
    first_usage = is_first_usage()
    return render_template('title.html', title='Title', form=form, help=help, is_first_usage=first_usage)


@res_bp.route('/data_package_id/<filename>', methods=['GET', 'POST'])
@login_required
def data_package_id(filename=None):
    form = DataPackageIDForm()
    eml_node = load_eml(filename=filename)

    # Process POST
    # if request.method == 'POST' and form.validate_on_submit():
    if request.method == 'POST':
        save = False
        if is_dirty_form(form):
            save = True

        if save:
            data_package_id = form.data_package_id.data
            create_data_package_id(data_package_id, filename)
            set_active_packageid(data_package_id)
            form.md5.data = form_md5(form)

        new_page = PAGE_TITLE
        this_page = PAGE_DATA_PACKAGE_ID
        new_page = handle_hidden_buttons(new_page, this_page)

        return redirect(url_for(new_page, filename=filename))

    # Process GET
    data_package_id = eml_node.attribute_value('packageId')
    form.data_package_id.data = data_package_id if data_package_id else ''
    form.md5.data = form_md5(form)

    set_current_page('data_package_id')
    help = get_helps(['data_package_id'])
    return render_template('data_package_id.html', form=form, help=help, title='Data Package ID')


@res_bp.route('/publication_info/<filename>', methods=['GET', 'POST'])
@login_required
def publication_info(filename=None):
    form = PublicationInfoForm()

    # Process POST
    # if request.method == 'POST' and form.validate_on_submit():
    if request.method == 'POST':

        new_page = PAGE_METHOD_STEP_SELECT
        this_page = PAGE_PUBLICATION_INFO
        new_page = handle_hidden_buttons(new_page, this_page)

        save = False
        if is_dirty_form(form):
            save = True

        if save:
            pubplace = form.pubplace.data
            pubdate = form.pubdate.data
            create_pubinfo(pubplace=pubplace, pubdate=pubdate, filename=filename)

        return redirect(url_for(new_page, filename=filename))

    # Process GET
    eml_node = load_eml(filename=filename)
    pubplace_node = eml_node.find_single_node_by_path([names.DATASET, names.PUBPLACE])
    if pubplace_node:
        form.pubplace.data = pubplace_node.content
    pubdate_node = eml_node.find_single_node_by_path([names.DATASET, names.PUBDATE])
    if pubdate_node:
        form.pubdate.data = pubdate_node.content
    form.md5.data = form_md5(form)
    set_current_page('publication_info')
    help = get_helps(['pubplace', 'pubdate'])
    return render_template('publication_info.html', help=help, form=form, title='Publication Info')


@res_bp.route('/abstract/<filename>', methods=['GET', 'POST'])
@login_required
def abstract(filename=None):
    form = AbstractForm(filename=filename)

    # Process POST
    if request.method == 'POST':

        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        if form_dict:
            if 'Reset' in form_dict:
                # User has elected to reset to last valid saved state
                return get_abstract(filename, form)

        new_page = PAGE_KEYWORD_SELECT
        this_page = PAGE_ABSTRACT
        new_page = handle_hidden_buttons(new_page, this_page)

        if form.validate_on_submit():
            if is_dirty_form(form):
                abstract = form.abstract.data
                valid, msg = is_valid_xml_fragment(abstract, names.ABSTRACT)
                if valid:
                    create_abstract(filename=filename, abstract=abstract)
                    return redirect(url_for(new_page, filename=filename))
                else:
                    flash(invalid_xml_error_message(msg), 'error')
                    return render_get_abstract_page(form, filename)
            else:
                return redirect(url_for(new_page, filename=filename))

    # Process GET
    return get_abstract(filename, form)


def render_get_abstract_page(form, filename):
    eml_node=load_eml(filename)
    form.md5.data = form_md5(form)
    set_current_page('abstract')
    help = [get_help('abstract'), get_help('nav')]
    return render_template('abstract.html',
                           title='Abstract', model_has_complex_texttypes=model_has_complex_texttypes(eml_node),
                           filename=filename, form=form, help=help)


def get_abstract(filename, form):
    # Process GET
    eml_node = load_eml(filename=filename)
    abstract_node = eml_node.find_single_node_by_path([
        names.DATASET,
        names.ABSTRACT
    ])
    if abstract_node:
        try:
            form.abstract.data = display_texttype_node(abstract_node)
        except InvalidXMLError as exc:
            flash('The XML is invalid. Please make corrections.', 'error')
    return render_get_abstract_page(form, filename)


@res_bp.route('/intellectual_rights/<filename>', methods=['GET', 'POST'])
@login_required
def intellectual_rights(filename=None):
    form = IntellectualRightsForm(filename=filename)

    # Process POST
    if request.method == 'POST' and form.validate_on_submit():

        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        if form_dict:
            if 'Reset' in form_dict:
                # User has elected to reset to last valid saved state
                return get_intellectual_rights(filename, form)

        submit_type = None
        if is_dirty_form(form):
            submit_type = 'Save Changes'

        if submit_type == 'Save Changes':
            if form.intellectual_rights_radio.data == 'CC0':
                intellectual_rights = INTELLECTUAL_RIGHTS_CC0
            elif form.intellectual_rights_radio.data == 'CCBY':
                intellectual_rights = INTELLECTUAL_RIGHTS_CC_BY
            else:
                intellectual_rights = form.intellectual_rights.data

            valid, msg = is_valid_xml_fragment(intellectual_rights, names.INTELLECTUALRIGHTS)
            if valid:
                create_intellectual_rights(filename=filename, intellectual_rights=intellectual_rights)
            else:
                flash(invalid_xml_error_message(msg), 'error')
                form.intellectual_rights.data = intellectual_rights
                # We don't have valid XML, so we can't look for literal descendant nodes
                font_family = ''
                return render_get_intellectual_rights_page(form, filename, font_family)

        new_page = PAGE_GEOGRAPHIC_COVERAGE_SELECT
        this_page = PAGE_INTELLECTUAL_RIGHTS
        new_page = handle_hidden_buttons(new_page, this_page)

        return redirect(url_for(new_page, filename=filename))

    # Process GET
    return get_intellectual_rights(filename=filename, form=form)


def render_get_intellectual_rights_page(form, filename, font_family):
    eml_node=load_eml(filename)
    form.md5.data = form_md5(form)
    set_current_page('intellectual_rights')
    help = [get_help('intellectual_rights')]

    return render_template('intellectual_rights.html',
                           title='Intellectual Rights', font_family=font_family,
                           model_has_complex_texttypes=model_has_complex_texttypes(eml_node),
                           filename=filename, form=form, help=help)


def get_intellectual_rights(filename, form):
    eml_node = load_eml(filename=filename)
    intellectual_rights_node = eml_node.find_single_node_by_path([
        names.DATASET,
        names.INTELLECTUALRIGHTS
    ])
    if intellectual_rights_node:
        ir_content = display_texttype_node(intellectual_rights_node)
        if INTELLECTUAL_RIGHTS_CC0 in ir_content:
            form.intellectual_rights_radio.data = 'CC0'
            form.intellectual_rights.data = ''
        elif INTELLECTUAL_RIGHTS_CC_BY in ir_content:
            form.intellectual_rights_radio.data = 'CCBY'
            form.intellectual_rights.data = ''
        else:
            form.intellectual_rights_radio.data = "Other"
            form.intellectual_rights.data = display_texttype_node(intellectual_rights_node)

    font_family = 'Courier' if node_has_literal_children(intellectual_rights_node) else ''

    return render_get_intellectual_rights_page(filename=filename, form=form, font_family=font_family)


def populate_keyword_form(form: KeywordForm, kw_node: Node, keyword_thesaurus_node: Node):
    keyword = ''
    keyword_type = ''
    keyword_thesaurus = ''

    if kw_node:
        keyword = kw_node.content if kw_node.content else ''
        kw_type = kw_node.attribute_value('keywordType')
        keyword_type = kw_type if kw_type else ''

    if keyword_thesaurus_node:
        keyword_thesaurus = keyword_thesaurus_node.content

    form.keyword.data = keyword
    form.keyword_thesaurus.data = keyword_thesaurus
    form.keyword_type.data = keyword_type
    form.md5.data = form_md5(form)


@res_bp.route('/keyword_select/<filename>', methods=['GET', 'POST'])
@login_required
def keyword_select(filename=None):
    form = KeywordSelectForm(filename=filename)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = keyword_select_post(filename, form, form_dict,
                                  'POST', PAGE_KEYWORD_SELECT, PAGE_ABSTRACT,
                                  PAGE_INTELLECTUAL_RIGHTS, PAGE_KEYWORD)
        return redirect(url)

    # Process GET
    return keyword_select_get(filename=filename, form=form)


def keyword_select_get(filename=None, form=None):
    # Process GET
    kw_list = []
    title = 'Keywords'
    eml_node = load_eml(filename=filename)

    if eml_node:
        kw_list = list_keywords(eml_node)

    set_current_page('keyword')
    help = [get_help('keywords')]
    return render_template('keyword_select.html', title=title,
                           filename=filename,
                           kw_list=kw_list,
                           form=form, help=help)


def keyword_select_post(filename=None, form=None, form_dict=None,
                        method=None, this_page=None, back_page=None,
                        next_page=None, edit_page=None):
    node_id = ''
    new_page = None
    if form_dict:
        for key in form_dict:
            val = form_dict[key][0]  # value is the first list element
            if val == BTN_BACK:
                new_page = back_page
            elif val == BTN_NEXT or val == BTN_SAVE_AND_CONTINUE:
                new_page = next_page
            elif val == BTN_EDIT:
                new_page = edit_page
                node_id = key
            elif val == BTN_REMOVE:
                new_page = this_page
                node_id = key
                remove_keyword(filename, node_id)
            elif val == UP_ARROW:
                new_page = this_page
                node_id = key
                process_up_button(filename, node_id)
            elif val == DOWN_ARROW:
                new_page = this_page
                node_id = key
                process_down_button(filename, node_id)
            elif val[0:3] == BTN_ADD:
                new_page = edit_page
                node_id = '1'
            new_page = check_val_for_hidden_buttons(val, new_page, this_page)

    if form.validate_on_submit():
        if new_page == edit_page:
            return url_for(new_page,
                           filename=filename,
                           node_id=node_id)
        else:
            return url_for(new_page,
                           filename=filename)


def remove_keyword(filename, node_id):
    eml_node = load_eml(filename=filename)

    if node_id:
        keyword_node = Node.get_node_instance(node_id)
        if keyword_node:
            keyword_set_node = keyword_node.parent
        remove_child(node_id=node_id)
        # if we've just removed the last keyword under the keywordSet, remove the keywordSet
        if not keyword_set_node.find_all_children(names.KEYWORD):
            parent_node = keyword_set_node.parent
            parent_node.remove_child(keyword_set_node)
        save_both_formats(filename=filename, eml_node=eml_node)


# node_id is the id of the keyword node being edited. If the value is
# '1', it means we are adding a new keyword node, otherwise we are
# editing an existing one.
#
@res_bp.route('/keyword/<filename>/<node_id>', methods=['GET', 'POST'])
@login_required
def keyword(filename=None, node_id=None):
    eml_node = load_eml(filename=filename)
    dataset_node = eml_node.find_child(names.DATASET)

    if not dataset_node:
        dataset_node = Node(names.DATASET, parent=eml_node)
        add_child(eml_node, dataset_node)

    form = KeywordForm(filename=filename, node_id=node_id)
    form.init_keywords()

    # Process POST
    if request.method == 'POST' and BTN_CANCEL in request.form:
            url = url_for(PAGE_KEYWORD_SELECT, filename=filename)
            return redirect(url)

    # if request.method == 'POST' and form.validate_on_submit():
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        new_page = PAGE_KEYWORD_SELECT
        if form_dict:
            for key in form_dict:
                val = form_dict[key][0]  # value is the first list element
                new_page = check_val_for_hidden_buttons(val, new_page, new_page)

        submit_type = None
        if is_dirty_form(form):
            submit_type = 'Save Changes'
        # flash(f'submit_type: {submit_type}')

        if submit_type == 'Save Changes':
            keyword = form.keyword.data
            keyword_type = form.keyword_type.data
            keyword_thesaurus = form.keyword_thesaurus.data

            # If no thesaurus was specified, see if the LTER Controlled Vocabulary applies
            if not keyword_thesaurus:
                lter_keywords = get_keywords('LTER')
                if keyword in lter_keywords:
                    keyword_thesaurus = 'LTER Controlled Vocabulary'

            keyword_set_nodes = []
            eml_node.find_all_descendants(names.KEYWORDSET, keyword_set_nodes)

            keyword_set_node = None
            for kws_node in keyword_set_nodes:
                keyword_thesaurus_node = kws_node.find_child(names.KEYWORDTHESAURUS)
                if keyword_thesaurus_node and keyword_thesaurus_node.content == keyword_thesaurus:
                    keyword_set_node = kws_node
                    break
                if not keyword_thesaurus_node and not keyword_thesaurus:
                    keyword_set_node = kws_node
                    break
            if not keyword_set_node:
                keyword_set_node = Node(names.KEYWORDSET, parent=dataset_node)
                add_child(dataset_node, keyword_set_node)
                if keyword_thesaurus:
                    keyword_thesaurus_node = Node(names.KEYWORDTHESAURUS, parent=keyword_set_node)
                    keyword_thesaurus_node.content = keyword_thesaurus
                    keyword_set_node.add_child(keyword_thesaurus_node, index=-1)

            keyword_node = Node(names.KEYWORD, parent=keyword_set_node)
            create_keyword(keyword_node, keyword, keyword_type)

            keyword_set_node.add_child(keyword_node, index=-1)

            if node_id and len(node_id) != 1:
                old_keyword_node = Node.get_node_instance(node_id)

                if old_keyword_node:
                    old_keyword_set_node = old_keyword_node.parent
                    old_keyword_set_node.remove_child(old_keyword_node)
                    # If we just removed the last keyword from a keyword set, remove the keyword set
                    if not old_keyword_set_node.children:
                        old_keyword_set_node.parent.remove_child(old_keyword_set_node)
                else:
                    msg = f"No keyword node found in the node store with node id {node_id}"
                    raise Exception(msg)

            save_both_formats(filename=filename, eml_node=eml_node)

        url = url_for(new_page, filename=filename)
        return redirect(url)

    # Process GET
    if node_id == '1':
        form.init_md5()
    else:
        keyword_set_nodes = []
        eml_node.find_all_descendants(names.KEYWORDSET, keyword_set_nodes)
        found = False
        for keyword_set_node in keyword_set_nodes:
            keyword_nodes = keyword_set_node.find_all_children(names.KEYWORD)
            keyword_thesaurus_node = keyword_set_node.find_child(names.KEYWORDTHESAURUS)
            if keyword_nodes:
                for kw_node in keyword_nodes:
                    if node_id == kw_node.id:
                        populate_keyword_form(form, kw_node, keyword_thesaurus_node)
                        found = True
                        break
            if found:
                break

    set_current_page('keyword')
    help = [get_help('keywords')]
    return render_template('keyword.html', title='Keyword', form=form, filename=filename, help=help)
