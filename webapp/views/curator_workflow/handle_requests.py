
import base64
import binascii
from enum import Enum
import os
from pathlib import Path
import requests
import time
from typing import Optional

from flask_login import current_user

from webapp.auth.edi_token import decode_edi_token
import webapp.auth.user_data as user_data
from webapp.config import Config
from webapp.home.utils.load_and_save import load_eml, save_both_formats

from webapp.home.home_utils import log_error, log_info
import webapp.home.exceptions as exceptions

class PastaEnvironment(Enum):
    DEVELOPMENT = 0
    STAGING = 1
    PRODUCTION = 2

PASTA_URL_BY_ENV = {
    PastaEnvironment.DEVELOPMENT: Config.PASTA_DEVELOPMENT_URL,
    PastaEnvironment.STAGING: Config.PASTA_STAGING_URL,
    PastaEnvironment.PRODUCTION: Config.PASTA_PRODUCTION_URL
}

PORTAL_URL_BY_ENV = {
    PastaEnvironment.DEVELOPMENT: Config.PORTAL_DEVELOPMENT_URL,
    PastaEnvironment.STAGING: Config.PORTAL_STAGING_URL,
    PastaEnvironment.PRODUCTION: Config.PORTAL_PRODUCTION_URL
}

def url_for_environment(pasta_environment: PastaEnvironment) -> str:
    return PASTA_URL_BY_ENV[pasta_environment]


def portal_url_for_environment(pasta_environment: PastaEnvironment) -> str:
    return PORTAL_URL_BY_ENV[pasta_environment]


def authenticate_for_workflow(pasta_url: str) -> Optional[dict[str, str]]:
    """
    Return auth cookies for a PASTA workflow request.

    Non-curators use their cached credentials so actions occur under their identity.
    EDI curators authenticate with the configured service account.
    """
    if not current_user.is_edi_curator():
        auth_token = user_data.get_auth_token()
        edi_token = user_data.get_edi_token()
        edi_token_decoded = None

        if not auth_token:
            # This shouldn't happen
            raise exceptions.AuthTokenExpired("Missing auth token")

        # See if auth_token has expired
        try:
            auth_decoded = base64.b64decode(auth_token.split('-')[0]).decode('utf-8')
            expiry = int(auth_decoded.split('*')[2])
        except (ValueError, IndexError, UnicodeDecodeError, binascii.Error) as e:
            raise exceptions.AuthTokenExpired("Unable to parse auth token") from e

        if edi_token:
            edi_token_decoded = decode_edi_token(edi_token)
            expiry = int(edi_token_decoded.get('exp', expiry))

        current_time = int(time.time())
        if expiry < current_time:
            log_info(f"Auth token expired at {expiry}; current_time={current_time}")
            raise exceptions.AuthTokenExpired('')

        cookies = {"auth-token": auth_token}
        if edi_token:
            cookies["edi-token"] = edi_token
        return cookies

    # EDI curator. Setup user credentials for EDI user.
    dn = f'uid={Config.EZEML_DATA_ACCESS_LDAP_USER},o=EDI,dc=edirepository,dc=org' # distinguished name
    pw = Config.EZEML_DATA_ACCESS_LDAP_PASSWORD
    url = f"{pasta_url}/eml"

    # Perform HTTP basic authentication and pull token from cookie
    try:
        response = requests.get(url, auth=(dn,pw), timeout=(5, 30))
        response.raise_for_status()
        auth_token = response.cookies.get('auth-token')
        edi_token = response.cookies.get('edi-token')

        if not auth_token:
            raise exceptions.AuthTokenExpired("Missing auth-token cookie")

        cookies = {"auth-token": auth_token}
        if edi_token:
            cookies["edi-token"] = edi_token
        return cookies

    except requests.exceptions.RequestException as e:
        log_error(f'handle_requests.authenticate_for_workflow() raised {e}')
        return None


def url_for_environment(pasta_environment: PastaEnvironment):
    return PASTA_URL_BY_ENV[pasta_environment]


def portal_url_for_environment(pasta_environment: PastaEnvironment):
    return PORTAL_URL_BY_ENV[pasta_environment]


def create_reservation(pasta_environment: PastaEnvironment, scope: str):
    pasta_url = url_for_environment(pasta_environment)
    r = requests.post(f"{pasta_url}/reservations/eml/{scope}",
                      cookies=authenticate_for_workflow(pasta_url),
                      timeout=(5, 30))
    return r.status_code, r.text


