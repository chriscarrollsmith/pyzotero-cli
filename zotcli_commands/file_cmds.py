import click
import os
import json
from pyzotero import zotero

@click.group(name='file')
@click.pass_context
def file_group(ctx):
    """Commands for managing Zotero file attachments."""
    try:
        ctx.obj['zot'] = zotero.Zotero(
            library_id=ctx.obj['LIBRARY_ID'],
            library_type=ctx.obj['LIBRARY_TYPE'],
            api_key=ctx.obj['API_KEY'],
            locale=ctx.obj['LOCALE']
        )
    except Exception as e:
        click.echo(f"Error initializing Zotero instance: {e}", err=True)
        ctx.exit(1)

@file_group.command(name='download')
@click.argument('item_key_of_attachment', required=True)
@click.option('--output', '-o', help='Output path. If a directory, original filename is used. If a file path, this will be the new name. Defaults to CWD with original filename.')
@click.pass_context
def download_file(ctx, item_key_of_attachment, output):
    """Download a file attachment."""
    zot_instance = ctx.obj['zot']
    
    try:
        if output:
            output_path = os.path.abspath(output)
            if os.path.isdir(output_path):
                # Output is a directory, use original filename
                target_dir = output_path
                filename = None # zot.dump will try to get it
            else:
                # Output is a file path
                target_dir = os.path.dirname(output_path)
                filename = os.path.basename(output_path)
                if not target_dir: # If only filename is given, path is CWD
                    target_dir = os.getcwd()
            
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)
            
            full_path = zot_instance.dump(item_key_of_attachment, filename=filename, path=target_dir)
            click.echo(f"File downloaded to: {full_path}")

        else:
            # No output specified, download to CWD with original filename
            full_path = zot_instance.dump(item_key_of_attachment, path=os.getcwd())
            click.echo(f"File downloaded to: {full_path}")

    except Exception as e:
        click.echo(f"Error downloading file {item_key_of_attachment}: {e}", err=True)
        if "404" in str(e) and "Not Found for " in str(e):
             click.echo(f"Hint: Ensure '{item_key_of_attachment}' is the key of an attachment item, not its parent item.", err=True)

@file_group.command(name='upload')
@click.argument('paths_to_local_file', nargs=-1, type=click.Path(exists=True, dir_okay=False, readable=True), required=True)
@click.option('--parent-item-id', help='The ID of the Zotero item to attach these files to.')
@click.option('--filename', 'filename_option', help='The filename to use in Zotero. Only applicable if uploading a single file.')
@click.pass_context
def upload_files(ctx, paths_to_local_file, parent_item_id, filename_option):
    """Upload file(s) as new attachment(s)."""
    zot_instance = ctx.obj['zot']

    if not paths_to_local_file:
        click.echo("Error: No local files specified for upload.", err=True)
        return

    try:
        if len(paths_to_local_file) == 1:
            local_file_path = os.path.abspath(paths_to_local_file[0])
            if filename_option:
                # Single file with custom filename
                files_list_of_tuples = [(filename_option, local_file_path)]
                response = zot_instance.attachment_both(files_list_of_tuples, parentid=parent_item_id)
            else:
                # Single file, original filename
                files_list = [local_file_path]
                response = zot_instance.attachment_simple(files_list, parentid=parent_item_id)
        else:
            # Multiple files
            if filename_option:
                click.echo("Warning: --filename option is ignored when uploading multiple files. Original filenames will be used.", err=True)
            
            absolute_file_paths = [os.path.abspath(p) for p in paths_to_local_file]
            response = zot_instance.attachment_simple(absolute_file_paths, parentid=parent_item_id)

        # Process response
        if response:
            click.echo("Upload results:")
            if 'success' in response and response['success']:
                for key, details in response['success'].items():
                    click.echo(f"  Successfully uploaded: {details.get('filename', key)} (Key: {key})")
            if 'failure' in response and response['failure']:
                for key, details in response['failure'].items():
                    click.echo(f"  Failed to upload: {details.get('filename', key)}. Reason: {details.get('message', 'Unknown error')}", err=True)
            # pyzotero attachment_simple/both might not return 'unchanged'. 
            # The example return in docs is for upload_attachments.
            # Let's dump the full response for clarity if not matching expected keys.
            if not ('success' in response or 'failure' in response):
                click.echo(json.dumps(response, indent=2))
        else:
            click.echo("No response from server or an issue occurred.", err=True)

    except Exception as e:
        click.echo(f"Error uploading file(s): {e}", err=True)

