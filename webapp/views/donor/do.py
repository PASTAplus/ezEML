from flask import (
    Blueprint, render_template, redirect, request, url_for
)

from webapp.views.donor.forms import (
    DonorForm
)

from webapp.home.forms import (
    form_md5, is_dirty_form
)

from webapp.home.metapype_client import (
    load_eml, save_both_formats,
)

from webapp.home.motherpype import (
    add_mother_metadata, create_donor
)

from metapype.eml import names
from metapype.model.node import Node

from webapp.home import motherpype_names as mdb_names

from webapp.buttons import *
from webapp.pages import *

from webapp.home.views import set_current_page, get_help


do_bp = Blueprint('do', __name__, template_folder='templates')

def select_new_page(back_page=None, next_page=None, edit_page=None):
    form_value = request.form
    form_dict = form_value.to_dict(flat=False)
    new_page = back_page
    if form_dict:
        for key in form_dict:
            val = form_dict[key][0]  # value is the first list element

            if val == BTN_BACK:
                new_page = back_page
                break
            elif val in (BTN_NEXT, BTN_SAVE_AND_CONTINUE):
                new_page = next_page
                break
            elif val == BTN_HIDDEN_NEW:
                new_page = PAGE_CREATE
                break
            elif val == BTN_HIDDEN_OPEN:
                new_page = PAGE_OPEN
                break
            elif val == BTN_HIDDEN_CLOSE:
                new_page = PAGE_CLOSE
                break

    return new_page


"""
    Function:       donor
    Params:         filename: the current filename
    Description:    Updates the current page (for proper navigation on the webpage)
    Returns:        Returns the result of new_donor function      
"""


@do_bp.route('/donor/<filename>', methods=['GET', 'POST'])
def donor(filename=None):
    method = request.method
    node_id = '1'

    if filename:
        eml_node = load_eml(filename=filename)
        additional_metadata_node = eml_node.find_child(names.ADDITIONALMETADATA)
        if additional_metadata_node:
            metadata_node = additional_metadata_node.find_child(names.METADATA)
            mother_node = metadata_node.find_child(mdb_names.MOTHER)
            if mother_node:
                node_id = mother_node.id
        else:
            add_mother_metadata(eml_node, filename=filename)

    save_both_formats(filename, eml_node)

    set_current_page('donor')
    help = [get_help('donor')]
    return new_donor(filename=filename, node_id=node_id,
                     method=method, node_name='donor',
                     back_page=PAGE_RELATED_PROJECT_SELECT, next_page=PAGE_IHC, title='Donor',
                     save_and_continue=True, help=help)


"""
    Function:       new_donor
    Params:         filename: the current filename
    Description:    POST Request - Creates the donor nodes based off form values
                    GET  Request - Updates the values of the donor nodes based off form values 
    Returns:        Returns the next page (ihc)
"""


def new_donor(filename=None, node_id=None, method=None,
              node_name=None, back_page=None, title=None,
              next_page=None, save_and_continue=False, help=None,
              project_node_id=None):

    if BTN_CANCEL in request.form:
        if not project_node_id:
            url = url_for(back_page, filename=filename)
        else:
            url = url_for(back_page, filename=filename, node_id=project_node_id)
        return redirect(url)

    form = DonorForm(filename=filename)
    eml_node = load_eml(filename=filename)

    additional_metadata_node = eml_node.find_child(names.ADDITIONALMETADATA)
    metadata_node = additional_metadata_node.find_child(names.METADATA)
    mother_node = metadata_node.find_child("mother")

    new_page = select_new_page(back_page, next_page)

    # Process POST
    save = False
    if is_dirty_form(form):
        save = True
    
    if form.validate_on_submit() and method == 'POST':
        if save:
            donorID = form.donorID.data
            donorSex = form.donorSex.data
            donorAge = Node('donorAge', parent=None)
            donorYears = form.donorYears.data
            donorDays = form.donorDays.data
            donorLifeStage = form.donorLifeStage.data
            donorType = form.donorType.data
            specimenSeqNum = form.specimenSeqNum.data
            specimenTissue = form.specimenTissue.data
            ovaryPosition = form.ovaryPosition.data
            specimenLocation = form.specimenLocation.data
            corpusLuteum = form.corpusLuteum.data
            specimenCycle = Node('specimenCycle', parent=None)
            dayOfCycle = form.dayOfCycle.data
            stageOfCycle = form.stageOfCycle.data
            follicular = form.follicular.data
            luteal = form.luteal.data
            slideID = form.slideID.data
            sectionSeqNum = form.sectionSeqNum.data
            sectionThickness = Node('thickness', parent=None)
            thickness = form.thickness.data
            thicknessUnit = form.thicknessUnit.data
            sampleProcessing = Node('sampleProcessing', parent=None)
            fixation = form.fixation.data
            fixationOther = form.fixationOther.data
            stain = form.stain.data
            stainType = Node('stainType', parent=None)
            lightMicroscopyStainType = form.lightMicroscopyStainType.data
            sudanStainType = form.sudanStainType.data
            lightMicroscopyStainOther = form.lightMicroscopyStainOther.data
            fluorescentMicroscopyStainType = form.fluorescentMicroscopyStainType.data
            fluorescentMicroscopyStainOther = form.fluorescentMicroscopyStainOther.data
            electronMicroscopyStainType = form.electronMicroscopyStainType.data
            electronMicroscopyStainOther = form.electronMicroscopyStainOther.data
            magnification = form.magnification.data
            microscopeType = Node('microscope', parent=None)
            maker = form.maker.data
            model = form.model.data
            notes = form.notes.data

            create_donor(
                mother_node,
                filename,
                donorID,
                donorSex,
                donorAge,
                donorYears,
                donorDays,
                donorLifeStage,
                specimenSeqNum,
                specimenTissue,
                ovaryPosition,
                specimenLocation,
                dayOfCycle,
                stageOfCycle,
                follicular,
                luteal,
                slideID,
                sectionSeqNum,
                sectionThickness,
                thickness,
                thicknessUnit,
                sampleProcessing,
                fixation,
                fixationOther,
                stain,
                stainType,
                lightMicroscopyStainType,
                sudanStainType,
                lightMicroscopyStainOther,
                fluorescentMicroscopyStainType,
                fluorescentMicroscopyStainOther,
                electronMicroscopyStainType,
                electronMicroscopyStainOther,
                magnification,
                microscopeType,
                maker,
                model,
                notes)

            if specimenLocation:
                create_specimen_location(
                    mother_node, 
                    specimenLocation, 
                    corpusLuteum)
            elif specimenLocation == "":
                specimenLocation_node = mother_node.find_child(mdb_names.SPEC_LOCATION)
                specimenLocation_node.remove_children()

            if stageOfCycle:
                create_stage_of_cycle(
                    mother_node, 
                    stageOfCycle, 
                    follicular, 
                    luteal)
                cycleType_node = mother_node.find_child(mdb_names.SPEC_CYCLE)
                stageOfCycle_node = cycleType_node.find_child(mdb_names.STAGE_OF_CYCLE)

                if donorType == "menstrual":
                    stageOfCycle_node.add_extras("xsi:type", "mdb:menstrualStageType")
                elif donorType == "estrous":
                    stageOfCycle_node.add_extras("xsi:type", "mdb:estrousStageType")

            elif stageOfCycle == "":
                cycleType_node = mother_node.find_child(mdb_names.SPEC_CYCLE)
                stageOfCycle_node = cycleType_node.find_child(mdb_names.STAGE_OF_CYCLE)
                cycleType_node.remove_child(stageOfCycle_node)

            if fixation:
                create_fixation(
                    mother_node, 
                    fixation, 
                    fixationOther)

            if stain:
                create_stain(
                    mother_node, 
                    stain,
                    lightMicroscopyStainType,
                    sudanStainType,
                    lightMicroscopyStainOther,
                    fluorescentMicroscopyStainType,
                    fluorescentMicroscopyStainOther,
                    electronMicroscopyStainType,
                    electronMicroscopyStainOther)

            if notes == "" and maker == "" and model == "":
                microscopeType_node = mother_node.find_child(mdb_names.MICROSCOPE)
                mother_node.remove_child(microscopeType_node)
            elif notes == "":
                microscopeType_node = mother_node.find_child(mdb_names.MICROSCOPE)
                microNotes_node = microscopeType_node.find_child(mdb_names.MICRO_NOTES)
                microscopeType_node.remove_child(microNotes_node)

            save_both_formats(filename=filename, eml_node=eml_node)
        return redirect(url_for(new_page, filename = filename))

    # Process GET
    if node_id == '1':
        form.init_md5()
    elif node_id:
        related_project_node = Node.get_node_instance(node_id)
        populate_donor_form(form, related_project_node)
    return render_template('donor.html', title=title, node_name=node_name, form=form,
                            next_page=next_page, save_and_continue=save_and_continue, help=help)


