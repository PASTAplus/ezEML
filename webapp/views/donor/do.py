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
#            mother_node = metadata_node.find_child("mdb:mother")  #PT5/27
            if mother_node:
                node_id = mother_node.id
                # do_node = mother_node.find_child("donor")
                # if do_node:
                #    node_id = do_node.id
        else:
            add_mother_metadata(eml_node)

    save_both_formats(filename, eml_node)

    set_current_page('donor')
    help = [get_help('publisher')]
    return newDonor(filename=filename, node_id=node_id,
                             method=method, node_name='donor',
                            back_page=PAGE_RELATED_PROJECT_SELECT, next_page=PAGE_IHC, title='Donor',
#PT5/26                             back_page=PAGE_DONOR, next_page= PAGE_DONOR, title='Donor',
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
#    mother_node = metadata_node.find_child("mdb:mother")  # PT5/27
#    donor_node = mother_node.find_child(node_name)
#    if not donor_node:
#        mother_node.add_child(Node(node_name, parent = mother_node))
#        donor_node = mother_node.find_child(node_name)



    new_page = select_new_page(back_page, next_page)

    # Process POST
    save = False
    if is_dirty_form(form):
        save = True
    
    if form.validate_on_submit() and method == 'POST':
        if save:
            donorID = form.donorID.data
            donorGender = form.donorGender.data
            donorAge = Node('donorAge', parent=None)
            donorYears = form.donorYears.data
            donorDays = form.donorDays.data
            donorLifeStage = form.donorLifeStage.data
            specimenSeqNum = form.specimenSeqNum.data
            specimenTissue = form.specimenTissue.data
            ovaryPosition = form.ovaryPosition.data
            specimenLocation = form.specimenLocation.data
            corpusLuteum = form.corpusLuteum.data
            specimenCycle = Node('specimenCycle', parent = None)
            dayOfCycle = form.dayOfCycle.data
            stageOfCycle = form.stageOfCycle.data
            follicular = form.follicular.data
            luteal = form.luteal.data
            slideID = form.slideID.data
            sectionSeqNum = form.sectionSeqNum.data
            sectionThickness = Node('thickness', parent = None)
            thickness = form.thickness.data
            thicknessUnit = form.thicknessUnit.data
            sampleProcessing = Node('sampleProcessing', parent = None)
            fixation = form.fixation.data
            fixationOther = form.fixationOther.data
            stain = form.stain.data
            stainType = Node('stainType', parent = None)
            lightMicroscopyStainType = form.lightMicroscopyStainType.data
            sudanStainType = form.sudanStainType.data
            lightMicroscopyStainOther = form.lightMicroscopyStainOther.data
            fluorescentMicroscopyStainType = form.fluorescentMicroscopyStainType.data
            fluorescentMicroscopyStainOther = form.fluorescentMicroscopyStainOther.data
            electronMicroscopyStainType = form.electronMicroscopyStainType.data
            electronMicroscopyStainOther = form.electronMicroscopyStainOther.data
            magnification = form.magnification.data
            microscopeType = Node('microscope', parent = None)
            maker = form.maker.data
            model = form.model.data
            notes = form.notes.data

            create_donor(
                mother_node,
                filename,
                donorID,
                donorGender,
                donorAge,
                donorYears,
                donorDays,
                donorLifeStage,
                specimenSeqNum,
                specimenTissue,
                ovaryPosition,
                specimenLocation,
                corpusLuteum,
                specimenCycle,
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

            if specimenLocation == 'corpusLuteum':
                populate_specimen_location(mother_node, corpusLuteum)

            if stageOfCycle == 'follicular':
                populate_stage_of_cycle(stageOfCycle, mother_node, follicular)
            elif stageOfCycle == 'luteal':
                populate_stage_of_cycle(stageOfCycle, mother_node, luteal)


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
    donorID_node = node.find_child('donorID')
    if donorID_node:
        form.donorID.data = donorID_node.content
    
    donorGender_node = node.find_child('donorGender')
    if donorGender_node:
        form.donorGender.data = donorGender_node.content
    
    donorAge_Node = node.find_child('donorAge')
    if donorAge_Node:
        donorYears_node = donorAge_Node.find_child('donorYears')
        if donorYears_node:
            form.donorYears.data = donorYears_node.content

        donorDays_node = donorAge_Node.find_child('donorDays')
        if donorDays_node:
            form.donorDays.data = donorDays_node.content

    donorLifeStage_node = node.find_child('donorLifeStage')
    if donorLifeStage_node:
        form.donorLifeStage.data = donorLifeStage_node.content

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
        corpusLuteum_node = specimenLocation_node.find_child('corpusLuteum')
        if corpusLuteum_node:
            form.corpusLuteum.data = corpusLuteum_node.content

    specimenCycle_node = node.find_child('specimenCycle')
    if specimenCycle_node: 
        dayOfCycle_node = specimenCycle_node.find_child('dayOfCycle')
        if dayOfCycle_node:
            form.dayOfCycle.data = dayOfCycle_node.content
        
        stageOfCycle_node = specimenCycle_node.find_child('stageOfCycle')
        if stageOfCycle_node:
            form.stageOfCycle.data = stageOfCycle_node.content
            follicular_node = stageOfCycle_node.find_child('follicular')
            if follicular_node:
                form.stageOfCycle.data = 'follicular'
                form.follicular.data = follicular_node.content
            luteal_node = stageOfCycle_node.find_child('luteal')
            if luteal_node:
                form.stageOfCycle.data = 'luteal'
                form.luteal.data = luteal_node.content

    slideID_node = node.find_child('slideID')
    if slideID_node:
        form.slideID.data = slideID_node.content

    sectionSeqNum_node = node.find_child('sectionSeqNum')
    if sectionSeqNum_node:
        form.sectionSeqNum.data = sectionSeqNum_node.content
    
    sectionThickness_node = node.find_child('sectionThickness')
    if sectionThickness_node:
        thickness_node = sectionThickness_node.find_child('thickness')
        if thickness_node:
            form.thickness.data = thickness_node.content
        
        thicknessUnit_node = sectionThickness_node.find_child('thicknessUnit')
        if thicknessUnit_node:
            form.thicknessUnit.data = thicknessUnit_node.content
    
    sampleProcessing_node = node.find_child('sampleProcessing')
    if sampleProcessing_node:
        fixation_node = sampleProcessing_node.find_child('fixation')
        if fixation_node:
            form.fixation.data = fixation_node.content

        fixationOther_node = sampleProcessing_node.find_child('fixationOther')
        if fixationOther_node:
            form.fixationOther.data = fixationOther_node.content
        
        stain_node = sampleProcessing_node .find_child('stain')
        if stain_node:
            form.stain.data = stain_node.content

    stainType_node = node.find_child('stainType')
    if stainType_node:
        lightMicroscopyStainType_node = stainType_node.find_child('lightMicroscopyStainType')
        if lightMicroscopyStainType_node:
            form.lightMicroscopyStainType.data = lightMicroscopyStainType_node.content

        sudanStainType_node = stainType_node.find_child('sudanStainType')
        if sudanStainType_node:
            form.sudanStainType.data = sudanStainType_node.content

        lightMicroscopyStainOther_node = stainType_node.find_child('lightMicroscopyStainOther')
        if lightMicroscopyStainOther_node:
            form.lightMicroscopyStainOther.data = lightMicroscopyStainOther_node.content
        
        fluorescentMicroscopyStainType_node = stainType_node.find_child('fluorescentMicroscopyStainType')
        if fluorescentMicroscopyStainType_node:
            form.fluorescentMicroscopyStainType.data = fluorescentMicroscopyStainType_node.content

        fluorescentMicroscopyStainOther_node = stainType_node.find_child('fluorescentMicroscopyStainOther')
        if fluorescentMicroscopyStainOther_node:
            form.fluorescentMicroscopyStainOther.data = fluorescentMicroscopyStainOther_node.content

        electronMicroscopyStainType_node = stainType_node.find_child('electronMicroscopyStainType')
        if electronMicroscopyStainType_node:
            form.electronMicroscopyStainType.data = electronMicroscopyStainType_node.content

        electronMicroscopyStainOther_node = stainType_node.find_child('electronMicroscopyStainOther')
        if electronMicroscopyStainOther_node:
            form.electronMicroscopyStainOther.data = electronMicroscopyStainOther_node.content
    
    magnification_node = node.find_child('magnification')
    if magnification_node:
        form.magnification.data = magnification_node.content

    microscopeType_node = node.find_child('microscope')
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

def populate_stage_of_cycle(stageOfCycle:None, mother_node:Node, content_value):
    cycleType_node = mother_node.find_child('specimenCycle')
    stageOfCycle_node = cycleType_node.find_child('stageOfCycle')
    if stageOfCycle == 'follicular':
        follicularType_node = stageOfCycle_node.find_child('follicularType')
        if not follicularType_node:
            follicularType_node = Node('follicularType', parent=stageOfCycle_node)
            stageOfCycle_node.add_child(follicularType_node)
        follicularType_node.content = content_value
    else:
        lutealType_node = stageOfCycle_node.find_child('lutealType')
        if not lutealType_node:
            lutealType_node = Node('lutealType', parent=stageOfCycle_node)
            stageOfCycle_node.add_child(lutealType_node)
        lutealType_node.content = content_value

def populate_specimen_location(mother_node:Node, content_value):
    specimenLocation_node = mother_node.find_child('specimenLocation')
    corpusLuteum_node = specimenLocation_node.find_child('corpusLuteumType')
    if not corpusLuteum_node:
        corpusLuteum_node = Node('corpusLuteumType', parent=specimenLocation_node)
        specimenLocation_node.add_child(corpusLuteum_node)
    corpusLuteum_node.content = content_value