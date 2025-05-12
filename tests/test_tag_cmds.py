import pytest
from click.testing import CliRunner
import json
import yaml
import uuid
from pyzotero import zotero as pyzotero_client
from pyzotero_cli.zot_cli import zot

# Helper to get a PyZotero client instance using credentials
def get_zot_client(credentials):
    return pyzotero_client.Zotero(
        credentials['library_id'],
        credentials['library_type'],
        credentials['api_key']
    )

@pytest.fixture
def temp_tag_in_library(real_api_credentials):
    """Ensures a unique tag exists in the library for testing and cleans it up."""
    zot_api_client = get_zot_client(real_api_credentials)
    tag_name = f"temp-tag-{uuid.uuid4()}"

    # Add tag to a temporary item to make it appear in library tags
    item_template = zot_api_client.item_template('note')
    item_template['note'] = f"Temporary note for tag {tag_name}"
    item_template['tags'] = [{'tag': tag_name}]
    
    resp = zot_api_client.create_items([item_template])
    if 'successful' not in resp or not resp['successful']:
        pytest.fail(f"Failed to create item for temporary tag {tag_name}: {resp}")
    item_key = list(resp['successful'].keys())[0]
    item_obj = zot_api_client.item(item_key)

    yield tag_name

    # Cleanup
    try:
        zot_api_client.delete_item(item_obj)
    except Exception as e:
        print(f"Warning: Failed to delete temporary item {item_key} during tag cleanup: {e}")
    try:
        zot_api_client.delete_tags(tag_name)
    except Exception as e:
        print(f"Warning: Failed to delete temporary tag {tag_name} during cleanup: {e}")

@pytest.fixture
def temp_item_with_tags(real_api_credentials):
    """Creates a temporary item with specific tags and cleans it up."""
    zot_api_client = get_zot_client(real_api_credentials)
    tag1_name = f"item-tag1-{uuid.uuid4()}"
    tag2_name = f"item-tag2-{uuid.uuid4()}"
    tags_on_item = sorted([tag1_name, tag2_name])
    
    item_template = zot_api_client.item_template('journalArticle')
    item_template['title'] = f"Test Item for Tags {uuid.uuid4()}"
    item_template['tags'] = [{'tag': t} for t in tags_on_item]
    
    resp = zot_api_client.create_items([item_template])
    if not resp or 'successful' not in resp or not resp['successful']:
        pytest.fail(f"Failed to create test item with tags: {resp}")
        
    item_key = list(resp['successful'].keys())[0]
    created_item_data = zot_api_client.item(item_key)

    yield item_key, tags_on_item

    # Teardown
    try:
        zot_api_client.delete_item(created_item_data)
    except Exception as e:
        print(f"Error during cleanup, deleting item {item_key}: {e}")
    # Tags on items are removed when item is deleted.
    # Global tags might persist; attempt to clean them if they were unique to this test.
    try:
        zot_api_client.delete_tags(*tags_on_item)
    except Exception:
        pass # Ignore errors if tags are already gone or were never global


# Tests for 'zot-cli tag list'
def test_list_tags_default_output(active_profile_with_real_credentials, temp_tag_in_library):
    tag_to_check = temp_tag_in_library
    runner = CliRunner()
    result = runner.invoke(zot, ['tags', 'list'])
    assert result.exit_code == 0
    assert tag_to_check in result.output.splitlines()

def test_list_tags_json_output(active_profile_with_real_credentials, temp_tag_in_library):
    tag_to_check = temp_tag_in_library
    runner = CliRunner()
    result = runner.invoke(zot, ['tags', 'list', '--output', 'json'])
    assert result.exit_code == 0
    try:
        output_json = json.loads(result.output)
        assert isinstance(output_json, list)
        assert tag_to_check in output_json
    except json.JSONDecodeError:
        pytest.fail(f"Output was not valid JSON: {result.output}")

