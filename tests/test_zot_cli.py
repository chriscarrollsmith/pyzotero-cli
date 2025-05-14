import pytest
from pyzotero_cli.zot_cli import zot, CONFIG_FILE
import configparser
import json
from click.testing import CliRunner


def test_zot_help(runner: CliRunner):
    result = runner.invoke(zot, ['--help'])
    assert result.exit_code == 0
    assert "Usage: zot [OPTIONS] COMMAND [ARGS]..." in result.output
    assert "A CLI for interacting with Zotero libraries via Pyzotero." in result.output

def test_configure_list_profiles_no_config(isolated_config, runner: CliRunner):
    result = runner.invoke(zot, ['configure', 'list-profiles'])
    assert result.exit_code == 0
    # Expecting implicit default when no config file exists
    assert "* default (active, not explicitly configured)" in result.output

def test_configure_current_profile_no_config(isolated_config, runner: CliRunner):
    result = runner.invoke(zot, ['configure', 'current-profile'])
    assert result.exit_code == 0
    assert "default" in result.output.strip()

def test_configure_setup_new_profile(isolated_config, monkeypatch, runner: CliRunner):
    inputs = iter([
        'test_library_id',    # Library ID
        'user',               # Library Type
        'test_api_key',       # API Key
        'n',                  # Use local Zotero? (no)
        'en-GB'               # Locale
    ])
    monkeypatch.setattr('click.prompt', lambda *args, **kwargs: next(inputs))
    monkeypatch.setattr('click.confirm', lambda *args, **kwargs: next(inputs) == 'y')

    result = runner.invoke(zot, ['configure', 'setup', '--profile', 'testprofile'])
    assert result.exit_code == 0
    assert "Configuring profile: testprofile" in result.output
    assert "Configuration for profile 'testprofile' saved" in result.output

    # Verify config file content
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    assert f"profile.testprofile" in config
    assert config[f"profile.testprofile"]['library_id'] == 'test_library_id'
    assert config[f"profile.testprofile"]['library_type'] == 'user'
    assert config[f"profile.testprofile"]['api_key'] == 'test_api_key'
    assert config[f"profile.testprofile"]['local_zotero'] == 'False'
    assert config[f"profile.testprofile"]['locale'] == 'en-GB'
    assert config['zotcli']['current_profile'] == 'testprofile'

def test_configure_setup_default_profile(isolated_config, monkeypatch, runner: CliRunner):
    inputs = iter([
        'default_lib_id',     # Library ID
        'group',              # Library Type
        'default_api_key',    # API Key
        'y',                  # Use local Zotero? (yes)
        'fr-FR'               # Locale
    ])
    monkeypatch.setattr('click.prompt', lambda *args, **kwargs: next(inputs))
    monkeypatch.setattr('click.confirm', lambda *args, **kwargs: next(inputs) == 'y')

    result = runner.invoke(zot, ['configure', 'setup', '--profile', 'default'])
    assert result.exit_code == 0
    assert "Configuring profile: default" in result.output
    assert "Profile 'default' set as the current active profile." in result.output
    assert "Configuration for profile 'default' saved" in result.output

    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    assert 'default' in config
    assert config['default']['library_id'] == 'default_lib_id'
    assert config['default']['library_type'] == 'group'
    assert config['default']['api_key'] == 'default_api_key'
    assert config['default']['local_zotero'] == 'True' 
    assert config['default']['locale'] == 'fr-FR'
    assert config['zotcli']['current_profile'] == 'default'

def test_configure_set_and_get_value(isolated_config, runner: CliRunner):
    # First, set up a default profile to modify
    result_setup = runner.invoke(zot, ['configure', 'setup', '--profile', 'myprof'], input="test_id\nuser\ntest_key\nn\nen-US\n")
    assert result_setup.exit_code == 0

    # Set a value
    result_set = runner.invoke(zot, ['configure', 'set', 'library_id', 'new_lib_id', '--profile', 'myprof'])
    assert result_set.exit_code == 0
    assert "Set 'library_id' to 'new_lib_id' for profile 'myprof'" in result_set.output

    # Get the value
    result_get = runner.invoke(zot, ['configure', 'get', 'library_id', '--profile', 'myprof'])
    assert result_get.exit_code == 0
    assert result_get.output.strip() == 'new_lib_id'

    # Test setting boolean local_zotero
    result_set_local_true = runner.invoke(zot, ['configure', 'set', 'local_zotero', 'true', '--profile', 'myprof'])
    assert result_set_local_true.exit_code == 0
    result_get_local_true = runner.invoke(zot, ['configure', 'get', 'local_zotero', '--profile', 'myprof'])
    assert result_get_local_true.exit_code == 0
    assert result_get_local_true.output.strip() == 'True'

    result_set_local_false = runner.invoke(zot, ['configure', 'set', 'local_zotero', '0', '--profile', 'myprof'])
    assert result_set_local_false.exit_code == 0
    result_get_local_false = runner.invoke(zot, ['configure', 'get', 'local_zotero', '--profile', 'myprof'])
    assert result_get_local_false.exit_code == 0
    assert result_get_local_false.output.strip() == 'False'

