from wtforms import (
    StringField, IntegerField, SelectField, HiddenField, Form, FormField, TextAreaField
)

from wtforms.validators import (
    Optional, NumberRange
)

from webapp.home.forms import EDIForm

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
    specimenSeqNum = IntegerField('Specimen Sequence Number', validators=[NumberRange(min=0)])
    specimenTissue = StringField('Specimen Tissue', validators=[], default ='ovary')
    ovaryPosition = SelectField('Ovary Position',
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
    corpusLuteumType = SelectField('Corpus Luteum Type',
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
    lutealType = SelectField('Luteal Values',
        choices=[("", ""),
            ("early", "Early"),
            ("mid", "Mid"),
            ("late", "Late"),
            ("regression", "Regression")])
    slideID = StringField('Slide ID', validators=[])
    sectionSeqNum = IntegerField('Section Sequence Number', validators=[NumberRange(min=0)])
    sectionThickness = IntegerField('Section Thickness', validators=[NumberRange(min=0)])
    sectionThicknessUnit = SelectField('Section Thickness Units',
        choices =[("", ""),
            ("microns","Microns"),
            ("nm", "NM")])
    fixation = SelectField('Fixation',
        choices=[("", ""),
            ("neutralBufferedFormalin10", "Neutral Buffered Formalin10"),
            ("paraformaldehyde4", "Paraformaldehyde"),
            ("davidsons", "Davidsons"),
            ("neutralBufferedFormalin5aceticAcid", "Neutral Buffered Formalin5 acetic Acid"),
            ("bouins", "Bouins"),
            ("other", "Other")])
    fixationOther = StringField('Other Fixation', validators=[])
    stain = SelectField('Stain',
        choices=[("", ""),
            ("lightMicroscopyStain", "Light Microscopy Stain"),
            ("fluorescentMicroscopyStain", "Fluorescent Microscopy Stain"),
            ("electronMicroscopyStain", "Electron Microscopy Stain")])
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
    sudanStainType = SelectField('Sudan Stain Value',
        choices=[("", ""),
            ("III", "III"),
            ("IV", "IV"),
            ("Black B", "Black B"),
            ("Oil Red O", "Oil Red O"),
            ("Osmium Tetroxide", "Osmium Tetroxide")])
    stainLightOther = StringField('Other Light Stain', validators=[])
    stainFluorescentType = SelectField('Stain Fluorescent Type',
        choices=[("", ""),
            ("acridineOrange", "Acridine Orange"),
            ("calcein", "Calcein"),
            ("DAPI", "DAPI"),
            ("hoechst", "Hoechst"),
            ("propidiumIodide", "Propidium Iodide"),
            ("rhodamine", "Rhodamine"),
            ("TUNEL", "TUNEL"),
            ("other", "Other")])
    stainFluorescentOther = StringField('Other Fluorescent Stain', validators=[])
    stainElectronType = SelectField('Stain Electron Type',
        choices=[("", ""),
            ("colloidalgold", "Colloidal Gold"),
            ("osmiumTetroxide", "Osmium Tetroxide"),
            ("phosphotundsticAcid", "Phosphotundstic Acid"),
            ("silverNitrate", "Silver Nitrate"),
            ("other", "Other")])
    stainElectronOther = StringField('Other Electron Stain', validators=[])
    magnification = StringField('Magnification', validators=[])
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
                self.specimenSeqNum.data,
                self.specimenTissue.data,
                self.ovaryPosition.data,
                self.specimenLocation.data,
                self.corpusLuteumType.data,
                self.dayOfCycle.data,
                self.stageOfCycle.data,
                self.follicularType.data,
                self.lutealType.data,
                self.slideID.data,
                self.sectionSeqNum.data,
                self.sectionThickness.data,
                self.sectionThicknessUnit.data,
                self.fixation.data,
                self.fixationOther.data,
                self.stain.data,
                self.stainLightType.data,
                self.sudanStainType.data,
                self.stainLightOther.data,
                self.stainFluorescentType.data,
                self.stainFluorescentOther.data,
                self.stainElectronType.data,
                self.stainElectronOther.data,
                self.magnification.data,
                self.maker.data,
                self.model.data,
                self.notes.data)
