import random
import string

import sqlalchemy
from sqlalchemy.types import TypeDecorator, String

from dataclasses import dataclass
from datetime import datetime, date
from enum import Enum, auto
from flask_login import current_user

from webapp import db
from webapp.config import Config

from webapp.views.collaborations.model import (
    Collaboration,
    CollaborationStatus,
    GroupCollaboration,
    GroupLock,
    Invitation,
    Lock,
    Package,
    User,
    UserGroup,
    UserGroupMembership
)

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


class CollaborationCase(Enum):
    LOGGED_IN_USER_IS_OWNER_COLLABORATOR_IS_INDIVIDUAL = auto()
    LOGGED_IN_USER_IS_OWNER_COLLABORATOR_IS_GROUP = auto()
    LOGGED_IN_USER_IS_INDIVIDUAL_COLLABORATOR = auto()
    LOGGED_IN_USER_IS_GROUP_COLLABORATOR = auto()


class LockStatus(Enum):
    NOT_LOCKED = auto()
    LOCKED_BY_LOGGED_IN_USER = auto()
    LOCKED_BY_ANOTHER_USER = auto()
    LOCKED_BY_GROUP_ONLY = auto()
    LOCKED_BY_GROUP_AND_LOGGED_IN_USER = auto()
    LOCKED_BY_GROUP_AND_ANOTHER_USER = auto()


class CollaborationAction(Enum):
    APPLY_GROUP_LOCK = auto()
    END_COLLABORATION = auto()
    END_GROUP_COLLABORATION = auto()
    OPEN = auto()
    RELEASE_GROUP_LOCK = auto()
    RELEASE_INDIVIDUAL_LOCK = auto()


def display_name(user_login: str) -> str:
    try:
        if user_login:
            return user_login[:user_login.rfind('-')]
        else:
            return ''
    except:
        ijk = 1
        return ''


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

        # See if a group lock exists for the package.
        group_lock = _get_group_lock(active_package.package_id)
        if group_lock:
            # Check if the current user is a member of the group.
            if not is_group_member(user_login, group_lock.locked_by, session=session):
                # The lock has not timed out, so raise an exception.
                package_name = active_package.package_name
                locked_by = display_name(_get_user(group_lock.locked_by).user_login)
                message = f'Package {package_name} is currently locked by {locked_by}'
                raise exceptions.LockOwnedByAGroup(message=message,
                                                   package_name=package_name,
                                                   user_name=locked_by)

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
        set_active_package_id(user_id, sqlalchemy.null(), session=session)
        session.flush()
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


def remove_group_collaboration(group_collab_id, session=None):
    with db_session(session) as session:
        group_collaboration = _get_group_collaboration(group_collab_id)
        if group_collaboration:
            # We delete the individual collaborations first, then the group collaboration.
            package_id = group_collaboration.package_id
            for member in get_group_members(group_collaboration.user_group_id, session=session):
                member_user = _get_user(member.user_id)
                collaboration = get_collaboration(member_user.user_id, package_id)
                if collaboration:
                    remove_collaboration(collaboration.collab_id, session=session)
            # Delete any locks associated with the package.
            _remove_lock(package_id, session=session)
            release_group_lock(package_id, session=session)
            session.delete(group_collaboration)


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


def _get_group_lock(package_id):
    try:
        lock = GroupLock.query.filter_by(package_id=package_id).first()
    except Exception as exc:
        lock = None
    return lock


def add_group_lock(package_id, locked_by, session=None):
    with db_session(session) as session:
        group_lock = _get_group_lock(package_id)
        if not group_lock:
            group_lock = GroupLock(package_id=package_id, locked_by=locked_by)
            session.add(group_lock)
            session.flush()
        # Remove individual lock if locked by a non-member of the group.
        lock = _get_lock(package_id)
        if lock:
            in_group = False
            members = get_group_members(group_lock.locked_by, session=session)
            for member in members:
                if member.user_id == lock.locked_by:
                    in_group = True
                    break
            if not in_group:
                _remove_lock(package_id, session=session)
        return group_lock


