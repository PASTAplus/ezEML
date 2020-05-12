
from wtforms import (
    StringField, BooleanField, SelectField,
    FloatField, IntegerField, HiddenField
)

from wtforms.validators import (
    URL, Optional
)

from webapp.home.forms import EDIForm


class AttributeSelectForm(EDIForm):
    pass


class AttributeDateTimeForm(EDIForm):
    attribute_name = StringField('Name', validators=[])
    attribute_label = StringField('Label (Optional)', validators=[])
    attribute_definition = StringField('Definition', validators=[])
    storage_type = StringField('Storage Type (Optional)', validators=[])
    storage_type_system = StringField('Storage Type System (Optional)', validators=[])
    format_string = StringField('Format String', validators=[])
    datetime_precision = FloatField('DateTime Precision (Optional)', validators=[Optional()])
    bounds_minimum = StringField('Bounds Minimum', validators=[])
    bounds_minimum_exclusive = BooleanField('Bounds Minimum is Exclusive', validators=[])
    bounds_maximum = StringField('Bounds Maximum', validators=[])
    bounds_maximum_exclusive = BooleanField('Bounds Maximum is Exclusive', validators=[])
    code_1 = StringField('Missing Value Code', validators=[])
    code_explanation_1 = StringField('Explanation', validators=[]) 
    code_2 = StringField('Missing Value Code', validators=[])
    code_explanation_2 = StringField('Explanation', validators=[])
    code_3 = StringField('Missing Value Code', validators=[])
    code_explanation_3 = StringField('Explanation', validators=[])
    md5 = HiddenField('')

    def field_data(self)->tuple:
        return (self.attribute_name.data, 
                self.attribute_label.data,
                self.attribute_definition.data,
                self.storage_type.data,
                self.storage_type_system.data,
                self.format_string.data,
                self.datetime_precision.data,
                self.bounds_minimum.data,
                self.bounds_minimum_exclusive.data,
                self.bounds_maximum.data,
                self.bounds_maximum_exclusive.data,
                self.code_1.data,
                self.code_explanation_1.data,
                self.code_2.data,
                self.code_explanation_2.data,
                self.code_3.data,
                self.code_explanation_3.data)


class AttributeNominalOrdinalForm(EDIForm):
    mscale_choice = SelectField('Measurement Scale', 
                                choices=[("nominal", "nominal"), ("ordinal", "ordinal")])
    attribute_name = StringField('Name', validators=[])
    attribute_label = StringField('Label (Optional)', validators=[])
    attribute_definition = StringField('Definition', validators=[])
    storage_type = StringField('Storage Type (Optional)', validators=[])
    storage_type_system = StringField('Storage Type System (Optional)', validators=[])
    enforced = SelectField('Enforce codes', 
                            choices=[("yes", "Yes, enforce the code values I've documented"), 
                                     ("no", "No, other code values are allowed")
                                    ])
    code_1 = StringField('Missing Value Code', validators=[])
    code_explanation_1 = StringField('Explanation', validators=[]) 
    code_2 = StringField('Missing Value Code', validators=[])
    code_explanation_2 = StringField('Explanation', validators=[])
    code_3 = StringField('Missing Value Code', validators=[])
    code_explanation_3 = StringField('Explanation', validators=[])
    md5 = HiddenField('')
    mscale = HiddenField('')
    init_str = "yes"

    def field_data(self)->tuple:
        return (self.mscale_choice.data, 
                self.attribute_name.data, 
                self.attribute_label.data,
                self.attribute_definition.data,
                self.storage_type.data,
                self.storage_type_system.data,
                self.enforced.data,
                self.code_1.data,
                self.code_explanation_1.data,
                self.code_2.data,
                self.code_explanation_2.data,
                self.code_3.data,
                self.code_explanation_3.data,
                self.mscale.data)


class AttributeIntervalRatioForm(EDIForm):
    mscale_choice = SelectField('Measurement Scale', 
                                choices=[("interval", "interval"), ("ratio", "ratio")])
    attribute_name = StringField('Name', validators=[])
    attribute_label = StringField('Label (Optional)', validators=[])
    attribute_definition = StringField('Definition', validators=[])
    storage_type = StringField('Storage Type (Optional)', validators=[])
    storage_type_system = StringField('Storage Type System (Optional)', validators=[])
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
    code_1 = StringField('Missing Value Code', validators=[])
    code_explanation_1 = StringField('Explanation', validators=[]) 
    code_2 = StringField('Missing Value Code', validators=[])
    code_explanation_2 = StringField('Explanation', validators=[])
    code_3 = StringField('Missing Value Code', validators=[])
    code_explanation_3 = StringField('Explanation', validators=[])
    md5 = HiddenField('')
    mscale = HiddenField('')
    init_str = 'real'

    def field_data(self)->tuple:
        return (self.mscale_choice.data,
                self.attribute_name.data, 
                self.attribute_label.data,
                self.attribute_definition.data,
                self.storage_type.data,
                self.storage_type_system.data,
                self.standard_unit.data,
                self.custom_unit.data,
                self.precision.data,
                self.number_type.data,
                self.bounds_minimum.data,
                self.bounds_minimum_exclusive.data,
                self.bounds_maximum.data,
                self.bounds_maximum_exclusive.data,
                self.code_1.data,
                self.code_explanation_1.data,
                self.code_2.data,
                self.code_explanation_2.data,
                self.code_3.data,
                self.code_explanation_3.data,
                self.mscale.data)


class DataTableSelectForm(EDIForm):
    pass


class DataTableForm(EDIForm):
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
    init_str = 'columncommano'

    def field_data(self)->tuple:
        return (self.entity_name.data, 
                self.entity_description.data, 
                self.object_name.data, 
                self.size.data, 
                self.num_header_lines.data, 
                self.record_delimiter.data, 
                self.attribute_orientation.data, 
                self.field_delimiter.data, 
                self.case_sensitive.data, 
                self.number_of_records.data, 
                self.online_url.data)


class CodeDefinitionSelectForm(EDIForm):
    pass


class CodeDefinitionForm(EDIForm):
    code = StringField('Code', validators=[])
    definition = StringField('Definition', validators=[])
    order = IntegerField('Order (Optional)', validators=[Optional()])
    md5 = HiddenField('')

    def field_data(self)->tuple:
        return (self.code.data, self.definition.data, self.order.data)