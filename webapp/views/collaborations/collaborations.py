"""
This module contains helper functions for accessing and manipulating the collaborations database.
"""
import os
import random
import string

import sqlalchemy
from sqlalchemy.types import TypeDecorator, String
from urllib.parse import urlparse

from dataclasses import dataclass
from datetime import datetime, date
from enum import Enum, auto
from flask import request
from flask_login import current_user

from webapp import db
from webapp.config import Config
import webapp.mimemail as mimemail

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
    GroupCollaborationOutput,
    LockOutput,
    GroupLockOutput,
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
    """
    Given a user login, return the display name for the user. If the user is not found, return an empty string.
    """
    try:
        if user_login:
            return user_login[:user_login.rfind('-')]
        else:
            return ''
    except:
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
        # If we are changing the active package for the user, we need to release the lock on the old active package.
        if user.active_package_id != package.package_id:
            lock = _get_lock(user.active_package_id)
            if lock and lock.locked_by == user.user_id:
                _remove_lock(user.active_package_id, session=session)
        user.active_package_id = package.package_id
    return package


def _set_active_package_id(user_id, package_id, session=None):
    """
    Set the active package ID for the user.
    This should only be called by the lock handling code. The user is assumed to exist.
    """
    with db_session(session) as session:
        user = _get_user(user_id)
        user.active_package_id = package_id


def _get_active_package(user_id):
    """
    Get the active package ID for the user, if any. If the user has no active package, return None.
    This should only be called by the lock handling code. The user is assumed to exist.
    """
    user = _get_user(user_id)
    active_package_id = user.active_package_id
    if active_package_id:
        return Package.query.get(active_package_id)
    else:
        return None


def get_active_package(user_login, session=None):
    """
    Get the active package for the user, if any. If the user has no active package, return None.
    If the user is not found, create the user.
    """
    with db_session(session) as session:
        user = get_user(user_login, create_if_not_found=True, session=session)
        active_package_id = user.active_package_id
        if active_package_id:
            return Package.query.get(active_package_id)
        else:
            return None


def get_active_package_owner_login(user_login, session=None):
    """
    Get the active package for the user, if any. If the user has an active package, get the owner login for the
    package. If the user has no active package, return None.
    If the user is not found, create the user.
    """
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

    # logging.info('****************************************************************************************************')
    # logging.info(f'update_lock: user_login={user_login}, package_name={package_name}, owner_login={owner_login}, opening={opening}')

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
            # This case arises, for example, when using Manage Data Packages to delete a package. It's different from
            #  the usual case where the user has the package open before deleting it.
            # logger.info(f'update_lock: package_name {package_name} does not match active package name {active_package.package_name}')
            active_package = None
        if not active_package:
            if not owner_login:
                # If there is no active package ID, we assume the user is owner of the package. In the case of a
                #  collaborator, the active package will be set when the collaborator opens the package, since the
                #  only entry point for a collaborator to open a package is through the collaboration page.
                active_package = set_active_package(user_login, package_name, owner_login=user_login, session=session)
            else:
                active_package = set_active_package(user_login, package_name, owner_login=owner_login, session=session)

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
                    _remove_lock(active_package.package_id, session=session)
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


def cull_locks(session=None):
    """
    cull_locks() is called periodically (by init_session_vars) to remove locks that have timed out.
    Otherwise, locks can accumulate if a user opens a package and then closes the browser without closing the package.
    """
    with db_session(session) as session:
        # t1 = datetime.now(timezone.utc)
        t1 = datetime.now()
        locks = session.query(Lock).all()
        for lock in locks:
            t2 = lock.timestamp
            if (t1 - t2).total_seconds() > Config.COLLABORATION_LOCK_INACTIVITY_TIMEOUT_MINUTES * 60:
                try:
                    logger.info(f'cull_locks: removing lock... lock_id={lock.lock_id}, package_id={lock.package_id}, locked_by={lock.locked_by}, timestamp={lock.timestamp}')
                    _remove_lock(lock.package_id, session=session)
                except Exception as exc:
                    logger.info(f'cull_locks: exception removing lock... lock_id={lock.lock_id}, exc={exc}')


def cull_packages(session=None):
    """
    Delete package records that aren't locked by a user or group or referenced by a collaboration record, invitation,
    or active package ID. This prevents the list of packages from growing indefinitely. If we're not using a package,
    we don't need to keep it around in the database.
    """
    packages = Package.query.all()
    active_package_ids = get_active_package_ids(session=session)
    for package in packages:
        if not _get_lock(package.package_id) \
                and not _get_group_lock(package.package_id) \
                and not Collaboration.query.filter_by(package_id=package.package_id).first() \
                and not GroupCollaboration.query.filter_by(package_id=package.package_id).first() \
                and not Invitation.query.filter_by(package_id=package.package_id).first() \
                and package.package_id not in active_package_ids:
            try:
                logger.info(f'cull_packages: removing package... package_id={package.package_id}, owner_id={package.owner_id}, package_name={package.package_name}')
                session.delete(package)
            except Exception as exc:
                logger.info(f'cull_packages: exception removing package... package_id={package.package_id}, exc={exc}')


def open_package(user_login, package_name, owner_login=None, session=None):
    """
    open_package() is called when a user wants to open a package. If the package is available to open, the user gets the
    lock and the user's active package is set to the package. If the package is locked by another user, an exception is
    raised.
    """
    if not owner_login:
        owner_login = user_login

    with db_session(session) as session:
        cull_packages(session=session)
        return update_lock(user_login, package_name, opening=True, owner_login=owner_login, session=session)


def close_package(user_login, session=None):
    """
    close_package() is called when a user is done with the active package, i.e., when the package is closed or
    deleted or the user logs off. The user's active package is set to None and if a lock is held by the user it is
    released.
    """
    with db_session(session) as session:
        user_id = get_user(user_login, create_if_not_found=True, session=session).user_id
        current_user.set_filename(None)
        active_package_id = _get_active_package_id(user_id)
        if active_package_id:
            release_lock(user_login, active_package_id, session=session)
        set_active_package_id(user_id, sqlalchemy.null(), session=session)
        session.flush()
        cull_packages(session=session)


def _get_lock(package_id):
    """
    Returns the lock record for the specified package, or None if the package is not locked.
    """
    try:
        lock = Lock.query.filter_by(package_id=package_id).first()
    except Exception as exc:
        lock = None
    return lock


