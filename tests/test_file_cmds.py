import pytest
import json
import time

from pyzotero_cli.zot_cli import zot


@pytest.fixture(scope="function")
def temp_local_file(tmp_path):
    """Creates a temporary local text file."""
    file_path = tmp_path / "test_attachment.txt"
    content = "This is a test file for Zotero attachment uploads."
    file_path.write_text(content)
    yield file_path

@pytest.fixture(scope="function")
def temp_local_files(tmp_path):
    """Creates multiple temporary local text files."""
    file_path1 = tmp_path / "test_attachment_1.txt"
    file_path2 = tmp_path / "test_attachment_2.pdf" # Use different extension for variety
    content1 = "Content for file 1."
    content2 = "Content for file 2 (pretend PDF)."
    file_path1.write_text(content1)
    file_path2.write_text(content2)
    yield [file_path1, file_path2]

@pytest.fixture(scope="function")
def temp_item_with_real_attachment(zot_instance, temp_parent_item, temp_local_file):
    """Creates a parent item and attaches a real file to it."""
    parent_key = temp_parent_item
    file_path = temp_local_file
    
    # 1. Create attachment item using create_items first
    print(f"Creating attachment item for file {file_path.name} under parent {parent_key}") # Debugging
    template = zot_instance.item_template('attachment', linkmode='imported_file')
    template['title'] = file_path.name # Use file name for title
    template['filename'] = file_path.name # Use file name for Zotero filename
    template['parentItem'] = parent_key
    # Let contentType be determined by upload?

    resp_create = zot_instance.create_items([template])
    if not resp_create or 'success' not in resp_create or not resp_create['success'] or '0' not in resp_create['success']:
        pytest.fail(f"Failed to create attachment item via create_items: {resp_create}")
        
    real_attachment_key = resp_create['success']['0']
    print(f"Created attachment item {real_attachment_key}, now uploading file...") # Debugging
    
    # 2. Upload the actual file content to the created attachment item
    # We need the full item dict for upload_attachments, fetch the one we just created.
    time.sleep(1) # Give API a moment
    try:
        # Fetch the created item to get its full structure including version
        attachment_item_dict = zot_instance.item(real_attachment_key)
        if not attachment_item_dict:
             pytest.fail(f"Failed to fetch created attachment item {real_attachment_key} after creation.")
        # Assuming .item() returns the item dict directly, not a list of one item
        attachment_item_data = attachment_item_dict['data'] 
    except Exception as e:
        pytest.fail(f"Failed to fetch created attachment item {real_attachment_key}: {e}")
        
    # Prepare for upload_attachments: list of dicts, 'filename' needs to be local path
    # The dict should be the 'data' part of the item structure.
    attachment_item_data['filename'] = str(file_path) # Crucial: point 'filename' to local path for upload
    
    print(f"Uploading file {file_path} to item {real_attachment_key}...") # Debugging
    resp_upload = zot_instance.upload_attachments([attachment_item_data]) 
    
    # Check response format from docs: {'success': [key1, key2], 'unchanged': [], 'failure': {key3: err_msg}}
    # Fail if not in success AND not in unchanged
    is_successful = resp_upload and \
                    ('success' in resp_upload and real_attachment_key in resp_upload['success'])
    # Treat 'unchanged' as success for the purpose of this fixture setup
    # Correctly check if any dict in the 'unchanged' list has the matching key
    is_unchanged = resp_upload and \
                   ('unchanged' in resp_upload and any(item.get('key') == real_attachment_key for item in resp_upload['unchanged']))

    if not (is_successful or is_unchanged):
         pytest.fail(f"Failed to upload file content for attachment {real_attachment_key}: {resp_upload}")
         
    print(f"Successfully uploaded/verified file content for {real_attachment_key}") # Debugging

    yield parent_key, real_attachment_key
    # Cleanup handled by temp_parent_item fixture (deletes parent, cascades to attachment)


