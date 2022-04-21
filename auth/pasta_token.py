#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: pasta_token

:Synopsis:

:Author:
    servilla

:Created:
    2020-09-23
"""
import base64

import daiquiri
import pendulum


logger = daiquiri.getLogger('pasta_token: ' + __name__)


class PastaToken(object):

    def __init__(self, auth_token: str):
        t_b64 = auth_token.split('-')[0]
        t = (base64.b64decode(t_b64)).decode('utf-8')
        token = t.split('*')
        self._token = dict()
        self._token['uid'] = token[0]
        self._token['system'] = token[1]
        self._token['ttl'] = token[2]
        self._token['groups'] = token[3]

    @property
    def groups(self) -> str:
        return self._token['groups']

    @property
    def system(self) -> str:
        return self._token['system']

    @property
    def ttl(self) -> str:
        return self._token['ttl']

    @property
    def uid(self) -> str:
        return self._token['uid']

    def to_b64(self):
        return base64.b64encode(self.to_string().encode('utf-8'))

    def to_string(self) -> str:
        token = list()
        for t in self._token:
            if self._token[t] != '':
                token.append(self._token[t])
        return '*'.join(token)

    def is_valid_ttl(self) -> bool:
        now = int(pendulum.now().timestamp() * 1000)
        delta = int(self._token['ttl']) - now
        return delta > 1

    def ttl_to_iso(self) -> str:
        dt = pendulum.from_timestamp(int(self._token['ttl']) * 0.001,
                                     tz='America/Denver')
        return dt.to_iso8601_string()
