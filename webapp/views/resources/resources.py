from flask import (
    Blueprint, flash, render_template, redirect, request, url_for
)

from webapp.home.metapype_client import (
    add_child, create_abstract, create_intellectual_rights,
    create_keyword, create_pubdate, create_pubplace,
    create_title, list_keywords, load_eml, remove_child,
    save_both_formats, DOWN_ARROW, UP_ARROW,
    add_paragraph_tags, remove_paragraph_tags
)

from webapp.home.forms import is_dirty_form, form_md5
from webapp.views.resources.forms import (
    AbstractForm,
    IntellectualRightsForm,
    KeywordForm,
    KeywordSelectForm,
    PubDateForm,
    PublicationPlaceForm,
    TitleForm
)

from webapp.buttons import *
from webapp.pages import *

from webapp.home.views import process_up_button, process_down_button, get_help
from metapype.eml import names
from metapype.model.node import Node

from webapp.home.intellectual_rights import (
    INTELLECTUAL_RIGHTS_CC0, INTELLECTUAL_RIGHTS_CC_BY
)

from webapp.home.views import set_current_page


res_bp = Blueprint('res', __name__, template_folder='templates')


@res_bp.route('/title/<packageid>', methods=['GET', 'POST'])
def title(packageid=None):
    form = TitleForm()

    # Process POST
    if request.method == 'POST' and form.validate_on_submit():
        new_page = PAGE_CREATOR_SELECT
        save = False
        if is_dirty_form(form):
            save = True
        # flash(f'save: {save}')

        if save:
            title_node = create_title(title=form.title.data, packageid=packageid)
            form.md5.data = form_md5(form)

        current_page = 'title'
        if 'Next' in request.form:
            new_page = PAGE_CREATOR_SELECT
            current_page = 'creators'
        elif 'Hidden_Save' in request.form:
            new_page = PAGE_TITLE
        elif 'Hidden_Download' in request.form:
            new_page = PAGE_DOWNLOAD

        return redirect(url_for(new_page, packageid=packageid))

    # Process GET
    eml_node = load_eml(packageid=packageid)
    dataset_node = eml_node.find_immediate_child(child_name=names.DATASET)
    title_node = dataset_node.find_immediate_child(names.TITLE)
    if title_node:
        form.title.data = title_node.content
    form.md5.data = form_md5(form)

    set_current_page('title')
    help = [get_help('title'), get_help('nav')]
    return render_template('title.html', title='Title', form=form, help=help)


@res_bp.route('/publication_place/<packageid>', methods=['GET', 'POST'])
def publication_place(packageid=None):
    form = PublicationPlaceForm()

    # Process POST
    if request.method == 'POST' and form.validate_on_submit():
        if 'Next' in request.form:
            new_page = PAGE_METHOD_STEP_SELECT
        elif 'Hidden_Save' in request.form:
            new_page = PAGE_PUBLICATION_PLACE
        elif 'Hidden_Download' in request.form:
            new_page = PAGE_DOWNLOAD
        else:
            new_page = PAGE_PUBLISHER

        save = False
        if is_dirty_form(form):
            save = True
        # flash(f'save: {save}')

        if save:
            pubplace = form.pubplace.data
            pubplace_node = create_pubplace(pubplace=pubplace, packageid=packageid)

        return redirect(url_for(new_page, packageid=packageid))

    # Process GET
    eml_node = load_eml(packageid=packageid)
    pubplace_node = eml_node.find_immediate_child(child_name='pubPlace')
    if pubplace_node:
        form.pubplace.data = pubplace_node.content
    form.md5.data = form_md5(form)
    set_current_page('publication_place')
    help = [get_help('pubplace')]
    return render_template('publication_place.html', title='Publication Place', form=form, help=help)


