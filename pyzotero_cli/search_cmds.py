import click
import json
from pyzotero import zotero
from pyzotero_cli.utils import common_options, format_data_for_output, handle_zotero_exceptions_and_exit

@click.group('search')
@click.pass_context
def search_group(ctx):
    """Manage Zotero saved searches."""
    # Ensure the zotero instance is created and passed if not already
    if 'zot' not in ctx.obj:
        try:
            ctx.obj['zot'] = zotero.Zotero(
                ctx.obj.get('LIBRARY_ID'),
                ctx.obj.get('LIBRARY_TYPE'),
                ctx.obj.get('API_KEY'),
                locale=ctx.obj.get('LOCALE'),
                local=ctx.obj.get('LOCAL', False)
            )
        except Exception as e:
            handle_zotero_exceptions_and_exit(ctx, e)

@search_group.command('list')
@common_options # We'll refine which common options are applicable
@click.pass_context
def list_searches(ctx, limit, start, since, sort, direction, output, query, qmode, filter_tags, filter_item_type):
    """List saved searches metadata."""
    z = ctx.obj['zot']
    try:
        # The pyzotero method for listing saved searches is just .searches()
        # It doesn't take most of the common_options directly.
        # We should consider which common_options are relevant or remove if not.
        # For now, we'll ignore most of them for this specific command.
        saved_searches = z.searches()
        
        # Define how to display saved search data in a table
        table_headers_map = [
            ("Key", "key"),
            ("Name", "name"),
            ("Library ID", "library.id"),
            ("Version", "version")
        ]
        # 'conditions' can be complex, might be better for json/yaml or a summary
        
        click.echo(format_data_for_output(saved_searches, output, table_headers_map=table_headers_map, requested_fields_or_key='key'))

    except Exception as e:
        handle_zotero_exceptions_and_exit(ctx, e)

@search_group.command('create')
@click.option('--name', required=True, help='Name of the saved search.')
@click.option('--conditions-json', 'conditions_json_str', required=True,
              help='JSON string or path to a JSON file describing search conditions. '
                   'Format: [{"condition": "title", "operator": "contains", "value": "ecology"}, ...]')
@click.option('--output', type=click.Choice(['json', 'yaml', 'table', 'keys']), default='json', show_default=True, help='Output format for the created search confirmation.')
@click.pass_context
def create_search(ctx, name, conditions_json_str, output):
    """Create a new saved search."""
    z = ctx.obj['zot']
    conditions = []
    try:
        # Try to load from file first
        try:
            with open(conditions_json_str, 'r') as f:
                conditions = json.load(f)
        except FileNotFoundError:
            # If not a file, try to parse as a JSON string
            try:
                conditions = json.loads(conditions_json_str)
            except json.JSONDecodeError:
                click.echo(f"Error: --conditions-json input '{conditions_json_str}' is not a valid JSON file path or JSON string.", err=True)
                ctx.exit(1)

        if not isinstance(conditions, list) or not all(isinstance(c, dict) for c in conditions):
            click.echo("Error: Conditions JSON must be a list of condition objects.", err=True)
            ctx.exit(1)
        
        # Basic validation for condition structure (can be expanded)
        for cond in conditions:
            if not all(key in cond for key in ["condition", "operator", "value"]):
                click.echo(f"Error: Each condition object must contain 'condition', 'operator', and 'value' keys. Problematic condition: {cond}", err=True)
                ctx.exit(1)

        # Use pyzotero's saved_search, which returns API response data with success/failure info
        response = z.saved_search(name=name, conditions=conditions)
        
        # Check if the API call was successful by examining the response
        if response and 'successful' in response and response['successful']:
            search_key = response.get('successful', {}).get('0', {}).get('key')
            # Output a success message based on output format
            if output == 'table':
                click.echo(f"Saved search '{name}' created successfully.")
            elif output == 'keys' and search_key:
                click.echo(search_key) # Just output the key if keys format is requested
            else:
                # For JSON/YAML, include more details
                message_data = {
                    "name": name,
                    "key": search_key, 
                    "status": "created successfully"
                }
                click.echo(format_data_for_output(message_data, output))
        else:
            # Handle API failure response
            error_msg = response.get('failed', {}).get('0', {}).get('message', 'Unknown error')
            click.echo(f"Failed to create saved search '{name}': {error_msg}", err=True)
            ctx.exit(1)

    except Exception as e:
        handle_zotero_exceptions_and_exit(ctx, e)

@search_group.command('delete')
@click.argument('search_keys', nargs=-1, required=True)
@click.option('--force', is_flag=True, help='Skip confirmation before deleting.')
@click.pass_context
def delete_search(ctx, search_keys, force):
    """Delete one or more saved searches by their keys."""
    z = ctx.obj['zot']
    
    if not force:
        click.confirm(f"Are you sure you want to delete saved search(es) with key(s): {', '.join(search_keys)}?", abort=True)
    
    try:
        # Pyzotero's delete_saved_search returns HTTP status code
        status_code = z.delete_saved_search(search_keys)
        
        # Check for successful status code (2xx)
        if status_code in (200, 204):
            click.echo(f"Successfully deleted saved search(es): {', '.join(search_keys)}.")
        else:
            # Non-successful status code
            click.echo(f"Failed to delete one or more saved searches. Status code: {status_code}. Keys provided: {', '.join(search_keys)}", err=True)
            ctx.exit(1)

    except Exception as e:
        handle_zotero_exceptions_and_exit(ctx, e)

# Expose search_group to be imported in zot_cli.py
__all__ = ['search_group']
