"""
The various routes for the collaborate page. E.g., display the page, enable EDI curation, invite a collaborator, etc.
"""
import os
import shutil
from urllib.parse import quote, unquote, urlparse

from flask import (
    Blueprint, flash, render_template, redirect, request, url_for,
    session, Markup, jsonify, send_file
)

from flask_login import (
    current_user, login_required
)
import webapp.auth.user_data as user_data

import webapp.mimemail as mimemail

from webapp.config import Config
from webapp.home.home_utils import log_error, log_info, get_check_metadata_status
from webapp.home.utils.hidden_buttons import is_hidden_button, handle_hidden_buttons
from webapp.home.utils.load_and_save import load_eml
from webapp.home.utils.lists import list_data_packages
from webapp.buttons import *
from webapp.pages import *
from metapype.eml import names
from webapp.home.log_usage import (
    actions,
    log_usage,
)

from webapp.home.views import get_helps, set_current_page, open_document, close_document, get_back_url
from webapp.home.exceptions import (
    CollaboratingWithGroupAlready,
    InvitationBeingAcceptedByOwner,
    InvitationNotFound,
    UserIsNotTheOwner,
    UserNotFound
)

import webapp.views.collaborations.backups as backups
import webapp.views.collaborations.collaborations as collaborations
from webapp.views.collaborations.collaborations import (
    get_package,
    package_is_under_edi_curation,
    another_package_with_same_name_is_under_edi_curation,
    get_package_by_id,
    get_collaborations,
    get_invitations,
    get_collaboration_output,
    get_group_collaboration_output,
    get_user_output,
    get_package_output,
    get_lock_output,
    get_group_lock_output,
    release_acquired_lock
)
import webapp.views.collaborations.backups as collaboration_backups
from webapp.views.collaborations.forms import (
    CollaborateForm,
    EnableEDICurationForm,
    InviteCollaboratorForm,
    AcceptInvitationForm)

collab_bp = Blueprint('collab', __name__, template_folder='templates')


@collab_bp.route('/collaborate', methods=['GET', 'POST'])
@collab_bp.route('/collaborate/<filename>', methods=['GET', 'POST'])
@collab_bp.route('/collaborate/<filename>/<dev>', methods=['GET', 'POST'])
@login_required
def collaborate(filename=None, dev=None):
    """
    Handle display of the collaborate page.
    """
    if is_hidden_button():
        new_page = handle_hidden_buttons(PAGE_COLLABORATE)
        current_document = current_user.get_filename()
        return redirect(url_for(new_page, filename=current_document))

    form = CollaborateForm()

    # Process POST
    if request.method == 'POST':

        if not filename:
            filename = current_user.get_filename()

        if request.form.get(BTN_SUBMIT) == BTN_INVITE_COLLABORATOR:
            return redirect(url_for(PAGE_INVITE_COLLABORATOR, filename=filename, dev=dev))

        if request.form.get(BTN_SUBMIT) == BTN_ACCEPT_INVITATION:
            return redirect(url_for(PAGE_ACCEPT_INVITATION, filename=filename, dev=dev))

        if request.form.get(BTN_SUBMIT) == BTN_SHOW_BACKUPS:
            return redirect(url_for(PAGE_SHOW_BACKUPS, filename=filename))

        if request.form.get(BTN_SUBMIT) == BTN_SAVE_BACKUP:
            return redirect(url_for(PAGE_SAVE_BACKUP))

        if request.form.get(BTN_SUBMIT) == BTN_REFRESH:
            return redirect(url_for(PAGE_COLLABORATE, filename=filename, dev=dev))

        if request.form.get(BTN_SUBMIT) == BTN_CLEAN_UP_DATABASE:
            collaborations.cleanup_db()
            flash('The database has been cleaned up.', 'success')
            return redirect(url_for(PAGE_COLLABORATE, filename=filename, dev=dev))

    flash_msg = request.args.get('flash_msg', '')
    if flash_msg:
        flash(flash_msg)

    user_login = current_user.get_user_login()
    log_usage(actions['COLLABORATE'], user_login)

    my_collaborations = get_collaborations(user_login)
    my_invitations = get_invitations(user_login)

    collaboration_list = get_collaboration_output()
    group_collaboration_list = get_group_collaboration_output()
    user_list = get_user_output()
    package_list = get_package_output()
    lock_list = get_lock_output()
    group_lock_list = get_group_lock_output()
    set_current_page('collaborate')
    if current_user.get_file_owner():
        owned_by_other = True
    else:
        owned_by_other = False
    invitation_disabled = owned_by_other or not current_user.get_filename()
    save_backup_disabled = collaborations.save_backup_is_disabled()
    is_edi_curator = current_user.is_edi_curator()
    help = get_helps(['collaborate_general', 'collaborate_invite_accept'])

    return render_template('collaborate.html', collaborations=my_collaborations, invitations=my_invitations,
                           user=user_login, invitation_disabled=invitation_disabled,
                           save_backup_disabled=save_backup_disabled,
                           collaboration_list=collaboration_list, group_collaboration_list=group_collaboration_list,
                           user_list=user_list, package_list=package_list,
                           lock_list=lock_list, group_lock_list=group_lock_list,
                           is_edi_curator=is_edi_curator, help=help, dev=dev)


