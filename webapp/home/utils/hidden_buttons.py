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

from webapp.buttons import *
from webapp.pages import *

HIDDEN_TARGETS = {
    BTN_HIDDEN_ABOUT: PAGE_ABOUT,
    BTN_HIDDEN_CHECK_DATA_TABLES: PAGE_CHECK_DATA_TABLES,
    BTN_HIDDEN_CHECK_METADATA: PAGE_CHECK_METADATA,
    BTN_HIDDEN_CLOSE: PAGE_CLOSE,
    BTN_HIDDEN_COLLABORATE: PAGE_COLLABORATE,
    BTN_HIDDEN_DOWNLOAD: PAGE_DOWNLOAD,
    BTN_HIDDEN_EXPORT_EZEML_DATA_PACKAGE: PAGE_EXPORT_EZEML_DATA_PACKAGE,
    BTN_HIDDEN_FETCH_FROM_EDI: PAGE_FETCH_FROM_EDI,
    BTN_HIDDEN_IMPORT_EZEML_DATA_PACKAGE: PAGE_IMPORT_EZEML_DATA_PACKAGE,
    BTN_HIDDEN_IMPORT_FUNDING_AWARDS: PAGE_IMPORT_FUNDING_AWARDS,
    BTN_HIDDEN_IMPORT_GEO_COVERAGE: PAGE_IMPORT_GEO_COVERAGE,
    BTN_HIDDEN_IMPORT_PARTIES: PAGE_IMPORT_PARTIES,
    BTN_HIDDEN_IMPORT_PROJECT: PAGE_IMPORT_PROJECT,
    BTN_HIDDEN_IMPORT_RELATED_PROJECTS: PAGE_IMPORT_RELATED_PROJECTS,
    BTN_HIDDEN_IMPORT_TAXONOMIC_COVERAGE: PAGE_IMPORT_TAXONOMIC_COVERAGE,
    BTN_HIDDEN_IMPORT_XML: PAGE_IMPORT_XML,
    BTN_HIDDEN_INDEX: PAGE_INDEX,
    BTN_HIDDEN_LOGOUT: PAGE_LOGOUT,
    BTN_HIDDEN_MANAGE: PAGE_MANAGE_PACKAGES,
    BTN_HIDDEN_NEW: PAGE_CREATE,
    BTN_HIDDEN_NEWS: PAGE_NEWS,
    BTN_HIDDEN_NEW_FROM_TEMPLATE: PAGE_IMPORT_TEMPLATE,
    BTN_HIDDEN_OPEN: PAGE_OPEN,
    BTN_HIDDEN_SAVE: PAGE_SAVE,
    BTN_HIDDEN_SAVE_AS: PAGE_SAVE_AS,
    BTN_HIDDEN_USER_GUIDE: PAGE_USER_GUIDE
}


def is_hidden_button():
    return any(button in request.form for button in HIDDEN_TARGETS)


def handle_hidden_buttons(target_page):
    """
    See if a "hidden" button has been clicked. If so, return the page that the button indicates.

    If none of the hidden buttons was clicked, leave target_page as we found it. I.e., target_page is the page
    that the user was trying to get to when they clicked on the menu option, so we'll go there in the absence of
    a hidden button. If a hidden button was clicked, we'll go to the page that the hidden button indicates, after
    saving the data that the user entered in the page that they were in when they clicked on the menu option.
    """
    for button in HIDDEN_TARGETS:
        if button in request.form:
            return HIDDEN_TARGETS[button]
    return target_page


def check_val_for_hidden_buttons(val, target_page):
    """
    See if a "hidden" button has been clicked. If so, return the page that the button indicates.

    The idea here is the same as in handle_hidden_buttons(), but the process is different because we're in a "select"
    page where the form dictionary has node_id's as keys and the button is a value.

    If none of the hidden buttons was clicked, leave target_page as we found it.
    """
    for button in HIDDEN_TARGETS:
        if val == button:
            return HIDDEN_TARGETS[button]
    return target_page