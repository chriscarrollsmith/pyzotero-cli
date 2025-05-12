import click
import json as json_lib

# Common options decorator
def common_options(func):
    options = [
        click.option('--limit', type=int, help='Number of results to return.'),
        click.option('--start', type=int, help='Offset for pagination.'),
        click.option('--since', help='Retrieve objects modified after a library version.'),
        click.option('--sort', help='Field to sort by.'),
        click.option('--direction', type=click.Choice(['asc', 'desc']), help='Sort direction.'),
        click.option('--output', type=click.Choice(['json', 'yaml', 'table', 'keys', 'bibtex', 'csljson']), default='json', show_default=True, help='Output format.'),
        click.option('--query', '-q', help='Quick search query.'),
        click.option('--qmode', type=click.Choice(['titleCreatorYear', 'everything']), help='Quick search mode.'),
        click.option('--filter-tag', 'filter_tags', multiple=True, help='Filter by tag (can be specified multiple times for AND logic).'),
        click.option('--filter-item-type', help='Filter by item type.')
    ]
    for option in reversed(options):
        func = option(func)
    return func 

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


def format_data_for_output(data, output_format, requested_fields_or_key=None, table_headers_map=None):
    """
    Formats data for output based on the specified format.

    Args:
        data: List of dicts or a single dict (raw from pyzotero or processed).
        output_format: 'json', 'yaml', 'table', 'keys'.
        requested_fields_or_key: For 'table' output with pre-processed data, this is a list of
                                 dict keys (display names) to determine column order.
                                 For 'keys' output, this is the string name of the key to extract.
        table_headers_map: For 'table' output with raw data, this is a list of tuples:
                           (display_header_name, accessor_lambda_or_dot_path_string).
                           If None, and data is suitable, 'requested_fields_or_key' is used for headers.
                           If data is not a list of dicts, it's tabulated as simple rows.
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