#!/usr/bin/env python
# -*- coding: utf-8 -*-

""":Mod: evaluate

:Synopsis:

:Author:
    servilla
    costa
    ide

:Created:
    6/21/18
"""

"""
    Modified to allow new functions for MOTHER to be added
"""

import daiquiri

from metapype.eml import names, evaluate
from metapype.model.node import Node
from metapype.eml.evaluation_warnings import EvaluationWarning

from webapp.validate.evaluation_warnings_mp import EvaluationWarningMp
import webapp.home.motherpype_names as mdb_names


logger = daiquiri.getLogger("evaluate: " + __name__)


def get_text_content(text_node: Node) -> str:
    # Collect the text under a TextType node.
    # This is intended for use in checking if text is present and that it has enough words, if there is
    #  such a requirement. I.e., it doesn't worry about getting the text in the correct order if, for example, there
    #  are para and markdown nodes interleaved.
    content = text_node.content if text_node.content else ''
    paras = []
    text_node.find_all_descendants(names.PARA, paras)
    for para in paras:
        if para.content:
            content += '\n' + para.content
    markdowns = []
    text_node.find_all_descendants(names.MARKDOWN, markdowns)
    for markdown in markdowns:
        if markdown.content:
            content += '\n' + markdown.content
    return content


# ==================== Begin of rules section ====================

def _associated_responsible_party_rule(node: Node) -> list:
    return _responsible_party_rule(node)


def _contact_rule(node: Node) -> list:
    return _responsible_party_rule(node)


def _creator_rule(node: Node) -> list:
    return _responsible_party_rule(node)


def check_taxon(node: Node, rank, value):
    nodes = [False] * 2
    for child in node.children:
        if child.name == rank and child.content == value:
            nodes[0] = True
        if child.name == names.TAXONRANKVALUE and child.content:
            nodes[1] = True
    if all(nodes):
        return True
    for child in node.children:
        if child.name == names.TAXONOMICCLASSIFICATION:
            return check_taxon(child, rank, value)
    return False


def _dataset_rule(node: Node) -> list:
    evaluation = []

    datanodes = [False] * 5
    for child in node.children:
        if child.name == names.COVERAGE:
            for cchild in child.children:
                if cchild.name == names.TAXONOMICCOVERAGE:
                    datanodes[0] = True
                    # check that any genus or species is present at all in the project
                    if check_taxon(cchild, names.TAXONRANKNAME, 'Genus'):
                        datanodes[2] = True
                    if check_taxon(cchild, names.TAXONRANKNAME, 'Species'):
                        datanodes[3] = True
                if cchild.name == names.TEMPORALCOVERAGE:
                    datanodes[1] = True
        if child.name == names.INTELLECTUALRIGHTS:
            for cchild in child.children:
                if cchild.name == names.PARA and cchild.content:
                    datanodes[4] = True

    if not datanodes[0]:
        evaluation.append((
            EvaluationWarningMp.TAXONOMIC_COVERAGE_MISSING,
            f'Taxonomic Coverage is required.',
            node
        ))
    if not datanodes[1]:
        evaluation.append((
            EvaluationWarningMp.TEMPORAL_COVERAGE_MISSING,
            f'Temporal Coverage is highly recommended, e.g. collection date.',
            node
        ))
    if not datanodes[2]:
        evaluation.append((
            EvaluationWarningMp.TAXONOMIC_COVERAGE_GENUS_MISSING,
            f'Taxon Genus is required',
            node
        ))
    if not datanodes[3]:
        evaluation.append((
            EvaluationWarningMp.TAXONOMIC_COVERAGE_SPECIES_MISSING,
            f'Taxon Species is required',
            node
        ))
    if not datanodes[4]:
        evaluation.append((
            EvaluationWarningMp.INTELLECTUAL_RIGHTS_MISSING,
            f'An Intellectual Rights policy should be specified.,',
            node
        ))
    return evaluation


def _datatable_rule(node: Node) -> list:
    evaluation = []
    description = any(
        child.name == names.ENTITYDESCRIPTION and child.content
        for child in node.children
    )
    if not description:
        evaluation.append((
            EvaluationWarning.DATATABLE_DESCRIPTION_MISSING,
            f'A data table Description is highly recommended.',
            node
        ))
    return evaluation


