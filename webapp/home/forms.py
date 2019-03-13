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
    StringField, PasswordField, BooleanField, SubmitField, SelectField,
    FloatField, IntegerField, DateField, DateTimeField, RadioField,
    HiddenField
)

from wtforms.validators import (
    DataRequired, Email, InputRequired, URL, Optional, Regexp
)

from wtforms.widgets import TextArea

from webapp.home.custom_validators import (
    valid_length, valid_min_length, valid_latitude, valid_longitude
)

from webapp.home.intellectual_rights import (
    INTELLECTUAL_RIGHTS_CC0, INTELLECTUAL_RIGHTS_CC_BY
)


def concat_str(form):
    concat_str = ''
    if form:
        field_data = form.field_data()
        for val in field_data:
            if val:
                concat_str += str(val)

    print(f"concat_str: {concat_str}")
    return concat_str


def form_md5(form):
    form_str = concat_str(form)
    md5 = hashlib.md5(form_str.encode('utf-8')).hexdigest()
    return md5


def is_dirty_form(form):
    is_dirty = False
    if form:
        md5 = form_md5(form)
        hidden_md5 = form.md5.data 
        is_dirty = (md5 != hidden_md5)
    return is_dirty


class AbstractForm(FlaskForm):
    abstract = StringField('Abstract', widget=TextArea(), 
                           validators=[Optional(), valid_min_length(min=20)])
    md5 = HiddenField('')

    def field_data(self)->set:
        return {self.abstract.data}


class AccessSelectForm(FlaskForm):
    pass


class AccessForm(FlaskForm):
    userid = StringField('User ID', validators=[])
    permission = SelectField('Permission', 
                             choices=[("all", "all"), ("changePermission", "changePermission"), ("read", "read"), ("write", "write")])
    md5 = HiddenField('')

    def field_data(self)->set:
        return {self.userid.data, self.permission.data}


class AttributeSelectForm(FlaskForm):
    pass


class AttributeForm(FlaskForm):
    attribute_name = StringField('Name', validators=[])
    attribute_label = StringField('Label (Optional)', validators=[])
    attribute_definition = StringField('Definition', validators=[])
    storage_type = StringField('Storage Type (Optional)', validators=[])
    storage_type_system = StringField('Storage Type System (Optional)', validators=[])
    mscale = SelectField('Measurement Scale', choices=[("nominal or ordinal", "nominal or ordinal"), 
                                                       ("ratio or interval", "ratio or interval"), 
                                                       ("dateTime", "dateTime")
                                                      ])
    code_1 = StringField('Missing Value Code', validators=[])
    code_explanation_1 = StringField('Explanation', validators=[]) 
    code_2 = StringField('Missing Value Code', validators=[])
    code_explanation_2 = StringField('Explanation', validators=[])
    code_3 = StringField('Missing Value Code', validators=[])
    code_explanation_3 = StringField('Explanation', validators=[])
    md5 = HiddenField('')

    def field_data(self)->set:
        return {self.attribute_name.data, 
                self.attribute_label.data,
                self.attribute_definition.data,
                self.storage_type.data,
                self.storage_type_system.data,
                self.mscale.data,
                self.code_1.data,
                self.code_explanation_1.data,
                self.code_2.data,
                self.code_explanation_2.data,
                self.code_3.data,
                self.code_explanation_3.data}


class CodeDefinitionSelectForm(FlaskForm):
    pass


class CodeDefinitionForm(FlaskForm):
    code = StringField('Code', validators=[])
    definition = StringField('Definition', validators=[])
    order = IntegerField('Order (Optional)', validators=[Optional()])
    md5 = HiddenField('')

    def field_data(self)->set:
        return {self.code.data, self.definition.data, self.order.data}


class CreateEMLForm(FlaskForm):
    packageid = StringField('Package ID', 
                            validators=[DataRequired(), Regexp(r'^[a-z][a-z\-]+\.\d+\.\d+$', message='Invalid package ID value')])