def delete_reservation(pasta_environment: PastaEnvironment, scope: str, identifier: str):
    pasta_url = url_for_environment(pasta_environment)
    r = requests.delete(f"{pasta_url}/reservations/eml/{scope}/{identifier}",
                        cookies=authenticate_for_workflow(pasta_url),
                        timeout=(5, 30))
    return r.status_code, r.text


def check_existence(pasta_environment: PastaEnvironment, scope:str, identifier: str, revision: str=None):
    pasta_url = url_for_environment(pasta_environment)
    if revision:
        r = requests.get(f"{pasta_url}/eml/{scope}/{identifier}/{revision}",
                         cookies=authenticate_for_workflow(pasta_url),
                         timeout=(5, 30))
    else:
        r = requests.get(f"{pasta_url}/eml/{scope}/{identifier}",
                         cookies=authenticate_for_workflow(pasta_url),
                         timeout=(5, 30))
    return r.status_code, r.text


def evaluate_upload_data_package(pasta_environment: PastaEnvironment, upload: bool=False, pid: str=None):
    pasta_url = url_for_environment(pasta_environment)
    if not upload:
        url = f'{pasta_url}/evaluate/eml'
        request_func = requests.post
    elif pid:
        # Whether we PUT or POST depends on whether we're updating or creating. Just looking at the revision
        #  number isn't good enough to determine which case it is. We check with PASTA to see if the package
        #  exists.
        try:
            scope, identifier, _ = pid.split('.')
        except ValueError as e:
            raise ValueError(f"Invalid pid format: {pid!r}") from e
        status, _ = check_existence(pasta_environment, scope, identifier)
        if 200 <= status < 300:
            # Updating an existing package
            url = f'{pasta_url}/eml/{scope}/{identifier}'
            request_func = requests.put
        else:
            # Inserting a new package
            url = f'{pasta_url}/eml'
            request_func = requests.post

    current_document = user_data.get_active_document()
    if current_document:
        # Force the document to be saved, so it gets cleaned
        eml_node = load_eml(filename=current_document)
        save_both_formats(filename=current_document, eml_node=eml_node)

        # Do the evaluation
        package_id = eml_node.attribute_value("packageId")
        user_folder = user_data.get_user_folder_name(current_user_directory_only=False)

        pathname = Path(user_folder) / f'{current_document}.xml'
        if pathname.exists():
            xml_data = pathname.read_bytes()

            # Set the headers
            headers = {'Content-Type': 'application/xml'}

            # Make the request
            r = request_func(
                url=url,
                headers=headers,
                data=xml_data,
                cookies = authenticate_for_workflow(pasta_url),
                timeout=(5, 120)
            )
            return r.status_code, r.text

    log_error(f'evaluate_upload_data_package  not returning a value - '
              f'{pasta_environment.name} - upload={upload} - pid={pid}')
    return '999', 'evaluate_upload_data_package not returning a value'


def evaluate_data_package(pasta_environment: PastaEnvironment):
    return evaluate_upload_data_package(pasta_environment, upload=False)


def upload_data_package(pasta_environment: PastaEnvironment, pid: str=None):
    return evaluate_upload_data_package(pasta_environment, upload=True, pid=pid)


def get_error_report(pasta_environment: PastaEnvironment, eval_transaction_id: str):
    pasta_url = url_for_environment(pasta_environment)
    r = requests.get(
        f'{pasta_url}/error/eml/{eval_transaction_id}',
        cookies=authenticate_for_workflow(pasta_url),
        timeout=(5, 120)
    )
    return r.status_code, r.text


def get_evaluate_report(pasta_environment: PastaEnvironment, eval_transaction_id: str):
    pasta_url = url_for_environment(pasta_environment)
    r = requests.get(
        f'{pasta_url}/evaluate/report/eml/{eval_transaction_id}',
        cookies=authenticate_for_workflow(pasta_url),
        timeout=(5, 120)
    )
    return r.status_code, r.text


if __name__ == "__main__":
    # transaction_id = evaluate_data_package(PastaEnvironment.STAGING)
    # identifier = delete_reservation(PastaEnvironment.STAGING, 'edi', '1141')
    # identifier = create_reservation(PastaEnvironment.STAGING, 'edi')
    # identifier = delete_reservation(PastaEnvironment.STAGING, 'edi', identifier)
    pass