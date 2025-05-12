import pytest
from click.testing import CliRunner
import json
import uuid
from pyzotero import zotero
from typing import cast, List, Dict, Any
import time

# Import the CLI entry point and fixtures
from pyzotero_cli.zot_cli import zot as cli_entry_point
# Fixtures 'runner', 'isolated_config', 'real_api_credentials', 
# 'active_profile_with_real_credentials' are implicitly available via conftest.py

# Sample data (can still be useful for structure)
SAMPLE_CONDITIONS_LIST = [{"condition": "title", "operator": "contains", "value": "test_marker"}]
SAMPLE_CONDITIONS_JSON = json.dumps(SAMPLE_CONDITIONS_LIST)


# --- Helper Fixture for Temporary Saved Search ---
@pytest.fixture
def temp_saved_search(real_api_credentials, request):
    """Creates a temporary saved search in the Zotero library and cleans it up."""
    zot = zotero.Zotero(
        real_api_credentials['library_id'],
        real_api_credentials['library_type'],
        real_api_credentials['api_key']
    )
    search_name = f"zot_test_{uuid.uuid4().hex[:8]}"
    
    # Create the search directly using pyzotero
    response_data = zot.saved_search(name=search_name, conditions=SAMPLE_CONDITIONS_LIST)
    
    # Let pytest handle the assertion error with proper traceback
    assert 'successful' in response_data and '0' in response_data['successful'], f"Failed to create temporary search via API. response_data: {response_data}"
    search_key = response_data['successful']['0']['key']
    
    print(f"\nCreated temporary search: Name='{search_name}', Key='{search_key}'")

    # Use yield for cleaner fixture teardown
    yield {'key': search_key, 'name': search_name}
    
    # Cleanup after test completes
    print(f"Cleaning up temporary search: Key='{search_key}'")
    status_code = zot.delete_saved_search((search_key,))
    assert status_code in (200, 204), f"API call to delete search '{search_key}' returned status {status_code}."


# --- Test List Searches ---

def test_list_searches_success_table(runner: CliRunner, active_profile_with_real_credentials, temp_saved_search):
    """Test successful listing of saved searches in table format (explicitly specified)."""
    # temp_saved_search ensures there's at least one search to list
    profile_name = active_profile_with_real_credentials # Ensure profile is active

    result = runner.invoke(
        cli_entry_point,
        ['search', 'list', '--output', 'table'],
        catch_exceptions=False
    )

    assert result.exit_code == 0, f"CLI Error: {result.output}"
    assert temp_saved_search['key'] in result.output

def test_list_searches_success_json(runner: CliRunner, active_profile_with_real_credentials, temp_saved_search):
    """Test successful listing of saved searches in JSON format (default)."""
    profile_name = active_profile_with_real_credentials
    
    result = runner.invoke(
        cli_entry_point,
        ['search', 'list'],
        catch_exceptions=False
    )
    
    # Let failure be clear with proper traceback
    assert result.exit_code == 0, f"Command failed with output: {result.output}"
    
    # JSON parsing errors will show proper traceback
    output_data = json.loads(result.output)
    
    # Direct assertions with clear error messages
    assert isinstance(output_data, list), "Output should be a JSON list"
    
    # Using any() with a clear assertion message
    found_search = any(
        (s.get('data', {}).get('key') == temp_saved_search['key'] and
         s.get('data', {}).get('name') == temp_saved_search['name'])
        for s in output_data
    )
    assert found_search, f"Temporary search with key '{temp_saved_search['key']}' not found in list output"


# --- Test Create Search ---