def _remove_group_lock(package_id, session=None):
    with db_session(session) as session:
        lock = _get_group_lock(package_id)
        if lock:
            session.delete(lock)


def release_group_lock(package_id, session=None):
    with db_session(session) as session:
        group = GroupCollaboration.query.filter_by(package_id=package_id).first()
        if group:
            _remove_group_lock(package_id, session=session)
            for member in get_group_members(group.user_group_id, session=session):
                member_user = _get_user(member.user_id)
                release_lock(member_user.user_login, package_id, session=session)


def set_active_package_id(user_id, package_id, session=None):
    with db_session(session) as session:
        user = User.query.filter_by(user_id=user_id).first()
        user.active_package_id = package_id


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


def change_active_package_account(package_name, session=None):
    with db_session(session) as session:
        user_login = current_user.get_user_login()
        logged_in_user_id = get_user(user_login, create_if_not_found=True, session=session).user_id
        current_active_package = get_active_package(user_login, session=session)
        if current_active_package:
            if current_active_package.owner_id == logged_in_user_id:
                return
            # release_lock(user_login, current_active_package.package_id, session=session)

        new_package = get_package(user_login,
                                  package_name,
                                  create_if_not_found=True,
                                  session=session)

        set_active_package_id(logged_in_user_id, new_package.package_id, session=session)
        current_user.set_file_owner(display_name(user_login))
        session.flush()


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
            collaboration = Collaboration(owner_id=owner_id,
                                          collaborator_id=collaborator_id,
                                          package_id=package_id,
                                          date_created=datetime.today().date())
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


def get_groups_for_user(user_id, session=None):
    groups = []
    with db_session(session) as session:
        group_memberships = UserGroupMembership.query.filter_by(user_id=user_id).all()
        for group_membership in group_memberships:
            user_group = UserGroup.query.filter_by(user_group_id=group_membership.user_group_id).first()
            if user_group:
                groups.append(user_group)
    return groups


def get_locked_by_id(package_id, session=None):
    with db_session(session) as session:
        lock = _get_group_lock(package_id)
        if not lock:
            lock = _get_lock(package_id)
        if lock:
            return lock.locked_by


def get_lock_status(package_id, session=None):
    group_locked_by_id = None
    individual_locked_by_id = None
    with db_session(session) as session:
        group_lock = _get_group_lock(package_id)
        if group_lock:
            group_locked_by_id = group_lock.locked_by
        individual_lock = _get_lock(package_id)
        if individual_lock:
            individual_locked_by_id = individual_lock.locked_by
    return group_locked_by_id, individual_locked_by_id


def _calculate_lock_status(collaboration_case, logged_in_user_id, package_id, session=None):
    with db_session(session) as session:
        group_locked_by_id, individual_locked_by_id = get_lock_status(package_id, session=session)
        if not group_locked_by_id and not individual_locked_by_id:
            return LockStatus.NOT_LOCKED, None
        if individual_locked_by_id:
            if not group_locked_by_id:
                if individual_locked_by_id == logged_in_user_id:
                    return LockStatus.LOCKED_BY_LOGGED_IN_USER, individual_locked_by_id
                else:
                    return LockStatus.LOCKED_BY_ANOTHER_USER, individual_locked_by_id
            else:
                # There is a group lock. There are two cases...
                locked_by_id = individual_locked_by_id
                if collaboration_case == CollaborationCase.LOGGED_IN_USER_IS_OWNER_COLLABORATOR_IS_GROUP:
                    locked_by_id = group_locked_by_id
                if individual_locked_by_id == logged_in_user_id:
                    return LockStatus.LOCKED_BY_GROUP_AND_LOGGED_IN_USER, locked_by_id
                else:
                    return LockStatus.LOCKED_BY_GROUP_AND_ANOTHER_USER, locked_by_id
        else:
            # There is a group lock but no individual lock
            return LockStatus.LOCKED_BY_GROUP_ONLY, group_locked_by_id

        return None, None


