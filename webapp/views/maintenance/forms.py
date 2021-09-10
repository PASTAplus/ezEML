from wtforms import (
    StringField, SelectField, HiddenField, validators
)

from wtforms.validators import (
    InputRequired
)

from wtforms.widgets import TextArea

from webapp.home.forms import EDIForm


class MaintenanceForm(EDIForm):
    description = StringField('Description *', widget=TextArea(), validators=[InputRequired(message='Description is required')])
    update_frequency = SelectField('Maintenance Update Frequency (Optional)',
                                   choices=[("", ""),
                                            ("annually", "annually"),
                                            ("asNeeded", "as needed"),
                                            ("biannually", "biannually"),
                                            ("continually", "continually"),
                                            ("daily", "daily"),
                                            ("irregular", "irregular"),
                                            ("monthly", "monthly"),
                                            ("notPlanned", "not planned"),
                                            ("weekly", "weekly"),
                                            ("unknown", "unknown"),
                                            ("otherMaintenancePeriod", "other maintenance period")])
