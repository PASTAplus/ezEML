import random
import string

from sqlalchemy.types import TypeDecorator, String

from dataclasses import dataclass
from datetime import datetime, date
from flask import url_for, Blueprint
from flask_login import current_user

from webapp import db #, engine
from webapp.config import Config

from webapp.views.collaborations.model import Collaboration, CollaborationStatus, Invitation, Lock, Package, User
from webapp.views.collaborations.data_classes import (
    CollaborationRecord,
    InvitationRecord,
    CollaborationOutput,
    LockOutput,
    PackageOutput,
    UserOutput
)
from webapp.views.collaborations.db_session import db_session
import webapp.home.exceptions as exceptions


import daiquiri
import logging

logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.ERROR)

logger = daiquiri.getLogger('collaborations: ' + __name__)


logger = daiquiri.getLogger('views: ' + __name__)
# col_bp = Blueprint('col', __name__, template_folder='templates')

# session_factory = sessionmaker(bind=engine)
# Session = scoped_session(sessionmaker(bind=engine))


def display_name(user_login: str) -> str:
    try:
        if user_login:
            return user_login[:user_login.rfind('-')]
        else:
            return ''
    except:
        ijk = 1
        return ''


# def set_active_package_for_collaborator(collaborator_id, package_id):
#     collaborator = _get_user(collaborator_id)
#     if not collaborator:
#         raise exceptions.CollaborationDatabaseError(f'Collaborator {collaborator_id} does not exist.')
#     _set_active_package_id(collaborator_id, package_id)


def set_active_package(user_login, package_name, owner_login=None, session=None):
    """
    Set the active package for the user. This is called when a package is opened. We set it right away, before we know
    whether we can get the lock. That way, the lock handling code can assume it's set. If we can't get the lock, we'll
    reset it to None.
    """
    with db_session(session) as session:
        user = get_user(user_login, create_if_not_found=True, session=session)
        if not owner_login:
            owner_login = user_login
        package = get_package(owner_login, package_name, create_if_not_found=True, session=session)
        user.active_package_id = package.package_id
    return package


def _set_active_package_id(user_id, package_id, session=None):
    with db_session(session) as session:
        # This should only be called by the lock handling code. The user is assumed to exist.
        user = _get_user(user_id)
        user.active_package_id = package_id


def _get_active_package(user_id):
    user = _get_user(user_id)
    active_package_id = user.active_package_id
    if active_package_id:
        return Package.query.get(active_package_id)
    else:
        return None


def get_active_package(user_login, session=None):
    with db_session(session) as session:
        user = get_user(user_login, create_if_not_found=True, session=session)
        active_package_id = user.active_package_id
        if active_package_id:
            return Package.query.get(active_package_id)
        else:
            return None


def get_active_package_owner_login(user_login, session=None):
    with db_session(session) as session:
        package = get_active_package(user_login, session=session)
        if package:
            owner = package.owner
            if owner:
                return owner.user_login
        return None


