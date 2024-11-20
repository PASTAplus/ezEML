import re
import unicodedata

def sanitize_filename(value):
    """
    Sanitize a string to make it safe for use as a filename.

    Parameters:
    value (str): The original string.

    Returns:
    str: A sanitized string safe for filenames.
    """
    # Normalize the string to remove accents and special characters
    value = unicodedata.normalize('NFKD', value)
    value = value.encode('ascii', 'ignore').decode('ascii')

    # Replace invalid characters with an underscore
    value = re.sub(r'[<>:"/\\|?*]', '_', value)

    # Remove any remaining non-word characters (except spaces and hyphens)
    value = re.sub(r'[^\w\s-]', '', value)

    # Replace spaces and hyphens with a single underscore
    value = re.sub(r'[\s-]+', '_', value)

    # Trim leading and trailing underscores
    value = value.strip('_')

    return value
