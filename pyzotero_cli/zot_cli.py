import click
import os
import configparser
from pyzotero_cli.utils import common_options # Import common_options
from pyzotero import zotero as pyzotero_client # Import the client class
from pyzotero import zotero_errors # Import exceptions
from .utils import handle_zotero_exceptions_and_exit # Import error handler

# Define the configuration directory and file path
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "zotcli")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.ini")

# Helper function to ensure config directory exists
def ensure_config_dir():
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)

# Helper function to load config
def load_config():
    ensure_config_dir()
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    return config

# Helper function to save config
def save_config(config):
    ensure_config_dir()
    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)

@click.group(name='zot')
@click.option('--profile', default=None, help='Use a specific configuration profile.')
@click.option('--api-key', default=None, help='Override API key.')
@click.option('--library-id', default=None, help='Override library ID.')
@click.option('--library-type', type=click.Choice(['user', 'group']), help='Override library type.')
@click.option('--local', is_flag=True, help='Use local Zotero instance (read-only).')
@click.option('--verbose', '-v', is_flag=True, help='Verbose logging.')
@click.option('--debug', is_flag=True, help='Debug logging.')
@click.option('--no-interaction', is_flag=True, help='Disable interactive prompts.')
@click.pass_context
def _zot_main_group_logic(ctx, profile, api_key, library_id, library_type, local, verbose, debug, no_interaction):
    """A CLI for interacting with Zotero libraries via Pyzotero."""
    ctx.ensure_object(dict)
    ctx.obj['PROFILE'] = profile
    ctx.obj['API_KEY'] = api_key
    ctx.obj['LIBRARY_ID'] = library_id
    ctx.obj['LIBRARY_TYPE'] = library_type
    ctx.obj['LOCAL'] = local
    ctx.obj['VERBOSE'] = verbose
    ctx.obj['DEBUG'] = debug
    ctx.obj['NO_INTERACTION'] = no_interaction

    # Skip credential validation and client instantiation for 'configure' commands
    if ctx.invoked_subcommand == 'configure':
        return

    config = load_config()
    active_profile_name = profile or config.get('zotcli', 'current_profile', fallback='default')

    if active_profile_name == 'default' and 'default' not in config:
        config.add_section('default') # Ensure default profile exists

    if f"profile.{active_profile_name}" not in config and active_profile_name != 'default':
         if not no_interaction:
            click.echo(f"Profile '{active_profile_name}' not found. Please create it using 'zot configure --profile {active_profile_name}'.")
            # Potentially exit or prompt for creation
            # For now, we'll proceed with potentially missing config
         ctx.obj['ACTIVE_PROFILE_NAME'] = active_profile_name
         ctx.obj['PROFILE_CONFIG'] = {}

    elif active_profile_name == 'default':
        ctx.obj['ACTIVE_PROFILE_NAME'] = 'default'
        ctx.obj['PROFILE_CONFIG'] = config['default'] if 'default' in config else {}
    else:
        ctx.obj['ACTIVE_PROFILE_NAME'] = active_profile_name
        ctx.obj['PROFILE_CONFIG'] = config[f"profile.{active_profile_name}"]

    # Determine effective configuration
    # Precedence: CLI > Environment Variable > Profile Config

    # Start with profile config values as baseline
    final_api_key = ctx.obj['PROFILE_CONFIG'].get('api_key')
    final_library_id = ctx.obj['PROFILE_CONFIG'].get('library_id')
    final_library_type = ctx.obj['PROFILE_CONFIG'].get('library_type')

    # Override with environment variables if they are set (and valid for type)
    env_api_key = os.environ.get('ZOTERO_API_KEY')
    if env_api_key:
        final_api_key = env_api_key

    env_library_id = os.environ.get('ZOTERO_LIBRARY_ID')
    if env_library_id:
        final_library_id = env_library_id

    env_library_type = os.environ.get('ZOTERO_LIBRARY_TYPE')
    if env_library_type and env_library_type in ['user', 'group']:
        final_library_type = env_library_type
    # If env_library_type is set but invalid, it does not override a potentially valid final_library_type from profile.

    # Override with CLI options if they were actually provided (parameters to this function)
    if api_key is not None:  # CLI --api-key option
        final_api_key = api_key
    if library_id is not None:  # CLI --library-id option
        final_library_id = library_id
    if library_type is not None:  # CLI --library-type option
        final_library_type = library_type
        
    ctx.obj['API_KEY'] = final_api_key
    ctx.obj['LIBRARY_ID'] = final_library_id
    ctx.obj['LIBRARY_TYPE'] = final_library_type
    
    # Locale and Local flag (original logic for these seemed okay, but let's ensure consistency if needed)
    # For Locale: CLI (--locale, though not a direct zot option) > ENV > Profile > Default
    # For Local: CLI (--local flag) > ENV > Profile > Default
    
    # Current zot() does not have a --locale option, it's per profile.
    # So LOCALE is ENV > Profile > Default
    ctx.obj['LOCALE'] = os.environ.get('ZOTERO_LOCALE', ctx.obj['PROFILE_CONFIG'].get('locale', 'en-US'))
    
    # For LOCAL flag (local parameter is from --local CLI flag on zot command)
    profile_local_str = str(ctx.obj['PROFILE_CONFIG'].getboolean('local_zotero', False))
    env_local_str = os.environ.get('ZOTERO_USE_LOCAL')

    # <<< START DEBUG PRINTS >>>
    if ctx.obj['DEBUG']: # Only print if --debug is passed to the main command
        click.echo(f"DEBUG: Initial --local flag value: {local}", err=True)
    # <<< END DEBUG PRINTS >>>

    if local: # CLI flag --local takes highest precedence
        ctx.obj['LOCAL'] = True
    elif env_local_str is not None:
        ctx.obj['LOCAL'] = env_local_str.lower() == 'true'
    else:
        ctx.obj['LOCAL'] = profile_local_str.lower() == 'true'

    # --- Check credentials and Instantiate the Zotero client ---

    # <<< START DEBUG PRINTS >>>
    if ctx.obj['DEBUG']:
        click.echo(f"DEBUG: Resolved ctx.obj['LOCAL']: {ctx.obj['LOCAL']}", err=True)
        click.echo(f"DEBUG: final_library_id: {final_library_id}", err=True)
        click.echo(f"DEBUG: final_library_type: {final_library_type}", err=True)
        click.echo(f"DEBUG: final_api_key: {final_api_key}", err=True)
        click.echo(f"DEBUG: API key to be used: {final_api_key if not ctx.obj['LOCAL'] else None}", err=True)
    # <<< END DEBUG PRINTS >>>

    # Ensure required credentials are present before trying to instantiate
    if not ctx.obj['LOCAL'] and not final_api_key:
        click.echo("Error: API key is required when not using --local mode. Set via --api-key, ZOTERO_API_KEY, or profile.", err=True)
        ctx.exit(1)
    if not final_library_id:
        click.echo("Error: Library ID is required. Set via --library-id, ZOTERO_LIBRARY_ID, or profile.", err=True)
        ctx.exit(1)
    if not final_library_type:
        click.echo("Error: Library type ('user' or 'group') is required. Set via --library-type, ZOTERO_LIBRARY_TYPE, or profile.", err=True)
        ctx.exit(1)

    try:
        # <<< START DEBUG PRINTS >>>
        if ctx.obj['DEBUG']:
            # Log the actual values that will be passed to the constructor
            click.echo(f"DEBUG: Instantiating Zotero with: library_id='{final_library_id}', library_type='{final_library_type}', api_key='{final_api_key if not ctx.obj['LOCAL'] else None}', local={ctx.obj['LOCAL']}, locale='{ctx.obj['LOCALE']}'", err=True)
        # <<< END DEBUG PRINTS >>>
        zot_client = pyzotero_client.Zotero(
            library_id=final_library_id,  # Pass directly
            library_type=final_library_type,  # Pass directly
            api_key=final_api_key if not ctx.obj['LOCAL'] else None,
            local=ctx.obj['LOCAL'],
            locale=ctx.obj['LOCALE'],
            # preserve_json_order could be added as an option/config if needed
        )
        ctx.obj['ZOTERO_CLIENT'] = zot_client

    except zotero_errors.PyZoteroError as e:
        # Use the shared handler for Zotero-specific errors during instantiation
        handle_zotero_exceptions_and_exit(ctx, e)
    except Exception as e: # Catch any other unexpected errors during init
        handle_zotero_exceptions_and_exit(ctx, e)

