import os
import json
import sys
# from webapp.config import Config


def scan_directory(base_dir, subs_only=False, filter_cnames=None):
    # Get a sorted list of subdirectories
    subdirectories = sorted([d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))])
    found = []

    for subdir in subdirectories:
        subdir_path = os.path.join(base_dir, subdir)
        if filter_cnames and subdir.split('-')[0] not in filter_cnames:
            continue
        user_data_file = os.path.join(subdir_path, '__user_properties__.json')

        if os.path.exists(user_data_file):
            with open(user_data_file, 'r') as file:
                try:
                    data = json.load(file)
                    uid = data.get('uid', 'No uid found')
                    if subs_only:
                        try:
                            int(uid.strip())
                            found.append((subdir, uid))
                            # print(f"{subdir}\t{uid}")
                        except ValueError:
                            continue
                    else:
                        found.append((subdir, uid))
                        # print(f"{subdir}\t{uid}")
                except json.JSONDecodeError:
                    print(f"Subdirectory: {subdir}, Error: Invalid JSON in {user_data_file}")
    return found


if __name__ == '__main__':
    # Add the parent directory to the sys.path
    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    sys.path.insert(0, parent_dir)
    from config import Config
    base_directory = Config.USER_DATA_DIR
    found = scan_directory(base_directory)
    for subdir, uid in found:
        print(f"{subdir}\t{uid}")
    print('\n\n')
    found = scan_directory(base_directory, subs_only=True)
    for subdir, uid in found:
        print(f"{subdir}\t{uid}")
    print('\n\n')
    filter_cnames = []
    for subdir, uid in found:
        filter_cnames.append(subdir.split('-')[0])
    found = scan_directory(base_directory, filter_cnames=filter_cnames)
    for subdir, uid in found:
        print(f"{subdir}\t{uid}")
