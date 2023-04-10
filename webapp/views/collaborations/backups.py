from datetime import datetime
import os
from pathlib import Path
from shutil import copyfile

from webapp.auth.user_data import get_user_folder_name
from webapp.config import Config

import webapp.views.collaborations as collaborations

def save_backup(package_id):
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
    backup_filename = f'{os.path.join(collaboration_backups_folder_name, filename)}.{timestamp}'
    copyfile(filepath, backup_filename)
