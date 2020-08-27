from wtforms import (
    StringField,
    FloatField,
    HiddenField
)

from wtforms.validators import (
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
    geographic_description = StringField('Geographic Description (*)', widget=TextArea(),
                                         validators=[])
    wbc = FloatField('West Bounding Coordinate (*)', validators=[valid_longitude(), Optional()])
    ebc = FloatField('East Bounding Coordinate (*)', validators=[valid_longitude(), Optional()])
    nbc = FloatField('North Bounding Coordinate (*)', validators=[valid_latitude(), Optional()])
    sbc = FloatField('South Bounding Coordinate (*)', validators=[valid_latitude(), Optional()])
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

    def field_data(self)->tuple:
        return (self.general_taxonomic_coverage.data,
                self.kingdom_value.data,
                self.kingdom_common_name.data,
                self.phylum_value.data,
                self.phylum_common_name.data,
                self.class_value.data,
                self.class_common_name.data,
                self.order_value.data,
                self.order_common_name.data,
                self.family_value.data,
                self.family_common_name.data,
                self.genus_value.data,
                self.genus_common_name.data,
                self.species_value.data,
                self.species_common_name.data)


class TemporalCoverageSelectForm(EDIForm):
    pass


class TemporalCoverageForm(EDIForm):
    begin_date = StringField('Begin Date (*)', validators=[Optional(), Regexp(r'^(\d\d\d\d)-(01|02|03|04|05|06|07|08|09|10|11|12)-(0[1-9]|[1-2]\d|30|31)|(\d\d\d\d)$', message='Invalid date format')])
    end_date = StringField('End Date', validators=[Optional(), Regexp(r'^(\d\d\d\d)-(01|02|03|04|05|06|07|08|09|10|11|12)-(0[1-9]|[1-2]\d|30|31)|(\d\d\d\d)$', message='Invalid date format')])
    md5 = HiddenField('')

    def field_data(self)->tuple:
        return (self.begin_date.data,
                self.end_date.data)