class DataTableSelectForm(FlaskForm):
    pass


class DataTableForm(FlaskForm):
    entity_name = StringField('Name', validators=[])
    entity_description = StringField('Description (Optional)', validators=[])
    object_name = StringField('Object Name', validators=[])
    size = IntegerField('Size (Optional)', validators=[Optional()])
    num_header_lines = IntegerField('Number of Header Lines (Optional)', validators=[Optional()])
    record_delimiter = StringField('Record Delimiter (Optional)', validators=[])
    attribute_orientation = SelectField('Attribute Orientation', choices=[("column", "column"), ("row", "row")])
    field_delimiter = SelectField('Simple Delimited: Field Delimiter', choices=[("comma", "comma"), ("space", "space"), ("tab", "tab")])
    case_sensitive = SelectField('Case Sensitive', choices=[("no", "no"), ("yes", "yes")])
    number_of_records = IntegerField('Number of Records (Optional)', validators=[Optional()])
    online_url = StringField('Online Distribution URL', validators=[Optional(), URL()])
    md5 = HiddenField('')

    def field_data(self)->set:
        return {self.entity_name.data, 
                self.entity_description.data, 
                self.object_name.data, 
                self.size.data, 
                self.num_header_lines.data, 
                self.record_delimiter.data, 
                self.attribute_orientation.data, 
                self.field_delimiter.data, 
                self.case_sensitive.data, 
                self.number_of_records.data, 
                self.online_url.data}


class DeleteEMLForm(FlaskForm):
    packageid = SelectField('Data Package Identifier', choices=[])


class DownloadEMLForm(FlaskForm):
    packageid = SelectField('Data Package Identifier', choices=[])


class GeographicCoverageSelectForm(FlaskForm):
    pass


class GeographicCoverageForm(FlaskForm):
    geographic_description = StringField('Geographic Description', widget=TextArea(), 
                                         validators=[valid_min_length(min=20)])
    # Declaring these as FloatField forces the user to input a floating point value,
    # preventing the user from leaving the field empty when they leave the form.
    wbc = FloatField('West Bounding Coordinate', validators=[valid_longitude()])
    ebc = FloatField('East Bounding Coordinate', validators=[valid_longitude()])
    nbc = FloatField('North Bounding Coordinate', validators=[valid_latitude()])
    sbc = FloatField('South Bounding Coordinate', validators=[valid_latitude()])
    md5 = HiddenField('')

    def field_data(self)->set:
        return {self.geographic_description.data,
                self.wbc.data, 
                self.ebc.data, 
                self.nbc.data, 
                self.sbc.data}


class IntellectualRightsForm(FlaskForm):
    intellectual_rights_radio = RadioField('Intellectual Rights', 
                                choices=[("CC0", INTELLECTUAL_RIGHTS_CC0), 
                                         ("CCBY", INTELLECTUAL_RIGHTS_CC_BY), 
                                         ("Other", "Other (Enter text below)")
                                        ], validators=[InputRequired()])
    intellectual_rights = StringField('', widget=TextArea(), validators=[])
    md5 = HiddenField('')

    def field_data(self)->set:
        return {self.intellectual_rights_radio.data,
                self.intellectual_rights.data}


class KeywordSelectForm(FlaskForm):
    pass


class KeywordForm(FlaskForm):
    keyword = StringField('Keyword', validators=[])
    keyword_type = SelectField('Keyword Type (Optional)', 
                               choices=[("", ""), 
                                        ("place", "place"), 
                                        ("stratum", "stratum"), 
                                        ("taxonomic", "taxonomic"), 
                                        ("temporal", "temporal"), 
                                        ("theme", "theme")])
    md5 = HiddenField('')
 
    def field_data(self)->set:
        return {self.keyword.data,
                self.keyword_type.data}


