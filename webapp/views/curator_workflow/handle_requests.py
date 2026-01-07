
import base64
from enum import Enum
import requests
import time

from flask_login import current_user

from webapp.auth.edi_token import decode_edi_token
from webapp.config import Config
from webapp.home.home_utils import log_error, log_info
import webapp.home.exceptions as exceptions

PASTA_DEVELOPMENT_URL = "https://pasta-d.lternet.edu/package"
PASTA_STAGING_URL = "https://pasta-d.lternet.edu/package"  # TEMP set to dev
PASTA_PRODUCTION_URL = "https://pasta-s.lternet.edu/package"  # TEMP set to staging

class PastaEnvironment(Enum):
    DEVELOPMENT = 0
    STAGING = 1
    PRODUCTION = 2

pasta_url_lut = {
    PastaEnvironment.DEVELOPMENT: Config.PASTA_DEVELOPMENT_URL,
    PastaEnvironment.STAGING: Config.PASTA_STAGING_URL,
    PastaEnvironment.PRODUCTION: Config.PASTA_PRODUCTION_URL
}

portal_url_lut = {
    PastaEnvironment.DEVELOPMENT: Config.PORTAL_DEVELOPMENT_URL,
    PastaEnvironment.STAGING: Config.PORTAL_STAGING_URL,
    PastaEnvironment.PRODUCTION: Config.PORTAL_PRODUCTION_URL
}

def authenticate_for_workflow(pasta_url):
    """
    If the user is an EDI curator, we re-authenticate so the token won't time out.
    Otherwise, we use the cached auth_token for the user -- which may time out, but we want the user's actions
    to be taken under their identity.
    """
    if not current_user.is_edi_curator():
        auth_token = user_data.get_auth_token()
        # See if auth_token has expired
        auth_decoded = base64.b64decode(auth_token.split('-')[0]).decode('utf-8')
        expiry = int(auth_decoded.split('*')[2])
        edi_token = user_data.get_edi_token()
        if edi_token:
            edi_token_decoded = decode_edi_token(edi_token)
            expiry = int(edi_token_decoded.get('exp', expiry))
        current_time = int(time.time())
        if expiry < current_time:
            log_info(f'auth_decoded:{auth_decoded}')
            log_info(f'expiry:{expiry}  current_time:{current_time}')
            log_error('raising exceptions.AuthTokenExpired')
            raise exceptions.AuthTokenExpired('')

        if edi_token:
            return {'auth-token': auth_token,
                    'edi-token': edi_token}
        else:
            return {'auth-token': auth_token}

    # EDI curator. Setup user credentials for EDI user.
    dn = f'uid={Config.EZEML_DATA_ACCESS_LDAP_USER},o=EDI,dc=edirepository,dc=org' # distinguished name
    pw = Config.EZEML_DATA_ACCESS_LDAP_PASSWORD
    url = f"{pasta_url}/eml"

    # Perform HTTP basic authentication and pull token from cookie
    try:
        response = requests.get(url, auth=(dn,pw))
        response.raise_for_status()
        auth_token = response.cookies['auth-token']
        # Whether the edi-token is present depends on whether we're connecting to "old" auth or "new" auth
        try:
            edi_token = response.cookies['edi-token']
            cookies = {'auth-token': auth_token,
                       'edi-token': edi_token}
        except Exception as e:
            cookies = {'auth-token': auth_token}
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
    r = requests.post(f"{pasta_url}/reservations/eml/{scope}", cookies=authenticate_for_workflow(pasta_url))
    return r.status_code, r.text


def delete_reservation(pasta_environment: PastaEnvironment, scope: str, identifier: str):
    pasta_url = url_for_environment(pasta_environment)
    r = requests.delete(f"{pasta_url}/reservations/eml/{scope}/{identifier}", cookies=authenticate_for_workflow(pasta_url))
    return r.status_code, r.text


def check_existence(pasta_environment: PastaEnvironment, scope:str, identifier: str, revision: str=None):
    pasta_url = url_for_environment(pasta_environment)
    if revision:
        r = requests.get(f"{pasta_url}/eml/{scope}/{identifier}/{revision}",
                         cookies=authenticate_for_workflow(pasta_url))
    else:
        r = requests.get(f"{pasta_url}/eml/{scope}/{identifier}",
                         cookies=authenticate_for_workflow(pasta_url))
    return r.status_code, r.text


import os
import webapp.auth.user_data as user_data
from webapp.home.utils.load_and_save import get_pathname, load_eml, save_both_formats

def evaluate_upload_data_package(pasta_environment: PastaEnvironment, upload: bool=False, pid: str=None):
    pasta_url = url_for_environment(pasta_environment)
    if not upload:
        url = f'{pasta_url}/evaluate/eml'
        request = requests.post
    elif pid:
        # Whether we PUT or POST depends on whether we're updating or creating. Just looking at the revision
        #  number isn't good enough to determine which case it is. We check with PASTA to see if the package
        #  exists.
        scope, identifier, revision = pid.split('.')
        status, text = check_existence(pasta_environment, scope, identifier)
        if 200 <= status < 300:
            # Updating an existing package
            url = f'{pasta_url}/eml/{scope}/{identifier}'
            request = requests.put
        else:
            # Inserting a new package
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
                cookies = authenticate_for_workflow(pasta_url)
            )
            return r.status_code, r.text

    log_error(f'evaluate_upload_data_package  not returning a value - '
              f'{PastaEnvironment[pasta_environment]} - upload={upload} - pid={pid}')
    return '999', 'evaluate_upload_data_package not returning a value'


def evaluate_data_package(pasta_environment: PastaEnvironment):
    return evaluate_upload_data_package(pasta_environment, upload=False)


def upload_data_package(pasta_environment: PastaEnvironment, pid: str=None):
    return evaluate_upload_data_package(pasta_environment, upload=True, pid=pid)


def get_error_report(pasta_environment: PastaEnvironment, eval_transaction_id: str):
    pasta_url = url_for_environment(pasta_environment)
    r = requests.get(
        f'{pasta_url}/error/eml/{eval_transaction_id}',
        cookies=authenticate_for_workflow(pasta_url)
    )
    return r.status_code, r.text


def get_evaluate_report(pasta_environment: PastaEnvironment, eval_transaction_id: str):
    pasta_url = url_for_environment(pasta_environment)
    r = requests.get(
        f'{pasta_url}/evaluate/report/eml/{eval_transaction_id}',
        cookies=authenticate_for_workflow(pasta_url)
    )
    return r.status_code, r.text


if __name__ == "__main__":
    # transaction_id = evaluate_data_package(PastaEnvironment.STAGING)
    # identifier = delete_reservation(PastaEnvironment.STAGING, 'edi', '1141')
    # identifier = create_reservation(PastaEnvironment.STAGING, 'edi')
    # identifier = delete_reservation(PastaEnvironment.STAGING, 'edi', identifier)
    pass