  #!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: custom_validators.py

:Synopsis:

:Author:
    costa
    ide

:Created:
    3/5/19
"""

import math

from wtforms import (
    validators, ValidationError, IntegerField
)

from metapype.model.node import Node
from metapype.eml.evaluation_warnings import EvaluationWarning

from webapp.home import motherpype_names as names

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
    message = f'Latitude must be a decimal value between {min} and {max}'

    def _valid_latitude(form, field):
        if field.data is not None:
            l = float(field.data)
            if l < min or l > max or math.isnan(l):
                raise ValidationError(message)
        # else:
        #     raise ValidationError("Missing value")
           

    return _valid_latitude
    

def valid_longitude(min:float=-180.0, max:float=180.0):
    message = f'Longitude must be a decimal value between {min} and {max}'

    def _valid_longitude(form, field):
        if field.data is not None:
            l = float(field.data)
            if l < min or l > max or math.isnan(l):
                raise ValidationError(message)
        # else:
        #     raise ValidationError("Missing value")

    return _valid_longitude

class IntegerField(IntegerField):
    def process_formdata(self, valuelist):
        if not valuelist:
            return

        try:
            self.data = int(valuelist[0])
        except ValueError as exc:
            self.data = None

def _intellectual_rights_rule(node: Node) -> list:
    evaluation = []
    rights = False
    for child in node.children:
        if child.name == names.INTELLECTUAL_RIGHTS and child.content:
            rights = True
    if not rights:
        evaluation.append((
            EvaluationWarning.INTELLECTUAL_RIGHTS_MISSING,
            f'Intellectual Rights are recommended.',
            node
        ))
    return evaluation

def _donor_rule(node: Node) -> list:
    evaluation = []
    id = age = days = years = gender = False
    for child in node.children:
        if child.name == names.DONOR_ID and child.content:
            id = True
        if child.name == names.DONOR_AGE and child.content:
            age = True
        if child.name == names.DONOR_DAYS and child.content:
            days = True
        if child.name == names.DONOR_YEARS and child.content:
            years = True
        if child.name == names.DONOR_GENDER and child.content:
            gender = True
    if not id:
        evaluation.append((
            EvaluationWarning.DONOR_ID_MISSING,
            f'A Donor ID is recommended.',
            node
        ))
    if not age:
        evaluation.append((
            EvaluationWarning.DONOR_AGE_MISSING,
            f'A Donor age is recommended.',
            node
        ))
    if not days:
        evaluation.append((
            EvaluationWarning.DONOR_DAYS_MISSING,
            f'Days are recommended.',
            node
        ))
    if not years:
        evaluation.append((
            EvaluationWarning.DONOR_YEARS_MISSING,
            f'Donor years are recommended.',
            node
        ))
    if not gender:
        evaluation.append((
            EvaluationWarning.DONOR_GENDER_MISSING,
            f'A Donor gender is recommended.',
            node
        ))
    return evaluation


  # Rule function pointers
rules = {
    names.INTELLECTUAL_RIGHTS: _intellectual_rights_rule,
    # names.DONOR: _donor_rule,
}