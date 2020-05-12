from wtforms import (
    StringField, SelectField, IntegerField, HiddenField
)

from wtforms.validators import (
    URL, Optional
)

from webapp.home.forms import EDIForm


class OtherEntitySelectForm(EDIForm):
    pass


class OtherEntityForm(EDIForm):
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
    init_str = 'columncomma'

    def field_data(self)->tuple:
        return (self.entity_name.data,
                self.entity_type.data,
                self.entity_description.data,
                self.object_name.data,
                self.size.data,
                self.num_header_lines.data,
                self.record_delimiter.data,
                self.attribute_orientation.data,
                self.field_delimiter.data,
                self.online_url.data)

