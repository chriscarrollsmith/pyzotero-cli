import json
from urllib import error

import pytest

from pyzotero_cli import doi as doi_utils


class FakeResponse:
    def __init__(self, payload: str):
        self.payload = payload

    def read(self):
        return self.payload.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeZoteroClient:
    def item_template(self, item_type):
        return {
            "itemType": item_type,
            "title": "",
            "DOI": "",
            "url": "",
            "accessDate": "",
            "language": "",
            "libraryCatalog": "",
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
            "shortTitle": "",
            "creators": [],
            "collections": [],
        }

    def item_creator_types(self, itemtype):
        return [
            {"creatorType": "author"},
            {"creatorType": "editor"},
            {"creatorType": "translator"},
        ]


class FakeDirectLookupClient:
    library_id = "12345"
    library_type = "users"
    api_key = "secret"


def test_normalize_doi_accepts_common_input_forms():
    bare = doi_utils.normalize_doi("10.1016/j.econmod.2026.107590")
    assert bare == "10.1016/j.econmod.2026.107590"

    with_prefix = doi_utils.normalize_doi("doi:10.1016/J.ECONMOD.2026.107590")
    assert with_prefix == bare

    with_url = doi_utils.normalize_doi("https://doi.org/10.1016/J.ECONMOD.2026.107590")
    assert with_url == bare


def test_normalize_doi_rejects_invalid_values():
    with pytest.raises(doi_utils.DOIError):
        doi_utils.normalize_doi("not-a-doi")


def test_map_csl_json_to_zotero_item_maps_core_fields():
    client = FakeZoteroClient()
    csl_json = {
        "type": "article-journal",
        "title": "Testing DOI Imports",
        "subtitle": ["A Practical Guide"],
        "URL": "https://example.com/paper",
        "language": "en",
        "volume": "12",
        "issue": "3",
        "page": "10-20",
        "publisher": "Example Press",
        "ISSN": ["1234-5678"],
        "abstract": "Summary",
        "container-title": ["Journal of Testing"],
        "issued": {"date-parts": [[2026, 3, 30]]},
        "author": [{"family": "Smith", "given": "Ada"}],
        "editor": [{"literal": "Editorial Board"}],
        "translator": [{"family": "Jones", "given": "Robin"}],
    }

    item = doi_utils.map_csl_json_to_zotero_item(client, csl_json, "10.1016/j.econmod.2026.107590")

    assert item["itemType"] == "journalArticle"
    assert item["title"] == "Testing DOI Imports: A Practical Guide"
    assert item["shortTitle"] == "Testing DOI Imports"
    assert item["DOI"] == "10.1016/j.econmod.2026.107590"
    assert item["libraryCatalog"] == "DOI.org (AI Agent)"
    assert item["publicationTitle"] == "Journal of Testing"
    assert item["date"] == "2026-03-30"
    assert item["ISSN"] == "1234-5678"
    assert item["abstractNote"] == "Summary"
    assert item["accessDate"].endswith("Z")
    assert item["creators"] == [
        {"creatorType": "author", "lastName": "Smith", "firstName": "Ada"},
        {"creatorType": "editor", "name": "Editorial Board"},
        {"creatorType": "translator", "lastName": "Jones", "firstName": "Robin"},
    ]


def test_map_csl_json_to_zotero_item_maps_edited_book_to_book():
    client = FakeZoteroClient()
    csl_json = {
        "type": "edited-book",
        "title": "Edited Volume",
        "publisher": "Example Press",
        "issued": {"date-parts": [[2025, 3, 28]]},
        "author": [{"family": "He", "given": "Jiani"}],
    }

    item = doi_utils.map_csl_json_to_zotero_item(client, csl_json, "10.1515/9789048555864")

    assert item["itemType"] == "book"
    assert item["title"] == "Edited Volume"
    assert item["date"] == "2025-03-28"
    assert item["libraryCatalog"] == "DOI.org (AI Agent)"


def test_map_csl_json_to_zotero_item_maps_journal_article_to_journal_article():
    client = FakeZoteroClient()
    csl_json = {
        "type": "journal-article",
        "title": "Journal Article Title",
        "container-title": "Habitat International",
        "volume": "171",
        "page": "103784",
        "issued": {"date-parts": [[2026, 5]]},
        "author": [{"family": "Yang", "given": "Linyu"}],
    }

    item = doi_utils.map_csl_json_to_zotero_item(client, csl_json, "10.1016/j.habitatint.2026.103784")

    assert item["itemType"] == "journalArticle"
    assert item["publicationTitle"] == "Habitat International"
    assert item["volume"] == "171"
    assert item["pages"] == "103784"
    assert item["date"] == "2026-05"
    assert item["shortTitle"] == ""


