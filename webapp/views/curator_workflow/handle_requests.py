
from enum import Enum
import requests

from webapp.config import Config
from webapp.home.home_utils import log_error, log_info

PASTA_DEVELOPMENT_URL = "https://pasta-d.lternet.edu/package"
PASTA_STAGING_URL = "https://pasta-d.lternet.edu/package"  # TEMP set to dev
PASTA_PRODUCTION_URL = "https://pasta-s.lternet.edu/package"  # TEMP set to staging

class PastaEnvironment(Enum):
    DEVELOPMENT = 0
    STAGING = 1
    PRODUCTION = 2

pasta_url_lut = {
    PastaEnvironment.DEVELOPMENT: PASTA_DEVELOPMENT_URL,
    PastaEnvironment.STAGING: PASTA_STAGING_URL,
    PastaEnvironment.PRODUCTION: PASTA_PRODUCTION_URL
}

PORTAL_DEVELOPMENT_URL = "https://portal-d.edirepository.org"
PORTAL_STAGING_URL = "https://portal-d.edirepository.org"  # TEMP set to dev
PORTAL_PRODUCTION_URL = "https://portal-s.edirepository.org"  # TEMP set to staging

portal_url_lut = {
    PastaEnvironment.DEVELOPMENT: PORTAL_DEVELOPMENT_URL,
    PastaEnvironment.STAGING: PORTAL_STAGING_URL,
    PastaEnvironment.PRODUCTION: PORTAL_PRODUCTION_URL
}

def authenticate(pasta_url):
    # Setup user credentials
    dn = f'uid={Config.EZEML_DATA_ACCESS_LDAP_USER},o=EDI,dc=edirepository,dc=org' # distinguished name
    pw = Config.EZEML_DATA_ACCESS_LDAP_PASSWORD
    url = f"{pasta_url}/eml"
    # url = 'https://pasta.lternet.edu/package/eml'

    # Perform HTTP basic authentication and pull token from cookie
    try:
        response = requests.get(url, auth=(dn,pw))
        response.raise_for_status()
        token = response.cookies['auth-token']
        cookies = {'auth-token': token}
        return cookies
    except requests.exceptions.RequestException as e:
        log_error(f'handle_requests.authenticate() raised {e}')
        return None

def url_for_environment(pasta_environment: PastaEnvironment):
    return pasta_url_lut[pasta_environment]


def portal_url_for_environment(pasta_environment: PastaEnvironment):
    return portal_url_lut[pasta_environment]


def create_reservation(pasta_environment: PastaEnvironment, scope: str):
    pasta_url = url_for_environment(pasta_environment)
    r = requests.post(f"{pasta_url}/reservations/eml/{scope}", cookies=authenticate(pasta_url))
    return r.status_code, r.text


def delete_reservation(pasta_environment: PastaEnvironment, scope: str, identifier: str):
    pasta_url = url_for_environment(pasta_environment)
    r = requests.delete(f"{pasta_url}/reservations/eml/{scope}/{identifier}", cookies=authenticate(pasta_url))
    return r.status_code, r.text


def check_existence(pasta_environment: PastaEnvironment, scope:str, identifier: str, revision: str):
    pasta_url = url_for_environment(pasta_environment)
    r = requests.get(f"{pasta_url}/eml/{scope}/{identifier}/{revision}", cookies=authenticate(pasta_url))
    return r.status_code, r.text


import os
import webapp.auth.user_data as user_data
from webapp.home.utils.load_and_save import get_pathname, load_eml, save_both_formats

def evaluate_upload_data_package(pasta_environment: PastaEnvironment, upload: bool=False, revision_of: str=None):
    pasta_url = url_for_environment(pasta_environment)
    if not upload:
        url = f'{pasta_url}/evaluate/eml'
        request = requests.post
    elif revision_of:
        substrs = revision_of.split('.')
        url = f'{pasta_url}/eml/{substrs[0]}/{substrs[1]}'
        request = requests.put
    else:
        url = f'{pasta_url}/eml'
        request = requests.post

    current_document = user_data.get_active_document()
    if current_document:
        # Force the document to be saved, so it gets cleaned
        eml_node = load_eml(filename=current_document)
        save_both_formats(filename=current_document, eml_node=eml_node)

        # Do the evaluation
        package_id = eml_node.attribute_value("packageId")
        user_folder = user_data.get_user_folder_name(current_user_directory_only=False)
        filename_xml = f'{current_document}.xml'
        pathname = f'{user_folder}/{filename_xml}'
        if os.path.exists(pathname):
            # Read the XML file
            with open(pathname, 'rb') as file:
                xml_data = file.read()

            # Set the headers
            headers = {'Content-Type': 'application/xml'}

            # Make the request
            r = request(
                url=url,
                headers=headers,
                data=xml_data,
                cookies = authenticate(pasta_url)
            )
            return r.status_code, r.text


def evaluate_data_package(pasta_environment: PastaEnvironment):
    return evaluate_upload_data_package(pasta_environment, upload=False)


def upload_data_package(pasta_environment: PastaEnvironment, revision_of: str=None):
    return evaluate_upload_data_package(pasta_environment, upload=True, revision_of=revision_of)


def get_error_report(pasta_environment: PastaEnvironment, eval_transaction_id: str):
    pasta_url = url_for_environment(pasta_environment)
    r = requests.get(
        f'{pasta_url}/error/eml/{eval_transaction_id}',
        cookies=authenticate(pasta_url)
    )
    return r.status_code, r.text


def get_evaluate_report(pasta_environment: PastaEnvironment, eval_transaction_id: str):
    pasta_url = url_for_environment(pasta_environment)
    r = requests.get(
        f'{pasta_url}/evaluate/report/eml/{eval_transaction_id}',
        cookies=authenticate(pasta_url)
    )
    return r.status_code, r.text


if __name__ == "__main__":
    # transaction_id = evaluate_data_package(PastaEnvironment.STAGING)
    # identifier = delete_reservation(PastaEnvironment.STAGING, 'edi', '1141')
    identifier = create_reservation(PastaEnvironment.STAGING, 'edi')
    identifier = delete_reservation(PastaEnvironment.STAGING, 'edi', identifier)
