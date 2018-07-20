# -*- coding: utf-8 -*-

""":Mod: __init__

:Synopsis:

:Author:
    servilla

:Created:
    2/15/18
"""
import logging
import os

import daiquiri
from flask import Flask
from flask_bootstrap import Bootstrap

from webapp.config import Config

cwd = os.path.dirname(os.path.realpath(__file__))
logfile = cwd + '/metadata-eml.log'
daiquiri.setup(level=logging.INFO,
               outputs=(daiquiri.output.File(logfile), 'stdout',))
logger = daiquiri.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)
bootstrap = Bootstrap(app)

from webapp import views