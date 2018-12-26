#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: user

:Synopsis:

:Author:
    servilla

:Created:
    3/7/18
"""
import base64

import daiquiri
from flask_login import UserMixin
import requests

from webapp import (
    login
)

from webapp.auth.user_data import (
    set_active_packageid, get_active_packageid
)

from webapp.config import Config

logger = daiquiri.getLogger('user.py: ' + __name__)


class User(UserMixin):

    def __init__(self, auth_token=None):
        self._auth_token = auth_token

    @staticmethod
    def authenticate(user_dn=None, password=None):
        auth_token = None
        r = requests.get(Config.PASTA_URL, auth=(user_dn, password))
        if r.status_code == requests.codes.ok:
            auth_token = r.cookies['auth-token']
        return auth_token

    def get_id(self):
        return self._auth_token

    def get_dn(self):
        token64 = self._auth_token.split('-')[0]
        token = base64.b64decode(token64).decode('utf-8')
        dn = token.split('*')[0]
        return dn

    def get_organization(self):
        dn = self.get_dn()
        o = dn.split(',')[1]
        organization = o.split('=')[1]
        return organization

    def get_uid(self):
        dn = self.get_dn()
        uid = dn.split(',')[0]
        return uid

    def get_username(self):
        uid = self.get_uid()
        username = uid.split('=')[1]
        return username

    def get_user_org(self):
        user_org = None
        try:
            username = self.get_username()
            organization = self.get_organization()
            user_org = f'{username}-{organization}'
        except AttributeError:
            pass
        return user_org
    
    def get_packageid(self):
        packageid = get_active_packageid()
        return packageid

    def set_packageid(self, packageid:str=None):
        set_active_packageid(packageid)


@login.user_loader
def load_user(id):
    auth_token = id
    return User(auth_token=auth_token)
