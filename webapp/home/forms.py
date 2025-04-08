"""
Forms used in the home blueprint.
"""

import hashlib
from flask_wtf import FlaskForm

from wtforms import (
    StringField, SelectField, SelectMultipleField, HiddenField, BooleanField, RadioField, widgets, validators
)

from wtforms.validators import (
    DataRequired, Email, Optional, ValidationError, StopValidation
)

from wtforms.widgets import TextArea


class EDIForm(FlaskForm):
    """
    Base class for EDI forms.

    Contains MD5 hash of form data to detect whether form contents have changed.
    Various methods are provided to support MD5 hash calculation, external to the class. See below.
    """

    md5 = HiddenField('')
    init_str = ''

    def init_md5(self):
        # Note: this initializes the MD5 hash for the empty form. After the form is populated with data, the MD5 hash
        # needs to be updated. See init_form_md5().
        self.md5.data = hashlib.md5(self.init_str.encode('utf-8')).hexdigest()

    def field_data(self):
        """Return a tuple of field data, excluding md5 and csrf_token."""
        fields = [
            val
            for key, val in self.data.items()
            if key not in ('md5', 'csrf_token')
        ]
        return tuple(fields)


def concat_str(form):
    """Return a concatenated string of field data, excluding md5 and csrf_token, interleaved with field index.
    We interleave the field index so we can detect if a field's value is copy-pasted to another field, for example.
    If the field index were not interleaved, then the MD5 hash would be the same for two forms with the same field
    values in permuted order."""

    concat_str = ''
    if form:
        field_data = form.field_data()
        if field_data:
            i = 0  # We interleave the field index so we can detect if a field's value is copy-pasted to another field
            for val in field_data:
                # Initially a field may have value None, but in the normal course of processing GET and POST, Flask
                # will convert None to an empty string. So we do the same here. Otherwise, we get lots of false
                # positives, where it appears that a form is dirty when the only change is that a field has been
                # converted from None to ''.
                if val is None:
                    val = ''
                concat_str += str(i) + str(val)
                i += 1
    return concat_str


def form_md5(form):
    """Return the MD5 hash of the relevant field data, i.e., excluding md5 and csrf_token."""
    form_str = concat_str(form)
    # Browser may convert line endings to \r\n, so we convert to \n to ensure consistent results.
    form_str = form_str.replace('\r\n', '\n')
    md5 = hashlib.md5(form_str.encode('utf-8')).hexdigest()
    return md5


def init_form_md5(form):
    """Initialize the MD5 hash for a form."""
    form.md5.data = form_md5(form)


def is_dirty_form(form):
    """Return True if the form data has changed since the form was last checked."""
    is_dirty = False
    if form:
        md5 = form_md5(form)
        hidden_md5 = form.md5.data 
        is_dirty = (md5 != hidden_md5)
        # if is_dirty:
        #     import os
        #     os.system('say "Beep"')
    return is_dirty


def validate_float(form, field):
    """Validate that the field data is a float, but allow an empty field."""
    if len(field.data) == 0:
        return
    try:
        _ = float(field.data)
    except ValueError:
        raise ValidationError('A numeric value is required')


def validate_integer(form, field):
    """Validate that the field data is an integer, but allow an empty field."""
    if len(field.data) == 0:
        return
    try:
        _ = int(field.data)
    except ValueError:
        raise ValidationError('An integer value is required')


class CheckboxField(SelectField):
    """A select field that displays a list of checkboxes rather than radio buttons."""
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class MultiCheckboxField(SelectMultipleField):
    """
    A multiple-select that displays a list of checkboxes.

    Iterating the field will produce subfields, allowing custom rendering of
    the enclosed checkbox fields.
    """
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


# The forms below are used in the home blueprint.

class OpenDocumentForm(FlaskForm):
    filename = SelectField('Document Name', choices=[])


class ImportEMLForm(FlaskForm):
    filename = SelectField('Document Name', choices=[])
    template = SelectField('Template', choices=[])

    def validate_filename(form, field):
        if not form.filename.choices:
            if form.template.data:
                # It's okay for the filename to be empty if the template is not empty.
                # This happens, for example, when a new user is working on their first and only document.
                return
        else:
            validators.AnyOf([value for value, _ in form.filename.choices])(form, field)


class ImportPackageForm(FlaskForm):
    pass


class ImportXmlForm(FlaskForm):
    pass


class ImportSingleItemForm(FlaskForm):
    to_import = RadioField('Import', choices=[], validators=[])


class ImportItemsForm(FlaskForm):
    to_import = MultiCheckboxField('Import', choices=[], validators=[])


class ImportItemsSortableForm(FlaskForm):
    to_import = MultiCheckboxField('Import', choices=[], validators=[])
    to_import_sorted = MultiCheckboxField('Import', choices=[], validators=[])


