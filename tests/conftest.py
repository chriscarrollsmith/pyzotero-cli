import pytest
import os
import shutil
import configparser
import time
from pyzotero_cli.zot_cli import CONFIG_FILE, CONFIG_DIR
from click.testing import CliRunner
import uuid
from pyzotero import zotero
from pyzotero.zotero_errors import ResourceNotFoundError


# Import the main click command group
from pyzotero_cli.zot_cli import zot

@pytest.fixture(scope="function")
def isolated_config():
    """Ensure each test runs with a fresh config, backing up and restoring any existing one."""
    backup_config_file = None
    config_dir_existed_before = os.path.exists(CONFIG_DIR)

    if os.path.exists(CONFIG_FILE):
        backup_config_file = CONFIG_FILE + ".bak"
        shutil.copy2(CONFIG_FILE, backup_config_file)
        os.remove(CONFIG_FILE)  # Ensure it's gone before test
    
    if not config_dir_existed_before:
        os.makedirs(CONFIG_DIR, exist_ok=True)

    yield

    if os.path.exists(CONFIG_FILE):  # If test created one
        os.remove(CONFIG_FILE)
    
    if backup_config_file and os.path.exists(backup_config_file):
        shutil.move(backup_config_file, CONFIG_FILE)
    
    # Cleanup CONFIG_DIR if we created it and it's now empty
    if not config_dir_existed_before and os.path.exists(CONFIG_DIR):
        try:
            if not os.listdir(CONFIG_DIR):  # Check if empty
                shutil.rmtree(CONFIG_DIR)
        except OSError:
            pass

@pytest.fixture(scope="session")
def real_api_credentials():
    """Provides Zotero API credentials from environment variables. Skips test if not found."""
    api_key = os.environ.get('ZOTERO_API_KEY')
    library_id = os.environ.get('ZOTERO_LIBRARY_ID')
    library_type = os.environ.get('ZOTERO_LIBRARY_TYPE', 'user') # Default to 'user'

    if not api_key or not library_id:
        pytest.skip("ZOTERO_API_KEY and ZOTERO_LIBRARY_ID environment variables are required for this test.")
    
    return {
        "api_key": api_key,
        "library_id": library_id,
        "library_type": library_type
    }

@pytest.fixture(scope="function")
def active_profile_with_real_credentials(isolated_config, real_api_credentials):
    """
    Sets up an isolated config with a specific profile configured with real API credentials
    and sets this profile as the current active one.
    Yields the name of the configured profile.
    """
    profile_name = "ci_e2e_profile"
    config = configparser.ConfigParser()
    section_name = f"profile.{profile_name}"

    config.add_section(section_name)
    config[section_name]['library_id'] = real_api_credentials['library_id']
    config[section_name]['api_key'] = real_api_credentials['api_key']
    config[section_name]['library_type'] = real_api_credentials['library_type']
    config[section_name]['locale'] = 'en-US'
    config[section_name]['local_zotero'] = 'False'

    if not config.has_section('zotcli'):
        config.add_section('zotcli')
    config['zotcli']['current_profile'] = profile_name
    
    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)
        
    return profile_name 

# Fixture to provide the Click CliRunner, always used
@pytest.fixture(scope="session", autouse=True)
def runner() -> CliRunner:
    return CliRunner()


# Helper to get Zotero instance from credentials fixture
@pytest.fixture(scope="function") # Function scope to ensure clean state for API interactions per test
def zot_instance(real_api_credentials):
    """Provides an authenticated Pyzotero instance for direct API checks."""
    try:
        return zotero.Zotero(
            library_id=real_api_credentials['library_id'],
            library_type=real_api_credentials['library_type'],
            api_key=real_api_credentials['api_key']
        )
    except Exception as e:
        pytest.fail(f"Failed to create Zotero instance for testing: {e}")