def test_create_search_success_json_string(runner: CliRunner, active_profile_with_real_credentials, real_api_credentials, request):
    """Test successful creation of a saved search using a JSON string with default JSON output."""
    profile_name = active_profile_with_real_credentials
    search_name = f"zotcli_test_create_str_{uuid.uuid4()}"
    conditions_list = [{"condition": "tag", "operator": "is", "value": f"test_tag_{uuid.uuid4()}"}]
    conditions_json = json.dumps(conditions_list)
    created_search_key = None # Keep track of key for cleanup

    # Finalizer to clean up the search created specifically by this test
    def cleanup_created_search():
        if created_search_key:
             print(f"\nCleaning up search created by test_create_search_success_json_string: Key='{created_search_key}'")
             zot = zotero.Zotero(real_api_credentials['library_id'], real_api_credentials['library_type'], real_api_credentials['api_key'])
             try:
                 status_code = zot.delete_saved_search((created_search_key,))
                 if status_code not in (200, 204):
                     print(f"Warning: API call returned status {status_code} when deleting search '{created_search_key}'.")
             except Exception as e:
                 print(f"Error during cleanup of created search '{created_search_key}': {e}")
    request.addfinalizer(cleanup_created_search)


    result = runner.invoke(cli_entry_point, [
        'search', 'create', '--name', search_name, '--conditions-json', conditions_json
    ], catch_exceptions=False)
    
    assert result.exit_code == 0, f"CLI Error: {result.output}"
    
    # Verify JSON output format
    try:
        output_data = json.loads(result.output)
        assert isinstance(output_data, dict), "Output should be a JSON dictionary"
        assert output_data.get('name') == search_name, "Created search name should be in the JSON output"
        assert 'key' in output_data, "Created search key should be in the JSON output"
        assert output_data.get('status') == "created successfully", "Status should indicate successful creation"
        
        # Store the key for cleanup
        created_search_key = output_data.get('key')
    except json.JSONDecodeError:
        assert False, "Output should be valid JSON"

    # Verify creation via API - give API a moment to reflect changes
    time.sleep(1)  # Short pause for API consistency

    zot = zotero.Zotero(real_api_credentials['library_id'], real_api_credentials['library_type'], real_api_credentials['api_key'])
    all_searches_raw = cast(List[Dict[str, Any]], zot.searches())
    found_search_raw = next((s for s in all_searches_raw if s.get('data', {}).get('name') == search_name), None)
    assert found_search_raw is not None, f"Search '{search_name}' not found via API after creation. Raw searches: {all_searches_raw}"
    assert found_search_raw.get('data', {}).get('conditions') is not None # Basic check on structure

def test_create_search_success_table_output(runner: CliRunner, active_profile_with_real_credentials, real_api_credentials, request):
    """Test successful creation of a saved search with explicit table output format."""
    profile_name = active_profile_with_real_credentials
    search_name = f"zotcli_test_create_table_{uuid.uuid4()}"
    conditions_list = [{"condition": "title", "operator": "contains", "value": f"test_{uuid.uuid4()}"}]
    conditions_json = json.dumps(conditions_list)
    created_search_key = None # Keep track of key for cleanup

    # Finalizer to clean up the search created specifically by this test
    def cleanup_created_search():
        if created_search_key:
             print(f"\nCleaning up search created by test_create_search_success_table_output: Key='{created_search_key}'")
             zot = zotero.Zotero(real_api_credentials['library_id'], real_api_credentials['library_type'], real_api_credentials['api_key'])
             try:
                 status_code = zot.delete_saved_search((created_search_key,))
                 if status_code not in (200, 204):
                     print(f"Warning: API call returned status {status_code} when deleting search '{created_search_key}'.")
             except Exception as e:
                 print(f"Error during cleanup of created search '{created_search_key}': {e}")
    request.addfinalizer(cleanup_created_search)

    result = runner.invoke(cli_entry_point, [
        'search', 'create', '--name', search_name, '--conditions-json', conditions_json, '--output', 'table'
    ], catch_exceptions=False)
    
    assert result.exit_code == 0, f"CLI Error: {result.output}"
    assert f"Saved search '{search_name}' created successfully." in result.output

    # Verify creation via API
    zot = zotero.Zotero(real_api_credentials['library_id'], real_api_credentials['library_type'], real_api_credentials['api_key'])
    all_searches_raw = cast(List[Dict[str, Any]], zot.searches())
    found_search_raw = next((s for s in all_searches_raw if s.get('data', {}).get('name') == search_name), None)
    assert found_search_raw is not None, f"Search '{search_name}' not found via API after creation. Raw searches: {all_searches_raw}"
    assert found_search_raw.get('data', {}).get('conditions') is not None # Basic check on structure
    created_search_key = found_search_raw['key'] # Store key for cleanup