"""
    Function:       populate_donor_form
    Params:         form: the values from the donor form
                    node: mother_node
    Description:    populates the html donor form display if the values exist
"""


def populate_donor_form(form: DonorForm, node: Node):
    donorID_node = node.find_child(mdb_names.DONOR_ID)
    if donorID_node:
        form.donorID.data = donorID_node.content

    donorSex_node = node.find_child(mdb_names.DONOR_SEX)
    if donorSex_node.content:
        form.donorSex.data = donorSex_node.content

    donorAge_Node = node.find_child(mdb_names.DONOR_AGE)
    if donorAge_Node:
        donorYears_node = donorAge_Node.find_child(mdb_names.DONOR_YEARS)
        if donorYears_node:
            form.donorYears.data = donorYears_node.content

        donorDays_node = donorAge_Node.find_child(mdb_names.DONOR_DAYS)
        if donorDays_node:
            form.donorDays.data = donorDays_node.content

    donorLifeStage_node = node.find_child(mdb_names.DONOR_LIFE_STAGE)
    if donorLifeStage_node:
        form.donorLifeStage.data = donorLifeStage_node.content

    specimenSeqNum_node = node.find_child(mdb_names.SPEC_SEQ_NUM)
    if specimenSeqNum_node:
        form.specimenSeqNum.data = specimenSeqNum_node.content

    specimenTissue_node = node.find_child(mdb_names.SPEC_TISSUE)
    if specimenTissue_node.content:
        form.specimenTissue.data = specimenTissue_node.content

    ovaryPosition_node = node.find_child(mdb_names.OVARY_POSITION)
    if ovaryPosition_node:
        form.ovaryPosition.data = ovaryPosition_node.content

    specimenLocation_node = node.find_child(mdb_names.SPEC_LOCATION)
    if specimenLocation_node:
        wholeOvary_node = specimenLocation_node.find_child(mdb_names.WHOLE_OVARY)
        if wholeOvary_node:
            form.specimenLocation.data = wholeOvary_node.name
        ovarianCortex_node = specimenLocation_node.find_child(mdb_names.OVARIAN_CORTEX)
        if ovarianCortex_node:
            form.specimenLocation.data = ovarianCortex_node.name
        ovarianMedulla_node = specimenLocation_node.find_child(mdb_names.OVARIAN_MEDULLA)
        if ovarianMedulla_node:
            form.specimenLocation.data = ovarianMedulla_node.name
        follicle_node = specimenLocation_node.find_child(mdb_names.FOLLICLE)
        if follicle_node:
            form.specimenLocation.data = follicle_node.name
        unspecified_node = specimenLocation_node.find_child(mdb_names.EMPTY_UNSPECIFIED)
        if unspecified_node:
            form.specimenLocation.data = unspecified_node.name
        corpusLuteum_node = specimenLocation_node.find_child(mdb_names.CORPUS_LUTEUM)
        if corpusLuteum_node:
            form.specimenLocation.data = corpusLuteum_node.name
            form.corpusLuteum.data = corpusLuteum_node.attributes.get("value", None)
            if not form.corpusLuteum.data:
                form.corpusLuteum.data = corpusLuteum_node.content

    specimenCycle_node = node.find_child(mdb_names.SPEC_CYCLE)
    if specimenCycle_node:
        dayOfCycle_node = specimenCycle_node.find_child(mdb_names.DAY_OF_CYCLE)
        if dayOfCycle_node:
            form.dayOfCycle.data = dayOfCycle_node.content

        stageOfCycle_node = specimenCycle_node.find_child(mdb_names.STAGE_OF_CYCLE)
        if stageOfCycle_node:
            follicular_node = stageOfCycle_node.find_child(mdb_names.FOLLICULAR)
            if follicular_node:
                form.stageOfCycle.data = follicular_node.name
                form.follicular.data = follicular_node.attributes.get("value", None)
                if not form.follicular.data:
                    form.follicular.data = follicular_node.content
            pre_ovulatory_node = stageOfCycle_node.find_child(mdb_names.PRE_OVULATORY)
            if pre_ovulatory_node:
                form.stageOfCycle.data = pre_ovulatory_node.name
            ovulation_node = stageOfCycle_node.find_child(mdb_names.OVULATION)
            if ovulation_node:
                form.stageOfCycle.data = ovulation_node.name
            luteal_node = stageOfCycle_node.find_child(mdb_names.LUTEAL)
            if luteal_node:
                form.stageOfCycle.data = luteal_node.name
                form.luteal.data = luteal_node.attributes.get("value", None)
                if not form.luteal.data:
                    form.luteal.data = luteal_node.content
            unspecified_node = stageOfCycle_node.find_child(mdb_names.EMPTY_UNSPECIFIED)
            if unspecified_node:
                form.stageOfCycle.data = unspecified_node.name

            proestrus_node = stageOfCycle_node.find_child(mdb_names.PROESTRUS)
            if proestrus_node:
                form.stageOfCycle.data = proestrus_node.name
            estrus_node = stageOfCycle_node.find_child(mdb_names.ESTRUS)
            if estrus_node:
                form.stageOfCycle.data = estrus_node.name
            metestrus_node = stageOfCycle_node.find_child(mdb_names.METESTRUS)
            if metestrus_node:
                form.stageOfCycle.data = metestrus_node.name
            diestrus_node = stageOfCycle_node.find_child(mdb_names.DIESTRUS)
            if diestrus_node:
                form.stageOfCycle.data = diestrus_node.name
            anestrus_node = stageOfCycle_node.find_child(mdb_names.ANESTRUS)
            if anestrus_node:
                form.stageOfCycle.data = anestrus_node.name

        if stageOfCycle_node:
            extras = stageOfCycle_node.extras
            if "xsi:type" in extras:
                xsi_type = extras.pop("xsi:type")
                if xsi_type == "mdb:menstrualStageType":
                    form.donorType.data = "menstrual"
                if xsi_type == "mdb:estrousStageType":
                    form.donorType.data = "estrous"

    slideID_node = node.find_child(mdb_names.SLIDE_ID)
    if slideID_node:
        form.slideID.data = slideID_node.content

    sectionSeqNum_node = node.find_child(mdb_names.SEC_SEQ_NUM)
    if sectionSeqNum_node:
        form.sectionSeqNum.data = sectionSeqNum_node.content

    sectionThickness_node = node.find_child(mdb_names.SECTION_THICKNESS)
    if sectionThickness_node:
        thickness_node = sectionThickness_node.find_child(mdb_names.THICKNESS)
        if thickness_node:
            form.thickness.data = thickness_node.content

        thicknessUnit_node = sectionThickness_node.find_child(mdb_names.UNIT)
        if thicknessUnit_node:
            form.thicknessUnit.data = thicknessUnit_node.content

    sampleProcessing_node = node.find_child(mdb_names.SAMPLE_PROCESS)
    if sampleProcessing_node:
        fixation_node = sampleProcessing_node.find_child(mdb_names.FIXATION)
        if fixation_node:
            neutralBufferedFormalin10_node = fixation_node.find_child(mdb_names.NEUTRAL_BUFFERED_FORMALIN10)
            if neutralBufferedFormalin10_node:
                form.fixation.data = neutralBufferedFormalin10_node.name
            paraformaldehyde4_node = fixation_node.find_child(mdb_names.PARA_FORMALDEHYDE)
            if paraformaldehyde4_node:
                form.fixation.data = paraformaldehyde4_node.name
            davidsons_node = fixation_node.find_child(mdb_names.DAVIDSONS)
            if davidsons_node:
                form.fixation.data = davidsons_node.name
            neutralBufferedFormalin5aceticAcid_node = fixation_node.find_child(mdb_names.NEUTRAL_BUFFERED_FORMALIN5)
            if neutralBufferedFormalin5aceticAcid_node:
                form.fixation.data = neutralBufferedFormalin5aceticAcid_node.name
            bouins_node = fixation_node.find_child(mdb_names.BOUINS)
            if bouins_node:
                form.fixation.data = bouins_node.name
            fixationOther_node = fixation_node.find_child(mdb_names.STRING_OTHER)
            if fixationOther_node:
                form.fixation.data = fixationOther_node.name
                form.fixationOther.data = fixationOther_node.content
        stain_node = sampleProcessing_node.find_child(mdb_names.STAIN)
        if stain_node:
            lightMicroscopyStain_node = stain_node.find_child(mdb_names.LIGHT_MICRO_STAIN)
            if lightMicroscopyStain_node:
                form.stain.data = lightMicroscopyStain_node.name
                eosinOnly_node = lightMicroscopyStain_node.find_child(mdb_names.EOSIN_ONLY)
                if eosinOnly_node:
                    form.lightMicroscopyStainType.data = eosinOnly_node.name
                hematoxylinOnly_node = lightMicroscopyStain_node.find_child(mdb_names.HEMA_ONLY)
                if hematoxylinOnly_node:
                    form.lightMicroscopyStainType.data = hematoxylinOnly_node.name
                hematoxylinAndEosin_node = lightMicroscopyStain_node.find_child(mdb_names.HEMA_EOSIN)
                if hematoxylinAndEosin_node:
                    form.lightMicroscopyStainType.data = hematoxylinAndEosin_node.name
                masonsTrichrome_node = lightMicroscopyStain_node.find_child(mdb_names.MASONS_TRI)
                if masonsTrichrome_node:
                    form.lightMicroscopyStainType.data = masonsTrichrome_node.name
                mallorysTrichrome_node = lightMicroscopyStain_node.find_child(mdb_names.MALLORYS_TRI)
                if mallorysTrichrome_node:
                    form.lightMicroscopyStainType.data = mallorysTrichrome_node.name
                periodicAcidSchiff_node = lightMicroscopyStain_node.find_child(mdb_names.PERIODIC_ACID_SCHIFF)
                if periodicAcidSchiff_node:
                    form.lightMicroscopyStainType.data = periodicAcidSchiff_node.name
                sudan_node = lightMicroscopyStain_node.find_child(mdb_names.SUDAN)
                if sudan_node:
                    form.lightMicroscopyStainType.data = sudan_node.name
                    form.sudanStainType.data = sudan_node.attributes.get("value", None)
                    if not form.sudanStainType.data:
                        form.sudanStainType.data = sudan_node.content
                acidFuschin_node = lightMicroscopyStain_node.find_child(mdb_names.ACID_FUSCHIN)
                if acidFuschin_node:
                    form.lightMicroscopyStainType.data = acidFuschin_node.name
                alcianBlue_node = lightMicroscopyStain_node.find_child(mdb_names.ALCIAN_BLUE)
                if alcianBlue_node:
                    form.lightMicroscopyStainType.data = alcianBlue_node.name
                azanTrichrome_node = lightMicroscopyStain_node.find_child(mdb_names.AZAN_TRI)
                if azanTrichrome_node:
                    form.lightMicroscopyStainType.data = azanTrichrome_node.name
                casansTrichrome_node = lightMicroscopyStain_node.find_child(mdb_names.CASANS_TRI)
                if casansTrichrome_node:
                    form.lightMicroscopyStainType.data = casansTrichrome_node.name
                cresylVioletNissl_node = lightMicroscopyStain_node.find_child(mdb_names.CRESYL_VIOLET_NISSL)
                if cresylVioletNissl_node:
                    form.lightMicroscopyStainType.data = cresylVioletNissl_node.name
                giemsa_node = lightMicroscopyStain_node.find_child(mdb_names.GIEMSA)
                if giemsa_node:
                    form.lightMicroscopyStainType.data = giemsa_node.name
                methyleneBlue_node = lightMicroscopyStain_node.find_child(mdb_names.METHYLENE_BLUE)
                if methyleneBlue_node:
                    form.lightMicroscopyStainType.data = methyleneBlue_node.name
                neutralRed_node = lightMicroscopyStain_node.find_child(mdb_names.NEUTRAL_RED)
                if neutralRed_node:
                    form.lightMicroscopyStainType.data = neutralRed_node.name
                nileBlue_node = lightMicroscopyStain_node.find_child(mdb_names.NILE_BLUE)
                if nileBlue_node:
                    form.lightMicroscopyStainType.data = nileBlue_node.name
                nileRed_node = lightMicroscopyStain_node.find_child(mdb_names.NILE_RED)
                if nileRed_node:
                    form.lightMicroscopyStainType.data = nileRed_node.name
                orcein_node = lightMicroscopyStain_node.find_child(mdb_names.ORCEIN)
                if orcein_node:
                    form.lightMicroscopyStainType.data = orcein_node.name
                reticulin_node = lightMicroscopyStain_node.find_child(mdb_names.RETICULIN)
                if reticulin_node:
                    form.lightMicroscopyStainType.data = reticulin_node.name
                toluidineBlue_node = lightMicroscopyStain_node.find_child(mdb_names.TOLUIDINE_BLUE)
                if toluidineBlue_node:
                    form.lightMicroscopyStainType.data = toluidineBlue_node.name
                vanGieson_node = lightMicroscopyStain_node.find_child(mdb_names.VAN_GIESON)
                if vanGieson_node:
                    form.lightMicroscopyStainType.data = vanGieson_node.name
                lightMicroscopyStainOther_node = lightMicroscopyStain_node.find_child(mdb_names.STRING_OTHER)
                if lightMicroscopyStainOther_node:
                    form.lightMicroscopyStainType.data = lightMicroscopyStainOther_node.name
                    form.lightMicroscopyStainOther.data = lightMicroscopyStainOther_node.content

            fluorescentMicroscopyStain_node = stain_node.find_child(mdb_names.FLU_MICRO_STAIN)
            if fluorescentMicroscopyStain_node:
                form.stain.data = fluorescentMicroscopyStain_node.name
                acridineOrange_node = fluorescentMicroscopyStain_node.find_child(mdb_names.ACRIDINE_ORANGE)
                if acridineOrange_node:
                    form.fluorescentMicroscopyStainType.data = acridineOrange_node.name
                calcein_node = fluorescentMicroscopyStain_node.find_child(mdb_names.CALCEIN)
                if calcein_node:
                    form.fluorescentMicroscopyStainType.data = calcein_node.name
                DAPI_node = fluorescentMicroscopyStain_node.find_child(mdb_names.DAPI)
                if DAPI_node:
                    form.fluorescentMicroscopyStainType.data = DAPI_node.name
                hoechst_node = fluorescentMicroscopyStain_node.find_child(mdb_names.HOECHST)
                if hoechst_node:
                    form.fluorescentMicroscopyStainType.data = hoechst_node.name
                propidiumIodide_node = fluorescentMicroscopyStain_node.find_child(mdb_names.PROP_IODIDE)
                if propidiumIodide_node:
                    form.fluorescentMicroscopyStainType.data = propidiumIodide_node.name
                rhodamine_node = fluorescentMicroscopyStain_node.find_child(mdb_names.RHODAMINE)
                if rhodamine_node:
                    form.fluorescentMicroscopyStainType.data = rhodamine_node.name
                TUNEL_node = fluorescentMicroscopyStain_node.find_child(mdb_names.TUNEL)
                if TUNEL_node:
                    form.fluorescentMicroscopyStainType.data = TUNEL_node.name
                fluorescentMicroscopyStainOther_node = fluorescentMicroscopyStain_node.find_child(mdb_names.STRING_OTHER)
                if fluorescentMicroscopyStainOther_node:
                    form.fluorescentMicroscopyStainType.data = fluorescentMicroscopyStainOther_node.name
                    form.fluorescentMicroscopyStainOther.data = fluorescentMicroscopyStainOther_node.content

            electronMicroscopyStain_node = stain_node.find_child(mdb_names.ELE_MICRO_STAIN)
            if electronMicroscopyStain_node:
                form.stain.data = electronMicroscopyStain_node.name
                colloidalgold_node = electronMicroscopyStain_node.find_child(mdb_names.COLLOIDAL_GOLD)
                if colloidalgold_node:
                    form.electronMicroscopyStainType.data = colloidalgold_node.name
                osmiumTetroxide_node = electronMicroscopyStain_node.find_child(mdb_names.OSMIUM_TETRO)
                if osmiumTetroxide_node:
                    form.electronMicroscopyStainType.data = osmiumTetroxide_node.name
                phosphotundsticAcid_node = electronMicroscopyStain_node.find_child(mdb_names.PHOS_ACID)
                if phosphotundsticAcid_node:
                    form.electronMicroscopyStainType.data = phosphotundsticAcid_node.name
                silverNitrate_node = electronMicroscopyStain_node.find_child(mdb_names.SILVER_NITRATE)
                if silverNitrate_node:
                    form.electronMicroscopyStainType.data = silverNitrate_node.name
                electronMicroscopyStainOther_node = electronMicroscopyStain_node.find_child(mdb_names.STRING_OTHER)
                if electronMicroscopyStainOther_node:
                    form.electronMicroscopyStainType.data = electronMicroscopyStainOther_node.name
                    form.electronMicroscopyStainOther.data = electronMicroscopyStainOther_node.content

    magnification_node = node.find_child(mdb_names.MAGNIFICATION)
    if magnification_node:
        form.magnification.data = magnification_node.attributes.get("value", None)
        if not form.magnification.data:
            form.magnification.data = magnification_node.content

    microscopeType_node = node.find_child(mdb_names.MICROSCOPE)
    if microscopeType_node:
        maker_node = microscopeType_node.find_child(mdb_names.MICRO_MAKER)
        if maker_node:
            form.maker.data = maker_node.content

        model_node = microscopeType_node.find_child(mdb_names.MICRO_MODEL)
        if model_node:
            form.model.data = model_node.content

        notes_node = microscopeType_node.find_child(mdb_names.MICRO_NOTES)
        if notes_node:
            form.notes.data = notes_node.content

    form.md5.data = form_md5(form)