def _description_rule(node: Node) -> list:
    # Various description nodes are required but since they have TextType, the rules allow them to be empty.
    # Require them to have nonempty content (including para and markdown children).
    evaluation = []
    warning = None
    content = get_text_content(node)
    if not content:
        parent = node.parent.name
        if parent == 'connectionDefinition':
            warning = EvaluationWarning.CONNECTION_DEFINITION_DESCRIPTION_MISSING
        elif parent == 'designDescription':
            warning = EvaluationWarning.DESIGN_DESCRIPTION_DESCRIPTION_MISSING
        elif parent == 'maintenance':
            warning = EvaluationWarning.MAINTENANCE_DESCRIPTION_MISSING
        elif parent == 'methodStep':
            warning = EvaluationWarning.METHOD_STEP_DESCRIPTION_MISSING
        elif parent == 'procedureStep':
            warning = EvaluationWarning.PROCEDURE_STEP_DESCRIPTION_MISSING
        elif parent == 'qualityControl':
            warning = EvaluationWarning.QUALITY_CONTROL_DESCRIPTION_MISSING
        elif parent == 'samplingDescription':
            warning = EvaluationWarning.SAMPLING_DESCRIPTION_DESCRIPTION_MISSING
        elif parent == 'studyExtent':
            warning = EvaluationWarning.STUDY_EXTENT_DESCRIPTION_MISSING
    if warning:
        evaluation.append((
            warning,
            f'A Description is required.',
            node
        ))
    return evaluation


def _individual_name_rule(node: Node) -> list:
    evaluation = []
    givename = False
    surname = False
    for child in node.children:
        if child.name == names.GIVENNAME and child.content:
            givename = True
        if child.name == names.SURNAME and child.content:
            surname = True
    if givename and surname:
        evaluation = None
    else:
        evaluation.append((
            EvaluationWarning.INDIVIDUAL_NAME_INCOMPLETE,
            f'An individual\'s name should have both a "{names.GIVENNAME}" and a "{names.SURNAME}"',
            node
        ))
    return evaluation


def _responsible_party_rule(node: Node) -> list:
    evaluation = []
    userid = False
    orcid = False
    email = False
    for child in node.children:
        if child.name == names.USERID and child.content:
            userid = True
            if child.attributes.get('directory') == 'https://orcid.org':
                orcid = True
        if child.name == names.ELECTRONICMAILADDRESS and child.content:
            email = True
    if not orcid:
        evaluation.append((
            EvaluationWarning.ORCID_ID_MISSING,
            f'An ORCID ID is recommended."',
            node
        ))
    if not userid:
        evaluation.append((
            EvaluationWarning.USER_ID_MISSING,
            f'A User ID should be provided. An ORCID ID is recommended."',
            node
        ))
    if not email:
        evaluation.append((
            EvaluationWarning.EMAIL_MISSING,
            f'An email address should be provided."',
            node
        ))
    return evaluation


def _metadata_provider_rule(node: Node) -> list:
    return _responsible_party_rule(node)


def _image_rule(node: Node) -> list:
    evaluation = []

    imagenodes = [False] * 3

    for child in node.children:
        if child.name == names.ENTITYNAME and child.content:
            imagenodes[0] = True
        if child.name == names.ENTITYTYPE and child.content:
            imagenodes[1] = True
        if child.name == names.PHYSICAL:
            ext_node = child.find_single_node_by_path([names.DATAFORMAT, names.EXTERNALLYDEFINEDFORMAT])
            for extchild in ext_node.children:
                if extchild.name == names.FORMATNAME and extchild.content:
                    imagenodes[2] = True

    if not imagenodes[0]:
        evaluation.append((
            EvaluationWarningMp.IMAGE_NAME_MISSING,
            f'Image Name is required."',
            node
        ))
    if not imagenodes[1]:
        evaluation.append((
            EvaluationWarningMp.IMAGE_TYPE_MISSING,
            f'Image Type is required."',
            node
        ))
    if not imagenodes[2]:
        evaluation.append((
            EvaluationWarningMp.IMAGE_FORMAT_MISSING,
            f'Image Data Format is required."',
            node
        ))

    return evaluation

