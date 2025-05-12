import click
from pyzotero import zotero_errors # For exception handling

# Import shared utilities
from .utils import format_data_for_output, handle_zotero_exceptions_and_exit

# Options decorator for the 'group list' command
def group_list_options(func):
    options = [
        click.option('--limit', type=int, help='Number of results to return.'),
        click.option('--start', type=int, help='Offset for pagination.'),
        click.option('--sort', help="Field to sort groups by (e.g., 'name', 'created', 'numItems')."),
        click.option('--direction', type=click.Choice(['asc', 'desc']), help="Sort direction ('asc' or 'desc')."),
        click.option('--output', type=click.Choice(['json', 'yaml', 'table', 'keys']), default='json', show_default=True, help='Output format.')
    ]
    for option in reversed(options):
        func = option(func)
    return func

@click.group(name="group")
def group_group():
    """Commands for interacting with Zotero groups."""
    pass

@group_group.command("list")
@group_list_options
@click.pass_context
def list_groups(ctx, limit, start, sort, direction, output):
    """List groups the API key has access to."""
    try:
        zot_client = ctx.obj.get('ZOTERO_CLIENT')
        if not zot_client:
            # This case should ideally be caught by client initialization in zot_cli.py
            click.echo("Error: Zotero client not initialized. Please check configuration.", err=True)
            if ctx: ctx.exit(1)
            else: import sys; sys.exit(1)

        params = {k: v for k, v in {'limit': limit, 'start': start, 'sort': sort, 'direction': direction}.items() if v is not None}
        
        groups_data = zot_client.groups(**params)
        
        if not groups_data:
            click.echo("No groups found or accessible with the current API key and permissions.")
            return

        if output == 'keys':
            # For groups, the primary key is 'id' at the top level of each group object.
            click.echo(format_data_for_output(groups_data, 'keys', requested_fields_or_key='id'))
        else:
            # Define how to extract and display group information for table/json/yaml
            fields_map = [
                ('ID', lambda g: g.get('id')),
                ('Name', lambda g: g.get('data', {}).get('name')),
                ('Description', lambda g: g.get('data', {}).get('description', '')),
                ('Type', lambda g: g.get('data', {}).get('type')),
                ('Owner ID', lambda g: g.get('data', {}).get('owner')),
                ('Num Items', lambda g: g.get('meta', {}).get('numItems')),
                ('Version', lambda g: g.get('version')), # Top-level version
                ('URL', lambda g: g.get('links', {}).get('alternate', {}).get('href'))
            ]
            
            if output in ['json', 'yaml']:
                # For JSON/YAML, pass the raw data as PyZotero returns it.
                click.echo(format_data_for_output(groups_data, output))
            else: # 'table'
                # The format_data_for_output will use fields_map to process raw groups_data for table display
                click.echo(format_data_for_output(groups_data, output, table_headers_map=fields_map))

    except zotero_errors.PyZoteroError as e:
        handle_zotero_exceptions_and_exit(ctx, e)
    except Exception as e: # Catch any other unexpected errors
        handle_zotero_exceptions_and_exit(ctx, e)