class ImportEMLItemsForm(FlaskForm):
    to_import = MultiCheckboxField('Import', choices=[], validators=[])
    target = RadioField('Target', choices=[], validators=[])


class ImportPartiesFromTemplateForm(FlaskForm):
    to_import = MultiCheckboxField('Import', choices=[], validators=[])
    to_import_sorted = MultiCheckboxField('Import', choices=[], validators=[])
    target = RadioField('Target', choices=[], validators=[])


class ImportKeywordsForm(FlaskForm):
    to_import = MultiCheckboxField('Import', choices=[], validators=[])
    to_import_sorted = MultiCheckboxField('Import', choices=[], validators=[])


class SelectUserForm(FlaskForm):
    user = RadioField('User', choices=[], validators=[])


class SelectDataFileForm(FlaskForm):
    data_file = RadioField('Data File', choices=[], validators=[])


class SelectEMLFileForm(FlaskForm):
    eml_file = RadioField('EML File', choices=[], validators=[])


class ImportEMLTargetForm(FlaskForm):
    target = RadioField('Target', choices=[])


class CreateEMLForm(FlaskForm):
    filename = StringField('Document Name', validators=[DataRequired()])


class DeleteEMLForm(FlaskForm):
    filename = SelectField('Document Name', choices=[])


class DownloadEMLForm(FlaskForm):
    filename = StringField('Document Name', validators=[DataRequired()])


class LoadDataForm(EDIForm):
    delimiter = SelectField('Field Delimiter', choices=[
        (',', 'comma'),
        ('\t', 'tab'),
        ('|', 'vertical bar, or pipe - |'),
        (';', 'semicolon'),
        (':', 'colon')
    ], default=','
    )
    quote = SelectField('Quote Character', choices=[
        ('"', 'double quote - "'),
        ("'", "single quote - '")
    ], default='"'
    )


class ReloadDataForm(EDIForm):
    delimiter = SelectField('Field Delimiter', choices=[
        (',', 'comma'),
        ('\t', 'tab'),
        ('|', 'vertical bar, or pipe - |'),
        (';', 'semicolon'),
        (':', 'colon')
    ], default=','
    )
    quote = SelectField('Quote Character', choices=[
        ('"', 'double quote - "'),
        ("'", "single quote - '")
    ], default='"'
    )
    update_codes = SelectField('Update Categorical Codes', choices=[
        ('yes', 'yes'),
        ('no', 'no')
    ], default='yes'
    )



class LoadOtherEntityForm(FlaskForm):
    pass


class LoadMetadataForm(FlaskForm):
    pass


class OpenEMLDocumentForm(FlaskForm):
    filename = SelectField('Document Name', choices=[])


class OpenTemplateForm(FlaskForm):
    filename = SelectField('Template Name', choices=[])


class SaveAsTemplateForm(FlaskForm):
    folder = RadioField('Template Folder', choices=[], validators=[DataRequired()])
    filename = StringField('Template Name', validators=[DataRequired()])


class DeleteTemplateForm(FlaskForm):
    filename = RadioField('Template Name', choices=[], validators=[DataRequired()])


class ValidateEMLFileForm(FlaskForm):
    filename = SelectField('EML XML File Name', choices=[])


class SaveAsForm(FlaskForm):
    filename = StringField('Document Name', validators=[DataRequired()])


class RenamePackageForm(FlaskForm):
    filename = StringField('New Document Name', validators=[DataRequired()])


class SubmitToEDIForm(FlaskForm):
    name = StringField('Your Name *', validators=[DataRequired()])
    email_address = StringField('Your Email Address *', validators=[Email(), DataRequired()])
    notes = StringField('Notes for EDI Data Curators (Optional)', widget=TextArea(), validators=[Optional()])


class SendToColleagueForm(FlaskForm):
    colleague_name = StringField("Colleague's Name *", validators=[DataRequired()])
    email_address = StringField("Colleague's Email Address *", validators=[Email(), DataRequired()])


class CollaborateForm(FlaskForm):
    pass


class AcceptInvitationForm(FlaskForm):
    invitation_code = StringField("Invitation Code *", validators=[DataRequired()])


class InviteCollaboratorForm(FlaskForm):
    user_name = StringField("Your Name *", validators=[DataRequired()])
    user_email = StringField("Your Email Address *", validators=[DataRequired()])
    collaborator_name = StringField("Collaborator's Name *", validators=[DataRequired()])
    email_address = StringField("Collaborator's Email Address *", validators=[Email(), DataRequired()])


class SettingsForm(FlaskForm):
    complex_text_editing_document = BooleanField('For the current EML document')
    complex_text_editing_global = BooleanField('For all EML documents')
    pass