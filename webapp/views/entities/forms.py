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
    entity_description = StringField('Description (Optional)', validators=[])
    object_name = StringField('Object Name', validators=[])
    format_name = StringField('Format Name (e.g., PNG)', validators=[])
    # size = IntegerField('Size (Optional)', validators=[Optional()])
    online_url = StringField('Online Distribution URL', validators=[Optional(), URL()])
    md5 = HiddenField('')

    def field_data(self)->tuple:
        return (self.entity_name.data,
                self.entity_type.data,
                self.entity_description.data,
                self.object_name.data,
                self.format_name.data,
                self.online_url.data)

