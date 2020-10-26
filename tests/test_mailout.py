#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
:Mod: test_mailout

:Synopsis:

:Author:
    servilla

:Created:
    10/26/20
"""
import logging
import os

import daiquiri
import pytest

import webapp.mailout as mailout

cwd = os.path.dirname(os.path.realpath(__file__))
logfile = cwd + "/test_mailout.log"
daiquiri.setup(level=logging.INFO,
               outputs=(daiquiri.output.File(logfile), "stdout",))
logger = daiquiri.getLogger(__name__)


def test_send_mail():
    subject = "Test ezEML support email notification..."
    msg = "IGNORE -- Test ezEML support email notification."
    to = "support@environmentaldatainitiative.org"
    mailout.send_mail(subject, msg, to)