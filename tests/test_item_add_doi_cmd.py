import copy
import json

from pyzotero_cli.zot_cli import zot


DUMMY_ENV = {
    "ZOTERO_API_KEY": "dummy-api-key",
    "ZOTERO_LIBRARY_ID": "dummy-library-id",
    "ZOTERO_LIBRARY_TYPE": "user",
}


class FakeZoteroClient:
    def __init__(self):
        self.items_by_key = {}
        self.next_key_index = 1
        self.collections = {"COLL1": {"key": "COLL1", "data": {"name": "Inbox"}}}

    def item_template(self, item_type):
        return {
            "itemType": item_type,
            "title": "",
            "DOI": "",
            "url": "",
            "language": "",
            "volume": "",
            "issue": "",
            "pages": "",
            "publisher": "",
            "ISSN": "",
            "ISBN": "",
            "abstractNote": "",
            "date": "",
            "publicationTitle": "",
            "bookTitle": "",
            "creators": [],
            "collections": [],
            "tags": [],
        }

    def item_creator_types(self, itemtype):
        return [
            {"creatorType": "author"},
            {"creatorType": "editor"},
            {"creatorType": "translator"},
        ]

    def items(self, **kwargs):
        q = kwargs.get("q")
        if not q:
            return list(self.items_by_key.values())
        needle = q.lower()
        return [
            copy.deepcopy(item)
            for item in self.items_by_key.values()
            if needle in item.get("data", {}).get("DOI", "").lower()
        ]

    def create_items(self, payloads):
        payload = copy.deepcopy(payloads[0])
        item_key = f"D{self.next_key_index:07d}"
        self.next_key_index += 1
        item = {"key": item_key, "version": 1, "data": payload}
        self.items_by_key[item_key] = item
        return {
            "successful": {"0": {"key": item_key, "version": 1}},
            "success": {"0": item_key},
        }

    def item(self, item_key):
        return copy.deepcopy(self.items_by_key[item_key])

    def update_item(self, item):
        updated = copy.deepcopy(item)
        updated["version"] = updated.get("version", 1) + 1
        self.items_by_key[item["key"]] = updated
        return True

    def collection(self, collection_key_or_id):
        return self.collections[collection_key_or_id]

    def add_existing_item(self, item_key, doi, title):
        self.items_by_key[item_key] = {
            "key": item_key,
            "version": 1,
            "data": {
                "itemType": "journalArticle",
                "title": title,
                "DOI": doi,
                "collections": [],
            },
        }


def _patch_clients(monkeypatch, fake_client):
    monkeypatch.setattr(
        "pyzotero_cli.zot_cli.pyzotero_client.Zotero",
        lambda **kwargs: fake_client,
    )
    monkeypatch.setattr(
        "pyzotero_cli.item_cmds.initialize_zotero_client",
        lambda ctx: fake_client,
    )


def _sample_csl_json(title="Imported by DOI"):
    return {
        "type": "article-journal",
        "title": title,
        "container-title": ["Journal of CLI Testing"],
        "issued": {"date-parts": [[2026, 3, 30]]},
        "author": [{"family": "Smith", "given": "Ada"}],
    }


def test_item_add_doi_creates_item(runner, monkeypatch):
    fake_client = FakeZoteroClient()
    _patch_clients(monkeypatch, fake_client)
    monkeypatch.setattr(
        "pyzotero_cli.item_cmds.doi_utils.fetch_csl_json_for_doi",
        lambda doi: _sample_csl_json(),
    )

    result = runner.invoke(
        zot,
        ["items", "add-doi", "10.1016/j.econmod.2026.107590"],
        env=DUMMY_ENV,
    )

    assert result.exit_code == 0
    output = json.loads(result.output)
    assert output == [
        {
            "doi": "10.1016/j.econmod.2026.107590",
            "status": "created",
            "item_key": "D0000001",
            "title": "Imported by DOI",
            "message": "Item created from DOI metadata.",
        }
    ]
    assert fake_client.items_by_key["D0000001"]["data"]["tags"] == [{"tag": "Added by AI Agent"}]


