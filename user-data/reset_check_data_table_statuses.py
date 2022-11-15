import os

user_data_dir = os.getcwd()

to_delete = []
for x in os.walk(user_data_dir):
    dir = x[0]
    if '/uploads/' in dir:
        files = x[2]
        for filename in files:
            if 'csv_eval' in filename:
                if not filename.endswith('_ok'):
                    to_delete.append(os.path.join(dir, filename))

for f in to_delete:
    print(f"Removing {f}")
    os.remove(f)

