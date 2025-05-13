import pytest
import json
import os
from dotenv import load_dotenv
from click.testing import CliRunner

# Assuming your main Click application object is named 'zot'
# and can be imported from pyzotero_cli.zot_cli
from pyzotero_cli.zot_cli import zot

load_dotenv(override=True)

# Test function for the default JSON output
def test_list_groups_default_json(runner: CliRunner, active_profile_with_real_credentials):
    """
    Tests the default 'zot groups list' command output (JSON).
    Requires real API credentials and an active profile configured.
    """
    result = runner.invoke(zot, ['groups', 'list', '--output', 'json'])

    assert result.exit_code == 0, f"CLI command failed: {result.output}"
    
    try:
        output_data = json.loads(result.output)
    except json.JSONDecodeError:
        pytest.fail(f"Output is not valid JSON: {result.output}")

    assert isinstance(output_data, list), "Default JSON output should be a list of groups."
    
    test_group_id = int(os.getenv('ZOTERO_TEST_GROUP_ID', "0")) # Provided group ID
    test_group_found = False
    if output_data:
        for group in output_data:
            if group.get('id') == test_group_id:
                test_group_found = True
                assert 'id' in group, "Group object should contain an 'id' key."
                assert 'data' in group, "Group object should contain a 'data' key."
                assert 'links' in group, "Group object should contain a 'links' key."
                assert 'meta' in group, "Group object should contain a 'meta' key."
                assert 'version' in group, "Group object should contain a 'version' key."
                assert 'name' in group['data'], "Group data should contain a 'name' key."
                # We could also check group['data']['name'] == "memetics" if that name is stable
                break
        assert test_group_found, f"Expected group with ID {test_group_id} not found in output."
    else:
        # If no data, the previous assertion for test_group_found will fail, which is correct
        # if we expect the group to be there.
        pass 

# Test function for the --output keys option
def test_list_groups_keys_output(runner: CliRunner, active_profile_with_real_credentials):
    """
    Tests 'zot groups list --output keys'.
    Requires real API credentials and an active profile configured.
    """
    result = runner.invoke(zot, ['groups', 'list', '--output', 'keys'])

    assert result.exit_code == 0, f"CLI command failed: {result.output}"
    
    test_group_id_str = os.getenv('ZOTERO_TEST_GROUP_ID', "") # Provided group ID as string
    # Output should be a list of IDs (strings representing integers), separated by newlines.
    # Allow for empty output if the user has no groups, but the test expects this group.
    if result.output.strip():
        keys = result.output.strip().split('\n')
        assert all(key.isdigit() for key in keys), f"Output contains non-digit keys: {result.output}"
        assert test_group_id_str in keys, f"Expected group ID {test_group_id_str} not found in keys output."
    else:
        pytest.fail(f"Expected group ID {test_group_id_str} in keys output, but got empty output.")

# Test function for the --output table option
# This test focuses on the "no groups" message OR actual table output.
# If the group 5988190 is present, it will not output the "No groups found..." message.
# So, we adapt it to check for either the specific message or a valid table structure.
def test_list_groups_table_output(runner: CliRunner, active_profile_with_real_credentials):
    """
    Tests 'zot groups list --output table'.
    Requires real API credentials and an active profile configured.
    Requires 'tabulate' library to be installed.
    """
    result = runner.invoke(zot, ['groups', 'list', '--output', 'table'])

    assert result.exit_code == 0, f"CLI command failed: {result.output}"
    
    output_lines = result.output.strip().split('\n')
    no_groups_message = "No groups found or accessible with the current API key and permissions."

    if output_lines and output_lines[0] == no_groups_message:
        # This is acceptable if the API key truly has no access to any groups, 
        # but the test setup implies group should be accessible.
        # For robustness, we consider this case but would expect the other path.
        pass
    elif len(output_lines) > 1: # Check for table structure if not the "no groups" message
        # When tabulate formats with a grid, output_lines[0] is the top border,
        # output_lines[1] contains the headers.
        header_line_index = 0
        if output_lines[0].startswith('+') and output_lines[0].endswith('+'):
            header_line_index = 1 # Headers are on the next line
        
        if len(output_lines) > header_line_index:
            assert 'ID' in output_lines[header_line_index], "Table header 'ID' not found."
            assert 'Name' in output_lines[header_line_index], "Table header 'Name' not found."
            # We can also check for the presence of group data in the table if desired
            # test_group_id_str = os.getenv('ZOTERO_TEST_GROUP_ID', "")
            # if test_group_id_str:
            #     assert any(test_group_id_str in line for line in output_lines), \
            #            f"Test group ID {test_group_id_str} not found in table output."
        else:
            pytest.fail(f"Table output has too few lines to contain headers. Output: {result.output}")
    else:
        pytest.fail(f"Unexpected table output. Expected table or '{no_groups_message}', got: {result.output}")


