import base64
from datetime import datetime
import hashlib
import json
import os

from webapp.config import Config


def decode_jwt(token):
    try:
        # Split the JWT into its three parts: header, payload, signature
        header, payload, signature = token.split('.')

        # Decode Base64Url for header and payload
        def decode_base64(data):
            # Add padding if necessary
            data += '=' * (4 - len(data) % 4) if len(data) % 4 else ''
            return base64.urlsafe_b64decode(data).decode('utf-8')

        # Decode header and payload
        decoded_header = decode_base64(header)
        decoded_payload = decode_base64(payload)

        # Parse JSON
        header_json = json.loads(decoded_header)
        payload_json = json.loads(decoded_payload)

        return {
            'header': header_json,
            'payload': payload_json,
            'signature': signature  # Signature is not decoded as it's not Base64-encoded JSON
        }

    except Exception as e:
        return {'error': f'Invalid JWT: {str(e)}'}


def decode_edi_token(edi_token):
    jwt = decode_jwt(edi_token)
    return jwt.get('payload')


def get_linked_ezeml_accounts(edi_token):

    def get_ezeml_account_contents(profile):
        uid = profile.get('idpUid')
        if uid:
            idp_cname = profile.get('idpCommonName', '')
            idp_name = profile.get('idpName', '')
            if idp_name == 'ldap':
                idp_name = 'EDI'
            else:
                idp_name = idp_name.capitalize()
            user_name = idp_cname
            auth_common_name = (profile.get('commonName', '') or profile.get('cn', '')).strip()
            uid_hash = hashlib.md5(uid.encode("utf-8")).hexdigest()
            user_name_clean = user_name.strip().replace(" ", "_")
            user_login = user_name_clean + "-" + uid_hash
            # See if there exists an ezEML user account for this user_login
            user_dir = f'{Config.USER_DATA_DIR}/{user_login}'
            ezeml_docs = []
            if os.path.exists(user_dir):
                # Create a list of ezEML documents in the user dir
                try:
                    folder_contents = os.listdir(user_dir)
                    only_files = [f for f in folder_contents if os.path.isfile(os.path.join(user_dir, f))]
                    if only_files:
                        for filename in only_files:
                            if filename and filename.endswith('.xml'):
                                package_id = os.path.splitext(filename)[0]
                                date_modified = datetime.fromtimestamp(
                                    os.path.getmtime(os.path.join(user_dir, filename))).strftime('%Y-%m-%d %H:%M:%S')
                                ezeml_docs.append((package_id, date_modified))
                except Exception as e:
                    pass
            return ((user_login, idp_cname, idp_name, auth_common_name, uid, ezeml_docs))
        else:
            return None

    edi_jwt = decode_edi_token(edi_token)
    ezeml_accounts = []
    # First, the principal user profile
    if ezeml_account := get_ezeml_account_contents(edi_jwt):
        ezeml_accounts.append(ezeml_account)
    # Now, any linked user profiles
    links = edi_jwt.get('links')
    for link in links:
        if ezeml_account := get_ezeml_account_contents(link):
            ezeml_accounts.append(ezeml_account)
    return ezeml_accounts