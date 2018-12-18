#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: views

:Synopsis:

:Author:
    servilla
    costa

:Created:
    3/6/18
"""
import daiquiri
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask import abort
from flask_login import current_user, login_user, logout_user, login_required

from werkzeug.urls import url_parse

from webapp.auth.forms import LoginForm
from webapp.auth.user import User
from webapp.config import Config

from webapp.auth.user_data import (
    initialize_user_data
)


logger = daiquiri.getLogger('views: ' + __name__)
auth = Blueprint('auth', __name__, template_folder='templates')


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        flash(current_user.get_username() + ', you are already logged in...')
        return redirect(url_for('home.index'))
    # Process POST
    form = LoginForm()
    if form.validate_on_submit():
        domain = form.domain.data # Never None
        user_dn = 'uid=' + form.username.data + ',' + Config.DOMAINS[domain]
        password = form.password.data
        user = None
        auth_token = User.authenticate(user_dn=user_dn, password=password)
        if auth_token is not None:
            user = User(auth_token=auth_token)
            login_user(user)
            initialize_user_data()
            next_page = request.args.get('next')
            if not next_page or url_parse(next_page).netloc != '':
                next_page = url_for('home.index')
            return redirect(next_page)
        flash('Invalid username or password')
        return redirect(url_for('auth.login'))
    # Process GET
    return render_template('login.html', title='Sign In', form=form)


@auth.route('/logout', methods=['GET'])
def logout():
    logout_user()
    return redirect(url_for('home.index'))
