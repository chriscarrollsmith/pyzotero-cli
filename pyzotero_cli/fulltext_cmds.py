import click
from pyzotero import zotero
import json # For parsing JSON input in 'set' command
from .utils import common_options, format_data_for_output, handle_zotero_exceptions_and_exit

@click.group("fulltext")
@click.pass_context
def fulltext_group(ctx):
    """Commands for working with full-text content."""
    try:
        profile_config = ctx.obj.get('PROFILE_CONFIG', {})
        api_key_val = ctx.obj.get('API_KEY', profile_config.get('api_key'))
        library_id_val = ctx.obj.get('LIBRARY_ID', profile_config.get('library_id'))
        library_type_val = ctx.obj.get('LIBRARY_TYPE', profile_config.get('library_type'))
        locale_val = ctx.obj.get('LOCALE', profile_config.get('locale', 'en-US'))
        use_local_server = ctx.obj.get('LOCAL', profile_config.getboolean('local_zotero', False))

        if not library_id_val:
            click.echo("Error: Library ID is required. Configure with 'zot configure setup'.", err=True)
            ctx.exit(1)

        zot_kwargs = {
            "library_id": library_id_val,
            "locale": locale_val
        }

        if use_local_server:
            zot_kwargs["local"] = library_id_val # Pass library_id to local if true
            # api_key and library_type are often not needed or ignored for local connections
            zot_kwargs["api_key"] = None
            zot_kwargs["library_type"] = None
        else:
            if not library_type_val:
                click.echo("Error: Library Type is required for remote connections. Configure with 'zot configure setup'.", err=True)
                ctx.exit(1)
            # api_key can be None if user intends read-only public library access, Pyzotero handles this.
            zot_kwargs["api_key"] = api_key_val
            zot_kwargs["library_type"] = library_type_val
            zot_kwargs["local"] = None

        ctx.obj['zot'] = zotero.Zotero(**zot_kwargs)

    except Exception as e:
        handle_zotero_exceptions_and_exit(ctx, e)


@fulltext_group.command("get")
@click.argument("item_key")
@click.option('--output', type=click.Choice(['json', 'yaml', 'raw_content']), default='json', show_default=True, help='Output format. "raw_content" outputs only the text content.')
@click.pass_context
def get_fulltext(ctx, item_key, output):
    """Retrieve full-text content for a specific attachment item."""
    zot_instance = ctx.obj['zot']
    try:
        data = zot_instance.fulltext_item(item_key)
        if not data:
            click.echo("No full-text content found or item is not an attachment with full-text.", err=True)
            return

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
@click.option('--output', type=click.Choice(['json', 'yaml', 'table', 'keys']), default='table', show_default=True, help='Output format.')
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
        payload_dict = None
        try:
            payload_dict = json.loads(payload_json_input)
        except json.JSONDecodeError:
            try:
                with open(payload_json_input, 'r') as f:
                    payload_dict = json.load(f)
            except FileNotFoundError:
                click.echo(f"Error: Input '{payload_json_input}' is not valid JSON or a findable file.", err=True)
                ctx.exit(1)
            except json.JSONDecodeError:
                click.echo(f"Error: File '{payload_json_input}' is not valid JSON.", err=True)
                ctx.exit(1)
            except Exception as e:
                click.echo(f"Error reading file '{payload_json_input}': {e}", err=True)
                ctx.exit(1)
        
        if isinstance(payload_dict, dict):
            # Now payload_dict is confirmed to be a dictionary.
            if "content" not in payload_dict:
                click.echo("Error: Payload must have a 'content' key.", err=True)
                ctx.exit(1)
            
            has_pages = "indexedPages" in payload_dict and "totalPages" in payload_dict
            has_chars = "indexedChars" in payload_dict and "totalChars" in payload_dict

            if not (has_pages or has_chars):
                click.echo("Error: Payload needs ('indexedPages' & 'totalPages') OR ('indexedChars' & 'totalChars').", err=True)
                ctx.exit(1)
            if has_pages and has_chars:
                click.echo("Warning: Payload has both page and char counts. Behavior may vary.", err=True)

            success = zot_instance.set_fulltext(item_key, payload_dict)
            if success:
                click.echo(f"Successfully set full-text for item '{item_key}'.")
            else:
                click.echo(f"Failed to set full-text for '{item_key}'. API reported no success/error.", err=True)
        else:
            # This case handles when payload_dict is None or not a dictionary (e.g. list, string from JSON)
            click.echo("Error: Parsed payload is not a JSON object (dictionary).", err=True)
            ctx.exit(1)

    except Exception as e:
        handle_zotero_exceptions_and_exit(ctx, e)