def test_configure_get_non_existent_key(isolated_config, runner: CliRunner):
    result_setup = runner.invoke(zot, ['configure', 'setup', '--profile', 'another'], input="id\nuser\nkey\nn\n\n") # Empty locale
    assert result_setup.exit_code == 0

    result = runner.invoke(zot, ['configure', 'get', 'non_existent_key', '--profile', 'another'])
    assert result.exit_code == 0 # The command itself succeeds but prints to stderr
    assert "Key 'non_existent_key' not found in profile 'another'." in result.output # click.echo with err=True prints to stdout in CliRunner

def test_configure_list_profiles_multiple(isolated_config, monkeypatch, runner: CliRunner):
    # Profile 1: test1
    inputs1 = iter(['id1', 'user', 'key1', 'n', 'en-US'])
    monkeypatch.setattr('click.prompt', lambda *args, **kwargs: next(inputs1))
    monkeypatch.setattr('click.confirm', lambda *args, **kwargs: next(inputs1) == 'y')
    runner.invoke(zot, ['configure', 'setup', '--profile', 'test1'], catch_exceptions=False)

    # Profile 2: default
    inputs2 = iter(['id_default', 'group', 'key_default', 'y', 'fr-FR'])
    monkeypatch.setattr('click.prompt', lambda *args, **kwargs: next(inputs2))
    monkeypatch.setattr('click.confirm', lambda *args, **kwargs: next(inputs2) == 'y')
    runner.invoke(zot, ['configure', 'setup', '--profile', 'default'], catch_exceptions=False)
    
    # Profile 3: test2
    inputs3 = iter(['id2', 'user', 'key2', 'n', 'de-DE'])
    monkeypatch.setattr('click.prompt', lambda *args, **kwargs: next(inputs3))
    monkeypatch.setattr('click.confirm', lambda *args, **kwargs: next(inputs3) == 'y')
    runner.invoke(zot, ['configure', 'setup', '--profile', 'test2'], catch_exceptions=False)

    # Set current profile to test1 (default becomes current after its own setup, test2 after its own)
    # So explicitly set to test1 to check current profile listing logic
    runner.invoke(zot, ['configure', 'current-profile', 'test1'])

    result = runner.invoke(zot, ['configure', 'list-profiles'])
    assert result.exit_code == 0
    output = result.output
    assert "* test1 (active)" in output
    assert "  default (actual section)" in output # changed from '  default' to match code logic
    assert "  test2" in output

def test_configure_current_profile_set_and_get(isolated_config, monkeypatch, runner: CliRunner):
    # Setup a couple of profiles
    inputs_p1 = iter(['id1', 'user', 'key1', 'n', 'en-US'])
    monkeypatch.setattr('click.prompt', lambda *args, **kwargs: next(inputs_p1))
    monkeypatch.setattr('click.confirm', lambda *args, **kwargs: next(inputs_p1) == 'y')
    runner.invoke(zot, ['configure', 'setup', '--profile', 'prof1'])

    inputs_p2 = iter(['id2', 'user', 'key2', 'n', 'en-US'])
    monkeypatch.setattr('click.prompt', lambda *args, **kwargs: next(inputs_p2))
    monkeypatch.setattr('click.confirm', lambda *args, **kwargs: next(inputs_p2) == 'y')
    runner.invoke(zot, ['configure', 'setup', '--profile', 'prof2'])

    # Default is prof2 because it was configured last and set as current
    result_get1 = runner.invoke(zot, ['configure', 'current-profile'])
    assert result_get1.exit_code == 0
    assert result_get1.output.strip() == 'prof2' 

    # Set current profile to prof1
    result_set = runner.invoke(zot, ['configure', 'current-profile', 'prof1'])
    assert result_set.exit_code == 0
    assert "Active profile set to: prof1" in result_set.output

    # Get current profile again
    result_get2 = runner.invoke(zot, ['configure', 'current-profile'])
    assert result_get2.exit_code == 0
    assert result_get2.output.strip() == 'prof1'

    # Try to set a non-existent profile
    result_set_non_existent = runner.invoke(zot, ['configure', 'current-profile', 'nonexistent'])
    assert result_set_non_existent.exit_code == 0 # Command exits 0 but prints error
    assert "Error: Profile 'nonexistent' does not exist." in result_set_non_existent.output

    # Check that current profile is still prof1
    result_get3 = runner.invoke(zot, ['configure', 'current-profile'])
    assert result_get3.exit_code == 0
    assert result_get3.output.strip() == 'prof1'

