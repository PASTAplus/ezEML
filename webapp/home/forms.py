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
    StringField, SelectField, SelectMultipleField, HiddenField, RadioField, widgets
)

from wtforms.validators import (
    DataRequired, Email, Optional
)

from wtforms.widgets import TextArea


class EDIForm(FlaskForm):
    # @classmethod
    # def init_md5(cls, init_str):
    #     cls.md5 = HiddenField(hashlib.md5(init_str.encode('utf-8')).hexdigest())
    md5 = HiddenField('')
    init_str = ''

    def init_md5(self):
        self.md5.data = hashlib.md5(self.init_str.encode('utf-8')).hexdigest()

    def field_data(self):
        fields = [
            val
            for key, val in self.data.items()
            if key not in ('md5', 'csrf_token')
        ]
        return tuple(fields)


def concat_str(form):
    concat_str = ''
    if form:
        field_data = form.field_data()
        if field_data:
            i = 0  # we interleave the field index so we can detect if a field's value is cut-and-pasted to another field
            for val in field_data:
                if val:
                    concat_str += str(i) + str(val)
                    i += 1
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


class CheckboxField(SelectField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class MultiCheckboxField(SelectMultipleField):
    """
    A multiple-select, except displays a list of checkboxes.

    Iterating the field will produce subfields, allowing custom rendering of
    the enclosed checkbox fields.
    """
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class ImportEMLForm(FlaskForm):
    filename = SelectField('Document Name', choices=[])


class ImportPackageForm(FlaskForm):
    pass


class ImportItemsForm(FlaskForm):
    to_import = MultiCheckboxField('Import', choices=[], validators=[])


class ImportEMLItemsForm(FlaskForm):
    to_import = MultiCheckboxField('Import', choices=[], validators=[])
    target = RadioField('Target', choices=[], validators=[])


class ImportEMLTargetForm(FlaskForm):
    target = RadioField('Target', choices=[])


class CreateEMLForm(FlaskForm):
    filename = StringField('Document Name', validators=[DataRequired()])


class DeleteEMLForm(FlaskForm):
    filename = SelectField('Document Name', choices=[])


class DownloadEMLForm(FlaskForm):
    filename = StringField('Document Name', validators=[DataRequired()])


class LoadDataForm(FlaskForm):
    # num_header_rows = IntegerField('Number of Header Lines', default=1)
    delimiter = SelectField('Field Delimiter', choices=[
        (',', 'comma'),
        ('\\t', 'tab'),
        ('|', 'vertical bar, or pipe - |'),
        (';', 'semicolon'),
        (':', 'colon')
    ], default=','
    )
    quote = SelectField('Quote Character', choices=[
        ('"', 'double quote - "'),
        ("'", "single quote - '")
    ], default='"'
    )


class LoadOtherEntityForm(FlaskForm):
    pass


class LoadMetadataForm(FlaskForm):
    pass


class OpenEMLDocumentForm(FlaskForm):
    filename = SelectField('Document Name', choices=[])


class SaveAsForm(FlaskForm):
    filename = StringField('Document Name', validators=[DataRequired()])


class SubmitToEDIForm(FlaskForm):
    name = StringField('Your Name *', validators=[DataRequired()])
    email_address = StringField('Your Email Address *', validators=[Email(), DataRequired()])
    notes = StringField('Notes for EDI Data Curators (Optional)', widget=TextArea(), validators=[Optional()])