def update_lock(user_login, package_name, owner_login=None, opening=False, session=None):
    """
    In most cases, this will be called when the package is already the active package for the user, who already
    has a lock on the package. But if the user is opening a package for the first time or switching to a different
    package, we will need to update the active package ID for the user.

    It would be preferable to have an open_package() function that would handle that part and would then call this
    function, but sqlite3 doesn't support nested transactions, so we can't do that. So, instead, we have some extra
    complexity in this function, but we still have an open_package() function; it calls this function with opening=True.

    The case where the user is opening a package for the first time or switching to a different package is signaled
    by setting opening=True. In that case, we require owner_login to be provided, i.e., not to be None. We need to
    know the owner_login so we can set the active package, creating a package record if necessary.

    In cases where opening==False, we just use the package_name for a sanity check, verifying that it matches the
    active package for the user.

    -----

    Get the user's active package. If its name doesn't match package_name, raise an exception.
    Just because the user has an active package doesn't mean they have a lock on it. They may have just opened it, or
    they may have opened it a long time ago and the lock has timed out.

    Check the lock status of the package.
    If the package is unlocked, lock it for the current user, initializing the timestamp.
        Note: we do this even if the package is not yet involved in a collaboration. This is done so that if a
        collaboration is created later, the package's lock status will be correct.
    If the current user already has a lock on the package, update the timestamp.
    If another user has a lock on the package, check to see if the lock has timed out.
        If not, raise a LockOwnedByAnotherUser exception.
        If so, remove the lock and lock the package for the current user. The user who had the lock will discover that
            the lock has been removed the next time they try to access the package.
    Return the lock.
    """

    logging.info('****************************************************************************************************')
    logging.info(f'update_lock: user_login={user_login}, package_name={package_name}, owner_login={owner_login}, opening={opening}')

    if opening:
        if not owner_login:
            raise exceptions.CollaborationDatabaseError('owner_login must be provided when opening a package')

    with db_session(session) as session:
        active_package = None

        user_id = get_user(user_login, create_if_not_found=True, session=session).user_id

        if opening:
            # If we are opening a package, we need to set the active package ID for the user, creating a package
            #  record if necessary.
            # Make sure the owner record exists.
            _ = get_user(owner_login, create_if_not_found=True, session=session)
            # If the user holds a lock, release it. We're switching to a different package.
            _release_lock_for_user(user_id, session=session)
            # Set the active package ID for the user.
            set_active_package(user_login, package_name, owner_login, session=session)

        user = get_user(user_login, create_if_not_found=True, session=session)
        active_package = _get_active_package(user.user_id)
        if active_package and active_package.package_name != package_name:
            # It's not clear what to do here. Should this case never arise? When does it?
            active_package = None
            # raise exceptions.CollaborationDatabaseError(
            #     f'update_lock: package_name {package_name} does not match active package name {active_package.package_name}')
        if not active_package:
            # If there is no active package ID, we assume the user is owner of the package. In the case of a
            #  collaborator, the active package will be set when the collaborator opens the package, since the
            #  only entry point for a collaborator to open a package is through the collaboration page.
            active_package = set_active_package(user_login, package_name, owner_login=user_login, session=session)

        # See if a lock exists for the package.
        lock = _get_lock(active_package.package_id)
        if lock:
            # If the lock exists, check to see if it's owned by the current user, i.e., the user on whose behalf
            # we're updating the lock.
            if lock.locked_by == user.user_id:
                # The lock is owned by the current user, so update the timestamp.
                # lock.timestamp = datetime.now(timezone.utc)
                lock.timestamp = datetime.now()
            else:
                # The lock is owned by another user, so check to see if it's timed out.
                # t1 = datetime.now(timezone.utc)
                t1 = datetime.now()
                t2 = lock.timestamp
                if (t1 - t2).total_seconds() > Config.COLLABORATION_LOCK_INACTIVITY_TIMEOUT_MINUTES * 60:
                    # The lock has timed out, so remove it and lock the package for the current user.
                    session.delete(lock)
                    _add_lock(active_package.package_id, user.user_id, session=session)
                else:
                    # The lock has not timed out, so raise an exception.
                    package_name = active_package.package_name
                    locked_by = display_name(_get_user(lock.locked_by).user_login)
                    message = f'Package {package_name} is currently locked by {locked_by}'
                    raise exceptions.LockOwnedByAnotherUser(message=message,
                                                            package_name=package_name,
                                                            user_name=locked_by)
        else:
            # The package is unlocked, so lock it.
            _add_lock(active_package.package_id, user.user_id, session=session)
        return lock


def open_package(user_login, package_name, owner_login=None, session=None):
    """
    open_package() is called when a user wants to open a package. If the package is available to open, the user gets the
    lock and the user's active package is set to the package. If the package is locked by another user, an exception is
    raised.
    """
    if not owner_login:
        owner_login = user_login

    with db_session(session) as session:
        return update_lock(user_login, package_name, opening=True, owner_login=owner_login, session=session)


