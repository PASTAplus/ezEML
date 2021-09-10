from wtforms import (
    StringField,
    HiddenField
)

from wtforms.validators import (
    InputRequired
)

from wtforms.widgets import TextArea

from webapp.home.forms import EDIForm


class MethodStepSelectForm(EDIForm):
    pass


class MethodStepForm(EDIForm):
    description = StringField('Description *', widget=TextArea(), validators=[InputRequired(message='Description is required')])
    instrumentation = StringField('Instrumentation (Optional)', widget=TextArea(), validators=[])
    data_sources = StringField('Data Sources (Optional)', widget=TextArea(), validators=[])
    md5 = HiddenField('')

    def field_data(self) -> tuple:
        return (self.description.data,
                self.instrumentation.data,
                self.data_sources)
