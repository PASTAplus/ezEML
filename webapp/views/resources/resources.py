import os
from flask import (
    Blueprint, flash, redirect, request, url_for
)
from flask_login import (
    current_user, login_required
)

from webapp.auth.user_data import (
    is_first_usage, set_active_packageid, set_active_document
)
from webapp.home.utils.render_page import render_page
from webapp.home.utils.node_utils import remove_child, add_child
from webapp.home.utils.node_store import dump_node_store
from webapp.home.utils.load_and_save import load_eml, save_both_formats
from webapp.home.utils.lists import UP_ARROW, DOWN_ARROW, list_keywords
from webapp.home.utils.create_nodes import create_title, create_data_package_id, create_pubinfo, create_abstract, \
    create_intellectual_rights, create_keyword
from webapp.home.utils.hidden_buttons import (
	handle_hidden_buttons, check_val_for_hidden_buttons, non_saving_hidden_buttons_decorator
)

from webapp.home.forms import is_dirty_form, init_form_md5
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

from webapp.buttons import (
    BTN_BACK, BTN_NEXT, BTN_SAVE_AND_CONTINUE, BTN_EDIT, BTN_REMOVE, BTN_CANCEL, BTN_ADD, BTN_IMPORT
)
from webapp.pages import (
    PAGE_INDEX, PAGE_DATA_TABLE_SELECT, PAGE_CHECK_METADATA, PAGE_METHOD_STEP_SELECT,
    PAGE_KEYWORD_SELECT, PAGE_ABSTRACT, PAGE_INTELLECTUAL_RIGHTS, PAGE_KEYWORD, PAGE_IMPORT_KEYWORDS,
    PAGE_GEOGRAPHIC_COVERAGE_SELECT
)
from webapp.home.exceptions import InvalidXMLError, NodeWithGivenIdNotFound

from webapp.home.views import process_up_button, process_down_button
from metapype.eml import names
from metapype.model.node import Node
from webapp.config import Config

from webapp.home.intellectual_rights import (
    INTELLECTUAL_RIGHTS_CC0, INTELLECTUAL_RIGHTS_CC_BY
)

from webapp.home.views import get_keywords
from webapp.home.home_utils import log_error, log_info

res_bp = Blueprint('res', __name__, template_folder='templates')


@res_bp.route('/title/<filename>', methods=['GET', 'POST'])
@login_required
def title(filename):
    """Handle the page for the Title item in the Contents menu."""

    # Log info that helps us see who's currently using ezEML. Title is a page that's frequently visited.
    user_name = current_user.get_username()
    current_packageid = current_user.get_filename()
    pid = os.getpid() # OS process ID for logging/debugging. Not to be confused with PASTA package ID.

    metapype_store = ''
    if Config.MEM_LOG_METAPYPE_STORE_ACTIONS:
        metapype_store_size = len(Node.store)
        metapype_store = f', metapype_store_size={metapype_store_size}'

    log_info(
        f'Title    PID={pid}, user={user_name}, package={current_packageid}{metapype_store}'
    )

    form = TitleForm()

    # POST
    if form.validate_on_submit():
        # If the form is dirty, then save the data.
        if is_dirty_form(form):
            create_title(title=form.title.data, filename=filename)

        next_page = handle_hidden_buttons(PAGE_DATA_TABLE_SELECT)
        return redirect(url_for(next_page, filename=filename))

    # GET
    eml_node = load_eml(filename=filename)
    if not eml_node:
        # This can happen if the user enters a URL directly into the browser, and the URL is for a package that
        #  doesn't exist or the URL is of the form https://ezeml.edirepository.org/title/ -- i.e., no filename given.
        log_error(f'No EML node found for filename={filename}')
        set_active_document(None)
        return redirect(url_for(PAGE_INDEX))

    dataset_node = eml_node.find_child(child_name=names.DATASET)
    title_node = dataset_node.find_child(names.TITLE) if dataset_node else None

    if title_node:
        form.title.data = title_node.content

    first_usage = is_first_usage()  # If this is the first time the user has used ezEML, we'll show the welcome popup.

    return render_page(
        "title.html",
        filename=filename,
        form=form,
        tooltip_section="title",
        current_page_key="title",
        help_keys=["title", "nav", "welcome"],
        eml_node=eml_node,
        title="Title",
        is_first_usage=first_usage,
    )


