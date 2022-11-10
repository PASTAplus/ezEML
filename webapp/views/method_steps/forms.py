from wtforms import (
    StringField,
    HiddenField
)

from wtforms.validators import (
    DataRequired
)

from wtforms.widgets import TextArea

from webapp.home.forms import EDIForm


class MethodStepSelectForm(EDIForm):
    pass


class MethodStepForm(EDIForm):
    description = StringField('Description *', widget=TextArea(), validators=[DataRequired(message='Description is required')])
    instrumentation = StringField('Instrumentation (Optional)', widget=TextArea(), validators=[])
    data_sources = StringField('Data Sources (Optional)', widget=TextArea(), validators=[])
    md5 = HiddenField('')

    def field_data(self) -> tuple:
        return (self.description.data,
                self.instrumentation.data,
                self.data_sources.data)


class DataSourceForm(EDIForm):
    title = StringField('Title *', widget=TextArea(), validators=[DataRequired(message='Title is required')])
    online_description = StringField('Online Description (Recommended)', widget=TextArea(), validators=[])
    url = StringField('URL (Recommended)', widget=TextArea(), validators=[])
    md5 = HiddenField('')
