"""
This module contains data classes used by the collaborations module.

These data classes represent the various data structures used by the collaborations module, but in a displayable form.
"""

from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from flask import url_for
from flask_login import current_user

from webapp.pages import *
import webapp.views.collaborations.collaborations as collaborations
from webapp.home.home_utils import log_error, log_info


"""
Represent a row of the backups table in a displayable form.
"""
@dataclass()
class Backup:
    owner_login: str
    owner_name: str
    package_name: str
    date: str
    is_primary: str
    preview: str
    restore: str
    delete: str


"""
Represent a row of the collaborations table in a displayable form. 
"""
@dataclass()
class CollaborationRecord:
    collaboration_case: Enum
    lock_status: Enum
    actions: list
    collab_id: int
    package_id: int
    package_name: str
    owner_id: int
    owner_login: str
    owner_name: str
    collaborator_id: int
    collaborator_login: str
    collaborator_name: str
    date_created: str
    locked_by_group_id: int
    locked_by_individual_id: int
    status_str: str
    action_str: str

    def update_action_str(self, action_str):
        """ Add an action to the action_str """
        if len(self.action_str) > 0:
            self.action_str += '<br>'
        self.action_str += action_str

    def __post_init__(self):
        """ Initialize various fields in the CollaborationRecord object based on values passed in. """
        current_user_login = current_user.get_user_org()
        current_user_id = collaborations.get_user(current_user_login).user_id
        self.owner_name = collaborations.display_name(self.owner_login)
        self.collaborator_name = collaborations.display_name(self.collaborator_login)

        trace = False
        # In development, you could uncomment the following line to see the trace, for example.
        # trace = self.owner_name in ['EDI', 'jide']

        is_group_entry = self.collaborator_login.endswith('-group_collaboration')
        locked_by_individual = None
        if self.locked_by_individual_id is not None:
            locked_by_individual = collaborations._get_user(self.locked_by_individual_id).user_login

        locked_by_group = None
        group_collaboration = None
        if self.locked_by_group_id is not None:
            group_lock = collaborations._get_group_lock_by_id(self.locked_by_group_id)
            if group_lock is not None:
                locked_by_id = group_lock.locked_by
                if locked_by_id is not None:
                    user_group = collaborations._get_user_group(locked_by_id)
                    group_collaboration = collaborations.get_group_collaboration_for_lock(locked_by_id)
                    if user_group is not None:
                        locked_by_group = user_group.user_group_name
            else:
                if trace:
                    log_info(f'collaborations._get_group_lock_by_id(self.locked_by_group_id) returns None')

        if trace:
            log_info(f'owner: {self.owner_name}, collaborator: {self.collaborator_name}, lock_status: {self.lock_status}, locked_by_group_id: {self.locked_by_group_id}, locked_by_group: {locked_by_group}, locked_by_individual: {locked_by_individual}')

        # Status
        if self.lock_status == collaborations.LockStatus.NOT_LOCKED:
            self.status_str = 'Available'

        if self.lock_status == collaborations.LockStatus.LOCKED_BY_LOGGED_IN_USER:
            if not is_group_entry or \
                    self.collaboration_case == collaborations.CollaborationCase.LOGGED_IN_USER_IS_OWNER_COLLABORATOR_IS_GROUP:
                self.status_str = 'In use by ' + collaborations.display_name(locked_by_individual)
            else:
                # The group lock is available
                self.status_str = 'Available'

        if self.lock_status == collaborations.LockStatus.LOCKED_BY_ANOTHER_USER:
            self.status_str = 'In use by ' + collaborations.display_name(locked_by_individual)
            if self.locked_by_group_id is not None:
                # If the collaborator is not a group member, we want to show the status as locked by the group
                group_collaboration = collaborations.get_group_collaboration_for_lock(self.locked_by_group_id)
                if group_collaboration:
                    if not collaborations.is_group_member(self.collaborator_login, group_collaboration.group_collab_id):
                        group_name = group_collaboration.user_group.user_group_name
                        self.status_str = f'In use by {group_name}'

        if self.lock_status == collaborations.LockStatus.LOCKED_BY_GROUP_ONLY:
            if self.collaboration_case == collaborations.CollaborationCase.LOGGED_IN_USER_IS_GROUP_COLLABORATOR and\
                   is_group_entry:
                self.status_str = f'In use by {self.collaborator_name}'
            elif self.collaboration_case == collaborations.CollaborationCase.LOGGED_IN_USER_IS_OWNER_COLLABORATOR_IS_GROUP:
                self.status_str = f'In use by {self.collaborator_name}'
            elif self.collaboration_case in [
                collaborations.CollaborationCase.LOGGED_IN_USER_IS_OWNER_COLLABORATOR_IS_INDIVIDUAL,
                collaborations.CollaborationCase.LOGGED_IN_USER_IS_INDIVIDUAL_COLLABORATOR]:
                # If the collaborator is not a group member, we want to show the status as locked by the group

                group_collaboration = collaborations.get_group_collaboration_for_lock(self.locked_by_group_id)
                if group_collaboration:
                    if not collaborations.is_group_member(self.collaborator_login, group_collaboration.group_collab_id):
                        group_name = group_collaboration.user_group.user_group_name
                        self.status_str = f'In use by {group_name}'
            else:
                self.status_str = 'Available'

        if self.lock_status == collaborations.LockStatus.LOCKED_BY_GROUP_AND_LOGGED_IN_USER:
            if not is_group_entry:
                self.status_str = 'In use by ' + collaborations.display_name(locked_by_individual)
            else:
                self.status_str = 'In use by ' + collaborations.display_name(self.collaborator_login)

        if self.lock_status == collaborations.LockStatus.LOCKED_BY_GROUP_AND_ANOTHER_USER:
            group_collaboration = collaborations.get_group_collaboration_for_lock(self.locked_by_group_id)
            if group_collaboration:
                if not collaborations.is_group_member(self.collaborator_login, group_collaboration.group_collab_id):
                    group_name = group_collaboration.user_group.user_group_name
                    self.status_str = f'In use by {group_name}'
                else:
                    self.status_str = 'In use by ' + collaborations.display_name(locked_by_individual)

        # Actions
        for action in self.actions:
            if action == collaborations.CollaborationAction.OPEN:
                if self.collaboration_case in [collaborations.CollaborationCase.LOGGED_IN_USER_IS_GROUP_COLLABORATOR,
                                               collaborations.CollaborationCase.LOGGED_IN_USER_IS_INDIVIDUAL_COLLABORATOR]:
                    link = url_for(PAGE_OPEN_BY_COLLABORATOR, collaborator_id=self.collaborator_id,
                                   package_id=self.package_id)
                    self.update_action_str(f'<a href="{link}">Open</a>')

            if action == collaborations.CollaborationAction.RELEASE_INDIVIDUAL_LOCK:
                # if self.collaborator_id == current_user_id:
                link = url_for(PAGE_RELEASE_LOCK, package_id=self.package_id)
                self.update_action_str(f'<a href="{link}">Make available</a>')

            if action == collaborations.CollaborationAction.RELEASE_GROUP_LOCK:
                link = url_for(PAGE_RELEASE_GROUP_LOCK, package_id=self.package_id)
                self.update_action_str(f'<a href="{link}">Release group lock</a>')

            if action == collaborations.CollaborationAction.APPLY_GROUP_LOCK:
                link = url_for(PAGE_APPLY_GROUP_LOCK,
                               package_id=self.package_id,
                               group_id=self.collaborator_id)
                self.update_action_str(f'<a href="{link}">Apply group lock</a>')

            if action == collaborations.CollaborationAction.END_COLLABORATION:
                link = url_for(PAGE_REMOVE_COLLABORATION, collab_id=self.collab_id)
                onclick = f"return confirm('Are you sure? This will end the collaboration for all participants and " \
                          f"cannot be undone.');"
                self.update_action_str(f'<a href="{link}" onclick="{onclick}">End collaboration</a>')

            if action == collaborations.CollaborationAction.END_GROUP_COLLABORATION:
                link = url_for(PAGE_REMOVE_COLLABORATION, collab_id=f'G{self.collab_id}')
                onclick = f"return confirm('Are you sure? This will end the collaboration for all participants and " \
                                  f"cannot be undone.');"
                self.update_action_str(f'<a href="{link}" onclick="{onclick}">End group collaboration</a>')

    def __lt__(self, other):
        """ This is used to sort the list of collaborations in the display table. """
        if self.package_name < other.package_name:
            return True
        elif self.package_name == other.package_name:
            if self.owner_name.lower() < other.owner_name.lower():
                return True
            elif self.owner_name.lower() == other.owner_name.lower():
                if self.collaborator_name.lower() < other.collaborator_name.lower():
                    return True
                else:
                    return False
            else:
                return False
        else:
            return False


