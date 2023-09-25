"""
Hidden Buttons...

When the user is working in a page where there are fields to fill in (e.g., the Title page or a Data Table page)
and the user clicks on a menu option like "New" or "Open", we don't go directly to that New or Open page because
we first need to save whatever changes the user has entered in the current page. Only the handler for the current
page knows how to do that. I.e., the Open handler, for example, can't generically save the data since Open may have
been clicked when the user was in any number of different pages, each with its own logic for saving entered data.

Instead, we post to the current page a "hidden" button that tells us which menu option was selected. Then, in the
current page, we save the data that the user has entered and then we go to the new page indicated by the "hidden"
button. E.g., if they clicked "Open" while on the Title page, we post to the Title page with Hidden_Open in the form
so the Title method can save the title data and then go to the Open page.
"""

from flask import request

from webapp.buttons import BTN_HIDDEN_CHECK, BTN_HIDDEN_SAVE, BTN_HIDDEN_DOWNLOAD, BTN_HIDDEN_NEW, \
    BTN_HIDDEN_NEW_FROM_TEMPLATE, BTN_HIDDEN_OPEN, BTN_HIDDEN_CLOSE
from webapp.pages import PAGE_CHECK, PAGE_DOWNLOAD, PAGE_CREATE, PAGE_IMPORT_TEMPLATE, PAGE_OPEN, PAGE_CLOSE


def is_hidden_button():
    return any(button in request.form for button in HIDDEN_BUTTONS)


def handle_hidden_buttons(new_page, this_page):
    """
    See if a "hidden" button has been clicked. If so, set new_page to the page that the button indicates.

    If none of the hidden buttons was clicked, leave new_page as we found it
    """
    if BTN_HIDDEN_CHECK in request.form:
        new_page = PAGE_CHECK
    elif BTN_HIDDEN_SAVE in request.form:
        new_page = this_page
    elif BTN_HIDDEN_DOWNLOAD in request.form:
        new_page = PAGE_DOWNLOAD
    elif BTN_HIDDEN_NEW in request.form:
        new_page = PAGE_CREATE
    elif BTN_HIDDEN_NEW_FROM_TEMPLATE in request.form:
        new_page = PAGE_IMPORT_TEMPLATE
    elif BTN_HIDDEN_OPEN in request.form:
        new_page = PAGE_OPEN
    elif BTN_HIDDEN_CLOSE in request.form:
        new_page = PAGE_CLOSE
    return new_page


def check_val_for_hidden_buttons(val, new_page, this_page):
    """
    See if a "hidden" button has been clicked. If so, set new_page to the page that the button indicates.

    The process here is different from handle_hidden_buttons() because we're in a "select" page where the form
    dictionary has node_id's as keys and the button is a value.

    If none of the hidden buttons was clicked, leave new_page as we found it.
    """

    if val == BTN_HIDDEN_CHECK:
        new_page = PAGE_CHECK
    elif val == BTN_HIDDEN_SAVE:
        new_page = this_page
    elif val == BTN_HIDDEN_DOWNLOAD:
        new_page = PAGE_DOWNLOAD
    elif val == BTN_HIDDEN_NEW:
        new_page = PAGE_CREATE
    elif val == BTN_HIDDEN_NEW_FROM_TEMPLATE:
        new_page = PAGE_IMPORT_TEMPLATE
    elif val == BTN_HIDDEN_OPEN:
        new_page = PAGE_OPEN
    elif val == BTN_HIDDEN_CLOSE:
        new_page = PAGE_CLOSE
    return new_page


HIDDEN_BUTTONS = [
    BTN_HIDDEN_CHECK,
    BTN_HIDDEN_SAVE,
    BTN_HIDDEN_DOWNLOAD,
    BTN_HIDDEN_NEW,
    BTN_HIDDEN_NEW_FROM_TEMPLATE,
    BTN_HIDDEN_OPEN,
    BTN_HIDDEN_CLOSE
]