def _add_lock(package_id, locked_by, session=None):
    """
    Adds a lock record for the specified package, unless the package is already locked.
    In either case, returns the lock record.
    """
    with db_session(session) as session:
        lock = _get_lock(package_id)
        if not lock:
            # lock = Lock(package_id=package_id, locked_by=locked_by, timestamp=datetime.now(timezone.utc))
            lock = Lock(package_id=package_id, locked_by=locked_by, timestamp=datetime.now())
            session.add(lock)
            session.flush()
        return lock


def remove_package(owner_login, package_name, session=None):
    """
    To be called when a package is deleted. Removes all records associated with the package.
    """
    with db_session(session) as session:
        package = get_package(owner_login, package_name, session)
        if package:
            # Remove any collaborations associated with the package.
            collaborations = Collaboration.query.filter_by(package_id=package.package_id).all()
            for collaboration in collaborations:
                session.delete(collaboration)
            # Remove any locks associated with the package.
            _remove_lock(package.package_id, session=session)
            # Remove any group collaborations associated with the package.
            group_collaborations = GroupCollaboration.query.filter_by(package_id=package.package_id).all()
            for group_collaboration in group_collaborations:
                session.delete(group_collaboration)
            # Remove any invitations associated with the package.
            invitations = Invitation.query.filter_by(package_id=package.package_id).all()
            for invitation in invitations:
                session.delete(invitation)
            # Remove any group locks associated with the package.
            group_lock = _get_group_lock(package.package_id)
            if group_lock:
                session.delete(group_lock)
            # Remove the package record.
            session.delete(package)


def remove_collaboration(collab_id, session=None):
    """
    To be called when a collaboration is terminated. Removes the collaboration record.
    """
    with db_session(session) as session:
        collaboration = Collaboration.query.filter_by(collab_id=collab_id).first()
        if collaboration:
            session.delete(collaboration)


def remove_group_collaboration(group_collab_id, session=None):
    """
    To be called when a grouop collaboration is terminated. Removes the individual collaboration records
    for the group participants and the group collaboration record. Also removes any locks associated with
    the package.
    """
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


def get_group_collaboration_for_lock(group_lock_id):
    """
    Returns the group collaboration associated with the specified group lock, or None if no such group lock exists or
    if the group lock is not associated with a group collaboration.
    """
    group_lock = _get_group_lock_by_id(group_lock_id)
    if group_lock:
        group_collaboration = GroupCollaboration.query.filter_by(package_id=group_lock.package_id,
                                                                 user_group_id=group_lock.locked_by).first()
        return group_collaboration
    return None


def _remove_lock(package_id, session=None):
    """
    Removes the lock record for the specified package, if any. If the user who held the lock has an active_package_id
    that matches the package_id, then the user's active_package_id is set to None.
    """
    with db_session(session) as session:
        lock = _get_lock(package_id)
        if lock:
            # We don't clear the active_package_id for the user who held the lock because otherwise when they resume
            #  work they will look for the package in their own account, not the owner's.
            session.delete(lock)


def _release_lock_for_user(user_id, session=None):
    """
    Removes all locks held by the specified user.
    """
    with db_session(session) as session:
        locks = Lock.query.filter_by(locked_by=user_id).all()
        for lock in locks:
            _remove_lock(lock.package_id, session=session)


def release_acquired_lock(lock, session=None):
    """
    Remove the specified lock. This is called, for example, when a user has acquired a lock on a package, but then
    loading the package fails for some reason.
    """
    if not lock:
        return
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


def _get_group_lock_by_id(group_lock_id):
    """
    Returns the group lock record with the specified group_lock_id, or None if no such group lock exists.
    """
    try:
        group_lock = GroupLock.query.filter_by(group_lock_id=group_lock_id).first()
    except Exception as exc:
        group_lock = None
    return group_lock


def _get_group_lock(package_id):
    """
    Returns the group lock record for the specified package, or None if no such group lock exists.
    """
    try:
        lock = GroupLock.query.filter_by(package_id=package_id).first()
    except Exception as exc:
        lock = None
    return lock


def add_group_lock(package_id, locked_by, session=None):
    """
    Adds a group lock record for the specified package. If a group lock already exists for the package, then the
    existing group lock is returned. If an individual lock exists for the package and the user who holds the lock
    is not a member of the group, then the individual lock is removed.
    """
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
    """
    Removes the group lock record for the specified package, if any.
    """
    with db_session(session) as session:
        lock = _get_group_lock(package_id)
        if lock:
            session.delete(lock)


def release_group_lock(package_id, session=None):
    """
    Removes the group lock record for the specified package, if any. Also removes any individual locks held by
    members of the group.
    Called when a group collaboration is terminated.
    """
    with db_session(session) as session:
        group = GroupCollaboration.query.filter_by(package_id=package_id).first()
        if group:
            _remove_group_lock(package_id, session=session)
            for member in get_group_members(group.user_group_id, session=session):
                member_user = _get_user(member.user_id)
                release_lock(member_user.user_login, package_id, session=session)


def set_active_package_id(user_id, package_id, session=None):
    """
    Sets the active_package_id for the specified user to the specified package_id. The user is assumed to exist.
    """
    with db_session(session) as session:
        user = User.query.filter_by(user_id=user_id).first()
        user.active_package_id = package_id


def _get_active_package_id(user_id):
    """
    Returns the active_package_id for the specified user, or None if no active package exists for the user.
    Raises an exception if no user with the specified ID exists.
    """
    user = User.query.filter_by(user_id=user_id).first()
    if not user:
        raise exceptions.CollaborationDatabaseError('_get_active_package_id: User does not exist')
    return user.active_package_id


def get_active_package(user_login, session=None):
    """
    Returns the active package for the specified user, or None if no active package exists for the user.
    If no user exists with the specified login, an exception is raised.
    """
    with db_session(session) as session:
        user_id = get_user(user_login, create_if_not_found=True, session=session).user_id
        package_id = _get_active_package_id(user_id)
        if package_id:
            return Package.query.filter_by(package_id=package_id).first()
        else:
            return None


def get_active_package_ids(session=None):
    """
    Returns a list of the IDs of all active packages. Used in culling inactive packages.
    """
    with db_session(session) as session:
        return [user.active_package_id for user in User.query.all() if user.active_package_id is not None]


