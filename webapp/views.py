#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: views.py

:Synopsis:

:Author:
    servilla

:Created:
    7/20/18
"""
import daiquiri

from webapp import app

logger = daiquiri.getLogger('views.py: ' + __name__)

@app.route('/')
def index():
    return 'Hell on wheels...'