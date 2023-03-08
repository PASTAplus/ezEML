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

from wtforms import (
    StringField, SelectField, SelectMultipleField, HiddenField, RadioField, widgets
)

from wtforms.validators import (
    DataRequired, Email, Optional, ValidationError
)


class CollaborateForm(FlaskForm):
    pass


class AcceptInvitationForm(FlaskForm):
    invitation_code = StringField("Invitation Code *", validators=[DataRequired()])


class InviteCollaboratorForm(FlaskForm):
    user_name = StringField("Your Name *", validators=[DataRequired()])
    user_email = StringField("Your Email Address *", validators=[DataRequired()])
    collaborator_name = StringField("Collaborator's Name *", validators=[DataRequired()])
    email_address = StringField("Collaborator's Email Address *", validators=[Email(), DataRequired()])
