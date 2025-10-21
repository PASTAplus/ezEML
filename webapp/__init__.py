# -*- coding: utf-8 -*-

""":Mod: __init__

:Synopsis:

:Author:
    servilla
    costa
    ide

:Created:
    2/15/18
"""
import base64
import json
import logging
import os

import daiquiri.formatter

from flask import Flask, g
from flask_bootstrap import Bootstrap
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from sqlalchemy import event

from webapp.config import Config


cwd = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
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

# Define the b64encode filter
def b64encode(value):
    return base64.b64encode(json.dumps(value).encode('utf-8')).decode('utf-8')

# Register the filter with Jinja2
app.jinja_env.filters['b64encode'] = b64encode

# The following makes the badge_data variable available to all templates
# Formerly, it was passed in the session, but that caused problems with
# the size of the session cookie. This is a better solution.
# And the beauty of it is that it is available in all templates without
# having to pass it in the render_template call, and it works with redirects
# as well without having to pass it in the url, which leads to urls that are
# too long.
@app.context_processor
def inject_badge_data():
    return dict(badge_data=getattr(g, 'badge_data', None))

bootstrap = Bootstrap(app)
login = LoginManager(app)
login.login_view = 'auth.login'

app.config['MAX_COOKIE_SIZE'] = 65535

# We'll use sqlite3 for managing collaborations in ezEML
db_dir = os.path.join(Config.USER_DATA_DIR, '__db')
if not os.path.exists(db_dir):
    os.makedirs(db_dir)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///' + os.path.join(db_dir, 'collaborations.db.sqlite3')
# print(app.config['SQLALCHEMY_DATABASE_URI'])
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# And we use sqlite3 for managing curator workflows in ezEML
# This bind needs to be set up before we call SQLAlchemy(app) !
bind_target = f'sqlite:///' + os.path.join(db_dir, 'curator_workflows.db.sqlite3')
app.config['SQLALCHEMY_BINDS'] = {
    'curator_workflow': bind_target
}

db = SQLAlchemy(app)
db.metadata.clear()
migrate = Migrate(app, db)

# Using sqlite3 for managing curator workflows
from webapp.views.curator_workflow.model import WorkflowPackage, Workflow
with app.app_context():
    engine = db.engines.get('curator_workflow')
    if engine is None:
        raise ValueError("The 'curator_workflow' bind was not found in db.engines.")
    db.metadata.create_all(bind=engine)  # Create tables for the bind

# Enable foreign key constraints for SQLite
def enable_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()
with app.app_context():
    engine = db.engines.get(None)
    if engine:
        event.listen(engine, "connect", enable_foreign_keys)
    else:
        raise ValueError("Default engine for collaborations.db not found")
    engine = db.engines.get('curator_workflow')
    if engine:
        event.listen(engine, "connect", enable_foreign_keys)
    else:
        raise ValueError("Engine for curator_workflows.db not found")

# Importing these modules causes the routes and error handlers to be associated
# with the blueprint. It is important to note that the modules are imported at
# the bottom of the webapp/__init__.py script to avoid errors due to circular 
# dependencies.

from webapp.auth.views import auth_bp
app.register_blueprint(auth_bp, url_prefix='/eml/auth')

from webapp.errors.handler import errors
app.register_blueprint(errors, url_prefix='/eml/error')

from webapp.home.views import home_bp
app.register_blueprint(home_bp, url_prefix='/eml')

from webapp.views.access.access import acc_bp
app.register_blueprint(acc_bp, url_prefix='/eml')

from webapp.views.collaborations.routes import collab_bp
app.register_blueprint(collab_bp, url_prefix='/eml')

from webapp.views.curator_workflow.routes import workflow_bp
app.register_blueprint(workflow_bp, url_prefix='/eml')

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


import requests
def download_qudt_annotations_data_file():
    url = "https://github.com/EDIorg/Units-WG/raw/main/RCode_JP/DataFiles4R/unitsWithQUDTInfo.csv"
    local_dir = os.path.join(app.root_path, 'static')
    local_path = os.path.join(local_dir, 'unitsWithQUDTInfo.csv')

    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad status codes

        os.makedirs(local_dir, exist_ok=True)
        with open(local_path, 'wb') as f:
            f.write(response.content)
        logger.info(f'QUDT annotations data file downloaded and saved to {local_path}')
    except Exception as e:
        logger.error(f'Failed to download QUDT annotations data file: {e}')

download_qudt_annotations_data_file()
