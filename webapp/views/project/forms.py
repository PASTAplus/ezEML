from wtforms import (
    StringField, HiddenField, validators
)

from wtforms.widgets import TextArea

from webapp.home.forms import EDIForm


class ProjectForm(EDIForm):
    title = StringField('Project Title', validators=[])  # validators.DataRequired()])
    abstract = StringField('Project Abstract (Optional)', widget=TextArea(), validators=[])
    funding = StringField('Project Funding (Optional)', validators=[])
    md5 = HiddenField('')

    def field_data(self)->tuple:
        return (self.title.data,
                self.abstract.data,
                self.funding.data)
