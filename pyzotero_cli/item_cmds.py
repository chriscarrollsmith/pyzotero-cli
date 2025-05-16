import click
from .utils import (
    common_options, format_data_for_output, prepare_api_params,
    output_option, pagination_options, sorting_options, filtering_options, versioning_option,
    deleted_items_options, handle_zotero_exceptions_and_exit
)
from pyzotero.zotero_errors import PyZoteroError, HTTPError, ResourceNotFoundError, PreConditionFailedError
from pyzotero import zotero
import json
import os

@click.group(name='items')
@click.pass_context
def item_group(ctx):
    """Manage Zotero items."""
    config = ctx.obj
    try:
        if not config.get('LOCAL'): # For remote operations, API key, lib ID/type are essential
            if not config.get('API_KEY'):
                raise click.UsageError(
                    "API Key is not configured. Please run 'zot configure setup --profile <profilename>' or set the ZOTERO_API_KEY environment variable."
                )
            if not config.get('LIBRARY_ID'):
                raise click.UsageError(
                    "Library ID is not configured. Please run 'zot configure setup --profile <profilename>' or set the ZOTERO_LIBRARY_ID environment variable."
                )
            if not config.get('LIBRARY_TYPE'):
                raise click.UsageError(
                    "Library Type is not configured. Please run 'zot configure setup --profile <profilename>' or set the ZOTERO_LIBRARY_TYPE environment variable."
                )

        use_local = config.get('LOCAL', False)
        if isinstance(use_local, str): # Ensure boolean if from config file
            use_local = use_local.lower() == 'true'

        ctx.obj['zotero_client'] = zotero.Zotero(
            library_id=config.get('LIBRARY_ID'),
            library_type=config.get('LIBRARY_TYPE'),
            api_key=config.get('API_KEY'),
            locale=config.get('LOCALE', 'en-US'),
            local=use_local
        )
    except PyZoteroError as e:
        click.echo(f"Zotero API Error during client initialization: {e}", err=True)
        ctx.exit(1)
    except Exception as e:
        click.echo(f"An unexpected error occurred during Zotero client initialization: {e}", err=True)
        ctx.exit(1)

@item_group.command(name="list")
@click.option('--top', is_flag=True, help='List top-level items. Corresponds to Zotero.top().')
@click.option('--publications', is_flag=True, help='List publications. Corresponds to Zotero.publications().')
@click.option('--trash', is_flag=True, help='List items from trash. Corresponds to Zotero.trash().')
@click.option('--deleted', is_flag=True, help='List deleted items (requires --since). Corresponds to Zotero.deleted().')
@output_option
@pagination_options
@sorting_options(entity_type='item')
@filtering_options
@versioning_option
@click.pass_context
def item_list(ctx, top, publications, trash, deleted, limit, start, since, sort, direction, output, query, qmode, filter_tags, filter_item_type):
    """List items in the Zotero library."""
    if deleted and not since:
        raise click.UsageError('The --deleted flag requires the --since option to be set.')
    
    list_type_flags = sum([top, publications, trash, deleted])
    if list_type_flags > 1:
        raise click.UsageError('Only one of --top, --publications, --trash, or --deleted can be specified.')

    zot_client = ctx.obj['zotero_client']
    
    # Determine which API method is being used to filter the allowed parameters
    api_method = 'items'  # Default
    if top:
        api_method = 'top'
    elif publications:
        api_method = 'publications'
    elif trash:
        api_method = 'trash'
    elif deleted:
        api_method = 'deleted'
    
    # Get allowed parameters for this method
    allowed_params = ['limit', 'start', 'since', 'sort', 'direction', 'q', 'qmode', 'tag', 'itemType']
    
    api_params = prepare_api_params(
        limit=limit, start=start, since=since, sort=sort, direction=direction,
        query=query, qmode=qmode, filter_tags=filter_tags, filter_item_type=filter_item_type
    )
    
    # Check for unused parameters and warn the user
    if deleted:
        unused_params = {k: v for k, v in api_params.items() if k != 'since' and v is not None}
        if unused_params:
            click.echo(f"Warning: The following parameters are not applicable to the 'deleted' call and will be ignored: {', '.join(unused_params.keys())}", err=True)
            # Keep only 'since' parameter for deleted items
            api_params = {'since': since} if since else {}

    try:
        if top:
            results = zot_client.top(**api_params)
        elif publications:
            if zot_client.library_type != 'user':
                raise click.UsageError('--publications can only be used with a user library.')
            results = zot_client.publications(**api_params)
        elif trash:
            results = zot_client.trash(**api_params)
        elif deleted:
            # 'deleted' in Pyzotero typically returns more than just items (collections, tags etc.)
            # The spec implies this is for items. Pyzotero's zot.deleted() takes 'since'.
            # It's fine, it will list deleted items among other things.
            results = zot_client.deleted(since=since) # 'since' is mandatory and already checked. Other params might not apply.
        else:
            results = zot_client.items(**api_params)
        click.echo(format_data_for_output(results, output))
    except PyZoteroError as e:
        handle_zotero_exceptions_and_exit(ctx, e)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)
        ctx.exit(1)

