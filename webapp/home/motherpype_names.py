"""
:Mod:
    XML mdb constant values

:Synopsis:
    This file contains constant values for the motherdb node names, and complextypes as per
    the .xsd file. These values are used to help build the xml file but adding the values
    to the json file using the methods in the Node object

:Author:
    Pierce Tyler

:Created:
    7/23/2022
"""

import daiquiri

logger = daiquiri.getLogger("names: " + __name__)


"""
*
* CONSTANT DEFINITIONS
*
"""
# Root element
MOTHER = "mother"

# Donor Elements
DONOR = "donor"
DONOR_ID = "donorID"
DONOR_SEX = "donorSex"
DONOR_GENDER = "donorGender"

# has children
DONOR_AGE = "donorAge"
# donorAgeType
DONOR_YEARS = "donorYears"  # child of DONOR_AGE
DONOR_DAYS = "donorDays"    # child of DONOR_AGE

# this has xsi:type = "mdb:mammalianLifeStageType" as string values
DONOR_LIFE_STAGE = "donorLifeStage"
# mammalianLifeStateType
FETAL = "fetal"
NEONATAL = "neonatal"
PRE_PUBERTAL = "prepubertal"
PUBERTAL = "pubertal"
ADULT = "adult"
AGING = "aging"


SPEC_SEQ_NUM = "specimenSeqNum"
SPEC_TISSUE = "specimenTissue"
OVARY_POSITION = "ovaryPosition"

# this has xsi:type = "mdb:ovaryLocationType" as emptyElementType
SPEC_LOCATION = "specimenLocation"
# ovaryLocationType
WHOLE_OVARY = "wholeOvary"
OVARIAN_CORTEX = "ovarianCortex"
OVARIAN_MEDULLA = "ovarianMedulla"
FOLLICLE = "follicle"
# has own type
CORPUS_LUTEUM = "corpusLuteum"
# corpusLutemTypes (values) as strings
EARLY = "early"
MID = "mid"
LATE = "late"
ALBICANS = "albicans"

EMPTY_UNSPECIFIED = "unspecified"

# has children
SPEC_CYCLE = "specimenCycle"
DAY_OF_CYCLE = "dayOfCycle"      # child of SPEC_CYCLE
# this has xsi:type = "mdb:menstrualStageType" as emptyElementType
STAGE_OF_CYCLE = "stageOfCycle"  # child of SPEC_CYCLE
# menstrualStageType ---
# follicaular has own type (follicularType)
FOLLICULAR = "follicular"   # child of STAGE_OF_CYCLE
# follicularTypes (values) as strings
# EARLY = "early"   (this is defined already but here as a placeholder)
# MID = "mid"       (this is defined already but here as a placeholder)
# LATE = "late"     (this is defined already but here as a placeholder)

PRE_OVULATORY = "pre-ovulatory"  # child of STAGE_OF_CYCLE
OVULATION = "ovulation"          # child of STAGE_OF_CYCLE
# luteal has own type (lutealType)
LUTEAL = "luteal"                # child of STAGE_OF_CYCLE
# lutealTypes (values) as strings
# EARLY = "early"   (this is defined already but here as a placeholder)
# MID = "mid"       (this is defined already but here as a placeholder)
# LATE = "late"     (this is defined already but here as a placeholder)
REGRESSING = "regressing"  # unique luteal value
# UNSPECIFIED = "unspecified"  (this is defined already but here as a placeholder) # child of STAGE_OF_CYCLE
# estrous types
PROESTRUS = "proestrus"
ESTRUS = "estrus"
METESTRUS = "metestrus"
DIESTRUS = "diestrus"
ANESTRUS = "anestrus"

#Test for other choice
OTHER = "other"

SLIDE_ID = "slideID"
SEC_SEQ_NUM = "sectionSeqNum"

# has children
SECTION_THICKNESS = "sectionThickness"
THICKNESS = "thickness"  # child of SECTION_THICKNESS
UNIT = "unit"            # child of SECTION_THICKNESS

# has children
SAMPLE_PROCESS = "sampleProcessing"

