"""
Routes for the home blueprint, and functions for initializing a session or a request, etc.
"""
import os
import urllib
from flask import (
    flash, redirect, url_for
)
from webapp.config import Config
from webapp.home.exceptions import InvalidFilename


def validate_download_url(url):
    # Define a whitelist of allowed domains
    allowed_domains = Config.ALLOWED_DOWNLOAD_DOMAINS

    # Define a safe base directory for local files
    allowed_file_base = Config.BASE_DIR

    parsed_url = urllib.parse.urlparse(url)

    # Case 1: Allow file:// URLs, but restrict to a safe base directory
    if parsed_url.scheme == "file":
        local_path = os.path.abspath(os.path.join(parsed_url.netloc, parsed_url.path))
        if not local_path.startswith(allowed_file_base):
            flash(f"Local file access is not allowed outside {Config.BASE_DIR}.", "error")
            return None
        return url

    # Case 2: Regular HTTP(S) URLs
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        flash("Invalid URL provided.", "error")
        return None

    domain = parsed_url.netloc.split(":")[0]
    if domain not in allowed_domains:
        flash(f"The URL's domain ({domain}) is not an allowed domain.", "error")
        return None

    return url


def validate_user_data_path(pathname):
    """
    Check that a path actually points to a directory in the user data tree.
    """
    path = os.path.normpath(pathname)
    local_path = os.path.abspath(path)
    if not local_path.startswith(Config.USER_DATA_DIR):
        raise PermissionError(f"Access to directory '{pathname}' is not allowed.")
    return local_path


def validate_filename(filename: str) -> str:
    """
    Validate filename to prevent path traversal and other security issues on Linux.
    Returns the safe filename or raises ValueError.
    """
    if not filename or not filename.strip():
        raise InvalidFilename("Filename cannot be empty or whitespace-only.")

    filename = filename.strip()

    # Disallow null bytes
    if '\x00' in filename:
        raise InvalidFilename(f'Filename "{filename}" contains a null byte and is not allowed.')

    # Disallow absolute paths
    if filename.startswith('/'):
        raise InvalidFilename(f'Absolute paths are not allowed: "{filename}"')

    # Normalize the path to catch obfuscated traversal attempts
    normalized = os.path.normpath(filename)

    # Check for path traversal in directory portion
    path = os.path.dirname(normalized)
    if '..' in path:
        raise InvalidFilename(f'Path traversal detected in filename: "{filename}"')

    # Check if normalization revealed an absolute path
    if normalized.startswith('/'):
        raise InvalidFilename(f'Path traversal detected in filename: "{filename}"')

    return filename
