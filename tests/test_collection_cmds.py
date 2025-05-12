import pytest
import os
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

# Import the main cli entry point
from pyzotero_cli.zot_cli import zot

# Import PyZotero errors for mocking/testing
from pyzotero.zotero_errors import (
    PyZoteroError, ResourceNotFoundError
)

# Helper function to create a mock Zotero client instance
def create_mock_zotero(config=None):
    mock_zot = MagicMock()
    # Mock basic config check if needed
    if config is None:
        config = {
            'API_KEY': 'testkey',
            'LIBRARY_ID': '12345',
            'LIBRARY_TYPE': 'user',
            'LOCALE': 'en-US',
            'LOCAL': False
        }
    # Mock methods used in collection_cmds.py
    mock_zot.collections = MagicMock(return_value=[{'key': 'C1', 'data': {'name': 'Coll 1'}}, {'key': 'C2', 'data': {'name': 'Coll 2'}}])
    mock_zot.collections_top = MagicMock(return_value=[{'key': 'C1', 'data': {'name': 'Coll 1'}}])
    mock_zot.collection = MagicMock(return_value=[{'key': 'C1', 'data': {'name': 'Coll 1', 'parentCollection': False}, 'version': 10, 'meta': {'numItems': 5}}]) # Return list for consistency
    mock_zot.collections_sub = MagicMock(return_value=[{'key': 'C3', 'data': {'name': 'SubColl 3', 'parentCollection': 'C1'}}])
    mock_zot.all_collections = MagicMock(return_value=[{'key': 'C1', 'data': {'name': 'Coll 1'}}, {'key': 'C3', 'data': {'name': 'SubColl 3'}}])
    mock_zot.collection_items = MagicMock(return_value=[{'key': 'I1', 'data': {'title': 'Item 1'}}, {'key': 'I2', 'data': {'title': 'Item 2'}}])
    mock_zot.collection_items_top = MagicMock(return_value=[{'key': 'I1', 'data': {'title': 'Item 1'}}])
    mock_zot.collection_versions = MagicMock(return_value={'C1': 10, 'C2': 11})
    mock_zot.create_collections = MagicMock(return_value={'success': {'0': 'C4'}, 'unchanged': {}, 'failed': {}})
    mock_zot.update_collection = MagicMock(return_value=True) # Or mock specific return dicts if needed
    mock_zot.delete_collection = MagicMock(return_value=True)
    mock_zot.item = MagicMock(return_value=[{'key': 'I1', 'data': {'title': 'Item 1', 'collections': []}, 'version': 5}]) # Return list for consistency
    mock_zot.update_item = MagicMock(return_value=True)
    mock_zot.collection_tags = MagicMock(return_value=[{'tag': 'tag1', 'type': 0}, {'tag': 'tag2', 'type': 0}])

    # Ensure config retrieval works within the group function context setup
    # This mimics the setup in collection_group()
    mock_instance_factory = MagicMock(return_value=mock_zot)
    return mock_zot, mock_instance_factory

# --- Fixtures ---

# Use the isolated_config fixture defined in main conftest.py
# This ensures config file operations don't interfere between tests.
pytestmark = pytest.mark.usefixtures("isolated_config")


# Fixture for a temporary collection - requires real API creds
@pytest.fixture(scope="function")
def temp_collection_in_library(active_profile_with_real_credentials):
    """Creates a temporary collection in the real Zotero library and cleans up."""
    runner = CliRunner()
    profile_name = active_profile_with_real_credentials
    collection_name = f"pytest_temp_collection_{os.urandom(4).hex()}"

    # Create the collection
    result_create = runner.invoke(zot, ['--profile', profile_name, 'collection', 'create', '--name', collection_name])
    print("Create output:", result_create.output)
    print("Create exception:", result_create.exception)
    assert result_create.exit_code == 0
    collection_key = None  # Initialize before try block
    try:
        # Parse the complex string output to get the key
        # Assuming output format like "{'success': {'0': 'KEY'}, ...}"
        output_dict = eval(result_create.output.strip()) # Use eval carefully, only in tests!
        collection_key = output_dict['success']['0']
        assert collection_key is not None

        # Yield the key to the test
        yield collection_key

    finally:
        # Cleanup: Delete the collection
        # Initialize collection_key to None before try block
        if collection_key:  # Now safely bound
            result_delete = runner.invoke(zot, ['--profile', profile_name, 'collection', 'delete', collection_key, '--force'])
            print(f"Cleanup delete output for {collection_key}:", result_delete.output)
        else:
             print(f"Skipping cleanup for collection '{collection_name}' as key was not obtained.")