def test_list_tags_yaml_output(active_profile_with_real_credentials, temp_tag_in_library):
    tag_to_check = temp_tag_in_library
    runner = CliRunner()
    result = runner.invoke(zot, ['tags', 'list', '--output', 'yaml'])
    assert result.exit_code == 0
    try:
        output_yaml = yaml.safe_load(result.output)
        assert isinstance(output_yaml, list)
        assert tag_to_check in output_yaml
    except yaml.YAMLError:
        pytest.fail(f"Output was not valid YAML: {result.output}")

def test_list_tags_with_limit(active_profile_with_real_credentials, real_api_credentials):
    zot_api_client = get_zot_client(real_api_credentials)
    runner = CliRunner()
    tag1 = f"limit-tag1-{uuid.uuid4()}"
    tag2 = f"limit-tag2-{uuid.uuid4()}"

    items_to_cleanup = []
    try:
        for tag_name in [tag1, tag2]:
            item_template = zot_api_client.item_template('note')
            item_template['note'] = f"Note for limit test with {tag_name}"
            item_template['tags'] = [{'tag': tag_name}]
            resp = zot_api_client.create_items([item_template])
            assert resp['successful']
            item_key = list(resp['successful'].keys())[0]
            items_to_cleanup.append(zot_api_client.item(item_key))
        
        # Ensure tags are present
        all_lib_tags = zot_api_client.tags()
        assert tag1 in all_lib_tags
        assert tag2 in all_lib_tags

        result = runner.invoke(zot, ['tags', 'list', '--limit', '1'])
        assert result.exit_code == 0
        tags_output = result.output.strip().splitlines()
        assert len(tags_output) == 1
    finally:
        for item_obj in items_to_cleanup:
            try:
                zot_api_client.delete_item(item_obj)
            except Exception: pass
        try:
            zot_api_client.delete_tags(tag1, tag2)
        except Exception: pass


# Tests for 'zot-cli tag list-for-item'
def test_list_item_tags_default_output(active_profile_with_real_credentials, temp_item_with_tags):
    item_key, expected_tags = temp_item_with_tags
    runner = CliRunner()
    result = runner.invoke(zot, ['tags', 'list-for-item', item_key])
    assert result.exit_code == 0
    output_tags = sorted(result.output.strip().splitlines())
    assert output_tags == sorted(expected_tags)

def test_list_item_tags_json_output(active_profile_with_real_credentials, temp_item_with_tags):
    item_key, expected_tags = temp_item_with_tags
    runner = CliRunner()
    result = runner.invoke(zot, ['tags', 'list-for-item', item_key, '--output', 'json'])
    assert result.exit_code == 0
    try:
        output_json = json.loads(result.output)
        assert isinstance(output_json, list)
        assert sorted(output_json) == sorted(expected_tags)
    except json.JSONDecodeError:
        pytest.fail(f"Output was not valid JSON: {result.output}")

def test_list_item_tags_non_existent_item(active_profile_with_real_credentials):
    non_existent_key = f"NONEXISTENTKEY{uuid.uuid4()}" # Ensure truly non-existent
    runner = CliRunner()
    result = runner.invoke(zot, ['tags', 'list-for-item', non_existent_key])
    assert result.exit_code == 0 # Command handles error internally and prints to stderr
    assert f"Error retrieving tags for item {non_existent_key}" in result.output


# Tests for 'zot-cli tag delete'
def test_delete_tag_force(active_profile_with_real_credentials, temp_tag_in_library, real_api_credentials):
    tag_to_delete = temp_tag_in_library
    zot_api_client = get_zot_client(real_api_credentials)
    runner = CliRunner()

    assert tag_to_delete in zot_api_client.tags(), "Tag should exist before deletion attempt."

    result = runner.invoke(zot, ['tags', 'delete', tag_to_delete, '--force'])
    assert result.exit_code == 0
    assert f"Successfully deleted tags: {tag_to_delete}" in result.output
    assert tag_to_delete not in zot_api_client.tags(), "Tag should be deleted from the library."

