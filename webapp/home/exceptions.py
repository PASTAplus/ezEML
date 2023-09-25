"""
Custom exceptions for ezEML.
"""

class ezEMLError(Exception):
    """Base class for exceptions in this module."""

    def __init__(self, message):
        self.message = message


class AuthTokenExpired(ezEMLError):
    pass


class DataTableError(ezEMLError):
    pass


class DeprecatedCodeError(ezEMLError):
    pass


class ExtraWhitespaceInColumnNames(ezEMLError):
    pass


class FileOpenError(ezEMLError):
    pass


class InternalError(ezEMLError):
    pass


class InvalidHeaderRow(ezEMLError):
    pass


class InvalidXMLError(ezEMLError):
    pass


class MetapypeStoreIsNonEmpty(ezEMLError):
    pass


class MissingFileError(ezEMLError):
    pass


class NumberOfColumnsHasChanged(ezEMLError):
    pass


class ReuploadTableNumColumnsError(ezEMLError):
    pass


class ReuploadTableColumnTypesError(ezEMLError):
    pass


class TaxonNotFound(ezEMLError):
    pass


class Unauthorized(ezEMLError):
    pass


class UnexpectedDataTypes(ezEMLError):
    pass


class UnicodeDecodeErrorInternal(ezEMLError):
    pass


class UnknownDistributionUrl(ezEMLError):
    pass


class CollaborationError(ezEMLError):
    def __init__(self, message, user_name=None, package_name=None):
        self.message = message
        self.user_name = user_name
        self.package_name = package_name
    pass


class CollaboratingWithGroupAlready(CollaborationError):
    pass


class InvitationNotFound(CollaborationError):
    pass


class InvitationBeingAcceptedByOwner(CollaborationError):
    pass


class LockHasTimedOut(CollaborationError):
    pass


class LockOwnedByAGroup(CollaborationError):
    pass


class LockOwnedByAnotherUser(CollaborationError):
    pass


class CollaborationDatabaseError(CollaborationError):
    pass


class UserIsNotTheOwner(CollaborationError):
    pass


class UserNotFound(CollaborationError):
    pass


