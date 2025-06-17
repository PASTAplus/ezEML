"""
Routes for the home blueprint, and functions for initializing a session or a request, etc.
"""
import os
import urllib
from flask import (
    flash, redirect, url_for
)
from webapp.config import Config

def validate_download_url(url, page):
    # Define a whitelist of allowed domains
    allowed_domains = {
        "ezeml-d.edirepository.org",
        "ezeml.edirepository.org",
        "pasta.lternet.edu"
    }

    # Define a safe base directory for local files
    allowed_file_base = Config.BASE_DIR

    parsed_url = urllib.parse.urlparse(url)

    # Case 1: Allow file:// URLs, but restrict to a safe base directory
    if parsed_url.scheme == "file":
        local_path = os.path.abspath(os.path.join(parsed_url.netloc, parsed_url.path))
        if not local_path.startswith(allowed_file_base):
            flash(f"Local file access is not allowed outside {Config.BASE_DIR}.", "error")
            return redirect(url_for(page))
        return url

    # Case 2: Regular HTTP(S) URLs
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        flash("Invalid URL provided.", "error")
        return redirect(url_for(page))

    domain = parsed_url.netloc.split(":")[0]
    if domain not in allowed_domains:
        flash(f"The URL's domain ({domain}) is not an allowed domain.", "error")
        return redirect(url_for(page))

    return url
