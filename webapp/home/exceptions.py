class ezEMLError(Exception):
    """Base class for exceptions in this module."""

    def __init__(self, message):
        self.message = message


class DataTableError(ezEMLError):
    pass


class MissingFileError(ezEMLError):
    pass
