""" Basic utility functions. """

import sys, daiquiri

from flask import session
from flask_login import current_user

from metapype.model.node import Node

RELEASE_NUMBER = '2023.11.01'


def extract_caller_module_name():
    """
    Extract the name of the module that called the function that called this function.
    """
    f = sys._getframe(2).f_code.co_filename
    # We want to keep the path, starting with 'webapp'
    index = f.find('webapp')
    f = f[index:]
    f = f.replace('/', '.')[:-3]
    return f


def log_error(msg):
    """
    Log an error message. Include the path to the calling module in the log message. If the current user is logged in,
    also include the username in the log message. The idea is that this can be called from anywhere, but it still logs
    the module that called it.
    """
    logger = daiquiri.getLogger(extract_caller_module_name())
    if current_user and hasattr(current_user, 'get_username'):
        logger.error(msg, USER=current_user.get_username())
    else:
        logger.error(msg)


def log_info(msg):
    """
    Log an info message. Include the path to the calling module in the log message. If the current user is logged in,
    also include the username in the log message. The idea is that this can be called from anywhere, but it still logs
    the module that called it.
    """
    logger = daiquiri.getLogger(extract_caller_module_name())
    if current_user and hasattr(current_user, 'get_username'):
        logger.info(msg, USER=current_user.get_username())
    else:
        logger.info(msg)


def get_check_metadata_status(eml_node:Node=None, filename:str=None):
    """
    Get the status of the metadata check and save it in the session variable.
    """
    import webapp.home.check_metadata as check_metadata
    errors, warnings = check_metadata.check_metadata_status(eml_node, filename)
    if errors > 0:
        status = "red"
    elif warnings > 0:
        status = "yellow"
    else:
        status = "green"
    session["check_metadata_status"] = status
    return status


