
from flask_wtf import FlaskForm

from wtforms import (
    StringField, RadioField, SelectField, HiddenField
)
from wtforms.widgets import TextArea

from wtforms.validators import (
    DataRequired, Email, Optional, ValidationError
)
from webapp.scopes import SCOPE_CHOICES
from webapp.home.forms import EDIForm


class ScopeSelectForm(FlaskForm):
    scope = SelectField('Select the Scope: ',
                       choices=SCOPE_CHOICES,
                        default='edi')


class CuratorWorkflowForm(FlaskForm):
    scope = HiddenField('Hidden Scope')                                       # validators=[Optional()])
    new_or_existing = RadioField('Data Package ID',
                                 choices=[('New', 'Get a new Package ID from PASTA'),
                                          ('Existing', 'I have a Package ID to use (enter it below)')],
                                 default='New',
                                 validators=[DataRequired()])
    # revision = RadioField('Revision of ')
    entered_pid = StringField('Package ID: ', validators=[Optional()])
    pass