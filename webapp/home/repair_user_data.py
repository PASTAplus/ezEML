from datetime import datetime
import hashlib
import json
import os
import shutil

from webapp.config import Config
from webapp.views.collaborations.collaborations import change_user_login

REPAIR_LOG_FILE = '__repair_user_data.log'

def log_info(msg):
    with open(REPAIR_LOG_FILE, 'a') as f:
        f.write(msg + '\n')


def generate_ezeml_user_data_dirs(cname, uid, sub):
    """
    This function is used to generate the ezeml user data directories corresponding to the uid and sub values.
    :param uid: The user's unique identifier
    :param sub: The user's subject value
    """
    cname_clean = cname.replace(" ", "_")
    uid_hash = hashlib.md5(uid.encode("utf-8")).hexdigest()
    uid_dir = os.path.join(Config.USER_DATA_DIR, cname_clean + "-" + uid_hash)
    sub_hash = hashlib.md5(sub.encode("utf-8")).hexdigest()
    sub_dir = os.path.join(Config.USER_DATA_DIR, cname_clean + "-" + sub_hash)
    return uid_dir, sub_dir


def is_repair_needed(cname, idp, uid, sub):
    """
    This function is used to determine if the user data needs to be repaired.
    :param cname: The user's common name
    :param idp: The user's identity provider
    :param uid: The user's unique identifier
    :param sub: The user's subject value

    When a user logs in via some identity provider other than LDAP, we want to see if the user data needs to be repaired.
    The logic is as follows:
    - If the idp is not 'google', return status is False.
    - Else
        - Generate the ezeml user data directories corresponding to the uid and sub values.
        - If the sub-based dir doesn't exist, return status is False.
        - Otherwise, return status is True.

    Returns a tuple of three values:
    - A boolean indicating if the repair is needed.
    - The uid-based directory (or None if it doesn't exist).
    - The sub-based directory (or None if it doesn't exist).
    """
    current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_info(f"***** {current_datetime} ********************")
    log_info(f"is_repair_needed: {cname} {idp} {uid} {sub}")
    if idp != 'google':
        log_info('  returns False, None, None')
        return False, None, None
    uid_dir, sub_dir = generate_ezeml_user_data_dirs(cname, uid, sub)
    if not os.path.exists(sub_dir):
        log_info(f'  returns False, {uid_dir}, None')
        return False, uid_dir, None
    log_info(f'  returns True, {uid_dir}, {sub_dir}')
    return True, uid_dir, sub_dir


def copy_dir_to_backup(dir):
    """
    This function is used to copy a directory to the backup directory.
    :param dir: The directory to be copied
    """
    backup_dir = os.path.join(Config.USER_DATA_DIR, "__repair_user_data_backups", "uid_dirs")
    log_info(f"copy_dir_to_backup: {dir} {backup_dir}")
    copy_directory(dir, backup_dir)


def move_dir_to_backup(dir):
    """
    This function is used to move a directory to the backup directory.
    :param dir: The directory to be moved
    """
    backup_dir = os.path.join(Config.USER_DATA_DIR, "__repair_user_data_backups", "sub_dirs")
    log_info(f"move_dir_to_backup: {dir} {backup_dir}")
    move_directory(dir, backup_dir)


def copy_sub_dir_to_uid_dir(sub_dir, uid_dir):
    """
    This function is used to copy the sub directory to the uid directory.
    :param sub_dir: The sub directory to be copied
    :param uid_dir: The uid directory to which the sub directory is copied
    """
    log_info(f"copy_sub_dir_to_uid_dir: {sub_dir} {uid_dir}")
    shutil.copytree(sub_dir, uid_dir, dirs_exist_ok=True)


def merge_sub_dir_to_uid_dir(sub_dir, uid_dir):
    """
    This function is used to merge the sub directory into the uid directory.
    :param sub_dir: The sub directory to be merged
    :param uid_dir: The uid directory into which the sub directory is merged

    Assumes that the sub directory exists and the uid directory exists.
    """
    log_info(f"merge_sub_dir_to_uid_dir: {sub_dir} {uid_dir}")
    copy_dir_to_backup(uid_dir)
    exclude = ["__user_properties__.json"]
    copy_files_with_exclusions(sub_dir, uid_dir, exclude)
    merge_user_properties(uid_dir, sub_dir)


