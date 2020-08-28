from wtforms import (
    StringField, SelectField, HiddenField, validators
)

from wtforms.widgets import TextArea

from webapp.home.forms import EDIForm


class MaintenanceForm(EDIForm):
    description = StringField('Description *', widget=TextArea(), validators=[])
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
