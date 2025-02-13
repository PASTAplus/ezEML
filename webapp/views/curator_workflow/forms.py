
from flask_wtf import FlaskForm

from wtforms import (
    StringField, RadioField, SubmitField
)
from wtforms.widgets import TextArea

from wtforms.validators import (
    DataRequired, Email, Optional, ValidationError
)
from webapp.home.forms import EDIForm


class CuratorWorkflowForm(FlaskForm):
                                           # validators=[Optional()])

    new_or_revision = RadioField('New Package or Revision',
                                 choices=[('New', 'New package'), ('Revision', 'Revision')],
                                 default='New',
                                 validators=[DataRequired()])
    # revision = RadioField('Revision of ')
    revision_of = StringField('Revision of: ', validators=[Optional()])
    pass