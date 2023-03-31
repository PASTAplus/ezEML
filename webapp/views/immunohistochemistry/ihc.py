from flask import (
    Blueprint, flash, render_template, redirect, request, url_for
)

from webapp.views.immunohistochemistry.forms import (
    immunohistochemistryForm
)

from webapp.home.forms import (
    form_md5, is_dirty_form
)

from webapp.home.metapype_client import (
    load_eml, save_both_formats,
    add_child, new_child_node
)

from webapp.home.motherpype import (
    create_immunohistochemistry
)

from webapp.home.motherpype import (
    add_mother_metadata
)

from metapype.eml import names
from metapype.model.node import Node

from webapp.home import motherpype_names as mdb_names

from webapp.buttons import *
from webapp.pages import *

from webapp.home.views import select_post, non_breaking, set_current_page, get_help, get_helps

ihc_bp = Blueprint('ihc', __name__, template_folder='templates')

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

@ihc_bp.route('/immunohistochemistry/<filename>', methods=['GET', 'POST'])
def immunohistochemistry(filename=None):
    method = request.method
    node_id = '1'
    if filename:
        eml_node = load_eml(filename=filename)
        additional_metadata_node = eml_node.find_child(names.ADDITIONALMETADATA)
        if additional_metadata_node:
            metadata_node = additional_metadata_node.find_child(names.METADATA)
            mother_node = metadata_node.find_child("mother")
#            mother_node = metadata_node.find_child("mdb:mother")  # PT5/27
            if mother_node:
                ihc_node = mother_node.find_child("immunohistochemistry")
                if ihc_node:
                    node_id = ihc_node.id
        else:
            add_mother_metadata(eml_node, filename=filename)
    # Added in 4/8/2022
    save_both_formats(filename, eml_node)
    set_current_page('ihc')
    help = [get_help('immunohistochemistry')]
    return new_immunohistochemistry(filename=filename, node_id=node_id,
                                    method=method, node_name="immunohistochemistry",
                                    back_page=PAGE_DONOR, next_page=PAGE_CHECK, title='Immunohistochemistry',  #PT5/26
                                    save_and_continue=True, help=help)


def new_immunohistochemistry(filename=None, node_id=None, method=None,
                             node_name=None, back_page=None, title=None,
                             next_page=None, save_and_continue=False, help=None,
                             project_node_id=None):
    if BTN_CANCEL in request.form:
        if not project_node_id:
            url = url_for(back_page, filename=filename)
        else:
            url = url_for(back_page, filename=filename, node_id=project_node_id)
        return redirect(url)

    form = immunohistochemistryForm(filename=filename)
    eml_node = load_eml(filename=filename)

    additional_metadata_node = eml_node.find_child(names.ADDITIONALMETADATA)
    metadata_node = additional_metadata_node.find_child(names.METADATA)
    mother_node = metadata_node.find_child("mother")