def test_item_add_doi_handles_exists_and_failure_in_batch(runner, monkeypatch):
    fake_client = FakeZoteroClient()
    fake_client.add_existing_item("EXIST001", "10.1000/existing", "Already Present")
    _patch_clients(monkeypatch, fake_client)

    def fake_fetch(doi):
        if doi == "10.1000/new":
            return _sample_csl_json(title="Fresh Item")
        raise ValueError("lookup failed")

    monkeypatch.setattr("pyzotero_cli.item_cmds.doi_utils.fetch_csl_json_for_doi", fake_fetch)

    result = runner.invoke(
        zot,
        ["items", "add-doi", "--check-duplicate", "10.1000/existing", "10.1000/new", "10.1000/fail"],
        env=DUMMY_ENV,
    )

    assert result.exit_code == 1
    output = json.loads(result.output)
    assert output[0] == {
        "doi": "10.1000/existing",
        "status": "exists",
        "item_key": "EXIST001",
        "title": "Already Present",
        "message": "Item with DOI already exists.",
    }
    assert output[1]["status"] == "created"
    assert output[1]["title"] == "Fresh Item"
    assert output[2]["status"] == "failed"
    assert output[2]["message"] == "lookup failed"


def test_item_add_doi_default_creates_without_duplicate_check(runner, monkeypatch):
    fake_client = FakeZoteroClient()
    fake_client.add_existing_item("EXIST001", "10.1000/existing", "Already Present")
    _patch_clients(monkeypatch, fake_client)
    monkeypatch.setattr(
        "pyzotero_cli.item_cmds.doi_utils.fetch_csl_json_for_doi",
        lambda doi: _sample_csl_json(title="Duplicate Allowed"),
    )

    result = runner.invoke(
        zot,
        ["items", "add-doi", "10.1000/existing"],
        env=DUMMY_ENV,
    )

    assert result.exit_code == 0
    output = json.loads(result.output)
    assert output[0]["status"] == "created"
    assert len(fake_client.items_by_key) == 2
    assert fake_client.items_by_key["D0000001"]["data"]["tags"] == [{"tag": "Added by AI Agent"}]


def test_item_add_doi_adds_created_item_to_collection(runner, monkeypatch):
    fake_client = FakeZoteroClient()
    _patch_clients(monkeypatch, fake_client)
    monkeypatch.setattr(
        "pyzotero_cli.item_cmds.doi_utils.fetch_csl_json_for_doi",
        lambda doi: _sample_csl_json(),
    )

    result = runner.invoke(
        zot,
        ["items", "add-doi", "--collection", "COLL1", "10.1000/new"],
        env=DUMMY_ENV,
    )

    assert result.exit_code == 0
    created_item = fake_client.items_by_key["D0000001"]
    assert created_item["data"]["collections"] == ["COLL1"]
    assert created_item["data"]["tags"] == [{"tag": "Added by AI Agent"}]


def test_item_add_doi_rejects_local_mode(runner, monkeypatch):
    fake_client = FakeZoteroClient()
    _patch_clients(monkeypatch, fake_client)

    result = runner.invoke(
        zot,
        ["--local", "items", "add-doi", "10.1000/new"],
        env=DUMMY_ENV,
    )

    assert result.exit_code == 2
    assert "not available with --local" in result.output


def test_item_add_doi_keys_and_table_output(runner, monkeypatch):
    fake_client = FakeZoteroClient()
    _patch_clients(monkeypatch, fake_client)
    monkeypatch.setattr(
        "pyzotero_cli.item_cmds.doi_utils.fetch_csl_json_for_doi",
        lambda doi: _sample_csl_json(),
    )

    keys_result = runner.invoke(
        zot,
        ["items", "add-doi", "--output", "keys", "10.1000/keys"],
        env=DUMMY_ENV,
    )
    assert keys_result.exit_code == 0
    assert keys_result.output.strip() == "D0000001"

    table_result = runner.invoke(
        zot,
        ["items", "add-doi", "--output", "table", "10.1000/table"],
        env=DUMMY_ENV,
    )
    assert table_result.exit_code == 0
    assert "DOI" in table_result.output
    assert "Status" in table_result.output
    assert "created" in table_result.output
