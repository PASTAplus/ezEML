#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: token_uid

:Synopsis:

:Author:
    servilla

:Created:
    5/24/18
"""
import base64
import os

import daiquiri
import nacl.encoding
import nacl.signing
import nacl.hash
import pendulum


logger = daiquiri.getLogger('token_uid: ' + __name__)


def is_expired(ttl, expiry):
    timestamp = pendulum.fromtimestamp(float(ttl))
    future = timestamp.add(minutes=expiry).timestamp()
    now = pendulum.now().timestamp()
    return future <= now


def decode_token(token):
    token_file = './tokens/' + token
    try:
        with open(token_file, 'r') as t:
            token_pair = t.read()
        uid, ttl = token_pair.split(',')
        return uid, ttl
    except Exception as e:
        logger.error(e)
    return None, None


def remove_token(token=None):
    try:
        token_file = './tokens/' + token
        os.remove(token_file)
    except Exception as e:
        logger.error(e)


def to_token(uid=None):
    HASHER = nacl.hash.sha256
    timestamp = str(pendulum.now().timestamp())
    token_pair = uid + ',' + timestamp
    token = HASHER(token_pair.encode(), encoder=nacl.encoding.HexEncoder)
    token_file = './tokens/' + token.decode()
    with open(token_file, 'w') as t:
        t.write(token_pair)
    return token


class TTLException(Exception):
    pass


def main():

    return 0


if __name__ == "__main__":
    main()