"""
    Function:       create_specimen_location
    Params:         mother_node   : parent node 
                    specimenLocation : form value of specimenLocation
                    corpusLuteum  : form value of corpusLuteum, or None if empty
    Description:    Remove all existing children to avoid multiple child nodes.
                    Create a child node based on the selection of specimenLocation.
                    If the value of specimenLocation is corpusLuteum, then create a 
                    child Node of corpusLuteum including content value of the corpusLuteum
                    form field.
"""


def create_specimen_location(mother_node:Node, specimenLocation, corpusLuteum=None):
    specimenLocation_node = mother_node.find_child(mdb_names.SPEC_LOCATION)
    specimenLocation_node.remove_children()
    if specimenLocation == mdb_names.WHOLE_OVARY:
        wholeOvary_node = Node(mdb_names.WHOLE_OVARY, parent=specimenLocation_node)
        specimenLocation_node.add_child(wholeOvary_node)
    
    elif specimenLocation == mdb_names.OVARIAN_CORTEX:
        ovarianCortex_node = Node(mdb_names.OVARIAN_CORTEX, parent=specimenLocation_node)
        specimenLocation_node.add_child(ovarianCortex_node)
    
    elif specimenLocation == mdb_names.OVARIAN_MEDULLA:
        ovarianMedulla_node = Node(mdb_names.OVARIAN_MEDULLA, parent=specimenLocation_node)
        specimenLocation_node.add_child(ovarianMedulla_node)
    
    elif specimenLocation == mdb_names.FOLLICLE:
        follicle_node = Node(mdb_names.FOLLICLE, parent=specimenLocation_node)
        specimenLocation_node.add_child(follicle_node)
    
    elif specimenLocation == mdb_names.EMPTY_UNSPECIFIED:
        unspecified_node = Node(mdb_names.EMPTY_UNSPECIFIED, parent=specimenLocation_node)
        specimenLocation_node.add_child(unspecified_node)

    else:
        corpusLuteum_node = Node(mdb_names.CORPUS_LUTEUM, parent=specimenLocation_node)
        specimenLocation_node.add_child(corpusLuteum_node)
        corpusLuteum_node.content = corpusLuteum