def test_configure_without_credentials(isolated_config, runner: CliRunner):
    """
    Test that configure commands work without requiring API key, library ID, or library type.
    This specifically tests the early return in _zot_main_group_logic for 'configure' subcommands.
    """
    # Try to list profiles - this should work even with no credentials
    result_list = runner.invoke(zot, ['configure', 'list-profiles'])
    assert result_list.exit_code == 0
    assert "default" in result_list.output
    
    # Try to set up a new profile - should not fail due to credential validation
    result_setup = runner.invoke(
        zot, 
        ['configure', 'setup', '--profile', 'test_creds_exempt'], 
        input="123\nuser\nabc\nn\nen-US\n"
    )
    assert result_setup.exit_code == 0
    assert "Configuration for profile 'test_creds_exempt' saved" in result_setup.output
    
    # Verify that the configure commands still work even with the nested subcommands
    result_get = runner.invoke(zot, ['configure', 'get', 'library_id', '--profile', 'test_creds_exempt'])
    assert result_get.exit_code == 0
    assert result_get.output.strip() == '123'

def test_list_items_real_api(isolated_config, real_api_credentials, runner: CliRunner):
    """
    Tests 'zot items list --limit 1' using real API calls.
    Relies on Pyzotero picking up credentials from environment variables
    when no profile is configured and no explicit API key/library ID CLI args are passed.
    The 'isolated_config' fixture ensures no prior config interferes.
    The 'real_api_credentials' fixture provides credentials and handles skipping.
    """
    # This test specifically checks the --library-type global option.
    # We'll use 'user' for this test, assuming ZOTERO_LIBRARY_ID is for a user library
    # if real_api_credentials['library_type'] is also 'user'.
    # If ZOTERO_LIBRARY_TYPE is 'group', this still tests the override behavior of --library-type.
    cli_library_type_to_test = 'user'

    args = [
        '--library-type', cli_library_type_to_test,
        'items',
        'list',
        '--limit', '1'
    ]

    # Pass environment variables explicitly to runner.invoke to ensure Pyzotero sees them,
    # especially in CI environments or if the test runner isolates env vars.
    # isolated_config ensures that zot-cli itself doesn't find a configured profile with credentials.
    env_vars = {
        'ZOTERO_API_KEY': real_api_credentials['api_key'],
        'ZOTERO_LIBRARY_ID': real_api_credentials['library_id'],
        # Pass ZOTERO_LIBRARY_TYPE as well, as Pyzotero might use it if library_type is not passed to its constructor
        'ZOTERO_LIBRARY_TYPE': real_api_credentials['library_type'] 
    }

    result = runner.invoke(zot, args, catch_exceptions=False, env=env_vars)

    print(f"Output: {result.output}")
    print(f"Exception: {result.exception}")
    print(f"Exit Code: {result.exit_code}")

    assert result.exit_code == 0
    try:
        output_data = json.loads(result.output)
        assert isinstance(output_data, list)
        assert len(output_data) <= 1 
        if len(output_data) == 1:
            assert 'key' in output_data[0]
            assert 'version' in output_data[0]
            assert 'library' in output_data[0]
            # The type in the Zotero API response should match the --library-type we passed.
            assert output_data[0]['library']['type'] == cli_library_type_to_test
            # The library ID in the response should match the one from our environment variables.
            assert str(output_data[0]['library']['id']) == real_api_credentials['library_id']
    except json.JSONDecodeError:
        pytest.fail(f"Output was not valid JSON: {result.output}")

def test_list_items_with_active_profile(active_profile_with_real_credentials, real_api_credentials, runner: CliRunner):
    """
    Tests 'zot items list --limit 1' using a pre-configured active profile.
    The 'active_profile_with_real_credentials' fixture sets up this profile.
    This test ensures commands work correctly when relying on the active profile configuration.
    """
    # The active_profile_with_real_credentials fixture has already set up and activated
    # a profile (e.g., "ci_e2e_profile") with the credentials from real_api_credentials.
    # So, we don't need to pass --api-key, --library-id, or --library-type here.
    # The command should use the settings from the active profile.
    
    args = [
        # No global credential/library options needed here
        'items',
        'list',
        '--limit', '1'
    ]

    # No need to pass env_vars for credentials here, as zot-cli should read from the active profile
    result = runner.invoke(zot, args, catch_exceptions=False)

    print(f"Profile used (from fixture): {active_profile_with_real_credentials}")
    print(f"Output: {result.output}")
    print(f"Exception: {result.exception}")
    print(f"Exit Code: {result.exit_code}")

    assert result.exit_code == 0
    try:
        output_data = json.loads(result.output)
        assert isinstance(output_data, list)
        assert len(output_data) <= 1
        if len(output_data) == 1:
            item = output_data[0]
            assert 'key' in item
            assert 'version' in item
            assert 'library' in item
            # The library ID and type in the response should match those in the configured profile
            assert str(item['library']['id']) == real_api_credentials['library_id']
            assert item['library']['type'] == real_api_credentials['library_type']
    except json.JSONDecodeError:
        pytest.fail(f"Output was not valid JSON: {result.output}")

# More tests will be added here 