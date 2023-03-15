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
from webapp.home.log_usage import (
    actions,
    log_usage,
)
from webapp.home.views import get_helps
from webapp.views.collaborations.collaborations import close_package


logger = daiquiri.getLogger('views: ' + __name__)
auth_bp = Blueprint('auth', __name__, template_folder='templates')


def is_whitelisted_username(username):
    if Config.SERVER_LOGINS_WHITELIST:
        return username in Config.SERVER_LOGINS_WHITELIST
    else:
        return True


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        filename = get_active_document()
        if filename:
            return redirect(url_for(PAGE_TITLE, filename=filename))
        else:
            return redirect(url_for(PAGE_INDEX))
    # Process POST
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        if not is_whitelisted_username(username):
            flash(f'Username {username} is not authorized to log in to this server. Please contact ' 
                  'support@edirepository.org if you believe you need access to this server.', 'error')
            return redirect(url_for(PAGE_LOGIN))
        # domain = form.domain.data # Never None
        domain = "edi"
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
            initialize_user_data(cname, pasta_token.uid, auth_token)
            log_usage(actions['LOGIN'], cname, 'LDAP')
            next_page = request.args.get('next')
            if not next_page or url_parse(next_page).netloc != '':
                current_document = get_active_document()
                if current_document:
                    next_page = url_for(PAGE_TITLE, filename=current_document)
                else:
                    next_page = url_for(PAGE_INDEX)
            return redirect(next_page)
        elif auth_token == "teapot":
            log_usage(actions['LOGIN'], form.username.data, 'teapot')
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
        initialize_user_data(cname, pasta_token.uid, auth_token)
        log_usage(actions['LOGIN'], cname)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            current_document = get_active_document()
            if current_document:
                next_page = url_for(PAGE_TITLE, filename=current_document)
            else:
                next_page = url_for(PAGE_INDEX)
        return redirect(next_page)
    help = get_helps(['login'])
    return render_template(
        'login.html', form=form, auth=Config.AUTH, target=Config.TARGET, help=help
    )


@auth_bp.route('/logout', methods=['GET'])
def logout():
    log_usage(actions['LOGOUT'])
    user_login = current_user.get_user_login()
    logout_user()
    close_package(user_login)
    return redirect(url_for(PAGE_LOGIN))


def authenticate(user_dn=None, password=None):
    auth_token = None
    auth_url = Config.AUTH + f"/login/pasta?target={Config.TARGET}"
    r = requests.get(auth_url, auth=(user_dn, password))
    if r.status_code == requests.codes.ok:
        auth_token = r.cookies['auth-token']
    elif r.status_code == requests.codes.teapot:
        return "teapot"
    return auth_token