@collab_bp.route('/enable_edi_curation/<filename>', methods=['GET', 'POST'])
@login_required
def enable_edi_curation(filename=None):
    if is_hidden_button():
        new_page = handle_hidden_buttons(PAGE_SHARE_SUBMIT_PACKAGE)
        current_document = current_user.get_filename()
        return redirect(url_for(new_page, filename=current_document))

    form = EnableEDICurationForm()

    enable_disabled = False
    # if current_user.is_edi_curator():
    #     flash('You are logged in as an EDI Curator. You are not permitted to enable EDI curation from this user account.', 'error')
    #     enable_disabled = True

    # See if package is already under EDI curation. If so, just display an informational message.
    owner_login = user_data.get_active_document_owner_login()
    package = get_package(owner_login, filename, create_if_not_found=False)
    if package:
        package_id = package.package_id
        if package_is_under_edi_curation(package_id):
            flash(Markup('A collaboration with EDI Curators has already been established for this package.<p><p> ' \
                  'To make the package available to EDI Curators again, click the <b>Make available</b> link for ' \
                  'the package, below.'))
            return redirect(url_for(PAGE_COLLABORATE, filename=filename))

    # Process POST
    if request.method == 'POST':

        if request.form.get(BTN_CANCEL):
            return redirect(url_for(PAGE_SHARE_SUBMIT_PACKAGE, filename=filename))

        if request.form.get(BTN_SUBMIT):
            name = form.data['name']
            email_address = form.data['email_address']
            notes = form.data['notes']
            is_update = 'existing' in form.data['is_update']
            update_package = form.update_package.data if form.update_package.data else 'None'

            if notes:
                return redirect(url_for(PAGE_ENABLE_EDI_CURATION_2,
                                        filename=filename,
                                        name=name,
                                        email_address=email_address,
                                        notes=quote(notes, safe=''),
                                        is_update=is_update,
                                        update_package=quote(update_package, safe='')))
            else:
                return redirect(url_for(PAGE_ENABLE_EDI_CURATION_2,
                                        filename=filename,
                                        name=name,
                                        email_address=email_address,
                                        is_update=is_update,
                                        update_package=quote(update_package, safe='')))

        if request.form.get(BTN_CANCEL):
            return redirect(get_back_url())

    help = get_helps(['enable_edi_curation', 'enable_edi_curation_notes'])
    eml_node = load_eml(filename=filename)
    return render_template('enable_edi_curation.html', filename=filename, enable_disabled=enable_disabled,
                           check_metadata_status=get_check_metadata_status(eml_node, filename),
                           help=help, form=form)


