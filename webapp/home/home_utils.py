""" Basic utility functions. """

import sys
import daiquiri
from urllib.parse import urlparse, urlunparse, urlencode, parse_qs

from flask import session
from flask_login import current_user

import psutil
from pympler import muppy, summary, asizeof

from webapp.home.utils.hidden_buttons import is_hidden_button, handle_hidden_buttons
from webapp.config import Config

from metapype.model.node import Node

RELEASE_NUMBER = '2024.05.22'


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


def url_without_query_string(url):
    """
    Remove the query string from a URL.
    """
    # Parse the URL
    parsed_url = urlparse(url)

    # Construct the new URL without the query string
    new_url = urlunparse((
        parsed_url.scheme,
        parsed_url.netloc,
        parsed_url.path,
        parsed_url.params,
        '',
        parsed_url.fragment
    ))
    return new_url


def url_without_ui_element_id_query_string(url):
    # Parse the URL
    parsed_url = urlparse(url)

    # Parse the query string parameters
    query_params = parse_qs(parsed_url.query)

    # Remove the 'ui_element_id' parameter if it exists
    query_params.pop('ui_element_id', None)

    # Re-encode the query string without 'ui_element_id'
    new_query_string = urlencode(query_params, doseq=True)

    # Construct the new URL without the 'ui_element_id' parameter
    new_url = urlunparse((
        parsed_url.scheme,
        parsed_url.netloc,
        parsed_url.path,
        parsed_url.params,
        new_query_string,
        parsed_url.fragment
    ))
    return new_url


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


def log_available_memory(msg:str=None):
    """
    Log the available system memory.
    """
    if not Config.LOG_MEMORY_USAGE:
        return
    if msg:
        log_info(msg)
    available_memory = psutil.virtual_memory().available / 1024 / 1024
    process_usage = psutil.Process().memory_info().rss / 1024 / 1024
    log_info(f"Memory usage:   available system memory:{available_memory:.1f} MB   process usage:{process_usage:.1f} MB")


# def profile_and_save(func, *args, **kwargs):
#     # Profile the function and get memory usage
#     mem_usage = memory_usage((func, args, kwargs))
#
#     # Save the results to a file
#     with open('memory_profile.txt', 'a') as file:
#         file.write("Memory usage (in MB):\n")
#         for point in mem_usage:
#             file.write(f"{point}\n")
#
#
# def profile_and_save_with_return(func, *args, **kwargs):
#     # Function to wrap the original function and capture its return value
#     def wrapper():
#         return func(*args, **kwargs)
#
#     # Profile the memory usage of the wrapper function
#     mem_usage, retval = memory_usage((wrapper,), retval=True, max_usage=True)
#
#     # Save the memory usage data to a file
#     with open('memory_profile.txt', 'w') as file:
#         file.write("Memory usage (in MB):\n")
#         file.write(f"{mem_usage}\n")
#
#     # Return the original function's return value
#     return retval


def log_profile_details(all_objects_before, all_objects_after):
    ids_before = {id(obj) for obj in all_objects_before}
    ids_after = {id(obj) for obj in all_objects_after}

    # Find new object IDs
    new_ids = ids_after - ids_before

    # Retrieve new objects
    new_objects = [obj for obj in all_objects_after if id(obj) in new_ids]

    # Optionally, filter by type (e.g., list)
    new_lists = [obj for obj in new_objects if isinstance(obj, list)]

    # Sort by size and save the results to a file
    # original_stdout = sys.stdout
    with open('memory_profile.txt', 'a') as file:
        sys.stdout = file
        file.write("*********** Details ***********\n")
        obj = new_lists[0]
        print(f"List size: {asizeof.asizeof(obj)} bytes, Length: {len(obj)}, Example content: {str(obj[:10])}...")

        for obj in sorted(new_lists, key=lambda x: asizeof.asizeof(x), reverse=True)[:5]:
            print(f"List size: {asizeof.asizeof(obj)} bytes, Length: {len(obj)}, Example content: {str(obj[:10])}...")
        file.write("*********** End of details ***********\n")
        # sys.stdout = original_stdout


def profile_and_save(func, *args, **kwargs):
    # Profile the function and get memory usage

    # Start tracking memory
    all_objects_before = muppy.get_objects()
    summary_1 = summary.summarize(all_objects_before)

    # Execute the function
    retval = func(*args, **kwargs)

    # Check memory after the function execution
    all_objects_after = muppy.get_objects()
    summary_2 = summary.summarize(all_objects_after)

    # Compare before and after snapshots
    diff = summary.get_diff(summary_1, summary_2)

    original_stdout = sys.stdout

    try:
        # Save the results to a file
        with open('memory_profile.txt', 'a') as file:
            sys.stdout = file
            file.write(f"*********** Summary of memory usage: ***********\n")
            summary.print_(diff)
            file.write("*********** End of summary ***********\n")

        # Log details about the new objects
        # log_profile_details(all_objects_before, all_objects_after)
    except Exception as e:
        log_error(f"Error writing memory profile: {e}")
        raise
    finally:
        sys.stdout = original_stdout

    return retval