class MscaleNominalOrdinalForm(FlaskForm):
    mscale = SelectField("Choose nominal (e.g. 'Female', 'Male') or ordinal (e.g. 'low', 'medium', 'high')", 
                            choices=[("nominal", "nominal"), 
                                     ("ordinal", "ordinal")
                                    ])
    enforced = SelectField('Enforce codes', 
                            choices=[("yes", "Yes, enforce the code values I've documented"), 
                                     ("no", "No, other code values are allowed")
                                    ])
    md5 = HiddenField('')


class MscaleIntervalRatioForm(FlaskForm):
    mscale = SelectField("Choose between ratio (e.g.) or interval (e.g.)", 
                            choices=[("ratio", "ratio"),
                                     ("interval", "interval") 
                                    ])
    
    standard_units = ['', 'acre', 'ampere', 'amperePerMeter', 'amperePerMeterSquared', 'angstrom', 'are', 'atmosphere', 'bar', 'becquerel', 'britishThermalUnit', 'bushel', 'bushelPerAcre', 'calorie', 'candela', 'candelaPerMeterSquared', 'celsius', 'centigram', 'centimeter', 'centimeterCubed', 'centimeterPerSecond', 'centimeterSquared', 'centisecond', 'coulomb', 'decibar', 'decigram', 'decimeter', 'decisecond', 'degree', 'dekagram', 'dekameter', 'dekasecond', 'dimensionless', 'equivalentPerLiter', 'fahrenheit', 'farad', 'fathom', 'foot', 'Foot_Gold_Coast', 'Foot_US', 'footCubedPerSecond', 'footPerDay', 'footPerHour', 'footPerSecond', 'footPound', 'footSquared', 'footSquaredPerDay', 'gallon', 'grad', 'gram', 'gramPerCentimeterCubed', 'gramPercentimeterSquared', 'gramPerCentimeterSquaredPerSecond', 'gramPerDayPerHectare', 'gramPerDayPerLiter', 'gramPerGram', 'gramPerLiter', 'gramPerMeterSquared', 'gramPerMeterSquaredPerDay', 'gramPerMeterSquaredPerYear', 'gramPerMilliliter', 'gramPerYear', 'gray', 'hectare', 'hectogram', 'hectometer', 'hectopascal', 'hectosecond', 'henry', 'hertz', 'hour', 'inch', 'inchCubed', 'inchPerHour', 'inverseCentimeter', 'inverseMeter', 'joule', 'katal', 'kelvin', 'kilogram', 'kilogramPerHectare', 'kilogramPerHectarePerYear', 'kilogramPerMeterCubed', 'kilogramPerMeterSquared', 'kilogramPerMeterSquaredPerDay', 'kilogramPerMeterSquaredPerSecond', 'kilogramPerMeterSquaredPerYear', 'kilogramPerSecond', 'kilohertz', 'kiloliter', 'kilometer', 'kilometerPerHour', 'kilometerSquared', 'kilopascal', 'kilosecond', 'kilovolt', 'kilowatt', 'kilowattPerMeterSquared', 'knot', 'langley', 'langleyPerDay', 'Link_Clarke', 'liter', 'literPerHectare', 'literPerLiter', 'literPerMeterSquared', 'literPerSecond', 'lumen', 'lux', 'megagram', 'megagramPerMeterCubed', 'megahertz', 'megajoulePerMeterSquaredPerDay', 'megameter', 'megapascal', 'megasecond', 'megavolt', 'megawatt', 'meter', 'meterCubed', 'meterCubedPerHectare', 'meterCubedPerKilogram', 'meterCubedPerMeterCubed', 'meterCubedPerMeterSquared', 'meterCubedPerSecond', 'meterPerDay', 'meterPerGram', 'meterPerSecond', 'meterPerSecondSquared', 'meterSquared', 'meterSquaredPerDay', 'meterSquaredPerHectare', 'meterSquaredPerKilogram', 'meterSquaredPerSecond', 'microequivalentPerLiter', 'microgram', 'microgramPerGram', 'microgramPerGramPerDay', 'microgramPerGramPerHour', 'microgramPerGramPerWeek', 'microgramPerLiter', 'microliter', 'microliterPerLiter', 'micrometer', 'micrometerCubedPerGram', 'micromolePerCentimeterSquaredPerSecond', 'micromolePerGram', 'micromolePerGramPerDay', 'micromolePerGramPerHour', 'micromolePerGramPerSecond', 'micromolePerKilogram', 'micromolePerLiter', 'micromolePerMeterSquaredPerSecond', 'micromolePerMole', 'microsecond', 'microwattPerCentimeterSquaredPerNanometer', 'microwattPerCentimeterSquaredPerNanometerPerSteradian', 'microwattPerCentimeterSquaredPerSteradian', 'mile', 'milePerHour', 'milePerMinute', 'milePerSecond', 'mileSquared', 'millibar', 'milliequivalentPerLiter', 'milligram', 'milligramPerKilogram', 'milligramPerLiter', 'milligramPerMeterCubed', 'milligramPerMeterCubedPerDay', 'milligramPerMeterSquared', 'milligramPerMeterSquaredPerDay', 'milligramPerMilliliter', 'millihertz', 'milliliter', 'milliliterPerLiter', 'millimeter', 'millimeterPerDay', 'millimeterPerSecond', 'millimeterSquared', 'millimolePerGram', 'millimolePerKilogram', 'millimolePerLiter', 'millimolePerMeterCubed', 'millimolePerMole', 'millisecond', 'millivolt', 'milliwatt', 'minute', 'mole', 'molePerGram', 'molePerKilogram', 'molePerKilogram', 'molePerKilogramPerSecond', 'molePerLiter', 'molePerMeterCubed', 'molePerMeterSquaredPerSecond', 'molePerMole', 'nanogram', 'nanogramPerGram', 'nanogramPerGramPerHour', 'nanoliterPerLiter', 'nanometer', 'nanomolePerGramPerDay', 'nanomolePerGramPerHour', 'nanomolePerGramPerSecond', 'nanomolePerKilogram', 'nanomolePerLiter', 'nanomolePerMole', 'nanosecond', 'nauticalMile', 'newton', 'nominalDay', 'nominalHour', 'nominalLeapYear', 'nominalMinute', 'nominalWeek', 'nominalYear', 'number', 'numberPerGram', 'numberPerHectare', 'numberPerKilometerSquared', 'numberPerLiter', 'numberPerMeterCubed', 'numberPerMeterSquared', 'numberPerMilliliter', 'ohm', 'ohmMeter', 'pascal', 'percent', 'permil', 'pint', 'pound', 'poundPerAcre', 'poundPerInchSquared', 'quart', 'radian', 'second', 'siemens', 'siemensPerCentimeter', 'siemensPerMeter', 'sievert', 'steradian', 'tesla', 'ton', 'tonne', 'tonnePerHectare', 'tonnePerYear', 'volt', 'watt', 'wattPerMeterSquared', 'wattPerMeterSquaredPerNanometer', 'wattPerMeterSquaredPerNanometerPerSteradian', 'wattPerMeterSquaredPerSteradian', 'weber', 'yard', 'Yard_Indian', 'yardPerSecond', 'yardSquared']
    standard_unit = SelectField('Standard Unit', 
                                choices=[(unit, unit) for unit in standard_units])
    custom_unit = StringField('Custom Unit', validators=[])
    precision = FloatField('Precision (Optional)', validators=[Optional()])
    number_type = SelectField('Number Type', 
                               choices=[("real", "real"),
                                        ("integer", "integer"),
                                        ("natural", "natural"),
                                        ("whole", "whole")])
    bounds_minimum = FloatField('Bounds Minimum', validators=[Optional()])
    bounds_minimum_exclusive = BooleanField('Bounds Minimum is Exclusive', validators=[])
    bounds_maximum = FloatField('Bounds Maximum', validators=[Optional()])
    bounds_maximum_exclusive = BooleanField('Bounds Maximum is Exclusive', validators=[])
    md5 = HiddenField('')
    

