import click
from pyzotero import zotero
from .utils import format_data_for_output, handle_zotero_exceptions_and_exit, initialize_zotero_client
from typing import cast
from tabulate import tabulate

@click.group(name='util')
@click.pass_context
def util_group(ctx):
    """Utility and informational commands."""
    # Ensure the context object is available for subcommands
    ctx.ensure_object(dict)

@util_group.command(name='key-info')
@click.option('--output', type=click.Choice(['json', 'yaml', 'table']), default='json', show_default=True, help='Output format.')
@click.pass_context
def key_info(ctx, output):
    """Display API key permissions."""
    try:
        zot = initialize_zotero_client(ctx)
        key_data = zot.key_info()
        
        if output == 'table' and key_data:
            # Custom formatting for key_info as it's a single dict, not a list of items
            headers = ["Property", "Value"]
            rows = []
            if isinstance(key_data, dict):
                rows.append(["Key", key_data.get("key", "")])
                rows.append(["User ID", key_data.get("userID", "")])
                rows.append(["Username", key_data.get("username", "")])
                rows.append(["Access", str(key_data.get("access", {}))]) # Convert dict to string for table
            
            click.echo(tabulate(rows, headers=headers, tablefmt="grid"))

        else:
            click.echo(format_data_for_output(key_data, output))

    except Exception as e:
        handle_zotero_exceptions_and_exit(ctx, e)

@util_group.command(name='last-modified-version')
@click.pass_context
def last_modified_version(ctx):
    """Get the library's last modified version."""
    try:
        zot = initialize_zotero_client(ctx)
        version = zot.last_modified_version()
        click.echo(version)
    except Exception as e:
        handle_zotero_exceptions_and_exit(ctx, e)

@util_group.command(name='item-types')
@click.option('--output', type=click.Choice(['json', 'yaml', 'table']), default='json', show_default=True, help='Output format.')
@click.pass_context
def item_types(ctx, output):
    """List all available item types."""
    try:
        # For item_types, we don't need full Zotero client, can call class method
        # However, to respect potential 'local' or 'locale' settings if they were to influence this,
        # we instantiate, though pyzotero's item_types is static currently.
        zot = initialize_zotero_client(ctx)
        types_data = zot.item_types()
        if output == 'table':
            headers = ["Item Type", "Localized Name"]
            rows = [[cast(dict, it).get('itemType', ''), cast(dict, it).get('localized', '')] for it in types_data]
            click.echo(tabulate(rows, headers=headers, tablefmt="grid"))
        else:
            click.echo(format_data_for_output(types_data, output))
    except Exception as e:
        handle_zotero_exceptions_and_exit(ctx, e)

@util_group.command(name='item-fields')
@click.option('--output', type=click.Choice(['json', 'yaml', 'table']), default='json', show_default=True, help='Output format.')
@click.pass_context
def item_fields(ctx, output):
    """List all available item fields."""
    try:
        zot = initialize_zotero_client(ctx)
        fields_data = zot.item_fields()
        if output == 'table':
            headers = ["Field", "Localized Name"]
            rows = [[cast(dict, f).get('field', ''), cast(dict, f).get('localized', '')] for f in fields_data]
            click.echo(tabulate(rows, headers=headers, tablefmt="grid"))
        else:
            click.echo(format_data_for_output(fields_data, output))
    except Exception as e:
        handle_zotero_exceptions_and_exit(ctx, e)

@util_group.command(name='item-type-fields')
@click.argument('item_type')
@click.option('--output', type=click.Choice(['json', 'yaml', 'table']), default='json', show_default=True, help='Output format.')
@click.pass_context
def item_type_fields(ctx, item_type, output):
    """List fields for a specific item type."""
    try:
        zot = initialize_zotero_client(ctx)
        type_fields_data = zot.item_type_fields(itemtype=item_type)
        if output == 'table':
            headers = ["Field", "Localized Name"]
            rows = [[cast(dict, f).get('field', ''), cast(dict, f).get('localized', '')] for f in type_fields_data]
            click.echo(tabulate(rows, headers=headers, tablefmt="grid"))
        else:
            click.echo(format_data_for_output(type_fields_data, output))
    except Exception as e:
        handle_zotero_exceptions_and_exit(ctx, e)

@util_group.command(name='item-template')
@click.argument('item_type')
@click.option('--linkmode', type=click.Choice(['imported_file', 'imported_url', 'linked_file', 'linked_url']), help='Link mode for attachments.')
@click.option('--output', type=click.Choice(['json']), default='json', show_default=True, help='Output format (only JSON supported).')
@click.pass_context
def item_template(ctx, item_type, linkmode, output): # Added output param for consistency, though only json
    """Generate an item template (for item create)."""
    try:
        zot = initialize_zotero_client(ctx)
        params = {}
        if linkmode:
            params['linkmode'] = linkmode
        template_data = zot.item_template(item_type, **params)
        # Per spec, only JSON output. format_data_for_output will handle this.
        click.echo(format_data_for_output(template_data, 'json'))
    except Exception as e:
        handle_zotero_exceptions_and_exit(ctx, e)
