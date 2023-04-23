from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from flask import url_for
from flask_login import current_user

from webapp.pages import *
import webapp.views.collaborations.collaborations as collaborations


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
    locked_by_id: int
    locked_by: str
    status_str: str
    action_str: str

    def update_action_str(self, action_str):
        if len(self.action_str) > 0:
            self.action_str += '<br>'
        self.action_str += action_str

    def __post_init__(self):
        current_user_login = current_user.get_user_org()
        current_user_id = collaborations.get_user(current_user_login).user_id
        self.owner_name = collaborations.display_name(self.owner_login)
        self.collaborator_name = collaborations.display_name(self.collaborator_login)

        is_group_entry = self.collaborator_login.endswith('-group_collaboration')
        # if is_group_entry:
        #     self.locked_by = self.collaborator_login
        # else:
        if self.locked_by_id is not None:
            self.locked_by = collaborations._get_user(self.locked_by_id).user_login

        # Status
        if self.lock_status == collaborations.LockStatus.NOT_LOCKED:
            self.status_str = 'Available'

        if self.lock_status == collaborations.LockStatus.LOCKED_BY_LOGGED_IN_USER:
            if not is_group_entry or \
                    self.collaboration_case == collaborations.CollaborationCase.LOGGED_IN_USER_IS_OWNER_COLLABORATOR_IS_GROUP:
                self.status_str = 'In use by ' + collaborations.display_name(self.locked_by)
            else:
                # The group lock is available
                self.status_str = 'Available'

        if self.lock_status == collaborations.LockStatus.LOCKED_BY_ANOTHER_USER:
            self.status_str = 'In use by ' + collaborations.display_name(self.locked_by)
            # If the collaborator is not a group member, we want to show the status as locked by the group
            group_collaboration = collaborations._get_group_collaboration(self.collab_id)
            if group_collaboration:
                if not collaborations.is_group_member(self.collaborator_login, self.collab_id):
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

                group_collaboration = collaborations._get_group_collaboration(self.locked_by_id)
                if group_collaboration:
                    if not collaborations.is_group_member(self.collaborator_login, self.locked_by_id):
                        group_name = group_collaboration.user_group.user_group_name
                        self.status_str = f'In use by {group_name}'
            else:
                self.status_str = 'Available'

        if self.lock_status == collaborations.LockStatus.LOCKED_BY_GROUP_AND_LOGGED_IN_USER:
            if not is_group_entry:
                self.status_str = 'In use by ' + collaborations.display_name(self.locked_by)
            else:
                self.status_str = 'In use by ' + collaborations.display_name(self.collaborator_login)

        if self.lock_status == collaborations.LockStatus.LOCKED_BY_GROUP_AND_ANOTHER_USER:
            group_collaboration = collaborations._get_group_collaboration(self.locked_by_id)
            if group_collaboration:
                if not collaborations.is_group_member(self.collaborator_login, self.locked_by_id):
                    group_name = group_collaboration.user_group.user_group_name
                    self.status_str = f'In use by {group_name}'
                else:
                    self.status_str = 'In use by ' + collaborations.display_name(self.locked_by)

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
InvitationRecord is a dataclass that is used to represent an invitation in a displayable form.
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


@dataclass()
class CollaborationOutput:
    collab_id: int
    owner_id: int
    collaborator_id: int
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