def _donor_rule(node: Node) -> list:
    evaluation = []

    # array that notes the presence of nodes and their contents
    donornodes = [False] * 40

    for child in node.children:
        if child.name == mdb_names.DONOR_ID and child.content:
            donornodes[0] = True
        if child.name == mdb_names.DONOR_SEX and child.content:
            if child.content == "female":
                donornodes[15] = True
            donornodes[1] = True
        if child.name == mdb_names.DONOR_LIFE_STAGE and child.content:
            donornodes[2] = True
            if child.content in mdb_names.MAMMAL_STAGE_VALUES:
                donornodes[19] = True
        if child.name == mdb_names.SPEC_SEQ_NUM and child.content:
            try:
                val = int(child.content)
                if val < 0:
                    raise ValueError
                else:
                    donornodes[3] = True
            except ValueError:
                pass
        if child.name == mdb_names.SPEC_TISSUE and child.content:
            if child.content == "ovary":
                donornodes[16] = True
            donornodes[4] = True
        if child.name == mdb_names.OVARY_POSITION and child.content:
            donornodes[5] = True
            if child.content in mdb_names.OVARY_POSITION_VALUES:
                donornodes[20] = True
        if child.name == mdb_names.SLIDE_ID and child.content:
            donornodes[6] = True
        # if child.name == mdb_names.SEC_SEQ_NUM and child.content:
        #     donornodes[7] = True
        if child.name == mdb_names.SECTION_THICKNESS:
            for schild in child.children:
                if schild.name == mdb_names.THICKNESS and schild.content:
                    donornodes[8] = True
                    # check if Section Thickness is a positive integer
                    try:
                        val = int(schild.content)
                        if val <= 0:
                            raise ValueError
                    except ValueError:
                        donornodes[17] = True
                if schild.name == mdb_names.UNIT and schild.content:
                    donornodes[9] = True
                    if schild.content in mdb_names.UNIT_VALUES:
                        donornodes[21] = True
        if child.name == mdb_names.SAMPLE_PROCESS:
            for spchild in child.children:
                # check for presence of children since they do not count as node content
                if spchild.name == mdb_names.FIXATION and spchild.children:
                    donornodes[10] = True
                if spchild.name == mdb_names.STAIN and spchild.children:
                    donornodes[11] = True
                    for stchild in spchild.children:
                        if stchild.name == mdb_names.LIGHT_MICRO_STAIN:
                            for lmchild in stchild.children:
                                if lmchild.name == mdb_names.SUDAN and lmchild.content not in mdb_names.SUDAN_VALUES:
                                    donornodes[25] = True

        if child.name == mdb_names.MAGNIFICATION:
            if child.attributes.get("value", None):
                donornodes[12] = True
            elif child.content:
                donornodes[12] = True
        if child.name == mdb_names.SPEC_CYCLE:
            for spcchild in child.children:
                if spcchild.name == mdb_names.STAGE_OF_CYCLE:
                    for stgchild in child.children:
                        for stage in stgchild.children:
                            if stage.name not in mdb_names.CYCLE_STAGE:
                                donornodes[18] = True
                            if stage.name == mdb_names.FOLLICULAR and stage.content not in mdb_names.FOLLICULAR_VALUES:
                                donornodes[23] = True
                            if stage.name == mdb_names.LUTEAL and stage.content not in mdb_names.LUTEAL_VALUES:
                                donornodes[24] = True
                if spcchild.name == mdb_names.DAY_OF_CYCLE:
                    if spcchild.content:
                        try:
                            val = int(spcchild.content)
                            if val < 0:
                                raise ValueError
                            else:
                                donornodes[28] = True
                        except ValueError:
                            pass
                    else:
                        donornodes[28] = True   # Node is not required to have content
        if child.name == mdb_names.SPEC_LOCATION:
            for slchild in child.children:
                if slchild.name == mdb_names.CORPUS_LUTEUM and slchild.content not in mdb_names.CORPUS_LUTEUM_VALUES:
                    donornodes[22] = True
                if slchild.name not in mdb_names.SPEC_LOCATION_VALUES:
                    donornodes[30] = True
        if child.name == mdb_names.DONOR_AGE:
            for achild in child.children:
                if achild.name == mdb_names.DONOR_YEARS:
                    if achild.content:
                        try:
                            val = int(achild.content)
                            if val < 0:
                                raise ValueError
                            else:
                                donornodes[26] = True
                        except ValueError:
                            pass
                    else:
                        donornodes[26] = True   # Node is not required to have content
                if achild.name == mdb_names.DONOR_DAYS:
                    if achild.content:
                        try:
                            val = int(achild.content)
                            if val < 0:
                                raise ValueError
                            else:
                                donornodes[27] = True
                        except ValueError:
                            pass
                    else:
                        donornodes[27] = True  # Node is not required to have content
        if child.name == mdb_names.SEC_SEQ_NUM:
            if child.content:
                try:
                    val = int(child.content)
                    if val < 0:
                        raise ValueError
                    else:
                        donornodes[29] = True
                except ValueError:
                    pass
            else:
                donornodes[29] = True  # Node is not required to have content


        # if child.name == mdb_names.MICROSCOPE:
        #     for mchild in child.children:
        #         if mchild.name == mdb_names.MICRO_MAKER and mchild.content:
        #             donornodes[13] = True
        #         if mchild.name == mdb_names.MICRO_MODEL and mchild.content:
        #             donornodes[14] = True

    if not donornodes[0]:
        evaluation.append((
            EvaluationWarningMp.DONOR_ID_MISSING,
            f'Donor ID is required.',
            node
        ))
    if not donornodes[1]:
        evaluation.append((
            EvaluationWarningMp.DONOR_SEX_MISSING,
            f'Donor Sex is required.',
            node
        ))
    if not donornodes[2]:
        evaluation.append((
            EvaluationWarningMp.DONOR_LIFE_STAGE_MISSING,
            f'Donor Life Stage is required.',
            node
        ))
    if not donornodes[3]:
        evaluation.append((
            EvaluationWarningMp.DONOR_SPEC_SEQ_NUM_MISSING,
            f'Donor Specimen Sequence Number is required and must be a non-negative value.',
            node
        ))
    if not donornodes[4]:
        evaluation.append((
            EvaluationWarningMp.DONOR_SPEC_TISSUE_MISSING,
            f'Donor Specimen Tissue is required.',
            node
        ))
    if not donornodes[5]:
        evaluation.append((
            EvaluationWarningMp.DONOR_OVARY_POSITION_MISSING,
            f'Donor Ovary Position is required.',
            node
        ))
    if not donornodes[6]:
        evaluation.append((
            EvaluationWarningMp.DONOR_SLIDE_ID_MISSING,
            f'Donor Slide ID is required.',
            node
        ))
    # if not donornodes[7]:
    #     evaluation.append((
    #         EvaluationWarningMp.DONOR_SEC_SEQ_NUM_MISSING,
    #         f'Donor Section Sequence Number is required.',
    #         node
    #     ))
    if not donornodes[8]:
        evaluation.append((
            EvaluationWarningMp.DONOR_SEC_THICK_MISSING,
            f'Donor Section Thickness is required.',
            node
        ))
    if not donornodes[9]:
        evaluation.append((
            EvaluationWarningMp.DONOR_SEC_THICK_UNITS_MISSING,
            f'Donor Section Thickness Units are required.',
            node
        ))
    if not donornodes[10]:
        evaluation.append((
            EvaluationWarningMp.DONOR_FIXATION_MISSING,
            f'Donor Stain is required.',
            node
        ))
    if not donornodes[11]:
        evaluation.append((
            EvaluationWarningMp.DONOR_STAIN_MISSING,
            f'Donor Fixation is required.',
            node
        ))
    if not donornodes[12]:
        evaluation.append((
            EvaluationWarningMp.DONOR_MAGNIFICATION_MISSING,
            f'Donor Magnification is required.',
            node
        ))
    # if not donornodes[13]:
    #     evaluation.append((
    #         EvaluationWarningMp.DONOR_MICRO_MAKER_MISSING,
    #         f'Donor Microscope Maker is required.',
    #         node
    #     ))
    # if not donornodes[14]:
    #     evaluation.append((
    #         EvaluationWarningMp.DONOR_MICRO_MODEL_MISSING,
    #         f'Donor Microscope Model is required.',
    #         node
    #     ))
    if not donornodes[15]:
        evaluation.append((
            EvaluationWarningMp.DONOR_SEX_FEMALE,
            f'Donor Sex must be female.',
            node
        ))
    if not donornodes[16]:
        evaluation.append((
            EvaluationWarningMp.DONOR_SPEC_TISSUE_OVARY,
            f'Donor Specimen Tissue must be ovary.',
            node
        ))
    if donornodes[17]:
        evaluation.append((
            EvaluationWarningMp.DONOR_SEC_THICK_POSITIVE_INT,
            f'Donor Section Thickness must be a positive integer.',
            node
        ))
    if donornodes[18]:
        evaluation.append((
            EvaluationWarningMp.DONOR_STAGE_OF_CYCLE_ENUM,
            f'Donor Stage of Cycle must be a valid stage.',
            node
        ))
    if not donornodes[19]:
        evaluation.append((
            EvaluationWarningMp.DONOR_LIFE_STAGE_ENUM,
            f'Donor Life Stage must be a valid stage.',
            node
        ))
    if not donornodes[20]:
        evaluation.append((
            EvaluationWarningMp.DONOR_OVARY_POSITION_ENUM,
            f'Donor Ovary Position must be a valid position.',
            node
        ))
    if not donornodes[21]:
        evaluation.append((
            EvaluationWarningMp.DONOR_SEC_THICK_UNITS_ENUM,
            f'Donor Ovary Position must be a valid position.',
            node
        ))
    if donornodes[22]:
        evaluation.append((
            EvaluationWarningMp.DONOR_CORPUS_LUTEUM_ENUM,
            f'Donor Corpus Luteum Type must be a valid type.',
            node
        ))
    if donornodes[23]:
        evaluation.append((
            EvaluationWarningMp.DONOR_FOLLICULAR_ENUM,
            f'Donor Follicular Values must be a valid type.',
            node
        ))
    if donornodes[24]:
        evaluation.append((
            EvaluationWarningMp.DONOR_LUTEAL_ENUM,
            f'Donor Luteal Values must be a valid type.',
            node
        ))
    if donornodes[25]:
        evaluation.append((
            EvaluationWarningMp.DONOR_SUDAN_STAIN_ENUM,
            f'Donor Sudan Stain Value must be a valid value.',
            node
        ))
    if not donornodes[26]:
        evaluation.append((
            EvaluationWarningMp.DONOR_YEARS_NON_NEGATIVE,
            f'Donor Years must be a non-negative value.',
            node
        ))
    if not donornodes[27]:
        evaluation.append((
            EvaluationWarningMp.DONOR_DAYS_NON_NEGATIVE,
            f'Donor Days must be a non-negative value.',
            node
        ))
    if not donornodes[28]:
        evaluation.append((
            EvaluationWarningMp.DONOR_DAY_OF_CYCLE_NON_NEGATIVE,
            f'Donor Day Of Cycle must be a non-negative value.',
            node
        ))
    if not donornodes[29]:
        evaluation.append((
            EvaluationWarningMp.DONOR_SEC_SEQ_NUM_NON_NEGATIVE,
            f'Donor Section Sequence Number must be a non-negative value.',
            node
        ))
    if donornodes[30]:
        evaluation.append((
            EvaluationWarningMp.DONOR_SPEC_LOCATION_CHOICE,
            f'Donor Specimen Location is required and must be a valid value.',
            node
        ))

    return evaluation