def test_map_csl_json_maps_generic_article_with_container_title_to_journal_article():
    client = FakeZoteroClient()
    csl_json = {
        "type": "article",
        "title": "Generic Article Title",
        "container-title": "Comparative Studies in Society and History",
        "page": "1-25",
        "issued": {"date-parts": [[2026, 3, 25]]},
        "author": [{"family": "Rippa", "given": "Alessandro"}],
    }

    item = doi_utils.map_csl_json_to_zotero_item(client, csl_json, "10.1017/S0010417526100462")

    assert item["itemType"] == "journalArticle"
    assert item["publicationTitle"] == "Comparative Studies in Society and History"
    assert item["pages"] == "1-25"


def test_map_csl_json_uses_explicit_short_title_when_present():
    client = FakeZoteroClient()
    csl_json = {
        "type": "book",
        "title": "Long Form Title",
        "subtitle": ["Subtitle"],
        "short-title": ["Short Form"],
    }

    item = doi_utils.map_csl_json_to_zotero_item(client, csl_json, "10.1000/test")

    assert item["title"] == "Long Form Title: Subtitle"
    assert item["shortTitle"] == "Short Form"


def test_map_csl_json_derives_short_title_from_title_delimiter():
    client = FakeZoteroClient()
    csl_json = {
        "type": "journal-article",
        "title": "When is a Frontier? Nostalgia and Aspirations at China's Borderlands",
    }

    item = doi_utils.map_csl_json_to_zotero_item(client, csl_json, "10.1000/test")

    assert item["shortTitle"] == "When is a Frontier?"


def test_map_csl_json_derives_short_title_from_exclamation():
    client = FakeZoteroClient()
    csl_json = {
        "type": "journal-article",
        "title": "Amazing Discovery! A follow-up explanation",
    }

    item = doi_utils.map_csl_json_to_zotero_item(client, csl_json, "10.1000/test")

    assert item["shortTitle"] == "Amazing Discovery!"


def test_map_csl_json_maps_arxiv_article_to_preprint():
    client = FakeZoteroClient()
    csl_json = {
        "type": "article",
        "title": "AI Can Learn Scientific Taste",
        "publisher": "arXiv",
        "URL": "https://arxiv.org/abs/2603.14473",
        "issued": {"date-parts": [[2026]]},
        "author": [{"family": "Tong", "given": "Jingqi"}],
    }

    item = doi_utils.map_csl_json_to_zotero_item(client, csl_json, "10.48550/arXiv.2603.14473")

    assert item["itemType"] == "preprint"
    assert item["title"] == "AI Can Learn Scientific Taste"
    assert item["libraryCatalog"] == "DOI.org (AI Agent)"
    assert item["publisher"] == "arXiv" or item.get("repository") == "arXiv"


def test_map_csl_json_sanitizes_abstract_markup_and_spaces():
    client = FakeZoteroClient()
    csl_json = {
        "type": "article",
        "title": "Markup Test",
        "container-title": "Test Journal",
        "abstract": "<jats:title>Abstract</jats:title>\n<jats:p>Hello\u00A0world.</jats:p>",
    }

    item = doi_utils.map_csl_json_to_zotero_item(client, csl_json, "10.1000/test")

    assert item["abstractNote"] == "Abstract Hello world."


def test_fetch_csl_json_for_doi_returns_json(monkeypatch):
    monkeypatch.setattr(
        doi_utils.request,
        "urlopen",
        lambda req, timeout=10: FakeResponse('{"title":"ok"}'),
    )

    data = doi_utils.fetch_csl_json_for_doi("10.1000/test")
    assert data == {"title": "ok"}


def test_fetch_csl_json_for_doi_handles_http_errors(monkeypatch):
    def raise_http_error(req, timeout=10):
        raise error.HTTPError(req.full_url, 404, "Not Found", hdrs=None, fp=None)

    monkeypatch.setattr(doi_utils.request, "urlopen", raise_http_error)

    with pytest.raises(doi_utils.DOIError, match="HTTP 404"):
        doi_utils.fetch_csl_json_for_doi("10.1000/test")


def test_fetch_csl_json_for_doi_handles_invalid_json(monkeypatch):
    monkeypatch.setattr(
        doi_utils.request,
        "urlopen",
        lambda req, timeout=10: FakeResponse("not-json"),
    )

    with pytest.raises(doi_utils.DOIError, match="invalid JSON"):
        doi_utils.fetch_csl_json_for_doi("10.1000/test")


def test_find_existing_item_by_doi_uses_direct_lookup(monkeypatch):
    payload = json.dumps(
        [
            {
                "key": "ABCD1234",
                "data": {"DOI": "10.1515/9789048555864", "title": "Title"},
            }
        ]
    )
    captured = {}

    def fake_urlopen(req, timeout=1.5):
        captured["url"] = req.full_url
        captured["headers"] = dict(req.header_items())
        return FakeResponse(payload)

    monkeypatch.setattr(doi_utils.request, "urlopen", fake_urlopen)

    item = doi_utils.find_existing_item_by_doi(FakeDirectLookupClient(), "10.1515/9789048555864")

    assert item["key"] == "ABCD1234"
    assert "/users/12345/items" in captured["url"]
    assert any(key.lower() == "zotero-api-key" for key in captured["headers"])
