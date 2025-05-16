import click
import json as json_lib

# --- Define a comprehensive list of known Zotero sort keys ---
# This list is for user guidance; not all keys are valid for all endpoints.
# The API/pyzotero will handle errors for invalid key/endpoint combinations.
ZOTERO_SORT_KEYS = [
    "dateAdded", "dateModified", "title", "creator", "type", "date", "publisher",
    "publicationTitle", "journalAbbreviation", "language", "accessDate",
    "libraryCatalog", "callNumber", "rights", "addedBy", "numItems", "tags"
]
# Removed ZOTERO_GROUP_SORT_KEYS, ZOTERO_TAG_SORT_KEYS, and VALID_SORT_KEYS_MAP

# Define entity-specific sort keys
COLLECTION_SORT_KEYS = ["dateAdded", "dateModified", "title", "numItems"]
ITEM_SORT_KEYS = ["dateAdded", "dateModified", "title", "creator", "type", "date", 
                 "publisher", "publicationTitle", "journalAbbreviation", "language", 
                 "accessDate", "libraryCatalog", "callNumber", "rights"]
TAG_SORT_KEYS = ["title", "numItems"]
GROUP_SORT_KEYS = ["title", "numItems", "created", "lastActivity"]

# Mapping of allowed API parameters for specific PyZotero methods
ALLOWED_API_PARAMS_MAP = {
    'collections': ['limit', 'start', 'sort', 'direction', 'since'],
    'collections_top': ['limit', 'start', 'sort', 'direction', 'since'],
    'collection': ['since'],
    'collection_items': ['limit', 'start', 'sort', 'direction', 'q', 'qmode', 'tag', 'itemType', 'since'],
    'collection_items_top': ['limit', 'start', 'sort', 'direction', 'q', 'qmode', 'tag', 'itemType', 'since'],
    'items': ['limit', 'start', 'sort', 'direction', 'q', 'qmode', 'tag', 'itemType', 'since', 'itemKey', 'content', 'style', 'linkwrap'],
    'top': ['limit', 'start', 'sort', 'direction', 'q', 'qmode', 'tag', 'itemType', 'since'],
    'trash': ['limit', 'start', 'sort', 'direction', 'q', 'qmode', 'tag', 'itemType', 'since'],
    'publications': ['limit', 'start', 'sort', 'direction', 'q', 'qmode', 'tag', 'itemType', 'since'],
    'deleted': ['since'],
    'item': ['since', 'content', 'style', 'linkwrap'],
    'children': ['limit', 'start', 'sort', 'direction', 'since'],
}

# Granular decorators for Click commands

def output_option(func):
    """Decorator to add output format option to a Click command."""
    return click.option(
        '--output',
        type=click.Choice(['json', 'yaml', 'table', 'keys', 'bibtex', 'csljson', 'bib']),
        default='json',
        show_default=True,
        help='Output format.'
    )(func)

def pagination_options(func):
    """Decorator to add pagination options to a Click command."""
    func = click.option('--limit', type=int, help='Number of results to return.')(func)
    func = click.option('--start', type=int, help='Offset for pagination.')(func)
    return func

def sorting_options(entity_type=None):
    """
    Decorator factory to add sorting options to a Click command.
    
    Args:
        entity_type: Optional entity type to use specific sort keys.
                    Can be 'collection', 'item', 'tag', or 'group'.
    
    Returns:
        A decorator function that adds sorting options.
    """
    def decorator(func):
        sort_keys = ZOTERO_SORT_KEYS  # Default to all sort keys
        
        # Use entity-specific sort keys if provided
        if entity_type == 'collection':
            sort_keys = COLLECTION_SORT_KEYS
        elif entity_type == 'item':
            sort_keys = ITEM_SORT_KEYS
        elif entity_type == 'tag':
            sort_keys = TAG_SORT_KEYS
        elif entity_type == 'group':
            sort_keys = GROUP_SORT_KEYS
        
        func = click.option(
            '--sort',
            type=click.Choice(sort_keys, case_sensitive=False),
            help=f"Field to sort by. Valid sort keys for this entity: {' | '.join(sort_keys)}."
        )(func)
        
        func = click.option(
            '--direction',
            type=click.Choice(['asc', 'desc'], case_sensitive=False),
            default='asc',
            show_default=True,
            help='Sort direction.'
        )(func)
        
        return func
    return decorator

def filtering_options(func):
    """Decorator to add filtering options to a Click command."""
    func = click.option('--query', '-q', help='Quick search query.')(func)
    func = click.option(
        '--qmode',
        type=click.Choice(['titleCreatorYear', 'everything']),
        help='Quick search mode.'
    )(func)
    func = click.option(
        '--filter-tag',
        'filter_tags',
        multiple=True,
        help='Filter by tag (can be specified multiple times for AND logic).'
    )(func)
    func = click.option('--filter-item-type', help='Filter by item type.')(func)
    return func

