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
from urllib.parse import urlparse
import base64
import jwt

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
import requests

from webapp.pages import *
from webapp.auth.forms import LoginForm
from webapp.auth.pasta_token import PastaToken
from webapp.auth.user import User
from webapp.auth.user_data import get_active_document, initialize_user_data
from webapp.config import Config
from webapp.home.home_utils import log_error, log_info
from webapp.home.utils.hidden_buttons import is_hidden_button, handle_hidden_buttons

from webapp.home.log_usage import (
    actions,
    log_usage,
)
from webapp.home.views import get_helps
from webapp.views.collaborations.collaborations import close_package


auth_bp = Blueprint('auth', __name__, template_folder='templates')


def is_whitelisted_username(username):
    if hasattr(Config, 'SERVER_LOGINS_WHITELIST') and Config.SERVER_LOGINS_WHITELIST:
        return username in Config.SERVER_LOGINS_WHITELIST
    else:
        return True


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # We want to be able to handle hidden buttons for User Guide, About, and News without user being logged in
    if is_hidden_button():
        new_page = handle_hidden_buttons(PAGE_LOGIN)
        return redirect(url_for(new_page, filename=None))

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
            log_error(f'Non-whitelisted login attempt by {username}')
            return redirect(url_for(PAGE_LOGIN))
        domain = "edi"
        user_dn = f'uid={form.username.data},{Config.DOMAINS[domain]}'
        password = form.password.data
        _, pasta_token = authenticate(user_dn=user_dn, password=password)
        if pasta_token is not None and pasta_token != "teapot":
            _jwt_ = jwt.decode(
                pasta_token,
                options={'verify_signature': False},
                algorithms=['HS256']
            )
            uid = _jwt_['pastaIdpUid']
            cname = _jwt_['cn']
            if cname:
                cname = cname.strip()
            session_id = f'{cname}*{uid}'
            user = User(session_id)
            login_user(user)
            initialize_user_data(cname, 'LDAP', uid)
            log_usage(actions['LOGIN'], cname, 'LDAP', current_user.get_user_login())
            next_page = request.args.get('next')
            if not next_page or urlparse(next_page).netloc != '':
                current_document = get_active_document()
                if current_document:
                    next_page = url_for(PAGE_TITLE, filename=current_document)
                else:
                    next_page = url_for(PAGE_INDEX)
            return redirect(next_page)
        elif pasta_token == "teapot":
            log_usage(actions['LOGIN'], form.username.data, 'teapot')
            accept_url = f"{Config.AUTH}/accept?uid={user_dn}&target={Config.TARGET}"
            return redirect(accept_url)
        flash('Invalid username or password')
        return redirect(url_for(PAGE_LOGIN))

    # Process GET
    _jwt_ = None
    pasta_token = request.args.get("pasta_token")
    if pasta_token:
        _jwt_ = jwt.decode(
            pasta_token,
            options={'verify_signature': False},
            algorithms=['HS256']
        )

    if _jwt_:
        sub = _jwt_['sub']
        cname = _jwt_['cn']
        idp = _jwt_['pastaIdpName']
        uid = _jwt_['pastaIdpUid']
        log_info(f"uid: {uid}  cname: {cname}  idp: {idp}  sub: {sub}")

        # If it's a Google login, we need to see if the user data needs to be repaired.
        from webapp.home.repair_user_data import repair_user_data
        if Config.REPAIR_USER_DATA and idp == 'google':
            repair_user_data(cname, idp, uid, sub)

        session_id = f"{cname}*{uid}"
        user = User(session_id)
        login_user(user)
        initialize_user_data(cname, idp, uid, sub)
        log_usage(actions['LOGIN'], cname, idp, uid, current_user.get_user_login())
        next_page = request.args.get('next')
        if not next_page or urlparse(next_page).netloc != '':
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
    if current_user.is_authenticated:
        log_usage(actions['LOGOUT'])
        user_login = current_user.get_user_login()
        close_package(user_login)
        logout_user()
    return redirect(url_for(PAGE_LOGIN))


def authenticate(user_dn=None, password=None):
    auth_token = None
    pasta_token = None
    auth_url = f"{Config.AUTH}/login/pasta?target={Config.TARGET}"
    r = requests.get(auth_url, auth=(user_dn, password))
    if r.status_code == requests.codes.ok:
        try:
            auth_token = r.cookies['auth-token']
        except:
            auth_token = None
        try:
            pasta_token = r.cookies['pasta-token']
        except:
            pasta_token = None
    elif r.status_code == requests.codes.teapot:
        return "teapot", "teapot"
    return auth_token, pasta_token
