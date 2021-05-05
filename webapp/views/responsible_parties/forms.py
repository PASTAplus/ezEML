from wtforms import (
    StringField, SelectField, HiddenField
)

from wtforms.validators import (
    Email, URL, Optional
)

from webapp.home.forms import EDIForm


class ResponsiblePartySelectForm(EDIForm):
    pass


class ResponsiblePartyForm(EDIForm):
    salutation = StringField('Salutation (Optional)', validators=[])
    gn = StringField('First Name (Optional)', validators=[])
    mn = StringField('Middle Name/Initial (Optional)', validators=[])
    sn = StringField('Last Name', validators=[])
    organization = StringField('Organization', validators=[])
    org_id = StringField('Org ID (Optional)', validators=[])
    org_id_type = SelectField('Org ID Type (Required for Org ID)',
                              choices=[("", ""),
                                        ("https://www.grid.ac/", "GRID – Global Research Identifier Database"),
                                        ("https://isni.oclc.org/", "ISNI – International Standard Name Identifier"),
                                        ("https://ror.org/", "ROR – Research Organization Registry"),
                                        ("https://www.wikidata.org/", "Wikidata Organization Identifier")])
    position_name = StringField('Position Name', validators=[])
    address_1 = StringField('Address 1 (Optional)', validators=[])
    address_2 = StringField('Address 2 (Optional)', validators=[])
    city = StringField('City (Optional)', validators=[])
    state = StringField('State (Optional)', validators=[])
    postal_code = StringField('Postal Code (Optional)', validators=[])
    country = StringField('Country (Optional)', validators=[])
    phone = StringField('Phone (Optional)', validators=[])
    fax = StringField('Fax (Optional)', validators=[])
    email = StringField('Email (Recommended)', validators=[Optional(), Email()])
    user_id = StringField('ORCID ID (Recommended)', validators=[])
    online_url = StringField('Online URL (Optional)', validators=[Optional(), URL()])
    role = StringField('Role *', validators=[])
    md5 = HiddenField('')

    def field_data(self)->tuple:
        return (self.salutation.data,
                self.gn.data,
                self.mn.data,
                self.sn.data,
                self.user_id.data,
                self.organization.data,
                self.org_id.data,
                self.org_id_type,
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
