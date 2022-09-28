from wtforms import (
    StringField, SelectField, IntegerField, HiddenField, TextAreaField
)

from wtforms.validators import (
    URL, Optional, InputRequired, DataRequired
)

from flask_wtf.file import (
    FileField, FileRequired, FileAllowed
)

from webapp.home.forms import EDIForm

class OtherEntitySelectForm(EDIForm):
    pass


class OtherEntityForm(EDIForm):
    #TODO: make input required unless image is uploaded
    entity_name = StringField('Name *', validators=[DataRequired()])
    entity_type = StringField('Image Type (e.g., histology) *', validators=[DataRequired()])
#    entity_description = StringField('Description (Recommended)', validators=[])
#    object_name = StringField('Source Name (e.g., filename)', validators=[])
    format_name = StringField('Data Format (e.g., tif) *', validators=[DataRequired()])
#    size = IntegerField('Size (Optional)', validators=[Optional()])
    file_upload = FileField("Upload Image")
#    file_name = StringField("Filename", validators=[])
    additional_info = TextAreaField("Additional Info", validators=[])
#    md5_hash = StringField('MD5 Checksum (Optional)', validators=[Optional()])
    online_url = StringField('Online Distribution URL (Optional)', validators=[Optional(), URL()])
    md5 = HiddenField('')

    def field_data(self)->tuple:
        return (self.entity_name.data,
                self.entity_type.data,
                self.format_name.data,
                self.file_upload.data,
#                self.file_name.data,
                self.additional_info.data,
#                self.entity_description.data,
#                self.object_name.data,
#                self.size.data,
#                self.md5_hash.data,
                self.online_url.data)

