class Error(Exception):
    """Base class for exceptions in this module."""
    pass

class DataTableError(Error):

    def __init__(self, message):
        self.message = message

