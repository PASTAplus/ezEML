class ezEMLError(Exception):
    """Base class for exceptions in this module."""

    def __init__(self, message):
        self.message = message


class AuthTokenExpired(ezEMLError):
    pass


class DataTableError(ezEMLError):
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


class InvitationNotFound(CollaborationError):
    pass


class InvitationBeingAcceptedByOwner(CollaborationError):
    pass


class LockHasTimedOut(CollaborationError):
    pass


class LockOwnedByAnotherUser(CollaborationError):
    pass


class CollaborationDatabaseError(CollaborationError):
    pass