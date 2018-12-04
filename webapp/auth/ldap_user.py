#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: ldap_user

:Synopsis:

:Author:
    servilla
    costa

:Created:
    5/22/18
"""
import random
import string

import daiquiri
from ldap3 import Server, Connection, ALL, HASHED_SALTED_SHA, MODIFY_REPLACE
from ldap3.utils.hashed import hashed

from webapp.config import Config
from webapp.auth import token_uid

logger = daiquiri.getLogger('ldap_user: ' + __name__)



class LdapUser(object):

    def __init__(self, uid=None):
        self._uid = uid
        self._gn = None
        self._sn = None
        self._email = None
        self._cn = None
        self._password = None
        if self._uid is not None:
            if not self._load_attributes():
                msg = 'Unknown UID: {0}'.format(self._uid)
                raise UidError(msg)

    @property
    def uid(self):
        return self._uid

    @uid.setter
    def uid(self, uid):
        self._uid = uid

    @property
    def gn(self):
        return self._gn

    @gn.setter
    def gn(self, gn=None):
        self._gn = gn

    @property
    def sn(self):
        return self._sn

    @sn.setter
    def sn(self, sn=None):
        self._sn = sn

    @property
    def cn(self):
        return self._cn

    @property
    def password(self):
        return self._password

    @password.setter
    def password(self, password=None):
        self._password = password

    @property
    def email(self):
        return self._email

    @email.setter
    def email(self, email=None):
        self._email = email

    @property
    def token(self):
        return token_uid.to_token(uid = self._uid)

    def _load_attributes(self):
        result = False
        dn = Config.LDAP_DN.replace(Config.LDAP_UID, self._uid)
        attributes = ['givenName', 'sn', 'mail']
        filter = '(&(objectclass=inetOrgPerson)(uid={uid}))'.format(uid=self._uid)
        server = Server(Config.LDAP, use_ssl=True, get_info=ALL)
        try:
            conn = Connection(server=server, user=Config.LDAP_ADMIN,
                              password=Config.LDAP_ADMIN_PASSWORD,
                              auto_bind=True, receive_timeout=30)
            if conn.search(dn, filter, attributes=attributes):
                entry = conn.entries[0]
                self._gn = entry['givenName'].values[0]
                self._sn = entry['sn'].values[0]
                self._email = entry['mail'].values[0]
                self._cn = self._gn + ' ' + self._sn
                result = True
            conn.unbind()
        except Exception as e:
            logger.error(e)
        return result


    def _none_attributes(self):
        none_attributes = []
        if self._uid is None: none_attributes.append('uid')
        if self._gn is None: none_attributes.append('gn')
        if self._sn is None: none_attributes.append('sn')
        if self._email is None: none_attributes.append('email')
        return none_attributes

    def _random_password(self):
        chars = string.ascii_uppercase + string.ascii_lowercase + string.digits
        password = ''.join(random.choice(chars) for x in range(24))
        return password

    def _valid_password(self):
        result = False
        dn = Config.LDAP_DN.replace(Config.LDAP_UID, self._uid)
        server = Server(Config.LDAP, use_ssl=True, get_info=ALL)
        try:
            conn = Connection(server=server, user=dn, password=self._password,
                              auto_bind=True, receive_timeout=30)
            result = True
            conn.unbind()
        except Exception as e:
            logger.error(e)
        return result


class LdapError(Exception):
    pass

class UidError(LdapError):
    pass

class AttributeError(LdapError):
    pass


def main():
    return 0


if __name__ == "__main__":
    main()