"""
    Function:       create_stage_of_cycle
    Params:         mother_node   : parent node
                    stageOfCycle  : node to add children to
                    follicular    : form value of follicular, or None if empty
                    luteul        : form value of luteul, or None if empty
    Description:    Remove all existing children to avoid multiple child nodes.
                    Create a child node based on the selection of stageOfCycle.
                    If the value of stageOfCycle is follicular or luteul, then create a 
                    child Node of that type including its content value from the form field.
"""


def create_stage_of_cycle(mother_node: Node, stageOfCycle: None, follicular: None, luteal: None):
    cycleType_node = mother_node.find_child(mdb_names.SPEC_CYCLE)
    stageOfCycle_node = cycleType_node.find_child(mdb_names.STAGE_OF_CYCLE)
    stageOfCycle_node.remove_children()
    
    if stageOfCycle == mdb_names.FOLLICULAR:
        follicular_node = Node(mdb_names.FOLLICULAR, parent=stageOfCycle_node)
        stageOfCycle_node.add_child(follicular_node)
        follicular_node.content = follicular

    elif stageOfCycle == mdb_names.PRE_OVULATORY:
        pre_ovulatory_node = Node(mdb_names.PRE_OVULATORY, parent=stageOfCycle_node)
        stageOfCycle_node.add_child(pre_ovulatory_node)

    elif stageOfCycle == mdb_names.OVULATION:
        ovulation_node = Node(mdb_names.OVULATION, parent=stageOfCycle_node)
        stageOfCycle_node.add_child(ovulation_node)

    elif stageOfCycle == mdb_names.LUTEAL:
        luteal_node = Node(mdb_names.LUTEAL, parent=stageOfCycle_node)
        stageOfCycle_node.add_child(luteal_node)
        luteal_node.content = luteal

    elif stageOfCycle == mdb_names.EMPTY_UNSPECIFIED:
            unspecified_node = Node(mdb_names.EMPTY_UNSPECIFIED, parent=stageOfCycle_node)
            stageOfCycle_node.add_child(unspecified_node)

    elif stageOfCycle == mdb_names.PROESTRUS:
        proestrus_node = Node(mdb_names.PROESTRUS, parent=stageOfCycle_node)
        stageOfCycle_node.add_child(proestrus_node)
    elif stageOfCycle == mdb_names.ESTRUS:
        estrus_node = Node(mdb_names.ESTRUS, parent=stageOfCycle_node)
        stageOfCycle_node.add_child(estrus_node)
    elif stageOfCycle == mdb_names.METESTRUS:
        metestrus_node = Node(mdb_names.METESTRUS, parent=stageOfCycle_node)
        stageOfCycle_node.add_child(metestrus_node)
    elif stageOfCycle == mdb_names.DIESTRUS:
        diestrus_node = Node(mdb_names.DIESTRUS, parent=stageOfCycle_node)
        stageOfCycle_node.add_child(diestrus_node)
    elif stageOfCycle == mdb_names.ANESTRUS:
        anestrus_node = Node(mdb_names.ANESTRUS, parent=stageOfCycle_node)
        stageOfCycle_node.add_child(anestrus_node)