def merge_user_properties(uid_dir, sub_dir):
    """
    This function is used to merge the __user_properties__.json files in the uid and sub directories into the uid directory.
    :param uid_dir: The uid directory
    :param sub_dir: The sub directory

    Assumes both directories exist, although the __user_properties__.json files may not.
    """
    def get_uploads(data1, data2):
        uploads_1 = set(map(tuple, data1.get('data_table_upload_filenames', [])))
        uploads_2 = set(map(tuple, data2.get('data_table_upload_filenames', [])))
        uploads = uploads_1.union(uploads_2)
        return sorted(list(map(list, uploads)))

    uid_path = os.path.join(Config.USER_DATA_DIR, uid_dir, '__user_properties__.json')
    sub_path = os.path.join(Config.USER_DATA_DIR, sub_dir, '__user_properties__.json')
    if not os.path.exists(uid_path) and os.path.exists(sub_path):
        shutil.copy(sub_path, uid_path)
        return
    if os.path.exists(uid_path) and not os.path.exists(sub_path):
        return
    if not os.path.exists(uid_path) and not os.path.exists(sub_path):
        return

    with open(uid_path, 'r') as uid_file:
        uid_data = json.load(uid_file)
    with open(sub_path, 'r') as sub_file:
        sub_data = json.load(sub_file)

    merged = {}
    merged['data_table_upload_filenames'] = get_uploads(uid_data, sub_data)
    merged['is_first_usage'] = uid_data.get('is_first_usage', False) and sub_data.get('is_first_usage', False)
    merged['new_to_badges'] = uid_data.get('new_to_badges', False) and sub_data.get('new_to_badges', False)
    merged['model_has_complex_texttypes'] = sub_data.get('model_has_complex_texttypes', False)
    merged['enable_complex_text_element_editing_global'] = uid_data.get('enable_complex_text_element_editing_global', False) or sub_data.get('enable_complex_text_element_editing_global', False)
    merged['enable_complex_text_element_editing_documents'] = uid_data.get('enable_complex_text_element_editing_documents', []) + sub_data.get('enable_complex_text_element_editing_documents', [])

    with open(uid_path, 'w') as uid_file:
        json.dump(merged, uid_file, indent=2)


def repair_user_data(cname, idp, uid, sub):
    """
    This function is used to repair the user data.
    :param cname: The user's common name
    :param idp: The user's identity provider
    :param uid: The user's unique identifier
    :param sub: The user's subject value

    When a user logs in via google, we may need to repair the user data.
    """
    # Determine if the user data needs to be repaired
    repair_needed, uid_dir, sub_dir = is_repair_needed(cname, idp, uid, sub)
    if repair_needed:
        if not os.path.exists(uid_dir):
            # We never created a directory based on the user's uid (email address), so we copy the sub-based directory
            #  to the uid-based directory.
            copy_sub_dir_to_uid_dir(sub_dir, uid_dir)
        else:
            # We have both the uid-based and sub-based directories, so we merge the sub-based directory into the
            #  uid-based directory.
            merge_sub_dir_to_uid_dir(sub_dir, uid_dir)
            # Fixup the collaborations database to use the uid-based login instead of the sub-based login
            log_info(f"change_user_login: {os.path.basename(sub_dir)} {os.path.basename(uid_dir)}")
            change_user_login(os.path.basename(sub_dir), os.path.basename(uid_dir))
        # Move the sub-based directory to the backup directory
        move_dir_to_backup(sub_dir)


def copy_directory(src, dst):
    # Check if the source directory exists
    if not os.path.exists(src):
        raise FileNotFoundError(f"Source directory {src} does not exist.")

    # Check if the destination directory exists, create it if it doesn't
    dst_path = os.path.join(dst, os.path.basename(src))
    if not os.path.exists(dst):
        os.makedirs(dst)

    # Copy the directory tree from src to dst
    shutil.copytree(src, dst_path, dirs_exist_ok=True)


def move_directory(src, dst):
    # Check if the source directory exists
    if not os.path.exists(src):
        raise FileNotFoundError(f"Source directory {src} does not exist.")

    if not os.path.isdir(dst):
        os.mkdir(dst)

    dst_path = os.path.join(dst, os.path.basename(src))

    # Move the directory
    shutil.move(src, dst_path)


def copy_files_with_exclusions(src, dst, exclude_files):
    # Check if the source directory exists
    if not os.path.exists(src):
        raise FileNotFoundError(f"Source directory {src} does not exist.")

    # Ensure the destination directory exists
    if not os.path.exists(dst):
        os.makedirs(dst)

    for root, dirs, files in os.walk(src):
        # Create corresponding directories in the destination
        for dir in dirs:
            dest_dir = os.path.join(dst, os.path.relpath(os.path.join(root, dir), src))
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir)

        # Copy files excluding those in the exclude_files list
        for file in files:
            if file not in exclude_files:
                src_file = os.path.join(root, file)
                dest_file = os.path.join(dst, os.path.relpath(src_file, src))
                shutil.copy2(src_file, dest_file)

