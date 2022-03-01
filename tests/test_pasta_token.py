#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
:Mod: test_pasta_token

:Synopsis:

:Author:
    servilla

:Created:
    12/1/21
"""
import pytest

from webapp.auth.pasta_token import PastaToken


def test_pasta_token():
    auth_token = "dWlkPUVESSxvPUVESSxkYz1lZGlyZXBvc2l0b3J5LGRjPW9yZypodHRwczovL3Bhc3RhLmVkaXJlcG9zaXRvcnkub3JnL2F1dGhlbnRpY2F0aW9uKjE1NTgwOTA3MDM5NDYqYXV0aGVudGljYXRlZA==-yUoVTpyVityVkfqOpGSPosJYzndBMdwoUTGB0osuqyCNOouPxRllz/pRklaEWqi+faNLGHh8Dzh7qrtxTLLDs+MpBXudaJIIQep6PNnvEDgasrTvA9KV/vnKsyDnu4VaJnyuoKGRryP6PXlJs8UTXhtGpRf2vnTM/oifeRx0NB3y7aEv3Xn85ogxl0MaeyXJFeQMAAyN9ahYgJUC4jFgCqYlLj/x0PAlXwq2C/AwnjC/XJ2mxEQm1E/RMY9Z9EjHx+dSruXEs3wQiBbnus7BPvJR84zqEjl3EYpYwmYRkLViDHYoGdbegcDfuUfKv4y5Hun+r0ICNt09nBV4wci3TQ=="
    pasta_token = PastaToken(auth_token)
    valid_ttl = pasta_token.is_valid_ttl()
    ttl = pasta_token.ttl_to_iso()