def is_a_group_lock_status(lock_status):
    return lock_status in [LockStatus.LOCKED_BY_GROUP_ONLY,
                           LockStatus.LOCKED_BY_GROUP_AND_LOGGED_IN_USER,
                           LockStatus.LOCKED_BY_GROUP_AND_ANOTHER_USER]


def _calculate_actions(logged_in_user_id, user_id, collaboration_group, collaboration_case, lock_status, locked_by_id, session=None):
    with db_session(session) as session:
        actions = []
        user_id = str(user_id)

        if collaboration_case == CollaborationCase.LOGGED_IN_USER_IS_OWNER_COLLABORATOR_IS_INDIVIDUAL:
            if lock_status == LockStatus.NOT_LOCKED and user_id != logged_in_user_id:
                actions.append(CollaborationAction.OPEN)
            if lock_status == LockStatus.LOCKED_BY_LOGGED_IN_USER and locked_by_id == logged_in_user_id:
                actions.append(CollaborationAction.RELEASE_INDIVIDUAL_LOCK)
                actions.append(CollaborationAction.END_COLLABORATION)

        if collaboration_case == CollaborationCase.LOGGED_IN_USER_IS_OWNER_COLLABORATOR_IS_GROUP:
            if lock_status == LockStatus.LOCKED_BY_LOGGED_IN_USER:
                actions.append(CollaborationAction.RELEASE_INDIVIDUAL_LOCK)

        if collaboration_case == CollaborationCase.LOGGED_IN_USER_IS_INDIVIDUAL_COLLABORATOR:
            if lock_status == LockStatus.NOT_LOCKED:
                actions.append(CollaborationAction.OPEN)
            if lock_status == LockStatus.LOCKED_BY_LOGGED_IN_USER:
                actions.append(CollaborationAction.RELEASE_INDIVIDUAL_LOCK)
            if lock_status == LockStatus.LOCKED_BY_GROUP_AND_LOGGED_IN_USER:
                actions.append(CollaborationAction.RELEASE_INDIVIDUAL_LOCK)
                actions.append(CollaborationAction.END_GROUP_COLLABORATION)

        if collaboration_case == CollaborationCase.LOGGED_IN_USER_IS_GROUP_COLLABORATOR:
            if user_id.startswith('G'):
                # We're doing the entry for the group as a whole
                if collaboration_group in get_groups_for_user(logged_in_user_id, session=session):
                    if lock_status == LockStatus.NOT_LOCKED:
                        actions.append(CollaborationAction.APPLY_GROUP_LOCK)
                    else:
                        if is_a_group_lock_status(lock_status):
                            actions.append(CollaborationAction.RELEASE_GROUP_LOCK)
                            if locked_by_id == logged_in_user_id:
                                actions.append(CollaborationAction.END_GROUP_COLLABORATION)
                        elif lock_status == LockStatus.LOCKED_BY_LOGGED_IN_USER:
                            actions.append(CollaborationAction.APPLY_GROUP_LOCK)
            else:
                # Doing an entry for a group member
                if lock_status in [LockStatus.NOT_LOCKED, LockStatus.LOCKED_BY_GROUP_ONLY]:
                    if user_id == str(logged_in_user_id):
                        actions.append(CollaborationAction.OPEN)
                if lock_status in [LockStatus.LOCKED_BY_LOGGED_IN_USER, LockStatus.LOCKED_BY_GROUP_AND_LOGGED_IN_USER]:
                    if user_id == str(logged_in_user_id):
                        actions.append(CollaborationAction.RELEASE_INDIVIDUAL_LOCK)
        return actions


