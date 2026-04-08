"""Mock Zotero client for testing without live API credentials."""

import json
import copy
from pathlib import Path

from pyzotero.zotero_errors import ResourceNotFoundError, PyZoteroError


_DATA_DIR = Path(__file__).parent / "api_responses"


def _load_json(filename):
    with open(_DATA_DIR / filename) as f:
        return json.load(f)


class MockZoteroClient:
    """A mock pyzotero.zotero.Zotero client that returns canned API responses."""

    def __init__(self, library_id="12345", library_type="user", api_key="fake_api_key_12345", **kwargs):
        self.library_id = library_id
        self.library_type = library_type
        self.api_key = api_key
        self._created_items = {}
        self._deleted_keys = set()
        self._counter = 0

    def _next_key(self):
        self._counter += 1
        return f"MOCK{self._counter:04d}"

    # ── Items ──────────────────────────────────────────────────────────

    def items(self, **kwargs):
        content = kwargs.get("content")
        if content == "bib":
            return ['<div class="csl-entry">Mock Bibliography Entry</div>']
        if content == "citation":
            return ["(Mock Author, 2024)"]
        if kwargs.get("format") == "bibtex":
            return "@book{mock2024,\n  title={Mock Book},\n  author={Author, Mock},\n  year={2024}\n}"
        data = _load_json("items_doc.json")
        limit = kwargs.get("limit")
        if limit:
            data = data[:int(limit)]
        return data

    def top(self, **kwargs):
        return self.items(**kwargs)

    def publications(self, **kwargs):
        return self.items(**kwargs)

    def trash(self, **kwargs):
        return []

    def deleted(self, **kwargs):
        return {"items": [], "collections": [], "searches": [], "tags": []}

    def item(self, key, **kwargs):
        if key.startswith("NONEXIST"):
            raise ResourceNotFoundError(
                f"https://api.zotero.org/users/12345/items/{key}",
                "404",
                "Not found",
            )
        content = kwargs.get("content")
        if content == "bib":
            return '<div class="csl-entry">Mock Bibliography Entry</div>'
        if content == "citation":
            return "(Mock Author, 2024)"
        if content == "csljson":
            return {"id": key, "type": "article-journal", "title": "Mock Item"}
        if key in self._created_items:
            return self._created_items[key]
        return _load_json("item_doc.json")

    def children(self, key, **kwargs):
        items = _load_json("items_doc.json")
        return items[:1]

    def count_items(self):
        return 42

    def num_items(self):
        return 42

    def item_versions(self, **kwargs):
        return _load_json("item_versions.json")

    def create_items(self, payloads):
        result = {"success": {}, "successful": {}, "failed": {}, "unchanged": {}}
        for i, payload in enumerate(payloads):
            key = self._next_key()
            item_data = copy.deepcopy(payload)
            item_data["key"] = key
            item_data["version"] = 1
            result["success"][str(i)] = key
            result["successful"][str(i)] = {
                "key": key,
                "version": 1,
                "data": item_data,
            }
            self._created_items[key] = {
                "key": key,
                "version": 1,
                "library": {"type": self.library_type, "id": int(self.library_id)},
                "data": item_data,
            }
        return result

    def update_item(self, item_dict):
        key = item_dict.get("key") or item_dict.get("data", {}).get("key")
        if key and key in self._created_items:
            self._created_items[key]["version"] += 1
        return True

    def delete_item(self, item_dict):
        key = item_dict.get("key") if isinstance(item_dict, dict) else None
        if key:
            self._deleted_keys.add(key)
            self._created_items.pop(key, None)
        return True

    def add_tags(self, item, *tags):
        return True

    def item_template(self, item_type, linkmode=None):
        # Base fields common to all types
        base = {
            "itemType": item_type,
            "title": "",
            "creators": [],
            "abstractNote": "",
            "date": "",
            "language": "",
            "shortTitle": "",
            "url": "",
            "accessDate": "",
            "extra": "",
            "tags": [],
            "collections": [],
            "relations": {},
            "rights": "",
            "dateAdded": "",
            "dateModified": "",
            "libraryCatalog": "",
            "DOI": "",
        }
        # Type-specific fields
        type_fields = {
            "journalArticle": {"publicationTitle": "", "volume": "", "issue": "", "pages": "", "ISSN": "", "journalAbbreviation": ""},
            "book": {"publisher": "", "place": "", "ISBN": "", "numPages": "", "edition": "", "series": "", "seriesNumber": ""},
            "bookSection": {"bookTitle": "", "publisher": "", "place": "", "ISBN": "", "pages": "", "edition": "", "series": ""},
            "preprint": {"repository": "", "archiveID": "", "place": ""},
            "conferencePaper": {"conferenceName": "", "proceedingsTitle": "", "publisher": "", "place": "", "pages": "", "ISBN": ""},
            "report": {"reportNumber": "", "reportType": "", "institution": "", "place": ""},
            "webpage": {"websiteTitle": "", "websiteType": ""},
            "thesis": {"university": "", "thesisType": "", "place": ""},
            "attachment": {"linkMode": linkmode or "", "contentType": "", "charset": "", "filename": "", "parentItem": ""},
            "note": {"note": "", "parentItem": ""},
        }
        if item_type in type_fields:
            base.update(type_fields[item_type])
        if linkmode:
            base["linkMode"] = linkmode
        return base

    # ── Collections ────────────────────────────────────────────────────

    def collections(self, **kwargs):
        data = _load_json("collections_doc.json")
        limit = kwargs.get("limit")
        if limit:
            data = data[:int(limit)]
        return data

    def collections_top(self, **kwargs):
        data = _load_json("collections_doc.json")
        return [c for c in data if not c.get("data", {}).get("parentCollection")]

    def collection(self, key, **kwargs):
        if key.startswith("NONEXIST"):
            raise ResourceNotFoundError(
                f"https://api.zotero.org/users/12345/collections/{key}",
                "404",
                "Not found",
            )
        return _load_json("collection_doc.json")

    def collections_sub(self, key, **kwargs):
        return _load_json("collections_doc.json")[:2]

    def all_collections(self, parent_id=None):
        return _load_json("collections_doc.json")

    def collection_items(self, key, **kwargs):
        return self.items(**kwargs)

    def collection_items_top(self, key, **kwargs):
        return self.items(**kwargs)

    def collection_tags(self, key, **kwargs):
        return _load_json("collection_tags.json")

    def collection_versions(self, **kwargs):
        return _load_json("collection_versions.json")

    def create_collections(self, payloads):
        result = {"success": {}, "successful": {}, "failed": {}, "unchanged": {}}
        for i, payload in enumerate(payloads):
            key = self._next_key()
            result["success"][str(i)] = key
            result["successful"][str(i)] = {"key": key, "version": 1}
        return result

    def update_collection(self, coll_dict):
        return True

    def delete_collection(self, coll_dict):
        return True

    # ── Tags ───────────────────────────────────────────────────────────

    def tags(self, **kwargs):
        raw = _load_json("tags_doc.json")
        limit = kwargs.get("limit")
        tag_names = [t["tag"] for t in raw]
        if limit:
            tag_names = tag_names[:int(limit)]
        return tag_names

    def item_tags(self, key, **kwargs):
        return ["mock-tag-1", "mock-tag-2"]

    def delete_tags(self, *tag_names):
        return True

    # ── Groups ─────────────────────────────────────────────────────────

    def groups(self, **kwargs):
        data = _load_json("groups_doc.json")
        limit = kwargs.get("limit")
        if limit:
            data = data[:int(limit)]
        return data

    # ── Saved Searches ─────────────────────────────────────────────────

    def searches(self):
        return _load_json("searches_doc.json")

    def saved_search(self, name, conditions):
        key = self._next_key()
        return {
            "successful": {
                "0": {"key": key, "version": 1}
            },
            "success": {"0": key},
            "failed": {},
            "unchanged": {},
        }

    def delete_saved_search(self, keys_tuple):
        return 204

    # ── Fulltext ───────────────────────────────────────────────────────

    def fulltext_item(self, key):
        if key.startswith("NONEXIST") or key.startswith("THISKEY"):
            raise ResourceNotFoundError(
                f"https://api.zotero.org/users/12345/items/{key}/fulltext",
                "404",
                "Not found",
            )
        return _load_json("fulltext_doc.json")

    def set_fulltext(self, key, payload):
        return True

    def new_fulltext(self, since=None):
        return {}

    # ── Files ──────────────────────────────────────────────────────────

    def file(self, key):
        return b"Mock file content for testing."

    def dump(self, key, filename=None, path=None):
        import os
        if filename and path:
            full_path = os.path.join(path, filename)
        elif path:
            full_path = os.path.join(path, "mock_file.txt")
        else:
            full_path = "mock_file.txt"
        with open(full_path, "wb") as f:
            f.write(b"Mock file content for testing.")
        return full_path

    def upload_attachments(self, items):
        result = {"success": [], "unchanged": [], "failure": {}}
        for item in items:
            key = item.get("key", self._next_key())
            result["success"].append(key)
        return result

    def attachment_simple(self, files, parentid=None):
        import os
        result = {"success": [], "unchanged": [], "failure": []}
        for f in (files if isinstance(files, list) else [files]):
            key = self._next_key()
            fname = os.path.basename(f) if isinstance(f, str) else "file"
            result["success"].append({"key": key, "filename": fname})
        return result

    def attachment_both(self, files, parentid=None):
        import os
        result = {"success": [], "unchanged": [], "failure": []}
        for f, name in (files if isinstance(files, list) else [files]):
            key = self._next_key()
            result["success"].append({"key": key, "filename": name})
        return result

    # ── Utility ────────────────────────────────────────────────────────

    def key_info(self):
        return _load_json("key_info_doc.json")

    def last_modified_version(self):
        return 12345

    def item_types(self):
        return _load_json("item_types.json")

    def item_fields(self):
        return _load_json("item_fields.json")

    def item_type_fields(self, itemtype=None):
        if itemtype == "notAnItemType":
            raise PyZoteroError(f"Invalid item type '{itemtype}'")
        return [
            {"field": "title", "localized": "Title"},
            {"field": "abstractNote", "localized": "Abstract"},
            {"field": "publisher", "localized": "Publisher"},
            {"field": "date", "localized": "Date"},
            {"field": "language", "localized": "Language"},
            {"field": "ISBN", "localized": "ISBN"},
            {"field": "numPages", "localized": "# of Pages"},
        ]

    def item_creator_types(self, itemtype=None):
        return [
            {"creatorType": "author", "localized": "Author"},
            {"creatorType": "editor", "localized": "Editor"},
        ]