def test_create_search_success_json_file(runner: CliRunner, active_profile_with_real_credentials, real_api_credentials, tmp_path, request):
    """Test successful creation of a saved search using a JSON file with default JSON output."""
    profile_name = active_profile_with_real_credentials
    search_name = f"zotcli_test_create_file_{uuid.uuid4()}"
    conditions_list = [{"condition": "dateAdded", "operator": "is", "value": "today"}]
    conditions_json = json.dumps(conditions_list)
    created_search_key = None # Keep track of key for cleanup

    conditions_file = tmp_path / "conditions.json"
    conditions_file.write_text(conditions_json)

    # Finalizer to clean up the search created specifically by this test
    def cleanup_created_search():
        if created_search_key:
             print(f"\nCleaning up search created by test_create_search_success_json_file: Key='{created_search_key}'")
             zot = zotero.Zotero(real_api_credentials['library_id'], real_api_credentials['library_type'], real_api_credentials['api_key'])
             try:
                 status_code = zot.delete_saved_search((created_search_key,))
                 if status_code not in (200, 204):
                     print(f"Warning: API call returned status {status_code} when deleting search '{created_search_key}'.")
             except Exception as e:
                 print(f"Error during cleanup of created search '{created_search_key}': {e}")
    request.addfinalizer(cleanup_created_search)

    result = runner.invoke(cli_entry_point, [
        'search', 'create', '--name', search_name, '--conditions-json', str(conditions_file)
    ], catch_exceptions=False)
    
    assert result.exit_code == 0, f"CLI Error: {result.output}"
    
    # Verify JSON output format
    try:
        output_data = json.loads(result.output)
        assert isinstance(output_data, dict), "Output should be a JSON dictionary"
        assert output_data.get('name') == search_name, "Created search name should be in the JSON output"
        assert 'key' in output_data, "Created search key should be in the JSON output"
        assert output_data.get('status') == "created successfully", "Status should indicate successful creation"
        
        # Store the key for cleanup
        created_search_key = output_data.get('key')
    except json.JSONDecodeError:
        assert False, "Output should be valid JSON"

    # Verify creation via API
    zot = zotero.Zotero(real_api_credentials['library_id'], real_api_credentials['library_type'], real_api_credentials['api_key'])
    all_searches_raw = cast(List[Dict[str, Any]], zot.searches())
    found_search_raw = next((s for s in all_searches_raw if s.get('data', {}).get('name') == search_name), None)
    assert found_search_raw is not None, f"Search '{search_name}' not found via API after creation. Raw searches: {all_searches_raw}"
    assert found_search_raw.get('data', {}).get('conditions') is not None # Basic check on structure
    created_search_key = found_search_raw['key'] # Store key for cleanup


# --- Tests for Invalid Input (should not hit API) ---

def test_create_search_invalid_json_input(runner: CliRunner, active_profile_with_real_credentials):
    """Test create search with invalid JSON input (not file or string)."""
    profile_name = active_profile_with_real_credentials
    result = runner.invoke(cli_entry_point, [
        'search', 'create', '--name', 'Bad Search', '--conditions-json', 'not_a_file_or_json'
    ]) # Catch exceptions is False by default, CLI handles it

    assert result.exit_code == 1 # Expecting CLI validation error
    assert "An unexpected application error occurred:" in result.output # Check for generic handler
    assert "JSONDecodeError" in result.output # Specific error type

def test_create_search_malformed_json_string(runner: CliRunner, active_profile_with_real_credentials):
    """Test create search with malformed JSON string."""
    profile_name = active_profile_with_real_credentials
    result = runner.invoke(cli_entry_point, [
        'search', 'create', '--name', 'Malformed', '--conditions-json', '{"key": "value", invalid json}'
    ])
    
    assert result.exit_code == 1
    assert "An unexpected application error occurred:" in result.output
    assert "JSONDecodeError" in result.output

def test_create_search_json_not_list(runner: CliRunner, active_profile_with_real_credentials):
    """Test create search where JSON is not a list."""
    profile_name = active_profile_with_real_credentials
    result = runner.invoke(cli_entry_point, [
        'search', 'create', '--name', 'Not List', '--conditions-json', '{"condition": "a"}' 
    ])
    
    assert result.exit_code == 1
    assert "Error: Conditions JSON must be a list of condition objects." in result.output

def test_create_search_invalid_condition_structure(runner: CliRunner, active_profile_with_real_credentials):
    """Test create search with missing keys in a condition object."""
    profile_name = active_profile_with_real_credentials
    invalid_conditions = json.dumps([{"condition": "title", "operator": "is"}]) # Missing 'value'
    result = runner.invoke(cli_entry_point, [
        'search', 'create', '--name', 'Bad Condition', '--conditions-json', invalid_conditions
    ])
    
    assert result.exit_code == 1
    assert "Error: Each condition object must contain 'condition', 'operator', and 'value' keys." in result.output


# --- Test Delete Search ---

def test_delete_search_success_single_force(runner: CliRunner, active_profile_with_real_credentials, temp_saved_search, real_api_credentials):
    """Test successful deletion of a single search with --force."""
    profile_name = active_profile_with_real_credentials
    search_key = temp_saved_search['key']
    
    result = runner.invoke(cli_entry_point, ['search', 'delete', search_key, '--force'], catch_exceptions=False)
    
    assert result.exit_code == 0, f"CLI Error: {result.output}"
    assert f"Successfully deleted saved search(es): {search_key}." in result.output

    # Verify deletion via API
    zot = zotero.Zotero(real_api_credentials['library_id'], real_api_credentials['library_type'], real_api_credentials['api_key'])
    searches = cast(List[Dict[str, Any]], zot.searches())
    assert not any(s.get('key') == search_key for s in searches), f"Search '{search_key}' still found via API after forced deletion."