def get_group_collaborations(logged_in_user_id, logged_in_user_records_only=True, session=None):
    """
    Handling group collaborations:
    We build a list of collaboration records and a set of collaboration_ids to suppress because they are details
     of group membership and the user is not a member of the group.
    - Find group collaborations where the user is the package owner
        For each such collaboration, if the user is not a member of the group, we want to suppress the ordinary
        collaborations with members of the group
    - Find group collaborations where the user is a member
        First, find groups where the user is a member
        For each such group, find the group collaborations where the user is not the owner
    """
    collaboration_records = []
    collaborations_to_suppress = set()
    with db_session(session) as session:
        groups_for_user = get_groups_for_user(logged_in_user_id, session=session)

        # First, where the user is package owner
        group_collaborations = GroupCollaboration.query.filter_by(owner_id=logged_in_user_id).all()
        for group_collaboration in group_collaborations:
            # Is the user a member?
            if group_collaboration.user_group not in groups_for_user:
                # No, so we want to suppress the ordinary collaborations with members of the group
                # E.g., for users who are not EDI Curators, we don't display the individual collaborations
                # with the EDI Curators group
                for member in get_group_members(group_collaboration.user_group.user_group_id):
                    collaborations_to_suppress.add((group_collaboration.package_id, member.user_id))
            group_as_user = get_user(fake_login_for_group(group_collaboration.user_group.user_group_name),
                                     session=session)

            collaboration_case = CollaborationCase.LOGGED_IN_USER_IS_OWNER_COLLABORATOR_IS_GROUP
            lock_status, locked_by_id = _calculate_lock_status(collaboration_case,
                                                               logged_in_user_id,
                                                               group_collaboration.package_id,
                                                               session=session)
            actions = _calculate_actions(logged_in_user_id, group_as_user.user_id, group_collaboration.user_group,
                                         collaboration_case, lock_status, locked_by_id, session=session)
            collaboration_records.append(CollaborationRecord(
                collaboration_case=collaboration_case,
                lock_status=lock_status,
                actions=actions,
                collab_id=group_collaboration.group_collab_id,
                package_id=group_collaboration.package_id,
                package_name=group_collaboration.package.package_name,
                owner_id=group_collaboration,
                owner_login=group_collaboration.owner.user_login,
                owner_name='',
                collaborator_id=group_as_user.user_id,
                collaborator_login=group_as_user.user_login,
                collaborator_name='',
                date_created=group_collaboration.date_created.strftime('%Y-%m-%d'),
                locked_by_id=locked_by_id,
                locked_by='',
                status_str='',
                action_str=''))

        # Second, where the user is a member. Here, we want to add each group member as a collaborator
        groups = get_groups_for_user(logged_in_user_id, session=session)
        for group in groups:
            group_collaborations = GroupCollaboration.query.filter_by(user_group_id=group.user_group_id).all()
            for group_collaboration in group_collaborations:
                if group_collaboration.owner_id != logged_in_user_id:
                    group_as_user = get_user(fake_login_for_group(group_collaboration.user_group.user_group_name),
                                             session=session)

                    collaboration_case = CollaborationCase.LOGGED_IN_USER_IS_GROUP_COLLABORATOR
                    lock_status, locked_by_id = _calculate_lock_status(collaboration_case, logged_in_user_id,
                                                                       group_collaboration.package_id, session=session)
                    actions = _calculate_actions(logged_in_user_id, f'G{group_as_user.user_id}',
                                                 group_collaboration.user_group,
                                                 collaboration_case, lock_status, locked_by_id, session=session)
                    collaboration_records.append(CollaborationRecord(
                        collaboration_case=collaboration_case,
                        lock_status=lock_status,
                        actions=actions,
                        collab_id=group_collaboration.group_collab_id,
                        package_id=group_collaboration.package_id,
                        package_name=group_collaboration.package.package_name,
                        owner_id=group_collaboration,
                        owner_login=group_collaboration.owner.user_login,
                        owner_name='',
                        collaborator_id=group_as_user.user_id,
                        collaborator_login=group_as_user.user_login,
                        collaborator_name='',
                        date_created=group_collaboration.date_created.strftime('%Y-%m-%d'),
                        locked_by_id=locked_by_id,
                        locked_by='',
                        status_str='',
                        action_str=''))

                    members = get_group_members(group_collaboration.user_group.user_group_id, session=session)
                    lock = _get_lock(group_collaboration.package_id)
                    for member in members:
                        if logged_in_user_records_only and member.user_id != logged_in_user_id:
                            continue
                        collaboration = get_collaboration(member.user_id, group_collaboration.package_id)
                        # We don't want the collaboration to show up twice when we handle individual collaborations
                        collaborations_to_suppress.add((group_collaboration.package_id, member.user_id))

                        collaboration_case = CollaborationCase.LOGGED_IN_USER_IS_GROUP_COLLABORATOR
                        lock_status, locked_by_id = _calculate_lock_status(collaboration_case,
                                                                           logged_in_user_id,
                                                                           group_collaboration.package_id,
                                                                           session=session)
                        actions = _calculate_actions(logged_in_user_id, member.user_id,
                                                     group_collaboration.user_group,
                                                     collaboration_case, lock_status, locked_by_id, session=session)
                        collaboration_records.append(CollaborationRecord(
                            collaboration_case=collaboration_case,
                            lock_status=lock_status,
                            actions=actions,
                            collab_id=group_collaboration.group_collab_id,
                            package_id=group_collaboration.package_id,
                            package_name=group_collaboration.package.package_name,
                            owner_id=group_collaboration,
                            owner_login=group_collaboration.owner.user_login,
                            owner_name='',
                            collaborator_id=member.user_id,
                            collaborator_login=get_member_login(member),
                            collaborator_name='',
                            date_created=group_collaboration.date_created.strftime('%Y-%m-%d'),
                            locked_by_id=locked_by_id,
                            locked_by='',
                            status_str='',
                            action_str=''))

    return collaboration_records, collaborations_to_suppress


