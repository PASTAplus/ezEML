
class ezEMLError(Exception):
    pass


class ezEMLXMLError(ezEMLError):
    pass


class ezEMLXMLParseError(ezEMLXMLError):
    pass


class ezEMLXMLParsePruned(ezEMLXMLError):
    def __init__(self, pruned):
        self.pruned = pruned


class ezEMLXMLParsePruneError(ezEMLXMLError):
    pass


class ezEMLXMLParsePruneFailure(ezEMLXMLError):
    pass


class ezEMLErrorCreatingUploadDirectory(ezEMLError):
    pass


class ezEMLUnableToRetrieveMetadata(ezEMLError):
    pass


class ezEMLAttemptToAccessNonPASTAData(ezEMLError):
    pass

class ezEMLUnableToRetrieveDataEntity(ezEMLError):
    pass




