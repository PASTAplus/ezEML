from flask import (
    Blueprint, flash, render_template, redirect, request, url_for
)

from webapp.views.donor.forms import (
    DonorForm
)

from webapp.home.forms import (
    form_md5, is_dirty_form
)

from webapp.home.metapype_client import (
    load_eml, save_both_formats,
    add_child, create_donor, add_mother_metadata
)

from metapype.eml import names
from metapype.model.node import Node

from webapp.buttons import *
from webapp.pages import *

from webapp.home.views import select_post, non_breaking, set_current_page, get_help, get_helps


do_bp = Blueprint('do', __name__, template_folder='templates')

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
                             back_page=PAGE_DONOR, title='Donor',
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
        donor_node = mother_node.find(node_name)

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
            dayOfCycle = form.dayOfCycle.data
            stageOfCycle = form.stageOfCycle.data
            follicularType = form.follicularType.data
            lutealType = form.lutealType.data
            slideID = form.slideID.data
            sectionSeqNum = form.sectionSeqNum.data
            sectionThickness = form.sectionThickness.data
            sectionThicknessUnit = form.sectionThicknessUnit.data
            fixation = form.fixation.data
            fixationOther = form.fixationOther.data
            stain = form.stain.data
            stainLightType = form.stainLightType.data
            sudanStainType = form.sudanStainType.data
            stainLightOther = form.stainLightOther.data
            stainFluorescentType = form.stainFluorescentType.data
            stainFluorescentOther = form.stainFluorescentOther.data
            stainElectronType = form.stainElectronType.data
            stainElectronOther = form.stainElectronOther.data
            magnification = form.magnification.data
            maker = form.maker.data
            model = form.model.data
            notes = form.notes.data

            #do_node = Node(node_name, parent=parent_node)

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
                dayOfCycle,
                stageOfCycle,
                follicularType,
                lutealType,
                slideID,
                sectionSeqNum,
                sectionThickness,
                sectionThicknessUnit,
                fixation,
                fixationOther,
                stain,
                stainLightType,
                sudanStainType,
                stainLightOther,
                stainFluorescentType,
                stainFluorescentOther,
                stainElectronType,
                stainElectronOther,
                magnification,
                maker,
                model,
                notes)

            print("Test=", donor_node)

            #if node_id and len(node_id) != 1:
            #    old_do_node = Node.get_node_instance(node_id)
            #    if old_do_node:
            #        old_do_parent_node = old_do_node.parent
            #        old_do_parent_node.replace_child(old_do_node, do_node)
            #    else:
            #        msg = f"No node found in the node store with node id {node_id}"
            #        raise Exception(msg)
            #else:
                #add_child(parent_node, do_node)
            #    parent_node.add_child(do_node)

            save_both_formats(filename=filename, eml_node=eml_node)
            new_page = 'do.donor'
            return redirect(url_for(new_page, filename = filename))
        #return redirect(url)

    # Process GET
    if node_id == '1':
        print('get request NODE_ID = 1')
        form.init_md5()
    elif node_id:
        #if parent_node:
        #    do_nodes = parent_node.find_all_children(child_name=node_name)
        #    if do_nodes:
        #        for do_node in do_nodes:
        #            if node_id == do_node.id:
        #                populate_donor_form(form, do_node)
        related_project_node = Node.get_node_instance(node_id)
        populate_donor_form(form, related_project_node)
    return render_template('donor.html', title=title, node_name=node_name, form=form,
                            next_page=next_page, save_and_continue=save_and_continue, help=help)

    # help = get_helps([node_name])
    # return render_template('donor.html', title=title, node_name=node_name, form=form,
    #                        next_page=next_page, save_and_continue=save_and_continue, help=help)

def populate_donor_form(form: DonorForm, node: Node):
    donorId_node = node.find_child('donorId')
    if donorId_node:
        form.donorId.data = donorId_node.content
    
    donorGender_node = node.find_child('donorGender')
    if donorGender_node:
        form.donorGender.data = donorGender_node.content
    
    age_node = node.find_child('ageType')
    if age_node:
        years_node = age_node.find_child('ageYears')
        if years_node:
            form.ageYears.data = years_node.content

        days_node = age_node.find_child('ageDays')
        if days_node:
            form.ageDays.data = days_node.content

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

    corpusluteumType_node = node.find_child('corpusluteumType')
    if corpusluteumType_node:
        form.corpusluteumType.data = corpusluteumType_node.content
        
    dayOfCycle_node = node.find_child('dayOfCycle')
    if dayOfCycle_node:
        form.dayOfCycle.data = dayOfCycle_node.content
    
    stageOfCycle_node = node.find_child('stageOfCycle')
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
    
    sectionThickness_node = node.find_child('sectionThickness')
    if sectionThickness_node:
        form.sectionThickness.data = sectionThickness_node.content
    
    sectionThicknessUnit_node = node.find_child('sectionThicknessUnit')
    if sectionThicknessUnit_node:
        form.sectionThicknessUnit.data = sectionThicknessUnit_node.content

    fixation_node = node.find_child('fixation')
    if fixation_node:
        form.fixation.data = fixation_node.content

    fixationOther_node = node.find_child('fixationOther')
    if fixationOther_node:
        form.fixationOther.data = fixationOther_node.content
    
    stain_node = node.find_child('stain')
    if stain_node:
        form.stain.data = stain_node.content

    stainLightType_node = node.find_child('stainLightType_node')
    if stainLightType_node:
        form.stainLightType.data = stainLightType_node.content

    sudanStainType_node = node.find_child('sudanStainType')
    if sudanStainType_node:
        form.sudanStainType.data = sudanStainType_node.content

    stainLightOther_node = node.find_child('stainLightOther_node')
    if stainLightOther_node:
        form.stainLightOther.data = stainLightOther_node.content
    
    stainFluorescentType_node = node.find_child('stainFluorescentType')
    if stainFluorescentType_node:
        form.stainFluorescentType.data = stainFluorescentType_node.content

    stainFluorescentOther_node = node.find_child('stainFluorescentOther')
    if stainFluorescentOther_node:
        form.stainFluorescentOther.data = stainFluorescentOther_node.content

    stainElectronType_node = node.find_child('stainElectronType')
    if stainElectronType_node:
        form.stainElectronType.data = stainElectronType_node.content

    stainElectronOther_node = node.find_child('stainElectronOther')
    if stainElectronOther_node:
        form.stainElectronOther.data = stainElectronOther_node.content

    magnification_node = node.find_child('magnification')
    if magnification_node:
        form.magnification.data = magnification_node.content

    maker_node = node.find_child('maker')
    if maker_node:
        form.maker.data = maker_node.content

    model_node = node.find_child('model')
    if model_node:
        form.model.data = model_node.content

    notes_node = node.find_child('notes')
    if notes_node:
        form.notes.data = notes_node.content

    form.md5.data = form_md5(form)