class MscaleDateTimeForm(FlaskForm):
    format_string = StringField('Format String', validators=[])
    datetime_precision = FloatField('DateTime Precision (Optional)', validators=[Optional()])
    bounds_minimum = StringField('Bounds Minimum', validators=[])
    bounds_minimum_exclusive = BooleanField('Bounds Minimum is Exclusive', validators=[])
    bounds_maximum = StringField('Bounds Maximum', validators=[])
    bounds_maximum_exclusive = BooleanField('Bounds Maximum is Exclusive', validators=[])
    md5 = HiddenField('')
    

class MethodStepSelectForm(FlaskForm):
    pass


class MethodStepForm(FlaskForm):
    description = StringField('Description', widget=TextArea(), validators=[])
    instrumentation = StringField('Instrumentation', widget=TextArea(), validators=[])
    md5 = HiddenField('')
 
    def field_data(self)->set:
        return {self.description.data,
                self.instrumentation.data}


class OpenEMLDocumentForm(FlaskForm):
    packageid = SelectField('Data Package Identifier', choices=[])


class OtherEntitySelectForm(FlaskForm):
    pass


class OtherEntityForm(FlaskForm):
    entity_name = StringField('Name', validators=[])
    entity_type = StringField('Entity Type', validators=[])
    entity_description = StringField('Description (Optional)', validators=[])
    object_name = StringField('Object Name', validators=[])
    size = IntegerField('Size (Optional)', validators=[Optional()])
    num_header_lines = IntegerField('Number of Header Lines (Optional)', validators=[Optional()])
    record_delimiter = StringField('Record Delimiter (Optional)', validators=[])
    attribute_orientation = SelectField('Attribute Orientation', choices=[("column", "column"), ("row", "row")])
    field_delimiter = SelectField('Simple Delimited: Field Delimiter', choices=[("comma", "comma"), ("space", "space"), ("tab", "tab")])
    online_url = StringField('Online Distribution URL', validators=[Optional(), URL()])
    md5 = HiddenField('')