# --- Test Cases ---

# Test Group Initialization & Authentication Checks
def test_collection_group_no_creds(runner, isolated_config):
    """Test that commands fail if creds are missing and not using local."""
    # Ensure no creds in config or env for this test
    config_path = isolated_config
    if os.path.exists(config_path):
        os.remove(config_path) # Remove any potentially existing config

    # Unset env vars if they exist, just for this test's scope
    with patch.dict(os.environ, {k: '' for k in ['ZOTERO_API_KEY', 'ZOTERO_LIBRARY_ID', 'ZOTERO_LIBRARY_TYPE']}):
        result = runner.invoke(zot, ['collection', 'list'])
        assert result.exit_code != 0
        assert "API Key is not configured" in result.output or \
               "Library ID is not configured" in result.output or \
               "Library Type is not configured" in result.output

@patch('pyzotero_cli.collection_cmds.zotero.Zotero')
def test_collection_group_init_error(mock_zotero_class, runner, active_profile_with_real_credentials):
    """Test handling of PyZoteroError during client initialization."""
    mock_zotero_class.side_effect = PyZoteroError("Initialization failed")
    result = runner.invoke(zot, ['--profile', active_profile_with_real_credentials, 'collection', 'list'])
    assert result.exit_code == 1
    assert "Zotero API Error during client initialization: Initialization failed" in result.output

# Test `collection list`
@patch('pyzotero_cli.collection_cmds.zotero.Zotero')
def test_collection_list_basic(mock_zotero_class, runner, active_profile_with_real_credentials):
    mock_zot_instance, mock_factory = create_mock_zotero()
    mock_zotero_class.side_effect = mock_factory # Make constructor return our mock

    result = runner.invoke(zot, ['--profile', active_profile_with_real_credentials, 'collection', 'list'])
    assert result.exit_code == 0
    mock_zot_instance.collections.assert_called_once_with() # No extra params passed
    assert "'key': 'C1'" in result.output
    assert "'key': 'C2'" in result.output

@patch('pyzotero_cli.collection_cmds.zotero.Zotero')
def test_collection_list_top(mock_zotero_class, runner, active_profile_with_real_credentials):
    mock_zot_instance, mock_factory = create_mock_zotero()
    mock_zotero_class.side_effect = mock_factory

    result = runner.invoke(zot, ['--profile', active_profile_with_real_credentials, 'collection', 'list', '--top'])
    assert result.exit_code == 0
    mock_zot_instance.collections_top.assert_called_once_with()
    assert "'key': 'C1'" in result.output
    assert "'key': 'C2'" not in result.output # C2 was not in the top mock return

@patch('pyzotero_cli.collection_cmds.zotero.Zotero')
def test_collection_list_with_params(mock_zotero_class, runner, active_profile_with_real_credentials):
    mock_zot_instance, mock_factory = create_mock_zotero()
    mock_zotero_class.side_effect = mock_factory

    result = runner.invoke(zot, ['--profile', active_profile_with_real_credentials, 'collection', 'list', '--limit', '5', '--sort', 'name'])
    assert result.exit_code == 0
    mock_zot_instance.collections.assert_called_once_with(limit=5, sort='name')

@patch('pyzotero_cli.collection_cmds.zotero.Zotero')
def test_collection_list_api_error(mock_zotero_class, runner, active_profile_with_real_credentials):
    mock_zot_instance, mock_factory = create_mock_zotero()
    mock_zotero_class.side_effect = mock_factory
    mock_zot_instance.collections.side_effect = PyZoteroError("API List Failed")

    result = runner.invoke(zot, ['--profile', active_profile_with_real_credentials, 'collection', 'list'])
    assert result.exit_code == 0 # Command itself succeeded, but printed error
    assert "Zotero API Error: API List Failed" in result.output