def enable_edi_curation_mail_body(server=None, package_id=None, filename=None, name=None, email_address=None, notes=None,
                                  is_update=False, update_package=None):
    msg = 'Dear EDI Data Curator:' + '\n\n' + \
        f'This email was auto-generated by ezEML on {server}.\n\n\n' + \
        'An ezEML user has enabled EDI Curation.\n\n' + \
        '   User\'s name: ' + name + '\n\n' + \
        '   User\'s email: ' + email_address + '\n\n' + \
        '   Package name: ' + filename + '\n\n'
    if is_update:
        msg += '   This package is an update to package ' + unquote(update_package) + '.\n\n'
    else:
        msg += '   This package is a new package.\n\n'
    if notes:
        msg += '   User\'s Notes: ' + unquote(notes)
    if package_id and another_package_with_same_name_is_under_edi_curation(package_id):
        msg += '\n\n' + \
            'ezEML-Generated Note to Curators:\n' + \
            '   Another package with the same name but a different owner is already under EDI curation.\n' + \
            '   This may indicate that the package has been duplicated in multiple accounts amd the user is confused\n' + \
            '   about how collaboration is intended to work. Please contact the user to clarify the situation.'
    return msg


@collab_bp.route('/enable_edi_curation_2/<filename>/<name>/<email_address>/<is_update>/<update_package>', methods=['GET', 'POST'])
@collab_bp.route('/enable_edi_curation_2/<filename>/<name>/<email_address>/<notes>/<is_update>/<update_package>', methods=['GET', 'POST'])
@login_required
def enable_edi_curation_2(filename=None, name=None, email_address=None, notes=None, is_update:bool=False, update_package=None):
    if is_hidden_button():
        new_page = handle_hidden_buttons(PAGE_DELETE)
        current_document = current_user.get_filename()
        return redirect(url_for(new_page, filename=current_document))

    try:
        owner_login = user_data.get_active_document_owner_login()

        # Create a group collaboration with EDI Curators
        package_id = None
        group_collaboration = collaborations.add_group_collaboration(owner_login, 'EDI Curators', filename)

        # Activate group lock
        if group_collaboration:
            collaborations.add_group_lock(package_id=group_collaboration.package_id,
                                          locked_by=group_collaboration.user_group_id)
            package_id = group_collaboration.package_id

            # Back up the current package
            collaboration_backups.save_backup(package_id, primary=True)

        # Send an email to EDI Curators to let them know that a new package is available for curation
        parsed_url = urlparse(request.base_url)
        server = parsed_url.netloc
        msg = enable_edi_curation_mail_body(server, package_id, filename, name, email_address, notes, eval(is_update), update_package)

        if not Config.DISABLE_ENABLE_EDI_CURATION_EMAILS:
            sent = mimemail.send_mail(subject='An ezEML user has enabled EDI curation',
                                      msg=msg,
                                      to=Config.TO,
                                      to_name=Config.TO_NAME)
        else:
            sent = True
        if sent is True:
            log_usage(actions['ENABLE_EDI_CURATION'], name, email_address)
        flash('The package has been submitted to the EDI data curation team for review.', 'success')

    except UserIsNotTheOwner:
        flash('Only the owner of the package can submit it to EDI.', 'error')
        # return redirect(url_for(PAGE_COLLABORATE, filename=filename))
    except CollaboratingWithGroupAlready:
        flash('A collaboration with EDI Curators has already been established for this package.\n\n ' \
                'To make the package available to EDI Curators again, click the "Make available" link for the ' \
                'package, below.')
        # return redirect(url_for(PAGE_COLLABORATE, filename=filename))
    except Exception as e:
        flash('An error occurred while enabling EDI curation for this package. Please report this to support@edirepository.org.', 'error')
        log_error(e)

    return redirect(url_for(PAGE_COLLABORATE, filename=current_user.get_filename()))


