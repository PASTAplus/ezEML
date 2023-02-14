from wtforms import (
    StringField, SelectField, HiddenField, validators, RadioField
)

from wtforms.validators import (
    InputRequired
)

from wtforms.widgets import TextArea

from webapp.home.forms import EDIForm


class immunohistochemistryForm(EDIForm):
    pass


class immunohistochemistryForm(EDIForm):
    # IHC
    isIHC = SelectField('', choices=['Yes', 'No'],
                       render_kw={'onchange': "isIHCfunction()"})
    # Protein
    targetProtein = StringField('Target Protein *', validators=[InputRequired(message='Target Protein is required')])
    # Primary Antibody
    clonality = SelectField('Clonality', choices=[("", ""), ("monoclonal", "monoclonal"), ("polyclonal", "polyclonal")])
    targetSpecies = StringField('Target Species *', validators=[InputRequired(message='Target Species is required')])
    hostSpecies = StringField('Host Species *', validators=[InputRequired(message='Host Species is required')])
    dilution = StringField('Dilution *', validators=[InputRequired(message='Dilution is required')])
    lotNumber = StringField('Lot Number *', validators=[InputRequired(message='Lot Number is required')])
    catNumber = StringField('Cat Number *', validators=[InputRequired(message='Cat Number is required')])
    # Source
    sourceName = StringField('Source Name *', validators=[InputRequired(message='Source Name is required')])
    sourceCity = StringField('Source City *', validators=[InputRequired(message='Source City is required')])
    sourceState = StringField('Source State *', validators=[InputRequired(message='Source State is required')])
    rrid = StringField('RRID', validators=[])
    # Secondary Antibody
    targetSpecies_2 = StringField('Target Species *', validators=[InputRequired(message='Target Species is required')])
    hostSpecies_2 = StringField('Host Species *', validators=[InputRequired(message='Host Species is required')])
    dilution_2 = StringField('Dilution *', validators=[InputRequired(message='Dilution is required')])
    lotNumber_2 = StringField('Lot Number *', validators=[InputRequired(message='Lot Number is required')])
    catNumber_2 = StringField('Cat Number *', validators=[InputRequired(message='Cat Number is required')])
    # Source_2
    sourceName_2 = StringField('Source Name *', validators=[InputRequired(message='Source Name is required')])
    sourceCity_2 = StringField('Source City *', validators=[InputRequired(message='Source City is required')])
    sourceState_2 = StringField('Source State *', validators=[InputRequired(message='Source State is required')])
    rrid_2 = StringField('RRID', validators=[])
    # Detection Method
    detectionMethod = SelectField("Detection Method", choices=[
        ("ABC (avidin-biotin complex)", "ABC (avidin-biotin complex)",),
        ("Alkaline Phosphates", "Alkaline Phosphates"),
        ("Diaminobonzidine", "Diaminobonzidine"),
        ("FITC", "FITC"),
        ("Horseradish Peroxiduse", "Horseradish Peroxiduse"),
        ("LSAB (labeled streptavidin-biotin)", "LSAB (labeled streptavidin-biotin)"),
        ("RPE", "RPE")])

    def field_data(self) -> tuple:
        return (self.targetProtein.data,
                self.clonality.data,
                self.targetSpecies.data,
                self.hostSpecies.data,
                self.dilution.data,
                self.lotNumber.data,
                self.catNumber.data,
                self.sourceName.data,
                self.sourceCity.data,
                self.sourceState.data,
                self.rrid.data,
                self.targetSpecies_2.data,
                self.hostSpecies_2.data,
                self.dilution_2.data,
                self.lotNumber_2.data,
                self.catNumber_2.data,
                self.sourceName_2.data,
                self.sourceCity_2.data,
                self.sourceState_2.data,
                self.rrid_2.data,
                self.detectionMethod.data)

    def validate(self):
        if self.isIHC.data == "No":
            return True
        return super()