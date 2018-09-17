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


class DataTableSelectForm(FlaskForm):
    pass


class DataTableForm(FlaskForm):
    pass


class GeographicCoverageSelectForm(FlaskForm):
    pass


class GeographicCoverageForm(FlaskForm):
    geographic_description = StringField('Geographic Description', widget=TextArea(), validators=[])
    # Declaring these as FloatField forces the user to input a floating point value,
    # preventing the user from leaving the field empty when they leave the form.
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


class TaxonomicCoverageSelectForm(FlaskForm):
    pass


class TaxonomicCoverageForm(FlaskForm):
    general_taxonomic_coverage = StringField('General Taxonomic Coverage', validators=[])
    kingdom_value = StringField('Kingdom', validators=[])
    kingdom_common_name = StringField('Common Name', validators=[])
    phylum_value =  StringField('Phylum', validators=[])
    phylum_common_name = StringField('Common Name', validators=[])
    class_value = StringField('Class', validators=[])
    class_common_name = StringField('Common Name', validators=[])
    order_value = StringField('Order', validators=[])
    order_common_name = StringField('Common Name', validators=[])
    family_value = StringField('Family', validators=[])
    family_common_name = StringField('Common Name', validators=[])
    genus_value = StringField('Genus', validators=[])
    genus_common_name = StringField('Common Name', validators=[])
    species_value = StringField('Species', validators=[])
    species_common_name = StringField('Common Name', validators=[])       


class TemporalCoverageSelectForm(FlaskForm):
    pass


class TemporalCoverageForm(FlaskForm):
    begin_date = StringField('Begin Date', validators=[])
    end_date = StringField('End Date', validators=[])


class TitleForm(FlaskForm):
    title = StringField('Title', validators=[])


class MinimalEMLForm(FlaskForm):
    packageid = StringField('Package ID', validators=[DataRequired()])
    title = StringField('Title', validators=[DataRequired()])
    creator_gn = StringField('Creator given name', validators=[DataRequired()])
    creator_sn = StringField('Creator surname', validators=[DataRequired()])
    contact_gn = StringField('Contact given name', validators=[DataRequired()])
    contact_sn = StringField('Contact surname', validators=[DataRequired()])