# has unique values fixationType as emptyElementType
FIXATION = "fixation"  # child of SAMPLE_PROCESS
NEUTRAL_BUFFERED_FORMALIN10 = "neutralBufferedFormalin10"
PARA_FORMALDEHYDE = "paraformaldehyde4"
DAVIDSONS = "davidsons"
NEUTRAL_BUFFERED_FORMALIN5 = "neutralBufferedFormalin5aceticAcid"
BOUINS = "bouins"
# OTHER = "other"   defined below

# has children
STAIN = "stain"        # child of SAMPLE_PROCESS
# has unique values defined below (stainLightType)
LIGHT_MICRO_STAIN = "lightMicroscopyStain"      # child of STAIN
# has unique values defined below (stainFluorescentType)
FLU_MICRO_STAIN = "fluorescentMicroscopyStain"  # child of STAIN
# has unique values defined below (stainElectronType)
ELE_MICRO_STAIN = "electronMicroscopyStain"     # child of STAIN

# seems to set value = instead of have value in node (as per the examples)
MAGNIFICATION = "magnification"

# IHC section start ------->
IHC = "immunohistochemistry"

# IHC type
TARGET_PROTEIN = "targetProtein"

PRIMARY_ANTIBODY = "primaryAntibody"

CLONALITY = "clonality"
# clonality type values as enumerations
MONOCLONAL = "monoclonal"
POLYCLONAL = "polyclonal"

SECONDARY_ANTIBODY = "secondaryAntibody"

# antibodyTypeGroup
TARGET_SPECIES = "targetSpecies"
HOST_SPECIES = "hostSpecies"
DILUTION = "dilution"
LOT_NUMBER = "lotNumber"
CAT_NUMBER = "catNumber"
SOURCE = "source"
SOURCE_NAME = "sourceName"
SOURCE_CITY = "sourceCity"
SOURCE_STATE = "sourceState"
RRID = "RRID"

DETECTION_METHOD = "detectionMethod"
# detectionMethodTypeValues as enumerations
ABC = "ABC (avidin-biotin complex)"
ALKALINE_PHOS = "Alkaline phosphatase"
DIAMINOBENZIDINE = "Diaminobenzidine"
FITC = "FITC"
HORSERADISH_PERO = "Horseradish Peroxidase"
LSAB = "LSAB (labeled streptavidin-biotin)"
RPE = "RPE"
# <----------- IHC section end

# has children
MICROSCOPE = "microscope"
MICRO_MAKER = "maker"   # child of MICROSCOPE
MICRO_MODEL = "model"   # child of MICROSCOPE
MICRO_NOTES = "notes"   # child of MICROSCOPE

STRING_UNSPECIFIED = "unspecified"
STRING_OTHER = "other"

# stainLightType as emptyElementType
EOSIN_ONLY = "eosinOnly"
HEMA_ONLY = "hematoxylinOnly"
HEMA_EOSIN = "hematoxylinAndEosin"
MASONS_TRI = "masonsTrichrome"
MALLORYS_TRI = "mallorysTrichrome"
PERIODIC_ACID_SCHIFF = "periodicAcidSchiff"
# sudan has its own type (values) as strings
SUDAN = "sudan"
III = "III"
IV = "IV"
BLACK_B = "Black B"
OIL_RED_O = "Oil Red O"
OSMIUM_TETRAOXIDE = "Osmium tetroxide"
# end sudan types
ACID_FUSCHIN = "acidFuschin"
ALCIAN_BLUE = "alcianBlue"
AZAN_TRI = "azanTrichrome"
CASANS_TRI = "casansTrichrome"
CRESYL_VIOLET_NISSL = "cresylVioletNissl"
GIEMSA = "giesma"
METHYLENE_BLUE = "methyleneBlue"
NEUTRAL_RED = "neutralRed"
NILE_BLUE = "nileBlue"
NILE_RED = "nileRed"
ORCEIN = "orcein"
RETICULIN = "reticulin"
TOLUIDINE_BLUE = "toluidineBlue"
VAN_GIESON = "vanGieson"

# stainFluorescentType as emptyElementType
ACRIDINE_ORANGE = "acridineOrange"
CALCEIN = "calcein"
DAPI = "DAPI"
HOECHST = "hoechst"
PROP_IODIDE = "propidiumIodide"
RHODAMINE = "rhodamine"
TUNEL = "TUNEL"