def test_delete_multiple_tags_force(active_profile_with_real_credentials, real_api_credentials):
    zot_api_client = get_zot_client(real_api_credentials)
    runner = CliRunner()
    tag1 = f"del-multi1-{uuid.uuid4()}"
    tag2 = f"del-multi2-{uuid.uuid4()}"
    items_to_cleanup = []

    try:
        for tag_name in [tag1, tag2]:
            item_template = zot_api_client.item_template('note')
            item_template['note'] = f"Note for multi-delete test {tag_name}"
            item_template['tags'] = [{'tag': tag_name}]
            resp = zot_api_client.create_items([item_template])
            assert resp['successful']
            item_key = list(resp['successful'].keys())[0]
            items_to_cleanup.append(zot_api_client.item(item_key))

        library_tags_before = zot_api_client.tags()
        assert tag1 in library_tags_before
        assert tag2 in library_tags_before

        result = runner.invoke(zot, ['tags', 'delete', tag1, tag2, '--force'])
        assert result.exit_code == 0
        assert "Successfully deleted tags" in result.output
        assert tag1 in result.output
        assert tag2 in result.output

        library_tags_after = zot_api_client.tags()
        assert tag1 not in library_tags_after
        assert tag2 not in library_tags_after
    finally:
        for item_obj in items_to_cleanup:
            try:
                zot_api_client.delete_item(item_obj)
            except Exception: pass
        # Tags should already be deleted by the command; this is a safeguard.
        try:
            zot_api_client.delete_tags(tag1, tag2)
        except Exception: pass

def test_delete_tag_interactive_confirm_yes(active_profile_with_real_credentials, temp_tag_in_library, real_api_credentials):
    tag_to_delete = temp_tag_in_library
    zot_api_client = get_zot_client(real_api_credentials)
    runner = CliRunner()
    assert tag_to_delete in zot_api_client.tags()

    result = runner.invoke(zot, ['tags', 'delete', tag_to_delete], input='y\n')
    assert result.exit_code == 0
    assert f"Successfully deleted tags: {tag_to_delete}" in result.output
    assert "Are you sure you want to delete" in result.output # Check prompt was shown
    assert tag_to_delete not in zot_api_client.tags()

def test_delete_tag_interactive_confirm_no(active_profile_with_real_credentials, temp_tag_in_library, real_api_credentials):
    tag_to_delete = temp_tag_in_library
    zot_api_client = get_zot_client(real_api_credentials)
    runner = CliRunner()
    assert tag_to_delete in zot_api_client.tags()

    result = runner.invoke(zot, ['tags', 'delete', tag_to_delete], input='n\n')
    assert result.exit_code == 0
    assert "Operation cancelled." in result.output
    assert "Are you sure you want to delete" in result.output
    assert tag_to_delete in zot_api_client.tags() # Tag should still exist

def test_delete_tag_no_interaction_flag(active_profile_with_real_credentials, temp_tag_in_library, real_api_credentials):
    tag_to_delete = temp_tag_in_library
    zot_api_client = get_zot_client(real_api_credentials)
    runner = CliRunner()
    assert tag_to_delete in zot_api_client.tags()

    # The --no-interaction flag is a top-level option for zot_cli
    result = runner.invoke(zot, ['--no-interaction', 'tags', 'delete', tag_to_delete])
    assert result.exit_code == 0
    assert f"Successfully deleted tags: {tag_to_delete}" in result.output
    assert "Are you sure you want to delete" not in result.output # Prompt should be skipped
    assert tag_to_delete not in zot_api_client.tags()

def test_delete_non_existent_tag_force(active_profile_with_real_credentials):
    runner = CliRunner()
    non_existent_tag = f"non-existent-tag-{uuid.uuid4()}"
    result = runner.invoke(zot, ['tags', 'delete', non_existent_tag, '--force'])
    assert result.exit_code == 0
    # Pyzotero's delete_tags usually doesn't error on non-existent tags.
    # The CLI reports success based on the tags provided.
    assert f"Successfully deleted tags: {non_existent_tag}" in result.output