def versioning_option(func, required=False):
    """
    Decorator to add library version option to a Click command.
    
    Args:
        required: Whether the since option is required.
    """
    return click.option(
        '--since',
        required=required,
        help='Retrieve objects modified after a library version.'
    )(func)

def deleted_items_options(func):
    """Decorator for options specific to listing deleted items."""
    return versioning_option(func, required=True)

# Common options decorator as a composition of granular decorators
def common_options(func):
    """Legacy decorator that applies all common options."""
    func = output_option(func)
    func = pagination_options(func)
    func = sorting_options()(func)
    func = filtering_options(func)
    func = versioning_option(func)
    return func

def prepare_api_params(limit=None, start=None, since=None, sort=None, direction=None, 
                       query=None, qmode=None, filter_tags=None, filter_item_type=None, 
                       api_method=None, **kwargs):
    """
    Prepares parameters for Pyzotero API calls.
    
    Args:
        limit: Number of results to return.
        start: Offset for pagination.
        since: Retrieve objects modified after a library version.
        sort: Field to sort by.
        direction: Sort direction ('asc' or 'desc').
        query: Quick search query.
        qmode: Quick search mode ('titleCreatorYear' or 'everything').
        filter_tags: Filter by tag (multiple tags use AND logic).
        filter_item_type: Filter by item type.
        api_method: The Pyzotero API method being called (e.g., 'items', 'collections').
                   If provided, will check for unused parameters.
        **kwargs: Additional parameters to pass to the API.
        
    Returns:
        dict: Dictionary of parameters for Pyzotero API calls.
    """
    params = {}
    if limit is not None: params['limit'] = limit
    if start is not None: params['start'] = start
    if since is not None: params['since'] = since  # Used for versioning/syncing
    if sort is not None: params['sort'] = sort
    if direction is not None: params['direction'] = direction
    if query is not None: params['q'] = query
    if qmode is not None: params['qmode'] = qmode
    if filter_tags:  # filter_tags is a tuple of strings from click
        # Pyzotero expects a list for multiple tags (results in tag=A&tag=B)
        # or a comma-separated string for some endpoints (tag=A,B).
        # For general items() filtering, list is usually preferred for AND.
        params['tag'] = list(filter_tags)
    if filter_item_type is not None: params['itemType'] = filter_item_type
    
    # Clean out None values explicitly, as Pyzotero might treat them as actual params
    params = {k: v for k, v in params.items() if v is not None}
    
    params.update(kwargs)
    
    # Check for unused parameters if api_method is provided
    if api_method and api_method in ALLOWED_API_PARAMS_MAP:
        check_unused_params(params, api_method)
    
    return params

def check_unused_params(params, api_method, ctx=None):
    """
    Check for parameters that are not used by the specific Pyzotero method.
    Issues a warning if any are found.
    
    Args:
        params: Dictionary of parameters for the API call.
        api_method: The Pyzotero API method being called (e.g., 'items', 'deleted').
        ctx: Click context, if available, for exiting on critical errors.
    
    Returns:
        dict: Filtered dictionary containing only the allowed parameters.
    """
    if api_method not in ALLOWED_API_PARAMS_MAP:
        # If we don't know about this method, return all params unfiltered
        return params
    
    allowed_params = ALLOWED_API_PARAMS_MAP[api_method]
    unused_params = {k: v for k, v in params.items() if k not in allowed_params}
    
    if unused_params:
        warning_msg = f"Warning: The following parameters are not applicable to the '{api_method}' call and will be ignored: {', '.join(unused_params.keys())}"
        click.echo(warning_msg, err=True)
        
        # Return a filtered dictionary with only the allowed parameters
        return {k: v for k, v in params.items() if k in allowed_params}
    
    # If no unused parameters, return the original dict
    return params

# Import optional libraries for formatting, with fallbacks
try:
    import yaml
except ImportError:
    yaml = None # type: ignore

try:
    from tabulate import tabulate
except ImportError:
    tabulate = None # type: ignore

from pyzotero import zotero_errors # For specific Zotero exceptions

# Table header presets for common Zotero entities
TABLE_HEADER_PRESETS = {
    'collection': [
        ("Name", 'data.name'),
        ("Key", 'key'),
        ("Items", 'meta.numItems')
    ],
    'item': [
        ("Title", 'data.title'),
        ("Key", 'key'),
        ("Type", 'data.itemType'),
        ("Date", 'data.date'),
        ("Creator", lambda item: item.get('meta', {}).get('creatorSummary', ''))
    ],
    'tag': [
        ("Tag", 'tag'),
        ("Type", 'type'),
        ("Count", lambda item: item.get('meta', {}).get('numItems', 0))
    ],
    'group': [
        ("Name", 'data.name'),
        ("ID", 'id'),
        ("Type", 'data.type'),
        ("Owner", 'data.owner'),
        ("Members", lambda item: len(item.get('data', {}).get('members', [])))
    ]
}