def close_package(user_login, session=None):
    """
    close_package() is called when a user is done with the active package, i.e., when the package is closed or
    deleted or the user logs off. The user's active package is set to None and if a lock is held by the user it is
    released.
    """
    with db_session(session) as session:
        user_id = get_user(user_login, create_if_not_found=True, session=session).user_id
        active_package_id = _get_active_package_id(user_id)
        if active_package_id:
            release_lock(user_login, active_package_id, session=session)
        set_active_package_id(user_id, None, session=session)
        # Delete package records that aren't locked by another user or referenced
        # by a collaboration record.
        packages = Package.query.all()
        for package in packages:
            if not _get_lock(package.package_id) and not Collaboration.query.filter_by(package_id=package.package_id).first():
                try:
                    session.delete(package)
                except:
                    pass


def _get_lock(package_id):
    try:
        lock = Lock.query.filter_by(package_id=package_id).first()
    except Exception as exc:
        lock = None
    return lock


def _add_lock(package_id, locked_by, session=None):
    with db_session(session) as session:
        lock = _get_lock(package_id)
        if not lock:
            # lock = Lock(package_id=package_id, locked_by=locked_by, timestamp=datetime.now(timezone.utc))
            lock = Lock(package_id=package_id, locked_by=locked_by, timestamp=datetime.now())
            session.add(lock)
            session.flush()
        return lock


def remove_package(owner_login, package_name, session=None):
    # To be called when an ezEML document is deleted. Remove all records associated with the package.
    with db_session(session) as session:
        package = get_package(owner_login, package_name, session)
        if package:
            # Remove any collaborations associated with the package.
            collaborations = Collaboration.query.filter_by(package_id=package.package_id).all()
            for collaboration in collaborations:
                session.delete(collaboration)
            # Remove any locks associated with the package.
            lock = _get_lock(package.package_id)
            if lock:
                session.delete(lock)
            # Remove the package record.
            session.delete(package)


def remove_collaboration(collab_id, session=None):
    with db_session(session) as session:
        collaboration = Collaboration.query.filter_by(collab_id=collab_id).first()
        if collaboration:
            session.delete(collaboration)


def _remove_lock(package_id, session=None):
    with db_session(session) as session:
        lock = _get_lock(package_id)
        if lock:
            session.delete(lock)


def _release_lock_for_user(user_id, session=None):
    with db_session(session) as session:
        locks = Lock.query.filter_by(locked_by=user_id).all()
        for lock in locks:
            session.delete(lock)


def release_acquired_lock(lock, session=None):
    with db_session(session) as session:
        _remove_lock(lock.package_id, session=session)


def release_lock(user_login, package_id, session=None):
    """
    release_lock() is called to release a lock on a package. It is called by close_package(), but it also may be
    called via a link from the collaboration page to release a lock that is no longer needed, without closing the
    package. The active_package_id is not set to None in this case since the package is still open.
    """
    with db_session(session) as session:
        lock = _get_lock(package_id)
        user_id = get_user(user_login, create_if_not_found=True, session=session).user_id
        if lock and lock.locked_by == user_id:
            _remove_lock(package_id, session=session)


def set_active_package_id(user_id, package_id, session=None):
    with db_session(session) as session:
        user = User.query.filter_by(user_id=user_id).first()
        user.active_package = package_id


def _get_active_package_id(user_id):
    user = User.query.filter_by(user_id=user_id).first()
    if not user:
        raise exceptions.CollaborationDatabaseError('_get_active_package_id: User does not exist')
    return user.active_package_id


def get_active_package(user_login, session=None):
    with db_session(session) as session:
        user_id = get_user(user_login, create_if_not_found=True, session=session).user_id
        package_id = _get_active_package_id(user_id)
        if package_id:
            return Package.query.filter_by(package_id=package_id).first()
        else:
            return None


def get_user(user_login, create_if_not_found=False, session=None):
    with db_session(session) as session:
        user = User.query.filter_by(user_login=user_login).first()
        if not user and create_if_not_found:
            user = add_user(user_login, session=session)
        return user


