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
    FloatField, IntegerField
)

from wtforms.validators import DataRequired, Email, URL
from wtforms.widgets import TextArea


class AbstractForm(FlaskForm):
    abstract = StringField('Abstract', widget=TextArea(), validators=[])


class AttributeSelectForm(FlaskForm):
    pass


class AttributeForm(FlaskForm):
    attribute_name = StringField('Name', validators=[])
    attribute_label = StringField('Label (Optional)', validators=[])
    attribute_definition = StringField('Definition', validators=[])
    storage_type = StringField('Storage Type (Optional)', validators=[])
    storage_type_system = StringField('Storage Type System (Optional)', validators=[])
    code_1 = StringField('1. Code', validators=[])
    code_explanation_1 = StringField('Explanation', validators=[])
    code_2 = StringField('2. Code', validators=[])
    code_explanation_2 = StringField('Explanation', validators=[])
    code_3 = StringField('3. Code', validators=[])
    code_explanation_3 = StringField('Explanation', validators=[])


class CreateEMLForm(FlaskForm):
    packageid = StringField('Package ID', validators=[DataRequired()])


class DataTableSelectForm(FlaskForm):
    pass


class DataTableForm(FlaskForm):
    entity_name = StringField('Name', validators=[])
    entity_description = StringField('Description (Optional)', validators=[])
    object_name = StringField('Object Name', validators=[])
    size = StringField('Size (Optional)', validators=[])
    num_header_lines = StringField('Number of Header Lines (Optional)', validators=[])
    record_delimiter = StringField('Record Delimiter (Optional)', validators=[])
    attribute_orientation = SelectField('Attribute Orientation', choices=[("column", "column"), ("row", "row")])
    field_delimiter = SelectField('Simple Delimited: Field Delimiter', choices=[("comma", "comma"), ("space", "space"), ("tab", "tab")])
    case_sensitive = SelectField('Case Sensitive', choices=[("no", "no"), ("yes", "yes")])
    number_of_records = StringField('Number of Records (Optional)', validators=[])
    online_url = StringField('Online Distribution URL', validators=[])


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