zot = _zot_main_group_logic

from pyzotero_cli.item_cmds import item_group # Import the item command group
from pyzotero_cli.collection_cmds import collection_group # Import the collection command group
from pyzotero_cli.tag_cmds import tag_group # Import the tag command group
from pyzotero_cli.file_cmds import file_group # Import the file command group
from pyzotero_cli.search_cmds import search_group # Import the search command group
from pyzotero_cli.fulltext_cmds import fulltext_group # Import the fulltext command group
from pyzotero_cli.group_cmds import group_group # Import the group command group
from pyzotero_cli.util_cmds import util_group # Import the utility command group

# Add command groups to the main zot application
zot.add_command(item_group, name='items')
zot.add_command(collection_group, name='collections')
zot.add_command(tag_group, name='tags')
zot.add_command(file_group, name='files')
zot.add_command(search_group, name='search')
zot.add_command(fulltext_group, name='fulltext')
zot.add_command(group_group, name='groups')
zot.add_command(util_group, name='util')

@zot.group()
def configure():
    """Manage zot-cli configuration profiles."""
    pass

@configure.command(name="setup")
@click.option('--profile', 'profile_name', default='default', help='Name of the profile to configure.')
@click.pass_context
def setup_profile(ctx, profile_name):
    """Interactive wizard to set up or modify a profile."""
    if ctx.obj.get('NO_INTERACTION'):
        click.echo("Interactive configuration disabled via --no-interaction.")
        return

    config = load_config()
    section_name = f"profile.{profile_name}" if profile_name != 'default' else 'default'

    if section_name not in config:
        config.add_section(section_name)

    click.echo(f"Configuring profile: {profile_name}")

    library_id = click.prompt("Enter Zotero Library ID", default=config.get(section_name, 'library_id', fallback=''))
    library_type = click.prompt("Enter Library Type (user/group)", type=click.Choice(['user', 'group']), default=config.get(section_name, 'library_type', fallback='user'))
    api_key = click.prompt("Enter Zotero API Key", default=config.get(section_name, 'api_key', fallback=''), hide_input=True)
    local_zotero = click.confirm("Use local Zotero instance (read-only)?", default=config.getboolean(section_name, 'local_zotero', fallback=False))
    locale = click.prompt("Enter locale", default=config.get(section_name, 'locale', fallback='en-US'))

    config[section_name]['library_id'] = library_id
    config[section_name]['library_type'] = library_type
    config[section_name]['api_key'] = api_key
    config[section_name]['local_zotero'] = str(local_zotero)
    config[section_name]['locale'] = locale

    if 'zotcli' not in config:
        config.add_section('zotcli')
    
    # Always set the newly configured or modified profile as the current active one.
    config['zotcli']['current_profile'] = profile_name
    click.echo(f"Profile '{profile_name}' set as the current active profile.")

    save_config(config)
    click.echo(f"Configuration for profile '{profile_name}' saved to {CONFIG_FILE}")