def _get_user(user_id):
    user = User.query.filter_by(user_id=user_id).first()
    return user


def add_user(user_login, session=None):
    with db_session(session) as session:
        user = get_user(user_login, session=session)
        if not user:
            user = User(user_login=user_login)
            session.add(user)
            session.flush()
        return user


def get_package_by_id(package_id):
    # This function uses the database id, but is intended to be called from outside the collaboration module, hence
    # no preceding underscore in the name. This function is used in handling a request to open a package by a
    # collaborator.
    package = Package.query.filter_by(package_id=package_id).first()
    return package


def get_package_owner(package_id):
    package = get_package_by_id(package_id)
    if package:
        return _get_user(package.owner_id)


def _get_package(owner_id, package_name, create_if_not_found=False, session=None):
    with db_session(session) as session:
        package = Package.query.filter_by(owner_id=owner_id, package_name=package_name).first()
        if not package and create_if_not_found:
            package = _add_package(owner_id, package_name, session=session)
        return package


def get_package(owner_login, package_name, create_if_not_found=False, session=None):
    with db_session(session) as session:
        owner_id = get_user(owner_login, create_if_not_found=True, session=session).user_id
        return _get_package(owner_id, package_name, create_if_not_found, session=session)


def _add_package(owner_id, package_name, session=None):
    with db_session(session) as session:
        package = _get_package(owner_id, package_name, session=session)
        if not package:
            package = Package(owner_id=owner_id, package_name=package_name)
            session.add(package)
            session.flush()
        return package


def get_collaboration(collaborator_id, package_id):
    collaboration = Collaboration.query.filter_by(collaborator_id=collaborator_id, package_id=package_id).first()
    return collaboration


def get_owner_login(package_id):
    package = get_package_by_id(package_id)
    if package:
        return _get_user(package.owner_id).user_login


def _add_collaboration(owner_id, collaborator_id, package_id, status=None, session=None):
    with db_session(session) as session:
        collaboration = get_collaboration(collaborator_id, package_id)
        if not collaboration:
            collaboration = Collaboration(owner_id=owner_id, collaborator_id=collaborator_id, package_id=package_id)
            session.add(collaboration)
            session.flush()
        if status:
            _set_collaboration_status(collaboration.collab_id, status, session=session)
        return collaboration


def _get_collaboration_status(collab_id):
    collaboration_status = CollaborationStatus.query.filter_by(collab_id=collab_id).first()
    return collaboration_status


def _set_collaboration_status(collab_id, status, session=None):
    with db_session(session) as session:
        collaboration_status = db.session.query(CollaborationStatus).filter_by(collab_id=collab_id).first()
        if not collaboration_status:
            collaboration_status = CollaborationStatus(collab_id=collab_id, status=status)
            session.add(collaboration_status)
            session.flush()
        if collaboration_status.status != status:
            collaboration_status.status = status
        return collaboration_status


# For development and debugging
def get_collaboration_output():
    with db_session() as session:
        collaboration_list = []
        collaborations = Collaboration.query.filter_by().all()
        for collaboration in collaborations:
            collaboration_list.append(CollaborationOutput(
                collab_id=collaboration.collab_id,
                owner_id=collaboration.owner_id,
                collaborator_id=collaboration.collaborator_id,
                package_id=collaboration.package_id))
        return collaboration_list


# For development and debugging
def get_user_output():
    with db_session() as session:
        user_list = []
        users = User.query.filter_by().all()
        for user in users:
            user_list.append(UserOutput(
                user_id=user.user_id,
                user_login=user.user_login,
                active_package_id=user.active_package_id))
        return user_list


# For development and debugging
def get_package_output():
    with db_session() as session:
        package_list = []
        packages = Package.query.filter_by().all()
        for package in packages:
            owner = User.query.filter_by(user_id=package.owner_id).first()
            if owner:
                owner = owner.user_login
            package_list.append(PackageOutput(
                package_id=package.package_id,
                owner=owner,
                package_name=package.package_name))
        return package_list


