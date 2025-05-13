import pytest
from click.testing import CliRunner
from pyzotero_cli.zot_cli import zot
import json
import os # For ZOTERO_USERNAME if used in assertions

# Fixtures like active_profile_with_real_credentials and real_api_credentials
# are automatically available from conftest.py

def test_util_key_info(active_profile_with_real_credentials, real_api_credentials, runner: CliRunner):
    """Test the 'zot util key-info' command."""
    profile_name = active_profile_with_real_credentials # Ensures profile is set up

    # Test with default output (JSON)
    result_json = runner.invoke(zot, ['util', 'key-info'])
    print(f"key-info (json) output: {result_json.output}")
    assert result_json.exit_code == 0
    try:
        data = json.loads(result_json.output)
        assert isinstance(data, dict)
        assert data['key'] == real_api_credentials['api_key']
        assert str(data['userID']) == real_api_credentials['library_id']
        zotero_username = os.environ.get('ZOTERO_USERNAME')
        if zotero_username:
            assert data['username'] == zotero_username
        assert 'access' in data # Check for presence of access permissions
        # Validate proper JSON serialization with double quotes
        assert '"key"' in result_json.output
        assert '"userID"' in result_json.output
    except json.JSONDecodeError:
        pytest.fail(f"Output was not valid JSON: {result_json.output}")

    # Test with table output
    result_table = runner.invoke(zot, ['util', 'key-info', '--output', 'table'])
    print(f"key-info (table) output: {result_table.output}")
    assert result_table.exit_code == 0
    assert "Key" in result_table.output
    assert "User ID" in result_table.output
    assert "Username" in result_table.output
    assert real_api_credentials['api_key'] in result_table.output
    assert real_api_credentials['library_id'] in result_table.output 
    # Username might not be in real_api_credentials fixture, 
    # but we can check it's present in output.
    # If ZOTERO_USERNAME is set in env, we could try to match it.
    if zotero_username:
        assert zotero_username in result_table.output

def test_util_last_modified_version(active_profile_with_real_credentials, runner: CliRunner):
    """Test the 'zot util last-modified-version' command."""
    profile_name = active_profile_with_real_credentials # Ensures profile is set up

    result = runner.invoke(zot, ['util', 'last-modified-version'])
    print(f"last-modified-version output: {result.output}")
    assert result.exit_code == 0
    # The output should be an integer representing the version number.
    # We strip any potential newline before checking if it's a digit.
    assert result.output.strip().isdigit()
    # Optionally, convert to int and check if it's positive, though isdigit() is a good start.
    assert int(result.output.strip()) >= 0

def test_util_item_types(active_profile_with_real_credentials, runner: CliRunner):
    """Test the 'zot util item-types' command."""
    profile_name = active_profile_with_real_credentials # Ensures profile is set up

    # Test with default output (JSON)
    result_json = runner.invoke(zot, ['util', 'item-types'])
    print(f"item-types (json) output: {result_json.output}")
    assert result_json.exit_code == 0
    try:
        data = json.loads(result_json.output)
        assert isinstance(data, list)
        assert len(data) > 0 # Should have at least one item type
        # Check structure of the first item type
        if data:
            assert 'itemType' in data[0]
            assert 'localized' in data[0]
            # Verify a known item type if possible
            book_type = next((item for item in data if item.get('itemType') == 'book'), None)
            assert book_type is not None
            assert book_type['localized'] == 'Book'
        # Validate proper JSON serialization with double quotes
        assert '"itemType"' in result_json.output
        assert '"localized"' in result_json.output
    except json.JSONDecodeError:
        pytest.fail(f"Output was not valid JSON: {result_json.output}")

    # Test with table output
    result_table = runner.invoke(zot, ['util', 'item-types', '--output', 'table'])
    print(f"item-types (table) output: {result_table.output}")
    assert result_table.exit_code == 0
    assert "Item Type" in result_table.output # Check for header
    assert "Localized Name" in result_table.output # Check for header
    assert "book" in result_table.output        # Check for known item type value
    assert "Journal Article" in result_table.output # Check for known localized name value

def test_util_item_fields(active_profile_with_real_credentials, runner: CliRunner):
    """Test the 'zot util item-fields' command."""
    profile_name = active_profile_with_real_credentials # Ensures profile is set up

    # Test with default output (JSON)
    result_json = runner.invoke(zot, ['util', 'item-fields'])
    print(f"item-fields (json) output: {result_json.output}")
    assert result_json.exit_code == 0
    try:
        data = json.loads(result_json.output)
        assert isinstance(data, list)
        assert len(data) > 0 # Should have at least one field
        if data:
            assert 'field' in data[0]
            assert 'localized' in data[0]
            title_field = next((item for item in data if item.get('field') == 'title'), None)
            assert title_field is not None
            assert title_field['localized'] == 'Title'
        # Validate proper JSON serialization with double quotes
        assert '"field"' in result_json.output
        assert '"localized"' in result_json.output
    except json.JSONDecodeError:
        pytest.fail(f"Output was not valid JSON: {result_json.output}")

    # Test with table output
    result_table = runner.invoke(zot, ['util', 'item-fields', '--output', 'table'])
    print(f"item-fields (table) output: {result_table.output}")
    assert result_table.exit_code == 0
    assert "Field" in result_table.output       # Check for header
    assert "Localized Name" in result_table.output # Check for header
    assert "title" in result_table.output       # Check for known field value
    assert "Date" in result_table.output        # Check for known localized name value

