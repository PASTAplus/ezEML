"""
Custom validators for WTForms.
"""

import math

from wtforms import (
    ValidationError
)

def valid_length(min_len:int=10, max_len:int=1000):
    message = f'Must be between {min_len} and {max_len} characters long'

    def _valid_length(form, field):
        l = field.data and len(field.data) or 0
        if l < min_len or max_len != -1 and l > max_len:
            raise ValidationError(message)

    return _valid_length


def valid_min_length(min_len:int=10):
    message = f'Must be a minimum of {min_len} characters long'

    def _valid_min_length(form, field):
        l = field.data and len(field.data) or 0
        if l < min_len:
            raise ValidationError(message)

    return _valid_min_length


def valid_latitude(min_val:float=-90.0, max_val:float=90.0):
    message = f'Latitude must be a decimal value between {min_val} and {max_val}'

    def _valid_latitude(form, field):
        if field.data is not None:
            l = float(field.data)
            if l < min_val or l > max_val or math.isnan(l):
                raise ValidationError(message)
        # else:
        #     raise ValidationError("Missing value")
           

    return _valid_latitude
    

def valid_longitude(min_val:float=-180.0, max_val:float=180.0):
    message = f'Longitude must be a decimal value between {min_val} and {max_val}'

    def _valid_longitude(form, field):
        if field.data is not None:
            l = float(field.data)
            if l < min_val or l > max_val or math.isnan(l):
                raise ValidationError(message)
        # else:
        #     raise ValidationError("Missing value")

    return _valid_longitude
