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

# my (Pierce) changes --> 3/2X/2022
import json
from os import environ as env
from urllib.parse import quote_plus, urlencode

from authlib.integrations.flask_client import OAuth
from dotenv import find_dotenv, load_dotenv
from flask import Flask, redirect, render_template, session, url_for

logger = daiquiri.getLogger('views: ' + __name__)
auth = Blueprint('auth', __name__, template_folder='templates')

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)
app = Flask(__name__)
app.secret_key = env.get("APP_SECRET_KEY")

oauth = OAuth(app)

oauth.register(
    "auth0",
    client_id=env.get("AUTH0_CLIENT_ID"),
    client_secret=env.get("AUTH0_CLIENT_SECRET"),
    client_kwargs={
        "scope": "openid email",
    },
    server_metadata_url=f'https://{env.get("AUTH0_DOMAIN")}/.well-known/openid-configuration'
)


@auth.route("/login", methods=['GET', 'POST'])
def login():
    return oauth.auth0.authorize_redirect(
        redirect_uri=url_for("auth.callback", _external=True)
    )


@auth.route("/callback", methods=["GET", "POST"])
def callback():
    token = oauth.auth0.authorize_access_token()
    # print("******FULL TOKEN = ", token)
#    session["user"] = token
#    session["user"] = token["userinfo"]["email"]
#    return redirect(url_for("auth.home"))
#  OLD CODE BUT WE'RE MANIPULATING IT ---- PT 3/28/2022 ---------
    if not token["userinfo"]["email_verified"]:
        logout_user()
        return render_template("verify.html")
#        return redirect(
#            "https://" + env.get("AUTH0_DOMAIN")
#            + "/v2/logout?"
#            + urlencode(
#                {
#                    #                "returnTo": url_for("auth.home", _external=True),
#                    "returnTo": render_template("verify.html"),
#                    "client_id": env.get("AUTH0_CLIENT_ID"),
#                },
#                quote_via=quote_plus,
#            )
#        )
    if current_user.is_authenticated:
        flash(current_user.get_username() + ', you are already logged in...')
        return redirect(url_for(PAGE_INDEX))
        # Process POST
    form = LoginForm()
#    print("Form = ", form)
#    if form.validate_on_submit():
        # domain = form.domain.data # Never None
    domain = "edi"
#        user_dn = 'uid=' + form.username.data + ',' + Config.DOMAINS[domain]
#    user_dn = 'uid=' + token['id_token'] + ',' + Config.DOMAINS[domain]
    user_dn = 'uid=' + token["userinfo"]["email"] + ',' + Config.DOMAINS[domain]
#    password = form.password.data
    # auth_token = authenticate(user_dn=user_dn, password=password)
    auth_token = token["access_token"]
    if auth_token is not None and auth_token != "teapot":
#        pasta_token = PastaToken(auth_token)
#        uid = pasta_token.uid.split(",")[0]
#        uid = token['id_token']
#        uid = token["userinfo"]["email"]
        uid = "MotherDB"
#        cname = uid.split('=')[1]
        cname = token["userinfo"]["email"]
#        session_id = cname + "*" + pasta_token.uid
        session_id = cname + "*" + uid
#        session_id = "this is a constant * value"
        user = User(session_id)
        login_user(user)
#        initialize_user_data(cname, pasta_token.uid)
        initialize_user_data(cname, uid)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            current_document = get_active_document()
            if current_document:
                next_page = url_for(PAGE_TITLE, filename=current_document)
            else:
                next_page = url_for(PAGE_INDEX)
        return redirect(next_page)
    else:
        return redirect(url_for("auth.home"))
#    elif auth_token == "teapot":
#        accept_url = f"{Config.AUTH}/accept?uid={user_dn}&target={Config.TARGET}"
#        return redirect(accept_url)
#    flash('Invalid username or password')
#    return redirect(url_for(PAGE_LOGIN))
    # Process GET
#    auth_token = request.args.get("token")
#    cname = request.args.get("cname")
#    if auth_token is not None and cname is not None:
#        pasta_token = PastaToken(auth_token)
#        uid = pasta_token.uid
#        session_id = cname + "*" + uid
#        user = User(session_id)
#        login_user(user)
#        initialize_user_data(cname, pasta_token.uid)
#        next_page = request.args.get('next')
#        if not next_page or url_parse(next_page).netloc != '':
#            current_document = get_active_document()
#            if current_document:
#                next_page = url_for(PAGE_TITLE, filename=current_document)
#            else:
#                next_page = url_for(PAGE_INDEX)
#        return redirect(next_page)
#    return render_template(
#        'login.html', form=form, auth=Config.AUTH, target=Config.TARGET
#    )
#--- end of code manipulation pt 3/28/2022 ---#

@auth.route("/logout")
def logout():
    logout_user()
    return redirect(
        "https://" + env.get("AUTH0_DOMAIN")
        + "/v2/logout?"
        + urlencode(
            {
#                "returnTo": url_for("auth.home", _external=True),
                "returnTo": url_for(PAGE_INDEX, _external=True),
                "client_id": env.get("AUTH0_CLIENT_ID"),
            },
            quote_via=quote_plus,
        )
    )


@auth.route("/")
def home():
    print(session.get('user'))
    return render_template("home.html", session=session.get('user'), pretty=json.dumps(session.get('user'), indent=4))


"""
@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        flash(current_user.get_username() + ', you are already logged in...')
        return redirect(url_for(PAGE_INDEX))
    # Process POST
    form = LoginForm()
    if form.validate_on_submit():
        # domain = form.domain.data # Never None
        domain = "edi"
        user_dn = 'uid=' + form.username.data + ',' + Config.DOMAINS[domain]
        password = form.password.data
        #auth_token = authenticate(user_dn=user_dn, password=password)
        auth_token = "dWlkPUVESSxvPUVESSxkYz1lZGlyZXBvc2l0b3J5LGRjPW9yZypodHRwczovL3Bhc3RhLmVkaXJlcG9zaXRvcnkub3JnL2F1dGhlbnRpY2F0aW9uKjE1NTgwOTA3MDM5NDYqYXV0aGVudGljYXRlZA==-yUoVTpyVityVkfqOpGSPosJYzndBMdwoUTGB0osuqyCNOouPxRllz/pRklaEWqi+faNLGHh8Dzh7qrtxTLLDs+MpBXudaJIIQep6PNnvEDgasrTvA9KV/vnKsyDnu4VaJnyuoKGRryP6PXlJs8UTXhtGpRf2vnTM/oifeRx0NB3y7aEv3Xn85ogxl0MaeyXJFeQMAAyN9ahYgJUC4jFgCqYlLj/x0PAlXwq2C/AwnjC/XJ2mxEQm1E/RMY9Z9EjHx+dSruXEs3wQiBbnus7BPvJR84zqEjl3EYpYwmYRkLViDHYoGdbegcDfuUfKv4y5Hun+r0ICNt09nBV4wci3TQ=="
        if auth_token is not None and auth_token != "teapot":
            pasta_token = PastaToken(auth_token)
            uid = pasta_token.uid.split(",")[0]
            cname = uid.split('=')[1]
            session_id = cname + "*" + pasta_token.uid
            user = User(session_id)
            login_user(user)
            initialize_user_data(cname, pasta_token.uid)
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
        initialize_user_data(cname, pasta_token.uid)
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
"""