"""
    Function:       create_fixation
    Params:         mother_node     : parent node
                    fixation        : node to add children to
                    fixationOther   : form value of fixationOther
    Description:    Remove all existing children to avoid multiple child nodes.
                    Create a child node based on the selection of fixation.
                    If the value of fixation is other, then create a 
                    child Node of that type including its content value from the form field.
"""


def create_fixation(mother_node: Node, fixation, fixationOther):
    sampleProcessing_node = mother_node.find_child(mdb_names.SAMPLE_PROCESS)
    fixation_node = sampleProcessing_node.find_child(mdb_names.FIXATION)
    fixation_node.remove_children()

    if  fixation == mdb_names.NEUTRAL_BUFFERED_FORMALIN10:
        neutralBufferedFormalin10_node = Node(mdb_names.NEUTRAL_BUFFERED_FORMALIN10, parent=fixation_node)
        fixation_node.add_child(neutralBufferedFormalin10_node)

    elif  fixation == mdb_names.PARA_FORMALDEHYDE:
        paraformaldehyde4_node = Node(mdb_names.PARA_FORMALDEHYDE, parent=fixation_node)
        fixation_node.add_child(paraformaldehyde4_node)

    elif  fixation == mdb_names.DAVIDSONS:
        davidsons_node = Node(mdb_names.DAVIDSONS, parent=fixation_node)
        fixation_node.add_child(davidsons_node)

    elif  fixation == mdb_names.NEUTRAL_BUFFERED_FORMALIN5:
        neutralBufferedFormalin5aceticAcid_node = Node(mdb_names.NEUTRAL_BUFFERED_FORMALIN5, parent=fixation_node)
        fixation_node.add_child(neutralBufferedFormalin5aceticAcid_node)

    elif  fixation == mdb_names.BOUINS:
        bouins_node = Node(mdb_names.BOUINS, parent=fixation_node)
        fixation_node.add_child(bouins_node)

    elif  fixation == mdb_names.STRING_OTHER:
        fixationOther_node = Node(mdb_names.STRING_OTHER, parent=fixation_node)
        fixation_node.add_child(fixationOther_node)
        fixationOther_node.content = fixationOther


