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
    md5 = HiddenField('')

    def field_data(self)->tuple:
        return (self.geographic_description.data,
                self.wbc.data,
                self.ebc.data,
                self.nbc.data,
                self.sbc.data)


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
        ("ITIS", "ITIS - Integrated Taxonomic Information System"),
        ("NCBI", "NCBI - National Center for Biotechnology Information"),
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


class TemporalCoverageSelectForm(EDIForm):
    pass


class TemporalCoverageForm(EDIForm):
    begin_date = StringField('Begin Date *', validators=[InputRequired(message='Begin Date is required'), Regexp(r'^(\d\d\d\d)-(01|02|03|04|05|06|07|08|09|10|11|12)-(0[1-9]|[1-2]\d|30|31)|(\d\d\d\d)$', message='Invalid date format')])
    end_date = StringField('End Date', validators=[Optional(), Regexp(r'^(\d\d\d\d)-(01|02|03|04|05|06|07|08|09|10|11|12)-(0[1-9]|[1-2]\d|30|31)|(\d\d\d\d)$', message='Invalid date format')])
    md5 = HiddenField('')

    def field_data(self)->tuple:
        return (self.begin_date.data,
                self.end_date.data)