# stainElectronType as emptyElementType
COLLOIDAL_GOLD = "colloidalGold"
OSMIUM_TETRO = "osmiumTetroxide"
PHOS_ACID = "phosphotundsticAcid"
SILVER_NITRATE = "silverNitrate"

MOTHER_PREFIX = "mdb"
XSI_TYPE = "xsi:type"
INTELLECTUAL_RIGHTS = 'intellectualRights'

FILENAME = "filename"
ADDITIONAL_INFO = "additionalInfo"

"""
*   SET_VALUE_NODES
*   A list containing the names of the elements whose value is defined within the tag
*   instead of in between the open and close tag
*   Example : <mdb:magnification value="10X"/>  VERSUS  <mdb:magnification>10X<magnification/>       
"""
SET_VALUE_NODES = [
    CORPUS_LUTEUM,
    FOLLICULAR,
    LUTEAL,
    SUDAN,
    MAGNIFICATION,
    CLONALITY,
    DETECTION_METHOD
]

"""
*   XSI_TYPE
*   All k,v pairs in this dictionary have 'xsi:type="theirValue"' as attributes
*   Example : <mdb:specimenLocation xsi:type="mdb:ovaryLocationType">
"""
XSI_TYPE = {
    DONOR_LIFE_STAGE: "mdb:mammalianLifeStageType",
    SPEC_LOCATION: "mdb:ovaryLocationType",
}

# Names for enumeration validators

MAMMAL_STAGE = {
    FOLLICULAR: "mdb:menstrualStageType",
    PRE_OVULATORY: "mdb:menstrualStageType",
    OVULATION: "mdb:menstrualStageType",
    LUTEAL: "mdb:menstrualStageType"
}

ESTROUS_STAGE = {
    PROESTRUS: "mdb:estrousStageType",
    ESTRUS: "mdb:estrousStageType",
    METESTRUS: "mdb:estrousStageType",
    DIESTRUS: "mdb:estrousStageType",
    ANESTRUS: "mdb:estrousStageType"
}

OTHER_STAGE = {
    OTHER: "mdb:otherStageType"
}

CYCLE_STAGE = {**MAMMAL_STAGE, **ESTROUS_STAGE, **OTHER_STAGE, EMPTY_UNSPECIFIED: ""}

MAMMAL_STAGE_VALUES = {
    FETAL,
    NEONATAL,
    PRE_PUBERTAL,
    PUBERTAL,
    ADULT,
    AGING
}

OVARY_POSITION_VALUES = {
    "left",
    "right",
    EMPTY_UNSPECIFIED
}

CORPUS_LUTEUM_VALUES = {
    EARLY,
    MID,
    LATE,
    ALBICANS
}

FOLLICULAR_VALUES = {
    EARLY,
    MID,
    LATE
}

LUTEAL_VALUES = {
    EARLY,
    MID,
    LATE,
    REGRESSING
}

UNIT_VALUES = {
    "microns",
    "nm"
}

SUDAN_VALUES = {
    "III",
    "IV",
    "Black B",
    "Oil Red O",
    "Osmium tetroxide",
}

CLONALITY_VALUES = {
    MONOCLONAL,
    POLYCLONAL
}

DETECTION_METHOD_VALUES = {
    "ABC (avidin-biotin complex)",
    "Alkaline phosphatase",
    "Diaminobenzidine",
    "FITC",
    "Horseradish Peroxidase",
    "LSAB (labeled streptavidin-biotin)",
    "RPE"
}

#   Choice Values
SPEC_LOCATION_VALUES = {
    WHOLE_OVARY,
    OVARIAN_CORTEX,
    OVARIAN_MEDULLA,
    FOLLICLE,
    CORPUS_LUTEUM,
    EMPTY_UNSPECIFIED
}

NILLABLE = {
    DONOR_YEARS,
    DONOR_DAYS,
    DONOR_AGE,
    SPEC_CYCLE,
    DAY_OF_CYCLE
}

OPTIONAL = {
    STAGE_OF_CYCLE,
    SEC_SEQ_NUM,
    IHC,
    RRID,
    MICROSCOPE,
    MICRO_NOTES
}