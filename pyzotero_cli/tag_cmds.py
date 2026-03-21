import click
import json
from pyzotero import zotero
from .utils import common_options, format_data_for_output, handle_zotero_exceptions_and_exit, create_click_exception, initialize_zotero_client

@click.group(name='tags')
@click.pass_context
def tag_group(ctx):
    """Manage Zotero tags."""
    ctx.obj['zot'] = initialize_zotero_client(ctx)

@tag_group.command(name='list')
@common_options
@click.pass_context
def list_tags(ctx, **kwargs):
    """List all tags in the library."""
    zot = ctx.obj['zot']
    
    # Extract relevant parameters for the tags call
    params = {k: v for k, v in kwargs.items() if v is not None and k in 
             ['limit', 'start', 'sort', 'direction']}
    
    try:
        # Get tags from the library
        tags = zot.tags(**params)
        
        # Use format_data_for_output for consistent formatting
        output_format = kwargs.get('output', 'json')
        click.echo(format_data_for_output(tags, output_format, preset_key='tag'))
        
    except Exception as e:
        handle_zotero_exceptions_and_exit(ctx, e)

@tag_group.command(name='list-for-item')
@common_options
@click.argument('item_key', required=True)
@click.pass_context
def list_item_tags(ctx, item_key, **kwargs):
    """List tags for a specific item."""
    zot = ctx.obj['zot']
    
    # Extract relevant parameters for the item_tags call
    params = {k: v for k, v in kwargs.items() if v is not None and k in 
             ['limit', 'start', 'sort', 'direction']}
    
    try:
        # Get tags for the specific item
        tags = zot.item_tags(item_key, **params)
        
        # Use format_data_for_output for consistent formatting
        output_format = kwargs.get('output', 'json')
        click.echo(format_data_for_output(tags, output_format, preset_key='tag'))
        
    except Exception as e:
        handle_zotero_exceptions_and_exit(ctx, e)

@tag_group.command(name='delete')
@click.argument('tag_names', nargs=-1, required=True)
@click.option('--force', is_flag=True, help='Skip confirmation prompt.')
@click.pass_context
def delete_tags(ctx, tag_names, force):
    """Delete tag(s) from the library."""
    zot = ctx.obj['zot']
    
    if not force and not ctx.obj.get('NO_INTERACTION'):
        if not click.confirm(f"Are you sure you want to delete the following tags: {', '.join(tag_names)}?"):
            click.echo("Operation cancelled.")
            return
    
    try:
        result = zot.delete_tags(*tag_names)
        click.echo(f"Successfully deleted tags: {', '.join(tag_names)}")
    except Exception as e:
        handle_zotero_exceptions_and_exit(ctx, e)
