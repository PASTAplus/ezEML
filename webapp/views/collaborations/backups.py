from datetime import datetime
import os
from pathlib import Path
from shutil import copyfile
from urllib.parse import quote_plus, urlencode

from flask import (url_for)

from webapp.auth.user_data import get_user_folder_name
from webapp.config import Config

import webapp.views.collaborations as collaborations
from webapp.pages import *


def save_backup(package_id, primary=False):
    package = collaborations.model.Package.query.filter_by(package_id=package_id).first()
    if package is None:
        raise ValueError(f'Package {package_id} not found')

    package_name = package.package_name
    filename = f'{package_name}.json'

    user_folder = get_user_folder_name()
    filepath = os.path.join(user_folder, filename)
    if not os.path.exists(filepath):
        raise ValueError(f'File {filepath} not found')

    owner_login = package.owner.user_login
    collaboration_backups_folder_name = os.path.join(Config.USER_DATA_DIR, '__collaboration_backups', owner_login)
    Path(collaboration_backups_folder_name).mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().date().strftime('%Y_%m_%d') + '_' + datetime.now().time().strftime('%H_%M_%S')
    primary_str = '.primary' if primary else ''
    backup_filename = f'{os.path.join(collaboration_backups_folder_name, filename)}{primary_str}.{timestamp}'
    copyfile(filepath, backup_filename)


def format_datetime(str_date):
    substrs = str_date.split('_')
    return f'{substrs[0]}-{substrs[1]}-{substrs[2]}&nbsp;{substrs[3]}:{substrs[4]}'


def get_backups():
    collaboration_backups_folder_name = os.path.join(Config.USER_DATA_DIR, '__collaboration_backups')
    backups = []

    # Loop over all subfolders, i.e. user logins
    for owner_login in os.listdir(collaboration_backups_folder_name):
        user_backups_folder = os.path.join(collaboration_backups_folder_name, owner_login)
        if not os.path.isdir(user_backups_folder):
            continue

        # Loop over all files in the subfolder
        for filename in os.listdir(user_backups_folder):
            if '.json.' not in filename:
                continue

            owner_name = collaborations.collaborations.display_name(owner_login)

            pathname = os.path.join(user_backups_folder, filename)
            pathname = quote_plus(pathname)

            # Get the package name from the filename
            package_name = filename[:filename.find('.json.')]

            # Get the date from the filename
            date = filename.split('.')[-1]
            date = format_datetime(date)

            # Check if the backup is the primary backup
            is_primary = '&#x2713;' if '.primary.' in filename else ''

            link = url_for(PAGE_PREVIEW_BACKUP, filename=pathname)
            onclick = f"return confirm('Are you sure? This will open the backed up version in your own account " \
                      f"so you can take a look at it. If you want to restore the backed up version to the " \
                      f"owner\\'s ezEML account, use the Restore option instead.');"
            preview = f'<a href="{link}" onclick="{onclick}">Preview</a>'

            link = url_for(PAGE_RESTORE_BACKUP, filename=pathname, owner=owner_login)
            onclick = f"return confirm('Are you sure? Caution: this will overwrite the version in the owner\\'s " \
                      f"ezEML account with the backed up version. If you just want to take a look at the backed up " \
                      f"version using your own ezEML account, use the Preview option instead.');"
            restore = f'<a href="{link}" onclick="{onclick}">Restore</a>'

            link = url_for(PAGE_DELETE_BACKUP, filename=pathname)
            onclick = f"return confirm('Are you sure? This will permanently delete the backup and " \
                      f"cannot be undone.');"
            delete = f'<a href="{link}" onclick="{onclick}">Delete</a>'

            # Create the backup object
            backup = collaborations.data_classes.Backup(owner_login,
                                                        owner_name,
                                                        package_name,
                                                        date,
                                                        is_primary,
                                                        preview,
                                                        restore,
                                                        delete)
            backups.append(backup)
    return sorted(backups, key=lambda x: (x.owner_name, x.package_name, x.date))

