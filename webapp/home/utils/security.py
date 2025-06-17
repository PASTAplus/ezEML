"""
Routes for the home blueprint, and functions for initializing a session or a request, etc.
"""

import urllib
from flask import (
    flash, redirect, url_for
)

def validate_download_url(url, page):
    # Define a whitelist of allowed domains
    allowed_domains = {"ezeml-d.edirepository.org", "ezeml.edirepository.org", "pasta.lternet.edu"}

    # Validate the URL
    parsed_url = urllib.parse.urlparse(url)
    if not parsed_url.scheme or not parsed_url.netloc:
        flash("Invalid URL provided.", "error")
        return redirect(url_for(page))

    domain = parsed_url.netloc.split(':')[0]  # Extract domain without port
    if domain not in allowed_domains:
        flash(f"The URL's domain ({domain}) is not an allowed domain.", "error")
        return redirect(url_for(page))

    return url