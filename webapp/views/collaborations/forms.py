  #!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: forms.py

:Synopsis:

:Author:
    ide

:Created:
    3/3/23
"""

import hashlib
from flask_wtf import FlaskForm
from webapp.home.forms import EDIForm

from wtforms import (
    StringField
)
from wtforms.widgets import TextArea

from wtforms.validators import (
    DataRequired, Email, Optional, ValidationError
)


class CollaborateForm(EDIForm):
    pass


class EnableEDICurationForm(EDIForm):
    name = StringField('Your Name *', validators=[DataRequired()])
    email_address = StringField('Your Email Address *', validators=[Email(), DataRequired()])
    notes = StringField('Notes for EDI Data Curators (Optional)', widget=TextArea(), validators=[Optional()])


class AcceptInvitationForm(EDIForm):
    invitation_code = StringField("Invitation Code *")


class InviteCollaboratorForm(EDIForm):
    user_name = StringField("Your Name *", validators=[DataRequired()])
    user_email = StringField("Your Email Address *", validators=[DataRequired()])
    collaborator_name = StringField("Collaborator's Name *", validators=[DataRequired()])
    email_address = StringField("Collaborator's Email Address *", validators=[Email(), DataRequired()])
