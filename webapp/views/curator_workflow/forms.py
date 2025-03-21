
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

    new_or_existing = RadioField('Data Package ID',
                                 choices=[('New', 'Get a new Package ID from PASTA'),
                                          ('Existing', 'I have a Package ID to use (enter it below)')],
                                 default='New',
                                 validators=[DataRequired()])
    # revision = RadioField('Revision of ')
    entered_pid = StringField('Package ID: ', validators=[Optional()])
    pass