# Test `collection get`
@patch('pyzotero_cli.collection_cmds.zotero.Zotero')
def test_collection_get_basic(mock_zotero_class, runner, active_profile_with_real_credentials):
    mock_zot_instance, mock_factory = create_mock_zotero()
    mock_zotero_class.side_effect = mock_factory

    result = runner.invoke(zot, ['--profile', active_profile_with_real_credentials, 'collection', 'get', 'C1'])
    assert result.exit_code == 0
    mock_zot_instance.collection.assert_called_once_with('C1')
    assert "'key': 'C1'" in result.output
    assert "'name': 'Coll 1'" in result.output

@patch('pyzotero_cli.collection_cmds.zotero.Zotero')
def test_collection_get_not_found(mock_zotero_class, runner, active_profile_with_real_credentials):
    mock_zot_instance, mock_factory = create_mock_zotero()
    mock_zotero_class.side_effect = mock_factory
    mock_zot_instance.collection.side_effect = ResourceNotFoundError("Collection not found")

    result = runner.invoke(zot, ['--profile', active_profile_with_real_credentials, 'collection', 'get', 'C_NOT_EXIST'])
    assert result.exit_code == 0 # Command handles error internally
    assert "Zotero API Error: Collection not found" in result.output

# Test `collection subcollections`
@patch('pyzotero_cli.collection_cmds.zotero.Zotero')
def test_collection_subcollections_basic(mock_zotero_class, runner, active_profile_with_real_credentials):
    mock_zot_instance, mock_factory = create_mock_zotero()
    mock_zotero_class.side_effect = mock_factory

    result = runner.invoke(zot, ['--profile', active_profile_with_real_credentials, 'collection', 'subcollections', 'C1'])
    assert result.exit_code == 0
    mock_zot_instance.collections_sub.assert_called_once_with('C1')
    assert "'key': 'C3'" in result.output # Mocked subcollection
    assert "'name': 'SubColl 3'" in result.output

# Test `collection all`
@patch('pyzotero_cli.collection_cmds.zotero.Zotero')
def test_collection_all_basic(mock_zotero_class, runner, active_profile_with_real_credentials):
    mock_zot_instance, mock_factory = create_mock_zotero()
    mock_zotero_class.side_effect = mock_factory

    result = runner.invoke(zot, ['--profile', active_profile_with_real_credentials, 'collection', 'all'])
    assert result.exit_code == 0
    mock_zot_instance.all_collections.assert_called_once_with()
    assert "'key': 'C1'" in result.output
    assert "'key': 'C3'" in result.output # Mocked flat list

@patch('pyzotero_cli.collection_cmds.zotero.Zotero')
def test_collection_all_with_parent(mock_zotero_class, runner, active_profile_with_real_credentials):
    mock_zot_instance, mock_factory = create_mock_zotero()
    mock_zotero_class.side_effect = mock_factory

    result = runner.invoke(zot, ['--profile', active_profile_with_real_credentials, 'collection', 'all', '--parent-collection-id', 'P1'])
    assert result.exit_code == 0
    mock_zot_instance.all_collections.assert_called_once_with(collectionID='P1')

# Test `collection items`
@patch('pyzotero_cli.collection_cmds.zotero.Zotero')
def test_collection_items_basic(mock_zotero_class, runner, active_profile_with_real_credentials):
    mock_zot_instance, mock_factory = create_mock_zotero()
    mock_zotero_class.side_effect = mock_factory

    result = runner.invoke(zot, ['--profile', active_profile_with_real_credentials, 'collection', 'items', 'C1'])
    assert result.exit_code == 0
    mock_zot_instance.collection_items.assert_called_once_with('C1')
    assert "'key': 'I1'" in result.output
    assert "'key': 'I2'" in result.output

@patch('pyzotero_cli.collection_cmds.zotero.Zotero')
def test_collection_items_top(mock_zotero_class, runner, active_profile_with_real_credentials):
    mock_zot_instance, mock_factory = create_mock_zotero()
    mock_zotero_class.side_effect = mock_factory

    result = runner.invoke(zot, ['--profile', active_profile_with_real_credentials, 'collection', 'items', 'C1', '--top'])
    assert result.exit_code == 0
    mock_zot_instance.collection_items_top.assert_called_once_with('C1')
    assert "'key': 'I1'" in result.output
    assert "'key': 'I2'" not in result.output

