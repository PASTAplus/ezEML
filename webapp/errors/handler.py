#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: handler

:Synopsis:

:Author:
    servilla

:Created:
    5/30/18
"""
import daiquiri
from flask import Blueprint, render_template
from webapp import app


logger = daiquiri.getLogger('handler: ' + __name__)
errors = Blueprint('errors', __name__, template_folder='templates')

@app.errorhandler(400)
def bad_request(error):
    return render_template('400.html'), 400


@app.errorhandler(404)
def bad_request(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def bad_request(error):
    return render_template('500.html'), 500
