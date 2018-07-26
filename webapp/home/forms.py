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

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, \
    SelectField
from wtforms.validators import DataRequired, Email, EqualTo, Length
from wtforms.widgets import TextArea


class CreateEMLForm(FlaskForm):
    packageid = StringField('Package ID', validators=[DataRequired()])
    title = StringField('Title', validators=[DataRequired()])
    abstract = StringField('Abstract', widget=TextArea())


class KeywordsForm(FlaskForm):
    k01 = StringField('Keyword', validators=[])
    k02 = StringField('Keyword', validators=[])
    k03 = StringField('Keyword', validators=[])
    k04 = StringField('Keyword', validators=[])
    k05 = StringField('Keyword', validators=[])
    k06 = StringField('Keyword', validators=[])
    k07 = StringField('Keyword', validators=[])
    k08 = StringField('Keyword', validators=[])


class MinimalEMLForm(FlaskForm):
    packageid = StringField('Package ID', validators=[DataRequired()])
    title = StringField('Title', validators=[DataRequired()])
    creator_gn = StringField('Creator given name', validators=[DataRequired()])
    creator_sn = StringField('Creator surname', validators=[DataRequired()])
    contact_gn = StringField('Contact given name', validators=[DataRequired()])
    contact_sn = StringField('Contact surname', validators=[DataRequired()])