def format_data_for_output(data, output_format, requested_fields_or_key=None, table_headers_map=None, preset_key=None):
    """
    Formats data for output based on the specified format.

    Args:
        data: List of dicts or a single dict (raw from pyzotero or processed).
        output_format: 'json', 'yaml', 'table', 'keys', 'bibtex', 'csljson'.
        requested_fields_or_key: For 'table' output with pre-processed data, this is a list of
                                 dict keys (display names) to determine column order.
                                 For 'keys' output, this is the string name of the key to extract.
        table_headers_map: For 'table' output with raw data, this is a list of tuples:
                           (display_header_name, accessor_lambda_or_dot_path_string).
                           If None, and data is suitable, 'requested_fields_or_key' is used for headers.
                           If data is not a list of dicts, it's tabulated as simple rows.
        preset_key: String key for predefined table header mappings (e.g., 'collection', 'item').
                    If provided and matches an entry in TABLE_HEADER_PRESETS, those headers are used.
    """
    if output_format == 'json':
        return json_lib.dumps(data, indent=2, ensure_ascii=False)
    elif output_format == 'yaml':
        if yaml:
            return yaml.dump(data, sort_keys=False, allow_unicode=True)
        else:
            click.echo("Warning: PyYAML not installed. Falling back to JSON for YAML output.", err=True)
            return json_lib.dumps(data, indent=2, ensure_ascii=False)
    elif output_format == 'table':
        if not data:
            return "No data to display."

        source_list = data if isinstance(data, list) else [data]
        if not source_list: # handles case where data was an empty list initially
            return "No data to display."

        items_for_tabulation = []
        display_headers = []

        # Use preset table headers if specified
        if preset_key and preset_key in TABLE_HEADER_PRESETS:
            table_headers_map = TABLE_HEADER_PRESETS[preset_key]

        if table_headers_map:
            # Data is raw, needs processing using the table_headers_map
            display_headers = [h_map[0] for h_map in table_headers_map]
            for raw_item in source_list:
                item_dict = {}
                for display_name, accessor in table_headers_map:
                    if callable(accessor):
                        try:
                            item_dict[display_name] = accessor(raw_item)
                        except Exception: # pylint: disable=broad-except
                            item_dict[display_name] = '' # Graceful failure for accessor
                    elif isinstance(accessor, str): # dot-path string
                        current_value = raw_item
                        try:
                            for part in accessor.split('.'):
                                current_value = current_value.get(part) if isinstance(current_value, dict) else None
                                if current_value is None: break
                            item_dict[display_name] = current_value if current_value is not None else ''
                        except AttributeError:
                            item_dict[display_name] = ''
                    else: # Should not happen if map is correctly defined
                        item_dict[display_name] = ''
                items_for_tabulation.append(item_dict)
        else:
            # Data is assumed to be a list of dicts already suitable for tabulation
            # or a simple list of items.
            if not isinstance(source_list[0], dict): # e.g. list of strings/numbers
                 items_for_tabulation = [[item] for item in source_list]
                 display_headers = ["Value"] # Default header for simple list
            else: # list of dicts
                items_for_tabulation = source_list
                if requested_fields_or_key and isinstance(requested_fields_or_key, list):
                    display_headers = requested_fields_or_key
                elif items_for_tabulation: # Auto-detect headers from first item's keys
                    display_headers = list(items_for_tabulation[0].keys())
                else: # No data to determine headers
                    display_headers = []
        
        # Prepare rows for tabulate based on display_headers order
        tabulate_rows = []
        for item_d in items_for_tabulation:
            if isinstance(item_d, dict): # if it was processed into dict or was originally dict
                tabulate_rows.append([item_d.get(h, '') for h in display_headers])
            else: # if it's a simple list like [[val1],[val2]]
                tabulate_rows.append(item_d)


        if tabulate:
            return tabulate(tabulate_rows, headers=display_headers, tablefmt="grid")
        else:
            click.echo("Warning: 'tabulate' library not installed. Using basic text table.", err=True)
            output_str = ""
            if display_headers:
                output_str += "\t".join(map(str, display_headers)) + "\n"
                output_str += "\t".join(["---"] * len(display_headers)) + "\n"
            for r_values in tabulate_rows:
                output_str += "\t".join(map(str, r_values)) + "\n"
            return output_str.strip()

    elif output_format == 'keys':
        if not data:
            return ""
        
        source_list = data if isinstance(data, list) else [data]
        key_to_extract_str = requested_fields_or_key if isinstance(requested_fields_or_key, str) else 'key' # Default 'key' for Zotero items, 'id' for groups

        keys_list = []
        for item_data in source_list:
            if isinstance(item_data, dict):
                value = None
                # Try direct access, then 'data' sub-dict for common Zotero item structure
                if key_to_extract_str in item_data:
                    value = item_data[key_to_extract_str]
                elif 'data' in item_data and isinstance(item_data['data'], dict) and key_to_extract_str in item_data['data']:
                    value = item_data['data'][key_to_extract_str]
                
                if value is not None:
                    keys_list.append(str(value))
        return "\n".join(keys_list)
    elif output_format == 'csljson':
        # Handle csljson which is typically already in the right format but might need to be serialized
        if isinstance(data, (list, dict)):
            return json_lib.dumps(data, indent=2, ensure_ascii=False)
        else:
            # If it's a string, just return it
            return data
    else: # Should not be reached if output_format is validated by click.Choice
        return json_lib.dumps(data)


