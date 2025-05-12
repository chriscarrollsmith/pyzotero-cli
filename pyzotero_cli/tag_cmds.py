import click
import json
from pyzotero import zotero
from .utils import common_options

@click.group(name='tag')
def tag_group():
    """Commands for working with Zotero tags."""
    pass

@tag_group.command(name='list')
@common_options
@click.pass_context
def list_tags(ctx, **kwargs):
    """List all tags in the library."""
    zot = zotero.Zotero(
        ctx.obj['LIBRARY_ID'],
        ctx.obj['LIBRARY_TYPE'],
        ctx.obj['API_KEY'],
        locale=ctx.obj['LOCALE']
    )
    
    # Extract relevant parameters for the tags call
    params = {k: v for k, v in kwargs.items() if v is not None and k in 
             ['limit', 'start', 'sort', 'direction']}
    
    # Get tags from the library
    tags = zot.tags(**params)
    
    # Output based on format preference
    output_format = kwargs.get('output', 'json')
    if output_format == 'yaml':
        import yaml
        click.echo(yaml.dump(tags))
    elif output_format == 'table':
        for tag in tags:
            click.echo(tag)
    else:  # Default is JSON output
        click.echo(json.dumps(tags))

@tag_group.command(name='list-for-item')
@common_options
@click.argument('item_key', required=True)
@click.pass_context
def list_item_tags(ctx, item_key, **kwargs):
    """List tags for a specific item."""
    zot = zotero.Zotero(
        ctx.obj['LIBRARY_ID'],
        ctx.obj['LIBRARY_TYPE'],
        ctx.obj['API_KEY'],
        locale=ctx.obj['LOCALE']
    )
    
    # Extract relevant parameters for the item_tags call
    params = {k: v for k, v in kwargs.items() if v is not None and k in 
             ['limit', 'start', 'sort', 'direction']}
    
    # Get tags for the specific item
    try:
        tags = zot.item_tags(item_key, **params)
        
        # Output based on format preference
        output_format = kwargs.get('output', 'json')
        if output_format == 'yaml':
            import yaml
            click.echo(yaml.dump(tags))
        elif output_format == 'table':
            for tag in tags:
                click.echo(tag)
        else:  # Default is JSON output
            click.echo(json.dumps(tags))
    except Exception as e:
        click.echo(f"Error retrieving tags for item {item_key}: {str(e)}", err=True)

@tag_group.command(name='delete')
@click.argument('tag_names', nargs=-1, required=True)
@click.option('--force', is_flag=True, help='Skip confirmation prompt.')
@click.pass_context
def delete_tags(ctx, tag_names, force):
    """Delete tag(s) from the library."""
    zot = zotero.Zotero(
        ctx.obj['LIBRARY_ID'],
        ctx.obj['LIBRARY_TYPE'],
        ctx.obj['API_KEY'],
        locale=ctx.obj['LOCALE']
    )
    
    if not force and not ctx.obj.get('NO_INTERACTION'):
        if not click.confirm(f"Are you sure you want to delete the following tags: {', '.join(tag_names)}?"):
            click.echo("Operation cancelled.")
            return
    
    try:
        result = zot.delete_tags(*tag_names)
        click.echo(f"Successfully deleted tags: {', '.join(tag_names)}")
    except Exception as e:
        click.echo(f"Error deleting tags: {str(e)}", err=True)
