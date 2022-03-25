from flask import (
    Blueprint, flash, render_template, redirect, request, url_for
)

from webapp.views.Immunohistochemistry.forms import (
    ImmunohistochemistryForm
)

from webapp.home.forms import (
    form_md5, is_dirty_form
)

from webapp.home.metapype_client import (
    load_eml, list_responsible_parties, save_both_formats,
    add_child, create_responsible_party
)

from metapype.eml import names
from metapype.model.node import Node

from webapp.buttons import *
from webapp.pages import *

from webapp.home.views import select_post, non_breaking, set_current_page, get_help, get_helps

ihc_bp = Blueprint('ihc', __name__, template_folder='templates')


@ihc_bp.route('/test/<filename>', methods=['GET', 'POST'])
def test(filename=None):
    method = request.method
    node_id = '1'
    if filename:
        eml_node = load_eml(filename=filename)
        dataset_node = eml_node.find_child(names.DATASET)
        if dataset_node:
            publisher_node = dataset_node.find_child(names.PUBLISHER)
            if publisher_node:
                node_id = publisher_node.id
    set_current_page('publisher')
    help = [get_help('publisher')]
    # return responsible_party(filename=filename, node_id=node_id,
    #                         method=method, node_name=names.PUBLISHER,
    #                         back_page=PAGE_CONTACT_SELECT, title='Publisher',
    #                         next_page=PAGE_PUBLICATION_INFO,
    #                         save_and_continue=True, help=help)
    return "<p>Hello World</p>"
