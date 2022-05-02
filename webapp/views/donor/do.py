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
    load_eml, save_both_formats, create_donor, add_mother_metadata
)

from metapype.eml import names
from metapype.model.node import Node

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

@do_bp.route('/donor/<filename>', methods=['GET', 'POST'])
def donor(filename=None):
    method = request.method
    node_id = '1'

    if filename:
        eml_node = load_eml(filename=filename)
        additional_metadata_node = eml_node.find_child(names.ADDITIONALMETADATA)
        if additional_metadata_node:
            metadata_node = additional_metadata_node.find_child(names.METADATA)
            mother_node = metadata_node.find_child("mother")
            if mother_node:
                do_node = mother_node.find_child("donor")
                if do_node:
                    node_id = do_node.id
        else:
            add_mother_metadata(eml_node)
    
    save_both_formats(filename, eml_node)
    set_current_page('donor')
    help = [get_help('publisher')]
    return newDonor(filename=filename, node_id=node_id,
                             method=method, node_name='donor',
                             back_page=PAGE_DONOR, next_page= PAGE_DONOR, title='Donor',
                             save_and_continue=True, help=help)

def newDonor(filename=None, node_id=None, method=None,
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
    donor_node = mother_node.find_child(node_name)
    if not donor_node:
        mother_node.add_child(Node(node_name, parent = mother_node))
        donor_node = mother_node.find_child(node_name)

    new_page = select_new_page(back_page, next_page)

    # Process POST
    save = False
    if is_dirty_form(form):
        save = True
    
    if form.validate_on_submit() and method == 'POST':
        if save:
            donorId = form.donorId.data
            donorGender = form.donorGender.data
            ageType = Node('ageType', parent=None)
            ageYears = form.ageYears.data
            ageDays = form.ageDays.data
            lifeStage = form.lifeStage.data
            specimenSeqNum = form.specimenSeqNum.data
            specimenTissue = form.specimenTissue.data
            ovaryPosition = form.ovaryPosition.data
            specimenLocation = form.specimenLocation.data
            corpusLuteumType = form.corpusLuteumType.data
            cycleType = Node('cycleType', parent = None)
            dayOfCycle = form.dayOfCycle.data
            stageOfCycle = form.stageOfCycle.data
            follicularType = form.follicularType.data
            lutealType = form.lutealType.data
            slideID = form.slideID.data
            sectionSeqNum = form.sectionSeqNum.data
            sectionThicknessType = Node('sectionThicknessType', parent = None)
            sectionThickness = form.sectionThickness.data
            sectionThicknessUnit = form.sectionThicknessUnit.data
            sampleProcessingType = Node('sampleProcessingType', parent = None)
            fixation = form.fixation.data
            fixationOther = form.fixationOther.data
            stain = form.stain.data
            stainType = Node('stainType', parent = None)
            stainLightType = form.stainLightType.data
            sudanStainType = form.sudanStainType.data
            stainLightOther = form.stainLightOther.data
            stainFluorescentType = form.stainFluorescentType.data
            stainFluorescentOther = form.stainFluorescentOther.data
            stainElectronType = form.stainElectronType.data
            stainElectronOther = form.stainElectronOther.data
            magnification = form.magnification.data
            microscopeType = Node('microscopeType', parent = None)
            maker = form.maker.data
            model = form.model.data
            notes = form.notes.data

            create_donor(
                donor_node,
                filename,
                donorId,
                donorGender,
                ageType,
                ageYears,
                ageDays,
                lifeStage,
                specimenSeqNum,
                specimenTissue,
                ovaryPosition,
                specimenLocation,
                corpusLuteumType,
                cycleType,
                dayOfCycle,
                stageOfCycle,
                follicularType,
                lutealType,
                slideID,
                sectionSeqNum,
                sectionThicknessType,
                sectionThickness,
                sectionThicknessUnit,
                sampleProcessingType,
                fixation,
                fixationOther,
                stain,
                stainType,
                stainLightType,
                sudanStainType,
                stainLightOther,
                stainFluorescentType,
                stainFluorescentOther,
                stainElectronType,
                stainElectronOther,
                magnification,
                microscopeType,
                maker,
                model,
                notes)

            print("Test=", donor_node)

            save_both_formats(filename=filename, eml_node=eml_node)
        return redirect(url_for(new_page, filename = filename))

    # Process GET
    if node_id == '1':
        print('get request NODE_ID = 1')
        form.init_md5()
    elif node_id:
        related_project_node = Node.get_node_instance(node_id)
        populate_donor_form(form, related_project_node)
    return render_template('donor.html', title=title, node_name=node_name, form=form,
                            next_page=next_page, save_and_continue=save_and_continue, help=help)

def populate_donor_form(form: DonorForm, node: Node):
    donorId_node = node.find_child('donorId')
    if donorId_node:
        form.donorId.data = donorId_node.content
    
    donorGender_node = node.find_child('donorGender')
    if donorGender_node:
        form.donorGender.data = donorGender_node.content
    
    ageType_node = node.find_child('ageType')
    if ageType_node:
        ageYears_node = ageType_node.find_child('ageYears')
        if ageYears_node:
            form.ageYears.data = ageYears_node.content

        ageDays_node = ageType_node.find_child('ageDays')
        if ageDays_node:
            form.ageDays.data = ageDays_node.content

    lifeStage_node = node.find_child('lifeStage')
    if lifeStage_node:
        form.lifeStage.data = lifeStage_node.content

    specimenSeqNum_node = node.find_child('specimenSeqNum')
    if specimenSeqNum_node:
        form.specimenSeqNum.data = specimenSeqNum_node.content

    specimenTissue_node = node.find_child('specimenTissue')
    if specimenTissue_node:
        form.specimenTissue.data = specimenTissue_node.content

    ovaryPosition_node = node.find_child('ovaryPosition')
    if ovaryPosition_node:
        form.ovaryPosition.data = ovaryPosition_node.content

    specimenLocation_node = node.find_child('specimenLocation')
    if specimenLocation_node:
        form.specimenLocation.data = specimenLocation_node.content

    corpusLuteumType_node = node.find_child('corpusLuteumType')
    if corpusLuteumType_node:
        form.corpusLuteumType.data = corpusLuteumType_node.content

    cycleType_node = node.find_child('cycleType')
    if cycleType_node: 
        dayOfCycle_node = cycleType_node.find_child('dayOfCycle')
        if dayOfCycle_node:
            form.dayOfCycle.data = dayOfCycle_node.content
        
        stageOfCycle_node = cycleType_node.find_child('stageOfCycle')
        if stageOfCycle_node:
            form.stageOfCycle.data = stageOfCycle_node.content
    
    follicularType_node = node.find_child('follicularType')
    if follicularType_node:
        form.follicularType.data = follicularType_node.content
    
    lutealType_node = node.find_child('lutealType')
    if lutealType_node:
        form.lutealType.data = lutealType_node.content

    slideID_node = node.find_child('slideID')
    if slideID_node:
        form.slideID.data = slideID_node.content

    sectionSeqNum_node = node.find_child('sectionSeqNum')
    if sectionSeqNum_node:
        form.sectionSeqNum.data = sectionSeqNum_node.content
    
    sectionThicknessType_node = node.find_child('sectionThicknessType')
    if sectionThicknessType_node:
        sectionThickness_node = sectionThicknessType_node.find_child('sectionThickness')
        if sectionThickness_node:
            form.sectionThickness.data = sectionThickness_node.content
        
        sectionThicknessUnit_node = sectionThicknessType_node.find_child('sectionThicknessUnit')
        if sectionThicknessUnit_node:
            form.sectionThicknessUnit.data = sectionThicknessUnit_node.content
    
    sampleProcessingType_node = node.find_child('sampleProcessingType')
    if sampleProcessingType_node:
        fixation_node = sampleProcessingType_node.find_child('fixation')
        if fixation_node:
            form.fixation.data = fixation_node.content

            fixationOther_node = fixation_node.find_child('fixationOther')
            if fixationOther_node:
                form.fixationOther.data = fixationOther_node.content
        
        stain_node = sampleProcessingType_node .find_child('stain')
        if stain_node:
            form.stain.data = stain_node.content

    stainType_node = node.find_child('stainType')
    if stainType_node:
        stainLightType_node = stainType_node.find_child('stainLightType')
        if stainLightType_node:
            form.stainLightType.data = stainLightType_node.content

            sudanStainType_node = stainLightType_node.find_child('sudanStainType')
            if sudanStainType_node:
                form.sudanStainType.data = sudanStainType_node.content

            stainLightOther_node = stainLightType_node.find_child('stainLightOther')
            if stainLightOther_node:
                form.stainLightOther.data = stainLightOther_node.content
        
        stainFluorescentType_node = stainType_node.find_child('stainFluorescentType')
        if stainFluorescentType_node:
            form.stainFluorescentType.data = stainFluorescentType_node.content

            stainFluorescentOther_node = stainFluorescentType_node.find_child('stainFluorescentOther')
            if stainFluorescentOther_node:
                form.stainFluorescentOther.data = stainFluorescentOther_node.content

        stainElectronType_node = stainType_node.find_child('stainElectronType')
        if stainElectronType_node:
            form.stainElectronType.data = stainElectronType_node.content

            stainElectronOther_node = stainElectronType_node.find_child('stainElectronOther')
            if stainElectronOther_node:
                form.stainElectronOther.data = stainElectronOther_node.content
    
    magnification_node = node.find_child('magnification')
    if magnification_node:
        form.magnification.data = magnification_node.content

    microscopeType_node = node.find_child('microscopeType')
    if microscopeType_node:
        maker_node = microscopeType_node.find_child('maker')
        if maker_node:
            form.maker.data = maker_node.content

        model_node = microscopeType_node.find_child('model')
        if model_node:
            form.model.data = model_node.content

        notes_node = microscopeType_node.find_child('notes')
        if notes_node:
            form.notes.data = notes_node.content

    form.md5.data = form_md5(form)
