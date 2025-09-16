import zipfile
import sys
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def extract_zip(zip_file, extract_to):
    """Extract a ZIP file to the specified directory."""
    try:
        logger.info(f"Extracting {zip_file} to {extract_to}")
        os.makedirs(extract_to, exist_ok=True)
        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
        logger.info("Extraction complete")
    except Exception as e:
        logger.error(f"Error extracting {zip_file}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 extract_zip.py <zip_file> <extract_to>")
        sys.exit(1)
    extract_zip(sys.argv[1], sys.argv[2])

