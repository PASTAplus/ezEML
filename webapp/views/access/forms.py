"""
Not currently used. WTForms for setting access rules for a dataset,  but we don't expose that functionality to users,
currently.
"""

from wtforms import (
    StringField, SelectField, HiddenField
)

from webapp.home.forms import EDIForm


class AccessSelectForm(EDIForm):
    pass


class AccessForm(EDIForm):
    userid = StringField('User ID', validators=[])
    permission = SelectField('Permission',
                             choices=[("all", "all"), ("changePermission", "changePermission"), ("read", "read"), ("write", "write")])
    md5 = HiddenField('')
    init_str = 'all'

    # def field_data(self)->tuple:
    #     return (self.userid.data, self.permission.data)

