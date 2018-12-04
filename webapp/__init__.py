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
from flask import Flask
from flask_bootstrap import Bootstrap
from flask_login import LoginManager

from webapp.config import Config

cwd = os.path.dirname(os.path.realpath(__file__))
logfile = cwd + '/metadata-eml.log'
daiquiri.setup(level=logging.INFO,
               outputs=(daiquiri.output.File(logfile), 'stdout',))
logger = daiquiri.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)
bootstrap = Bootstrap(app)
login = LoginManager(app)
login.login_view = 'auth.login'

from webapp.auth.views import auth
app.register_blueprint(auth, url_prefix='/eml/auth')

from webapp.home.views import home
app.register_blueprint(home, url_prefix='/eml')

from webapp.errors.handler import errors
app.register_blueprint(errors, url_prefix='/eml/error')
