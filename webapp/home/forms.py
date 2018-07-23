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


class MinimalEMLForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    contact_gn = StringField('Contact given name', validators=[DataRequired()])
    contact_sn = StringField('Contact surname', validators=[DataRequired()])
    creator_gn = StringField('Creator given name', validators=[DataRequired()])
    creator_sn = StringField('Creator surname', validators=[DataRequired()])
