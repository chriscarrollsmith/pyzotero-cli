import pytest
from click.testing import CliRunner
import json
import yaml
import uuid
import traceback
from pyzotero_cli.zot_cli import zot
from pyzotero.zotero_errors import ResourceNotFoundError

# Use the isolated_config fixture defined in main conftest.py
pytestmark = pytest.mark.usefixtures("isolated_config")

@pytest.fixture(scope="function")
def temp_tag_in_library(zot_instance):
    """Creates a temporary tag in the real Zotero library and cleans up."""
    zot_api_client = zot_instance
    tag_name = f"pytest_temp_tag_{uuid.uuid4()}"
    # Add the tag via an item (simplest way to ensure tag exists for testing list/delete)
    item_template = zot_api_client.item_template('note')
    item_template['tags'] = [{'tag': tag_name}]
    item_resp = zot_api_client.create_items([item_template])
    item_key = None
    if item_resp and 'successful' in item_resp and item_resp['successful']:
        item_key = list(item_resp['successful'].keys())[0]
        created_item = zot_api_client.item(item_key)
    else:
        pytest.fail(f"Failed to create temporary item needed for tag fixture setup: {item_resp}")

    yield tag_name # Yield the tag name to the test

    # Cleanup
    try:
        if created_item and item_key:
            zot_api_client.delete_item(created_item) # Delete the temporary item
    except Exception as e:
        print(f"Error during tag fixture cleanup (deleting item {item_key}): {e}")

# Tests for 'zot-cli tag list'
def test_list_tags_default_output(temp_tag_in_library, runner: CliRunner):
    tag_to_check = temp_tag_in_library
    result = runner.invoke(zot, ['tags', 'list'])
    assert result.exit_code == 0
    try:
        output_json = json.loads(result.output)
        assert isinstance(output_json, list)
        assert tag_to_check in output_json
    except json.JSONDecodeError:
        pytest.fail(f"Default output was not valid JSON: {result.output}")

def test_list_tags_json_output(temp_tag_in_library, runner: CliRunner):
    tag_to_check = temp_tag_in_library
    result = runner.invoke(zot, ['tags', 'list', '--output', 'json'])
    assert result.exit_code == 0
    try:
        output_json = json.loads(result.output)
        assert isinstance(output_json, list)
        assert tag_to_check in output_json
    except json.JSONDecodeError:
        pytest.fail(f"Output was not valid JSON: {result.output}")

def test_list_tags_yaml_output(temp_tag_in_library, runner: CliRunner):
    tag_to_check = temp_tag_in_library
    result = runner.invoke(zot, ['tags', 'list', '--output', 'yaml'])
    assert result.exit_code == 0
    try:
        output_yaml = yaml.safe_load(result.output)
        assert isinstance(output_yaml, list)
        assert tag_to_check in output_yaml
    except yaml.YAMLError:
        pytest.fail(f"Output was not valid YAML: {result.output}")

def test_list_tags_with_limit(zot_instance, runner: CliRunner):
    zot_api_client = zot_instance
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
        output_json = json.loads(result.output)
        assert isinstance(output_json, list)
        assert len(output_json) == 1
    finally:
        for item_obj in items_to_cleanup:
            try:
                zot_api_client.delete_item(item_obj)
            except Exception: pass
        try:
            zot_api_client.delete_tags(tag1, tag2)
        except Exception: pass


# Tests for 'zot-cli tag list-for-item'
def test_list_item_tags_default_output(temp_item_with_tags, runner: CliRunner):
    item_key, expected_tags = temp_item_with_tags
    result = runner.invoke(zot, ['tags', 'list-for-item', item_key])
    assert result.exit_code == 0
    try:
        output_json = json.loads(result.output)
        assert isinstance(output_json, list)
        assert sorted(output_json) == sorted(expected_tags)
    except json.JSONDecodeError:
        pytest.fail(f"Default output was not valid JSON: {result.output}")

def test_list_item_tags_json_output(temp_item_with_tags, runner: CliRunner):
    item_key, expected_tags = temp_item_with_tags
    result = runner.invoke(zot, ['tags', 'list-for-item', item_key, '--output', 'json'])
    assert result.exit_code == 0
    try:
        output_json = json.loads(result.output)
        assert isinstance(output_json, list)
        assert sorted(output_json) == sorted(expected_tags)
    except json.JSONDecodeError:
        pytest.fail(f"Output was not valid JSON: {result.output}")

