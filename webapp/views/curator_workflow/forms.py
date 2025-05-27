
from flask_wtf import FlaskForm

from wtforms import (
    StringField, RadioField, SelectField, HiddenField
)
from wtforms.widgets import TextArea

from wtforms.validators import (
    DataRequired, Email, Optional, ValidationError
)
from webapp.home.forms import EDIForm


class ScopeSelectForm(FlaskForm):
    scope = SelectField('Scope: ',
                       choices=[("edi", "edi"),
                                ("knb-lter-and", "knb-lter-and"),
                                ("knb-lter-arc", "knb-lter-arc"),
                                ("knb-lter-bes", "knb-lter-bes"),
                                ("knb-lter-ble", "knb-lter-ble"),
                                ("knb-lter-bnz", "knb-lter-bnz"),
                                ("knb-lter-cap", "knb-lter-cap"),
                                ("knb-lter-cce", "knb-lter-cce"),
                                ("knb-lter-cdr", "knb-lter-cdr"),
                                ("knb-lter-cwt", "knb-lter-cwt"),
                                ("knb-lter-fce", "knb-lter-fce"),
                                ("knb-lter-gce", "knb-lter-gce"),
                                ("knb-lter-hbr", "knb-lter-hbr"),
                                ("knb-lter-hfr", "knb-lter-hfr"),
                                ("knb-lter-jrn", "knb-lter-jrn"),
                                ("knb-lter-kbs", "knb-lter-kbs"),
                                ("knb-lter-knz", "knb-lter-knz"),
                                ("knb-lter-luq", "knb-lter-luq"),
                                ("knb-lter-mcm", "knb-lter-mcm"),
                                ("knb-lter-mcr", "knb-lter-mcr"),
                                ("knb-lter-msp", "knb-lter-msp"),
                                ("knb-lter-nes", "knb-lter-nes"),
                                ("knb-lter-nga", "knb-lter-nga"),
                                ("knb-lter-nin", "knb-lter-nin"),
                                ("knb-lter-ntl", "knb-lter-ntl"),
                                ("knb-lter-nwk", "knb-lter-nwk"),
                                ("knb-lter-nwt", "knb-lter-nwt"),
                                ("knb-lter-pal", "knb-lter-pal"),
                                ("knb-lter-pie", "knb-lter-pie"),
                                ("knb-lter-sbc", "knb-lter-sbc"),
                                ("knb-lter-sev", "knb-lter-sev"),
                                ("knb-lter-sgs", "knb-lter-sgs"),
                                ("knb-lter-vcr", "knb-lter-vcr")
                                ],
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