@collab_bp.route('/accept_invitation', methods=['GET', 'POST'])
@collab_bp.route('/accept_invitation/<filename>', methods=['GET', 'POST'])
@collab_bp.route('/accept_invitation/<filename>/<invitation_code>', methods=['GET', 'POST'])
@login_required
def accept_invitation(filename=None, invitation_code=None):
    if is_hidden_button():
        new_page = handle_hidden_buttons(PAGE_DELETE)
        current_document = current_user.get_filename()
        return redirect(url_for(new_page, filename=current_document))

    form = AcceptInvitationForm()
    if request.method == 'POST' and form.validate_on_submit():
        if request.form.get(BTN_SUBMIT):
            invitation_code = form.invitation_code.data
            if invitation_code:
                user_login = current_user.get_user_login()
                try:
                    # Get the details on the invitation. It will be deleted if it is accepted, so we capture
                    #  the details here.
                    invitation = collaborations.get_invitation_by_code(invitation_code)
                    inviter_name = invitation.inviter_name
                    inviter_email = invitation.inviter_email
                    invitee_name = invitation.invitee_name
                    invitee_email = invitation.invitee_email
                    package_name = invitation.package.package_name

                    collaboration = collaborations.accept_invitation(user_login, invitation_code)
                    flash('You have successfully accepted the invitation.', 'success')

                    # Check if user owns a package of the same name. If so, warn them. They're probably confused.
                    duplicate_name = False
                    for user_package in list_data_packages(True, True):
                        if package_name == user_package[0]:
                            duplicate_name = True
                            break
                    if duplicate_name:
                        flash("You own a package with the same name as the one you're being invited to collaborate on. "
                              "This often indicates some confusion about how collaboration is meant to be used. "
                              "You may want to contact support@edirepository.org for assistance.", 'error')

                    msg = compose_inform_inviter_of_acceptance_email(inviter_name, invitee_name,
                                                                     invitee_email, package_name)
                    sent = mimemail.send_mail(subject='Invitation to collaborate has been accepted',
                                              msg=msg,
                                              to=inviter_email,
                                              to_name=inviter_name)
                    if sent is True:
                        log_usage(actions['ACCEPT_INVITATION'], inviter_name, invitee_name)
                        flash(f'An email has been sent to {inviter_name} ({inviter_email}) to tell them you have accepted their invitation.',
                              'info')
                except InvitationNotFound:
                    flash('The invitation code was not found. Check that you entered it correctly. Otherwise, it '
                          'was already accepted, has expired, or has been cancelled.', 'error')
                except InvitationBeingAcceptedByOwner:
                    flash('You are the originator of this invitation. You cannot accept your own invitation.', 'error')
                except Exception as e:
                    flash(f'An error occurred while accepting the invitation. {e}', 'error')

        return redirect(url_for(PAGE_COLLABORATE, filename=filename))

    set_current_page('collaborate')
    help = get_helps(['invite_collaborator'])
    return render_template('accept_invitation.html',
                           title='Accept an Invitation',
                           form=form, help=help)


def compose_inform_inviter_of_acceptance_email(inviter_name, invitee_name, invitee_email, title):
    msg_raw = f'Dear {inviter_name}:\n\n' \
        f'{invitee_name} ({invitee_email}) has accepted your invitation to collaborate with you on editing the data ' \
        f'package "{title}" in ezEML.\n\n' \
        f'To manage the collaboration, go to the "Collaborate" page in ezEML.\n\n' \
        f'Thank you for using ezEML.'
    return msg_raw


def compose_invite_collaborator_email(name, sender_name, sender_email, title, invitation_code, ezeml_url):
    msg_html = Markup(f'Dear {name}:<p><br>'
        f'I am inviting you to collaborate with me on editing a data package in ezEML.<p><br>Data Package Title: "{title}"<p>' \
        f'To accept the invitation, please do the following:<p>' \
        f'- go to {ezeml_url} and log in using the login account you will use to edit the package<br>' \
        f'- in ezEML, click the "Collaborate" link<br>' \
        f'- on the "Collaborate" page, click the "Accept an Invitation" button<br>' \
        f'- enter this invitation code: <b>{invitation_code}</b><p>' \
        f'After you accept the invitation, you will be able to edit the data package with me in ezEML.<p>' \
        f'To learn more about ezEML, go to https://ezeml.edirepository.org.<p>' \
        f'Thanks!<p>{sender_name}<br>{sender_email}')
    msg_raw = f'Dear {name}:\n\n' \
        f'I am inviting you to collaborate with me on editing a data package in ezEML.\n\nData Package Title: "{title}"\n\n' \
        f'To accept the invitation, please do the following:\n' \
        f'- go to {ezeml_url} and log in using the login account you will use to edit the package\n' \
        f'- in ezEML, click the "Collaborate" link\n' \
        f'- on the "Collaborate" page, click the "Accept an Invitation" button\n' \
        f'- enter this invitation code: {invitation_code}\n\n' \
        f'After you accept the invitation, you will be able to edit the data package with me in ezEML.\n\n' \
        f'To learn more about ezEML, go to https://ezeml.edirepository.org.\n\n' \
        f'Thanks!\n\n{sender_name}\n{sender_email}'
    msg_quoted = f'mailto:{quote(msg_raw)}'
    return msg_quoted, msg_html, msg_raw


