"""
Handlers for the various errors that can occur in the webapp. Logs the error and returns a template.
"""

import daiquiri
from flask import Blueprint, redirect, render_template, request, url_for
from flask_login import current_user
from flask_wtf.csrf import CSRFError
from webapp import app
from webapp.home.exceptions import EMLFileNotFound, LockOwnedByAGroup, LockOwnedByAnotherUser, DeprecatedCodeError, \
    NodeWithGivenIdNotFound, InvalidFilename
from webapp.config import Config
import webapp.auth.user_data as user_data
from webapp.pages import *


logger = daiquiri.getLogger('handler: ' + __name__)
errors = Blueprint('errors', __name__, template_folder='templates')


def log_error(error):
    if current_user and hasattr(current_user, 'get_username'):
        logger.error(error, USER=current_user.get_username())
        if hasattr(error, 'original_exception'):
            logger.error(error.original_exception, USER=current_user.get_username())
    else:
        logger.error(error)
        if hasattr(error, 'original_exception'):
            logger.error(error.original_exception)


@app.errorhandler(400)
def bad_request(error):
    log_error(error)
    return render_template('400.html'), 400


@app.errorhandler(401)
def bad_request(error):
    log_error(error)
    return render_template('401.html'), 401


@app.errorhandler(404)
def bad_request(error):
    log_error(error)
    if request and request.url:
        logger.error(f'404 request.url: {request.url}')
    return render_template('404.html'), 404


@app.errorhandler(500)
def bad_request(error):
    log_error(error)
    return render_template('500.html'), 500


@app.errorhandler(EMLFileNotFound)
def handle_eml_file_not_found(error):
    log_error('EML file not found: {0}'.format(error.message))
    user_data.set_active_document(None)
    return redirect(url_for(PAGE_INDEX))


@app.errorhandler(InvalidFilename)
def handle_invalid_filename(error):
    log_error('Invalid filename: {0}'.format(error.message))
    user_data.set_active_document(None)
    return render_template('invalid_filename_error.html',
                           message=error.message)


@app.errorhandler(NodeWithGivenIdNotFound)
def handle_node_with_given_id_not_found(error):
    log_error('Node with given ID not found: {0}'.format(error.message))
    return render_template('node_with_given_id_not_found.html'), 404


@app.errorhandler(LockOwnedByAGroup)
def handle_locked_by_a_group(error):
    log_error('Attempt to access a locked document: {0}'.format(error.message))
    return render_template('locked_by_group.html',
                           package_name=error.package_name,
                           locked_by=error.user_name), 403


@app.errorhandler(LockOwnedByAnotherUser)
def handle_lock_is_not_owned_by_user(error):
    log_error('Attempt to access a locked document: {0}'.format(error.message))
    return render_template('locked_by_another.html',
                           package_name=error.package_name,
                           locked_by=error.user_name,
                           lock_timeout=Config.COLLABORATION_LOCK_INACTIVITY_TIMEOUT_MINUTES), 403


@app.errorhandler(CSRFError)
def handle_csrf_error(error):
    log_error('**** A CSRF error occurred: {0}'.format(error.description))
    return render_template('401.html'), 403


@app.errorhandler(DeprecatedCodeError)
def handle_deprecated_code_error(error):
    log_error('**** A deprecated code error occurred: {0}'.format(error.message))
    return render_template('deprecated_code_error.html', message=error.message), 403