def change_active_package_account(package_name, session=None):
    """
    Changes the active package for the currently logged in user to the specified package, creating a package record
    if necessary.

    This is called when we're opening a backup for review in the logged in user's account. We need to set the active
    package to the backup but owned by the logged in user because we're opening the document in the logged in user's
    account.
    """
    with db_session(session) as session:
        # Get a user object for the logged in user.
        user_login = current_user.get_user_login()
        logged_in_user_id = get_user(user_login, create_if_not_found=True, session=session).user_id
        # Get the current active package for the logged in user.
        current_active_package = get_active_package(user_login, session=session)
        if current_active_package:
            # If the current active package is already owned by the logged in user, then we don't need to do anything.
            if current_active_package.owner_id == logged_in_user_id:
                return

        # Otherwise, we need to set the active package to the specified package, owned by the logged in user, creating
        #  a package record if necessary.
        new_package = get_package(user_login,
                                  package_name,
                                  create_if_not_found=True,
                                  session=session)

        set_active_package_id(logged_in_user_id, new_package.package_id, session=session)
        current_user.set_file_owner(display_name(user_login), owner_login=user_login)
        session.flush()


def get_user(user_login, create_if_not_found=False, session=None):
    """
    Returns the user object for the specified user login. If create_if_not_found is True, then the user is created if
    it doesn't already exist. If create_if_not_found is False, then None is returned if the user doesn't exist.
    """
    with db_session(session) as session:
        user = User.query.filter_by(user_login=user_login).first()
        if not user and create_if_not_found:
            user = add_user(user_login, session=session)
        return user


def _get_user(user_id):
    """
    Returns the user object for the specified user ID. Returns None if no user with the specified ID exists.
    """
    user = User.query.filter_by(user_id=user_id).first()
    return user


def add_user(user_login, session=None):
    """
    Adds a user with the specified login to the database and returns the user object. If the user already exists, the
    existing user object is returned.
    """
    with db_session(session) as session:
        user = get_user(user_login, session=session)
        if not user:
            user = User(user_login=user_login)
            session.add(user)
            session.flush()
        return user


def get_package_by_id(package_id):
    """
    Returns the package object with the specified package ID. Returns None if no package with the specified ID exists.

    This function uses the database id, but is intended to be called from outside the collaboration module, hence
    no preceding underscore in the name. This function is used in handling a request to open a package by a
    collaborator (i.e., when clicing an "Open" link on the collaboration page). The package's database id is passed in
    the URL in that request.
    """
    package = Package.query.filter_by(package_id=package_id).first()
    return package


def get_package_owner(package_id):
    """
    Returns the user object for the owner of the specified package. Returns None if no package with the specified ID
    exists.
    """
    package = get_package_by_id(package_id)
    if package:
        return _get_user(package.owner_id)


def _get_package(owner_id, package_name, create_if_not_found=False, session=None):
    """
    Returns the package object for the specified owner and package name. If create_if_not_found is True, then a package
    record is created if one doesn't already exist. If create_if_not_found is False, then None is returned if no
    package with the specified owner and package name exists.
    """
    with db_session(session) as session:
        package = Package.query.filter_by(owner_id=owner_id, package_name=package_name).first()
        if not package and create_if_not_found:
            package = _add_package(owner_id, package_name, session=session)
        return package


def get_package(owner_login, package_name, create_if_not_found=False, session=None):
    """
    Returns the package object for the specified owner and package name. If create_if_not_found is True, then a package
    record is created if one doesn't already exist. If create_if_not_found is False, then None is returned if no
    package with the specified owner and package name exists.
    Also, if no user with the specified owner_login exists, then a user record is created for that user.
    """
    with db_session(session) as session:
        owner_id = get_user(owner_login, create_if_not_found=True, session=session).user_id
        return _get_package(owner_id, package_name, create_if_not_found, session=session)


def _add_package(owner_id, package_name, session=None):
    """
    Adds a package with the specified owner and package name to the database and returns the package object. If such a
    package already exists, the existing package object is returned.
    """
    with db_session(session) as session:
        package = _get_package(owner_id, package_name, session=session)
        if not package:
            package = Package(owner_id=owner_id, package_name=package_name)
            session.add(package)
            session.flush()
        return package


def get_collaboration(collaborator_id, package_id):
    """
    Returns the collaboration object for the specified collaborator and package. Returns None if no collaboration
    exists for the specified collaborator and package.
    """
    collaboration = Collaboration.query.filter_by(collaborator_id=collaborator_id, package_id=package_id).first()
    return collaboration


def get_owner_login(package_id):
    """
    Returns the login for the owner of the specified package. Returns None if no package with the specified ID exists.
    """
    package = get_package_by_id(package_id)
    if package:
        return _get_user(package.owner_id).user_login


def _add_collaboration(owner_id, collaborator_id, package_id, status=None, session=None):
    """
    Adds a collaboration with the specified owner, collaborator, and package to the database and returns the
    collaboration object. If such a collaboration already exists, the existing collaboration object is returned.
    Also, optionally sets the status of the collaboration, although this functionality is not currently used.
    """
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
    """
    Not currently used.
    """
    collaboration_status = CollaborationStatus.query.filter_by(collab_id=collab_id).first()
    return collaboration_status


def _set_collaboration_status(collab_id, status, session=None):
    """
    Not currently used.
    """
    with db_session(session) as session:
        collaboration_status = db.session.query(CollaborationStatus).filter_by(collab_id=collab_id).first()
        if not collaboration_status:
            collaboration_status = CollaborationStatus(collab_id=collab_id, status=status)
            session.add(collaboration_status)
            session.flush()
        if collaboration_status.status != status:
            collaboration_status.status = status
        return collaboration_status


def get_collaboration_output():
    """
    Returns a list of all collaborations in the database.
    For development and debugging. Displayed when the collaborate page is displayed with a request of the form:
        collaborate/package_name/dev
    It's the "dev" that signals that the collaboration list should be displayed.
    """
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


def get_group_collaboration_output():
    """
    Returns a list of all group collaborations in the database.
    For development and debugging. Displayed when the collaborate page is displayed with a request of the form:
        collaborate/package_name/dev
    It's the "dev" that signals that the collaboration list should be displayed.
    """
    with db_session() as session:
        group_collaboration_list = []
        group_collaborations = GroupCollaboration.query.filter_by().all()
        for group_collaboration in group_collaborations:
            group_collaboration_list.append(GroupCollaborationOutput(
                group_collab_id=group_collaboration.group_collab_id,
                owner_id=group_collaboration.owner_id,
                user_group_id=group_collaboration.user_group_id,
                package_id=group_collaboration.package_id))
        return group_collaboration_list


def get_user_output():
    """
    Returns a list of all users in the database.
    For development and debugging. Displayed when the collaborate page is displayed with a request of the form:
        collaborate/package_name/dev
    It's the "dev" that signals that the collaboration list should be displayed.
    """
    with db_session() as session:
        user_list = []
        users = User.query.filter_by().all()
        for user in users:
            user_list.append(UserOutput(
                user_id=user.user_id,
                user_login=user.user_login,
                active_package_id=user.active_package_id))
        return user_list


