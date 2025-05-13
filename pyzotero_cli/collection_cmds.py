import click
from .utils import (
    common_options, format_data_for_output, prepare_api_params, 
    output_option, pagination_options, sorting_options, filtering_options, versioning_option,
    handle_zotero_exceptions_and_exit
)
from pyzotero import zotero
from pyzotero.zotero_errors import PyZoteroError, HTTPError, ResourceNotFoundError, PreConditionFailedError
import json
import os

@click.group(name='collections')
@click.pass_context
def collection_group(ctx):
    """Manage Zotero collections."""
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

@collection_group.command(name="list")
@click.option('--top', is_flag=True, help='List top-level collections. Corresponds to Zotero.collections_top().')
@output_option
@pagination_options
@sorting_options(entity_type='collection')
@filtering_options
@versioning_option
@click.pass_context
def collection_list(ctx, top, limit, start, since, sort, direction, output, query, qmode, filter_tags, filter_item_type):
    """List collections in the Zotero library."""
    zot_client = ctx.obj['zotero_client']
    
    # Determine which API method is being used
    api_method = 'collections_top' if top else 'collections'
    
    api_params = prepare_api_params(limit, start, since, sort, direction, query, qmode, filter_tags, filter_item_type)
    
    try:
        if top:
            results = zot_client.collections_top(**api_params)
        else:
            results = zot_client.collections(**api_params)
        click.echo(format_data_for_output(results, output)) # Use format_data_for_output
    except PyZoteroError as e:
        handle_zotero_exceptions_and_exit(ctx, e)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)
        ctx.exit(1)

@collection_group.command(name="get")
@click.argument('collection_key_or_id', required=True)
@common_options 
@click.pass_context
def collection_get(ctx, collection_key_or_id, limit, start, since, sort, direction, output, query, qmode, filter_tags, filter_item_type):
    """Retrieve a specific Zotero collection."""
    zot_client: zotero.Zotero = ctx.obj['zotero_client']
    api_params = prepare_api_params() 
    try:
        results = zot_client.collection(collection_key_or_id, **api_params)
        click.echo(format_data_for_output(results, output)) # Use format_data_for_output
    except PyZoteroError as e:
        handle_zotero_exceptions_and_exit(ctx, e)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)
        ctx.exit(1)

@collection_group.command(name="subcollections")
@click.argument('parent_collection_key_or_id', required=True)
@common_options
@click.pass_context
def collection_subcollections(ctx, parent_collection_key_or_id, limit, start, since, sort, direction, output, query, qmode, filter_tags, filter_item_type):
    """List subcollections of a specific collection."""
    zot_client = ctx.obj['zotero_client']
    api_params = prepare_api_params(limit, start, since, sort, direction, query, qmode, filter_tags, filter_item_type)
    try:
        results = zot_client.collections_sub(parent_collection_key_or_id, **api_params)
        click.echo(format_data_for_output(results, output)) # Use format_data_for_output
    except PyZoteroError as e:
        handle_zotero_exceptions_and_exit(ctx, e)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)
        ctx.exit(1)

@collection_group.command(name="all")
@click.option('--parent-collection-id', 'parent_id', help='Optional parent collection ID to start from.')
@common_options
@click.pass_context
def collection_all(ctx, parent_id, limit, start, since, sort, direction, output, query, qmode, filter_tags, filter_item_type):
    """List all collections and subcollections, flattened."""
    zot_client = ctx.obj['zotero_client']
    # Pyzotero's all_collections() only takes an optional collectionID (parent_id here).
    # It does not accept other parameters like limit, sort, direction directly.
    # If filtering/sorting is needed, it would typically be done client-side on the results,
    # or by setting parameters on the Zotero instance if the specific method respects them (all_collections likely doesn't).
    try:
        if parent_id:
            results = zot_client.all_collections(parent_id)
        else:
            results = zot_client.all_collections()
        click.echo(format_data_for_output(results, output)) # Use format_data_for_output
    except PyZoteroError as e:
        click.echo(f"Zotero API Error: {e}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)

@collection_group.command(name="items")
@click.argument('collection_key_or_id', required=True)
@click.option('--top', is_flag=True, help='List top-level items in the collection. Corresponds to Zotero.collection_items_top().')
@common_options
@click.pass_context
def collection_items(ctx, collection_key_or_id, top, limit, start, since, sort, direction, output, query, qmode, filter_tags, filter_item_type):
    """List items in a specific collection."""
    zot_client = ctx.obj['zotero_client']
    api_params = prepare_api_params(limit, start, since, sort, direction, query, qmode, filter_tags, filter_item_type)
    try:
        if top:
            results = zot_client.collection_items_top(collection_key_or_id, **api_params)
        else:
            results = zot_client.collection_items(collection_key_or_id, **api_params)
        click.echo(format_data_for_output(results, output)) # Use format_data_for_output
    except PyZoteroError as e:
        handle_zotero_exceptions_and_exit(ctx, e)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)
        ctx.exit(1)

