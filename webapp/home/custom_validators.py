  #!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: custom_validators.py

:Synopsis:

:Author:
    costa

:Created:
    3/5/19
"""

from wtforms import (
    validators, ValidationError
)

def valid_length(min:int=10, max:int=1000):
    message = f'Must be between {min} and {max} characters long'

    def _valid_length(form, field):
        l = field.data and len(field.data) or 0
        if l < min or max != -1 and l > max:
            raise ValidationError(message)

    return _valid_length


def valid_min_length(min:int=10):
    message = f'Must be a minimum of {min} characters long'

    def _valid_min_length(form, field):
        l = field.data and len(field.data) or 0
        if l < min:
            raise ValidationError(message)

    return _valid_min_length


def valid_latitude(min:float=-90.0, max:float=90.0):
    message = f'Latitude must be between {min} and {max}'

    def _valid_latitude(form, field):
        if field.data is not None:
            l = float(field.data)
            if l < min or l > max:
                raise ValidationError(message)
        # else:
        #     raise ValidationError("Missing value")
           

    return _valid_latitude
    

def valid_longitude(min:float=-180.0, max:float=180.0):
    message = f'Longitude must be between {min} and {max}'

    def _valid_longitude(form, field):
        if field.data is not None:
            l = float(field.data)
            if l < min or l > max:
                raise ValidationError(message)
        # else:
        #     raise ValidationError("Missing value")

    return _valid_longitude
