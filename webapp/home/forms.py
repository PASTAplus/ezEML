  #!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: forms.py

:Synopsis:

:Author:
    servilla
    costa

:Created:
    7/20/18
"""

import hashlib
from flask_wtf import FlaskForm

from wtforms import (
    StringField, SelectField, HiddenField
)

from wtforms.validators import (
    DataRequired, Regexp
)


class EDIForm(FlaskForm):
    # @classmethod
    # def init_md5(cls, init_str):
    #     cls.md5 = HiddenField(hashlib.md5(init_str.encode('utf-8')).hexdigest())
    md5 = HiddenField('')
    init_str = ''

    def init_md5(self):
        self.md5.data = hashlib.md5(self.init_str.encode('utf-8')).hexdigest()

    def field_data(self):
        fields = []
        for key, val in self.data.items():
            if key not in ('md5', 'csrf_token'):
                fields.append(val)
        return tuple(fields)


def concat_str(form):
    concat_str = ''
    if form:
        field_data = form.field_data()
        if field_data:
            for val in field_data:
                if val:
                    concat_str += str(val)
    return concat_str


def form_md5(form):
    form_str = concat_str(form)
    md5 = hashlib.md5(form_str.encode('utf-8')).hexdigest()
    return md5


def init_form_md5(form):
    form.md5.data = form_md5(form)


def is_dirty_form(form):
    is_dirty = False
    if form:
        md5 = form_md5(form)
        hidden_md5 = form.md5.data 
        is_dirty = (md5 != hidden_md5)
    return is_dirty


class CreateEMLForm(FlaskForm):
    packageid = StringField('Package ID', 
                            validators=[DataRequired(), Regexp(r'^[a-z][a-z\-]+\.\d+\.\d+$', message='Invalid package ID value')])

class DeleteEMLForm(FlaskForm):
    packageid = SelectField('Data Package Identifier', choices=[])


class DownloadEMLForm(FlaskForm):
    packageid = SelectField('Data Package Identifier', choices=[])


class LoadDataForm(FlaskForm):
    pass


class LoadMetadataForm(FlaskForm):
    pass


class OpenEMLDocumentForm(FlaskForm):
    packageid = SelectField('Data Package Identifier', choices=[])


class SaveAsForm(FlaskForm):
    packageid = StringField('Package ID', validators=[DataRequired()])