# @collab_bp.route('/invite_collaborator', methods=['GET', 'POST'])
@collab_bp.route('/invite_collaborator/<filename>', methods=['GET', 'POST'])
@login_required
def invite_collaborator(filename=None):
    if is_hidden_button():
        new_page = handle_hidden_buttons(PAGE_DELETE)
        current_document = current_user.get_filename()
        return redirect(url_for(new_page, filename=current_document))

    eml_node = load_eml(filename=filename)
    title_node = eml_node.find_single_node_by_path([names.DATASET, names.TITLE])
    if not title_node or not title_node.content:
        flash('The data package must have a Title before a collaboration invitation can be sent.', 'error')
        return redirect(url_for(PAGE_TITLE, filename=filename))

    form = InviteCollaboratorForm()
    if request.method == 'POST' and form.validate_on_submit():
        # If the user has clicked Save in the EML Documents menu, for example, we want to ignore the
        #  programmatically generated Submit
        if request.form.get(BTN_SUBMIT) == BTN_SEND_INVITATION:

            user_name = form.data['user_name']
            user_email = form.data['user_email']

            collaborator_name = form.data['collaborator_name']
            email_address = form.data['email_address']
            title = title_node.content

            parsed_url = urlparse(request.base_url)
            ezeml_url = f"{parsed_url.scheme}://{parsed_url.netloc}/eml"

            # Generate an Invitation record in the database
            try:
                invitation_code = collaborations.create_invitation(filename, user_name, user_email,
                                                                   collaborator_name, email_address)
            except Exception as e:
                log_error(f'create_invitation: {e}')
                raise

            try:
                mailto, mailto_html, mailto_raw = compose_invite_collaborator_email(collaborator_name,
                                                                                    user_name, user_email,
                                                                                    title, invitation_code,
                                                                                    ezeml_url)
            except Exception as e:
                collaborations.remove_invitation(invitation_code)
                raise

            subject = 'Invitation to collaborate on editing an ezEML data package'
            sent = mimemail.send_mail(subject=subject, msg=mailto_raw, to=email_address, to_name=collaborator_name)
            if sent is True:
                log_usage(actions['INVITE_COLLABORATOR'], collaborator_name, email_address)
                flash(f'An invitation has been sent to {collaborator_name} ({email_address}) to collaborate on editing the data package "{title}".')
                flash(f'When {collaborator_name} has accepted the invitation, you will be notified by email.', 'info')
                return redirect(url_for(PAGE_COLLABORATE, filename=filename))
            else:
                collaborations.remove_invitation(invitation_code)
                log_usage(actions['INVITE_COLLABORATOR'], 'failed')
                flash(sent, 'error')

    elif 'Cancel' in request.form:
        return redirect(url_for(PAGE_COLLABORATE, filename=filename))

    set_current_page('collaborate')
    help = get_helps(['invite_collaborator'])
    return render_template('invite_collaborator.html',
                           title=filename,
                           form=form, help=help)


@collab_bp.route('/remove_collaboration/<collab_id>', methods=['GET', 'POST'])
@collab_bp.route('/remove_collaboration/<collab_id>/<filename>', methods=['GET', 'POST'])
@login_required
def remove_collaboration(collab_id, filename=None):
    if not collab_id.startswith('G'):
        collaborations.remove_collaboration(collab_id)
        log_usage(actions['END_COLLABORATION'], collab_id)
        return redirect(url_for(PAGE_COLLABORATE, filename=filename))
    else:
        collab_id = int(collab_id[1:])
        collaborations.remove_group_collaboration(collab_id)
        current_document = user_data.get_active_document()
        log_usage(actions['END_GROUP_COLLABORATION'], collab_id)
        return redirect(url_for(PAGE_CLOSE, filename=current_document))