def get_package_output():
    """
    Returns a list of all packages in the database.
    For development and debugging. Displayed when the collaborate page is displayed with a request of the form:
        collaborate/package_name/dev
    It's the "dev" that signals that the collaboration list should be displayed.
    """
    with db_session() as session:
        package_list = []
        packages = Package.query.filter_by().all()
        for package in packages:
            owner = User.query.filter_by(user_id=package.owner_id).first()
            if owner:
                owner_login = owner.user_login
            package_list.append(PackageOutput(
                package_id=package.package_id,
                owner_login=owner_login,
                package_name=package.package_name))
        return package_list


def get_lock_output():
    """
    Returns a list of all locks in the database.
    For development and debugging. Displayed when the collaborate page is displayed with a request of the form:
        collaborate/package_name/dev
    It's the "dev" that signals that the collaboration list should be displayed.
    """
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


def get_group_lock_output():
    """
    Returns a list of all group locks in the database.
    For development and debugging. Displayed when the collaborate page is displayed with a request of the form:
        collaborate/package_name/dev
    It's the "dev" that signals that the collaboration list should be displayed.
    """
    with db_session() as session:
        group_lock_list = []
        group_locks = GroupLock.query.filter_by().all()
        for group_lock in group_locks:
            group_lock_id = group_lock.group_lock_id
            package_id = group_lock.package_id
            locked_by_id = group_lock.locked_by
            group_lock_list.append(GroupLockOutput(
                group_lock_id=group_lock_id,
                package_id=package_id,
                locked_by_id=locked_by_id))
        return group_lock_list


def get_groups_for_user(user_id, session=None):
    """
    Returns a list of all groups that have the given user as a member.
    """
    groups = []
    with db_session(session) as session:
        group_memberships = UserGroupMembership.query.filter_by(user_id=user_id).all()
        for group_membership in group_memberships:
            user_group = UserGroup.query.filter_by(user_group_id=group_membership.user_group_id).first()
            if user_group:
                groups.append(user_group)
    return groups


def get_locked_by_id(package_id, session=None):
    """
    Returns the ID of the user who has the lock on the given package. If no lock exists, returns None.
    """
    with db_session(session) as session:
        lock = _get_group_lock(package_id)
        if not lock:
            lock = _get_lock(package_id)
        if lock:
            return lock.locked_by


def get_lock_status(package_id, session=None):
    """
    Returns a tuple consisting of:
         - the group lock ID of the group lock on the given package, or None if no group lock exists
         - the ID of the user who has the individual lock on the given package, or None if no individual lock exists
    """
    group_locked_by_id = None
    individual_locked_by_id = None
    with db_session(session) as session:
        # Get group lock status based on the provided package ID
        group_lock = _get_group_lock(package_id)
        # If a group lock exists, get the ID of the group lock
        if group_lock:
            group_locked_by_id = group_lock.group_lock_id
        # Get individual lock status based on the provided package ID
        individual_lock = _get_lock(package_id)
        # If an individual lock exists, get the ID of the user who has the lock
        if individual_lock:
            individual_locked_by_id = individual_lock.locked_by
    # Return the IDs of the group lock and of holders of individual locks, respectively
    return group_locked_by_id, individual_locked_by_id


def _calculate_lock_status(collaboration_case, logged_in_user_id, package_id, session=None):
    """
    Calculates the lock status for the given package.

    Lock status is calculated as follows:
        - If there is an individual lock, and no group lock, and the logged-in user is the one who has the individual
            lock, then the status is LOCKED_BY_LOGGED_IN_USER
        - Elsif there is an individual lock, and no group lock, and the logged-in user is not the one who has the
            individual lock, then the status is LOCKED_BY_OTHER_USER
        - Elsif there is an individual lock and a group lock, and the logged-in user is the holder of the individual
            lock, then the status is LOCKED_BY_GROUP_AND_LOGGED_IN_USER
        - Elsif there is an individual lock and a group lock, and the logged-in user is bot the holder of the
            individual lock, then the status is LOCKED_BY_GROUP_AND_ANOTHER_USER
        - Elsif there is a group lock but no individual lock, then the status is LOCKED_BY_GROUP_ONLY
        - Elsif there is no individual lock, and no group lock, then the status is NOT_LOCKED

    Returns a tuple consisting of:
            - the lock status
            - the ID of the group lock, or None if no group lock exists
            - the ID of the user who has the individual lock, or None if no individual lock exists
    """
    with db_session(session) as session:
        # Get the IDs of the group locks and holders of individual locks, respectively
        group_locked_by_id, individual_locked_by_id = get_lock_status(package_id, session=session)
        # Initialize lock status as NOT_LOCKED
        lock_status = LockStatus.NOT_LOCKED
        # If there is an individual lock
        if individual_locked_by_id:
            # If there is no group lock
            if not group_locked_by_id:
                # If the logged-in user is the one who locked it
                if individual_locked_by_id == logged_in_user_id:
                    # Set the status as LOCKED_BY_LOGGED_IN_USER
                    lock_status = LockStatus.LOCKED_BY_LOGGED_IN_USER
                else:
                    # Else, set it as LOCKED_BY_ANOTHER_USER
                    lock_status = LockStatus.LOCKED_BY_ANOTHER_USER
            else:  # There is a group lock
                # If the logged-in user holds an individual lock
                if individual_locked_by_id == logged_in_user_id:
                    # Set the status as LOCKED_BY_GROUP_AND_LOGGED_IN_USER
                    lock_status = LockStatus.LOCKED_BY_GROUP_AND_LOGGED_IN_USER
                else:
                    # Else, set it as LOCKED_BY_GROUP_AND_ANOTHER_USER
                    lock_status = LockStatus.LOCKED_BY_GROUP_AND_ANOTHER_USER
        # If there is no individual lock but there is a group lock
        elif group_locked_by_id:
            # Set the status as LOCKED_BY_GROUP_ONLY
            lock_status = LockStatus.LOCKED_BY_GROUP_ONLY

        # Return the lock status and the IDs of the holders of the group and individual locks, respectively
        return lock_status, group_locked_by_id, individual_locked_by_id