@file_group.command(name='upload-batch')
@click.option('--json', 'json_manifest_path', type=click.Path(exists=True, dir_okay=False, readable=True), required=True, help='Path to a JSON manifest file for batch uploading.')
@click.pass_context
def upload_batch_files(ctx, json_manifest_path):
    """Upload files in batch based on a JSON manifest."""
    zot_instance = ctx.obj['zot']

    try:
        with open(json_manifest_path, 'r') as f:
            manifest = json.load(f)
    except Exception as e:
        click.echo(f"Error reading or parsing JSON manifest '{json_manifest_path}': {e}", err=True)
        return

    if not isinstance(manifest, list):
        click.echo("Error: JSON manifest must be a list of objects.", err=True)
        return

    attachments_to_upload = []
    created_items_info = [] # To hold info about newly created items before file upload

    click.echo("Processing manifest...")
    for index, entry in enumerate(manifest):
        if not isinstance(entry, dict):
            click.echo(f"Warning: Manifest entry at index {index} is not an object, skipping.", err=True)
            continue

        local_path = entry.get('local_path')
        zotero_filename = entry.get('zotero_filename')
        parent_item_id = entry.get('parent_item_id')
        existing_attachment_key = entry.get('existing_attachment_key')

        if not local_path or not os.path.exists(local_path):
            click.echo(f"Warning: Invalid or missing 'local_path' for entry at index {index}: '{local_path}'. Skipping.", err=True)
            continue
        
        absolute_local_path = os.path.abspath(local_path)

        if existing_attachment_key:
            attachments_to_upload.append({
                'key': existing_attachment_key,
                'filename': absolute_local_path, # This is the local path for upload_attachments
                'title': zotero_filename or os.path.basename(local_path) # Store for potential reporting
            })
        else:
            # Need to create the attachment item first
            if not zotero_filename:
                click.echo(f"Warning: 'zotero_filename' is required for new attachments (entry at index {index}). Skipping.", err=True)
                continue
            
            template = zot_instance.item_template('attachment', link_mode='imported_file')
            template['title'] = zotero_filename
            template['filename'] = zotero_filename # Zotero uses this for the stored filename
            if parent_item_id:
                template['parentItem'] = parent_item_id
            
            try:
                click.echo(f"Creating attachment item for '{zotero_filename}'...")
                creation_response = zot_instance.create_items([template])
                if creation_response['success']:
                    new_item_key = list(creation_response['success'].keys())[0]
                    created_items_info.append({
                        'original_filename': zotero_filename,
                        'key': new_item_key,
                        'local_path_to_upload': absolute_local_path
                    })
                    click.echo(f"  Successfully created item '{zotero_filename}' with key {new_item_key}.")
                else:
                    err_msg = creation_response.get('failed', {}).get(0, {}).get('message', 'Unknown error')
                    click.echo(f"Error creating attachment item for '{zotero_filename}': {err_msg}", err=True)
            except Exception as e_create:
                click.echo(f"Exception creating attachment item for '{zotero_filename}': {e_create}", err=True)
    
    # Add newly created items to the upload list
    for item_info in created_items_info:
        attachments_to_upload.append({
            'key': item_info['key'],
            'filename': item_info['local_path_to_upload'],
            'title': item_info['original_filename']
        })

    if not attachments_to_upload:
        click.echo("No valid attachments to upload after processing manifest.")
        return

    click.echo(f"Attempting to upload {len(attachments_to_upload)} file(s)...")
    try:
        # pyzotero's upload_attachments expects `filename` to be the path to the local file.
        # It does not use a `basedir` argument in the version I am referencing (e.g. 1.3.10).
        # The `attachment['filename']` is directly used as the filepath.
        upload_results = zot_instance.upload_attachments(attachments_to_upload)
        
        if upload_results:
            click.echo("Batch upload results:")
            if upload_results.get('success'):
                for item_key in upload_results['success']:
                    # Find the original title for better reporting
                    uploaded_item_title = next((att['title'] for att in attachments_to_upload if att['key'] == item_key), item_key)
                    click.echo(f"  Successfully uploaded file for item: {uploaded_item_title} (Key: {item_key})")
            if upload_results.get('failure'):
                for item_key, reason in upload_results['failure'].items(): # Assuming failure items are keys
                    failed_item_title = next((att['title'] for att in attachments_to_upload if att['key'] == item_key), item_key)
                    click.echo(f"  Failed to upload file for item: {failed_item_title} (Key: {item_key}). Reason: {reason}", err=True)
            if upload_results.get('unchanged'):
                 for item_key in upload_results['unchanged']:
                    unchanged_item_title = next((att['title'] for att in attachments_to_upload if att['key'] == item_key), item_key)
                    click.echo(f"  File for item {unchanged_item_title} (Key: {item_key}) was unchanged on server.")
        else:
            click.echo("No detailed results from batch upload operation.", err=True)

    except Exception as e_upload:
        click.echo(f"Error during batch file upload process: {e_upload}", err=True)
