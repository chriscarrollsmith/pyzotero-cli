import json
import pytest
from click.testing import CliRunner
from pyzotero_cli.zot_cli import zot # Import the main command group
import uuid

# Test for `zot items list`
def test_item_list_default_json_output(runner: CliRunner):
    """Test `zot items list` returns JSON by default and is not empty."""
    result = runner.invoke(zot, ['items', 'list', '--limit', '1'])
    assert result.exit_code == 0
    try:
        data = json.loads(result.output)
        assert isinstance(data, list), "Output should be a JSON list."
        # Depending on the library, it might be empty if --limit 1 doesn't find anything quickly
        # or if the library is empty. For now, just check it's a list.
        # If the library has items:
        # assert len(data) > 0, "Should return at least one item if library is not empty and limit is applied."
    except json.JSONDecodeError:
        pytest.fail("Output was not valid JSON.")

def test_item_list_top_flag(runner: CliRunner):
    """Test `zot items list --top`."""
    result = runner.invoke(zot, ['items', 'list', '--top', '--limit', '1'])
    assert result.exit_code == 0
    try:
        data = json.loads(result.output)
        assert isinstance(data, list)
    except json.JSONDecodeError:
        pytest.fail("Output was not valid JSON for --top flag.")

def test_item_list_output_table(runner: CliRunner):
    """Test `zot items list --output table`."""
    result = runner.invoke(zot, ['items', 'list', '--limit', '1', '--output', 'table'])
    assert result.exit_code == 0
    assert "Key" in result.output or "Title" in result.output or "No data to display." in result.output # Check for table headers or empty message

def test_item_list_output_keys(runner: CliRunner, zot_instance):
    """Test `zot items list --output keys`."""
    # Ensure there's at least one item to get a key from
    items = zot_instance.top(limit=1)
    if not items:
        # If the library is empty, this test might not be meaningful in its current form
        # or we should skip it. For now, we'll proceed, it might return empty string.
        pass

    result = runner.invoke(zot, ['items', 'list', '--limit', '1', '--output', 'keys'])
    assert result.exit_code == 0
    output_lines = result.output.strip().split('\n')
    if items: # If we know there should be an item
        assert len(output_lines) >= 1, "Should output at least one key if items exist."
        assert len(output_lines[0]) == 8, "Zotero keys are typically 8 characters long."
    else: # If library might be empty
        assert result.output.strip() == "" or len(output_lines[0]) == 8, "Output is empty or a key"

# Test for `zot items get`
def test_item_get_single_item(runner: CliRunner, temp_item_with_tags):
    """Test `zot items get <item_key>` for an existing item."""
    item_key, _ = temp_item_with_tags # This fixture creates an item
    result = runner.invoke(zot, ['items', 'get', item_key])
    assert result.exit_code == 0
    try:
        data = json.loads(result.output)
        assert isinstance(data, dict), "Output should be a JSON dictionary for a single item."
        # Pyzotero item() returns a single dict, format_data_for_output will dump it as is.
        # The item_get command in item_cmds.py when one key is provided does:
        #   results = zot_client.item(item_key_or_id[0], **api_params)
        #   click.echo(format_data_for_output(results, output))
        # So, if 'results' is a dict, format_data_for_output handles it.
        assert data['key'] == item_key, "Returned item key should match the requested key."
    except json.JSONDecodeError:
        pytest.fail("Output was not valid JSON for item get.")

def test_item_get_non_existent_item(runner: CliRunner):
    """Test `zot items get <item_key>` for a non-existent item."""
    non_existent_key = "NONEXIST" # A key that is unlikely to exist
    result = runner.invoke(zot, ['items', 'get', non_existent_key])
    # Updated to expect exit code 1 for non-existent item - this is the correct behavior
    assert result.exit_code == 1
    # Check for key components of the error message
    assert "A PyZotero library error occurred:" in result.output
    assert "Code: 404" in result.output
    assert "Response: Not found" in result.output

