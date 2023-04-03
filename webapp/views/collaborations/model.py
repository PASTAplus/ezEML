from datetime import datetime
from sqlalchemy.types import TypeDecorator, String

from webapp import db

"""
Within this module, user_id refers to the database ID of the user, not the ezEML login ID. 
The latter is called user_login. Functions that take a user_id as a parameter are intended to be called
internally, within this module, with just a couple of exceptions. Functions that take a user_login as a 
parameter are provided to be called from other modules. To help enforce this convention, names of functions 
that take user_id as a parameter and are intended to be used internally are prefixed with an underscore.

We use the following conventions:
    user_id: database ID of a user
    user_login: ezEML login ID of a user (e.g., 'EDI-1a438b985e1824a5aa709daa1b6e12d2')
    package_id: database ID of a package
    package_name: name of a package
    owner_id: database ID of the owner of a package
    owner_login: ezEML login ID of the owner of a package
    collaborator_id: database ID of a collaborator on a package
    collaborator_login: ezEML login ID of a collaborator on a package

To get the user_login for the currently logged in user, use current_user.get_user_org().
"""

# Database models


class User(db.Model):
    user_id = db.Column(db.Integer, primary_key=True)
    user_login = db.Column(db.String(1024), unique=True, nullable=False)
    active_package_id = db.Column(db.Integer, db.ForeignKey('package.package_id'), nullable=True)

    def __repr__(self):
        return f'<User {self.user_id} {self.user_login} {self.active_package_id}>'


class UserGroup(db.Model):
    user_group_id = db.Column(db.Integer, primary_key=True)
    user_group_name = db.Column(db.String(1024), unique=True, nullable=False)

    def __repr__(self):
        return f'<UserGroup {self.user_group_id}>'


class UserGroupMembership(db.Model):
    user_group_membership_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    user_group_id = db.Column(db.Integer, db.ForeignKey('user_group.user_group_id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('user_id', 'user_group_id', name='_user_user_group_uc'),)

    user = db.relationship('User', foreign_keys=[user_id])

    def __repr__(self):
        return f'<UserGroupMembership {self.user_group_membership_id} {self.user_id} {self.user_group_id}>'


class Package(db.Model):
    package_id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    package_name = db.Column(db.String(1024), unique=False, nullable=False)
    # package_name may be non-unique, but the (owner_id, package_name) pair must be unique
    __table_args__ = (db.UniqueConstraint('owner_id', 'package_name', name='_owner_package_uc'),)

    owner = db.relationship('User', foreign_keys=[owner_id])

    def __repr__(self):
        return f'<Package {self.package_id} {self.owner_id} {self.package_name}>'


class GroupCollaboration(db.Model):
    group_collab_id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    user_group_id = db.Column(db.Integer, db.ForeignKey('user_group.user_group_id'), nullable=False)
    package_id = db.Column(db.Integer, db.ForeignKey('package.package_id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('user_group_id', 'package_id', name='_user_group_package_uc'),)

    owner = db.relationship('User', foreign_keys=[owner_id])
    user_group = db.relationship('UserGroup', foreign_keys=[user_group_id])
    package = db.relationship('Package', foreign_keys=[package_id])

    def __repr__(self):
        return f'<GroupCollaboration {self.group_collab_id} {self.user_group_id} {self.package_id}>'


class Collaboration(db.Model):
    collab_id = db.Column(db.Integer, primary_key=True)
    # owner_id is redundant, but it is needed to make the relationship work.
    owner_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    collaborator_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    package_id = db.Column(db.Integer, db.ForeignKey('package.package_id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('collaborator_id', 'package_id', name='_collaborator_package_uc'),)

    owner = db.relationship('User', foreign_keys=[owner_id])
    collaborator = db.relationship('User', foreign_keys=[collaborator_id])
    package = db.relationship('Package', foreign_keys=[package_id])

    def __repr__(self):
        return f'<Collaboration {self.collab_id} {self.collaborator_id} {self.package_id}>'


class Invitation(db.Model):
    invitation_id = db.Column(db.Integer, primary_key=True)
    inviter_id = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    inviter_name = db.Column(db.String(1024), unique=False, nullable=False)
    inviter_email = db.Column(db.String(1024), unique=False, nullable=False)
    invitee_name = db.Column(db.String(1024), unique=False, nullable=False)
    invitee_email = db.Column(db.String(1024), unique=False, nullable=False)
    package_id = db.Column(db.Integer, db.ForeignKey('package.package_id'), nullable=False)
    invitation_code = db.Column(db.String(4), unique=True, nullable=False)
    date = db.Column(db.DateTime, nullable=False)

    inviter = db.relationship('User', foreign_keys=[inviter_id])
    package = db.relationship('Package', foreign_keys=[package_id])

    def __repr__(self):
        return f'<Invitation {self.invitation_id} {self.inviter_id} {self.inviter_name}' \
               f' {self.inviter_email} {self.invitee_name} {self.invitee_email}' \
               f' {self.package_id} {self.invitation_code} {self.date}>'


class CollaborationStatus(db.Model):
    collab_status_id = db.Column(db.Integer, primary_key=True)
    collab_id = db.Column(db.Integer, db.ForeignKey('collaboration.collab_id'), unique=True, nullable=False)
    status = db.Column(db.String(32), unique=False, nullable=False)

    def __repr__(self):
        return f'<CollaborationStatus {self.collab_status_id} {self.collab_id} {self.status}>'


class UTCDateTime(TypeDecorator):
    """
    SQLite does not save tzinfo, but we want to store the timestamp in UTC. So, we use the following workaround courtesy of
    ChatGPT.
    """
    impl = String

    def process_bind_param(self, value, dialect):
        if value is not None:
            return value.isoformat()
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            return datetime.fromisoformat(value)
        return None


class GroupLock(db.Model):
    group_lock_id = db.Column(db.Integer, primary_key=True)
    package_id = db.Column(db.Integer, db.ForeignKey('package.package_id'), unique=True, nullable=False)
    locked_by = db.Column(db.Integer, db.ForeignKey('user_group.user_group_id'), nullable=False)

    package = db.relationship('Package', foreign_keys=[package_id])
    locked_by_group = db.relationship('UserGroup', foreign_keys=[locked_by])

    def __repr__(self):
        return f'<GroupLock {self.group_lock_id} {self.package_id} {self.locked_by}>'


class Lock(db.Model):
    """
    Note that Lock does not have a collab_id field. This is because a package may be opened before any collaboration
    exists for it, and we still want to be able to lock it. So, the lock is associated with the package, i.e., the
    (owner_id, package_name) pair, not a collaboration.
    """
    lock_id = db.Column(db.Integer, primary_key=True)
    package_id = db.Column(db.Integer, db.ForeignKey('package.package_id'), unique=True, nullable=False)
    locked_by = db.Column(db.Integer, db.ForeignKey('user.user_id'), nullable=False)
    timestamp = db.Column(db.DateTime, unique=False, nullable=False)
    comment = db.Column(db.String(128), unique=False, nullable=True)

    package = db.relationship('Package', foreign_keys=[package_id])

    @property
    def owner_id(self):
        try:
            return self.package.owner_id
        except Exception:
            return None

    @owner_id.setter
    def owner_id(self, value):
        self.package.owner_id = value

    @property
    def owner(self):
        try:
            return self.package.owner
        except:
            return None

    @owner.setter
    def owner(self, value):
        self.package.owner = value

    def __repr__(self):
        return f'<Lock {self.lock_id} {self.package_id} {self.locked_by} {self.timestamp}>'