"""
Represent an invitation in a displayable form.
"""
@dataclass()
class InvitationRecord:
    invitation_id: int
    package_id: int
    package: str
    invitee_name: str
    invitee_email: str
    date: str
    action: str

    def __post_init__(self):
        current_user_login = current_user.get_user_org()
        if current_user_login == collaborations.get_package_owner(self.package_id).user_login:
            link = url_for(PAGE_CANCEL_INVITATION, invitation_id=self.invitation_id)
            self.action = f'<a href="{link}">Cancel invitation</a>'

    def __lt__(self, other):
        if self.package.lower() < other.package.lower():
            return True
        elif self.package.lower() == other.package.lower():
            if self.invitee_name.lower() < other.invitee_name.lower():
                return True
            elif self.invitee_name.lower() == other.invitee_name.lower():
                if self.date < other.date:
                    return True
                else:
                    return False
            else:
                return False
        else:
            return False


"""
The various data classes below with "Output" in their name are used to list the database contents for development and 
debugging when the collaborate page is loaded with the "dev" parameter.
"""

@dataclass()
class CollaborationOutput:
    collab_id: int
    owner_id: int
    collaborator_id: int
    package_id: int


@dataclass()
class GroupCollaborationOutput:
    group_collab_id: int
    owner_id: int
    user_group_id: int
    package_id: int


@dataclass()
class UserOutput:
    user_id: int
    user_login: str
    active_package_id: int


@dataclass()
class PackageOutput:
    package_id: int
    owner_login: str
    package_name: str


@dataclass()
class LockOutput:
    owner: str
    package_name: str
    locked_by: str
    timestamp: datetime


@dataclass()
class GroupLockOutput:
    group_lock_id: int
    package_id: int
    locked_by_id: int