# Test for `zot items create`, `delete`
def test_item_create_and_delete(runner: CliRunner, zot_instance):
    """Test creating an item and then deleting it."""
    item_title = f"Test Book Created by CLI - {uuid.uuid4()}" # Use uuid for uniqueness
    
    # Create item
    create_result = runner.invoke(zot, [
        'items', 'create', 
        '--template', 'book', 
        '--field', 'title', item_title
    ])
    if create_result.exit_code != 0:
        print("Create command raw output on non-zero exit:")
        print(create_result.output)
        print(f"Create command exception: {create_result.exception}")

    assert create_result.exit_code == 0
    
    # Diagnostic print if output is not as expected before trying to parse JSON
    if not create_result.output.strip().startswith('{'):
        print("Create command raw output (not JSON):")
        print(create_result.output)

    created_item_key = None
    try:
        create_data = json.loads(create_result.output)
        assert 'success' in create_data
        assert '0' in create_data['success'] # Assuming single item creation
        created_item_key = create_data['success']['0']
        assert created_item_key is not None
    except (json.JSONDecodeError, KeyError, AssertionError) as e:
        pytest.fail(f"Failed to parse create item response or find key: {e}\nOutput: {create_result.output}")

    # Verify item exists using zot_instance (direct API call)
    try:
        item_details = zot_instance.item(created_item_key)
        assert item_details is not None
        # Handle both dict and list return types for backwards compatibility
        if isinstance(item_details, list):
            assert item_details[0]['data']['title'] == item_title
        else:
            assert item_details['data']['title'] == item_title
    except Exception as e:
        # Cleanup attempt before failing
        if created_item_key:
            try:
                # Need version for delete usually, fetch fresh item for version
                item_to_delete = zot_instance.item(created_item_key)
                if item_to_delete:
                    if isinstance(item_to_delete, list):
                        zot_instance.delete_item(item_to_delete[0])
                    else:
                        zot_instance.delete_item(item_to_delete)
            except Exception:
                pass # Ignore cleanup error if primary assertion fails
        pytest.fail(f"Failed to verify created item {created_item_key} via API: {e}")

    # Delete item
    delete_result = runner.invoke(zot, ['items', 'delete', created_item_key, '--force'])
    assert delete_result.exit_code == 0
    try:
        delete_data = json.loads(delete_result.output)
        # Expecting list of dicts: [{'ITEM_KEY': 'Successfully deleted'}]
        assert isinstance(delete_data, list)
        assert len(delete_data) == 1
        assert delete_data[0].get(created_item_key) == "Successfully deleted"
    except (json.JSONDecodeError, IndexError, KeyError, AssertionError) as e:
        pytest.fail(f"Failed to parse delete response or verify success: {e}\nOutput: {delete_result.output}")

    # Verify item is deleted using zot_instance
    try:
        # zot_instance.item() for a deleted item should raise ResourceNotFoundError or return empty list
        # Pyzotero usually returns an empty list if item() is called with a non-existent key.
        # If zot_instance.delete_item was called directly, it would be clearer.
        # The CLI calls zot_client.delete_item(item_dict_with_key_and_version)
        deleted_item_check = zot_instance.item(created_item_key)
        assert not deleted_item_check, f"Item {created_item_key} should have been deleted."
    except Exception as e: # Catching general exception in case of unexpected API behavior
        # ResourceNotFoundError (404) is expected behavior for deleted items
        # Don't fail if we get a 404 - that's what we want
        if "404" in str(e) and "Item does not exist" in str(e):
            pass  # This is expected behavior
        else:
            pytest.fail(f"Error when checking if item {created_item_key} was deleted: {e}")