"""
    Function:       create_stain
    Params:         mother_node                     : parent node
                    stain                           : form value of stain
                    lightMicroscopyStainType        : form value of lightMicroscopyStainType
                    sudanStainType                  : form value of sudanStainType
                    lightMicroscopyStainOther       : form value of lightMicroscopyStainOther
                    fluorescentMicroscopyStainType  : form value of fluorescentMicroscopyStainType
                    fluorescentMicroscopyStainOther : form value of fluorescentMicroscopyStainOther
                    electronMicroscopyStainType     : form value of electronMicroscopyStainType
                    electronMicroscopyStainOther    : form value of electronMicroscopyStainOther
    Description:    Remove all existing children to avoid multiple child nodes.
                    Create a child node based on the selection of stain.
                    If the value of stain is "sudan" within "lightmicroscopystain", then create a 
                    child Node of that type including its content value from the form field.
                    
"""


def create_stain(mother_node: Node, stain, 
                lightMicroscopyStainType, sudanStainType, lightMicroscopyStainOther, 
                fluorescentMicroscopyStainType, fluorescentMicroscopyStainOther, 
                electronMicroscopyStainType, electronMicroscopyStainOther):

    sampleProcessing_node = mother_node.find_child(mdb_names.SAMPLE_PROCESS)
    stain_node = sampleProcessing_node.find_child(mdb_names.STAIN)
    stain_node.remove_children()

    if stain == mdb_names.LIGHT_MICRO_STAIN:
        lightMicroscopyStainType_node = Node(mdb_names.LIGHT_MICRO_STAIN, parent=stain_node)
        stain_node.add_child(lightMicroscopyStainType_node)
        if lightMicroscopyStainType == mdb_names.EOSIN_ONLY:
            eosinOnly_node = Node(mdb_names.EOSIN_ONLY, parent=lightMicroscopyStainType_node)
            lightMicroscopyStainType_node.add_child(eosinOnly_node)

        elif lightMicroscopyStainType == mdb_names.HEMA_ONLY:
            hematoxylinOnly_node = Node(mdb_names.HEMA_ONLY, parent=lightMicroscopyStainType_node)
            lightMicroscopyStainType_node.add_child(hematoxylinOnly_node)

        elif lightMicroscopyStainType == mdb_names.HEMA_EOSIN:
            hematoxylinAndEosin_node = Node(mdb_names.HEMA_EOSIN, parent=lightMicroscopyStainType_node)
            lightMicroscopyStainType_node.add_child(hematoxylinAndEosin_node)

        elif lightMicroscopyStainType == mdb_names.MASONS_TRI:
            masonsTrichrome_node = Node(mdb_names.MASONS_TRI, parent=lightMicroscopyStainType_node)
            lightMicroscopyStainType_node.add_child(masonsTrichrome_node)

        elif lightMicroscopyStainType == mdb_names.MALLORYS_TRI:
            mallorysTrichrome_node = Node(mdb_names.MALLORYS_TRI, parent=lightMicroscopyStainType_node)
            lightMicroscopyStainType_node.add_child(mallorysTrichrome_node)

        elif lightMicroscopyStainType == mdb_names.PERIODIC_ACID_SCHIFF:
            periodicAcidSchiff_node = Node(mdb_names.PERIODIC_ACID_SCHIFF, parent=lightMicroscopyStainType_node)
            lightMicroscopyStainType_node.add_child(periodicAcidSchiff_node)

        elif lightMicroscopyStainType == mdb_names.SUDAN:
            sudan_node = Node(mdb_names.SUDAN, parent=lightMicroscopyStainType_node)
            lightMicroscopyStainType_node.add_child(sudan_node)
            if sudanStainType == mdb_names.III:
                sudan_node.content = mdb_names.III
            elif sudanStainType == mdb_names.IV:
                sudan_node.content = mdb_names.IV
            elif sudanStainType == mdb_names.BLACK_B:
                sudan_node.content = mdb_names.BLACK_B
            elif sudanStainType == mdb_names.OIL_RED_O:
                sudan_node.content = mdb_names.OIL_RED_O
            elif sudanStainType == mdb_names.OSMIUM_TETRAOXIDE:
                sudan_node.content = mdb_names.OSMIUM_TETRAOXIDE

        elif lightMicroscopyStainType == mdb_names.ACID_FUSCHIN:
            acidFuschin_node = Node(mdb_names.ACID_FUSCHIN, parent=lightMicroscopyStainType_node)
            lightMicroscopyStainType_node.add_child(acidFuschin_node)

        elif lightMicroscopyStainType == mdb_names.ALCIAN_BLUE:
            alcianBlue_node = Node(mdb_names.ALCIAN_BLUE, parent=lightMicroscopyStainType_node)
            lightMicroscopyStainType_node.add_child(alcianBlue_node)

        elif lightMicroscopyStainType == mdb_names.AZAN_TRI:
            azanTrichrome_node = Node(mdb_names.AZAN_TRI, parent=lightMicroscopyStainType_node)
            lightMicroscopyStainType_node.add_child(azanTrichrome_node)

        elif lightMicroscopyStainType == mdb_names.CASANS_TRI:
            casansTrichrome_node = Node(mdb_names.CASANS_TRI, parent=lightMicroscopyStainType_node)
            lightMicroscopyStainType_node.add_child(casansTrichrome_node)

        elif lightMicroscopyStainType == mdb_names.CRESYL_VIOLET_NISSL:
            cresylVioletNissl_node = Node(mdb_names.CRESYL_VIOLET_NISSL, parent=lightMicroscopyStainType_node)
            lightMicroscopyStainType_node.add_child(cresylVioletNissl_node)

        elif lightMicroscopyStainType == mdb_names.GIEMSA:
            giemsa_node = Node(mdb_names.GIEMSA, parent=lightMicroscopyStainType_node)
            lightMicroscopyStainType_node.add_child(giemsa_node)

        elif lightMicroscopyStainType == mdb_names.METHYLENE_BLUE:
            methyleneBlue_node = Node(mdb_names.METHYLENE_BLUE, parent=lightMicroscopyStainType_node)
            lightMicroscopyStainType_node.add_child(methyleneBlue_node)

        elif lightMicroscopyStainType == mdb_names.NEUTRAL_RED:
            neutralRed_node = Node(mdb_names.NEUTRAL_RED, parent=lightMicroscopyStainType_node)
            lightMicroscopyStainType_node.add_child(neutralRed_node)

        elif lightMicroscopyStainType == mdb_names.NILE_BLUE:
            nileBlue_node = Node(mdb_names.NILE_BLUE, parent=lightMicroscopyStainType_node)
            lightMicroscopyStainType_node.add_child(nileBlue_node)

        elif lightMicroscopyStainType == mdb_names.NILE_RED:
            nileRed_node = Node(mdb_names.NILE_RED, parent=lightMicroscopyStainType_node)
            lightMicroscopyStainType_node.add_child(nileRed_node)

        elif lightMicroscopyStainType == mdb_names.ORCEIN:
            orcein_node = Node(mdb_names.ORCEIN, parent=lightMicroscopyStainType_node)
            lightMicroscopyStainType_node.add_child(orcein_node)

        elif lightMicroscopyStainType == mdb_names.RETICULIN:
            reticulin_node = Node(mdb_names.RETICULIN, parent=lightMicroscopyStainType_node)
            lightMicroscopyStainType_node.add_child(reticulin_node)

        elif lightMicroscopyStainType == mdb_names.TOLUIDINE_BLUE:
            toluidineBlue_node = Node(mdb_names.TOLUIDINE_BLUE, parent=lightMicroscopyStainType_node)
            lightMicroscopyStainType_node.add_child(toluidineBlue_node)

        elif lightMicroscopyStainType == mdb_names.VAN_GIESON:
            vanGieson_node = Node(mdb_names.VAN_GIESON, parent=lightMicroscopyStainType_node)
            lightMicroscopyStainType_node.add_child(vanGieson_node)

        elif lightMicroscopyStainType == mdb_names.STRING_OTHER:
            lightMicroscopyStainOther_node = Node(mdb_names.STRING_OTHER, parent=lightMicroscopyStainType_node)
            lightMicroscopyStainType_node.add_child(lightMicroscopyStainOther_node)
            lightMicroscopyStainOther_node.content = lightMicroscopyStainOther

    elif stain == mdb_names.FLU_MICRO_STAIN:
        fluorescentMicroscopyStainType_node = Node(mdb_names.FLU_MICRO_STAIN, parent=stain_node)
        stain_node.add_child(fluorescentMicroscopyStainType_node)
        if fluorescentMicroscopyStainType == mdb_names.ACRIDINE_ORANGE:
            acridineOrange_node = Node(mdb_names.ACRIDINE_ORANGE, parent=fluorescentMicroscopyStainType_node)
            fluorescentMicroscopyStainType_node.add_child(acridineOrange_node)

        elif fluorescentMicroscopyStainType == mdb_names.CALCEIN:
            calcein_node = Node(mdb_names.CALCEIN, parent=fluorescentMicroscopyStainType_node)
            fluorescentMicroscopyStainType_node.add_child(calcein_node)

        elif fluorescentMicroscopyStainType == mdb_names.DAPI:
            DAPI_node = Node(mdb_names.DAPI, parent=fluorescentMicroscopyStainType_node)
            fluorescentMicroscopyStainType_node.add_child(DAPI_node)

        elif fluorescentMicroscopyStainType == mdb_names.HOECHST:
            hoechst_node = Node(mdb_names.HOECHST, parent=fluorescentMicroscopyStainType_node)
            fluorescentMicroscopyStainType_node.add_child(hoechst_node)

        elif fluorescentMicroscopyStainType == mdb_names.PROP_IODIDE:
            propidiumIodide_node = Node(mdb_names.PROP_IODIDE, parent=fluorescentMicroscopyStainType_node)
            fluorescentMicroscopyStainType_node.add_child(propidiumIodide_node)

        elif fluorescentMicroscopyStainType == mdb_names.RHODAMINE:
            rhodamine_node = Node(mdb_names.RHODAMINE, parent=fluorescentMicroscopyStainType_node)
            fluorescentMicroscopyStainType_node.add_child(rhodamine_node)

        elif fluorescentMicroscopyStainType == mdb_names.TUNEL:
            TUNEL_node = Node(mdb_names.TUNEL, parent=fluorescentMicroscopyStainType_node)
            fluorescentMicroscopyStainType_node.add_child(TUNEL_node)

        elif fluorescentMicroscopyStainType == mdb_names.STRING_OTHER:
            fluorescentMicroscopyStainOther_node = Node(mdb_names.STRING_OTHER, parent=fluorescentMicroscopyStainType_node)
            fluorescentMicroscopyStainType_node.add_child(fluorescentMicroscopyStainOther_node)
            fluorescentMicroscopyStainOther_node.content = fluorescentMicroscopyStainOther

    elif stain == mdb_names.ELE_MICRO_STAIN:
        electronMicroscopyStainType_node = Node(mdb_names.ELE_MICRO_STAIN, parent=stain_node)
        stain_node.add_child(electronMicroscopyStainType_node)
        if electronMicroscopyStainType == mdb_names.COLLOIDAL_GOLD:
            colloidalGold_node = Node(mdb_names.COLLOIDAL_GOLD, parent=electronMicroscopyStainType_node)
            electronMicroscopyStainType_node.add_child(colloidalGold_node)

        elif electronMicroscopyStainType == mdb_names.OSMIUM_TETRO:
            osmiumTetroxide_node = Node(mdb_names.OSMIUM_TETRO, parent=electronMicroscopyStainType_node)
            electronMicroscopyStainType_node.add_child(osmiumTetroxide_node)

        elif electronMicroscopyStainType == mdb_names.PHOS_ACID:
            phosphotundsticAcid_node = Node(mdb_names.PHOS_ACID, parent=electronMicroscopyStainType_node)
            electronMicroscopyStainType_node.add_child(phosphotundsticAcid_node)

        elif electronMicroscopyStainType == mdb_names.SILVER_NITRATE:
            silverNitrate_node = Node(mdb_names.SILVER_NITRATE, parent=electronMicroscopyStainType_node)
            electronMicroscopyStainType_node.add_child(silverNitrate_node)

        elif electronMicroscopyStainType == mdb_names.STRING_OTHER:
            electronMicroscopyStainOther_node = Node(mdb_names.STRING_OTHER, parent=electronMicroscopyStainType_node)
            electronMicroscopyStainType_node.add_child(electronMicroscopyStainOther_node)
            electronMicroscopyStainOther_node.content = electronMicroscopyStainOther

