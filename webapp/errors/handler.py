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
from flask import Blueprint, render_template
from flask_login import current_user
from webapp import app


logger = daiquiri.getLogger('handler: ' + __name__)
errors = Blueprint('errors', __name__, template_folder='templates')


def log_error(error):
    if current_user and hasattr(current_user, 'get_username'):
        logger.error(error, USER=current_user.get_username())
        logger.error(error.original_exception, USER=current_user.get_username())
    else:
        logger.error(error)
        logger.error(error.original_exception)


@app.errorhandler(400)
def bad_request(error):
    log_error(error)
    return render_template('400.html'), 400


@app.errorhandler(404)
def bad_request(error):
    log_error(error)
    return render_template('404.html'), 404


@app.errorhandler(500)
def bad_request(error):
    log_error(error)
    return render_template('500.html'), 500
