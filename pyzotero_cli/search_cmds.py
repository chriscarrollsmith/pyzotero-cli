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
@click.option('--output', type=click.Choice(['json', 'yaml', 'table', 'keys']), default='table', show_default=True, help='Output format for the created search confirmation.')
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

        # Use pyzotero's create_saved_search, which returns True on success or False.
        success = z.create_saved_search(name=name, conditions=conditions)
        
        if success:
            # Output a simple success message. The user can list searches to see details.
            message_data = {"name": name, "status": "created successfully"}
            if output == 'table':
                click.echo(f"Saved search '{name}' created successfully.")
            elif output == 'keys': # Not typical for create, but handle gracefully
                 click.echo(name) # Or perhaps nothing, as there's no key from create_saved_search
            else:
                click.echo(format_data_for_output(message_data, output))
        else:
            click.echo(f"Failed to create saved search '{name}'.", err=True)
            # Pyzotero's create_saved_search doesn't provide detailed error messages on False return,
            # but an exception would be caught by handle_zotero_exceptions_and_exit.

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
        # Pyzotero's delete_saved_search expects a list of keys.
        # It returns True if all deletions were successful, False otherwise, or raises an exception.
        deleted_count = 0
        failed_keys = []

        # The method is zot.delete_saved_search(key_or_list_of_keys)
        # If a single key is passed, it works. If a list, it tries to delete all.
        # It returns True for success, False if any fail.
        # Let's adapt to iterate and give more specific feedback if possible,
        # or rely on its batch behavior. The current pyzotero docs say "key or list of keys".
        # The rule doc says "list of unique saved search keys".

        # If z.delete_saved_search handles a list and returns a boolean for overall success:
        success = z.delete_saved_search(search_keys)
        if success:
             click.echo(f"Successfully deleted saved search(es): {', '.join(search_keys)}.")
        else:
            # This doesn't tell us WHICH ones failed if it's a batch operation
            # returning a single False.
            click.echo(f"Failed to delete one or more saved searches. Keys provided: {', '.join(search_keys)}", err=True)
            click.echo("Note: Pyzotero's batch delete might not specify which exact key(s) failed.", err=True)

    except Exception as e:
        handle_zotero_exceptions_and_exit(ctx, e)

# Expose search_group to be imported in zot_cli.py
__all__ = ['search_group']