@pytest.fixture(scope="function")
def temp_empty_attachment(zot_instance, temp_parent_item):
    """Creates an empty 'imported_file' attachment item."""
    parent_key = temp_parent_item
    template = zot_instance.item_template('attachment', linkmode='imported_file')
    template['title'] = 'Empty Test Attachment'
    template['parentItem'] = parent_key
    template['filename'] = 'placeholder_for_upload.bin' # Add placeholder filename
    template['contentType'] = 'application/octet-stream' # Placeholder

    resp = zot_instance.create_items([template])
    if not resp['success'] or '0' not in resp['success']:
        pytest.fail(f"Failed to create empty attachment item: {resp}")
    
    attachment_key = resp['success']['0']
    print(f"Created temp empty attachment: {attachment_key} under parent {parent_key}") # Debugging
    
    # Yield parent key as well for context if needed
    yield parent_key, attachment_key 
    # Cleanup handled by temp_parent_item fixture


# --- Test Functions ---

def test_file_download_to_dir(runner, active_profile_with_real_credentials, temp_item_with_real_attachment, tmp_path):
    """Test downloading a file attachment to a specified directory."""
    _parent_key, attachment_key = temp_item_with_real_attachment
    output_dir = tmp_path / "downloads"
    output_dir.mkdir()

    result = runner.invoke(zot, [
        'files', 'download', attachment_key,
        '--output', str(output_dir)
    ])

    print(f"Download to dir stdout:\n{result.stdout}") # Debugging
    print(f"Download to dir stderr:\n{result.stderr}") # Debugging
    assert result.exit_code == 0
    assert "File downloaded to:" in result.stdout
    
    # Check if the file exists (original filename is test_attachment.txt)
    expected_file = output_dir / "test_attachment.txt"
    assert expected_file.exists()
    assert expected_file.is_file()
    assert expected_file.read_text() == "This is a test file for Zotero attachment uploads."


def test_file_download_to_file(runner, active_profile_with_real_credentials, temp_item_with_real_attachment, tmp_path):
    """Test downloading a file attachment to a specific file path."""
    _parent_key, attachment_key = temp_item_with_real_attachment
    output_file = tmp_path / "my_downloaded_file.txt"

    result = runner.invoke(zot, [
        'files', 'download', attachment_key,
        '--output', str(output_file)
    ])

    print(f"Download to file stdout:\n{result.stdout}") # Debugging
    print(f"Download to file stderr:\n{result.stderr}") # Debugging
    assert result.exit_code == 0
    assert f"File downloaded to: {output_file.resolve()}" in result.stdout
    assert output_file.exists()
    assert output_file.is_file()
    assert output_file.read_text() == "This is a test file for Zotero attachment uploads."

def test_file_download_invalid_key(runner, active_profile_with_real_credentials, temp_parent_item, tmp_path):
    """Test downloading using a parent item key instead of an attachment key."""
    parent_key = temp_parent_item # This is a note item, not an attachment

    result = runner.invoke(zot, [
        'files', 'download', parent_key,
        '--output', str(tmp_path)
    ])

    print(f"Download invalid key stdout:\n{result.stdout}") # Debugging
    print(f"Download invalid key stderr:\n{result.stderr}") # Debugging
    assert result.exit_code != 0 # Should fail
    assert f"Error downloading file {parent_key}" in result.stderr
    # Check for the actual error related to missing filename info
    assert "'filename'" in result.stderr


def test_file_upload_single(runner, active_profile_with_real_credentials, temp_parent_item, temp_local_file, zot_instance):
    """Test uploading a single file attachment."""
    parent_key = temp_parent_item
    local_file = temp_local_file

    result = runner.invoke(zot, [
        'files', 'upload', str(local_file),
        '--parent-item-id', parent_key
    ])

    print(f"Upload single stdout:\n{result.stdout}") # Debugging
    print(f"Upload single stderr:\n{result.stderr}") # Debugging
    assert result.exit_code == 0
    assert "Upload results:" in result.stdout
    # Check for either success or unchanged message
    assert ("Successfully uploaded: test_attachment.txt" in result.stdout or \
            "File unchanged on server: test_attachment.txt" in result.stdout)
    
    # Verify attachment exists using API
    time.sleep(1) # API consistency delay
    children = zot_instance.children(parent_key, itemType='attachment')
    assert len(children) == 1
    assert children[0]['data']['filename'] == "test_attachment.txt"
    assert children[0]['data']['linkMode'] == 'imported_file'