# Returns the list of collaborations for a given user, to be displayed on the Collaboration page
def get_collaborations(user_login):
    if not user_login:
        return []
    # Get all collaborations where the user is the owner or the collaborator
    with db_session() as session:
        logged_in_user_id = get_user(user_login, create_if_not_found=True, session=session).user_id
        # Get group collaborations involving this user
        collaboration_records, collaborations_to_suppress = get_group_collaborations(logged_in_user_id, session=session)
        # Now get the ordinary collaborations, adding them to the collaboration_records list
        # First, where the user is owner
        collaborations = Collaboration.query.filter_by(owner_id=logged_in_user_id).all()
        annotated_collaborations = []
        for collaboration in collaborations:
            annotated_collaborations.append((collaboration, CollaborationCase.LOGGED_IN_USER_IS_OWNER_COLLABORATOR_IS_INDIVIDUAL))
        # Then, where the user is collaborator
        collaborations = Collaboration.query.filter_by(collaborator_id=logged_in_user_id).all()
        for collaboration in collaborations:
            annotated_collaborations.append((collaboration, CollaborationCase.LOGGED_IN_USER_IS_INDIVIDUAL_COLLABORATOR))
        for collaboration, collaboration_case in annotated_collaborations:
            if (collaboration.package_id, collaboration.collaborator_id) in collaborations_to_suppress:
                continue
            owner_id = collaboration.owner_id

            locked_by = None
            lock = _get_lock(collaboration.package_id)
            # If the lock has timed out, remove it. We do this here because a collaborator cannot open a locked package
            #  and has no way to remove the lock.
            if lock:
                t1 = datetime.now()
                t2 = lock.timestamp
                if (t1 - t2).total_seconds() > Config.COLLABORATION_LOCK_INACTIVITY_TIMEOUT_MINUTES * 60:
                    # The lock has timed out, so remove it
                    session.delete(lock)
                else:
                    locked_by = lock.locked_by

            lock_status, locked_by_id = _calculate_lock_status(collaboration_case, logged_in_user_id,
                                                               collaboration.package_id, session=session)
            actions = _calculate_actions(logged_in_user_id, collaboration.collaborator_id, None,
                                         collaboration_case, lock_status, locked_by_id, session=session)

            try:
                collaboration_records.append(CollaborationRecord(
                    collaboration_case=collaboration_case,
                    lock_status=lock_status,
                    actions=actions,
                    collab_id=collaboration.collab_id,
                    package_id=collaboration.package_id,
                    package_name=collaboration.package.package_name,
                    owner_id=owner_id,
                    owner_login=collaboration.owner.user_login,
                    owner_name='',
                    collaborator_id=collaboration.collaborator_id,
                    collaborator_login=collaboration.collaborator.user_login,
                    collaborator_name='',
                    date_created=collaboration.date_created.strftime('%Y-%m-%d'),
                    locked_by_id=locked_by,
                    locked_by='',
                    status_str='',
                    action_str=''))
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


