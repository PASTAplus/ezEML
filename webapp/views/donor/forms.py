from wsgiref.validate import validator
from wtforms import (
    StringField, IntegerField, SelectField, HiddenField, Form, FormField, TextAreaField
)

from wtforms.validators import (
    Optional, NumberRange
)

from webapp.home.forms import EDIForm


class DonorForm(EDIForm):
    donorID = StringField('Donor ID', validators=[])
    donorGender = StringField('Gender', validators=[], default='female')
    donorYears = IntegerField('Years', validators=[NumberRange(min=0)])
    donorDays = IntegerField('Days', validators=[NumberRange(min=0)])
    donorLifeStage = SelectField('Life Stage',
                                 choices=[("", ""),
                                          ("fetal", "Fetal"),
                                          ("neonatal", "Neonatal"),
                                          ("prepubertal", "Prepubertal"),
                                          ("pubertal", "Pubertal"),
                                          ("adult", "Adult"),
                                          ("aging", "Aging")])
    specimenSeqNum = IntegerField('Specimen Sequence Number', validators=[NumberRange(min=0)])
    specimenTissue = StringField('Specimen Tissue', validators=[], default='ovary')
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
                                            ("unspecified", "Unspecified")],
                                   render_kw={'onchange': "specimenLocationFunction()"})
    corpusLuteum = SelectField('Corpus Luteum Type',
                               choices=[("", ""),
                                        ("early", "Early"),
                                        ("mid", "Mid"),
                                        ("late", "Late"),
                                        ("albicans", "Albicans")], validators=[Optional()])
    dayOfCycle = StringField('Day Of Cycle', validators=[])
    stageOfCycle = SelectField('Stage Of Cycle',
                               choices=[("", ""),
                                        ("follicular", "Follicular"),
                                        ("pre-ovulatory", "Pre-Ovulatory"),
                                        ("ovulation", "Ovulation"),
                                        ("luteal", "Luteal"),
                                        ("unspecified", "Unspecified")],
                               render_kw={'onchange': "stageOfCycleFunction()"})
    follicular = SelectField('Follicular values',
                             choices=[("", ""),
                                      ("early", "Early"),
                                      ("mid", "Mid"),
                                      ("late", "Late")], validators=[Optional()])
    luteal = SelectField('Luteal Values',
                         choices=[("", ""),
                                  ("early", "Early"),
                                  ("mid", "Mid"),
                                  ("late", "Late"),
                                  ("regression", "Regression")], validators=[Optional()])
    slideID = StringField('Slide ID', validators=[])
    sectionSeqNum = IntegerField('Section Sequence Number', validators=[NumberRange(min=0)])
    thickness = IntegerField('Section Thickness', validators=[NumberRange(min=0)])
    thicknessUnit = SelectField('Section Thickness Units',
                                choices=[("", ""),
                                         ("microns", "Microns"),
                                         ("nm", "NM")])
    fixation = SelectField('Fixation',
                           choices=[("", ""),
                                    ("neutralBufferedFormalin10", "Neutral Buffered Formalin10"),
                                    ("paraformaldehyde4", "Paraformaldehyde"),
                                    ("davidsons", "Davidsons"),
                                    ("neutralBufferedFormalin5aceticAcid", "Neutral Buffered Formalin5 acetic Acid"),
                                    ("bouins", "Bouins"),
                                    ("other", "Other")],
                           render_kw={'onchange': "fixationFunction()"})
    fixationOther = StringField('Other Fixation', validators=[Optional()])
    stain = SelectField('Stain',
                        choices=[("", ""),
                                 ("lightMicroscopyStain", "Light Microscopy Stain"),
                                 ("fluorescentMicroscopyStain", "Fluorescent Microscopy Stain"),
                                 ("electronMicroscopyStain", "Electron Microscopy Stain")],
                        render_kw={'onchange': "stainTypeFunction()"})
    lightMicroscopyStainType = SelectField('Stain Light Type',
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
                                                    ("other", "other")],
                                           render_kw={'onchange': "lightMicroscopyStainTypeFunction()"}, 
                                           validators=[Optional()])
    sudanStainType = SelectField('Sudan Stain Value',
                                 choices=[("", ""),
                                          ("III", "III"),
                                          ("IV", "IV"),
                                          ("Black B", "Black B"),
                                          ("Oil Red O", "Oil Red O"),
                                          ("Osmium Tetroxide", "Osmium tetroxide")], 
                                 validators=[Optional()])
    lightMicroscopyStainOther = StringField('Other Light Stain', validators=[])
    fluorescentMicroscopyStainType = SelectField('Stain Fluorescent Type',
                                                 choices=[("", ""),
                                                          ("acridineOrange", "Acridine Orange"),
                                                          ("calcein", "Calcein"),
                                                          ("DAPI", "DAPI"),
                                                          ("hoechst", "Hoechst"),
                                                          ("propidiumIodide", "Propidium Iodide"),
                                                          ("rhodamine", "Rhodamine"),
                                                          ("TUNEL", "TUNEL"),
                                                          ("other", "Other")],
                                                 render_kw={'onchange': "fluorescentMicroscopyStainTypeFunction()"},
                                                 validators=[Optional()])
    fluorescentMicroscopyStainOther = StringField('Other Fluorescent Stain', validators=[])
    electronMicroscopyStainType = SelectField('Stain Electron Type',
                                              choices=[("", ""),
                                                       ("colloidalgold", "Colloidal Gold"),
                                                       ("osmiumTetroxide", "Osmium Tetroxide"),
                                                       ("phosphotundsticAcid", "Phosphotundstic Acid"),
                                                       ("silverNitrate", "Silver Nitrate"),
                                                       ("other", "Other")],
                                              render_kw={'onchange': "electronMicroscopyStainTypeFunction()"},
                                              validators=[Optional()])
    electronMicroscopyStainOther = StringField('Other Electron Stain', validators=[])
    magnification = StringField('Magnification', validators=[])
    maker = StringField('Microscope Maker', validators=[])
    model = StringField('Microscope Model', validators=[])
    notes = TextAreaField('Microscope Notes')
    md5 = HiddenField('')

    def field_data(self) -> tuple:
        return (self.donorID.data,
                self.donorGender.data,
                self.donorYears.data,
                self.donorDays.data,
                self.donorLifeStage.data,
                self.specimenSeqNum.data,
                self.specimenTissue.data,
                self.ovaryPosition.data,
                self.specimenLocation.data,
                self.corpusLuteum.data,
                self.dayOfCycle.data,
                self.stageOfCycle.data,
                self.follicular.data,
                self.luteal.data,
                self.slideID.data,
                self.sectionSeqNum.data,
                self.thickness.data,
                self.thicknessUnit.data,
                self.fixation.data,
                self.fixationOther.data,
                self.stain.data,
                self.lightMicroscopyStainType.data,
                self.sudanStainType.data,
                self.lightMicroscopyStainOther.data,
                self.fluorescentMicroscopyStainType.data,
                self.fluorescentMicroscopyStainOther.data,
                self.electronMicroscopyStainType.data,
                self.electronMicroscopyStainOther.data,
                self.magnification.data,
                self.maker.data,
                self.model.data,
                self.notes.data)