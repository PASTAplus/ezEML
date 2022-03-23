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


class ImmunohistochemistryForm(EDIForm):
    proteinName = StringField('Protein Name (Optional)', validators=[])
    geneSymbol = StringField('Gene Symbol', validators=[])
    # Primary Antibody
    clonality = SelectField('Clonality', choices=[("", ""), ("monoclonal", "monoclonal"), ("polyclonal", "polyclonal")])
    targetSpecies = StringField('Target Species', validators=[])
    hostSpecies = StringField('Host Species', validators=[])
    dilution = StringField('Dilution', validators=[])
    lotNumber = StringField('Lot Number', validators=[])
    catNumber = StringField('Cat Number', validators=[])
    source = StringField('Source', validators=[])
    rrid = StringField('RRID', validators=[])
    # Secondary Antibody
    targetSpecies2 = StringField('Target Species', validators=[])
    hostSpecies2 = StringField('Host Species', validators=[])
    dilution2 = StringField('Dilution', validators=[])
    lotNumber2 = StringField('Lot Number', validators=[])
    catNumber2 = StringField('Cat Number', validators=[])
    source2 = StringField('Source', validators=[])
    rrid2 = StringField('RRID', validators=[])
    detectionMethod = SelectField("Detection Method", choices=[
        ("ABC (avidin-biotin complex)", "ABC (avidin-biotin complex)",),
        ("Alkaline Phosphates", "Alkaline Phosphates"),
        ("Diaminobonzidine", "Diaminobonzidine"),
        ("FITC", "FITC"),
        ("Horseradish Peroxiduse", "Horseradish Peroxiduse"),
        ("LSAB (labeled streptavidin-biotin)", "LSAB (labeled streptavidin-biotin)"),
        ("RPE", "RPE")])

    def field_data(self) -> tuple:
        return (self.proteinName.data,
                self.geneSymbol.data,
                self.clonality.data,
                self.targetSpecies.data,
                self.hostSpecies.data,
                self.dilution.data,
                self.lotNumber.data,
                self.catNumber.data,
                self.source.data,
                self.rrid.data,
                self.targetSpecies2.data,
                self.hostSpecies2.data,
                self.dilution2.data,
                self.lotNumber2.data,
                self.catNumber2.data,
                self.source2.data,
                self.rrid2.data,
                self.detectionMethod.data)