# Test `collection item-count`
@patch('pyzotero_cli.collection_cmds.zotero.Zotero')
def test_collection_item_count_basic(mock_zotero_class, runner, active_profile_with_real_credentials):
    mock_zot_instance, mock_factory = create_mock_zotero()
    # Specific mock for collection to include 'meta'
    mock_zot_instance.collection.return_value = [{'key': 'C1', 'data': {'name': 'Coll 1'}, 'version': 10, 'meta': {'numItems': 5}}]
    mock_zotero_class.side_effect = mock_factory

    result = runner.invoke(zot, ['--profile', active_profile_with_real_credentials, 'collection', 'item-count', 'C1'])
    assert result.exit_code == 0
    mock_zot_instance.collection.assert_called_once_with('C1')
    assert "Number of items in collection 'C1': 5" in result.output

@patch('pyzotero_cli.collection_cmds.zotero.Zotero')
def test_collection_item_count_not_found(mock_zotero_class, runner, active_profile_with_real_credentials):
    mock_zot_instance, mock_factory = create_mock_zotero()
    mock_zot_instance.collection.side_effect = ResourceNotFoundError("Collection not found")
    mock_zotero_class.side_effect = mock_factory

    result = runner.invoke(zot, ['--profile', active_profile_with_real_credentials, 'collection', 'item-count', 'C_NOT_EXIST'])
    assert result.exit_code == 0 # Error handled internally
    assert "Collection 'C_NOT_EXIST' not found." in result.output

@patch('pyzotero_cli.collection_cmds.zotero.Zotero')
def test_collection_item_count_malformed(mock_zotero_class, runner, active_profile_with_real_credentials):
    mock_zot_instance, mock_factory = create_mock_zotero()
    # Return data without 'meta' or 'numItems'
    mock_zot_instance.collection.return_value = [{'key': 'C1', 'data': {'name': 'Coll 1'}, 'version': 10}]
    mock_zotero_class.side_effect = mock_factory

    result = runner.invoke(zot, ['--profile', active_profile_with_real_credentials, 'collection', 'item-count', 'C1'])
    assert result.exit_code == 0 # Error handled internally
    assert "Could not retrieve item count for collection 'C1'. Malformed response." in result.output

# Test `collection versions`
@patch('pyzotero_cli.collection_cmds.zotero.Zotero')
def test_collection_versions_basic(mock_zotero_class, runner, active_profile_with_real_credentials):
    mock_zot_instance, mock_factory = create_mock_zotero()
    mock_zotero_class.side_effect = mock_factory

    result = runner.invoke(zot, ['--profile', active_profile_with_real_credentials, 'collection', 'versions'])
    assert result.exit_code == 0
    mock_zot_instance.collection_versions.assert_called_once_with()
    assert "'C1': 10" in result.output
    assert "'C2': 11" in result.output

@patch('pyzotero_cli.collection_cmds.zotero.Zotero')
def test_collection_versions_since(mock_zotero_class, runner, active_profile_with_real_credentials):
    mock_zot_instance, mock_factory = create_mock_zotero()
    mock_zotero_class.side_effect = mock_factory

    result = runner.invoke(zot, ['--profile', active_profile_with_real_credentials, 'collection', 'versions', '--since', '9'])
    assert result.exit_code == 0
    mock_zot_instance.collection_versions.assert_called_once_with(since='9')