# For debugging
def get_package_output():
    with db_session() as session:
        package_list = []
        packages = Package.query.filter_by().all()
        for package in packages:
            owner = User.query.filter_by(user_id=package.owner_id).first()
            if owner:
                owner_login = owner.user_login
            else:
                owner_login = None
            package_list.append(PackageOutput(
                package_id=package.package_id,
                owner_login=owner_login,
                package_name=package.package_name))
        return package_list


# For development and debugging
def get_lock_output():
    with db_session() as session:
        lock_list = []
        locks = Lock.query.filter_by().all()
        for lock in locks:
            owner = User.query.filter_by(user_id=lock.owner_id).first()
            if owner:
                owner = owner.user_login
            package = Package.query.filter_by(package_id=lock.package_id).first()
            if package:
                package_name = package.package_name
            else:
                package_name = None
            locked_by = User.query.filter_by(user_id=lock.locked_by).first()
            if locked_by:
                locked_by = locked_by.user_login
            lock_list.append(LockOutput(
                owner=display_name(owner),
                package_name=package_name,
                locked_by=display_name(locked_by),
                timestamp=lock.timestamp))
        return lock_list


# Returns the list of collaborations for a given user, to be display on the Collaboration page
def get_collaborations(user_login):
    if not user_login:
        return []
    # Get all collaborations where the user is the owner or the collaborator
    collaboration_records = []
    with db_session() as session:
        # First, where the user is owner
        user_id = get_user(user_login, create_if_not_found=True, session=session).user_id
        collaborations = Collaboration.query.filter_by(owner_id=user_id).all()
        # Then, where the user is collaborator
        collaborations.extend(Collaboration.query.filter_by(collaborator_id=user_id).all())
        for collaboration in collaborations:
            owner_id = collaboration.owner_id
            status = _get_collaboration_status(collaboration.collab_id)
            if status:
                status = status.status
            else:
                status = None
            lock = _get_lock(collaboration.package_id)
            try:
                collaboration_records.append(CollaborationRecord(
                    collab_id=collaboration.collab_id,
                    package_id=collaboration.package_id,
                    package=collaboration.package.package_name,
                    owner_id=owner_id,
                    owner_login=collaboration.owner.user_login,
                    owner_name='',
                    collaborator_id=collaboration.collaborator_id,
                    collaborator_login=collaboration.collaborator.user_login,
                    collaborator_name='',
                    status=status,
                    locked_by_id=lock.locked_by if lock else None,
                    locked_by='',
                    action=''))
            except Exception as e:
                pass
        return sorted(collaboration_records)


# Returns the list of invitations made be a given user, to be display on the Collaboration page
def get_invitations(user_login):
    if not user_login:
        return []
    invitation_records = []
    with db_session() as session:
        # First, where the user is owner
        user_id = get_user(user_login, create_if_not_found=True, session=session).user_id
        invitations = Invitation.query.filter_by(inviter_id=user_id).all()
        for invitation in invitations:
            try:
                invitation_records.append(InvitationRecord(
                    invitation_id=invitation.invitation_id,
                    package_id=invitation.package_id,
                    package=invitation.package.package_name,
                    invitee_name=invitation.invitee_name,
                    invitee_email=invitation.invitee_email,
                    date=invitation.date.strftime('%Y-%m-%d'),
                    action=''
                ))
            except Exception as e:
                pass
        return sorted(invitation_records)


def get_invitation_by_code(invitation_code):
    # with db_session() as session:
    invitation = Invitation.query.filter_by(invitation_code=invitation_code).first()
    if not invitation:
        raise exceptions.InvitationNotFound(f'Invitation with code {invitation_code} not found')
    return invitation


