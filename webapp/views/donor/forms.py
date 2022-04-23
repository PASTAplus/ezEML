from wtforms import (
    StringField, IntegerField, SelectField, HiddenField, Form, FormField, TextAreaField
)

from wtforms.validators import (
    Optional, NumberRange
)

from webapp.home.forms import EDIForm
"""
class microscopeForm(Form):
    maker = StringField('Maker', validators=[])
    model = StringField('Model', validators=[])
    notes = TextAreaField('Notes')
"""

class DonorForm(EDIForm):
    donorId = StringField('Donor ID', validators=[])
    donorGender = StringField('Gender', validators=[], default ='female')
    ageYears = IntegerField('Years', validators=[NumberRange(min = 0)])
    ageDays = IntegerField('Days', validators=[NumberRange(min = 0)])
    lifeStage = SelectField('Life Stage',
        choices=[("", ""),
            ("fetal", "Fetal"),
            ("neonatal", "Neonatal"),
            ("prepubertal", "Prepubertal"),
            ("pubertal", "Pubertal"),
            ("adult", "Adult"),
            ("aging", "Aging")])
    specimenTissue = StringField('Specimen Tissue', validators=[], default ='ovary')
    ovaryLocation = SelectField('Ovary Position',
        choices=[("", ""),
            ("left", "Left"),
            ("right", "Right"),
            ("unspecified", "Unspecified")])
    specimenLocation = SelectField('Specimen Location',
        choices=[("", ""),
            ("wholeOvary", "Whole Ovary"),
            ("ovarianCortex", "Ovarian Cortex"),
            ("ovarianMedulla", "Ovarian Medulla"),
            ("follicle", "Follicle"),
            ("corpusLuteum", "CorpusLuteum"),
            ("unspecified", "Unspecified")])
    corpusLectumType = SelectField('Luteum',
        choices=[("", ""),
            ("early", "Early"),
            ("mid", "Mid"),
            ("late", "Late"),
            ("albicans", "Albicans")])
    dayOfCycle = StringField('Day Of Cycle', validators=[])
    stageOfCycle = SelectField('Stage Of Cycle',
        choices=[("", ""),
            ("follicular", "Follicular"),
            ("pre-ovulatory", "Pre-Ovulatory"),
            ("ovulation", "Ovulation"),
            ("luteal", "Luteal"),
            ("unspecified", "Unspecified")])
    follicularType = SelectField('Follicular values',
        choices=[("", ""),
            ("early", "Early"),
            ("mid", "Mid"),
            ("late", "Late")])
    luteralType = SelectField('Luteal Values',
        choices=[("", ""),
            ("early", "Early"),
            ("mid", "Mid"),
            ("late", "Late"),
            ("regression", "Regression")])
    slideID = StringField('Slide ID', validators=[])
    sectionSeqNum = IntegerField('Section Sequence Number', validators=[NumberRange(min=0)])
    sectionThickness = IntegerField('Section Thickness', validators=[NumberRange(min=0)])
    sectionThicknessType = SelectField('Section Thickness Units',
        choices =[("", ""),
            ("microns","Microns"),
            ("nm", "NM")])
    sampleProcessing = SelectField('Sample Processing',
        choices=[("", ""),
            ("fixation", "Fixation"),
            ("stain", "Stain")])
    fixation = SelectField('Fixation',
        choices=[("", ""),
            ("neutralBufferedFormalin10", "Natural Buffered Formalin10"),
            ("paraformaldehyde4", "Paraformalhyde"),
            ("davidsons", "Davidsons"),
            ("neutralBufferedFormalin5aceticAcid", "Neutral Buffered Formalin Sacetic Acid"),
            ("bouins", "Bouins"),
            ("other", "Other")])
    stain = SelectField('Stain',
        choices=[("", ""),
            ("lightMicroscopyStain", "Light Microscopy Stain"),
            ("fluorescentMicroscopyStain", "Flourecent Microscopy Stain"),
            ("electronMicroscopyStain", "Electro Microscopy Stain")])
    sudanStainType = SelectField('Sudan Stain Value',
        choices=[("", ""),
            ("III", "III"),
            ("IV", "IV"),
            ("Black B", "Black B"),
            ("Oil Red O", "Oil Red O"),
            ("Osmium Tetroxide", "Osmium Tetroxide")])
    stainLightType = SelectField('Stain Light Type',
        choices=[("", ""),
            ("eosinOnly", "Eosin Only"),
            ("hematoxylinOnly", "Hematoxylin Only"),
            ("hematoxylinAndEosin", "Hematoxylin And Eosin"),
            ("masonsTrichrome", "Masons Trichrome"),
            ("mallorysTrichrome", "Mallorys Trichrome"),
            ("periodicAcidSchiff", "Periodic Acid Schiff"),
            ("sudan", "Sudan"),
            ("acidFuschin", "Acid Fuschin"),
            ("alcianBlue", "Alcian Blue"),
            ("azanTrichrome", "Azan Trichrome"),
            ("casansTrichrome", "Casans Trichrome"),
            ("cresylVioletNissl", "Cresyl VioletNissl"),
            ("giemsa", "Giemsa"),
            ("methyleneBlue", "Methylene Blue"),
            ("neutralRed", "Neutral Red"),
            ("nileBlue", "Nile Blue"),
            ("nileRed", "Nile Red"),
            ("orcein", "Orcein"),
            ("reticulin", "Reticulin"),
            ("toluidineBlue", "Toluidine Blue"),
            ("vanGieson", "Van Gieson"),
            ("other", "other")])
    stainForecentType = SelectField('Stain Forecent Type',
        choices=[("", ""),
            ("acridineOrange", "Acridine Orange"),
            ("calcein", "Calcein"),
            ("DAPI", "DAPI"),
            ("hoechst", "Hoechst"),
            ("propidiumIodide", "Propidium Iodide"),
            ("rhodamine", "Rhodamine"),
            ("TUNEL", "TUNEL"),
            ("other", "Other")])
    stainElectronType = SelectField('Stain Electron Type',
        choices=[("", ""),
            ("colloidalgold", "Colloidal Gold"),
            ("osmiumTetroxide", "Osmium Tetroxide"),
            ("phosphotundsticAcid", "Phosphotundstic Acid"),
            ("silverNitrate", "Silver Nitrate"),
            ("other", "Other")])
    magnification = StringField('Magnification', validators=[])
    #microscope = FormField(microscopeForm)
    maker = StringField('Microscope Maker', validators=[])
    model = StringField('Microscope Model', validators=[])
    notes = TextAreaField('Microscope Notes')
    md5 = HiddenField('')
        
    def field_data(self)->tuple:
        return (self.donorId.data,
                self.donorGender.data,
                self.ageYears.data,
                self.ageDays.data,
                self.lifeStage.data,
                self.specimenTissue.data,
                self.ovaryLocation.data,
                self.specimenLocation.data,
                self.corpusLectumType.data,
                self.dayOfCycle.data,
                self.stageOfCycle.data,
                self.follicularType.data,
                self.luteralType.data,
                self.slideID.data,
                self.sectionSeqNum.data,
                self.sectionThickness.data,
                self.sectionThicknessType.data,
                self.sampleProcessing.data,
                self.fixation.data,
                self.stain.data,
                self.sudanStainType.data,
                self.stainLightType.data,
                self.stainForecentType.data,
                self.stainElectronType.data,
                self.magnification.data,
                self.maker.data,
                self.model.data,
                self.notes.data)