# Test `collection create` (requires real API or more complex mocking)
@pytest.mark.usefixtures("active_profile_with_real_credentials")
def test_collection_create_and_delete_real(runner, active_profile_with_real_credentials):
    """Tests creating and deleting a collection using the real API."""
    profile_name = active_profile_with_real_credentials
    collection_name = f"pytest_create_test_{os.urandom(4).hex()}"
    parent_name = f"pytest_create_parent_{os.urandom(4).hex()}"
    child_name = f"pytest_create_child_{os.urandom(4).hex()}"
    parent_key = None
    child_key = None
    single_key = None

    try:
        # 1. Create a single collection
        result_create = runner.invoke(zot, ['--profile', profile_name, 'collection', 'create', '--name', collection_name])
        print("Create single output:", result_create.output)
        assert result_create.exit_code == 0
        output_dict = eval(result_create.output.strip())
        single_key = output_dict['success']['0']
        assert single_key
        # Verify it exists (optional, relies on get working)
        result_get = runner.invoke(zot, ['--profile', profile_name, 'collection', 'get', single_key])
        assert result_get.exit_code == 0
        assert f"'name': '{collection_name}'" in result_get.output

        # 2. Create parent and child
        result_create_parent = runner.invoke(zot, ['--profile', profile_name, 'collection', 'create', '--name', parent_name])
        print("Create parent output:", result_create_parent.output)
        assert result_create_parent.exit_code == 0
        parent_key = eval(result_create_parent.output.strip())['success']['0']
        assert parent_key

        result_create_child = runner.invoke(zot, ['--profile', profile_name, 'collection', 'create', '--name', child_name, '--parent-id', parent_key])
        print("Create child output:", result_create_child.output)
        assert result_create_child.exit_code == 0
        child_key = eval(result_create_child.output.strip())['success']['0']
        assert child_key

        # Verify child relationship (optional)
        result_get_child = runner.invoke(zot, ['--profile', profile_name, 'collection', 'get', child_key])
        assert result_get_child.exit_code == 0
        assert f"'parentCollection': '{parent_key}'" in result_get_child.output

    finally:
        # Cleanup
        keys_to_delete = [k for k in [single_key, child_key, parent_key] if k]
        if keys_to_delete:
            delete_args = ['--profile', profile_name, 'collection', 'delete', '--force'] + keys_to_delete
            result_delete = runner.invoke(zot, delete_args)
            print("Cleanup delete output:", result_delete.output)
            # Don't assert exit code 0 strictly, focus is on creation success

# Test `collection update` (requires real API via fixture)
@pytest.mark.usefixtures("active_profile_with_real_credentials")
def test_collection_update_name_real(runner, active_profile_with_real_credentials, temp_collection_in_library):
    profile_name = active_profile_with_real_credentials
    collection_key = temp_collection_in_library
    new_name = f"pytest_updated_name_{os.urandom(4).hex()}"

    # Get initial version
    result_get = runner.invoke(zot, ['--profile', profile_name, 'collection', 'get', collection_key])
    assert result_get.exit_code == 0
    initial_data = eval(result_get.output.strip())[0] # Assumes list output
    initial_version = initial_data['version']

    # Update the name using the fetched version
    result_update = runner.invoke(zot, ['--profile', profile_name, 'collection', 'update', collection_key, '--name', new_name, '--last-modified', str(initial_version)])
    print("Update output:", result_update.output)
    assert result_update.exit_code == 0
    # Pyzotero update_collection returns True/False, not the updated object representation directly
    # assert 'True' in result_update.output # This assertion might be too brittle depending on exact output format

    # Verify the change
    result_get_updated = runner.invoke(zot, ['--profile', profile_name, 'collection', 'get', collection_key])
    assert result_get_updated.exit_code == 0
    assert f"'name': '{new_name}'" in result_get_updated.output
    updated_data = eval(result_get_updated.output.strip())[0]
    assert updated_data['version'] > initial_version # Version should increase

@pytest.mark.usefixtures("active_profile_with_real_credentials")
def test_collection_update_precondition_fail_real(runner, active_profile_with_real_credentials, temp_collection_in_library):
    profile_name = active_profile_with_real_credentials
    collection_key = temp_collection_in_library
    wrong_version = "1" # Definitely wrong version

    result_update = runner.invoke(zot, ['--profile', profile_name, 'collection', 'update', collection_key, '--name', 'wontwork', '--last-modified', wrong_version])
    assert result_update.exit_code == 0 # Command handles the error
    assert "Failed to update collection" in result_update.output
    assert "Version mismatch" in result_update.output # Or check for PreConditionFailedError message

@patch('pyzotero_cli.collection_cmds.zotero.Zotero')
def test_collection_update_options_conflict(mock_zotero_class, runner, active_profile_with_real_credentials):
    # No need for API call, just check Click's validation
    mock_zot_instance, mock_factory = create_mock_zotero()
    mock_zotero_class.side_effect = mock_factory

    result = runner.invoke(zot, ['--profile', active_profile_with_real_credentials, 'collection', 'update', 'C1', '--name', 'new', '--from-json', '{}'])
    assert result.exit_code != 0
    assert 'Usage Error: Cannot use --from-json with --name or --parent-id simultaneously.' in result.output