@configure.command(name="set")
@click.argument('key')
@click.argument('value')
@click.option('--profile', 'profile_name', default=None, help='Name of the profile to modify. Defaults to the active profile.')
@click.pass_context
def set_config(ctx, key, value, profile_name):
    """Set a specific configuration value for a profile."""
    config = load_config()
    active_profile_name = profile_name or ctx.obj.get('ACTIVE_PROFILE_NAME', 'default')
    section_name = f"profile.{active_profile_name}" if active_profile_name != 'default' else 'default'

    if section_name not in config:
        config.add_section(section_name)

    # Special handling for boolean 'local_zotero'
    if key == 'local_zotero':
        value = str(value.lower() in ['true', '1', 'yes', 'on'])
    
    config[section_name][key] = value
    save_config(config)
    click.echo(f"Set '{key}' to '{value}' for profile '{active_profile_name}'.")

@configure.command(name="get")
@click.argument('key')
@click.option('--profile', 'profile_name', default=None, help='Name of the profile to query. Defaults to the active profile.')
@click.pass_context
def get_config(ctx, key, profile_name):
    """Get a specific configuration value from a profile."""
    config = load_config()
    active_profile_name = profile_name or ctx.obj.get('ACTIVE_PROFILE_NAME', 'default')
    section_name = f"profile.{active_profile_name}" if active_profile_name != 'default' else 'default'

    if section_name in config and key in config[section_name]:
        click.echo(config[section_name][key])
    else:
        click.echo(f"Key '{key}' not found in profile '{active_profile_name}'.", err=True)


@configure.command(name="list-profiles")
def list_profiles_command():
    """List available configuration profiles."""
    config = load_config()
    profiles = [section.split('.', 1)[1] for section in config.sections() if section.startswith('profile.')]
    if 'default' in config: # Check if default profile exists as a section
        profiles.append('default (actual section)')
    elif not any(p == 'default' for p in profiles): # If no 'default' section, but might be implicitly active
        profiles.append('default (implicit)')


    current_profile = config.get('zotcli', 'current_profile', fallback='default')

    if not profiles:
        click.echo("No profiles found.")
        return

    for p_name in profiles:
        if p_name.endswith(' (implicit)') and current_profile == 'default' and 'default' not in config.sections():
             click.echo(f"* default (active, not explicitly configured)")
        elif p_name.endswith(' (actual section)') and p_name.startswith(current_profile):
            click.echo(f"* {current_profile} (active)")
        elif p_name == current_profile:
            click.echo(f"* {p_name} (active)")
        elif p_name.endswith(' (actual section)'):
             click.echo(f"  {p_name}")
        elif p_name.endswith(' (implicit)'):
            pass # Handled above
        else:
            click.echo(f"  {p_name}")


@configure.command(name="current-profile")
@click.argument('name', required=False)
@click.pass_context
def current_profile_command(ctx, name):
    """Get or set the active default profile."""
    config = load_config()
    if 'zotcli' not in config:
        config.add_section('zotcli')

    if name:
        # Set the current profile
        profile_section_name = f"profile.{name}" if name != 'default' else 'default'
        if name != 'default' and profile_section_name not in config:
            click.echo(f"Error: Profile '{name}' does not exist. Create it first with 'zot configure setup --profile {name}'.", err=True)
            return
        if name == 'default' and 'default' not in config: # Check if default section exists
            # It's okay to set 'default' as current even if the section isn't explicitly defined yet.
            # It will be created on first use or by 'zot configure setup --profile default'.
            pass


        config['zotcli']['current_profile'] = name
        save_config(config)
        click.echo(f"Active profile set to: {name}")
    else:
        # Get the current profile
        current = config.get('zotcli', 'current_profile', fallback='default')
        click.echo(current)

if __name__ == '__main__':
    zot() 