# Test for `zot items add-tags`
def test_item_add_tags(runner: CliRunner, zot_instance):
    """Test adding tags to an item."""
    # 1. Create a temporary item using zot_instance for simplicity in getting key/version
    template = zot_instance.item_template('journalArticle')
    item_title = f"Test Item for Adding Tags - {uuid.uuid4()}" # Use uuid
    template['title'] = item_title
    
    created_resp = zot_instance.create_items([template])
    assert created_resp['successful'] and '0' in created_resp['successful'], "Failed to create item for add-tags test"
    item_key = created_resp['successful']['0']['key']
    item_version = created_resp['successful']['0']['version']

    tag_to_add1 = f"clitag-{uuid.uuid4()}" # Use uuid
    tag_to_add2 = f"clitag-{uuid.uuid4()}" # Use uuid

    # 2. Add tags using the CLI command
    add_tags_result = runner.invoke(zot, [
        'items', 'add-tags', item_key, tag_to_add1, tag_to_add2
    ])
    assert add_tags_result.exit_code == 0
    try:
        add_tags_data = json.loads(add_tags_result.output)
        assert add_tags_data.get('status') == 'success'
        assert item_key == add_tags_data.get('item_key')
        assert sorted(add_tags_data.get('tags_added', [])) == sorted([tag_to_add1, tag_to_add2])
        
        # Immediate verification fetch
        check_item_after_cli = zot_instance.item(item_key)
        assert check_item_after_cli, f"Item {item_key} not found via API immediately after CLI 'add-tags' reported success."

    except (json.JSONDecodeError, AssertionError) as e:
        # Cleanup before failing
        try:
            zot_instance.delete_item({'key': item_key, 'version': item_version}) # Initial version
        except Exception: pass
        pytest.fail(f"Failed to parse add-tags response or verify success: {e}\nOutput: {add_tags_result.output}")

    # 3. Verify tags were added using zot_instance
    try:
        updated_item_details_list = zot_instance.item(item_key) # zot_instance.item() returns a list containing a dict
        assert updated_item_details_list
        if isinstance(updated_item_details_list, list):
            updated_item_details_dict = updated_item_details_list[0]
        else:
            # Handle case where item() returns a dict directly
            updated_item_details_dict = updated_item_details_list
            
        # Add debugging to see actual tag format
        print(f"DEBUG - Raw tags: {updated_item_details_dict['data']['tags']}")
        
        # Initialize empty list for retrieved tags
        retrieved_tags = []
        
        # Handle different tag formats - might be a list of dicts, strings, or a single string
        if updated_item_details_dict['data']['tags']:
            tags_data = updated_item_details_dict['data']['tags']
            
            if isinstance(tags_data, list):
                # Each tag might be a dict with 'tag' key or a string
                for tag_item in tags_data:
                    if isinstance(tag_item, dict) and 'tag' in tag_item:
                        retrieved_tags.append(tag_item['tag'])
                    elif isinstance(tag_item, str):
                        retrieved_tags.append(tag_item)
            elif isinstance(tags_data, str):
                # If tags is a single string (possibly string representation of list)
                if tags_data.startswith('[') and tags_data.endswith(']'):
                    # Handle string representation of list like "['tag1', 'tag2']"
                    import ast
                    try:
                        tags_list = ast.literal_eval(tags_data)
                        retrieved_tags = tags_list
                    except (SyntaxError, ValueError):
                        retrieved_tags = [tags_data]  # Just use the string as is
                else:
                    retrieved_tags = [tags_data]
        
        print(f"DEBUG - Processed tags: {retrieved_tags}")
        print(f"DEBUG - Looking for tags: {tag_to_add1}, {tag_to_add2}")
        
        # Check if our tags are in the processed list
        assert any(tag_to_add1 in tag for tag in retrieved_tags), f"Tag {tag_to_add1} not found in {retrieved_tags}"
        assert any(tag_to_add2 in tag for tag in retrieved_tags), f"Tag {tag_to_add2} not found in {retrieved_tags}"
        
        item_version = updated_item_details_dict['version'] # Update version for deletion
    except Exception as e:
        # Cleanup before failing
        try:
            zot_instance.delete_item({'key': item_key, 'version': item_version}) # Use potentially updated version
        except Exception: pass
        pytest.fail(f"Failed to verify tags on item {item_key} via API: {e}")
    finally:
        # 4. Cleanup: Delete the item
        try:
            # Fetch latest version before delete, as add_tags modifies it
            final_item_state = zot_instance.item(item_key)
            if final_item_state:
                if isinstance(final_item_state, list):
                    zot_instance.delete_item(final_item_state[0])
                else:
                    zot_instance.delete_item(final_item_state)
            # Also attempt to delete tags globally if they were created
            # zot_instance.delete_tags(tag_to_add1, tag_to_add2) # This might fail if tags not global, and that's ok.
        except Exception as e:
            print(f"Error during cleanup of item {item_key} or tags in test_item_add_tags: {e}")


