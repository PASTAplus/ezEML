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

from wtforms import (
    StringField, PasswordField, BooleanField, SubmitField, SelectField,
    FloatField
)

from wtforms.validators import DataRequired, Email, URL
from wtforms.widgets import TextArea


class AbstractForm(FlaskForm):
    abstract = StringField('Abstract', widget=TextArea(), validators=[])


class CreateEMLForm(FlaskForm):
    packageid = StringField('Package ID', validators=[DataRequired()])


class GeographicCoverageSelectForm(FlaskForm):
    pass


class GeographicCoverageForm(FlaskForm):
    geographic_description = StringField('Geographic Description', widget=TextArea(), validators=[])
    wbc = FloatField('West Bounding Coordinate', validators=[])
    ebc = FloatField('East Bounding Coordinate', validators=[])
    nbc = FloatField('North Bounding Coordinate', validators=[])
    sbc = FloatField('South Bounding Coordinate', validators=[])


class KeywordsForm(FlaskForm):
    keyword = StringField('Keyword', validators=[])
    keyword_type = SelectField('Keyword Type (Optional)', 
                               choices=[("", ""), 
                                        ("place", "place"), 
                                        ("stratum", "stratum"), 
                                        ("taxonomic", "taxonomic"), 
                                        ("temporal", "temporal"), 
                                        ("theme", "theme")])


class PubDateForm(FlaskForm):
    pubdate = StringField('Publication Date', validators=[])


class ResponsiblePartySelectForm(FlaskForm):
    pass


class ResponsiblePartyForm(FlaskForm):
    salutation = StringField('Salutation', validators=[])
    gn = StringField('First Name', validators=[])
    sn = StringField('Last Name', validators=[])
    organization = StringField('Organization', validators=[])
    position_name = StringField('Position Name', validators=[])
    address_1 = StringField('Address 1', validators=[])
    address_2 = StringField('Address 2', validators=[])
    city = StringField('City', validators=[])
    state = StringField('State', validators=[])
    postal_code = StringField('Postal Code', validators=[])
    country = StringField('Country', validators=[])
    phone = StringField('Phone', validators=[])
    fax = StringField('Fax', validators=[])
    email = StringField('Email', validators=[])
    online_url = StringField('Online URL', validators=[])


class TitleForm(FlaskForm):
    title = StringField('Title', validators=[])


class MinimalEMLForm(FlaskForm):
    packageid = StringField('Package ID', validators=[DataRequired()])
    title = StringField('Title', validators=[DataRequired()])
    creator_gn = StringField('Creator given name', validators=[DataRequired()])
    creator_sn = StringField('Creator surname', validators=[DataRequired()])
    contact_gn = StringField('Contact given name', validators=[DataRequired()])
    contact_sn = StringField('Contact surname', validators=[DataRequired()])
