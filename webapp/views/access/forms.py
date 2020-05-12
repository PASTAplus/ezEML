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

