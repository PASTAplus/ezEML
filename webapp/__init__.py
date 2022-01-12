# -*- coding: utf-8 -*-

""":Mod: __init__

:Synopsis:

:Author:
    servilla
    costa

:Created:
    2/15/18
"""
import logging
import os

import daiquiri
import daiquiri.formatter

from flask import Flask, session
from flask_bootstrap import Bootstrap
from flask_login import LoginManager

from webapp.config import Config

cwd = os.path.dirname(os.path.realpath(__file__))
logfile = cwd + '/metadata-eml.log'
daiquiri.setup(level=logging.INFO,
               outputs=[
                   daiquiri.output.File(logfile,
                                             formatter=daiquiri.formatter.ExtrasFormatter(
                                                fmt=("%(asctime)s [PID %(process)d] [%(levelname)s]" +
                                                     "%(extras)s %(name)s -> %(message)s"),
                                                keywords=None)), 'stdout'
                ])
logger = daiquiri.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)
bootstrap = Bootstrap(app)
login = LoginManager(app)
login.login_view = 'auth.login'

# Importing these modules causes the routes and error handlers to be associated
# with the blueprint. It is important to note that the modules are imported at
# the bottom of the webapp/__init__.py script to avoid errors due to circular 
# dependencies.

from webapp.auth.views import auth
app.register_blueprint(auth, url_prefix='/eml/auth')

from webapp.errors.handler import errors
app.register_blueprint(errors, url_prefix='/eml/error')

from webapp.home.views import home
app.register_blueprint(home, url_prefix='/eml')

from webapp.views.access.access import acc_bp
app.register_blueprint(acc_bp, url_prefix='/eml')

from webapp.views.coverage.coverage import cov_bp
app.register_blueprint(cov_bp, url_prefix='/eml')

from webapp.views.data_tables.dt import dt_bp
app.register_blueprint(dt_bp, url_prefix='/eml')

from webapp.views.entities.entities import ent_bp
app.register_blueprint(ent_bp, url_prefix='/eml')

from webapp.views.maintenance.maintenance import maint_bp
app.register_blueprint(maint_bp, url_prefix='/eml')

from webapp.views.method_steps.md import md_bp
app.register_blueprint(md_bp, url_prefix='/eml')

from webapp.views.project.project import proj_bp
app.register_blueprint(proj_bp, url_prefix='/eml')

from webapp.views.resources.resources import res_bp
app.register_blueprint(res_bp, url_prefix='/eml')

from webapp.views.responsible_parties.rp import rp_bp
app.register_blueprint(rp_bp, url_prefix='/eml')
