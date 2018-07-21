#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: views.py

:Synopsis:

:Author:
    servilla

:Created:
    3/6/18
"""
from flask import Blueprint, render_template, redirect, url_for

home = Blueprint('home', __name__, template_folder='templates')


@home.route('/')
def index():
    return render_template('index.html')

@home.route('/about')
def about():
    return render_template('about.html')