# Test for `zot items update`
def test_item_update_field(runner: CliRunner, zot_instance):
    """Test updating an item's field using --field."""
    # 1. Create item using zot_instance
    template = zot_instance.item_template('book')
    original_title = f"Original Title - {uuid.uuid4()}"
    template['title'] = original_title
    created_resp = zot_instance.create_items([template])
    assert created_resp['successful'] and '0' in created_resp['successful'], "Failed to create item for update test"
    item_key = created_resp['successful']['0']['key']
    original_version = created_resp['successful']['0']['version']

    new_title = f"Updated Title - {uuid.uuid4()}"

    # 2. Update item using CLI
    update_result = runner.invoke(zot, [
        'items', 'update', item_key,
        '--field', 'title', new_title,
        '--last-modified', 'auto' # Use auto to ensure version check
    ])
    assert update_result.exit_code == 0
    try:
        update_data = json.loads(update_result.output)
        assert update_data.get('status') == 'success'
        assert update_data.get('item_key') == item_key

        # Immediate verification fetch
        check_item_after_cli = zot_instance.item(item_key)
        assert check_item_after_cli, f"Item {item_key} not found via API immediately after CLI 'update --field' reported success."

    except (json.JSONDecodeError, AssertionError) as e:
        try: # Cleanup attempt
            zot_instance.delete_item({'key': item_key, 'version': original_version})
        except Exception: pass
        pytest.fail(f"Failed to parse update response or verify success: {e}\nOutput: {update_result.output}")

    # 3. Verify update using zot_instance
    updated_item_details = None
    try:
        updated_item_list = zot_instance.item(item_key) # zot_instance.item() returns a list of dicts
        assert updated_item_list, "Updated item not found via API"
        
        # Handle both dict and list return types
        if isinstance(updated_item_list, list):
            updated_item_data = updated_item_list[0]
        else:
            updated_item_data = updated_item_list
            
        assert updated_item_data['data']['title'] == new_title
        assert updated_item_data['version'] > original_version, "Version should have incremented"
        updated_item_details = updated_item_data # For cleanup
    except Exception as e:
        pytest.fail(f"Failed to verify updated item {item_key} via API: {e}")
    finally:
        # 4. Cleanup
        if updated_item_details: # Use the latest fetched item for deletion
            zot_instance.delete_item(updated_item_details)
        elif item_key: # Fallback if fetch failed but we have the key
             try:
                # Try to delete with original version if new one unknown
                zot_instance.delete_item({'key': item_key, 'version': original_version}) 
             except Exception:
                 # If that fails, try to fetch again and delete
                 try:
                     item_to_delete = zot_instance.item(item_key)
                     if item_to_delete:
                         if isinstance(item_to_delete, list):
                             zot_instance.delete_item(item_to_delete[0])
                         else:
                             zot_instance.delete_item(item_to_delete)
                 except Exception as ex_clean:
                     print(f"Secondary cleanup attempt failed for item {item_key}: {ex_clean}")

