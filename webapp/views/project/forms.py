from wtforms import (
    StringField, HiddenField, validators
)

from wtforms.validators import (
    InputRequired
)

from wtforms.widgets import TextArea

from webapp.home.forms import EDIForm


class ProjectForm(EDIForm):
    title = StringField('Project Title *', validators=[InputRequired(message='Project Title is required')])
    abstract = StringField('Project Abstract (Optional)', widget=TextArea(), validators=[])
    md5 = HiddenField('')
    init_str = ""

    def field_data(self)->tuple:
        return (self.title.data,
                self.abstract.data)


class AwardSelectForm(EDIForm):
    pass


class AwardForm(EDIForm):
    funder_name = StringField('Funder Name *', validators=[validators.DataRequired()])
    award_title = StringField('Award Title *', validators=[validators.DataRequired()])
    funder_identifier = StringField('Funder Identifier(s) (Optional)', validators=[])
    award_number = StringField('Award Number *', validators=[validators.DataRequired()])
    award_url = StringField('Award URL (Optional)', validators=[])
    md5 = HiddenField('')
    init_str = ""

    def field_data(self)->tuple:
        return (self.funder_name.data,
                self.award_title.data,
                self.funder_identifier.data,
                self.award_number.data,
                self.award_url.data)


class RelatedProjectSelectForm(EDIForm):
    pass