def test_delete_search_success_multiple_force(runner: CliRunner, active_profile_with_real_credentials, real_api_credentials):
    """Test successful deletion of multiple searches with --force."""
    profile_name = active_profile_with_real_credentials
    
    # Create two temporary searches for this test
    zot = zotero.Zotero(real_api_credentials['library_id'], real_api_credentials['library_type'], real_api_credentials['api_key'])
    search1_name = f"zotcli_test_multi_del1_{uuid.uuid4()}"
    search2_name = f"zotcli_test_multi_del2_{uuid.uuid4()}"
    
    # Create first search
    response1 = zot.saved_search(name=search1_name, conditions=SAMPLE_CONDITIONS_LIST)
    assert 'successful' in response1, f"Failed to create search {search1_name}"
    search1_key = response1['successful']['0']['key']
    
    # Create second search
    response2 = zot.saved_search(name=search2_name, conditions=SAMPLE_CONDITIONS_LIST)
    assert 'successful' in response2, f"Failed to create search {search2_name}"
    search2_key = response2['successful']['0']['key']
    
    print(f"\nCreated searches for multi-delete test: {search1_key}, {search2_key}")
    
    try:
        # Run the delete command
        result = runner.invoke(
            cli_entry_point, 
            ['search', 'delete', search1_key, search2_key, '--force'], 
            catch_exceptions=False
        )
        
        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        assert f"Successfully deleted saved search(es):" in result.output
        assert search1_key in result.output
        assert search2_key in result.output
        
        # Verify deletion via API
        remaining_searches = cast(List[Dict[str, Any]], zot.searches())
        assert not any(s.get('key') == search1_key for s in remaining_searches)
        assert not any(s.get('key') == search2_key for s in remaining_searches)
    
    finally:
        # Ensure cleanup even if assertions fail
        for key in (search1_key, search2_key):
            try:
                zot.delete_saved_search((key,))
            except Exception:
                pass  # Best effort cleanup


def test_delete_search_success_confirmation_yes(runner: CliRunner, active_profile_with_real_credentials, temp_saved_search, real_api_credentials):
    """Test successful deletion with user confirmation (yes)."""
    profile_name = active_profile_with_real_credentials
    search_key = temp_saved_search['key']
    
    result = runner.invoke(cli_entry_point, ['search', 'delete', search_key], input='y', catch_exceptions=False)
    
    assert result.exit_code == 0, f"CLI Error: {result.output}"
    assert f"Are you sure you want to delete saved search(es) with key(s): {search_key}?" in result.output
    assert f"Successfully deleted saved search(es): {search_key}." in result.output

    # Verify deletion via API
    zot = zotero.Zotero(real_api_credentials['library_id'], real_api_credentials['library_type'], real_api_credentials['api_key'])
    searches: List[Dict[str, Any]] = cast(List[Dict[str, Any]], zot.searches())
    assert not any(s.get('key') == search_key for s in searches), f"Search '{search_key}' still found via API after confirmed deletion."


def test_delete_search_confirmation_no(runner: CliRunner, active_profile_with_real_credentials, temp_saved_search, real_api_credentials):
    """Test deletion cancellation with user confirmation (no)."""
    profile_name = active_profile_with_real_credentials
    search_key = temp_saved_search['key']
    
    # Invoking with 'n' should cause click.Abort
    result = runner.invoke(cli_entry_point, ['search', 'delete', search_key], input='n', catch_exceptions=False) # Catch exceptions prevents runner crash
    
    assert result.exit_code == 1 # click.Abort usually results in exit code 1
    assert f"Are you sure you want to delete saved search(es) with key(s): {search_key}?" in result.output
    assert "Aborted!" in result.output # click default abort message

    # Verify the search still exists via API
    zot = zotero.Zotero(real_api_credentials['library_id'], real_api_credentials['library_type'], real_api_credentials['api_key'])
    searches: List[Dict[str, Any]] = cast(List[Dict[str, Any]], zot.searches())
    assert any(s.get('key') == search_key for s in searches), f"Search '{search_key}' was deleted unexpectedly after answering 'n'."


def test_delete_search_no_keys_provided(runner: CliRunner, active_profile_with_real_credentials):
    """Test delete search command when no keys are provided."""
    profile_name = active_profile_with_real_credentials
    # Don't need API credentials for this CLI validation test
    result = runner.invoke(cli_entry_point, ['search', 'delete']) 
    
    assert result.exit_code != 0 # Should be a usage error (Click typically exits 2 for UsageError)
    assert "Error: Missing argument 'SEARCH_KEYS...'" in result.output 
