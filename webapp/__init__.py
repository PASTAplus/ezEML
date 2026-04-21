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
from datetime import datetime, timedelta
import json
import logging
import os
import re

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


GC_START_RUN_REGEX = re.compile(
    r'^(?P<run_datetime>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+\s+__main__ -> Start run:.*\bdays=(?P<days>\d+)\b'
)
GC_LOG_DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'


def update_gc_cutoff_date_pickle():
    """Parse the GC log and persist the most recent GC cutoff datetime in user-data/GC_date.pkl as plain text."""
    gc_log_path = os.path.join(Config.USER_DATA_DIR, 'ezEML_GC.log')
    gc_date_file_path = os.path.join(Config.USER_DATA_DIR, 'GC_date.pkl')

    if not os.path.exists(gc_log_path):
        return

    latest_gc_cutoff = None
    try:
        # Expected log line format:
        # "YYYY-MM-DD HH:MM:SS,mmm __main__ -> Start run: ... days=<N> ... keep_uploads=False ... logonly=False"
        max_bytes = 2 * 1024 * 1024
        file_size = os.path.getsize(gc_log_path)

        def scan_lines(lines, latest_cutoff):
            for line in lines:
                match = GC_START_RUN_REGEX.search(line)
                if not match:
                    continue
                if 'keep_uploads=False' not in line or 'logonly=False' not in line:
                    continue
                run_datetime = datetime.strptime(match.group('run_datetime'), GC_LOG_DATETIME_FORMAT)
                days = int(match.group('days'))
                gc_cutoff_datetime = run_datetime - timedelta(days=days)
                if latest_cutoff is None or gc_cutoff_datetime > latest_cutoff:
                    latest_cutoff = gc_cutoff_datetime
            return latest_cutoff

        if file_size > max_bytes:
            with open(gc_log_path, 'rb') as f:
                f.seek(-max_bytes, os.SEEK_END)
                latest_gc_cutoff = scan_lines(
                    f.read().decode('utf-8', errors='ignore').splitlines(),
                    latest_gc_cutoff
                )
            if latest_gc_cutoff is None:
                with open(gc_log_path, 'r', encoding='utf-8') as f:
                    latest_gc_cutoff = scan_lines(f, latest_gc_cutoff)
        else:
            with open(gc_log_path, 'r', encoding='utf-8') as f:
                latest_gc_cutoff = scan_lines(f, latest_gc_cutoff)
    except Exception as e:
        logger.error(f'Failed to parse GC log file {gc_log_path}: {e}')
        return

    if latest_gc_cutoff is None:
        return

    try:
        with open(gc_date_file_path, 'w', encoding='utf-8') as f:
            f.write(latest_gc_cutoff.strftime(GC_LOG_DATETIME_FORMAT))
    except Exception as e:
        logger.error(f'Failed to write GC cutoff date to {gc_date_file_path}: {e}')

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

app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['SESSION_REFRESH_EACH_REQUEST'] = True               # Extends session on every request. Keep-alive.

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
update_gc_cutoff_date_pickle()
