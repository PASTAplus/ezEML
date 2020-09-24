#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: views

:Synopsis:

:Author:
    servilla
    costa
    ide

:Created:
    3/6/18
"""
import daiquiri
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
import requests
from werkzeug.urls import url_parse

from webapp.pages import *
from webapp.auth.forms import LoginForm
from webapp.auth.pasta_token import PastaToken
from webapp.auth.user import User
from webapp.auth.user_data import get_active_document, initialize_user_data
from webapp.config import Config


logger = daiquiri.getLogger('views: ' + __name__)
auth = Blueprint('auth', __name__, template_folder='templates')


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        flash(current_user.get_username() + ', you are already logged in...')
        return redirect(url_for(PAGE_INDEX))
    # Process POST
    form = LoginForm()
    if form.validate_on_submit():
        domain = form.domain.data # Never None
        user_dn = 'uid=' + form.username.data + ',' + Config.DOMAINS[domain]
        password = form.password.data
        auth_token = authenticate(user_dn=user_dn, password=password)
        if auth_token is not None and auth_token != "teapot":
            pasta_token = PastaToken(auth_token)
            uid = pasta_token.uid.split(",")[0]
            cname = uid.split('=')[1]
            session_id = cname + "*" + pasta_token.uid
            user = User(session_id)
            login_user(user)
            initialize_user_data()
            next_page = request.args.get('next')
            if not next_page or url_parse(next_page).netloc != '':
                current_document = get_active_document()
                if current_document:
                    next_page = url_for(PAGE_TITLE, filename=current_document)
                else:
                    next_page = url_for(PAGE_INDEX)
            return redirect(next_page)
        elif auth_token == "teapot":
            accept_url = f"{Config.AUTH}/accept?uid={user_dn}&target={Config.TARGET}"
            return redirect(accept_url)
        flash('Invalid username or password')
        return redirect(url_for(PAGE_LOGIN))
    # Process GET
    auth_token = request.args.get("token")
    cname = request.args.get("cname")
    if auth_token is not None and cname is not None:
        pasta_token = PastaToken(auth_token)
        uid = pasta_token.uid
        session_id = cname + "*" + uid
        user = User(session_id)
        login_user(user)
        initialize_user_data()
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            current_document = get_active_document()
            if current_document:
                next_page = url_for(PAGE_TITLE, filename=current_document)
            else:
                next_page = url_for(PAGE_INDEX)
        return redirect(next_page)
    return render_template(
        'login.html', form=form, auth=Config.AUTH, target=Config.TARGET
    )


@auth.route('/logout', methods=['GET'])
def logout():
    logout_user()
    return redirect(url_for(PAGE_INDEX))


def authenticate(user_dn=None, password=None):
    auth_token = None
    auth_url = Config.AUTH + f"/login/pasta?target={Config.TARGET}"
    r = requests.get(auth_url, auth=(user_dn, password))
    if r.status_code == requests.codes.ok:
        auth_token = r.cookies['auth-token']
    elif r.status_code == requests.codes.teapot:
        return "teapot"
    return auth_token
