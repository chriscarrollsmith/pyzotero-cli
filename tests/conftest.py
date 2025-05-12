import pytest
import os
import shutil
import configparser
from pyzotero_cli.zot_cli import CONFIG_FILE, CONFIG_DIR
from click.testing import CliRunner

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
            # Log or handle if necessary, e.g., directory not empty unexpectedly
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
    # isolated_config ensures CONFIG_FILE is clean and CONFIG_DIR exists.
    # real_api_credentials provides details and handles skipping.
    
    profile_name = "ci_e2e_profile"  # A consistent name for this test profile
    config = configparser.ConfigParser()
    
    # CONFIG_FILE path comes from pyzotero_cli.zot_cli
    # isolated_config ensures the directory exists and the file is initially clear.

    section_name = f"profile.{profile_name}" # Non-default profiles are prefixed

    config.add_section(section_name)
    config[section_name]['library_id'] = real_api_credentials['library_id']
    config[section_name]['api_key'] = real_api_credentials['api_key']
    config[section_name]['library_type'] = real_api_credentials['library_type']
    config[section_name]['locale'] = 'en-US' # Default locale
    config[section_name]['local_zotero'] = 'False' # For API tests

    # Set this profile as the current active profile
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