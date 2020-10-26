#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
:Mod: __init__.py

:Synopsis:

:Author:
    servilla

:Created:
    10/26/20
"""
import logging
import os
import sys

import daiquiri

sys.path.insert(0, os.path.abspath(".."))

cwd = os.path.dirname(os.path.realpath(__file__))
logfile = cwd + "/tests.log"
daiquiri.setup(
    level=logging.INFO, outputs=(daiquiri.output.File(logfile), "stdout",)
)
