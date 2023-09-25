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
import hashlib

from flask_login import UserMixin

from webapp import login
from webapp.auth.user_data import (
    set_active_packageid, get_active_packageid,
    set_active_document, get_active_document,
    set_active_document_owner, get_active_document_owner
)
from webapp.config import Config
import webapp.views.collaborations.collaborations as collaborations
from webapp.home.home_utils import log_error, log_info


class User(UserMixin):

    def __init__(self, session_id: str):
        self._session_id = session_id
        try:
            self._cname, self._uid = self._session_id.split("*")
        except ValueError as ex:
            log_error(ex)
            token64 = self._session_id.split('-')[0]
            token = base64.b64decode(token64).decode('utf-8')
            self._uid = token.split('*')[0]
            self._cname = self._uid.split(',')[0].split("=")[1]
            self._session_id = self._cname + "*" + self._uid

    def get_cname(self):
        return self._cname

    def get_id(self):
        return self._session_id

    def get_dn(self):
        return self._uid

    def get_username(self):
        return self._cname

    def get_user_org(self):
        uid_hash = hashlib.md5(self._uid.encode("utf-8")).hexdigest()
        cname_clean = self._cname.replace(" ", "_")
        user_org = cname_clean + "-" + uid_hash
        return user_org

    def get_user_login(self):
        return self.get_user_org()

    def get_packageid(self):
        return get_active_packageid()

    def set_packageid(self, packageid:str=None):
        set_active_packageid(packageid)

    def get_filename(self):
        return get_active_document()

    def set_filename(self, filename: str = None):
        set_active_document(filename)

    def get_file_owner(self):
        return get_active_document_owner()

    def set_file_owner(self, owner: str = None, owner_login: str = None):
        set_active_document_owner(owner, owner_login=owner_login)

    def is_edi_user(self):
        return self._cname == "EDI" and self._uid == "uid=EDI,o=EDI,dc=edirepository,dc=org"

    def is_admin(self):
        try:
            return self.get_username() in Config.ADMIN_LOGINS
        except AttributeError:
            return False

    def is_beta_tester(self):
        try:
            return self.get_username() in Config.BETA_TESTER_LOGINS
        except AttributeError:
            return False

    def is_edi_curator(self):
        return collaborations.is_edi_curator(self.get_user_login())

    def is_data_curator(self):
        try:
            return self.get_username() in Config.DATA_CURATOR_LOGINS
        except AttributeError:
            return False

    def is_whitelisted_user(self):
        try:
            if Config.SERVER_LOGINS_WHITELIST:
                return self.get_username() in Config.SERVER_LOGINS_WHITELIST
            else:
                return True
        except AttributeError:
            return False


@login.user_loader
def load_user(session_id):
    return User(session_id)