@collab_bp.route('/open_by_collaborator/<collaborator_id>/<package_id>', methods=['GET', 'POST'])
@login_required
def open_by_collaborator(collaborator_id, package_id):
    collaborator_id = int(collaborator_id)
    package_id = int(package_id)

    user_login = current_user.get_user_login()
    owner_login = collaborations.get_owner_login(package_id)
    package = get_package_by_id(package_id)
    if not owner_login or not package:
        flash('This collaboration is no longer active. Please contact the owner of the document.', 'error')
        return render_template('index.html')
    filename = package.package_name

    log_usage(actions['OPEN_BY_COLLABORATOR'], collaborator_id, package_id, filename)

    # Get a lock on the package, if available
    lock = collaborations.open_package(user_login, filename, owner_login=owner_login)
    # If there's a group collaboration and we're a group member, take the group lock as well
    if collaborations.is_edi_curator(user_login) and collaborations.package_is_under_edi_curation(package_id):
        user_id = collaborations.get_user(user_login, create_if_not_found=True).user_id
        edi_curator_group = collaborations.get_user_group("EDI Curators")
        collaborations.add_group_lock(package_id, edi_curator_group.user_group_id)

    # Open the document
    try:
        return open_document(filename, owner=collaborations.display_name(owner_login), owner_login=owner_login)
    except Exception as e:
        release_acquired_lock(lock)


@collab_bp.route('/apply_group_lock/<package_id>/<group_id>', methods=['GET', 'POST'])
@login_required
def apply_group_lock(package_id, group_id):
    collaborations.add_group_lock(int(package_id), group_id)
    current_document = user_data.get_active_document()
    return redirect(url_for(PAGE_COLLABORATE, filename=current_document))


@collab_bp.route('/release_group_lock/<package_id>', methods=['GET', 'POST'])
@login_required
def release_group_lock(package_id):
    # user_login = current_user.get_user_login()
    package_id = int(package_id)
    current_document = user_data.get_active_document()
    collaborations.release_group_lock(package_id)
    close_document()
    flash_message = f'Closed "{current_document}". The package is now available to collaborators.'
    return redirect(url_for(PAGE_COLLABORATE, filename=current_document, flash_msg=flash_message))


@collab_bp.route('/release_lock/<package_id>', methods=['GET', 'POST'])
@login_required
def release_lock(package_id):
    user_login = current_user.get_user_login()
    package_id = int(package_id)
    current_document = user_data.get_active_document()
    collaborations.release_lock(user_login, package_id)
    close_document()
    flash_message = f'Closed "{current_document}". The package is now available to collaborators.'
    return redirect(url_for(PAGE_COLLABORATE, filename=current_document, flash_msg=flash_message))


@collab_bp.route('/cancel_invitation/<invitation_id>', methods=['GET', 'POST'])
@collab_bp.route('/cancel_invitation/<invitation_id>/<filename>', methods=['GET', 'POST'])
@login_required
def cancel_invitation(invitation_id, filename=None):
    collaborations.cancel_invitation(invitation_id)
    if not filename:
        filename = user_data.get_active_document()
    return redirect(url_for(PAGE_COLLABORATE, filename=filename))


@collab_bp.route('/save_backup', methods=['GET', 'POST'])
@login_required
def save_backup():
    # current_document = current_user.get_filename()
    user_login = current_user.get_user_login()
    # owner = user_data.get_active_document_owner()
    active_package = collaborations.get_active_package(user_login)
    if active_package:
        package_id = active_package.package_id
        backups.save_backup(package_id)
    return redirect(url_for(PAGE_SHOW_BACKUPS))


