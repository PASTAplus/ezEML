from wtforms import (
    StringField, SelectField, HiddenField, validators
)

from wtforms.validators import (
    InputRequired
)

from wtforms.widgets import TextArea

from webapp.home.forms import EDIForm


class immunohistochemistryForm(EDIForm):
    pass


class immunohistochemistryForm(EDIForm):
    # Protein
    targetProtein = StringField('Target Protein', validators=[])
    # Primary Antibody
    clonality = SelectField('Clonality', choices=[("", ""), ("monoclonal", "monoclonal"), ("polyclonal", "polyclonal")])
    targetSpecies = StringField('Target Species', validators=[])
    hostSpecies = StringField('Host Species', validators=[])
    dilution = StringField('Dilution', validators=[])
    lotNumber = StringField('Lot Number', validators=[])
    catNumber = StringField('Cat Number', validators=[])
    # Source
    sourceName = StringField('Source Name', validators=[])
    sourceCity = StringField('Source City', validators=[])
    sourceState = StringField('Source State', validators=[])
    rrid = StringField('RRID', validators=[])
    # Secondary Antibody
    targetSpecies_2 = StringField('Target Species', validators=[])
    hostSpecies_2 = StringField('Host Species', validators=[])
    dilution_2 = StringField('Dilution', validators=[])
    lotNumber_2 = StringField('Lot Number', validators=[])
    catNumber_2 = StringField('Cat Number', validators=[])
    # Source_2
    sourceName_2 = StringField("Source Name", validators=[])
    sourceCity_2 = StringField("Source City", validators=[])
    sourceState_2 = StringField("Source State", validators=[])
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