def _calculate_actions(logged_in_user_id,
                       user_id,
                       collaboration_group,
                       collaboration_case,
                       lock_status,
                       locked_by_group_id,
                       locked_by_individual_id,
                       package_id=None, # not used but here so we can see it in the debugger
                       session=None):
    """
    This function calculates what actions are available for a given entry in the Collaborate page.
    Possible actions are defined by CollaborationAction enum.
    collaboration_case is a CollaborationCase enum value that indicates the type of collaboration.

    user_id identifies the user or group whose Collaborate page entry is being viewed.

    Returns a list of actions that are available for the given entry.
    """
    def is_a_group_lock_status(lock_status):
        return lock_status in [LockStatus.LOCKED_BY_GROUP_ONLY,
                               LockStatus.LOCKED_BY_GROUP_AND_LOGGED_IN_USER,
                               LockStatus.LOCKED_BY_GROUP_AND_ANOTHER_USER]


    with db_session(session) as session:
        # Initialize an empty list to store the possible actions
        actions = []
        # Ensure the user ID is a string
        user_id = str(user_id)

        # In the case where the logged-in user is the owner and the collaborator is an individual
        if collaboration_case == CollaborationCase.LOGGED_IN_USER_IS_OWNER_COLLABORATOR_IS_INDIVIDUAL:
            # If the package is not locked and the user is not the logged-in user
            if lock_status == LockStatus.NOT_LOCKED and user_id != logged_in_user_id:
                # The user can open the package via the Collaborate page
                actions.append(CollaborationAction.OPEN)
            # If the package is locked by the logged-in user
            if lock_status == LockStatus.LOCKED_BY_LOGGED_IN_USER:
                # The logged-in user can release the individual lock and end the collaboration
                actions.append(CollaborationAction.RELEASE_INDIVIDUAL_LOCK)
                actions.append(CollaborationAction.END_COLLABORATION)

        # In the case where the logged-in user is the owner and the collaborator is a group
        if collaboration_case == CollaborationCase.LOGGED_IN_USER_IS_OWNER_COLLABORATOR_IS_GROUP:
            # If the package is locked by the logged-in user
            if lock_status == LockStatus.LOCKED_BY_LOGGED_IN_USER:
                # The logged-in user can release the individual lock
                actions.append(CollaborationAction.RELEASE_INDIVIDUAL_LOCK)
            elif lock_status == LockStatus.LOCKED_BY_GROUP_AND_LOGGED_IN_USER:
                # The logged-in user can release the group lock and end the group collaboration
                actions.append(CollaborationAction.RELEASE_GROUP_LOCK)
                actions.append(CollaborationAction.END_GROUP_COLLABORATION)

        # In the case where the logged-in user is an individual collaborator
        if collaboration_case == CollaborationCase.LOGGED_IN_USER_IS_INDIVIDUAL_COLLABORATOR:
            # If the package is not locked
            if lock_status == LockStatus.NOT_LOCKED:
                # The user can open the package via the Collaborate page
                actions.append(CollaborationAction.OPEN)
            # If the package is locked by the logged-in user
            elif lock_status == LockStatus.LOCKED_BY_LOGGED_IN_USER:
                # The logged-in user can release the individual lock
                actions.append(CollaborationAction.RELEASE_INDIVIDUAL_LOCK)
                # If the user is the only collaborator, they can end the collaboration
                actions.append(CollaborationAction.END_COLLABORATION)
            # If the package is locked by the group and the logged-in user (who is a group member)
            elif lock_status == LockStatus.LOCKED_BY_GROUP_AND_LOGGED_IN_USER:
                # The logged-in user can release the individual lock and end the group collaboration
                actions.append(CollaborationAction.RELEASE_INDIVIDUAL_LOCK)
                actions.append(CollaborationAction.END_GROUP_COLLABORATION)
            # If the package is locked by the group only
            elif lock_status == LockStatus.LOCKED_BY_GROUP_ONLY:
                # There are no available actions
                pass

        # In the case where the logged-in user is a group collaborator
        if collaboration_case == CollaborationCase.LOGGED_IN_USER_IS_GROUP_COLLABORATOR:
            # If the user ID starts with 'G', indicating a group, we are processing the entry for the group
            if user_id.startswith('G'):
                # If the logged-in user is part of the collaboration group
                if collaboration_group in get_groups_for_user(logged_in_user_id, session=session):
                    # If the package is not locked
                    if lock_status == LockStatus.NOT_LOCKED:
                        # The user can apply a group lock
                        actions.append(CollaborationAction.APPLY_GROUP_LOCK)
                    else:
                        # If the package is locked by the group
                        if is_a_group_lock_status(lock_status):
                            # If the package is locked by the logged-in user
                            if locked_by_individual_id == logged_in_user_id:
                                # The logged-in user can release the group lock and end the group collaboration
                                actions.append(CollaborationAction.RELEASE_GROUP_LOCK)
                                actions.append(CollaborationAction.END_GROUP_COLLABORATION)
                        # If the package is locked by the logged-in user
                        elif lock_status == LockStatus.LOCKED_BY_LOGGED_IN_USER:
                            # The user can apply a group lock
                            actions.append(CollaborationAction.APPLY_GROUP_LOCK)
            else:
                # If the user is an individual member of the group
                # If the package is either not locked or locked by the group only
                if lock_status in [LockStatus.NOT_LOCKED, LockStatus.LOCKED_BY_GROUP_ONLY]:
                    # If the logged-in user is the one trying to take action
                    if user_id == str(logged_in_user_id):
                        # The user can open the package via the Collaborate page
                        actions.append(CollaborationAction.OPEN)
                # If the package is locked by either the logged-in user or both the group and the logged-in user
                elif lock_status in [LockStatus.LOCKED_BY_LOGGED_IN_USER, LockStatus.LOCKED_BY_GROUP_AND_LOGGED_IN_USER]:
                    # If the logged-in user is the one trying to take action
                    if user_id == str(logged_in_user_id):
                        # The logged-in user can release the individual lock
                        actions.append(CollaborationAction.RELEASE_INDIVIDUAL_LOCK)

        # Return the list of possible actions
        return actions