@patch('pyzotero_cli.collection_cmds.zotero.Zotero')
def test_collection_update_no_options(mock_zotero_class, runner, active_profile_with_real_credentials):
    # No need for API call, just check Click's validation
    mock_zot_instance, mock_factory = create_mock_zotero()
    mock_zotero_class.side_effect = mock_factory

    result = runner.invoke(zot, ['--profile', active_profile_with_real_credentials, 'collection', 'update', 'C1'])
    assert result.exit_code != 0
    assert 'Usage Error: Either --name, --parent-id, or --from-json must be provided for an update.' in result.output

# Test `collection delete` (uses fixture for temp collection)
@pytest.mark.usefixtures("active_profile_with_real_credentials")
def test_collection_delete_real_force(runner, active_profile_with_real_credentials, temp_collection_in_library):
    profile_name = active_profile_with_real_credentials
    collection_key = temp_collection_in_library # Fixture provides the key

    # Delete with force
    result_delete = runner.invoke(zot, ['--profile', profile_name, 'collection', 'delete', collection_key, '--force'])
    print("Delete output:", result_delete.output)
    assert result_delete.exit_code == 0
    # Check output for success message (adapt if output format changes)
    assert f"'{collection_key}': 'Successfully deleted'" in result_delete.output.replace('"',"'") # Normalize quotes

    # Verify deletion (expect not found)
    result_get = runner.invoke(zot, ['--profile', profile_name, 'collection', 'get', collection_key])
    assert result_get.exit_code == 0 # Command handles error
    assert "Zotero API Error: Resource not found /users/" in result_get.output or \
           "Zotero API Error: Resource not found /groups/" in result_get.output # API error message for not found

@patch('click.confirm')
@patch('pyzotero_cli.collection_cmds.zotero.Zotero')
def test_collection_delete_prompt_yes(mock_zotero_class, mock_confirm, runner, active_profile_with_real_credentials):
    mock_zot_instance, mock_factory = create_mock_zotero()
    # Mock the get call made for version retrieval when last-modified is not 'auto' or number
    mock_zot_instance.collection.return_value = [{'key': 'C1', 'data': {'name': 'Test'}, 'version': 123}]
    mock_zotero_class.side_effect = mock_factory
    mock_confirm.return_value = True # Simulate user saying yes

    result = runner.invoke(zot, ['--profile', active_profile_with_real_credentials, 'collection', 'delete', 'C1'])
    assert result.exit_code == 0
    mock_confirm.assert_called_once()
    mock_zot_instance.delete_collection.assert_called_once_with({'key': 'C1', 'version': 123})
    assert "'C1': 'Successfully deleted'" in result.output.replace('"', "'")

@patch('click.confirm')
@patch('pyzotero_cli.collection_cmds.zotero.Zotero')
def test_collection_delete_prompt_no(mock_zotero_class, mock_confirm, runner, active_profile_with_real_credentials):
    mock_zot_instance, mock_factory = create_mock_zotero()
    mock_zotero_class.side_effect = mock_factory
    mock_confirm.return_value = False # Simulate user saying no

    result = runner.invoke(zot, ['--profile', active_profile_with_real_credentials, 'collection', 'delete', 'C1'])
    assert result.exit_code == 0 # Command exits gracefully
    mock_confirm.assert_called_once()
    mock_zot_instance.delete_collection.assert_not_called()
    assert "Deletion cancelled." in result.output

