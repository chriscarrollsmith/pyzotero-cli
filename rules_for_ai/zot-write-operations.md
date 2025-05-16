---
description: 
globs: 
alwaysApply: true
---
The following commands are available from the `pyzotero-cli` tool, entrypoint `zot`. For a given command, use the `--help` flag to get more detail on usage.

```
Usage: zot [OPTIONS] COMMAND [ARGS]...

  A CLI for interacting with Zotero libraries via Pyzotero.

Options:
  --profile TEXT               Use a specific configuration profile.
  --api-key TEXT               Override API key.
  --library-id TEXT            Override library ID.
  --library-type [user|group]  Override library type.
  --local                      Use local Zotero instance (read-only).
  -v, --verbose                Verbose logging.
  --debug                      Debug logging.
  --no-interaction             Disable interactive prompts.
  --help                       Show this message and exit.

Commands:
  collections  Manage Zotero collections.
  configure    Manage pyzotero-cli configuration profiles.
  files        Commands for managing Zotero file attachments.
  fulltext     Commands for working with full-text content.
  groups       Commands for interacting with Zotero groups.
  items        Manage Zotero items.
  search       Manage Zotero saved searches.
  tags         Commands for working with Zotero tags.
  util         Utility and informational commands.
```

Here are some additional useful details:

### 1. **Available Item Types**
The `zot` tool supports a wide range of item types, including but not limited to:
- `journalArticle`
- `book`
- `bookSection`
- `conferencePaper`
- `thesis`
- `webpage`
- `report`
- `film`
- `audioRecording`
- `videoRecording`

You can list all available item types using:
```bash
zot util item-types
```

### 2. **Adding Items**
To add items to your Zotero library, use the `zot items create` command. There are two primary methods:
- **From JSON**: Provide JSON with the item details (can be a single object or array of objects):
  ```bash
  zot items create --from-json item.json

  zot items create --from-json '{
    "itemType": "journalArticle",
    "title": "My Paper",
    "creators": [{"creatorType": "author", "firstName": "John", "lastName": "Doe"}]
  }'
  ```
- **From Template**: Use the `--template` and `--field` options for simple fields:
  ```bash
  zot items create --template journalArticle --field title "My Article"
  ```
Every item requires "itemType", "title", and "creators". Other commonly shared fields include "abstractNote", "publicationTitle", "volume", "issue", "pages", "date", "DOI", "url", and "tags". (Tags must be objects: `{"tag": "value"}`.)

To list all fields for a given item type, use `zot util item-type-fields <item-type>`

### 3. **Debugging Tips**
- **Temporary Files**: Create a `temp` directory for working files and add it to `.gitignore`. Keep temporary files for debugging.
- **Capture Results**: When uploading records, write the result to a JSON file like `zot items create --from-json <input_file_path> | tee <output_file_path>`. This allows you to perform automated review such as count of created records and review by ID.
- **Verify Created Records**: Try to verify the count of created records and/or spot-check by ID. Can records in the input file be counted, e.g. by a substring uniquely associated with all records (`grep "^- " <input_file_path> | wc -l`)? If so, you can compare with the output JSON length: `jq '. | length' <output_file_path>`.