@collection_group.command(name="item-count")
@click.argument('collection_key_or_id', required=True)
@click.pass_context
def collection_item_count(ctx, collection_key_or_id):
    """Get the count of items in a specific collection."""
    zot_client = ctx.obj['zotero_client']
    try:
        collection_data_resp = zot_client.collection(collection_key_or_id)
        # Ensure it's a single dict if API returns a list
        collection_data = collection_data_resp[0] if isinstance(collection_data_resp, list) and collection_data_resp else collection_data_resp
            
        if isinstance(collection_data, dict) and 'meta' in collection_data and 'numItems' in collection_data['meta']:
            count = collection_data['meta']['numItems']
            click.echo(f"Number of items in collection '{collection_key_or_id}': {count}")
        else:
            click.echo(f"Could not retrieve item count for collection '{collection_key_or_id}'. Malformed response.", err=True)
    except ResourceNotFoundError:
        click.echo(f"Collection '{collection_key_or_id}' not found.", err=True)
    except PyZoteroError as e:
        click.echo(f"Zotero API Error: {e}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)

@collection_group.command(name="versions")
@click.option('--since', 'since_version', type=int, help='Retrieve objects modified after a library version.')
@click.option('--output', type=click.Choice(['json', 'yaml', 'table', 'keys']), default='json', show_default=True, help='Output format.')
@click.pass_context
def collection_versions(ctx, since_version, output):
    """Get collection version information."""
    zot_client = ctx.obj['zotero_client']
    kwargs_for_call = {}
    if since_version is not None:
        kwargs_for_call['since'] = since_version
        
    try:
        results = zot_client.collection_versions(**kwargs_for_call)
        click.echo(format_data_for_output(results, output))
    except PyZoteroError as e:
        click.echo(f"Zotero API Error: {e}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)

@collection_group.command(name="create")
@click.option('--name', 'collection_names', multiple=True, required=True, help='Name of the collection to create (can be specified multiple times).')
@click.option('--parent-id', 'parent_collection_id', help='ID of the parent collection for these new collection(s).')
@common_options
@click.pass_context
def collection_create(ctx, collection_names, parent_collection_id, limit, start, since, sort, direction, output, query, qmode, filter_tags, filter_item_type):
    """Create one or more new Zotero collections."""
    zot_client = ctx.obj['zotero_client']
    payloads = []
    for name in collection_names:
        collection_data = {'name': name}
        if parent_collection_id:
            collection_data['parentCollection'] = parent_collection_id
        payloads.append(collection_data)
    
    if not payloads:
        raise click.UsageError("No collection names provided to create.") 
        
    try:
        results = zot_client.create_collections(payloads)
        click.echo(format_data_for_output(results, output)) # Use format_data_for_output
    except PyZoteroError as e:
        click.echo(f"Zotero API Error: {e}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)

@collection_group.command(name="update")
@click.argument('collection_key_or_id', required=True)
@click.option('--name', 'new_name', help='New name for the collection.')
@click.option('--parent-id', 'new_parent_id', help='New parent ID for the collection (set to empty string "" to make it top-level, or boolean false).')
@click.option('--from-json', 'from_json_input', help='Path to a JSON file or a JSON string for complex updates.')
@click.option('--last-modified', 'last_modified_option', help='If-Unmodified-Since-Version header. Can be a version number or "auto".')
@common_options
@click.pass_context
def collection_update(ctx, collection_key_or_id, new_name, new_parent_id, from_json_input, last_modified_option, limit, start, since, sort, direction, output, query, qmode, filter_tags, filter_item_type):
    """Update an existing Zotero collection."""
    if not new_name and new_parent_id is None and not from_json_input:
        raise click.UsageError('Either --name, --parent-id, or --from-json must be provided for an update.')
    if from_json_input and (new_name or new_parent_id is not None):
        raise click.UsageError('Cannot use --from-json with --name or --parent-id simultaneously.')

    zot_client = ctx.obj['zotero_client']
    try:
        original_collection_resp = zot_client.collection(collection_key_or_id)
        
        original_collection = original_collection_resp[0] if isinstance(original_collection_resp, list) and original_collection_resp else original_collection_resp
        if not isinstance(original_collection, dict): # Check if it became a dict
            raise click.ClickException(f"Collection with key '{collection_key_or_id}' not found or API returned unexpected data type.")

        collection_to_update = original_collection.copy()
        
        if 'data' not in collection_to_update: # Ensure 'data' key exists for updates
            collection_to_update['data'] = {}

        # Set the top-level version for If-Unmodified-Since-Version header
        fetched_version = original_collection.get('version')
        if fetched_version is None:
            raise click.ClickException(f"Could not determine version for collection '{collection_key_or_id}'.")

        if last_modified_option == 'auto':
            collection_to_update['version'] = fetched_version
        elif last_modified_option:
            try:
                collection_to_update['version'] = int(last_modified_option)
            except ValueError:
                raise click.UsageError("--last-modified must be an integer version number or 'auto'.")
        else: 
            collection_to_update['version'] = fetched_version

        if from_json_input:
            try:
                if os.path.exists(from_json_input):
                    with open(from_json_input, 'r') as f:
                        update_json_data = json.load(f)
                else:
                    update_json_data = json.loads(from_json_input)
                
                if not isinstance(update_json_data, dict):
                    raise click.UsageError(f"Invalid JSON structure in --from-json: {from_json_input}. Expected a JSON object.")

                data_to_merge = update_json_data.get('data', update_json_data)
                if not isinstance(data_to_merge, dict): # Ensure data_to_merge is a dict before accessing its items
                     data_to_merge = {} # Or raise error, depending on how strict we want to be with JSON structure

                if 'name' in data_to_merge:
                    collection_to_update['data']['name'] = data_to_merge['name']
                if 'parentCollection' in data_to_merge: 
                    collection_to_update['data']['parentCollection'] = data_to_merge['parentCollection']
                
                json_version = update_json_data.get('version')
                if json_version is not None and last_modified_option != 'auto':
                     collection_to_update['version'] = json_version

            except json.JSONDecodeError:
                raise click.UsageError(f"Invalid JSON provided in --from-json: {from_json_input}")
            except FileNotFoundError:
                 raise click.UsageError(f"JSON file not found: {from_json_input}")
        else: 
            if new_name:
                collection_to_update['data']['name'] = new_name
            if new_parent_id is not None: 
                collection_to_update['data']['parentCollection'] = False if new_parent_id == "" else new_parent_id
        
        collection_to_update['key'] = collection_key_or_id

        results = zot_client.update_collection(collection_to_update)
        click.echo(format_data_for_output(results, output)) # Use format_data_for_output

    except ResourceNotFoundError:
        click.echo(f"Collection '{collection_key_or_id}' not found.", err=True)
    except PreConditionFailedError as e:
        click.echo(f"Failed to update collection '{collection_key_or_id}': Version mismatch. {e}", err=True)
    except PyZoteroError as e:
        click.echo(f"Zotero API Error: {e}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)

@collection_group.command(name="delete")
@click.argument('collection_key_or_id', nargs=-1, required=True)
@click.option('--last-modified', 'last_modified_option', help='If-Unmodified-Since-Version header. Can be a version number or "auto".')
@click.option('--force', is_flag=True, help='Confirm deletion without prompting.')
@common_options
@click.pass_context
def collection_delete(ctx, collection_key_or_id, last_modified_option, force, limit, start, since, sort, direction, output, query, qmode, filter_tags, filter_item_type):
    """Delete one or more Zotero collections."""
    if not collection_key_or_id:
        raise click.UsageError("At least one COLLECTION_KEY_OR_ID must be provided.")

    zot_client = ctx.obj['zotero_client']
    
    if not force and not ctx.obj.get('NO_INTERACTION'):
        confirm_keys = ', '.join(collection_key_or_id)
        if not click.confirm(f"Are you sure you want to delete collection(s): {confirm_keys}? This will NOT delete items in the collection(s)."):
            click.echo("Deletion cancelled.")
            ctx.exit()
    
    results_summary = []
    for key_str_val in collection_key_or_id:
        try:
            version_for_delete = None
            if last_modified_option == 'auto':
                coll_data_resp = zot_client.collection(key_str_val)
                coll_data = coll_data_resp[0] if isinstance(coll_data_resp, list) and coll_data_resp else coll_data_resp
                if isinstance(coll_data, dict) and coll_data.get('version') is not None:
                    version_for_delete = coll_data.get('version')
                else:
                    results_summary.append({key_str_val: f"Error: Collection '{key_str_val}' not found or could not retrieve version for 'auto'."})
                    continue
            elif last_modified_option:
                try:
                    version_for_delete = int(last_modified_option)
                except ValueError:
                    results_summary.append({key_str_val: f"Error: --last-modified must be an integer or 'auto' for collection '{key_str_val}'."})
                    continue
            else: 
                coll_data_resp = zot_client.collection(key_str_val)
                coll_data = coll_data_resp[0] if isinstance(coll_data_resp, list) and coll_data_resp else coll_data_resp
                if isinstance(coll_data, dict) and coll_data.get('version') is not None:
                    version_for_delete = coll_data.get('version')
                else:
                    results_summary.append({key_str_val: f"Error: Collection '{key_str_val}' not found or could not retrieve version."})
                    continue
            
            collection_to_delete = {'key': key_str_val, 'version': version_for_delete}
            result = zot_client.delete_collection(collection_to_delete)
            results_summary.append({key_str_val: "Successfully deleted" if result else "Failed to delete (or no explicit success returned)"})

        except PreConditionFailedError as e:
            results_summary.append({key_str_val: f"Failed to delete collection '{key_str_val}': Version mismatch. Error: {e}"})
        except ResourceNotFoundError:
            results_summary.append({key_str_val: f"Failed to delete collection '{key_str_val}': Collection not found."})
        except HTTPError as e:
             results_summary.append({key_str_val: f"Zotero API HTTP Error for collection '{key_str_val}': {str(e)}"})
        except PyZoteroError as e:
            results_summary.append({key_str_val: f"Zotero API Error for collection '{key_str_val}': {e}"})
        except Exception as e:
            results_summary.append({key_str_val: f"An unexpected error occurred for collection '{key_str_val}': {e}"})
            
    click.echo(format_data_for_output(results_summary, output)) # Use format_data_for_output

@collection_group.command(name="add-item")
@click.argument('collection_key_or_id', required=True)
@click.argument('item_key_or_id', nargs=-1, required=True)
@common_options
@click.pass_context
def collection_add_item(ctx, collection_key_or_id, item_key_or_id, limit, start, since, sort, direction, output, query, qmode, filter_tags, filter_item_type):
    """Add item(s) to a collection by modifying the item's 'collections' field."""
    if not item_key_or_id:
        raise click.UsageError("At least one ITEM_KEY_OR_ID must be provided.")
    
    zot_client = ctx.obj['zotero_client']
    items_to_process = list(item_key_or_id)

    try:
        zot_client.collection(collection_key_or_id) 

        results_summary = []
        for item_key in items_to_process:
            try:
                item_data_resp = zot_client.item(item_key)
                item_data = item_data_resp[0] if isinstance(item_data_resp, list) and item_data_resp else item_data_resp
                
                if not isinstance(item_data, dict): 
                    results_summary.append({item_key: f"Item '{item_key}' not found or invalid data returned."})
                    continue

                if 'data' not in item_data: item_data['data'] = {}
                if 'collections' not in item_data['data']:
                    item_data['data']['collections'] = []
                
                if collection_key_or_id not in item_data['data']['collections']:
                    item_data['data']['collections'].append(collection_key_or_id)
                    
                    if item_data.get('key') is None: item_data['key'] = item_key 
                    if item_data.get('version') is None:
                        # This case should ideally not happen if item was fetched successfully
                        raise click.ClickException(f"Could not determine version for item '{item_key}' before update.")

                    zot_client.update_item(item_data) 
                    results_summary.append({item_key: f"Added to collection '{collection_key_or_id}'."})
                else:
                    results_summary.append({item_key: f"Already in collection '{collection_key_or_id}'."})

            except ResourceNotFoundError:
                 results_summary.append({item_key: f"Item '{item_key}' not found."})
            except PreConditionFailedError as e:
                 results_summary.append({item_key: f"Failed to update item '{item_key}' (version mismatch): {e}"})    
            except PyZoteroError as e:
                results_summary.append({item_key: f"Zotero API Error for item '{item_key}': {e}"})
            except Exception as e:
                results_summary.append({item_key: f"Unexpected error for item '{item_key}': {e}"})
        
        click.echo(format_data_for_output(results_summary, output)) # Use format_data_for_output

    except ResourceNotFoundError: 
        click.echo(f"Collection '{collection_key_or_id}' not found.", err=True)
    except PyZoteroError as e:
        click.echo(f"Zotero API Error: {e}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)


@collection_group.command(name="remove-item")
@click.argument('collection_key_or_id', required=True)
@click.argument('item_key_or_id', nargs=-1, required=True)
@click.option('--force', is_flag=True, help='Confirm removal without prompting.')
@common_options
@click.pass_context
def collection_remove_item(ctx, collection_key_or_id, item_key_or_id, force, limit, start, since, sort, direction, output, query, qmode, filter_tags, filter_item_type):
    """Remove item(s) from a collection by modifying the item's 'collections' field."""
    if not item_key_or_id:
        raise click.UsageError("At least one ITEM_KEY_OR_ID must be provided.")

    items_to_process = list(item_key_or_id)
    
    if not force and not ctx.obj.get('NO_INTERACTION'):
        confirm_keys = ', '.join(items_to_process)
        if not click.confirm(f"Are you sure you want to remove item(s) {confirm_keys} from collection {collection_key_or_id}?"):
            click.echo("Removal cancelled.")
            ctx.exit()

    zot_client = ctx.obj['zotero_client']
    try:
        zot_client.collection(collection_key_or_id)

        results_summary = []
        for item_key in items_to_process:
            try:
                item_data_resp = zot_client.item(item_key)
                item_data = item_data_resp[0] if isinstance(item_data_resp, list) and item_data_resp else item_data_resp

                if not isinstance(item_data, dict):
                    results_summary.append({item_key: f"Item '{item_key}' not found or invalid data returned."})
                    continue

                if isinstance(item_data.get('data'), dict) and isinstance(item_data['data'].get('collections'), list) and collection_key_or_id in item_data['data']['collections']:
                    item_data['data']['collections'].remove(collection_key_or_id)
                    
                    if item_data.get('key') is None: item_data['key'] = item_key
                    if item_data.get('version') is None:
                         raise click.ClickException(f"Could not determine version for item '{item_key}' before update.")
                    
                    zot_client.update_item(item_data) 
                    results_summary.append({item_key: f"Removed from collection '{collection_key_or_id}'."})
                elif isinstance(item_data.get('data'), dict) and isinstance(item_data['data'].get('collections'), list):
                     results_summary.append({item_key: f"Not found in collection '{collection_key_or_id}'."})
                else: 
                    results_summary.append({item_key: f"Item '{item_key}' does not have a collections field or is not in collection '{collection_key_or_id}'."})
            
            except ResourceNotFoundError:
                 results_summary.append({item_key: f"Item '{item_key}' not found."})
            except PreConditionFailedError as e:
                 results_summary.append({item_key: f"Failed to update item '{item_key}' (version mismatch): {e}"})    
            except PyZoteroError as e:
                results_summary.append({item_key: f"Zotero API Error for item '{item_key}': {e}"})
            except Exception as e:
                results_summary.append({item_key: f"Unexpected error for item '{item_key}': {e}"})
        
        click.echo(format_data_for_output(results_summary, output)) # Use format_data_for_output

    except ResourceNotFoundError: 
        click.echo(f"Collection '{collection_key_or_id}' not found.", err=True)
    except PyZoteroError as e:
        click.echo(f"Zotero API Error: {e}", err=True)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)

@collection_group.command(name="tags")
@click.argument('collection_key_or_id', required=True)
@common_options 
@click.pass_context
def collection_tags(ctx, collection_key_or_id, limit, start, since, sort, direction, output, query, qmode, filter_tags, filter_item_type):
    """Get tags for items in a given collection."""
    zot_client = ctx.obj['zotero_client']
    api_params = prepare_api_params(limit, start, since, sort, direction, query, qmode, filter_tags, filter_item_type)
    try:
        # collection_tags requires a collection key/ID and returns all tags for items in the collection.
        results = zot_client.collection_tags(collection_key_or_id, **api_params)
        click.echo(format_data_for_output(results, output))
    except PyZoteroError as e:
        handle_zotero_exceptions_and_exit(ctx, e)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)
        ctx.exit(1) 