def get_group_collaborations(logged_in_user_id, session=None):
    """
    Handling group collaborations:
    We build a list of collaboration records and a set of collaboration_ids to suppress because they are details
     of group membership and the user is not a member of the group.
    - Find group collaborations where the user is the package owner
        For each such collaboration,
            - if the user is not a member of the group, we want to suppress the ordinary collaborations with members of the group
              E.g., for users who are not EDI Curators, we don't display the individual collaborations with the EDI Curators group
            - if the user is a member of the group, we want to suppress the ordinary collaborations with other members of the group
    - Find group collaborations where the user is a member
        First, find groups where the user is a member
        For each such group, find the group collaborations where the user is not the owner (the case where the user is
        the owner is handled above)
    """

    def get_member_login(member):
        return _get_user(member.user_id).user_login

    collaboration_records = []
    collaborations_to_suppress = set()
    with db_session(session) as session:
        groups_for_user = get_groups_for_user(logged_in_user_id, session=session)

        # First, where the logged in user is package owner
        group_collaborations = GroupCollaboration.query.filter_by(owner_id=logged_in_user_id).all()
        for group_collaboration in group_collaborations:
            # Is the user a member?
            if group_collaboration.user_group not in groups_for_user:
                # No, so we want to suppress the ordinary collaborations with members of the group
                # E.g., for users who are not EDI Curators, we don't display the individual collaborations
                # with the EDI Curators group
                for member in get_group_members(group_collaboration.user_group.user_group_id):
                    collaborations_to_suppress.add((group_collaboration.package_id, member.user_id))
            else:
                # Yes, so we want to suppress the ordinary collaborations with other members of the group
                # Find the group members
                group_members = get_group_members(group_collaboration.user_group.user_group_id)
                for member in group_members:
                    if member.user_id != logged_in_user_id:
                        collaborations_to_suppress.add((group_collaboration.package_id, member.user_id))

            collaboration_case = CollaborationCase.LOGGED_IN_USER_IS_OWNER_COLLABORATOR_IS_GROUP
            lock_status, locked_by_group_id, locked_by_individual_id = \
                _calculate_lock_status(collaboration_case,
                                       logged_in_user_id,
                                       group_collaboration.package_id,
                                       session=session)
            group_as_user = get_user(fake_login_for_group(group_collaboration.user_group.user_group_name),
                                     session=session)
            actions = _calculate_actions(logged_in_user_id, group_as_user.user_id, group_collaboration.user_group,
                                         collaboration_case, lock_status, locked_by_group_id, locked_by_individual_id,
                                         package_id=group_collaboration.package_id,
                                         session=session)

            # Add the entry for the group, case where the logged-in user is the package owner
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
                locked_by_group_id=locked_by_group_id,
                locked_by_individual_id=locked_by_individual_id,
                status_str='',
                action_str=''))

        # Second, where the logged in user is a member.
        groups = get_groups_for_user(logged_in_user_id, session=session)
        for group in groups:
            group_collaborations = GroupCollaboration.query.filter_by(user_group_id=group.user_group_id).all()
            for group_collaboration in group_collaborations:
                # If the logged-in user is the owner, we've already emitted an entry for this group collaboration,
                #  above, so we skip it here.
                if group_collaboration.owner_id != logged_in_user_id:
                    group_as_user = get_user(fake_login_for_group(group_collaboration.user_group.user_group_name),
                                             session=session)

                    collaboration_case = CollaborationCase.LOGGED_IN_USER_IS_GROUP_COLLABORATOR
                    lock_status, locked_by_group_id, locked_by_individual_id = \
                        _calculate_lock_status(collaboration_case, logged_in_user_id,
                                               group_collaboration.package_id, session=session)
                    actions = _calculate_actions(logged_in_user_id, f'G{group_as_user.user_id}',
                                                 group_collaboration.user_group, collaboration_case,
                                                 lock_status, locked_by_group_id, locked_by_individual_id,
                                                 package_id=group_collaboration.package_id,
                                                 session=session)

                    # Add the entry for the group, case where the logged-in user is not the package owner
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
                        locked_by_group_id=locked_by_group_id,
                        locked_by_individual_id=locked_by_individual_id,
                        status_str='',
                        action_str=''))

                members = get_group_members(group_collaboration.user_group.user_group_id, session=session)
                lock = _get_lock(group_collaboration.package_id)
                for member in members:
                    # We don't want to show entries for all the group members, just the logged-in user
                    if member.user_id != logged_in_user_id:
                        continue
                    collaboration = get_collaboration(member.user_id, group_collaboration.package_id)
                    # We don't want the collaboration to show up twice when we handle individual collaborations
                    collaborations_to_suppress.add((group_collaboration.package_id, member.user_id))

                    collaboration_case = CollaborationCase.LOGGED_IN_USER_IS_GROUP_COLLABORATOR
                    lock_status, locked_by_group_id, locked_by_individual_id = \
                        _calculate_lock_status(collaboration_case,
                                               logged_in_user_id,
                                               group_collaboration.package_id,
                                               session=session)
                    actions = _calculate_actions(logged_in_user_id, member.user_id,
                                                 group_collaboration.user_group, collaboration_case,
                                                 lock_status, locked_by_group_id, locked_by_individual_id,
                                                 package_id=group_collaboration.package_id,
                                                 session=session)

                    # Add the entry for the logged-in user as a group member
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
                        locked_by_group_id=locked_by_group_id,
                        locked_by_individual_id=locked_by_individual_id,
                        status_str='',
                        action_str=''))

    return collaboration_records, collaborations_to_suppress


def get_collaborations(user_login):
    """
    Returns the list of collaborations for a given user, to be displayed on the Collaboration page
    """
    if not user_login:
        return []

    # Get all collaborations where the user is the owner or the collaborator
    with db_session() as session:
        logged_in_user_id = get_user(user_login, create_if_not_found=True, session=session).user_id

        # Get group collaborations involving this user
        collaboration_records, collaborations_to_suppress = get_group_collaborations(logged_in_user_id, session=session)

        # Now get the ordinary collaborations, adding them to the collaboration_records list

        # We will annotate each ordinary collaboration with its collaboration case
        annotated_collaborations = []

        # First, where the user is owner
        collaborations = Collaboration.query.filter_by(owner_id=logged_in_user_id).all()
        for collaboration in collaborations:
            annotated_collaborations.append((collaboration, CollaborationCase.LOGGED_IN_USER_IS_OWNER_COLLABORATOR_IS_INDIVIDUAL))

        # Then, where the user is collaborator
        collaborations = Collaboration.query.filter_by(collaborator_id=logged_in_user_id).all()
        for collaboration in collaborations:
            annotated_collaborations.append((collaboration, CollaborationCase.LOGGED_IN_USER_IS_INDIVIDUAL_COLLABORATOR))
        for collaboration, collaboration_case in annotated_collaborations:
            if (collaboration.package_id, collaboration.collaborator_id) in collaborations_to_suppress:
                continue

            # Generate the entry for this ordinary collaboration. Note that entries for group collaborations are
            # generated in get_group_collaborations()

            owner_id = collaboration.owner_id

            # Check for a timed-out lock
            lock = _get_lock(collaboration.package_id)
            # If the lock has timed out, remove it. We do this here because a collaborator cannot open a locked package
            #  and has no way to remove the lock.
            if lock:
                t1 = datetime.now()
                t2 = lock.timestamp
                if (t1 - t2).total_seconds() > Config.COLLABORATION_LOCK_INACTIVITY_TIMEOUT_MINUTES * 60:
                    # The lock has timed out, so remove it
                    logger.info(f'get_collaborations: lock has timed out for {collaboration.package_id}')
                    _remove_lock(collaboration.package_id, session=session)

            lock_status, locked_by_group_id, locked_by_individual_id = \
                _calculate_lock_status(collaboration_case, logged_in_user_id,
                                       collaboration.package_id, session=session)
            actions = _calculate_actions(logged_in_user_id, collaboration.collaborator_id, None, collaboration_case,
                                         lock_status, locked_by_group_id, locked_by_individual_id,
                                         package_id=collaboration.package_id,
                                         session=session)

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
                    locked_by_group_id=locked_by_group_id,
                    locked_by_individual_id=locked_by_individual_id,
                    status_str='',
                    action_str=''))
            except Exception as e:
                logger.error(f'Exception in handling a Collaboration Record: {e}')
                pass
        return sorted(collaboration_records)