@item_group.command(name="get")
@click.argument('item_key_or_id', nargs=-1, required=True)
@common_options # For output formatting mostly, some params might be usable by item()/get_subset() e.g. 'format', 'style', 'content'
@click.option('--style', 'style_for_bib', help='CSL style to use for --output bib (e.g., "apa").')
@click.option('--linkwrap', 'linkwrap_for_bib', is_flag=True, help='Wrap URLs in <a> tags for --output bib.')
@click.pass_context
def item_get(ctx, item_key_or_id, limit, start, since, sort, direction, output, query, qmode, filter_tags, filter_item_type, style_for_bib, linkwrap_for_bib):
    """Retrieve one or more specific Zotero items by their key or ID."""
    if not item_key_or_id: # Should be caught by required=True, but good practice
        raise click.UsageError("At least one ITEM_KEY_OR_ID must be provided.")

    zot_client = ctx.obj['zotero_client']
    # Handle special output formats - we need to pass specific parameters to the API
    api_params = prepare_api_params() # Start with basic params
    
    # Add special parameters based on requested output format
    if output == 'bib':
        api_params['content'] = 'bib'
        if style_for_bib:
            api_params['style'] = style_for_bib
        if linkwrap_for_bib:
            api_params['linkwrap'] = '1' # Pyzotero expects '1' as a string
    elif output == 'bibtex':
        api_params['format'] = 'bibtex'
    elif output == 'csljson':
        api_params['content'] = 'csljson'
    
    try:
        if len(item_key_or_id) == 1:
            results = zot_client.item(item_key_or_id[0], **api_params)
        else:
            # Pyzotero's get_subset is for non-adjacent items, up to 50.
            # Or we can loop zot_client.item()
            # The spec says "Zotero.item() or Zotero.get_subset()". get_subset is more efficient.
            # However, pyzotero.items(itemKey='key1,key2,...') is often used.
            # Let's use items(itemKey=...) as it's common for retrieving multiple specific items by key.
            api_params['itemKey'] = ','.join(item_key_or_id)
            results = zot_client.items(**api_params)
            # If get_subset was preferred:
            # results = zot_client.get_subset(list(item_key_or_id), **api_params)

        # Handle bibtex format directly since it returns a special object
        if output == 'bib':
            if isinstance(results, list):
                for entry in results:
                    click.echo(entry)
            else:
                click.echo(results)
        elif output == 'bibtex' and hasattr(results, 'entries') and isinstance(results.entries, list):
            try:
                # Use bibtexparser to convert BibDatabase to string
                import bibtexparser
                from bibtexparser.bwriter import BibTexWriter
                writer = BibTexWriter()
                click.echo(bibtexparser.dumps(results, writer))
            except ImportError:
                # Fallback if bibtexparser isn't available for conversion
                entries = []
                for entry in results.entries:
                    entry_str = "@" + entry.get('ENTRYTYPE', 'article') + "{" + entry.get('ID', '') + ",\n"
                    for k, v in entry.items():
                        if k not in ('ENTRYTYPE', 'ID'):
                            entry_str += f"  {k} = {{{v}}},\n"
                    entry_str += "}"
                    entries.append(entry_str)
                click.echo("\n\n".join(entries))
        else:
            # For other formats, use the standard formatter
            click.echo(format_data_for_output(results, output))
    except PyZoteroError as e:
        handle_zotero_exceptions_and_exit(ctx, e)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)
        ctx.exit(1)

