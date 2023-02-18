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
        content += '\n' + para.content
    markdowns = []
    text_node.find_all_descendants(names.MARKDOWN, markdowns)
    for markdown in markdowns:
        content += '\n' + markdown.content
    return content


# ==================== Begin of rules section ====================

def _associated_responsible_party_rule(node: Node) -> list:
    return _responsible_party_rule(node)


def _contact_rule(node: Node) -> list:
    return _responsible_party_rule(node)


def _creator_rule(node: Node) -> list:
    return _responsible_party_rule(node)


def _dataset_rule(node: Node) -> list:
    evaluation = []
    abstract_node = None
    coverage_node = None
    datatable_node = None
    intellectual_rights_node = None
    keywordset_nodes = []
    methods_node = None
    project_node = None
    for child in node.children:
        if child.name == names.ABSTRACT:
            abstract_node = child
        elif child.name == names.COVERAGE:
            coverage_node = child
        elif child.name == names.DATATABLE:
            datatable_node = child
        elif child.name == names.INTELLECTUALRIGHTS:
            intellectual_rights_node = child
        elif child.name == names.KEYWORDSET:
            keywordset_nodes.append(child)
        elif child.name == names.METHODS:
            methods_node = child
        elif child.name == names.PROJECT:
            project_node = child

    if abstract_node:
        content = get_text_content(abstract_node)
        if content:
            words = content.split()
            if len(words) < 20:
                evaluation.append((
                    EvaluationWarning.DATASET_ABSTRACT_TOO_SHORT,
                    f'Consider increasing the length of the dataset''s abstract.',
                    node
                ))
        else:
            evaluation.append((
                EvaluationWarning.DATASET_ABSTRACT_MISSING,
                f'A dataset abstract should be provided.',
                node
            ))
    else:
        evaluation.append((
            EvaluationWarning.DATASET_ABSTRACT_MISSING,
            f'A dataset abstract should be provided.',
            node
        ))
    if not (coverage_node and coverage_node.children):
        evaluation.append((
            EvaluationWarning.DATASET_COVERAGE_MISSING,
            f'At least one coverage element should be present in a dataset. I.e., at least one of Geographic Coverage,'
            f' Temporal Coverage, or Taxonomic Coverage should be specified.',
            node
        ))
    if not datatable_node:
        evaluation.append((
            EvaluationWarning.DATATABLE_MISSING,
            f'A dataset should contain at least one Data Table.',
            node
        ))
    if not (intellectual_rights_node and intellectual_rights_node.content):
        evaluation.append((
            EvaluationWarning.INTELLECTUAL_RIGHTS_MISSING,
            f'An Intellectual Rights policy should be specified.',
            node
        ))
    if not keywordset_nodes:
        evaluation.append((
            EvaluationWarning.KEYWORDS_MISSING,
            f'Keywords should be provided to make the dataset more discoverable.',
            node
        ))
    else:
        num_keywords = 0
        for keywordset_node in keywordset_nodes:
            keyword_nodes = keywordset_node.find_all_children(names.KEYWORD)
            num_keywords += len(keyword_nodes)
        if num_keywords < 5:
            evaluation.append((
                EvaluationWarning.KEYWORDS_INSUFFICIENT,
                f'Consider adding more keywords to make the dataset more discoverable.',
                node
            ))
    if not methods_node:
        evaluation.append((
            EvaluationWarning.DATASET_METHOD_STEPS_MISSING,
            f'A dataset should contain at least one Method Step.',
            node
        ))
    if not project_node:
        evaluation.append((
            EvaluationWarning.DATASET_PROJECT_MISSING,
            f'A dataset should contain a Project.',
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
    donornodes = [False] * 19

    for child in node.children:
        if child.name == mdb_names.DONOR_ID and child.content:
            donornodes[0] = True
        if child.name == mdb_names.DONOR_GENDER and child.content:
            if child.content == "female":
                donornodes[15] = True
            donornodes[1] = True
        if child.name == mdb_names.DONOR_LIFE_STAGE and child.content:
            donornodes[2] = True
        if child.name == mdb_names.SPEC_SEQ_NUM and child.content:
            donornodes[3] = True
        if child.name == mdb_names.SPEC_TISSUE and child.content:
            if child.content == "ovary":
                donornodes[16] = True
            donornodes[4] = True
        if child.name == mdb_names.OVARY_POSITION and child.content:
            donornodes[5] = True
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
                        if val < 0:
                            raise ValueError
                    except ValueError:
                        donornodes[17] = True
                if schild.name == mdb_names.UNIT and schild.content:
                    donornodes[9] = True
        if child.name == mdb_names.SAMPLE_PROCESS:
            for spchild in child.children:
                # check for presence of children since they do not count as node content
                if spchild.name == mdb_names.FIXATION and spchild.children:
                    donornodes[10] = True
                if spchild.name == mdb_names.STAIN and spchild.children:
                    donornodes[11] = True
        if child.name == mdb_names.MAGNIFICATION and child.content:
            donornodes[12] = True
        if child.name == mdb_names.SPEC_CYCLE:
            for spcchild in child.children:
                if spcchild.name == mdb_names.STAGE_OF_CYCLE:
                    for stgchild in child.children:
                        print(stgchild.name)
                        for stgchild in stgchild.children:
                            print(stgchild.name)
                            if stgchild.name in mdb_names.CYCLE_STAGE:
                                print("valid")
                                donornodes[18] = True

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
            EvaluationWarningMp.DONOR_GENDER_MISSING,
            f'Donor Gender is required.',
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
            f'Donor Specimen Sequence Number is required.',
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
            EvaluationWarningMp.DONOR_GENDER_FEMALE,
            f'Donor Gender must be female.',
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
    if not donornodes[18]:
        evaluation.append((
            EvaluationWarningMp.DONOR_STAGE_OF_CYCLE_ENUM,
            f'Donor Stage of Cycle must be a valid stage.',
            node
        ))

    return evaluation


def _ihc_rule(node: Node) -> list:
    evaluation = []

    if node.children:
        # array that notes the presence of nodes and their contents
        ihcnodes = [False] * 17

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