def get_user_group(user_group_name, create_if_not_found=True, session=None):
    with db_session(session) as session:
        user_group = UserGroup.query.filter_by(user_group_name=user_group_name).first()
        if not user_group and create_if_not_found:
            user_group = add_user_group(user_group_name, session=session)
        return user_group


def add_user_group(user_group_name, session=None):
    with db_session(session) as session:
        user_group = get_user_group(user_group_name, create_if_not_found=False, session=session)
        if not user_group:
            user_group = UserGroup(user_group_name=user_group_name)
            session.add(user_group)
            session.flush()
        return user_group


def get_user_group_membership(user_group_id, user_id, create_if_not_found=False, session=None):
    with db_session(session) as session:
        user_group_membership = UserGroupMembership.query.filter_by(user_group_id=user_group_id, user_id=user_id).first()
        if not user_group_membership and create_if_not_found:
            user_group_membership = UserGroupMembership(user_group_id=user_group_id, user_id=user_id)
            session.add(user_group_membership)
        return user_group_membership


def _get_group_collaboration(group_collab_id):
    group_collaboration = GroupCollaboration.query.filter_by(group_collab_id=group_collab_id).first()
    return group_collaboration


def get_group_collaboration(user_group_id, package_id):
    group_collaboration = GroupCollaboration.query.filter_by(user_group_id=user_group_id, package_id=package_id).first()
    return group_collaboration


def get_group_members(user_group_id, session=None):
    with db_session(session) as session:
        user_group_memberships = UserGroupMembership.query.filter_by(user_group_id=user_group_id).all()
        return user_group_memberships


def is_group_member(user_login, user_group_id, session=None):
    with db_session(session) as session:
        user = get_user(user_login, session=session)
        if user:
            user_id = user.user_id
            user_group_membership = UserGroupMembership.query.filter_by(user_id=user_id, user_group_id=user_group_id).first()
            return user_group_membership is not None
        return False


def is_edi_curator(user_login, session=None):
    with db_session(session) as session:
        curator_group = get_user_group("EDI Curators", create_if_not_found=False, session=session)
        if curator_group:
            return is_group_member(user_login, curator_group.user_group_id, session=session)
        return False


def package_is_under_edi_curation(package_id, session=None):
    with db_session(session) as session:
        curator_group = get_user_group("EDI Curators", create_if_not_found=False, session=session)
        if curator_group:
            group_collaboration = get_group_collaboration(curator_group.user_group_id, package_id)
            return group_collaboration is not None
        return False


def get_member_login(member):
    return _get_user(member.user_id).user_login