@res_bp.route('/pubdate/<packageid>', methods=['GET', 'POST'])
def pubdate(packageid=None):
    form = PubDateForm(packageid=packageid)

    # Process POST
    if request.method == 'POST' and form.validate_on_submit():
        if 'Back' in request.form:
            new_page = PAGE_ASSOCIATED_PARTY_SELECT
        elif 'Hidden_Save' in request.form:
            new_page = PAGE_PUBDATE
        elif 'Hidden_Download' in request.form:
            new_page = PAGE_DOWNLOAD
        elif 'Next' in request.form:
            new_page = PAGE_ABSTRACT

        save = False
        if is_dirty_form(form):
            save = True
        # flash(f'save: {save}')

        if save:
            pubdate = form.pubdate.data
            create_pubdate(packageid=packageid, pubdate=pubdate)

        return redirect(url_for(new_page, packageid=packageid))

    # Process GET
    eml_node = load_eml(packageid=packageid)
    pubdate_node = eml_node.find_immediate_child(child_name=names.PUBDATE)
    if pubdate_node:
        form.pubdate.data = pubdate_node.content
    form.md5.data = form_md5(form)

    set_current_page('pubdate')
    help = [get_help('pubdate'), get_help('nav')]
    return render_template('pubdate.html',
                           title='Publication Date',
                           packageid=packageid, form=form, help=help)


@res_bp.route('/abstract/<packageid>', methods=['GET', 'POST'])
def abstract(packageid=None):
    form = AbstractForm(packageid=packageid)

    # Process POST
    if request.method == 'POST':
        if 'Back' in request.form:
            submit_type = 'Back'
            new_page = PAGE_PUBDATE
        elif 'Next' in request.form:
            submit_type = 'Next'
            new_page = PAGE_KEYWORD_SELECT
        elif 'Hidden_Save' in request.form:
            submit_type = 'Save'
            new_page = PAGE_ABSTRACT
        elif 'Hidden_Download' in request.form:
            submit_type = 'Save'
            new_page = PAGE_DOWNLOAD
        else:
            submit_type = None
            new_page = PAGE_KEYWORD_SELECT

        if form.validate_on_submit():
            if is_dirty_form(form):
                abstract = add_paragraph_tags(form.abstract.data)
                create_abstract(packageid=packageid, abstract=abstract)
                # flash(f"is_dirty_form: True")
            else:
                # flash(f"is_dirty_form: False")
                pass
            # new_page = PAGE_PUBDATE if (submit_type == 'Back') else PAGE_KEYWORD_SELECT
            return redirect(url_for(new_page, packageid=packageid))

    # Process GET
    eml_node = load_eml(packageid=packageid)
    abstract_node = eml_node.find_immediate_child(child_name=names.ABSTRACT)
    if abstract_node:
        form.abstract.data = remove_paragraph_tags(abstract_node.content)
    form.md5.data = form_md5(form)
    set_current_page('abstract')
    help = [get_help('abstract'), get_help('nav')]
    return render_template('abstract.html',
                           title='Abstract',
                           packageid=packageid, form=form, help=help)


@res_bp.route('/intellectual_rights/<packageid>', methods=['GET', 'POST'])
def intellectual_rights(packageid=None):
    form = IntellectualRightsForm(packageid=packageid)

    # Process POST
    if request.method == 'POST' and form.validate_on_submit():
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

            create_intellectual_rights(packageid=packageid, intellectual_rights=intellectual_rights)

        if 'Back' in request.form:
            new_page = PAGE_KEYWORD_SELECT
        elif 'Hidden_Save' in request.form:
            new_page = PAGE_PUBLICATION_PLACE
        elif 'Hidden_Download' in request.form:
            new_page = PAGE_DOWNLOAD
        else:
            new_page = PAGE_GEOGRAPHIC_COVERAGE_SELECT

        return redirect(url_for(new_page, packageid=packageid))

    # Process GET
    eml_node = load_eml(packageid=packageid)
    intellectual_rights_node = eml_node.find_single_node_by_path([
        names.DATASET,
        names.INTELLECTUALRIGHTS
    ])
    if intellectual_rights_node:
        ir_content = intellectual_rights_node.content
        if ir_content == INTELLECTUAL_RIGHTS_CC0:
            form.intellectual_rights_radio.data = 'CC0'
            form.intellectual_rights.data = ''
        elif ir_content == INTELLECTUAL_RIGHTS_CC_BY:
            form.intellectual_rights_radio.data = 'CCBY'
            form.intellectual_rights.data = ''
        else:
            form.intellectual_rights_radio.data = "Other"
            form.intellectual_rights.data = intellectual_rights_node.content

    form.md5.data = form_md5(form)

    set_current_page('intellectual_rights')
    help = [get_help('intellectual_rights')]
    return render_template('intellectual_rights.html',
                           title='Intellectual Rights',
                           packageid=packageid, form=form, help=help)


