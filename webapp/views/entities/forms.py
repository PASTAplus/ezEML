from wtforms import (
    StringField, SelectField, HiddenField
)

from wtforms.validators import (
    URL, Optional, InputRequired
)

from webapp.home.forms import EDIForm, validate_integer

class OtherEntitySelectForm(EDIForm):
    pass


class OtherEntityForm(EDIForm):
    entity_name = StringField('Name *', validators=[InputRequired(message='Name is required')])
    entity_type = StringField('Entity Type (e.g., photograph) *', validators=[])
    entity_description = StringField('Description (Recommended)', validators=[])
    object_name = StringField('Source Name (e.g., filename)', validators=[])
    format_name = StringField('Data Format (e.g., PNG) *', validators=[])
    size = StringField('Size (Optional)', validators=[Optional(), validate_integer])
    md5_hash = StringField('MD5 Checksum (Optional)', validators=[Optional()])
    online_url = StringField('Online Distribution URL (Optional)', validators=[Optional(), URL()])
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

