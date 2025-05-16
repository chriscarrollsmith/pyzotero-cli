# pyzotero-cli

[![PyPI version](https://badge.fury.io/py/pyzotero-cli.svg)](https://badge.fury.io/py/pyzotero-cli)
![Python Version](https://img.shields.io/pypi/pyversions/pyzotero-cli)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
<!-- [![Build Status](https://github.com/chriscarrollsmith/pyzotero-cli/actions/workflows/python-package.yml/badge.svg)](https://github.com/chriscarrollsmith/pyzotero-cli/actions/workflows/python-package.yml) -->

`pyzotero-cli` is a powerful command-line interface (CLI) for interacting with your Zotero library. It acts as a wrapper around the excellent [pyzotero](https://github.com/zotero/pyzotero) library, exposing its rich functionality directly to your terminal.

This tool is designed for users who prefer a command-line workflow, for scripting Zotero interactions, or for integration with other tools and AI agents that can leverage shell commands. Example "Rules for AI" to instruct your AI agent (e.g., in Cline or Cursor) how to use this tool are available in the [rules_for_ai](/rules_for_ai) directory.

## Features

*   **Comprehensive Zotero API Coverage:** Manage items, collections, tags, attachments, saved searches, full-text content, and groups.
*   **Flexible Configuration:**
    *   Support for multiple profiles.
    *   Configuration via interactive setup, environment variables, or direct CLI flags.
    *   Option to use a local Zotero instance (read-only).
*   **Multiple Output Formats:** Get data as JSON (default), YAML, or user-friendly tables. Also supports `keys` output for easy piping.
*   **Rich Querying Capabilities:**
    *   Pagination (`--limit`, `--start`).
    *   Sorting (`--sort`, `--direction`).
    *   Filtering (`--query`, `--filter-tag`, `--filter-item-type`).
    *   Versioning/Syncing (`--since`).
*   **Full CRUD Operations:** Create, Read, Update, and Delete various Zotero entities.
*   **File Management:** Download and upload attachments.
*   **Utility Commands:** Access API key info, library versions, item type definitions, and more.

## Why `pyzotero-cli`?

*   **Automation & Scripting:** Easily integrate Zotero operations into your shell scripts and automated workflows.
*   **Terminal Power Users:** Manage your Zotero library without leaving the command line.
*   **AI Agent Integration:** Designed to be easily consumable by AI systems with Bash/shell execution capabilities.
*   **Focused Interface:** Provides direct access to `pyzotero` features in a command-line paradigm.

## Installation

`pyzotero-cli` requires Python 3.10 or higher. You can install it using `pip`:

```bash
pip install pyzotero-cli -U # -g for global install
```

For global installation, better practice is to [download and install uv](https://docs.astral.sh/uv/getting-started/installation/) and then use `uv tool install` to install into `uv`'s persistent managed tool environment:

```bash
# Install latest version of pyzotero-cli as a persistent tool
uv tool install pyzotero-cli -U

# Ensure uv's bin directory is in your PATH (if needed)
uv tool update-shell

# Now the `zot` command is available directly
zot --help
```

You can also use `uvx` to run the CLI tool in a temporary environment without permanently installing it:

```bash
# Run the zot CLI in a temporary isolated environment
uvx --from pyzotero-cli zot --help
```

## Configuration

Before you can use `pyzotero-cli` to interact with your Zotero library (unless using the `--local` flag for a local read-only Zotero instance), you need to configure it with your Zotero API key and library details.

The easiest way to get started is with the interactive setup:

```bash
zot configure setup
```

This will guide you through setting up a default profile, asking for:
*   **Zotero Library ID:** Your Zotero User ID (for personal libraries) or Group ID.
*   **Library Type:** `user` or `group`.
*   **Zotero API Key:** Generate one from your Zotero account settings ([Feeds/API page](https://www.zotero.org/settings/keys)).
*   **Use local Zotero instance:** Whether to connect to a running Zotero desktop client locally (read-only mode, not recommended!).
*   **Locale:** Defaults to `en-US`.

Configuration is stored in `~/.config/zotcli/config.ini`.

### Profiles

You can manage multiple configurations using profiles:

```bash
# Set up a new profile named 'work_group'
zot configure setup --profile work_group

# List available profiles
zot configure list-profiles

# Set the default active profile
zot configure current-profile work_group

# Use a specific profile for a single command
zot --profile work_group items list
```

### Configuration Precedence

The CLI respects the following order of precedence for configuration settings:
1.  Command-line flags (e.g., `--api-key`, `--library-id`).
2.  Environment variables (e.g., `ZOTERO_API_KEY`, `ZOTERO_LIBRARY_ID`, `ZOTERO_LIBRARY_TYPE`).
3.  Active profile in `~/.config/zotcli/config.ini`.

## Basic Usage

Once configured, you can interact with your library using the `zot` command.

```bash
# List the 5 most recently modified items (default JSON output)
zot items list --limit 5

# Get details for a specific item (replace <ITEM_KEY> with an actual key)
zot items get <ITEM_KEY>

# List top-level collections in a table format
zot collections list --top --output table

# Get help for the 'items' command group
zot items --help

# Get help for a specific subcommand
zot items create --help
```

## Command Overview

`pyzotero-cli` is organized into several command groups:

*   `items`: Manage library items (books, articles, etc.).
    *   `list`, `get`, `create`, `update`, `delete`, `add-tags`, `children`, `count`, `versions`, `bib`, `citation`.
*   `collections`: Manage collections.
    *   `list`, `get`, `create`, `update`, `delete`, `items`, `item-count`, `versions`, `add-item`, `remove-item`, `tags`.
*   `tags`: Manage tags.
    *   `list`, `list-for-item`, `delete`.
*   `files`: Manage file attachments.
    *   `download`, `upload`, `upload-batch`.
*   `search`: Manage saved searches.
    *   `list`, `create`, `delete`.
*   `fulltext`: Work with full-text content of attachments.
    *   `get`, `list-new`, `set`.
*   `groups`: List accessible groups.
    *   `list`.
*   `util`: Utility and informational commands.
    *   `key-info`, `last-modified-version`, `item-types`, `item-fields`, `item-type-fields`, `item-template`.
*   `configure`: Manage CLI configuration and profiles.
    *   `setup`, `set`, `get`, `list-profiles`, `current-profile`.

### Common Options

Many commands support common options:

*   `--output <format>`: Set output format (`json`, `yaml`, `table`, `keys`). Default is `json`.
*   `--limit <N>`: Limit the number of results.
*   `--start <N>`: Offset for pagination.
*   `--sort <field>`: Field to sort by (e.g., `dateModified`, `title`).
*   `--direction <asc|desc>`: Sort direction.
*   `--query <term>`: Quick search query.
*   `--qmode <titleCreatorYear|everything>`: Quick search mode.
*   `--filter-tag <tag>`: Filter by tag (can be used multiple times).
*   `--filter-item-type <type>`: Filter by item type.
*   `--since <version>`: Retrieve objects modified after a Zotero library version.
*   `--local`: Use local Zotero instance (read-only mode - only GET operations will work, global option for `zot`).
*   `--profile <name>`: Use a specific configuration profile (global option for `zot`).
*   `--verbose`/`-v`, `--debug`: Increase verbosity.
*   `--no-interaction`: Disable interactive prompts (e.g., for confirmations).

## Examples

```bash
# Configure a profile named "personal_lib"
zot configure setup --profile personal_lib
# ... follow interactive prompts ...

# List 10 most recent journal articles in your personal library, output as a table
zot --profile personal_lib items list --filter-item-type journalArticle --sort dateModified --direction desc --limit 10 --output table

# Create a new book item from a Zotero item template
zot util item-template book > book_template.json
# ... edit book_template.json ...
zot items create --from-json book_template.json

# Get all collections containing the word "AI" in their name
zot collections list --query AI

# Download an attachment (replace <ATTACHMENT_KEY> and <PATH_TO_SAVE>)
zot files download <ATTACHMENT_KEY> -o <PATH_TO_SAVE>/attachment.pdf

# Add a tag to an item
zot items add-tags <ITEM_KEY> "needs-review" "important"
```

## Development

Contributions are welcome!

1.  Clone the repository:
    ```bash
    git clone https://github.com/chriscarrollsmith/pyzotero-cli.git
    cd pyzotero-cli
    ```

2.  This project uses `uv` for dependency management (see `uv.lock`).
    ```bash
    # Create a venv and install dependencies
    uv sync
    ```

3.  Run tests:
    ```bash
    uv run pytest
    ```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details (assuming one will be added).