def test_file_upload_single_with_filename(runner, active_profile_with_real_credentials, temp_parent_item, temp_local_file, zot_instance):
    """Test uploading a single file attachment with a custom Zotero filename."""
    parent_key = temp_parent_item
    local_file = temp_local_file
    custom_name = "My Custom Report.txt"

    result = runner.invoke(zot, [
        'files', 'upload', str(local_file),
        '--parent-item-id', parent_key,
        '--filename', custom_name
    ])

    print(f"Upload single custom name stdout:\n{result.stdout}") # Debugging
    print(f"Upload single custom name stderr:\n{result.stderr}") # Debugging
    assert result.exit_code == 0
    assert "Upload results:" in result.stdout
    # Check for either success or unchanged message for the custom name
    assert (f"Successfully uploaded: {custom_name}" in result.stdout or \
            f"File unchanged on server: {custom_name}" in result.stdout)

    # Verify attachment exists and has the custom name using API
    time.sleep(1) # API consistency delay
    children = zot_instance.children(parent_key, itemType='attachment')
    assert len(children) == 1
    # Check title, as filename might retain original local name
    assert children[0]['data']['title'] == custom_name 


def test_file_upload_multiple(runner, active_profile_with_real_credentials, temp_parent_item, temp_local_files, zot_instance):
    """Test uploading multiple file attachments."""
    parent_key = temp_parent_item
    local_files = temp_local_files
    file_paths_str = [str(f) for f in local_files]

    result = runner.invoke(zot, [
        'files', 'upload', *file_paths_str,
        '--parent-item-id', parent_key
    ])

    print(f"Upload multiple stdout:\n{result.stdout}") # Debugging
    print(f"Upload multiple stderr:\n{result.stderr}") # Debugging
    assert result.exit_code == 0
    assert "Upload results:" in result.stdout
    # Check for either success or unchanged message for both files
    assert ("Successfully uploaded: test_attachment_1.txt" in result.stdout or \
            "File unchanged on server: test_attachment_1.txt" in result.stdout)
    assert ("Successfully uploaded: test_attachment_2.pdf" in result.stdout or \
            "File unchanged on server: test_attachment_2.pdf" in result.stdout)

    # Verify attachments exist using API
    time.sleep(2) # Allow more time for multiple uploads/API sync
    children = zot_instance.children(parent_key, itemType='attachment', sort='dateAdded') # Sort helps consistency
    assert len(children) == 2
    filenames = sorted([c['data']['filename'] for c in children])
    assert filenames == ["test_attachment_1.txt", "test_attachment_2.pdf"]


def test_file_upload_multiple_with_filename_warning(runner, active_profile_with_real_credentials, temp_parent_item, temp_local_files):
    """Test that using --filename with multiple files generates a warning."""
    parent_key = temp_parent_item
    local_files = temp_local_files
    file_paths_str = [str(f) for f in local_files]

    result = runner.invoke(zot, [
        'files', 'upload', *file_paths_str,
        '--parent-item-id', parent_key,
        '--filename', 'should_be_ignored.txt'
    ])

    print(f"Upload multiple warning stdout:\n{result.stdout}") # Debugging
    print(f"Upload multiple warning stderr:\n{result.stderr}") # Debugging
    # Command might still succeed depending on pyzotero behavior, but check warning
    assert "Warning: --filename option is ignored when uploading multiple files." in result.stderr
    # Also check that uploads likely happened (best effort check)
    assert "Upload results:" in result.stdout
    # Check for either success or unchanged message for both files (even with warning)
    assert ("Successfully uploaded: test_attachment_1.txt" in result.stdout or \
            "File unchanged on server: test_attachment_1.txt" in result.stdout)
    assert ("Successfully uploaded: test_attachment_2.pdf" in result.stdout or \
            "File unchanged on server: test_attachment_2.pdf" in result.stdout)