# Fixture moved from test_tag_cmds.py - uses pyzotero directly
@pytest.fixture(scope="function")
def temp_item_with_tags(real_api_credentials):
    """Creates a temporary item with specific tags and cleans it up."""
    # Create client directly using credentials
    zot_api_client = zotero.Zotero(
        library_id=real_api_credentials['library_id'],
        library_type=real_api_credentials['library_type'],
        api_key=real_api_credentials['api_key']
    )
    tag1_name = f"item-tag1-{uuid.uuid4()}"
    tag2_name = f"item-tag2-{uuid.uuid4()}"
    tags_on_item = sorted([tag1_name, tag2_name])
    
    item_template = zot_api_client.item_template('journalArticle')
    item_template['title'] = f"Test Item for Tags {uuid.uuid4()}"
    item_template['tags'] = [{'tag': t} for t in tags_on_item]
    
    created_item_details = None # Store the dict from the successful response
    actual_item_key = None # Store the actual Zotero item key
    try:
        resp = zot_api_client.create_items([item_template])
        if not resp or 'successful' not in resp or not resp['successful']:
            pytest.fail(f"Failed to create test item with tags: {resp}")
            
        # Correctly extract the actual item key and details from the 'successful' dict
        # The key '0' is just the index from the input list
        result_index = list(resp['successful'].keys())[0] 
        created_item_details = resp['successful'][result_index] # Get the dict with key, version, etc.
        actual_item_key = created_item_details['key'] 

        yield actual_item_key, tags_on_item # Yield the CORRECT key

    finally:
        # Teardown
        if actual_item_key: # If we have a key, an item was likely created
            try:
                # Fetch the latest version of the item before attempting to delete
                item_to_delete = zot_api_client.item(actual_item_key)
                zot_api_client.delete_item(item_to_delete)
            except ResourceNotFoundError:
                # This can happen if the item was already deleted or creation wasn't fully successful
                print(f"Item {actual_item_key} not found during cleanup. Might have been already deleted or creation failed partially.")
            except Exception as e:
                # Catch other potential errors during fetch or delete
                print(f"Error during cleanup of item {actual_item_key}: {e}")

        # Tags on items are removed when item is deleted.
        # Global tags might persist; attempt to clean them if they were unique to this test.
        # This might fail if tags weren't created globally, which is fine.
        try:
            # Only delete tags if item creation was successful
            if actual_item_key: 
                zot_api_client.delete_tags(*tags_on_item)
        except Exception:
            pass # Ignore errors if tags are already gone or were never global


@pytest.fixture(scope="function")
def temp_parent_item(zot_instance):
    """Creates a temporary regular item (journalArticle) for attaching files and cleans it up."""
    # Change from 'note' to 'journalArticle' which can have attachments
    template = zot_instance.item_template('journalArticle')
    template['title'] = 'Temporary Test Article for Attachments'
    template['creators'] = [{'creatorType': 'author', 'firstName': 'Test', 'lastName': 'Author'}]
    
    resp = zot_instance.create_items([template])
    if not resp['success'] or '0' not in resp['success']:
        pytest.fail(f"Failed to create temporary parent item: {resp}")
    
    item_key = resp['success']['0']
    print(f"Created temp parent item: {item_key}") # Debugging
    yield item_key
    
    # Cleanup
    try:
        print(f"Attempting to delete temp parent item: {item_key}") # Debugging
        deleted = zot_instance.delete_item(zot_instance.item(item_key))
        print(f"Deletion result for {item_key}: {deleted}") # Debugging
        # Add a small delay sometimes needed for API consistency
        time.sleep(1) 
        # Verify deletion (optional but good practice)
        try:
            zot_instance.item(item_key)
            print(f"WARN: Item {item_key} still exists after deletion attempt.") # Debugging
        except ResourceNotFoundError: # Use imported exception directly
            print(f"Item {item_key} confirmed deleted.") # Debugging
            pass # Expected
    except Exception as e:
        print(f"Error during cleanup of item {item_key}: {e}") # Debugging output