def populate_keyword_form(form: KeywordForm, kw_node: Node):
    keyword = ''
    keyword_type = ''

    if kw_node:
        keyword = kw_node.content if kw_node.content else ''
        kw_type = kw_node.attribute_value('keywordType')
        keyword_type = kw_type if kw_type else ''

    form.keyword.data = keyword
    form.keyword_type.data = keyword_type
    form.md5.data = form_md5(form)


@res_bp.route('/keyword_select/<packageid>', methods=['GET', 'POST'])
def keyword_select(packageid=None):
    form = KeywordSelectForm(packageid=packageid)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = keyword_select_post(packageid, form, form_dict,
                                  'POST', PAGE_KEYWORD_SELECT, PAGE_ABSTRACT,
                                  PAGE_INTELLECTUAL_RIGHTS, PAGE_KEYWORD)
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

    set_current_page('keyword')
    help = [get_help('keywords')]
    return render_template('keyword_select.html', title=title,
                           packageid=packageid,
                           kw_list=kw_list,
                           form=form, help=help)


def keyword_select_post(packageid=None, form=None, form_dict=None,
                        method=None, this_page=None, back_page=None,
                        next_page=None, edit_page=None):
    node_id = ''
    new_page = ''
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
                eml_node = load_eml(packageid=packageid)
                remove_child(node_id=node_id)
                save_both_formats(packageid=packageid, eml_node=eml_node)
            elif val == BTN_HIDDEN_SAVE:
                new_page = this_page
            elif val == BTN_HIDDEN_DOWNLOAD:
                new_page = PAGE_DOWNLOAD
            elif val == UP_ARROW:
                new_page = this_page
                node_id = key
                process_up_button(packageid, node_id)
            elif val == DOWN_ARROW:
                new_page = this_page
                node_id = key
                process_down_button(packageid, node_id)
            elif val[0:3] == BTN_ADD:
                new_page = edit_page
                node_id = '1'

    if form.validate_on_submit():
        if new_page == edit_page:
            return url_for(new_page,
                           packageid=packageid,
                           node_id=node_id)
        else:
            return url_for(new_page,
                           packageid=packageid)


# node_id is the id of the keyword node being edited. If the value is
# '1', it means we are adding a new keyword node, otherwise we are
# editing an existing one.
#
@res_bp.route('/keyword/<packageid>/<node_id>', methods=['GET', 'POST'])
def keyword(packageid=None, node_id=None):
    eml_node = load_eml(packageid=packageid)
    dataset_node = eml_node.find_immediate_child(names.DATASET)

    if dataset_node:
        keyword_set_node = dataset_node.find_immediate_child(names.KEYWORDSET)
    else:
        dataset_node = Node(names.DATASET, parent=eml_node)
        add_child(eml_node, dataset_node)

    if not keyword_set_node:
        keyword_set_node = Node(names.KEYWORDSET, parent=dataset_node)
        add_child(dataset_node, keyword_set_node)

    form = KeywordForm(packageid=packageid, node_id=node_id)
    form.init_keywords()

    # Process POST
    if request.method == 'POST' and BTN_CANCEL in request.form:
            url = url_for(PAGE_KEYWORD_SELECT, packageid=packageid)
            return redirect(url)

    if request.method == 'POST' and form.validate_on_submit():
        next_page = PAGE_KEYWORD_SELECT  # Save or Back sends us back to the list of keywords

        submit_type = None
        if is_dirty_form(form):
            submit_type = 'Save Changes'
        # flash(f'submit_type: {submit_type}')

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
        form.init_md5()
    else:
        keyword_nodes = keyword_set_node.find_all_children(names.KEYWORD)
        if keyword_nodes:
            for kw_node in keyword_nodes:
                if node_id == kw_node.id:
                    populate_keyword_form(form, kw_node)
                    break

    set_current_page('keyword')
    help = [get_help('keywords')]
    return render_template('keyword.html', title='Keyword', form=form, packageid=packageid, help=help)