def test_item_update_from_json_string(runner: CliRunner, zot_instance):
    """Test updating an item using --from-json with a JSON string."""
    # 1. Create item
    template = zot_instance.item_template('journalArticle')
    original_title = f"Original JSON Update Title - {uuid.uuid4()}"
    template['title'] = original_title
    created_resp = zot_instance.create_items([template])
    assert created_resp['successful'] and '0' in created_resp['successful']
    item_key = created_resp['successful']['0']['key']
    original_version = created_resp['successful']['0']['version']

    new_title_for_json = f"Updated JSON Title - {uuid.uuid4()}"
    # The --from-json in item_cmds.py updates item_to_update['data'].update(new_data_fields)
    # So the JSON should contain the fields to update within the 'data' structure, or just the fields themselves.
    # The item_cmds.py code is: new_data_fields = update_data.get('data', update_data)
    # item_to_update['data'].update(new_data_fields)
    # So, providing just {"title": "New Title"} should work.
    json_update_string = json.dumps({"title": new_title_for_json, "abstractNote": "Updated abstract"})

    # 2. Update item using CLI with JSON string
    update_result = runner.invoke(zot, [
        'items', 'update', item_key,
        '--from-json', json_update_string,
        '--last-modified', 'auto'
    ])
    assert update_result.exit_code == 0
    try:
        update_data = json.loads(update_result.output)
        assert update_data.get('status') == 'success'

        # Immediate verification fetch
        check_item_after_cli = zot_instance.item(item_key)
        assert check_item_after_cli, f"Item {item_key} not found via API immediately after CLI 'update --from-json' reported success."

    except (json.JSONDecodeError, AssertionError) as e:
        try: zot_instance.delete_item({'key': item_key, 'version': original_version}); 
        except Exception: pass
        pytest.fail(f"Update from JSON string failed parsing: {e}")

    # 3. Verify update
    updated_item_details = None
    try:
        updated_item_list = zot_instance.item(item_key) # zot_instance.item() returns a list of dicts
        assert updated_item_list
        
        # Handle both dict and list return types
        if isinstance(updated_item_list, list):
            updated_item_data = updated_item_list[0]
        else:
            updated_item_data = updated_item_list
            
        assert updated_item_data['data']['title'] == new_title_for_json
        assert updated_item_data['data']['abstractNote'] == "Updated abstract"
        assert updated_item_data['version'] > original_version
        updated_item_details = updated_item_data # For cleanup
    except Exception as e:
        pytest.fail(f"Failed to verify JSON update for item {item_key}: {e}")
    finally:
        # 4. Cleanup
        if updated_item_details:
            zot_instance.delete_item(updated_item_details)
        elif item_key:
            try: zot_instance.delete_item({'key': item_key, 'version': original_version}); 
            except Exception: 
                try: 
                    item_to_delete = zot_instance.item(item_key)
                    if item_to_delete:
                        if isinstance(item_to_delete, list):
                            zot_instance.delete_item(item_to_delete[0])
                        else:
                            zot_instance.delete_item(item_to_delete)
                except Exception: pass

# Test for `items children`
def test_item_children(runner: CliRunner, zot_instance):
    """Test `zot items children <parent_key>`."""
    # 1. Create a parent item
    parent_template = zot_instance.item_template('journalArticle')
    parent_title = f"Parent Article - {uuid.uuid4()}"
    parent_template['title'] = parent_title
    parent_resp = zot_instance.create_items([parent_template])
    assert parent_resp['successful'] and '0' in parent_resp['successful']
    parent_item_key = parent_resp['successful']['0']['key']
    parent_item_details = parent_resp['successful']['0'] # Keep for deletion

    # 2. Create a child note item linked to the parent
    child_template = zot_instance.item_template('note')
    child_template['note'] = f"Child note for {parent_item_key} - {uuid.uuid4()}"
    child_template['parentItem'] = parent_item_key
    child_resp = zot_instance.create_items([child_template])
    assert child_resp['successful'] and '0' in child_resp['successful']
    child_item_key = child_resp['successful']['0']['key']
    child_item_details = child_resp['successful']['0'] # Keep for deletion

    # 3. Invoke `zot items children`
    children_result = runner.invoke(zot, ['items', 'children', parent_item_key])
    assert children_result.exit_code == 0
    
    child_found_in_output = False
    try:
        children_data = json.loads(children_result.output)
        assert isinstance(children_data, list)
        for child in children_data:
            if child['key'] == child_item_key:
                child_found_in_output = True
                break
        assert child_found_in_output, f"Child item {child_item_key} not found in children list of {parent_item_key}"
    except (json.JSONDecodeError, AssertionError) as e:
        pytest.fail(f"Failed to parse children response or find child: {e}\nOutput: {children_result.output}")
    finally:
        # 4. Cleanup (delete child first, then parent)
        try:
            # Convert to dict if needed for deletion
            if isinstance(child_item_details, dict):
                zot_instance.delete_item(child_item_details)
            else:
                zot_instance.delete_item(child_item_details)
        except Exception as e_child:
            print(f"Error cleaning up child item {child_item_key}: {e_child}")
        try:
            # Convert to dict if needed for deletion
            if isinstance(parent_item_details, dict):
                zot_instance.delete_item(parent_item_details)
            else:
                zot_instance.delete_item(parent_item_details)
        except Exception as e_parent:
            print(f"Error cleaning up parent item {parent_item_key}: {e_parent}")

