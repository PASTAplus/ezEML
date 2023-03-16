from datetime import datetime
from dataclasses import dataclass
from flask import url_for
from flask_login import current_user

from webapp.pages import *
import webapp.views.collaborations.collaborations as collaborations


"""
CollaborationRecord is a dataclass that is used to represent a collaboration in a displayable form.
"""
@dataclass()
class CollaborationRecord:
    collab_id: int
    package_id: int
    package: str
    owner_id: int
    owner_login: str
    owner_name: str
    collaborator_id: int
    collaborator_login: str
    collaborator_name: str
    status: str
    locked_by_id: int
    locked_by: str
    action: str

    def __post_init__(self):
        current_user_login = current_user.get_user_org()
        self.owner_name = collaborations.display_name(self.owner_login)
        self.collaborator_name = collaborations.display_name(self.collaborator_login)
        if not self.locked_by_id:
            self.status = 'Available'
            if self.collaborator_login == current_user_login:
                link = url_for(PAGE_OPEN_BY_COLLABORATOR, collaborator_id=self.collaborator_id,
                               package_id=self.package_id)
                self.action = f'<a href="{link}">Open</a>'
        else:
            self.locked_by = collaborations._get_user(self.locked_by_id).user_login
            self.status = 'Locked by ' + collaborations.display_name(self.locked_by)
            if self.locked_by == current_user_login:
                link = url_for(PAGE_RELEASE_LOCK, package_id=self.package_id)
                self.action = f'<a href="{link}">Release lock</a>'
        # Only the owner can end a collaboration, and only if the owner currently has the lock.
        if current_user_login == self.owner_login and self.locked_by == current_user_login:
            link = url_for(PAGE_REMOVE_COLLABORATION, collab_id=self.collab_id)
            if len(self.action) > 0:
                self.action += '<br>'
            onclick = f"return confirm('Are you sure? This will end the collaboration for all participants and " \
                      f"cannot be undone.');"
            self.action += f'<a href="{link}" onclick="{onclick}">End collaboration</a>'

    def __lt__(self, other):
        if self.package < other.package:
            return True
        elif self.package == other.package:
            if self.owner_name < other.owner_name:
                return True
            elif self.owner_name == other.owner_name:
                if self.collaborator_name < other.collaborator_name:
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
