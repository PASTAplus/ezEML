import os
import os.path


def path_exists(path):
    if path is not None:
        return os.path.exists(path)
    return False


def path_isdir(path):
    if path is not None:
        return os.path.isdir(path)
    return False


def path_join(*paths):
    for path in paths:
        if path is None:
            return None
    return os.path.join(*paths)


def remove(path):
    if path is not None:
        os.remove(path)


def null_string(s):
    if s is None:
        return True
    return s.isspace() or len(s) == 0