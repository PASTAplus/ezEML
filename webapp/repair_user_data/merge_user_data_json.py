import click
import json
import os
from webapp.config import Config


def check_for_duplicates(data1, data2):
    uploads = set()
    for upload in data1.get('data_table_upload_filenames', []):
        if upload in uploads:
            click.echo(f"Duplicate upload: {upload}")
            return False
        uploads.add(upload)
    for upload in data2.get('data_table_upload_filenames', []):
        if upload in uploads:
            click.echo(f"Duplicate upload: {upload}")
            return False
        uploads.add(upload)
    return sorted(list(uploads))


def merge_data(data1, data2):
    merged = {}
    merged['cname'] = data1['cname']
    merged['idp'] = data1.get('idp', 'google')
    merged['uid'] = data1['uid'] # We assume data1 is the preferred file, i.e., the one with the valid uid
    merged['auth_token'] = data1['auth_token'] # Or should we delete it?
    merged['datetime'] = data1['datetime'] # Or should we delete it or use the current time?
    merged['data_table_upload_filenames'] = check_for_duplicates(data1, data2)
    merged['is_first_usage'] = data1.get('is_first_usage', False) and data2.get('is_first_usage', False)
    merged['new_to_badges'] = data1.get('new_to_badges', False) and data2.get('new_to_badges', False)
    merged['model_has_complex_texttypes'] = data1.get('model_has_complex_texttypes', False) or data2.get('model_has_complex_texttypes', False)
    merged['enable_complex_text_element_editing_global'] = data1.get('enable_complex_text_element_editing_global', False) or data2.get('enable_complex_text_element_editing_global', False)
    merged['enable_complex_text_element_editing_documents'] = data1.get('enable_complex_text_element_editing_documents', []) + data2.get('enable_complex_text_element_editing_documents', [])



@click.command()
@click.argument('input_file1', type=click.Path(exists=True))
@click.argument('input_file2', type=click.Path(exists=True))
@click.argument('output_file', type=click.Path())
def process_files(input_file1, input_file2, output_file):
    """This script takes two input files and one output file as arguments."""
    # Read the content of the first input file
    with open(os.path.join(Config.USER_DATA_DIR, input_file1), 'r') as file1:
        data1 = json.load(file1)

    # Read the content of the second input file
    with open(os.path.join(Config.USER_DATA_DIR, input_file2), 'r') as file2:
        data2 = json.load(file2)

    if data1['cname'] != data2['cname']:
        click.echo("The input files' cnames are not compatible.")
        return

    if data1.get('idp', 'google') != data2.get('idp', 'google'):
        click.echo("The input files' idps are not compatible.")
        return

    # Combine the data (assuming both are dictionaries)
    combined_data = merge_data(data1, data2)

    # Write the combined data to the output file
    with open(output_file, 'w') as outfile:
        json.dump(combined_data, outfile, indent=4)

    click.echo(f"Combined data from {input_file1} and {input_file2} into {output_file}")


if __name__ == '__main__':
    process_files()