@collab_bp.route('/show_backups', methods=['GET', 'POST'])
@collab_bp.route('/show_backups/<filename>', methods=['GET', 'POST'])
@collab_bp.route('/show_backups/<filename>/<action>', methods=['GET', 'POST'])
@login_required
def show_backups(filename=None, action=None):
    current_document = current_user.get_filename()

    if is_hidden_button():
        new_page = handle_hidden_buttons(PAGE_SHOW_BACKUPS)
        return redirect(url_for(new_page, filename=current_document))

    # The action parameter is used to signal we want to
    #  return to the previous page.
    if action == '____back____' or filename == '____back____':
        return redirect(url_for(PAGE_COLLABORATE, filename=current_document))

    backups = collaboration_backups.get_backups()
    return render_template('show_backups.html', backups=backups)


@collab_bp.route('/oreview_backup/<filename>', methods=['GET', 'POST'])
@login_required
def preview_backup(filename=None):
    # Load the backup into the logged in user's session
    #  and then open the document for review.

    # Copy json file into the user's data directory
    user_data_dir = user_data.get_user_folder_name(current_user_directory_only=True)
    # Trim the filename
    filename = unquote(filename)
    # Remove the datetime and 'primary' flag from the filename. Append '_PREVIEW' so the user can keep it straight
    #  that the original is in the owner's account, not theirs.
    package_name = os.path.basename(filename.split('.json.')[0]) + '_PREVIEW'
    dest_filename = f"{package_name}.json"
    # Copy the file
    shutil.copyfile(filename, os.path.join(user_data_dir, dest_filename))

    # We need to set the active document to the backup but owned by the logged in user
    #  because we're opening the document in the logged in user's account.
    collaborations.change_active_package_account(package_name)

    return redirect(url_for(PAGE_OPEN_PACKAGE, package_name=package_name))


@collab_bp.route('/restore_backup/<filename>/<owner>', methods=['GET', 'POST'])
@login_required
def restore_backup(filename=None, owner=None):
    # Copy the backup into the collaboration owner's account
    # Load the backup into the logged in user's session
    #  and then open the document for review.

    # Copy json file into the owner's data directory
    owner_data_dir = os.path.join(Config.USER_DATA_DIR, owner)
    # Trim the filename
    filename = unquote(filename)
    trimmed_filename = os.path.basename(filename.split('.json.')[0] + '.json')
    # Copy the file
    shutil.copyfile(filename, os.path.join(owner_data_dir, trimmed_filename))
    package_name = os.path.splitext(trimmed_filename)[0]

    return redirect(url_for(PAGE_OPEN_PACKAGE, package_name=package_name, owner=owner))


@collab_bp.route('/delete_backup/<filename>', methods=['GET', 'POST'])
@login_required
def delete_backup(filename=None):
    # Remove the backup file from the server
    filename = unquote(filename)
    os.remove(filename)

    return redirect(url_for(PAGE_SHOW_BACKUPS))


@collab_bp.route('/patch_db/<package_id>/<owner_id>/<new_package_id>', methods=['GET', 'POST'])
@login_required
def patch_db(package_id=None, owner_id=None, new_package_id=None):
    import webapp.views.collaborations.collaborations as collaborations
    from webapp import db
    import daiquiri
    logger = daiquiri.getLogger('routes: ' + __name__)
    """
    Ad hoc patching of the database
    """
    # In collaborations where package_id == package_id and owner_id == owner_id, change package_id to new_package_id
    collabs = collaborations.Collaboration.query.filter_by(package_id=package_id, owner_id=owner_id).all()
    for collaboration in collabs:
        logger.info(f"collaboration: {collaboration}")
        collaboration.package_id = new_package_id
        db.session.commit()
    # In group_collaborations where package_id == package_id and owner_id == owner_id, change package_id to new_package_id
    group_collabs = collaborations.GroupCollaboration.query.filter_by(package_id=package_id, owner_id=owner_id).all()
    for group_collab in group_collabs:
        logger.info(f"group_collaboration: {group_collab}")
        group_collab.package_id = new_package_id
        db.session.commit()
    # In group_locks where package_id == package_id, change package_id to new_package_id
    group_locks = collaborations.GroupLock.query.filter_by(package_id=package_id).all()
    for group_lock in group_locks:
        logger.info(f"group_lock: {group_lock}")
        group_lock.package_id = new_package_id
        db.session.commit()
    return redirect(url_for(PAGE_COLLABORATE))