# Test for `items count`
def test_item_count(runner: CliRunner):
    """Test `zot items count`."""
    result = runner.invoke(zot, ['items', 'count'])
    assert result.exit_code == 0
    # Expected output: "Total items in library: X"
    assert "Total items in library:" in result.output
    try:
        count_str = result.output.split(":")[1].strip()
        assert int(count_str) >= 0 # Count should be a non-negative integer
    except (IndexError, ValueError) as e:
        pytest.fail(f"Could not parse item count from output: {result.output}\nError: {e}")

# Tests for `items bib` and `items citation`
def test_item_bib_and_citation(runner: CliRunner, zot_instance):
    """Test `zot items bib <key>` and `zot items citation <key>`."""
    # 1. Create a temporary item
    template = zot_instance.item_template('book')
    bib_test_title = f"Book for Bib/Cite Test - {uuid.uuid4()}"
    template['title'] = bib_test_title
    # Add a creator for better bib/citation output
    template['creators'] = [{'creatorType': 'author', 'firstName': 'Test', 'lastName': 'Author'}]
    
    created_resp = zot_instance.create_items([template])
    assert created_resp['successful'] and '0' in created_resp['successful']
    item_key = created_resp['successful']['0']['key']
    item_details = created_resp['successful']['0'] # For cleanup

    try:
        # Test `items bib`
        bib_result = runner.invoke(zot, ['items', 'bib', item_key])
        assert bib_result.exit_code == 0
        assert bib_result.output.strip() != "", "Bib output should not be empty."
        assert "<div class=\"csl-entry\">" in bib_result.output, "Bib output should contain csl-entry div."
        assert bib_test_title.lower() in bib_result.output.lower(), "Bib output should contain the item title (case-insensitive)."

        # Test `items citation`
        citation_result = runner.invoke(zot, ['items', 'citation', item_key])
        assert citation_result.exit_code == 0
        assert citation_result.output.strip() != "", "Citation output should not be empty."
        # Citations are often simpler, might be like (Author, Year) or just Author Year
        # For basic check, ensure it contains author or title part if no style applied.
        assert "author".lower() in citation_result.output.lower() or bib_test_title.lower() in citation_result.output.lower(), "Citation output seems empty or incorrect (case-insensitive)."
        # More specific checks could be style-dependent.

    finally:
        # 2. Cleanup
        try:
            zot_instance.delete_item(item_details)
        except Exception as e:
            print(f"Error cleaning up item {item_key} in bib/citation test: {e}")

# Test for `items get` with different output formats
def test_item_get_with_bibtex_format(runner: CliRunner, temp_item_with_tags):
    """Test `zot items get <item_key> --output bibtex` returns BibTeX format."""
    item_key, _ = temp_item_with_tags
    result = runner.invoke(zot, ['items', 'get', item_key, '--output', 'bibtex'])
    assert result.exit_code == 0
    # BibTeX format should start with @
    assert result.output.strip().startswith('@'), "BibTeX output should start with @"
    # Should not be JSON
    try:
        json.loads(result.output)
        pytest.fail("Output should not be valid JSON, but BibTeX format")
    except json.JSONDecodeError:
        # Expected - output should not be valid JSON
        pass