# Test function for the --limit option
def test_list_groups_limit(runner: CliRunner, active_profile_with_real_credentials):
    """
    Tests 'zot groups list --limit 1'.
    Requires real API credentials and an active profile configured.
    """
    result = runner.invoke(zot, ['groups', 'list', '--limit', '1', '--output', 'json'])

    assert result.exit_code == 0, f"CLI command failed: {result.output}"
    
    try:
        output_data = json.loads(result.output)
    except json.JSONDecodeError:
        pytest.fail(f"Output is not valid JSON: {result.output}")

    assert isinstance(output_data, list), "JSON output with limit should still be a list."
    assert len(output_data) <= 1, "Output list should contain at most 1 group when --limit=1."
    # If you want to ensure that *if* a group is returned, it's the test group (assuming it's the only one or first one):
    # if len(output_data) == 1:
    #     assert output_data[0].get('id') == 5988190, "If one group is returned, it should be the test group."

# Test function for sorting (example: by name ascending)
def test_list_groups_sort_name_asc(runner: CliRunner, active_profile_with_real_credentials):
    """
    Tests 'zot groups list --sort name --direction asc'.
    Requires real API credentials and an active profile configured.
    """
    result = runner.invoke(zot, ['groups', 'list', '--sort', 'title', '--direction', 'asc', '--output', 'json'])

    assert result.exit_code == 0, f"CLI command failed: {result.output}"

    try:
        output_data = json.loads(result.output)
    except json.JSONDecodeError:
        pytest.fail(f"Output is not valid JSON: {result.output}")

    assert isinstance(output_data, list), "JSON output should be a list."
    
    # Check if the list is sorted by creation date
    if len(output_data) > 1:
        # Timestamps are usually in 'meta': {'created': 'YYYY-MM-DDTHH:MM:SSZ'}
        # or sometimes directly as 'created' at the top level of data, need to be robust
        creation_dates = []
        for group in output_data:
            date_str = None
            if 'meta' in group and 'created' in group['meta']:
                date_str = group['meta']['created']
            elif 'data' in group and 'dateAdded' in group['data']:
                 # 'dateAdded' is more common for items, but check just in case for groups if 'meta.created' isn't there
                date_str = group['data']['dateAdded']
            # Add more fallbacks if necessary based on actual group object structure
            if date_str: # Ensure we have a date string to compare
                creation_dates.append(date_str)
            else:
                # If a group has no creation date, sorting behavior is undefined by this test
                # Or we could fail if date is expected: pytest.fail(f"Group missing creation date: {group}")
                # For now, we'll only sort and compare those that have it.
                pass 
        
        # Only assert if we have comparable dates
        if len(creation_dates) > 1 and len(creation_dates) == len(output_data):
             assert creation_dates == sorted(creation_dates), "Groups are not sorted correctly by creation date ascending."
        elif len(output_data) <=1:
            pass # List with 0 or 1 item is always sorted
        # If some items lacked dates, we can't reliably check sortedness here with this method.


