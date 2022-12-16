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