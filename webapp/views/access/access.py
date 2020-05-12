from flask import (
    Blueprint, flash, render_template, redirect, request, url_for
)

from webapp.home.metapype_client import (
    load_eml, save_both_formats, add_child, remove_child, UP_ARROW, DOWN_ARROW,
    list_access_rules, create_access_rule
)
from webapp.home.forms import is_dirty_form, form_md5
from webapp.views.access.forms import AccessForm, AccessSelectForm

from metapype.eml_2_2_0 import names
from metapype.model.node import Node

from webapp.home.views import process_up_button, process_down_button
from webapp.buttons import *
from webapp.pages import *

acc_bp = Blueprint('acc', __name__, template_folder='templates')


@acc_bp.route('/access_select/<packageid>', methods=['GET', 'POST'])
def access_select(packageid=None, node_id=None):
    form = AccessSelectForm(packageid=packageid)

    # Process POST
    if request.method == 'POST':
        form_value = request.form
        form_dict = form_value.to_dict(flat=False)
        url = access_select_post(packageid, form, form_dict,
                                 'POST', PAGE_ACCESS_SELECT, PAGE_TITLE,
                                 PAGE_CREATOR_SELECT, PAGE_ACCESS)
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

    if form.validate_on_submit():
        if new_page == edit_page:
            return url_for(new_page,
                           packageid=packageid,
                           node_id=node_id)
        elif new_page == this_page:
            return url_for(new_page,
                           packageid=packageid,
                           node_id=node_id)
        elif new_page == back_page or new_page == next_page:
            return url_for(new_page,
                           packageid=packageid)


# node_id is the id of the access node being edited. If the value is
# '1', it means we are adding a new access node, otherwise we are
# editing an existing access node.
#
@acc_bp.route('/access/<packageid>/<node_id>', methods=['GET', 'POST'])
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
    # form = AccessForm()

    # Process POST
    if request.method == 'POST':
        if BTN_CANCEL in request.form:
            url = url_for(PAGE_ACCESS_SELECT, packageid=packageid)
            return redirect(url)

        next_page = PAGE_ACCESS_SELECT  # Save or Back sends us back to the list of access rules

        if form.validate_on_submit():
            if is_dirty_form(form):
                submit_type = 'Save Changes'
            else:
                submit_type = 'Back'

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

            flash(f"submit_type: {submit_type}")
            url = url_for(next_page, packageid=packageid)
            return redirect(url)

    # Process GET
    if node_id == '1':
        form.init_md5()
    else:
        allow_nodes = access_node.find_all_children(names.ALLOW)
        if allow_nodes:
            for allow_node in allow_nodes:
                if node_id == allow_node.id:
                    populate_access_rule_form(form, allow_node)
                    break

    return render_template('access.html', title='Access Rule', form=form, packageid=packageid)


def populate_access_rule_form(form: AccessForm, allow_node: Node):
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
        form.md5.data = form_md5(form)


