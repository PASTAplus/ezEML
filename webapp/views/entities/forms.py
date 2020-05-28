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
    entity_type = StringField('Entity Type (e.g., photograph)', validators=[])
    entity_description = StringField('Description', validators=[])
    object_name = StringField('Object Name', validators=[])
    format_name = StringField('Format Name (e.g., PNG)', validators=[])
    size = IntegerField('Size (Optional)', validators=[Optional()])
    md5_hash = StringField('MD5 Checksum (Optional)', validators=[Optional()])
    online_url = StringField('Online Distribution URL', validators=[Optional(), URL()])
    md5 = HiddenField('')

    def field_data(self)->tuple:
        return (self.entity_name.data,
                self.entity_type.data,
                self.entity_description.data,
                self.object_name.data,
                self.format_name.data,
                self.size.data,
                self.md5_hash.data,
                self.online_url.data)

