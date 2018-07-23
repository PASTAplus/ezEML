#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: views.py

:Synopsis:

:Author:
    servilla

:Created:
    3/6/18
"""
from flask import Blueprint, flash, render_template, redirect, url_for
from webapp.home.forms import MinimalEMLForm

home = Blueprint('home', __name__, template_folder='templates')


@home.route('/')
def index():
    return render_template('index.html')

@home.route('/about')
def about():
    return render_template('about.html')

@home.route('/minimal', methods=['GET', 'POST'])
def minimal():
    # Process POST
    form = MinimalEMLForm()
    if form.validate_on_submit():
        flash(f'The title is: {form.title.data}')
        flash(f'The contact given name is {form.contact_gn.data}')
        flash(f'The contact surname is {form.contact_sn.data}')
        flash(f'The creator given name is {form.creator_gn.data}')
        flash(f'The creator surnmae is {form.creator_sn.data}')
    # Process GET
    return render_template('minimal_eml.html', title='Minimal EML', form=form)
