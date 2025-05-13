import click
from pyzotero import zotero_errors

# Import shared utilities
from .utils import format_data_for_output, handle_zotero_exceptions_and_exit, common_options


@click.group(name="group")
def group_group():
    """Commands for interacting with Zotero groups."""
    pass

@group_group.command("list")
@common_options
@click.pass_context
def list_groups(ctx, limit, start, since, sort, direction, output, query, qmode, filter_tags, filter_item_type):
    """List groups the API key has access to.
    
    Note: Not all common options (e.g., query, filter-tag, filter-item-type, since) 
    are directly supported by the underlying PyZotero 'groups()' method.
    They are included for CLI consistency if a future version of PyZotero or a 
    different internal method supports them for groups.
    Currently, 'limit', 'start', 'sort', and 'direction' are the primary passthrough parameters.
    """
    try:
        zot_client = ctx.obj.get('ZOTERO_CLIENT')
        if not zot_client:
            click.echo("Error: Zotero client not initialized. Please check configuration.", err=True)
            if ctx: ctx.exit(1)
            else: import sys; sys.exit(1)

        # Parameters directly supported by zot_client.groups()
        # PyZotero's groups() method primarily accepts: limit, start, sort, direction.
        # Other parameters like q, qmode, tag, itemType are not standard for this call.
        params = {k: v for k, v in {
            'limit': limit, 
            'start': start, 
            'sort': sort,       # Passed if user provides it
            'direction': direction # Passed if user provides it
            # 'since': since, # Not typically used for zot.groups()
            # 'q': query,     # Not typically used for zot.groups()
            # 'qmode': qmode, # Not typically used for zot.groups()
            # 'tag': filter_tags, # Not typically used for zot.groups()
            # 'itemType': filter_item_type # Not typically used for zot.groups()
        }.items() if v is not None}
        
        # Acknowledge unused common options for this specific command if they were provided
        if query: click.echo("Warning: --query is not used by 'groups list'.", err=True)
        if qmode: click.echo("Warning: --qmode is not used by 'groups list'.", err=True)
        if filter_tags: click.echo("Warning: --filter-tag is not used by 'groups list'.", err=True)
        if filter_item_type: click.echo("Warning: --filter-item-type is not used by 'groups list'.", err=True)
        if since: click.echo("Warning: --since is not used by 'groups list'.", err=True)

        groups_data = zot_client.groups(**params)
        
        if not groups_data:
            click.echo("No groups found or accessible with the current API key and permissions.")
            return

        if output == 'keys':
            click.echo(format_data_for_output(groups_data, 'keys', requested_fields_or_key='id'))
        else:
            fields_map = [
                ('ID', lambda g: g.get('id')), ('Name', lambda g: g.get('data', {}).get('name')),
                ('Description', lambda g: g.get('data', {}).get('description', '')),
                ('Type', lambda g: g.get('data', {}).get('type')),
                ('Owner ID', lambda g: g.get('data', {}).get('owner')),
                ('Num Items', lambda g: g.get('meta', {}).get('numItems')),
                ('Version', lambda g: g.get('version')), 
                ('URL', lambda g: g.get('links', {}).get('alternate', {}).get('href'))
            ]
            
            if output in ['json', 'yaml']:
                click.echo(format_data_for_output(groups_data, output))
            else: # 'table'
                click.echo(format_data_for_output(groups_data, output, table_headers_map=fields_map))

    except zotero_errors.PyZoteroError as e:
        handle_zotero_exceptions_and_exit(ctx, e)
    except Exception as e: 
        handle_zotero_exceptions_and_exit(ctx, e)