@item_group.command(name="children")
@click.argument('parent_item_key_or_id', required=True)
@common_options
@click.pass_context
def item_children(ctx, parent_item_key_or_id, limit, start, since, sort, direction, output, query, qmode, filter_tags, filter_item_type):
    """Get child items of a specific Zotero item."""
    zot_client = ctx.obj['zotero_client']
    api_params = prepare_api_params(limit, start, since, sort, direction, query, qmode, filter_tags, filter_item_type)
    try:
        results = zot_client.children(parent_item_key_or_id, **api_params)
        click.echo(format_data_for_output(results, output))
    except PyZoteroError as e:
        handle_zotero_exceptions_and_exit(ctx, e)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)
        ctx.exit(1)

@item_group.command(name="count")
@click.pass_context
def item_count(ctx):
    """Get the total count of items in the library."""
    zot_client = ctx.obj['zotero_client']
    try:
        # count_items() returns an int, not a list of dicts.
        # Pyzotero doesn't have a direct count_items() that returns just the number for all items.
        # It usually comes as a header 'Total-Results' in list responses.
        # Or, zot.num_items() can be used. Pyzotero docs state num_items().
        # The provided pyzotero_docs.md has `Zotero.count_items()` which returns an int.
        # Let's assume this is `zot_client.count_items()`
        # If not, use zot_client.num_items() or retrieve items with limit=1 and check Total-Results header.
        # The spec says `Zotero.count_items()`. So this should be it.
        # The pyzotero docs provided list `Zotero.count_items()`
        count = zot_client.count_items()
        click.echo(f"Total items in library: {count}")
    except PyZoteroError as e:
        click.echo(f"Zotero API Error: {e}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)

@item_group.command(name="versions")
@click.option('--since', 'since_version', help='Retrieve objects modified after a library version.') # Renamed to avoid clash
@click.option('--output', 'output_format', type=click.Choice(['json', 'yaml']), default='json', show_default=True, help='Output format.') # Renamed
@click.pass_context
def item_versions(ctx, since_version, output_format):
    """Get item version information."""
    zot_client = ctx.obj['zotero_client']
    params = {}
    if since_version:
        params['since'] = since_version
    
    try:
        # Pyzotero has item_versions method
        results = zot_client.item_versions(**params)
        # Output formatting based on output_format
        click.echo(format_data_for_output(results, output_format))
    except PyZoteroError as e:
        click.echo(f"Zotero API Error: {e}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)

@item_group.command(name="create")
@click.option('--from-json', 'from_json_input', help='Path to a JSON file or a JSON string describing the item(s).')
@click.option('--template', 'template_type', help='Item type to use as a template (e.g., book, journalArticle).')
@click.option('--field', 'fields', multiple=True, type=(str, str), help='Set a field for the item (e.g., --field title "My Book"). Use for simple fields if using --template.')
@click.option('--parent-id', 'parent_item_id', help='ID of the parent item for this new item (usually for notes/attachments).') # Renamed
# --last-modified is not applicable for create_items in Pyzotero, removing it based on typical API behavior
# @click.option('--last-modified', 'last_modified_version', help='If-Unmodified-Since-Version header value.')
@common_options # Added common options (includes output)
@click.pass_context
# Added output param from common_options (others like limit, start etc. are unused but harmless here)
def item_create(ctx, from_json_input, template_type, fields, parent_item_id, limit, start, since, sort, direction, output, query, qmode, filter_tags, filter_item_type):
    """Create new Zotero item(s)."""
    if from_json_input and template_type:
        raise click.UsageError('Cannot use --from-json and --template simultaneously.')
    if not from_json_input and not template_type:
        raise click.UsageError('Either --from-json or --template must be provided.')
    if fields and not template_type:
        raise click.UsageError('--field options can only be used with --template.')

    zot_client = ctx.obj['zotero_client']
    item_payloads = []

    try:
        if from_json_input:
            try:
                # Check if it's a file path
                if os.path.exists(from_json_input):
                    with open(from_json_input, 'r') as f:
                        data = json.load(f)
                else: # Assume it's a JSON string
                    data = json.loads(from_json_input)
                
                # Data can be a single item dict or a list of item dicts
                if isinstance(data, list):
                    item_payloads.extend(data)
                else:
                    item_payloads.append(data)
            except json.JSONDecodeError:
                raise click.UsageError(f"Invalid JSON provided in --from-json: {from_json_input}")
            except FileNotFoundError:
                 raise click.UsageError(f"JSON file not found: {from_json_input}")


        elif template_type:
            # Create a template
            template = zot_client.item_template(template_type)
            if not isinstance(template, dict): # Check if template is a dictionary
                 raise click.ClickException(
                     f"Could not generate a valid item template for type: '{template_type}'. "
                     f"Pyzotero.item_template() call result: {template}"
                 )

            # Apply fields to the template itself
            if fields:
                for key, value in fields:
                    # Creators need special handling if we want to set them via --field
                    # For now, this handles top-level simple fields in the template.
                    # e.g., template['title'] = "My Book"
                    # Complex paths like 'creators.0.firstName' are not handled by this simple loop.
                    if key == 'parentItem' and parent_item_id: # Special case for parentItem from option
                        template[key] = parent_item_id
                    elif key in template or key in getattr(template, 'data', {}): # Check if key is valid for template
                        template[key] = value
                    else:
                        # Optionally, warn or error if a field is not directly settable this way
                        # For now, we allow attempting to set any field. Pyzotero validation might catch it.
                        # Or, more strictly, only allow known template fields.
                        # For maximum flexibility with --field and to match previous behavior of assuming template['data']
                        # we could try to set it, but it might be better to be strict.
                        # Let's stick to setting only existing top-level keys for now for safety, or known ones.
                        # This was template['data'][key], now it's template[key]
                        # If a user wants to set a deep field, they should use --from-json.
                        # A simple default: if key exists in template, set it.
                        if key in template:
                             template[key] = value
                        else:
                             # If we want to be more permissive (like original template['data'][key] attempt)
                             # we could do template[key] = value anyway.
                             # For now, let's be a bit more careful and require the key to exist at top-level.
                             # This change means template['data'][key] implicitly worked because all fields were under 'data'.
                             # Now, they are at top-level of template.
                             # The original code template['data'][key] = value was trying to put all fields under a 'data' sub-dict.
                             # Pyzotero's create_items expects a list of item dicts, where each dict is the template structure.
                             # So, template[key] = value is correct for top-level fields of the template.
                             template[key] = value # Allow setting new keys as well, like original did for 'data'

            # This was an error: template['data']['parentItem'] = parent_item_id
            # parentItem is a top-level field in the template if it's for a note/attachment.
            if parent_item_id: # For notes or attachments linked to a parent item
                template['parentItem'] = parent_item_id
            
            item_payloads.append(template)

        if not item_payloads:
            raise click.UsageError("No item data to create.")

        results = zot_client.create_items(item_payloads) # Expects a list of item templates
        # Use format_data_for_output
        click.echo(format_data_for_output(results, output))

    except PyZoteroError as e:
        click.echo(f"Zotero API Error: {e}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)


@item_group.command(name="update")
@click.argument('item_key_or_id', required=True)
@click.option('--from-json', 'from_json_input', help='Path to a JSON file or a JSON string containing the item data for update.')
@click.option('--field', 'fields', multiple=True, type=(str, str), help='Set a specific field to update (e.g., --field title "New Title").')
@click.option('--last-modified', 'last_modified_option', help='If-Unmodified-Since-Version header. Can be a version number or "auto" to use the item\'s current version.')
@common_options # Added common options (includes output)
@click.pass_context
# Added output param from common_options (others unused but harmless)
def item_update(ctx, item_key_or_id, from_json_input, fields, last_modified_option, limit, start, since, sort, direction, output, query, qmode, filter_tags, filter_item_type):
    """Update an existing Zotero item."""
    if from_json_input and fields:
        raise click.UsageError('Cannot use --from-json and --field simultaneously.')
    if not from_json_input and not fields:
        raise click.UsageError('Either --from-json or at least one --field must be provided for an update.')

    zot_client = ctx.obj['zotero_client']
    
    try:
        # Fetch the item first to get its current version for If-Unmodified-Since-Version
        # and to have the full item structure if updating fields.
        original_item = zot_client.item(item_key_or_id)
        if not original_item: # Or if item() returns list and it's empty
            raise click.ClickException(f"Item with key '{item_key_or_id}' not found.")
        
        # If item() returns a list (even with one item), take the first.
        if isinstance(original_item, list):
            if not original_item:
                 raise click.ClickException(f"Item with key '{item_key_or_id}' not found.")
            original_item = original_item[0]


        item_to_update = original_item.copy() # Work on a copy

        if last_modified_option == 'auto':
            item_to_update['version'] = original_item['version']
        elif last_modified_option:
            try:
                item_to_update['version'] = int(last_modified_option)
            except ValueError:
                raise click.UsageError("--last-modified must be an integer version number or 'auto'.")
        # If no last_modified_option, Pyzotero update_item might overwrite without check,
        # or use the version from the fetched item if it's part of the payload.
        # Pyzotero's update_item(item_data) uses item_data['version'] for the header.

        if from_json_input:
            try:
                if os.path.exists(from_json_input):
                    with open(from_json_input, 'r') as f:
                        update_data = json.load(f)
                else:
                    update_data = json.loads(from_json_input)
                
                # Merge update_data into item_to_update['data']
                # Or replace item_to_update with update_data, ensuring key and version are correct.
                # For safety, the user-provided JSON should contain the full item structure.
                # Or, if it's partial, merge it.
                # The `update_item` method expects the *entire* item structure usually.
                # Let's assume `update_data` IS the new item structure (minus key/version potentially)
                # and we need to merge it carefully or ensure it has the right 'key'.
                # A common pattern is: user_json_data['key'] = original_item['key']
                # user_json_data['version'] = item_to_update['version'] (already set)
                # For now, let's assume from_json_input provides the complete item data fields.
                # We must preserve the key and the version (for If-Unmodified-Since).
                
                new_data_fields = update_data.get('data', update_data) # If JSON is full item or just 'data' part
                item_to_update['data'].update(new_data_fields) # Merge new fields into existing data
                if 'version' in update_data: # If user supplied version in JSON, respect it, unless 'auto' was used
                    if not (last_modified_option == 'auto'): # 'auto' takes precedence
                         item_to_update['version'] = update_data['version']


            except json.JSONDecodeError:
                raise click.UsageError(f"Invalid JSON provided in --from-json: {from_json_input}")
            except FileNotFoundError:
                 raise click.UsageError(f"JSON file not found: {from_json_input}")
        elif fields:
            for key, value in fields:
                # Assume simple key-value for data dictionary.
                # Type conversion might be needed for non-string values.
                item_to_update['data'][key] = value
        
        # Ensure the item key is present
        item_to_update['key'] = item_key_or_id


        results = zot_client.update_item(item_to_update)
        # Use format_data_for_output, structure boolean result
        output_data = {"status": "success", "item_key": item_key_or_id} if results else {"status": "failed", "item_key": item_key_or_id}
        click.echo(format_data_for_output(output_data, output))

    except PyZoteroError as e:
        click.echo(f"Zotero API Error: {e}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)


@item_group.command(name="delete")
@click.argument('item_key_or_id', nargs=-1, required=True)
@click.option('--last-modified', 'last_modified_option', help='If-Unmodified-Since-Version header. Can be a version number or "auto".')
@click.option('--force', is_flag=True, help='Confirm deletion without prompting.')
@common_options # Added common options (includes output)
@click.pass_context
# Added output param from common_options (others unused but harmless)
def item_delete(ctx, item_key_or_id, last_modified_option, force, limit, start, since, sort, direction, output, query, qmode, filter_tags, filter_item_type):
    """Delete one or more Zotero items."""
    if not item_key_or_id:
        raise click.UsageError("At least one ITEM_KEY_OR_ID must be provided.")

    zot_client = ctx.obj['zotero_client']
    
    if not force and not ctx.obj.get('NO_INTERACTION'):
        confirm_keys = ', '.join(item_key_or_id)
        if not click.confirm(f"Are you sure you want to delete item(s): {confirm_keys}?"):
            click.echo("Deletion cancelled.")
            ctx.exit() # Use ctx.exit() for cleaner exit
    
    results_summary = []
    for key_str_val in item_key_or_id: # renamed key to key_str_val to avoid Pylance issue with dict key
        try:
            item_to_delete = {'key': key_str_val}
            
            fetched_version_for_delete = None
            # Logic to determine version for deletion
            if last_modified_option == 'auto':
                item_data = zot_client.item(key_str_val)
                if isinstance(item_data, list) and item_data:
                    fetched_version_for_delete = item_data[0]['version']
                elif isinstance(item_data, dict) and 'version' in item_data:
                    fetched_version_for_delete = item_data['version']
                else:
                    results_summary.append({key_str_val: f"Error: Item '{key_str_val}' not found or could not retrieve version for 'auto'."})
                    continue
            elif last_modified_option:
                try:
                    fetched_version_for_delete = int(last_modified_option)
                except ValueError:
                    results_summary.append({key_str_val: f"Error: --last-modified must be an integer or 'auto' for item '{key_str_val}'."})
                    continue
            else: # Default: must fetch version for safe delete
                item_data = zot_client.item(key_str_val)
                if isinstance(item_data, list) and item_data:
                    fetched_version_for_delete = item_data[0]['version']
                elif isinstance(item_data, dict) and 'version' in item_data:
                    fetched_version_for_delete = item_data['version']
                else:
                    results_summary.append({key_str_val: f"Error: Item '{key_str_val}' not found or could not retrieve version."})
                    continue
            
            item_to_delete['version'] = fetched_version_for_delete

            result = zot_client.delete_item(item_to_delete) 
            results_summary.append({key_str_val: "Successfully deleted" if result else "Failed to delete (or no explicit success returned)"})
        except PreConditionFailedError as e: # Catch 412 Precondition Failed
            results_summary.append({key_str_val: f"Failed to delete item '{key_str_val}': Version mismatch (precondition failed). Error: {e}"})
        except ResourceNotFoundError as e: # Catch 404 Not Found
            results_summary.append({key_str_val: f"Failed to delete item '{key_str_val}': Item not found. Error: {e}"})
        except HTTPError as e: # Catch other HTTP errors that might not have specific classes
            results_summary.append({key_str_val: f"Zotero API HTTP Error for item '{key_str_val}': {str(e)}"}) 
        except PyZoteroError as e: # Catch other general PyZotero errors
            results_summary.append({key_str_val: f"Zotero API Error for item '{key_str_val}': {e}"})
        except Exception as e:
            results_summary.append({key_str_val: f"An unexpected error occurred for item '{key_str_val}': {e}"})
            
    # Use format_data_for_output
    click.echo(format_data_for_output(results_summary, output))


@item_group.command(name="add-tags")
@click.argument('item_key_or_id', required=True)
@click.argument('tag_names', nargs=-1, required=True)
@common_options # Added common options (includes output)
@click.pass_context
# Added output param from common_options (others unused but harmless)
def item_add_tags(ctx, item_key_or_id, tag_names, limit, start, since, sort, direction, output, query, qmode, filter_tags, filter_item_type):
    """Add one or more tags to a Zotero item."""
    if not tag_names:
        raise click.UsageError("At least one TAG_NAME must be provided.")

    zot_client = ctx.obj['zotero_client']
    try:
        # add_tags(item, tags) - item should be the item object with key and version.
        # First, fetch the item to get its version.
        item_data = zot_client.item(item_key_or_id)
        if isinstance(item_data, list) and item_data:
            item_data = item_data[0]
        elif not item_data:
            raise click.ClickException(f"Item with key '{item_key_or_id}' not found.")

        # Pyzotero's add_tags might also just take the item key.
        # Docs: zot.add_tags(item, 'tag1, tag2') OR zot.add_tags(item, ['tag1', 'tag2'])
        # The `item` param should be the item dict.
        # It implicitly uses item['version'] for If-Unmodified-Since.
        
        result = zot_client.add_tags(item_data, list(tag_names))
        # add_tags returns True on success.
        if result:
            # click.echo(f"Tags {list(tag_names)} added to item {item_key_or_id}.")
             output_data = {"status": "success", "item_key": item_key_or_id, "tags_added": list(tag_names)}
        else:
            # click.echo(f"Failed to add tags to item {item_key_or_id}.")
             output_data = {"status": "failed", "item_key": item_key_or_id, "tags": list(tag_names)}
        click.echo(format_data_for_output(output_data, output)) # Use format_data_for_output

    except PyZoteroError as e:
        click.echo(f"Zotero API Error: {e}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)

@item_group.command(name="bib")
@click.option('--style', help="CSL style to use for formatting (e.g., 'apa', 'mla').")
@click.option('--linkwrap', is_flag=True, help="Wrap URLs in bibliography entries in <a> tags.")
@click.argument('item_key_or_id', nargs=-1, required=True)
@click.pass_context
def item_bib(ctx, style, linkwrap, item_key_or_id):
    """Get bibliography entries for one or more Zotero items (output is HTML)."""
    if not item_key_or_id:
        raise click.UsageError("At least one ITEM_KEY_OR_ID must be provided.")

    zot_client = ctx.obj['zotero_client']
    api_params = {'content': 'bib'}
    if style:
        api_params['style'] = style
    if linkwrap: 
        api_params['linkwrap'] = '1' # Changed to string '1'

    # For multiple items, use itemKey with comma-separated keys
    api_params['itemKey'] = ','.join(item_key_or_id)
        
    try:
        # The .items() method with 'content' and 'itemKey' is suitable.
        results = zot_client.items(**api_params)
        # Results will be a list of HTML strings or a single HTML string.
        if isinstance(results, list):
            for entry in results:
                click.echo(entry) # Print each bib entry
        else:
            click.echo(results)

    except PyZoteroError as e:
        click.echo(f"Zotero API Error: {e}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)

@item_group.command(name="citation")
@click.option('--style', help="CSL style to use for formatting (e.g., 'apa', 'mla').")
@click.argument('item_key_or_id', nargs=-1, required=True)
@click.pass_context
def item_citation(ctx, style, item_key_or_id):
    """Get citation entries for one or more Zotero items (output is HTML)."""
    if not item_key_or_id:
        raise click.UsageError("At least one ITEM_KEY_OR_ID must be provided.")
        
    zot_client = ctx.obj['zotero_client']
    api_params = {'content': 'citation'}
    if style:
        api_params['style'] = style
    
    api_params['itemKey'] = ','.join(item_key_or_id)

    try:
        results = zot_client.items(**api_params)
        if isinstance(results, list):
            for entry in results: # Should be list of strings
                click.echo(entry)
        else: # Or a single string
            click.echo(results)
    except PyZoteroError as e:
        click.echo(f"Zotero API Error: {e}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True) 

@item_group.command(name="deleted")
@deleted_items_options
@output_option
@click.pass_context
def item_deleted(ctx, since, output):
    """List deleted items. Requires the --since parameter."""
    zot_client = ctx.obj['zotero_client']
    
    try:
        results = zot_client.deleted(since=since)
        # Filter to only show deleted items if desired
        items_deleted = results.get('items', [])
        click.echo(format_data_for_output(items_deleted, output))
    except PyZoteroError as e:
        handle_zotero_exceptions_and_exit(ctx, e)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)
        ctx.exit(1) 