def get_invitations(user_login):
    """
    Returns the list of invitations made by a given user, to be displayed on the Collaboration page.
    """
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
    """
    Returns the invitation with the given code, or raises an exception if not found. Used to look up an invitation
    when a user accepts an invitation.
    """
    invitation = Invitation.query.filter_by(invitation_code=invitation_code).first()
    if not invitation:
        raise exceptions.InvitationNotFound(f'Invitation with code {invitation_code} not found')
    return invitation


def generate_invitation_code():
    """
    Generates a unique invitation code.
    """
    ok = False
    while not ok:
        # Make a random 4-letter code, but limit to consonants to avoid offensive words
        code = ''.join(random.choices("BCDFGHJKLMNPQRSTVWXYZ", k=4))
        # Check to make sure the invitation code is unique, i.e., not already in the database for another invitation
        invitation = Invitation.query.filter_by(invitation_code=code).first()
        if not invitation:
            ok = True
    return code


def accept_invitation(user_login, invitation_code, session=None):
    """
    Accepts an invitation. Returns the collaboration that is created.
    """
    with db_session(session) as session:
        # Find the invitation
        invitation = Invitation.query.filter_by(invitation_code=invitation_code).first()
        if not invitation:
            raise exceptions.InvitationNotFound(f'Invitation with code {invitation_code} not found')

        # Find the user
        user = get_user(user_login, create_if_not_found=True)
        if invitation.inviter_id == user.user_id:
            raise exceptions.InvitationBeingAcceptedByOwner(
                f'Invitation with code {invitation_code} cannot be accepted by the user who created it')

        # Create the collaboration
        owner_id = invitation.inviter_id
        collaborator_id = user.user_id
        package_id = invitation.package_id
        collaboration = _add_collaboration(owner_id, collaborator_id, package_id, session=session)
        # Remove the invitation
        session.delete(invitation)
        return collaboration


def create_auto_collaboration(owner_login, collaborator_login, package_name, template_name, collaborator_email=None, session=None):
    """
    Creates a collaboration automatically, without an invitation. Certain templates are configured to automatically
    create collaborations between the owner and collaborator IMs. This function is called when a user creates a package
    from such a template.
    """
    def send_auto_collaboration_email(to_address, owner_login, package_name, template_name):
        parsed_url = urlparse(request.base_url)
        server = parsed_url.netloc
        subject = f'Collaboration on ezEML package "{package_name}" created from template "{template_name}"'
        msg = f'ezEML has added you as a collaborator on package "{package_name}" created by user ' \
              f'{display_name(owner_login)} from template "{template_name}" at {server}.\n\n' \
              f'ezEML currently is configured to automatically add you as a collaborator whenever a package is created ' \
              f'from any template under "{os.path.dirname(template_name)}". If you no longer wish to be added as a ' \
              f'collaborator on such packages, please contact support@edirepository.org.'
        mimemail.send_mail(subject=subject, msg=msg, to=to_address)

    with db_session(session) as session:
        owner_id = get_user(owner_login, create_if_not_found=True, session=session).user_id
        collaborator_id = get_user(collaborator_login, create_if_not_found=True, session=session).user_id
        package = get_package(owner_login, package_name, create_if_not_found=True, session=session)
        package_id = package.package_id
        if owner_id != collaborator_id:
            _ = _add_collaboration(owner_id, collaborator_id, package_id, session=session)
            if collaborator_email:
                # Send an email to the collaborator
                send_auto_collaboration_email(to_address=collaborator_email,
                                              owner_login=owner_login,
                                              package_name=package.package_name,
                                              template_name=template_name)


def remove_invitation(invitation_code):
    """
    Removes an invitation with the given code. Returns True if the invitation was found and removed, False otherwise.
    """
    invitation = Invitation.query.filter_by(invitation_code=invitation_code).first()
    if invitation:
        with db_session() as session:
            session.delete(invitation)
        return True
    return False


def cancel_invitation(invitation_id):
    """
    Cancels an invitation with the given ID. Returns True if the invitation was found and removed, False otherwise.
    """
    invitation = Invitation.query.filter_by(invitation_id=invitation_id).first()
    if invitation:
        with db_session() as session:
            session.delete(invitation)
        return True
    return False


def create_invitation(filename, inviter_name, inviter_email, invitee_name, invitee_email, session=None):
    """
    Creates an invitation in the database. Returns the invitation code.
    """
    with db_session(session) as session:
        inviter_login = current_user.get_user_login()
        active_package = get_active_package(inviter_login, session=session)
        if not active_package:
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


def _get_user_group(user_group_id):
    """
    Returns the user group object with the given ID, or None if not found.
    """
    user_group = UserGroup.query.filter_by(user_group_id=user_group_id).first()
    return user_group


def get_user_group(user_group_name, create_if_not_found=True, session=None):
    """
    Returns the user group object with the given name, or None if not found. If create_if_not_found is True, creates
    the user group if not found.
    """
    with db_session(session) as session:
        user_group = UserGroup.query.filter_by(user_group_name=user_group_name).first()
        if not user_group and create_if_not_found:
            user_group = add_user_group(user_group_name, session=session)
        return user_group