# Test `collection add-item`
@pytest.mark.usefixtures("active_profile_with_real_credentials", "temp_item_with_tags")
def test_collection_add_item_real(runner, active_profile_with_real_credentials, temp_collection_in_library, temp_item_with_tags):
    profile_name = active_profile_with_real_credentials
    collection_key = temp_collection_in_library
    item_key = temp_item_with_tags # Fixture provides item key

    # Add item to collection
    result_add = runner.invoke(zot, ['--profile', profile_name, 'collection', 'add-item', collection_key, item_key])
    print("Add item output:", result_add.output)
    assert result_add.exit_code == 0
    assert f"'{item_key}': \"Added to collection '{collection_key}'.\"" in result_add.output.replace("'", '"') # Normalize quotes for assertion

    # Verify item is in collection
    result_item_get = runner.invoke(zot, ['--profile', profile_name, 'item', 'get', item_key])
    assert result_item_get.exit_code == 0
    item_data = eval(result_item_get.output.strip())
    # Handle potential list vs dict return from 'item get' command if it changes
    item_details = item_data[0] if isinstance(item_data, list) else item_data
    assert collection_key in item_details['data']['collections']

    # Test adding again (should report already exists)
    result_add_again = runner.invoke(zot, ['--profile', profile_name, 'collection', 'add-item', collection_key, item_key])
    assert result_add_again.exit_code == 0
    assert f"'{item_key}': \"Already in collection '{collection_key}'.\"" in result_add_again.output.replace("'", '"')

# Test `collection remove-item`
@pytest.mark.usefixtures("active_profile_with_real_credentials", "temp_item_with_tags")
def test_collection_remove_item_real(runner, active_profile_with_real_credentials, temp_collection_in_library, temp_item_with_tags):
    profile_name = active_profile_with_real_credentials
    collection_key = temp_collection_in_library
    item_key = temp_item_with_tags

    # First, add the item to the collection
    add_result = runner.invoke(zot, ['--profile', profile_name, 'collection', 'add-item', collection_key, item_key])
    assert add_result.exit_code == 0
    assert f"Added to collection '{collection_key}'" in add_result.output

    # Now, remove the item with force
    result_remove = runner.invoke(zot, ['--profile', profile_name, 'collection', 'remove-item', collection_key, item_key, '--force'])
    print("Remove item output:", result_remove.output)
    assert result_remove.exit_code == 0
    assert f"'{item_key}': \"Removed from collection '{collection_key}'.\"" in result_remove.output.replace("'", '"')

    # Verify item is NOT in collection
    result_item_get = runner.invoke(zot, ['--profile', profile_name, 'item', 'get', item_key])
    assert result_item_get.exit_code == 0
    item_data = eval(result_item_get.output.strip())
    item_details = item_data[0] if isinstance(item_data, list) else item_data
    assert collection_key not in item_details['data']['collections']

    # Test removing again (should report not found in collection)
    result_remove_again = runner.invoke(zot, ['--profile', profile_name, 'collection', 'remove-item', collection_key, item_key, '--force'])
    assert result_remove_again.exit_code == 0
    assert f"'{item_key}': \"Not found in collection '{collection_key}'.\"" in result_remove_again.output.replace("'", '"')

# Test `collection tags`
@patch('pyzotero_cli.collection_cmds.zotero.Zotero')
def test_collection_tags_basic(mock_zotero_class, runner, active_profile_with_real_credentials):
    mock_zot_instance, mock_factory = create_mock_zotero()
    mock_zotero_class.side_effect = mock_factory

    result = runner.invoke(zot, ['--profile', active_profile_with_real_credentials, 'collection', 'tags', 'C1'])
    assert result.exit_code == 0
    # Need to mock the collection get call made before tags call
    mock_zot_instance.collection.assert_called_once_with('C1')
    mock_zot_instance.collection_tags.assert_called_once_with('C1')
    assert "'tag': 'tag1'" in result.output
    assert "'tag': 'tag2'" in result.output

@patch('pyzotero_cli.collection_cmds.zotero.Zotero')
def test_collection_tags_collection_not_found(mock_zotero_class, runner, active_profile_with_real_credentials):
    mock_zot_instance, mock_factory = create_mock_zotero()
    # Mock the initial collection check to fail
    mock_zot_instance.collection.side_effect = ResourceNotFoundError("Collection C_NOT_EXIST not found")
    mock_zotero_class.side_effect = mock_factory

    result = runner.invoke(zot, ['--profile', active_profile_with_real_credentials, 'collection', 'tags', 'C_NOT_EXIST'])
    assert result.exit_code == 0 # Error handled internally
    assert "Collection 'C_NOT_EXIST' not found." in result.output
    mock_zot_instance.collection_tags.assert_not_called() # Should not proceed to call collection_tags