def test_util_item_type_fields(active_profile_with_real_credentials, runner: CliRunner):
    """Test the 'zot util item-type-fields' command."""
    profile_name = active_profile_with_real_credentials # Ensures profile is set up
    item_type_to_test = "book"

    # Test with default output (JSON)
    result_json = runner.invoke(zot, ['util', 'item-type-fields', item_type_to_test])
    print(f"item-type-fields {item_type_to_test} (json) output: {result_json.output}")
    assert result_json.exit_code == 0
    try:
        data = json.loads(result_json.output)
        assert isinstance(data, list)
        assert len(data) > 0 # Should have fields for 'book'
        if data:
            assert 'field' in data[0]
            assert 'localized' in data[0]
            # Example: Check for 'publisher' field
            publisher_field = next((item for item in data if item.get('field') == 'publisher'), None)
            assert publisher_field is not None
            assert publisher_field['localized'] == 'Publisher'
        # Validate proper JSON serialization with double quotes
        assert '"field"' in result_json.output
        assert '"localized"' in result_json.output
    except json.JSONDecodeError:
        pytest.fail(f"Output was not valid JSON for {item_type_to_test}: {result_json.output}")

    # Test with table output
    result_table = runner.invoke(zot, ['util', 'item-type-fields', item_type_to_test, '--output', 'table'])
    print(f"item-type-fields {item_type_to_test} (table) output: {result_table.output}")
    assert result_table.exit_code == 0
    assert "Field" in result_table.output       # Check for header
    assert "Localized Name" in result_table.output # Check for header
    assert "publisher" in result_table.output   # Check for known field value for book
    assert "Date" in result_table.output        # Check for known localized name value

    # Test with a non-existent item type (should fail gracefully, Zotero API might return error or empty)
    # pyzotero raises ZoteroException for bad item type in item_type_fields, caught by our handler.
    non_existent_item_type = "notAnItemType"
    result_error = runner.invoke(zot, ['util', 'item-type-fields', non_existent_item_type])
    print(f"item-type-fields {non_existent_item_type} output: {result_error.output}")
    # The command will exit non-zero due to handle_zotero_exceptions_and_exit
    assert result_error.exit_code != 0 
    # Check for parts of the actual error message from handle_zotero_exceptions_and_exit
    assert "A PyZotero library error occurred" in result_error.output
    assert "Invalid item type 'notAnItemType'" in result_error.output # Specific part of Pyzotero response

def test_util_item_template(active_profile_with_real_credentials, runner: CliRunner):
    """Test the 'zot util item-template' command."""
    profile_name = active_profile_with_real_credentials # Ensures profile is set up
    item_type_to_test = "book"

    # Test with a common item type (default output is JSON)
    result_json_default = runner.invoke(zot, ['util', 'item-template', item_type_to_test])
    print(f"item-template {item_type_to_test} (json default) output: {result_json_default.output}")
    assert result_json_default.exit_code == 0
    try:
        data = json.loads(result_json_default.output)
        assert isinstance(data, dict)
        assert data.get('itemType') == item_type_to_test
        assert 'title' in data # Common field for book
        assert 'creators' in data
        assert isinstance(data['creators'], list)
        assert 'tags' in data
        assert isinstance(data['tags'], list)
    except json.JSONDecodeError:
        pytest.fail(f"Output was not valid JSON for item template {item_type_to_test}: {result_json_default.output}")

    # Test with --output json explicitly (should be the same)
    result_json_explicit = runner.invoke(zot, ['util', 'item-template', item_type_to_test, '--output', 'json'])
    assert result_json_explicit.exit_code == 0
    assert result_json_explicit.output == result_json_default.output

    # Test with --linkmode
    linkmode_to_test = "imported_file"
    result_linkmode = runner.invoke(zot, ['util', 'item-template', item_type_to_test, '--linkmode', linkmode_to_test])
    print(f"item-template {item_type_to_test} with linkmode (json) output: {result_linkmode.output}")
    assert result_linkmode.exit_code == 0
    try:
        data_link = json.loads(result_linkmode.output)
        assert isinstance(data_link, dict)
        assert data_link.get('itemType') == item_type_to_test
        # Pyzotero's item_template with linkMode doesn't directly add 'linkMode' to the template itself
        # but uses it to construct the attachment sub-template if applicable. 
        # For a 'book' item, linkMode mainly applies to how attachments would be handled if one were created based on this template.
        # The base template for 'book' itself might not change structure due to linkMode.
        # The important part is that the command runs and produces a valid template.
        # If we were testing 'attachment' item type, linkMode would be more directly visible.
        assert 'title' in data_link # Ensure basic template structure is still there
    except json.JSONDecodeError:
        pytest.fail(f"Output was not valid JSON for item template {item_type_to_test} with linkmode: {result_linkmode.output}")

    # Test with a non-existent item type
    non_existent_item_type = "notAnItemType"
    result_error = runner.invoke(zot, ['util', 'item-template', non_existent_item_type])
    print(f"item-template {non_existent_item_type} output: {result_error.output}")
    assert result_error.exit_code != 0
    assert "A PyZotero library error occurred" in result_error.output
    assert f"Invalid item type '{non_existent_item_type}'" in result_error.output 