def test_list_item_tags_non_existent_item(runner: CliRunner):
    non_existent_key = f"NONEXISTENTKEY{uuid.uuid4()}" # Ensure truly non-existent
    result = runner.invoke(zot, ['tags', 'list-for-item', non_existent_key])
    assert result.exit_code == 0 # Command handles error internally and prints to stderr
    assert f"Error retrieving tags for item {non_existent_key}" in result.output


# Tests for 'zot-cli tag delete'
def test_delete_tag_force(temp_tag_in_library, zot_instance, runner: CliRunner):
    tag_to_delete = temp_tag_in_library
    zot_api_client = zot_instance

    assert tag_to_delete in zot_api_client.tags(), "Tag should exist before deletion attempt."

    result = runner.invoke(zot, ['tags', 'delete', tag_to_delete, '--force'])
    assert result.exit_code == 0
    assert f"Successfully deleted tags: {tag_to_delete}" in result.output
    assert tag_to_delete not in zot_api_client.tags(), "Tag should be deleted from the library."

def test_delete_multiple_tags_force(zot_instance, runner: CliRunner):
    zot_api_client = zot_instance
    tag1 = f"del-multi1-{uuid.uuid4()}"
    tag2 = f"del-multi2-{uuid.uuid4()}"
    item_keys_for_cleanup = []

    try:
        for tag_name in [tag1, tag2]:
            item_template = zot_api_client.item_template('note')
            item_template['note'] = f"Note for multi-delete test {tag_name}"
            item_template['tags'] = [{'tag': tag_name}]
            resp = zot_api_client.create_items([item_template])
            assert resp['successful'], f"Failed to create item for tag {tag_name}: {resp}"
            created_item_dict = resp['successful']['0']
            item_keys_for_cleanup.append(created_item_dict['key'])

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
        for item_key in item_keys_for_cleanup:
            try:
                item_to_delete = zot_api_client.item(item_key)
                if item_to_delete:
                    zot_api_client.delete_item(item_to_delete)
                else:
                    print(f"Item {item_key} not found during cleanup, possibly already deleted.")
            except Exception as e:
                print(f"Error during cleanup of item {item_key}: {e}")
                traceback.print_exc()
        
        try:
            zot_api_client.delete_tags(tag1, tag2)
        except Exception as e:
            print(f"Error during safeguard tag deletion ('{tag1}', '{tag2}'): {e}")
            traceback.print_exc()

def test_delete_tag_interactive_confirm_yes(temp_tag_in_library, zot_instance, runner: CliRunner):
    tag_to_delete = temp_tag_in_library
    zot_api_client = zot_instance
    assert tag_to_delete in zot_api_client.tags()

    result = runner.invoke(zot, ['tags', 'delete', tag_to_delete], input='y\n')
    assert result.exit_code == 0
    assert f"Successfully deleted tags: {tag_to_delete}" in result.output
    assert "Are you sure you want to delete" in result.output # Check prompt was shown
    assert tag_to_delete not in zot_api_client.tags()

def test_delete_tag_interactive_confirm_no(temp_tag_in_library, zot_instance, runner: CliRunner):
    tag_to_delete = temp_tag_in_library
    zot_api_client = zot_instance
    assert tag_to_delete in zot_api_client.tags()

    result = runner.invoke(zot, ['tags', 'delete', tag_to_delete], input='n\n')
    assert result.exit_code == 0
    assert "Operation cancelled." in result.output
    assert "Are you sure you want to delete" in result.output
    assert tag_to_delete in zot_api_client.tags() # Tag should still exist

def test_delete_tag_no_interaction_flag(temp_tag_in_library, zot_instance, runner: CliRunner):
    tag_to_delete = temp_tag_in_library
    zot_api_client = zot_instance
    assert tag_to_delete in zot_api_client.tags()

    # The --no-interaction flag is a top-level option for zot_cli
    result = runner.invoke(zot, ['--no-interaction', 'tags', 'delete', tag_to_delete])
    assert result.exit_code == 0
    assert f"Successfully deleted tags: {tag_to_delete}" in result.output
    assert "Are you sure you want to delete" not in result.output # Prompt should be skipped
    assert tag_to_delete not in zot_api_client.tags()

def test_delete_non_existent_tag_force(runner: CliRunner):
    non_existent_tag = f"non-existent-tag-{uuid.uuid4()}"
    result = runner.invoke(zot, ['tags', 'delete', non_existent_tag, '--force'])
    assert result.exit_code == 0
    # Pyzotero's delete_tags usually doesn't error on non-existent tags.
    # The CLI reports success based on the tags provided.
    assert f"Successfully deleted tags: {non_existent_tag}" in result.output
