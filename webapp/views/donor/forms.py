from email import message
from wsgiref.validate import validator
from wtforms import (
    StringField, SelectField, IntegerField, HiddenField, Form, FormField, TextAreaField
)

from wtforms.validators import (
    Optional, NumberRange, InputRequired
)

from webapp.home.forms import EDIForm

from webapp.home.custom_validators import IntegerField


class DonorForm(EDIForm):
    donorType = SelectField('Cycle Type',
                                choices=[("",""),
                                         ("menstrual", "Menstrual"),
                                         ("estrous", "Estrous"),
                                         ("other", "Other")],
                                render_kw={'onchange': "speciesFunction(this.id, 'stageOfCycle')"})
    donorID = StringField('Donor ID *', validators=[InputRequired(message='Donor ID is required')])
    donorSex = StringField('Sex *', validators=[InputRequired(message='Sex is required')], default='female')
    donorYears = IntegerField('Years', validators=[NumberRange(min=0), Optional()])
    donorDays = IntegerField('Days', validators=[NumberRange(min=0), Optional()])
    donorLifeStage = SelectField('Life Stage *',
                                 choices=[("", ""),
                                          ("unspecified", "Unspecified"),
                                          ("fetal", "Fetal"),
                                          ("neonatal", "Neonatal"),
                                          ("prepubertal", "Prepubertal"),
                                          ("pubertal", "Pubertal"),
                                          ("adult", "Adult"),
                                          ("aging", "Aging")],
                                 validators=[InputRequired(message='Life Stage is required')])
    specimenSeqNum = IntegerField('Specimen Sequence Number *', 
                                validators=[NumberRange(min=0), InputRequired(message='Specimen Sequence Number is required')])
    specimenTissue = StringField('Specimen Tissue *', 
                                validators=[InputRequired(message='Specimen Tissue is required')],
                                default='ovary')
    ovaryPosition = SelectField('Ovary Position *',
                                choices=[("", ""),
                                         ("left", "Left"),
                                         ("right", "Right"),
                                         ("unspecified", "Unspecified")], 
                                validators=[InputRequired(message='Specimen Tissue is required')])
    specimenLocation = SelectField('Specimen Location *',
                                   choices=[("", ""),
                                            ("wholeOvary", "Whole Ovary"),
                                            ("ovarianCortex", "Ovarian Cortex"),
                                            ("ovarianMedulla", "Ovarian Medulla"),
                                            ("follicle", "Follicle"),
                                            ("corpusLuteum", "Corpus Luteum"),
                                            ("unspecified", "Unspecified")],
                                   render_kw={'onchange': "specimenLocationFunction()"},
                                   validators=[InputRequired(message='Specimen Location is required')])
    corpusLuteum = SelectField('Corpus Luteum Type',
                               choices=[("", ""),
                                        ("early", "Early"),
                                        ("mid", "Mid"),
                                        ("late", "Late"),
                                        ("albicans", "Albicans")], validators=[Optional()])
    dayOfCycle = StringField('Day Of Cycle', validators=[])
    stageOfCycle = SelectField('Stage Of Cycle',
                               choices=[("", ""),
                                        ("unspecified", "Unspecified"),
                                        ("follicular", "Follicular"),
                                        ("pre-ovulatory", "Pre-Ovulatory"),
                                        ("ovulation", "Ovulation"),
                                        ("luteal", "Luteal"),
                                        ("proestrus", "Proestrus"),
                                        ("estrus", "Estrus"),
                                        ("metestrus", "Metestrus"),
                                        ("diestrus", "Diestrus"),
                                        ("anestrus", "Anestrus")],
                               render_kw={'onchange': "stageOfCycleFunction()"})
    follicular = SelectField('Follicular Values',
                             choices=[("", ""),
                                      ("early", "Early"),
                                      ("mid", "Mid"),
                                      ("late", "Late")], validators=[Optional()])
    luteal = SelectField('Luteal Values',
                         choices=[("", ""),
                                  ("early", "Early"),
                                  ("mid", "Mid"),
                                  ("late", "Late"),
                                  ("regressing", "Regressing")], validators=[Optional()])
    slideID = StringField('Slide ID *', 
                        validators=[InputRequired(message='Slide ID is required')])
    sectionSeqNum = IntegerField('Section Sequence Number', 
                                validators=[NumberRange(min=0), Optional()])
    thickness = IntegerField('Section Thickness *', 
                            validators=[NumberRange(min=0), InputRequired(message='Thickness is required')])
    thicknessUnit = SelectField('Section Thickness Units *',
                                choices=[("", ""),
                                         ("microns", "Microns"),
                                         ("nm", "NM")],
                                validators=[InputRequired(message='Thickness Unit is required')])
    fixation = SelectField('Fixation *',
                           choices=[("", ""),
                                    ("neutralBufferedFormalin10", "Neutral Buffered Formalin10"),
                                    ("paraformaldehyde4", "Paraformaldehyde"),
                                    ("davidsons", "Davidsons"),
                                    ("neutralBufferedFormalin5aceticAcid", "Neutral Buffered Formalin5 acetic Acid"),
                                    ("bouins", "Bouins"),
                                    ("other", "Other")],
                           render_kw={'onchange': "fixationFunction()"},
                           validators=[InputRequired(message='Fixation is required')])
    fixationOther = StringField('Other Fixation', validators=[Optional()])
    stain = SelectField('Stain *',
                        choices=[("", ""),
                                 ("lightMicroscopyStain", "Light Microscopy Stain"),
                                 ("fluorescentMicroscopyStain", "Fluorescent Microscopy Stain"),
                                 ("electronMicroscopyStain", "Electron Microscopy Stain")],
                        render_kw={'onchange': "stainTypeFunction()"},
                        validators=[InputRequired(message='Stain is required')])
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
    magnification = StringField('Magnification *', validators=[InputRequired(message='Magnification is required')])
    maker = StringField('Microscope Maker', validators=[Optional()])
    model = StringField('Microscope Model', validators=[Optional()])
    notes = TextAreaField('Microscope Notes')
    md5 = HiddenField('')

    def field_data(self) -> tuple:
        return (self.donorID.data,
                self.donorSex.data,
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