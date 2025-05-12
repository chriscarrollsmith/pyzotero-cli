import pytest
from click.testing import CliRunner
from pyzotero_cli.zot_cli import zot, CONFIG_FILE, CONFIG_DIR
import os
import shutil
import configparser
import json

@pytest.fixture(scope="function")
def isolated_config():
    """Ensure each test runs with a fresh config."""
    # Backup existing config if it exists
    backup_config_file = None
    if os.path.exists(CONFIG_FILE):
        backup_config_file = CONFIG_FILE + ".bak"
        shutil.copy2(CONFIG_FILE, backup_config_file)
        os.remove(CONFIG_FILE)
    
    # Ensure config dir exists for the test
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)

    yield

    # Clean up: remove the config file created during the test
    if os.path.exists(CONFIG_FILE):
        os.remove(CONFIG_FILE)
    
    # Restore backup if it existed
    if backup_config_file and os.path.exists(backup_config_file):
        shutil.move(backup_config_file, CONFIG_FILE)
    elif not backup_config_file and not os.path.exists(CONFIG_FILE) and os.path.exists(CONFIG_DIR):
        # If no backup and no config file, ensure dir is clean if we created it
        # but only if it's empty
        if not os.listdir(CONFIG_DIR):
             shutil.rmtree(CONFIG_DIR, ignore_errors=True)
        elif CONFIG_DIR == os.path.join(os.path.expanduser("~"), ".config", "zotcli"): # safety check
            # if the test created the dir, and it's not empty, but it's the specific one we manage
            # we might leave it. For now, let's try to remove if it's our specific one.
            # This is a bit tricky, might need adjustment based on test runs.
            # If a test fails mid-way, this cleanup might not run perfectly.
            pass


def test_zot_help():
    runner = CliRunner()
    result = runner.invoke(zot, ['--help'])
    assert result.exit_code == 0
    assert "Usage: zot [OPTIONS] COMMAND [ARGS]..." in result.output
    assert "A CLI for interacting with Zotero libraries via Pyzotero." in result.output

def test_configure_list_profiles_no_config(isolated_config):
    runner = CliRunner()
    result = runner.invoke(zot, ['configure', 'list-profiles'])
    assert result.exit_code == 0
    # Expecting implicit default when no config file exists
    assert "* default (active, not explicitly configured)" in result.output

def test_configure_current_profile_no_config(isolated_config):
    runner = CliRunner()
    result = runner.invoke(zot, ['configure', 'current-profile'])
    assert result.exit_code == 0
    assert "default" in result.output.strip()

def test_configure_setup_new_profile(isolated_config, monkeypatch):
    runner = CliRunner()
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

def test_configure_setup_default_profile(isolated_config, monkeypatch):
    runner = CliRunner()
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

def test_configure_set_and_get_value(isolated_config):
    runner = CliRunner()
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

def test_configure_get_non_existent_key(isolated_config):
    runner = CliRunner()
    result_setup = runner.invoke(zot, ['configure', 'setup', '--profile', 'another'], input="id\nuser\nkey\nn\n\n") # Empty locale
    assert result_setup.exit_code == 0

    result = runner.invoke(zot, ['configure', 'get', 'non_existent_key', '--profile', 'another'])
    assert result.exit_code == 0 # The command itself succeeds but prints to stderr
    assert "Key 'non_existent_key' not found in profile 'another'." in result.output # click.echo with err=True prints to stdout in CliRunner

def test_configure_list_profiles_multiple(isolated_config, monkeypatch):
    runner = CliRunner()
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

def test_configure_current_profile_set_and_get(isolated_config, monkeypatch):
    runner = CliRunner()
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

def test_list_items_real_api(isolated_config, monkeypatch):
    """
    Tests 'zot items --limit 1' using real API calls.
    Requires ZOTERO_API_KEY and ZOTERO_LIBRARY_ID environment variables.
    """
    runner = CliRunner()

    api_key = os.environ.get('ZOTERO_API_KEY')
    library_id = os.environ.get('ZOTERO_LIBRARY_ID')

    if not api_key or not library_id:
        pytest.skip("ZOTERO_API_KEY and ZOTERO_LIBRARY_ID environment variables are required for this test.")

    args = [
        '--library-type', 'user',
        'items',
        'list',
        '--limit', '1'
    ]

    result = runner.invoke(zot, args, catch_exceptions=False)

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
            assert output_data[0]['library']['type'] == 'user' 
            assert str(output_data[0]['library']['id']) == library_id
    except json.JSONDecodeError:
        pytest.fail(f"Output was not valid JSON: {result.output}")
    except Exception as e:
        pytest.fail(f"An unexpected error occurred: {e}\nOutput:\n{result.output}")

# More tests will be added here 