def _ihc_rule(node: Node) -> list:
    evaluation = []

    if node.children:
        # array that notes the presence of nodes and their contents
        ihcnodes = [False] * 18

        for child in node.children:
            if child.name == mdb_names.TARGET_PROTEIN and child.content:
                ihcnodes[0] = True
            if child.name == mdb_names.PRIMARY_ANTIBODY:
                for schild in child.children:
                    if schild.name == mdb_names.TARGET_SPECIES and schild.content:
                        ihcnodes[1] = True
                    if schild.name == mdb_names.HOST_SPECIES and schild.content:
                        ihcnodes[2] = True
                    if schild.name == mdb_names.DILUTION and schild.content:
                        ihcnodes[3] = True
                    if schild.name == mdb_names.LOT_NUMBER and schild.content:
                        ihcnodes[4] = True
                    if schild.name == mdb_names.CAT_NUMBER and schild.content:
                        ihcnodes[5] = True
                    if schild.name == mdb_names.SOURCE:
                        for srchild in schild.children:
                            if srchild.name == mdb_names.SOURCE_NAME and srchild.content:
                                ihcnodes[6] = True
                            if srchild.name == mdb_names.SOURCE_CITY and srchild.content:
                                ihcnodes[7] = True
                            if srchild.name == mdb_names.SOURCE_STATE and srchild.content:
                                ihcnodes[8] = True
                    if schild.name == mdb_names.CLONALITY and schild.content not in mdb_names.CLONALITY_VALUES:
                        ihcnodes[17] = True
            if child.name == mdb_names.SECONDARY_ANTIBODY:
                for schild in child.children:
                    if schild.name == mdb_names.TARGET_SPECIES and schild.content:
                        ihcnodes[9] = True
                    if schild.name == mdb_names.HOST_SPECIES and schild.content:
                        ihcnodes[10] = True
                    if schild.name == mdb_names.DILUTION and schild.content:
                        ihcnodes[11] = True
                    if schild.name == mdb_names.LOT_NUMBER and schild.content:
                        ihcnodes[12] = True
                    if schild.name == mdb_names.CAT_NUMBER and schild.content:
                        ihcnodes[13] = True
                    if schild.name == mdb_names.SOURCE:
                        for srchild in schild.children:
                            if srchild.name == mdb_names.SOURCE_NAME and srchild.content:
                                ihcnodes[14] = True
                            if srchild.name == mdb_names.SOURCE_CITY and srchild.content:
                                ihcnodes[15] = True
                            if srchild.name == mdb_names.SOURCE_STATE and srchild.content:
                                ihcnodes[16] = True

        if not ihcnodes[0]:
            evaluation.append((
                EvaluationWarningMp.IHC_TARGET_PROTEIN_MISSING,
                f'Target Protein is required.',
                node
            ))
        if not ihcnodes[1]:
            evaluation.append((
                EvaluationWarningMp.IHC_PRIMARY_ANTIBODY_TARGET_SPECIES_MISSING,
                f'Primary Antibody Target Species is required.',
                node
            ))
        if not ihcnodes[2]:
            evaluation.append((
                EvaluationWarningMp.IHC_PRIMARY_ANTIBODY_HOST_SPECIES_MISSING,
                f'Primary Antibody Host Species is required.',
                node
            ))
        if not ihcnodes[3]:
            evaluation.append((
                EvaluationWarningMp.IHC_PRIMARY_ANTIBODY_DILUTION_MISSING,
                f'Primary Antibody Dilution is required.',
                node
            ))
        if not ihcnodes[4]:
            evaluation.append((
                EvaluationWarningMp.IHC_PRIMARY_ANTIBODY_LOT_NUMBER_MISSING,
                f'Primary Antibody Lot Number is required.',
                node
            ))
        if not ihcnodes[5]:
            evaluation.append((
                EvaluationWarningMp.IHC_PRIMARY_ANTIBODY_CAT_NUMBER_MISSING,
                f'Primary Antibody Cat Number is required.',
                node
            ))
        if not ihcnodes[6]:
            evaluation.append((
                EvaluationWarningMp.IHC_PRIMARY_ANTIBODY_SOURCE_NAME_MISSING,
                f'Primary Antibody Source Name is required.',
                node
            ))
        if not ihcnodes[7]:
            evaluation.append((
                EvaluationWarningMp.IHC_PRIMARY_ANTIBODY_SOURCE_CITY_MISSING,
                f'Primary Antibody Source City is required.',
                node
            ))
        if not ihcnodes[8]:
            evaluation.append((
                EvaluationWarningMp.IHC_PRIMARY_ANTIBODY_SOURCE_STATE_MISSING,
                f'Primary Antibody Source State is required.',
                node
            ))
        if not ihcnodes[9]:
            evaluation.append((
                EvaluationWarningMp.IHC_SECONDARY_ANTIBODY_TARGET_SPECIES_MISSING,
                f'Secondary Antibody Target Species is required.',
                node
            ))
        if not ihcnodes[10]:
            evaluation.append((
                EvaluationWarningMp.IHC_SECONDARY_ANTIBODY_HOST_SPECIES_MISSING,
                f'Secondary Antibody Host Species is required.',
                node
            ))
        if not ihcnodes[11]:
            evaluation.append((
                EvaluationWarningMp.IHC_SECONDARY_ANTIBODY_DILUTION_MISSING,
                f'Secondary Antibody Dilution is required.',
                node
            ))
        if not ihcnodes[12]:
            evaluation.append((
                EvaluationWarningMp.IHC_SECONDARY_ANTIBODY_LOT_NUMBER_MISSING,
                f'Secondary Antibody Lot Number is required.',
                node
            ))
        if not ihcnodes[13]:
            evaluation.append((
                EvaluationWarningMp.IHC_SECONDARY_ANTIBODY_CAT_NUMBER_MISSING,
                f'Secondary Antibody Cat Number is required.',
                node
            ))
        if not ihcnodes[14]:
            evaluation.append((
                EvaluationWarningMp.IHC_SECONDARY_ANTIBODY_SOURCE_NAME_MISSING,
                f'Secondary Antibody Source Name is required.',
                node
            ))
        if not ihcnodes[15]:
            evaluation.append((
                EvaluationWarningMp.IHC_SECONDARY_ANTIBODY_SOURCE_CITY_MISSING,
                f'Secondary Antibody Source City is required.',
                node
            ))
        if not ihcnodes[16]:
            evaluation.append((
                EvaluationWarningMp.IHC_SECONDARY_ANTIBODY_SOURCE_STATE_MISSING,
                f'Secondary Antibody Source State is required.',
                node
            ))
        if ihcnodes[17]:
            evaluation.append((
                EvaluationWarningMp.IHC_PRIMARY_ANTIBODY_CLONALITY_ENUM,
                f'Primary Antibody Clonality must be a valid value.',
                node
            ))

    return evaluation


