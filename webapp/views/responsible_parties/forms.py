from wtforms import (
    StringField, HiddenField
)

from wtforms.validators import (
    Email, URL, Optional
)

from webapp.home.forms import EDIForm


class ResponsiblePartySelectForm(EDIForm):
    pass


class ResponsiblePartyForm(EDIForm):
    salutation = StringField('Salutation', validators=[])
    gn = StringField('First Name', validators=[])
    sn = StringField('Last Name', validators=[])
    organization = StringField('Organization', validators=[])
    position_name = StringField('Position Name', validators=[])
    address_1 = StringField('Address 1', validators=[])
    address_2 = StringField('Address 2', validators=[])
    city = StringField('City', validators=[])
    state = StringField('State', validators=[])
    postal_code = StringField('Postal Code', validators=[])
    country = StringField('Country', validators=[])
    phone = StringField('Phone', validators=[])
    fax = StringField('Fax', validators=[])
    email = StringField('Email', validators=[Optional(), Email()])
    online_url = StringField('Online URL', validators=[Optional(), URL()])
    role = StringField('Role', validators=[])
    md5 = HiddenField('')

    def field_data(self)->tuple:
        return (self.salutation.data,
                self.gn.data,
                self.sn.data,
                self.organization.data,
                self.position_name.data,
                self.address_1.data,
                self.address_2.data,
                self.city.data,
                self.state.data,
                self.postal_code.data,
                self.country.data,
                self.phone.data,
                self.fax.data,
                self.email.data,
                self.online_url.data,
                self.role.data)
