"""
WTForms for the coverage blueprint.
"""

from wtforms import (
    StringField,
    FloatField,
    HiddenField,
    SelectField
)

from wtforms.validators import (
    InputRequired,
    Optional,
    Regexp
)

from wtforms.widgets import TextArea

from webapp.home.custom_validators import (
    valid_min_length, valid_latitude, valid_longitude
)

from webapp.home.forms import EDIForm


class GeographicCoverageSelectForm(EDIForm):
    pass


class GeographicCoverageForm(EDIForm):
    geographic_description = StringField('Geographic Description *', widget=TextArea(),
                                         validators=[InputRequired(message='Geographic Description is required')])
    wbc = FloatField('West Bounding Coordinate *', validators=[valid_longitude(), InputRequired(message='West Bounding Coordinate is required')])
    ebc = FloatField('East Bounding Coordinate *', validators=[valid_longitude(), InputRequired(message='East Bounding Coordinate is required')])
    nbc = FloatField('North Bounding Coordinate *', validators=[valid_latitude(), InputRequired(message='North Bounding Coordinate is required')])
    sbc = FloatField('South Bounding Coordinate *', validators=[valid_latitude(), InputRequired(message='South Bounding Coordinate is required')])
    amin = FloatField('Minimum Altitude', validators=[Optional()])
    amax = FloatField('Maximum Altitude', validators=[Optional()])
    aunits = SelectField('Altitude Units', choices=[
        ('', ''),
        ('meter', 'meter'),
        ('nanometer', 'nanometer'),
        ('micrometer', 'micrometer'),
        ('micron', 'micron'),
        ('millimeter', 'millimeter'),
        ('centimeter', 'centimeter'),
        ('decimeter', 'decimeter'),
        ('dekameter', 'dekameter'),
        ('hectameter', 'hectameter'),
        ('kilometer', 'kilometer'),
        ('megameter', 'megameter'),
        ('angstrom', 'angstrom'),
        ('inch', 'inch'),
        ('foot', 'foot'),
        ('Foot_US', 'foot (US)'),
        ('yard', 'yard'),
        ('mile', 'mile'),
        ('nauticalMile', 'nautical mile'),
        ('fathom', 'fathom'),
        ('Foot_Gold_Coast', 'foot (Gold Coast)'),
        ('Yard_Indian', 'yard (India)'),
        ('Link_Clarke', 'Clarke link'),
        ('Yard_Sears', 'Sears yard'),
    ], default=''
    )
    md5 = HiddenField('')

    def is_float(self, val):
        if val is None:
            return False
        try:
            __ = float(val)
            return True
        except ValueError:
            pass
        return False

    def is_float_or_None(self, val):
        try:
            __ = float(val)
            return True
        except ValueError:
            return False
        except TypeError:
            return True

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators):
            return False
        result = True
        if not self.is_float_or_None(self.amin.data):
            self.amin.errors.append('Not a valid float value')
            result = False
        if not self.is_float_or_None(self.amax.data):
            self.amax.errors.append('Not a valid float value')
            result = False
        if not result:
            return False
        if self.is_float(self.amin.data) or self.is_float(self.amax.data) or self.aunits.data:
            if self.amin.data is None:
                self.amin.errors.append('Minimum Alititude is required')
                result = False
            if self.amax.data is None:
                self.amax.errors.append('Maximum Alititude is required')
                result = False
            if not self.aunits.data:
                self.aunits.errors.append('Altitude Units are required')
                result = False
        if self.is_float(self.amin.data) and self.is_float(self.amax.data) and float(self.amax.data) < float(self.amin.data):
            self.amax.errors.append('Maximum must be greater than or equal to Minimum')
            result = False
        return result

    def field_data(self)->tuple:
        return (self.geographic_description.data,
                self.wbc.data,
                self.ebc.data,
                self.nbc.data,
                self.sbc.data,
                self.amin.data,
                self.amax.data,
                self.aunits.data)


class TaxonomicCoverageSelectForm(EDIForm):
    pass


