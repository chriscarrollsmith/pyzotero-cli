import click
from pyzotero import zotero # Keep for type hinting if necessary, but not for instantiation here
import json # For parsing JSON input in 'set' command
from .utils import common_options, format_data_for_output, handle_zotero_exceptions_and_exit, create_click_exception, parse_json_input, initialize_zotero_client

@click.group("fulltext")
@click.pass_context
def fulltext_group(ctx):
    """Commands for working with Zotero full-text content."""
    ctx.obj['zot'] = initialize_zotero_client(ctx)


@fulltext_group.command("get")
@click.argument("item_key")
@click.option('--output', type=click.Choice(['json', 'yaml', 'raw_content']), default='json', show_default=True, help='Output format. "raw_content" outputs only the text content.')
@click.pass_context
def get_fulltext(ctx, item_key, output):
    """Retrieve full-text content for a specific attachment item."""
    zot_instance = ctx.obj['zot']
    try:
        data = zot_instance.fulltext_item(item_key)

        if output == 'raw_content':
            content = data.get('content', '')
            if isinstance(content, str):
                click.echo(content)
            else:
                click.echo("Warning: 'content' field is not a string.", err=True)
                click.echo(str(content)) # Output string representation as fallback
        else:
            formatted_output = format_data_for_output(data, output_format=output)
            click.echo(formatted_output)

    except Exception as e:
        handle_zotero_exceptions_and_exit(ctx, e)

@fulltext_group.command("list-new")
@click.option('--since', required=True, help='Library version to retrieve new full-text since.')
@click.option('--output', type=click.Choice(['json', 'yaml', 'table', 'keys']), default='json', show_default=True, help='Output format.')
@click.pass_context
def list_new_fulltext(ctx, since, output):
    """List items with new full-text content since a specific library version."""
    zot_instance = ctx.obj['zot']
    try:
        data = zot_instance.new_fulltext(since=since)
        if not data:
             click.echo("No new full-text content found since the specified version.")
             return

        if output == 'table':
            table_data = [{"itemKey": k, "libraryVersion": v} for k, v in data.items()]
            headers_map = [
                ("Item Key", "itemKey"),
                ("Library Version", "libraryVersion")
            ]
            formatted_output = format_data_for_output(table_data, output_format='table', table_headers_map=headers_map)
        elif output == 'keys':
            keys_list = list(data.keys())
            formatted_output = format_data_for_output(keys_list, output_format='keys')
        else:
            formatted_output = format_data_for_output(data, output_format=output)
        
        click.echo(formatted_output)

    except Exception as e:
        handle_zotero_exceptions_and_exit(ctx, e)

@fulltext_group.command("set")
@click.argument("item_key")
@click.option('--from-json', 'payload_json_input', required=True, help='JSON string or path to a JSON file containing the full-text payload.')
@click.pass_context
def set_fulltext(ctx, item_key, payload_json_input):
    """Set full-text data for an attachment item.
    Payload should be JSON: e.g., '{"content": "...", "indexedPages": 50, "totalPages": 50}'
    or for text docs: '{"content": "...", "indexedChars": 1000, "totalChars": 1000}'.
    """
    zot_instance = ctx.obj['zot']
    
    if ctx.obj.get('LOCAL', False):
        click.echo("Warning: Attempting 'set' fulltext with local Zotero. This may fail (read-only).", err=True)
        if not ctx.obj.get('NO_INTERACTION', False) and not click.confirm("Proceed anyway?"):
            ctx.abort()

    try:
        # Parse JSON input (either file path or JSON string)
        payload_dict = parse_json_input(payload_json_input, "Full-text payload")
        
        if not isinstance(payload_dict, dict):
            raise create_click_exception(
                description="Invalid payload format",
                details="Parsed payload is not a JSON object (dictionary)"
            )
        
        if "content" not in payload_dict:
            raise create_click_exception(
                description="Invalid payload format",
                details="Payload must have a 'content' key"
            )
        
        has_pages = "indexedPages" in payload_dict and "totalPages" in payload_dict
        has_chars = "indexedChars" in payload_dict and "totalChars" in payload_dict

        if not (has_pages or has_chars):
            raise create_click_exception(
                description="Incomplete payload format",
                details="Payload needs ('indexedPages' & 'totalPages') OR ('indexedChars' & 'totalChars')"
            )
        if has_pages and has_chars:
            click.echo("Warning: Payload has both page and char counts. Behavior may vary.", err=True)

        success = zot_instance.set_fulltext(item_key, payload_dict)
        if success:
            click.echo(f"Successfully set full-text for item '{item_key}'.")
        else:
            raise create_click_exception(
                description="Failed to set full-text content",
                context=f"Item key: '{item_key}'",
                details="API reported no success/error"
            )

    except Exception as e:
        handle_zotero_exceptions_and_exit(ctx, e)