def add_user_group(user_group_name, session=None):
    """
    Adds a user group with the given name. Returns the user group object. If the user group already exists, returns
    the existing user group.
    """
    with db_session(session) as session:
        user_group = get_user_group(user_group_name, create_if_not_found=False, session=session)
        if not user_group:
            user_group = UserGroup(user_group_name=user_group_name)
            session.add(user_group)
            session.flush()
        return user_group


def get_user_group_membership(user_group_id, user_id, create_if_not_found=False, session=None):
    """
    Returns the user group membership object with the given user group ID and user ID, or None if not found. If
    create_if_not_found is True, creates the user group membership if not found.
    """
    with db_session(session) as session:
        user_group_membership = UserGroupMembership.query.filter_by(user_group_id=user_group_id, user_id=user_id).first()
        if not user_group_membership and create_if_not_found:
            user_group_membership = UserGroupMembership(user_group_id=user_group_id, user_id=user_id)
            session.add(user_group_membership)
        return user_group_membership


def _get_group_collaboration(group_collab_id):
    """
    Returns the group collaboration object with the given ID, or None if not found.
    """
    group_collaboration = GroupCollaboration.query.filter_by(group_collab_id=group_collab_id).first()
    return group_collaboration


def get_group_collaboration(user_group_id, package_id):
    """
    Returns the group collaboration object with the given user group ID and package ID, or None if not found.
    """
    group_collaboration = GroupCollaboration.query.filter_by(user_group_id=user_group_id, package_id=package_id).first()
    return group_collaboration


def get_group_members(user_group_id, session=None):
    """
    Returns a list of user group membership objects for the given user group ID.
    """
    with db_session(session) as session:
        user_group_memberships = UserGroupMembership.query.filter_by(user_group_id=user_group_id).all()
        return user_group_memberships


def is_group_member(user_login, user_group_id, session=None):
    """
    Returns True if the user with the given login is a member of the user group with the given ID, False otherwise.
    """
    with db_session(session) as session:
        user = get_user(user_login, session=session)
        if user:
            user_id = user.user_id
            user_group_membership = UserGroupMembership.query.filter_by(user_id=user_id, user_group_id=user_group_id).first()
            return user_group_membership is not None
        return False


def is_edi_curator(user_login, session=None):
    """
    Returns True if the user with the given login is an EDI curator, False otherwise.
    """
    with db_session(session) as session:
        curator_group = get_user_group("EDI Curators", create_if_not_found=False, session=session)
        if curator_group:
            return is_group_member(user_login, curator_group.user_group_id, session=session)
        return False


def package_is_under_edi_curation(package_id, session=None):
    """
    Returns True if the package with the given ID is under EDI curation, False otherwise.
    """
    with db_session(session) as session:
        curator_group = get_user_group("EDI Curators", create_if_not_found=False, session=session)
        if curator_group:
            group_collaboration = get_group_collaboration(curator_group.user_group_id, package_id)
            return group_collaboration is not None
        return False


def another_package_with_same_name_is_under_edi_curation(package_id, session=None):
    """
    Returns True if another package with the same name as the package with the given ID, but different owner, is under
    EDI curation, False otherwise.
    """
    with db_session(session) as session:
        package = get_package_by_id(package_id)
        if not package:
            return False
        package_name = package.package_name
        curator_group = get_user_group("EDI Curators", create_if_not_found=False, session=session)
        if curator_group:
            group_collaborations = GroupCollaboration.query.all()
            for group_collaboration in group_collaborations:
                if group_collaboration.package_id != package_id and group_collaboration.package.package_name == package_name:
                    return True
        return False


def get_member_login(member):
    return _get_user(member.user_id).user_login


def add_group_collaboration(user_login, user_group_name, package_name, session=None):
    """
    Adds a group collaboration with the given user as owner, collaborating with the given group on the given package.
    If the user doesn't exist or is not the owner of the package, raises UserNotFound or UserIsNotTheOwner, respectively.
    If the group collaboration already exists with the specified parameters, raises CollaboratingWithGroupAlready.

    Adds the group collaboration to the database and adds individual collaborations for the group members.
    Returns the group collaboration object.
    """
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
    """
    Initialize the database, if necessary, and populate it with the initial data.
    """
    db.create_all()
    init_groups()
    # test_stub()


def init_groups():
    """
    Initialize the database with the initial groups, defined in the configuration file.
    Currently, the only group is the EDI Curators group.
    """
    with db_session() as session:
        groups = Config.COLLABORATION_GROUPS
        for user_group_name in groups.keys():
            # We want a "user" representing each group so that we can add them as collaborators
            _ = add_user(user_login=fake_login_for_group(user_group_name), session=session)
        for user_group_name, members in groups.items():
            user_group = add_user_group(user_group_name=user_group_name, session=session)
            # Remove group members. If a member has been removed, then we need to remove them from the database.
            # We'll just remove all the members and re-add them below. The point here is that the group membership
            #  as defined in the config file may have changed since the last time we ran this function. Users who
            #  are no longer members of the group need to be removed from the database.
            UserGroupMembership.query.filter_by(user_group_id=user_group.user_group_id).delete()
            for member in members:
                user = get_user(member, create_if_not_found=True, session=session)
                # Add the members back in
                _ = get_user_group_membership(user_group_id=user_group.user_group_id,
                                              user_id=user.user_id,
                                              create_if_not_found=True, # This is what causes them to be added
                                              session=session)


def fake_login_for_group(user_group_name):
    """
    We prepend a null character to the group name to ensure that it is not a valid login (thereby conflicting with a
     user login) and to put it ahead of group members in the sort order for display purposes.
    """
    return "\0" + user_group_name + "-group_collaboration"


def save_backup_is_disabled():
    """
    Returns True if the save backup feature is disabled, False otherwise.
    I.e., returns True if the active package is not under EDI curation, False otherwise. Only packages under EDI
        curation can be backed up. Apologies for the double negative, but it makes sense for the caller.
    """
    active_package_id = None
    user_login = current_user.get_user_login()
    if user_login:
        active_package = get_active_package(user_login)
        if active_package:
            active_package_id = active_package.package_id
    # See if the active package is in a group collaboration with EDI Curators
    return not package_is_under_edi_curation(active_package_id)


def test_stub():
    """
    Used in development.
    """
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
    """
    Remove locks that have timed out and remove packages that have no locks and no collaborations.

    When the collaborate page is loaded with the "dev" parameter, a Clean Up Database button is displayed that will
    cause this function to be called. This is useful for development, but it should not be necessary in production.

    cull_locks() and cull_packages() make this function unnecessary, but it still may be useful for development.
    """
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
                _remove_lock(lock.package_id, session=session)
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