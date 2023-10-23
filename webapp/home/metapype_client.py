"""
Formerly, there was a very large metapype_client.py file that contained a large variety of code for
interacting with metapype in various ways, plus a bunch of other miscellaneous code.

This file was split into several files. Deleting the file altogether had one unfortunate side effect,
however.

The VariableType enum was defined in metapype_client.py, and it was referenced by the pickle file
__uploaded_table_properties__.pkl in user-data. Pickle files incorporate the module path of the enum,
so moving the enum to a different file caused the pickle file to break.

A more robust solution would be to use a different serialization format, but for now, we'll just
keep the enum here.
"""

from enum import Enum

class VariableType(Enum):
    """
    The four variable types represented in ezEML.

    ezEML makes no distinction between ratio and interval variables -- both are represented as NUMERICAL.
    Similarly, ezEML makes no distinction between ordinal and nominal variables -- both are represented as either
    CATEGORICAL or TEXT depending on whether they have enumeratedDomain or textDomain children.
    """
    CATEGORICAL = 1
    DATETIME = 2
    NUMERICAL = 3
    TEXT = 4