def test_item_get_with_csljson_format(runner: CliRunner, temp_item_with_tags):
    """Test `zot items get <item_key> --output csljson` returns CSL-JSON format."""
    item_key, _ = temp_item_with_tags
    result = runner.invoke(zot, ['items', 'get', item_key, '--output', 'csljson'])
    assert result.exit_code == 0
    # CSL-JSON should be valid JSON
    try:
        data = json.loads(result.output)
        # CSL-JSON usually has these keys at top level or as a list of objects with these keys
        csl_keys = ['id', 'type', 'title']
        
        # Handle both single object and list formats
        if isinstance(data, list):
            assert len(data) > 0, "CSL-JSON output should not be empty list"
            first_item = data[0]
        else:
            first_item = data
            
        # Check for at least one expected CSL-JSON key
        assert any(key in first_item for key in csl_keys), f"CSL-JSON should have some of these keys: {csl_keys}"
    except json.JSONDecodeError:
        pytest.fail("CSL-JSON output should be valid JSON")
    except KeyError as e:
        pytest.fail(f"Error accessing CSL-JSON data: {e}")

def test_item_get_with_bib_format_and_style(runner: CliRunner, zot_instance):
    """Test `zot items get <item_key> --output bib --style <style>`."""
    # 1. Create a temporary item with identifiable details
    template = zot_instance.item_template('book')
    test_title = f"Book for Bib Style Test - {uuid.uuid4()}"
    template['title'] = test_title
    template['creators'] = [{'creatorType': 'author', 'firstName': 'Test', 'lastName': 'Styler'}]
    
    created_resp = zot_instance.create_items([template])
    assert created_resp['successful'] and '0' in created_resp['successful']
    item_key = created_resp['successful']['0']['key']
    item_details = created_resp['successful']['0'] # For cleanup

    style_to_test = "apa" # A common CSL style

    try:
        result = runner.invoke(zot, ['items', 'get', item_key, '--output', 'bib', '--style', style_to_test])
        assert result.exit_code == 0
        assert result.output.strip() != "", "Bib output with style should not be empty."
        assert "<div class=\"csl-entry\">" in result.output, "Bib output with style should contain csl-entry div."
        # Check for elements that might indicate the style was applied (e.g., title, author)
        # Exact output depends on the style, so this is a basic check.
        assert test_title.lower() in result.output.lower(), "Bib output with style should contain the item title (case-insensitive)."
        assert "styler" in result.output.lower(), "Bib output with style should contain author name (case-insensitive)."

    finally:
        # 2. Cleanup
        try:
            zot_instance.delete_item(item_details)
        except Exception as e:
            print(f"Error cleaning up item {item_key} in bib style test: {e}")

def test_item_get_with_bib_format_and_linkwrap(runner: CliRunner, zot_instance):
    """Test `zot items get <item_key> --output bib --linkwrap`."""
    # 1. Create a temporary item with a URL
    template = zot_instance.item_template('webpage')
    test_title = f"Webpage for Linkwrap Test - {uuid.uuid4()}"
    test_url = f"http://example.com/{uuid.uuid4()}"
    template['title'] = test_title
    template['url'] = test_url
    
    created_resp = zot_instance.create_items([template])
    assert created_resp['successful'] and '0' in created_resp['successful']
    item_key = created_resp['successful']['0']['key']
    item_details = created_resp['successful']['0'] # For cleanup

    try:
        result = runner.invoke(zot, ['items', 'get', item_key, '--output', 'bib', '--linkwrap'])
        print(f"DEBUG linkwrap output: {result.output}")
        assert result.exit_code == 0
        assert result.output.strip() != "", "Bib output with linkwrap should not be empty."
        assert "<div class=\"csl-entry\">" in result.output, "Bib output with linkwrap should contain csl-entry div."
        # Check for the URL wrapped in an <a> tag
        # The exact format can vary based on CSL style, but we expect an <a> tag around the URL.
        assert f'href="{test_url}"' in result.output or f'href=\"{test_url}\"' in result.output
        assert f">{test_url}</a>" in result.output

    finally:
        # 2. Cleanup
        try:
            zot_instance.delete_item(item_details)
        except Exception as e:
            print(f"Error cleaning up item {item_key} in bib linkwrap test: {e}")


# More tests will be added here...