#    mother_node = metadata_node.find_child("mdb:mother")  # PT5/27
    ihc_node = mother_node.find_child(node_name) #PT4/25
    if not ihc_node: # PT4/25
        mother_node.add_child(Node(node_name, parent=mother_node)) # PT4/25
        ihc_node = mother_node.find_child(node_name)  # PT4/25

    new_page = select_new_page(back_page, next_page)

    # Could be important as well -NM 4/8/2022
    # new_page = select_new_page(back_page, next_page)
    # new_page = back_page

    # Could be important later -NM 4/8/2022
    # form_value = request.form
    # form_dict = form_value.to_dict(flat=False)
    # url = select_post(filename, form, form_dict,
    #                  'POST', PAGE_IHC, project_node_id=project_node_id)

    # Process POST

    isIHC = form.isIHC.data

    save = False
    if is_dirty_form(form) or isIHC == 'No':
        save = True

    if form.validate_on_submit() and method == 'POST': # I added 'and method == ' PT4/25

        if save:
            targetProtein = form.targetProtein.data
            primaryAntibody = Node("primaryAntibody", parent=None)
            clonality = form.clonality.data
            targetSpecies = form.targetSpecies.data
            hostSpecies = form.hostSpecies.data
            dilution = form.dilution.data
            lotNumber = form.lotNumber.data
            catNumber = form.catNumber.data
            source = Node("source", parent=None)
            sourceName = form.sourceName.data
            sourceCity = form.sourceCity.data
            sourceState = form.sourceState.data
            rrid = form.rrid.data
            secondaryAntibody = Node("secondaryAntibody", parent=None)
            targetSpecies_2 = form.targetSpecies_2.data
            hostSpecies_2 = form.hostSpecies_2.data
            dilution_2 = form.dilution_2.data
            lotNumber_2 = form.lotNumber_2.data
            catNumber_2 = form.catNumber_2.data
            source_2 = Node("source", parent=None)
            sourceName_2 = form.sourceName_2.data
            sourceCity_2 = form.sourceCity_2.data
            sourceState_2 = form.sourceState_2.data
            rrid_2 = form.rrid_2.data
            detectionMethod = form.detectionMethod.data

            if isIHC == 'Yes':
                create_immunohistochemistry( #PT4/25
                    ihc_node,
                    filename,
                    targetProtein,
                    primaryAntibody,
                    clonality,
                    targetSpecies,
                    hostSpecies,
                    dilution,
                    lotNumber,
                    catNumber,
                    source,
                    sourceName,
                    sourceCity,
                    sourceState,
                    rrid,
                    secondaryAntibody,
                    targetSpecies_2,
                    hostSpecies_2,
                    dilution_2,
                    lotNumber_2,
                    catNumber_2,
                    source_2,
                    sourceName_2,
                    sourceCity_2,
                    sourceState_2,
                    rrid_2,
                    detectionMethod,
                )
            else:
                ihc_node.remove_children()


#PT4/25            if node_id and len(node_id) != 1:
#PT4/25                old_ihc_node = Node.get_node_instance(node_id)
#PT4/25                if old_ihc_node:
#PT4/25                    old_ihc_parent_node = old_ihc_node.parent
#PT4/25                    old_ihc_parent_node.replace_child(old_ihc_node, ihc_node)
#PT4/25                else:
#PT4/25                    msg = f"No node found in the node store with node id {node_id}"
#PT4/25                    raise Exception(msg)
#PT4/25            else:
#PT4/25                print("we are adding the child")
#PT4/25                parent_node.add_child(new_ihc_node)

            save_both_formats(filename=filename, eml_node=eml_node)
            #new_page = "ihc.immunohistochemistry" #PT4/25 --> THIS WILL NEED TO BE CHANGED TO THE NEXT SEQUENCED ITEM IN SIDE LIST
#            return redirect(url_for(new_page, filename=filename, node_id=ihc_node.id)) #PT4/25
        return redirect(url_for(new_page, filename=filename)) #PT4/25
    # Process GET
    if node_id == '1':
        form.init_md5()

    #PT NEW 4/25
    elif node_id:
        related_project_node = Node.get_node_instance(node_id)
        populate_ihc_form(form, related_project_node)
    return render_template('ihc.html', title=title, node_name=node_name,
                           form=form, next_page=next_page, save_and_continue=save_and_continue, help=help)
    #END PT NEW 4/25
'''PT4/25START
        # else:
        if parent_node:
            rp_nodes = parent_node.find_all_children(child_name=node_name)
            if rp_nodes:
                for ihc_node in rp_nodes:
                    if node_id == ihc_node.id:
                        populate_ihc_form(form, ihc_node)

    help = get_helps([node_name]) 
    return render_template('ihc.html', title=title, node_name=node_name,
                           form=form, next_page=next_page, save_and_continue=save_and_continue, help=help) END'''


def populate_ihc_form(form: immunohistochemistryForm, node: Node):
    if node.children:
        form.isIHC.data = "Yes"
    else:
        form.isIHC.data = "No"

    protein_node = node.find_child(mdb_names.TARGET_PROTEIN)
    if protein_node:
#PT4/25        proteinName_node = protein_node.find_child("targetProtein")
#PT4/25        if proteinName_node:
#PT4/25                form.proteinName.data = proteinName_node.content
        form.targetProtein.data = protein_node.content    #PT4/25

    user_id_nodes = node.find_all_children(names.USERID)
    for user_id_node in user_id_nodes:
        directory = user_id_node.attribute_value('directory')
        if directory == 'https://orcid.org':
            form.user_id.data = user_id_node.content
        else:
            form.org_id.data = user_id_node.content
            form.org_id_type.data = directory

    primaryAntibody_node = node.find_child(mdb_names.PRIMARY_ANTIBODY)
    if primaryAntibody_node:
        clonality_node = primaryAntibody_node.find_child(mdb_names.CLONALITY)
        if clonality_node:
            form.clonality.data = clonality_node.content

        targetSpecies_node = primaryAntibody_node.find_child(mdb_names.TARGET_SPECIES)
        if targetSpecies_node:
            form.targetSpecies.data = targetSpecies_node.content

        hostSpecies_node = primaryAntibody_node.find_child(mdb_names.HOST_SPECIES)
        if hostSpecies_node:
            form.hostSpecies.data = hostSpecies_node.content

        dilution_node = primaryAntibody_node.find_child(mdb_names.DILUTION)
        if dilution_node:
            form.dilution.data = dilution_node.content

        lotNumber_node = primaryAntibody_node.find_child(mdb_names.LOT_NUMBER)
        if lotNumber_node:
            form.lotNumber.data = lotNumber_node.content

        catNumber_node = primaryAntibody_node.find_child(mdb_names.CAT_NUMBER)
        if catNumber_node:
            form.catNumber.data = catNumber_node.content

        source_node = primaryAntibody_node.find_child(mdb_names.SOURCE)
        if source_node:
            sourceName_node = source_node.find_child(mdb_names.SOURCE_NAME)
            if sourceName_node:
                form.sourceName.data = sourceName_node.content

            sourceCity_node = source_node.find_child(mdb_names.SOURCE_CITY)
            if sourceCity_node:
                form.sourceCity.data = sourceCity_node.content

            sourceState_node = source_node.find_child(mdb_names.SOURCE_STATE)
            if sourceState_node:
                form.sourceState.data = sourceState_node.content

        rrid_node = primaryAntibody_node.find_child(mdb_names.RRID)
        if rrid_node:
            form.rrid.data = rrid_node.content

    secondaryAntibody_node = node.find_child(mdb_names.SECONDARY_ANTIBODY)
    if secondaryAntibody_node:
        targetSpecies_node_2 = secondaryAntibody_node.find_child(mdb_names.TARGET_SPECIES)
        if targetSpecies_node_2:
            form.targetSpecies_2.data = targetSpecies_node_2.content

        hostSpecies_node_2 = secondaryAntibody_node.find_child(mdb_names.HOST_SPECIES)
        if hostSpecies_node_2:
            form.hostSpecies_2.data = hostSpecies_node_2.content

        dilution_node_2 = secondaryAntibody_node.find_child(mdb_names.DILUTION)
        if dilution_node_2:
            form.dilution_2.data = dilution_node_2.content

        lotNumber_node_2 = secondaryAntibody_node.find_child(mdb_names.LOT_NUMBER)
        if lotNumber_node_2:
            form.lotNumber_2.data = lotNumber_node_2.content

        catNumber_node_2 = secondaryAntibody_node.find_child(mdb_names.CAT_NUMBER)
        if catNumber_node_2:
            form.catNumber_2.data = catNumber_node_2.content

        source_node_2 = secondaryAntibody_node.find_child(mdb_names.SOURCE)
        if source_node_2:
            sourceName_node_2 = source_node_2.find_child(mdb_names.SOURCE_NAME)
            if sourceName_node_2:
                form.sourceName_2.data = sourceName_node_2.content

            sourceCity_node_2 = source_node_2.find_child(mdb_names.SOURCE_CITY)
            if sourceCity_node_2:
                form.sourceCity_2.data = sourceCity_node_2.content

            sourceState_node_2 = source_node_2.find_child(mdb_names.SOURCE_STATE)
            if sourceState_node_2:
                form.sourceState_2.data = sourceState_node_2.content

        rrid_node_2 = secondaryAntibody_node.find_child(mdb_names.RRID)
        if rrid_node_2:
            form.rrid_2.data = rrid_node_2.content

    detectionMethod_node = node.find_child(mdb_names.DETECTION_METHOD)
    if detectionMethod_node:
        form.detectionMethod.data = detectionMethod_node.content

    form.md5.data = form_md5(form)