def handle_zotero_exceptions_and_exit(ctx, e):
    """Handles PyZotero exceptions and prints user-friendly messages before exiting."""
    # Ensure all referenced zotero_errors attributes exist or use getattr
    error_messages = {
        getattr(zotero_errors, 'RateLimitExceeded', None): "Zotero API rate limit exceeded. Please try again later.",
        getattr(zotero_errors, 'InvalidAPIKey', None): "Invalid or missing Zotero API key.",
        getattr(zotero_errors, 'Forbidden', None): "Access forbidden. Check API key permissions or resource access rights.",
        getattr(zotero_errors, 'NotFound', None): "The requested resource was not found.",
        getattr(zotero_errors, 'ZoteroServerError', None): "A Zotero server error occurred. Please try again later.",
        getattr(zotero_errors, 'PreconditionFailed', None): "Precondition failed. This can occur if a library version ('since') is too old, or due to a data conflict (e.g., trying to update a deleted item).",
        getattr(zotero_errors, 'MissingCredentials', None): "Missing credentials for Zotero client (e.g. API key for non-local, or library ID/type).",
        getattr(zotero_errors, 'BadRequest', None): "Bad request. Check parameters and data format.",
        getattr(zotero_errors, 'MethodNotSupported', None): "The HTTP method is not supported for this resource.",
        getattr(zotero_errors, 'UnsupportedParams', None): "One or more parameters are not supported by this Zotero API endpoint.",
        getattr(zotero_errors, 'ResourceGone', None): "The resource is gone and no longer available.",
    }
    # Remove None keys if any exception type isn't found (defensive)
    error_messages = {k: v for k, v in error_messages.items() if k is not None}

    matched_message = None
    for exc_type, base_msg in error_messages.items():
        if isinstance(e, exc_type):
            matched_message = f"Error: {base_msg} (Details: {str(e)})"
            break
    
    # Add specific handling for HTTPError codes if not caught by the map above
    if not matched_message and isinstance(e, getattr(zotero_errors, 'HTTPError', type(None))):
        if hasattr(e, 'status_code'):
            if e.status_code == 404:
                # Use the same message as NotFound for consistency
                base_msg_404 = "The requested resource was not found."
                matched_message = f"Error: {base_msg_404} (Details: {str(e)})"
            # Potentially add other specific HTTP status code handlings here
            # elif e.status_code == 403:
            #     if not any(isinstance(e, ft) for ft in [getattr(zotero_errors, 'Forbidden', None), getattr(zotero_errors, 'UserNotAuthorisedError', None)] if ft): # Check if already handled by specific types
            #         base_msg_403 = "Access forbidden. Check API key permissions or resource access rights."
            #         matched_message = f"Error: {base_msg_403} (Details: {str(e)})"
    
    if not matched_message:
        if isinstance(e, zotero_errors.PyZoteroError): # Broader PyZotero exception
            matched_message = f"A PyZotero library error occurred: {str(e)}"
        else: # Non-PyZotero exception
            matched_message = f"An unexpected application error occurred: {type(e).__name__} - {str(e)}"

    click.echo(matched_message, err=True)
    
    is_debug_mode = False
    if ctx and hasattr(ctx, 'obj') and isinstance(ctx.obj, dict):
        is_debug_mode = ctx.obj.get('DEBUG', False)

    if is_debug_mode or not isinstance(e, zotero_errors.PyZoteroError): # Show traceback for debug or non-PyZotero errors
        import traceback
        click.echo(traceback.format_exc(), err=True)
    
    if ctx:
        ctx.exit(1)
    else: # If context is not available for some reason
        import sys
        sys.exit(1) 