class TaxonomicCoverageForm(EDIForm):
    general_taxonomic_coverage = StringField('General Taxonomic Coverage (Optional)', widget=TextArea(), validators=[])
    taxon_rank = SelectField('Taxon Rank', choices=[
        ('', ''),
        ('Subspecies', 'Subspecies'),
        ('Species', 'Species'),
        ('Subgenus', 'Subgenus'),
        ('Genus', 'Genus'),
        ('Subfamily', 'Subfamily'),
        ('Family', 'Family'),
        ('Superfamily', 'Superfamily'),
        ('Infraorder', 'Infraorder'),
        ('Suborder', 'Suborder'),
        ('Order', 'Order'),
        ('Superorder', 'Superorder'),
        ('Infraclass', 'Infraclass'),
        ('Subclass', 'Subclass'),
        ('Class', 'Class'),
        ('Superclass', 'Superclass'),
        ('Infraphylum', 'Infraphylum'),
        ('Subphylum', 'Subphylum'),
        ('Subdivision', 'Subdivision'),
        ('Subphylum (Subdivision)', 'Subphylum (Subdivision)'),
        ('Phylum', 'Phylum'),
        ('Division', 'Division'),
        ('Phylum (Division)', 'Phylum (Division)'),
        ('Superphylum', 'Superphylum'),
        ('Infrakingdom', 'Infrakingdom'),
        ('Subkingdom', 'Subkingdom'),
        ('Kingdom', 'Kingdom'),
        ('Domain', 'Domain'),
        ('Superdomain', 'Superdomain')
    ], default=''
    )
    taxon_value = StringField('Taxon Scientific Name', validators=[])
    hierarchy = HiddenField('')
    taxonomic_authority = SelectField("Taxonomic Authority", choices=[
        ("NCBI", "NCBI - National Center for Biotechnology Information"),
        ("ITIS", "ITIS - Integrated Taxonomic Information System"),
        ("WORMS", "WORMS - World Register of Marine Species")])
    md5 = HiddenField('')
    hidden_taxon_rank = HiddenField('')
    hidden_taxon_value = HiddenField('')
    hidden_taxonomic_authority = HiddenField('')

    def field_data(self)->tuple:
        return (self.general_taxonomic_coverage.data,
                self.taxon_value,
                self.taxon_rank,
                self.hierarchy)
                # self.kingdom_value.data,
                # self.kingdom_common_name.data,
                # self.phylum_value.data,
                # self.phylum_common_name.data,
                # self.class_value.data,
                # self.class_common_name.data,
                # self.order_value.data,
                # self.order_common_name.data,
                # self.family_value.data,
                # self.family_common_name.data,
                # self.genus_value.data,
                # self.genus_common_name.data,
                # self.species_value.data,
                # self.species_common_name.data)


class LoadTaxonomicCoverageForm(EDIForm):
    delimiter = SelectField('Field Delimiter', choices=[
            (',', 'comma'),
            ('\t', 'tab'),
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
    general_taxonomic_coverage = StringField('General Taxonomic Coverage (Optional)', widget=TextArea(), validators=[])
    hierarchy = HiddenField('')
    taxonomic_authority = SelectField("Taxonomic Authority", choices=[
        ("NCBI", "NCBI - National Center for Biotechnology Information"),
        ("ITIS", "ITIS - Integrated Taxonomic Information System"),
        ("WORMS", "WORMS - World Register of Marine Species")])
    md5 = HiddenField('')
    hidden_taxonomic_authority = HiddenField('')

    def field_data(self)->tuple:
        return (self.general_taxonomic_coverage.data,
                self.hierarchy,
                self.taxonomic_authority)


class TemporalCoverageSelectForm(EDIForm):
    pass


class TemporalCoverageForm(EDIForm):
    begin_date = StringField('Begin Date *', validators=[InputRequired(message='Begin Date is required'), Regexp(r'^(\d\d\d\d)-(01|02|03|04|05|06|07|08|09|10|11|12)-(0[1-9]|[1-2]\d|30|31)|(\d\d\d\d)$', message='Invalid date format')])
    end_date = StringField('End Date', validators=[Optional(), Regexp(r'^(\d\d\d\d)-(01|02|03|04|05|06|07|08|09|10|11|12)-(0[1-9]|[1-2]\d|30|31)|(\d\d\d\d)$', message='Invalid date format')])
    md5 = HiddenField('')

    def field_data(self)->tuple:
        return (self.begin_date.data,
                self.end_date.data)