@res_bp.route('/data_package_id/<filename>', methods=['GET', 'POST'])
@login_required
def data_package_id(filename):
    """Handle the page for the Data Package ID item in the Contents menu."""

    form = DataPackageIDForm()

    # POST
    if form.validate_on_submit():

        # If the form is dirty, then save the data.
        if is_dirty_form(form):
            data_package_id = form.data_package_id.data
            create_data_package_id(data_package_id, filename)
            set_active_packageid(data_package_id)

        next_page = handle_hidden_buttons(PAGE_CHECK_METADATA)
        return redirect(url_for(next_page, filename=filename))

    # GET
    eml_node = load_eml(filename=filename)
    # Populate the form values
    data_package_id = eml_node.attribute_value('packageId')
    form.data_package_id.data = data_package_id if data_package_id else ''

    return render_page(
        "data_package_id.html",
        filename=filename,
        form=form,
        tooltip_section="data_package_id",
        current_page_key="data_package_id",
        help_keys=['data_package_id'],
        eml_node=eml_node,
        title="Data Package ID"
    )


@res_bp.route('/publication_info/<filename>', methods=['GET', 'POST'])
@login_required
def publication_info(filename):
    """Handle the page for the Publication Info item in the Contents menu."""

    form = PublicationInfoForm()

    # POST
    if form.validate_on_submit():

        # If the form is dirty, then save the data.
        if is_dirty_form(form):
            pubplace = form.pubplace.data
            pubdate = form.pubdate.data
            create_pubinfo(pubplace=pubplace, pubdate=pubdate, filename=filename)

        next_page = handle_hidden_buttons(PAGE_METHOD_STEP_SELECT)
        return redirect(url_for(next_page, filename=filename))

    # Process GET
    eml_node = load_eml(filename=filename)
    # Populate the form values
    pubplace_node = eml_node.find_single_node_by_path([names.DATASET, names.PUBPLACE])
    if pubplace_node:
        form.pubplace.data = pubplace_node.content
    pubdate_node = eml_node.find_single_node_by_path([names.DATASET, names.PUBDATE])
    if pubdate_node:
        form.pubdate.data = pubdate_node.content

    return render_page(
        "publication_info.html",
        filename=filename,
        form=form,
        tooltip_section="publication_info",
        current_page_key="publication_info",
        help_keys=['pubplace', 'pubdate'],
        eml_node=eml_node,
        title="Publication Info"
    )


@res_bp.route('/abstract/<filename>', methods=['GET', 'POST'])
@login_required
def abstract(filename):
    """Handle the page for the Abstract item in the Contents menu."""

    form = AbstractForm(filename=filename)

    # POST
    if form.validate_on_submit():
        if 'Reset' in request.form:
            # User has elected to reset to last valid saved state
            return get_abstract(filename, form)

        # Decide which page to go to next: the next page in the sequence, unless the user clicked on a hidden button.
        new_page = handle_hidden_buttons(PAGE_KEYWORD_SELECT)

        # If the form is dirty, then save the data.
        abstract = form.abstract.data
        # We do this before checking is_dirty because is_valid_xml_fragment may change the form data (e.g.,
        #  replacing \r\n with \n) and the initial md5 hash will have been applied to that modified data.
        valid, msg = is_valid_xml_fragment(abstract, names.ABSTRACT)
        if not valid:
            flash(invalid_xml_error_message(msg), 'error')
            return render_get_abstract_page(form, filename)

        if is_dirty_form(form):
            create_abstract(filename=filename, abstract=abstract)

        return redirect(url_for(new_page, filename=filename))

    # GET
    return get_abstract(filename, form)