class ProjectForm(FlaskForm):
    title = StringField('Project Title', validators=[])
    abstract = StringField('Project Abstract (Optional)', widget=TextArea(), validators=[])
    funding = StringField('Project Funding (Optional)', validators=[])
    md5 = HiddenField('')


class PubDateForm(FlaskForm):
    pubdate = StringField('Publication Date', 
                          validators=[Optional(), Regexp(r'^(\d\d\d\d)-(01|02|03|04|05|06|07|08|09|10|11|12)-(0[1-9]|[1-2]\d|30|31)|(\d\d\d\d)$', message='Invalid date format')])
    md5 = HiddenField('')


class PublicationPlaceForm(FlaskForm):
    pubplace = StringField('Publication Place', validators=[])
    md5 = HiddenField('')


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
    email = StringField('Email', validators=[Optional(), Email()])
    online_url = StringField('Online URL', validators=[Optional(), URL()])
    role = StringField('Role', validators=[])
    md5 = HiddenField('')


class SaveAsForm(FlaskForm):
    packageid = StringField('Package ID', validators=[DataRequired()])


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
    md5 = HiddenField('')


class TemporalCoverageSelectForm(FlaskForm):
    pass


class TemporalCoverageForm(FlaskForm):
    begin_date = StringField('Begin Date', validators=[Optional(), Regexp(r'^(\d\d\d\d)-(01|02|03|04|05|06|07|08|09|10|11|12)-(0[1-9]|[1-2]\d|30|31)|(\d\d\d\d)$', message='Invalid date format')])
    end_date = StringField('End Date', validators=[Optional(), Regexp(r'^(\d\d\d\d)-(01|02|03|04|05|06|07|08|09|10|11|12)-(0[1-9]|[1-2]\d|30|31)|(\d\d\d\d)$', message='Invalid date format')])
    md5 = HiddenField('')


class TitleForm(FlaskForm):
    title = StringField('Title', validators=[valid_min_length(min=20)])
    md5 = HiddenField('')