def generate_invitation_code():
    ok = False
    while not ok:
        # Make a random 4-letter code, but limit to consonants to avoid offensive words
        code = ''.join(random.choices("BCDFGHJKLMNPQRSTVWXYZ", k=4))
        # Check to make sure the invitation code is unique
        invitation = Invitation.query.filter_by(invitation_code=code).first()
        if not invitation:
            ok = True
    return code


def accept_invitation(user_login, invitation_code, session=None):
    with db_session(session) as session:
        # Find the invitation
        invitation = Invitation.query.filter_by(invitation_code=invitation_code).first()
        if not invitation:
            raise exceptions.InvitationNotFound(f'Invitation with code {invitation_code} not found')

        # Find the user
        user = get_user(user_login, create_if_not_found=True)
        if invitation.inviter_id == user.user_id:
            raise exceptions.InvitationBeingAcceptedByOwner(f'Invitation with code {invitation_code} cannot be accepted by the inviter')
        # Create the collaboration
        owner_id = invitation.inviter_id
        collaborator_id = user.user_id
        package_id = invitation.package_id
        collaboration = _add_collaboration(owner_id, collaborator_id, package_id, session=session)
        # Remove the invitation
        session.delete(invitation)
        return collaboration


def remove_invitation(invitation_code):
    invitation = Invitation.query.filter_by(invitation_code=invitation_code).first()
    if invitation:
        with db_session() as session:
            session.delete(invitation)
        return True
    return False


def cancel_invitation(invitation_id):
    invitation = Invitation.query.filter_by(invitation_id=invitation_id).first()
    if invitation:
        with db_session() as session:
            session.delete(invitation)
        return True
    return False


def create_invitation(filename, inviter_name, inviter_email, invitee_name, invitee_email, session=None):
    with db_session(session) as session:
        inviter_login = current_user.get_user_login()
        active_package = get_active_package(inviter_login, session=session)
        if not active_package:  # TODO - Error handling
            active_package = set_active_package(inviter_login, filename, session=session)
        package_id = active_package.package_id

        invitation_code = generate_invitation_code()
        inviter_id = get_user(inviter_login).user_id
        invitation = Invitation(inviter_id=inviter_id,
                                inviter_name=inviter_name,
                                inviter_email=inviter_email,
                                invitee_name=invitee_name,
                                invitee_email=invitee_email,
                                package_id=package_id,
                                invitation_code=invitation_code,
                                date=date.today())

        session.add(invitation)
        session.flush()
        return invitation_code


def init_db():
    db.create_all()


def cleanup_db(session=None):
    with db_session(session) as session:
        # Remove locks that have timed out. This shouldn't be necessary, but it will help guard against gradual
        # accumulation of zombie locks. For the removed locks, clear the active_package_id for the user who held the
        # lock.
        locks = Lock.query.all()
        for lock in locks:
            t1 = datetime.now()
            t2 = lock.timestamp
            if (t1 - t2).total_seconds() > Config.COLLABORATION_LOCK_INACTIVITY_TIMEOUT_MINUTES * 60:
                # The lock has timed out
                # Clear the active_package_id for the user who held the lock
                _set_active_package_id(lock.locked_by, None, session=session)
                # Remove the lock
                session.delete(lock)
        # Remove packages that have no locks and no collaborations
        packages = Package.query.all()
        for package in packages:
            locks = Lock.query.filter_by(package_id=package.package_id).all()
            if not locks:
                collaborations = Collaboration.query.filter_by(package_id=package.package_id).all()
                if not collaborations:
                    session.delete(package)
        # Remove users that are not referenced by any packages, collaborations, or locks
        users = User.query.all()
        for user in users:
            packages = Package.query.filter_by(owner_id=user.user_id).all()
            if not packages:
                collaborations = Collaboration.query.filter_by(owner_id=user.user_id).all()
                if not collaborations:
                    collaborations = Collaboration.query.filter_by(collaborator_id=user.user_id).all()
                    if not collaborations:
                        locks = Lock.query.filter_by(locked_by=user.user_id).all()
                        if not locks:
                            session.delete(user)


if __name__ == '__main__':
    # create_collaborations_db()
    pass