def _personnel_rule(node: Node) -> list:
    return _responsible_party_rule(node)


def _title_rule(node: Node) -> list:
    evaluation = []
    title = node.content
    if title is not None:
        length = len(title.split(" "))
        if length < 5:
            evaluation.append((
                EvaluationWarning.TITLE_TOO_SHORT,
                f'The title "{title}" is too short. A title should have at least 5 words;'
                f' between 7 and 20 words is recommended.',
                node
            ))
    return evaluation


# ===================== End of rules section =====================


def node(node: Node):
    """
    Evaluates a given node for rule compliance.

    Args:
        node: Node instance to be evaluated

    Returns:
        None or evaluation dict
    """
    evaluation = None
    if node.name in rules:
        evaluation = rules[node.name](node)
    return evaluation


def tree(root: Node, warnings: list):
    """
    Recursively walks from the root node and evaluates
    each child node for rule compliance.

    Args:
        root: Node instance of root for evaluation
        warnings: List of warnings collected during the evaluation

    Returns:
        None
    """
    evaluation = node(root)
    if evaluation is not None:
        warnings.extend(evaluation)
    for child in root.children:
        tree(child, warnings)


# Rule function pointers
rules = {
    names.ASSOCIATEDPARTY: _associated_responsible_party_rule,
    names.CONTACT: _contact_rule,
    names.CREATOR: _creator_rule,
    names.DATASET: _dataset_rule,
    names.DATATABLE: _datatable_rule,
    names.DESCRIPTION: _description_rule,
    names.INDIVIDUALNAME: _individual_name_rule,
    names.METADATAPROVIDER: _metadata_provider_rule,
    names.OTHERENTITY: _image_rule,
    names.PERSONNEL: _personnel_rule,
    names.TITLE: _title_rule,
    mdb_names.MOTHER: _donor_rule,
    mdb_names.IHC: _ihc_rule,
}