def add_group_collaboration(user_login, user_group_name, package_name, session=None):
    with db_session(session) as session:
        user = get_user(user_login, session=session)
        if not user:
            raise exceptions.UserNotFound(f'User {user_login} not found')
        owner_id = user.user_id
        package = _get_package(owner_id, package_name, create_if_not_found=False, session=session)
        if not package or package.owner_id != owner_id:
            raise exceptions.UserIsNotTheOwner(f'User {user_login} is not the owner of package {package_name}')

        user_group = get_user_group(user_group_name, session=session)
        group_collaboration = get_group_collaboration(user_group.user_group_id, package.package_id)
        if group_collaboration:
            raise exceptions.CollaboratingWithGroupAlready(
                f'Group collaboration already exists for group {user_group_name} and package {package_name}')

        group_collaboration = GroupCollaboration(owner_id=owner_id,
                                                 user_group_id=user_group.user_group_id,
                                                 package_id=package.package_id,
                                                 date_created=datetime.today().date())

        session.add(group_collaboration)
        session.flush()
        # Add all the members of the group as collaborators
        user_group_memberships = get_group_members(user_group.user_group_id, session=session)
        for user_group_membership in user_group_memberships:
            if owner_id != user_group_membership.user_id:
                _add_collaboration(owner_id, user_group_membership.user_id, package.package_id, session=session)
        return group_collaboration


def init_db():
    db.create_all()
    init_groups()
    # test_stub()


def fake_login_for_group(user_group_name):
    # We prepend a null character to the group name to ensure that it is not a valid login and to put it ahead
    # of group members in the sort order for display purposes
    return "\0" + user_group_name + "-group_collaboration"


def init_groups():
    with db_session() as session:
        groups = Config.COLLABORATION_GROUPS
        for user_group_name in groups.keys():
            # We want a user representing each group so that we can add them as collaborators
            _ = add_user(user_login=fake_login_for_group(user_group_name), session=session)
        for user_group_name, members in groups.items():
            user_group = add_user_group(user_group_name=user_group_name, session=session)
            for member in members:
                user = get_user(member, create_if_not_found=True, session=session)
                user_group_membership = get_user_group_membership(user_group_id=user_group.user_group_id,
                                                                  user_id=user.user_id,
                                                                  create_if_not_found=True,
                                                                  session=session)


def save_backup_is_disabled():
    active_package_id = None
    user_login = current_user.get_user_login()
    if user_login:
        active_package = get_active_package(user_login)
        if active_package:
            active_package_id = active_package.package_id
    # See if the active package is in a group collaboration with EDI Curators
    return not package_is_under_edi_curation(active_package_id)


def test_stub():
    with db_session() as session:
        # Add user EDI
        edi_user = add_user("EDI-1a438b985e1824a5aa709daa1b6e12d2", session=session)
        jide_user = add_user("jide-7a03c1e6f4528a6f9c4b1ae3cec24b39", session=session)
        curation_team = get_user_group("EDI Curators", create_if_not_found=False, session=session)
        # Create three packages, two owned by EDI, one owned by jide
        package_1 = get_package("EDI-1a438b985e1824a5aa709daa1b6e12d2", "edi.1.1", create_if_not_found=True, session=session)
        package_2 = get_package("EDI-1a438b985e1824a5aa709daa1b6e12d2", "edi.2.2", create_if_not_found=True, session=session)
        package_3 = get_package("jide-7a03c1e6f4528a6f9c4b1ae3cec24b39", "A sample data package",
                                create_if_not_found=True, session=session)
        # Create a collaboration between EDI and jide for the package owned by jide
        _add_collaboration(jide_user.user_id, edi_user.user_id, package_3.package_id, session=session)
        # Create a collaboration between EDI and jide for a package owned by EDI
        _add_collaboration(edi_user.user_id, jide_user.user_id, package_1.package_id, session=session)
        # Create a group collaboration between EDI and EDI Curation Team for the other package owned by EDI
        try:
            group_collaboration_1 = add_group_collaboration(edi_user.user_login, "EDI Curators", package_2.package_name, session=session)
        except Exception as e:
            pass
        # add_group_lock(package_2.package_id, group_collaboration_1.group_collab_id, session=session)


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