def render_get_abstract_page(form, filename):
    eml_node=load_eml(filename)

    return render_page(
        "abstract.html",
        filename=filename,
        form=form,
        tooltip_section="abstract",
        current_page_key="abstract",
        help_keys=['abstract', 'nav'],
        eml_node=eml_node,
        title="Abstract",
        model_has_complex_texttypes=model_has_complex_texttypes(eml_node)
    )


def get_abstract(filename, form):
    # GET
    eml_node = load_eml(filename=filename)
    abstract_node = eml_node.find_single_node_by_path([
        names.DATASET,
        names.ABSTRACT
    ])
    if abstract_node:
        try:
            form.abstract.data = display_texttype_node(abstract_node)
        except InvalidXMLError:
            flash('The XML is invalid. Please make corrections.', 'error')

    return render_get_abstract_page(form, filename)


@res_bp.route('/intellectual_rights/<filename>', methods=['GET', 'POST'])
@login_required
def intellectual_rights(filename):
    """Handle the page for the Intellectual Rights item in the Contents menu."""

    form = IntellectualRightsForm(filename=filename)

    # POST
    if form.validate_on_submit():

        if 'Reset' in request.form:
            # User has elected to reset to last valid saved state
            return get_intellectual_rights(filename, form)

        # If the form is dirty, then save the data.
        if is_dirty_form(form):
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

        # Decide which page to go to next: the next page in the sequence, unless the user clicked on a hidden button.
        new_page = handle_hidden_buttons(PAGE_GEOGRAPHIC_COVERAGE_SELECT)

        return redirect(url_for(new_page, filename=filename))

    # GET
    return get_intellectual_rights(filename=filename, form=form)


def render_get_intellectual_rights_page(form, filename, font_family):
    eml_node=load_eml(filename)

    return render_page(
        "intellectual_rights.html",
        filename=filename,
        form=form,
        tooltip_section="intellectual_rights",
        current_page_key="intellectual_rights",
        help_keys=['intellectual_rights'],
        eml_node=eml_node,
        title="Intellectual Rights",
        font_family=font_family,
        model_has_complex_texttypes=model_has_complex_texttypes(eml_node)
    )


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
    init_form_md5(form)


@res_bp.route('/keyword_select/<filename>', methods=['GET', 'POST'])
@login_required
@non_saving_hidden_buttons_decorator
def keyword_select(filename):
    """Handle the page for the Keywords item in the Contents menu. It allows selection of a keyword from the list."""

    form = KeywordSelectForm(filename=filename)

    # POST
    if form.validate_on_submit():

        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        # Decide which page to go to next depending on the button clicked.
        url = keyword_select_post(
            filename, form, form_dict,
            this_page=PAGE_KEYWORD_SELECT,
            back_page=PAGE_ABSTRACT,
            next_page=PAGE_INTELLECTUAL_RIGHTS,
            edit_page=PAGE_KEYWORD,
            import_page=PAGE_IMPORT_KEYWORDS,
        )
        return redirect(url)

    # GET
    return keyword_select_get(filename=filename, form=form)


def keyword_select_get(filename=None, form=None):
    """Render the page with the list of keywords."""

    kw_list = []
    eml_node = load_eml(filename=filename)
    if eml_node:
        kw_list = list_keywords(eml_node)

    return render_page(
        "keyword_select.html",
        filename=filename,
        form=form,
        tooltip_section="keyword",
        current_page_key="keyword",
        help_keys=['keywords'],
        eml_node=eml_node,
        title="Keywords",
        kw_list=kw_list
    )


