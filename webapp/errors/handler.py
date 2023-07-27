#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: handler

:Synopsis:

:Author:
    servilla
    ide

:Created:
    5/30/18
"""
import daiquiri
from flask import Blueprint, render_template, request
from flask_login import current_user
from flask_wtf.csrf import CSRFError
from webapp import app
from webapp.home.exceptions import LockOwnedByAGroup, LockOwnedByAnotherUser, DeprecatedCodeError
from webapp.config import Config


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