def test_file_upload_batch(runner, active_profile_with_real_credentials, temp_parent_item, temp_empty_attachment, temp_local_files, tmp_path, zot_instance):
    """Test batch uploading files using a JSON manifest."""
    parent_key_for_new = temp_parent_item
    _parent_key_for_existing, existing_attachment_key = temp_empty_attachment
    local_file1, local_file2 = temp_local_files

    # Create manifest file
    manifest_data = [
        {
            # Entry to create a new attachment under parent_key_for_new
            "local_path": str(local_file1.resolve()),
            "zotero_filename": "Batch Upload New.txt",
            "parent_item_id": parent_key_for_new
        },
        {
            # Entry to upload a file to the existing empty attachment
            "local_path": str(local_file2.resolve()),
            "existing_attachment_key": existing_attachment_key
            # Optionally add zotero_filename here too if you want to potentially update title
            # "zotero_filename": "Batch Upload Existing.pdf" 
        }
    ]
    manifest_path = tmp_path / "batch_manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest_data, f)

    result = runner.invoke(zot, [
        'files', 'upload-batch', '--json', str(manifest_path)
    ])

    print(f"Upload batch stdout:\n{result.stdout}") # Debugging
    print(f"Upload batch stderr:\n{result.stderr}") # Debugging
    assert result.exit_code == 0
    assert "Processing manifest..." in result.stdout
    assert "Creating attachment item for 'Batch Upload New.txt'..." in result.stdout # Check item creation step
    assert "Attempting to upload 2 file(s)..." in result.stdout # Check upload step initiation
    assert "Batch upload results:" in result.stdout
    # Check success messages - format depends slightly on implementation (item key vs title)
    assert (f"Successfully uploaded file for item: Batch Upload New.txt" in result.stdout or 
            f"File for item Batch Upload New.txt" in result.stdout)
    # Allow either success or unchanged for the existing item, checking by title or key
    assert (f"Successfully uploaded file for item: Empty Test Attachment" in result.stdout or
            f"Successfully uploaded file for item: {existing_attachment_key}" in result.stdout or
            f"File for item Empty Test Attachment" in result.stdout or
            f"File for item test_attachment_2.pdf" in result.stdout or # Check original title if fetch failed
            f"File for item {existing_attachment_key}" in result.stdout)

    # Verify using API
    time.sleep(2) # API consistency delay
    
    # 1. Check the newly created attachment
    children_new = zot_instance.children(parent_key_for_new, itemType='attachment')
    assert len(children_new) >= 1 # Could be >1 if other tests ran concurrently without perfect cleanup
    new_attach = next((c for c in children_new if c['data']['title'] == "Batch Upload New.txt"), None)
    assert new_attach is not None, "Newly created batch attachment not found"
    # Check title, as filename might retain original local name after upload
    assert new_attach['data']['title'] == "Batch Upload New.txt"
    # Check if file content exists (will raise exception if not found or not uploaded)
    try:
        file_content_new = zot_instance.file(new_attach['key'])
        assert len(file_content_new) > 0
        assert "Content for file 1." in file_content_new.decode('utf-8', errors='ignore')
    except Exception as e:
        pytest.fail(f"Failed to retrieve file content for newly created batch attachment {new_attach['key']}: {e}")

    # 2. Check the existing attachment that was updated
    existing_attach_updated = zot_instance.item(existing_attachment_key)
    assert existing_attach_updated is not None
    # Filename might remain empty or be updated depending on how pyzotero handles it
    # But the crucial part is that the file content is there
    try:
        file_content_existing = zot_instance.file(existing_attachment_key)
        assert len(file_content_existing) > 0
        assert "Content for file 2" in file_content_existing.decode('utf-8', errors='ignore')
    except Exception as e:
        pytest.fail(f"Failed to retrieve file content for existing batch attachment {existing_attachment_key}: {e}")