def keyword_select_post(filename, form, form_dict,
                        this_page, back_page, next_page, edit_page, import_page):
    node_id = None
    new_page = None

    # Decide action based on which button was clicked
    if form_dict:
        for key, values in form_dict.items():
            val = values[0]

            if val == BTN_BACK:
                new_page = back_page
            elif val in (BTN_NEXT, BTN_SAVE_AND_CONTINUE):
                new_page = next_page
            elif val == BTN_EDIT:
                new_page = edit_page
                node_id = key
            elif val == BTN_REMOVE:
                remove_keyword(filename, key)
                new_page = this_page
            elif val == UP_ARROW:
                process_up_button(filename, key)
                new_page = this_page
            elif val == DOWN_ARROW:
                process_down_button(filename, key)
                new_page = this_page
            elif val.startswith(BTN_ADD):
                # convention: node_id == '1' means add new
                new_page = edit_page
                node_id = '1'
            elif val.startswith(BTN_IMPORT):
                new_page = import_page

            new_page = check_val_for_hidden_buttons(val, new_page)
            if new_page:
                break

    # Note: keyword_select_post is called from a validate_on_submit() block, so we may assume the form is valid.

    # Build the final URL
    if new_page == edit_page:
        return url_for(new_page, filename=filename, node_id=node_id or '1')

    return url_for(new_page or this_page, filename=filename)


def remove_keyword(filename, node_id):
    eml_node = load_eml(filename=filename)
    if not node_id:
        return

    keyword_node = Node.get_node_instance(node_id)
    if not keyword_node:
        log_error(f"remove_keyword: no node found for id={node_id}")
        return

    keyword_set_node = keyword_node.parent
    remove_child(keyword_node)

    # If we removed the last keyword under keywordSet, remove keywordSet too
    if keyword_set_node and not keyword_set_node.find_all_children(names.KEYWORD):
        remove_child(keyword_set_node)

    save_both_formats(filename=filename, eml_node=eml_node)


# node_id is the id of the keyword node being edited. If the value is
# '1', it means we are adding a new keyword node, otherwise we are
# editing an existing one.
@res_bp.route('/keyword/<filename>/<node_id>', methods=['GET', 'POST'])
@login_required
def keyword(filename, node_id):
    """Handle the page for adding/editing a particular Keyword. We come here when Edit is clicked for a keyword in the
    list of keywords, or when Add Keyword is clicked to add a new keyword."""

    eml_node = load_eml(filename=filename)
    dataset_node = eml_node.find_child(names.DATASET)

    if not dataset_node:
        dataset_node = Node(names.DATASET, parent=eml_node)
        add_child(eml_node, dataset_node)

    form = KeywordForm(filename=filename, node_id=node_id)
    form.init_keywords()

    # POST
    if request.method == "POST" and BTN_CANCEL in request.form:
        # Cancel has been clicked so go back to the Keyword Select page
        url = url_for(PAGE_KEYWORD_SELECT, filename=filename)
        return redirect(url)

    if form.validate_on_submit():
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        new_page = PAGE_KEYWORD_SELECT
        if form_dict:
            for key in form_dict:
                val = form_dict[key][0]  # value is the first list element
                new_page = check_val_for_hidden_buttons(val, new_page)

        if is_dirty_form(form):
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
                    keyword_thesaurus_node.nsmap = keyword_set_node.nsmap
                    keyword_set_node.add_child(keyword_thesaurus_node, index=-1)

            keyword_node = Node(names.KEYWORD, parent=keyword_set_node)
            create_keyword(keyword_node, keyword, keyword_type)

            keyword_node.nsmap = keyword_set_node.nsmap
            keyword_set_node.add_child(keyword_node, index=-1)

            if node_id and len(node_id) != 1:
                old_keyword_node = Node.get_node_instance(node_id)

                if old_keyword_node:
                    old_keyword_set_node = old_keyword_node.parent
                    remove_child(old_keyword_node)
                    # If we just removed the last keyword from a keyword set, remove the keyword set
                    if not old_keyword_set_node.children:
                        remove_child(old_keyword_set_node)
                else:
                    msg = f"No node found in the node store with node id {node_id}"
                    dump_node_store(eml_node, 'keyword')
                    raise NodeWithGivenIdNotFound(msg)

            save_both_formats(filename=filename, eml_node=eml_node)

        url = url_for(new_page, filename=filename)
        return redirect(url)

    # GET
    if node_id != '1':
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

    return render_page(
        "keyword.html",
        filename=filename,
        form=form,
        tooltip_section="keyword",
        current_page_key="keyword",
        help_keys=['keywords'],
        eml_node=eml_node,
        title="Keyword",
    )
