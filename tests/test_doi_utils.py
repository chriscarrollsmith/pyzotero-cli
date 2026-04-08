import pytest

from pyzotero_cli import doi as doi_utils

pytestmark = pytest.mark.usefixtures("isolated_config")

# A stable, well-known open-access DOI used for live network tests.
STABLE_DOI = "10.7717/peerj.4375"


# ---------------------------------------------------------------------------
# Pure function tests — no API calls
# ---------------------------------------------------------------------------

def test_normalize_doi_accepts_common_input_forms():
    bare = doi_utils.normalize_doi("10.1016/j.econmod.2026.107590")
    assert bare == "10.1016/j.econmod.2026.107590"

    with_prefix = doi_utils.normalize_doi("doi:10.1016/J.ECONMOD.2026.107590")
    assert with_prefix == bare

    with_url = doi_utils.normalize_doi("https://doi.org/10.1016/J.ECONMOD.2026.107590")
    assert with_url == bare


def test_clean_doi_preserves_input_case():
    cleaned = doi_utils.clean_doi("https://doi.org/10.1016/J.ECONMOD.2026.107590")
    assert cleaned == "10.1016/J.ECONMOD.2026.107590"


def test_normalize_doi_rejects_invalid_values():
    with pytest.raises(doi_utils.DOIError):
        doi_utils.normalize_doi("not-a-doi")


# ---------------------------------------------------------------------------
# CSL-JSON → Zotero mapping tests (use real Zotero API for item templates)
# ---------------------------------------------------------------------------

@pytest.mark.live
def test_map_csl_json_to_zotero_item_maps_core_fields(zot_instance):
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

    item = doi_utils.map_csl_json_to_zotero_item(zot_instance, csl_json, "10.1016/j.econmod.2026.107590")

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


@pytest.mark.live
def test_map_csl_json_to_zotero_item_maps_edited_book_to_book(zot_instance):
    csl_json = {
        "type": "edited-book",
        "title": "Edited Volume",
        "publisher": "Example Press",
        "issued": {"date-parts": [[2025, 3, 28]]},
        "author": [{"family": "He", "given": "Jiani"}],
    }

    item = doi_utils.map_csl_json_to_zotero_item(zot_instance, csl_json, "10.1515/9789048555864")

    assert item["itemType"] == "book"
    assert item["title"] == "Edited Volume"
    assert item["date"] == "2025-03-28"
    assert item["libraryCatalog"] == "DOI.org (AI Agent)"


@pytest.mark.live
def test_map_csl_json_to_zotero_item_maps_journal_article_to_journal_article(zot_instance):
    csl_json = {
        "type": "journal-article",
        "title": "Journal Article Title",
        "container-title": "Habitat International",
        "volume": "171",
        "page": "103784",
        "issued": {"date-parts": [[2026, 5]]},
        "author": [{"family": "Yang", "given": "Linyu"}],
    }

    item = doi_utils.map_csl_json_to_zotero_item(zot_instance, csl_json, "10.1016/j.habitatint.2026.103784")

    assert item["itemType"] == "journalArticle"
    assert item["publicationTitle"] == "Habitat International"
    assert item["volume"] == "171"
    assert item["pages"] == "103784"
    assert item["date"] == "2026-05"
    assert item["shortTitle"] == ""


@pytest.mark.live
def test_map_csl_json_maps_generic_article_with_container_title_to_journal_article(zot_instance):
    csl_json = {
        "type": "article",
        "title": "Generic Article Title",
        "container-title": "Comparative Studies in Society and History",
        "page": "1-25",
        "issued": {"date-parts": [[2026, 3, 25]]},
        "author": [{"family": "Rippa", "given": "Alessandro"}],
    }

    item = doi_utils.map_csl_json_to_zotero_item(zot_instance, csl_json, "10.1017/S0010417526100462")

    assert item["itemType"] == "journalArticle"
    assert item["publicationTitle"] == "Comparative Studies in Society and History"
    assert item["pages"] == "1-25"


@pytest.mark.live
def test_map_csl_json_uses_explicit_short_title_when_present(zot_instance):
    csl_json = {
        "type": "book",
        "title": "Long Form Title",
        "subtitle": ["Subtitle"],
        "short-title": ["Short Form"],
    }

    item = doi_utils.map_csl_json_to_zotero_item(zot_instance, csl_json, "10.1000/test")

    assert item["title"] == "Long Form Title: Subtitle"
    assert item["shortTitle"] == "Short Form"


@pytest.mark.live
def test_map_csl_json_derives_short_title_from_title_delimiter(zot_instance):
    csl_json = {
        "type": "journal-article",
        "title": "When is a Frontier? Nostalgia and Aspirations at China's Borderlands",
    }

    item = doi_utils.map_csl_json_to_zotero_item(zot_instance, csl_json, "10.1000/test")

    assert item["shortTitle"] == "When is a Frontier?"


@pytest.mark.live
def test_map_csl_json_derives_short_title_from_exclamation(zot_instance):
    csl_json = {
        "type": "journal-article",
        "title": "Amazing Discovery! A follow-up explanation",
    }

    item = doi_utils.map_csl_json_to_zotero_item(zot_instance, csl_json, "10.1000/test")

    assert item["shortTitle"] == "Amazing Discovery!"


@pytest.mark.live
def test_map_csl_json_maps_arxiv_article_to_preprint(zot_instance):
    csl_json = {
        "type": "article",
        "title": "AI Can Learn Scientific Taste",
        "publisher": "arXiv",
        "URL": "https://arxiv.org/abs/2603.14473",
        "issued": {"date-parts": [[2026]]},
        "author": [{"family": "Tong", "given": "Jingqi"}],
    }

    item = doi_utils.map_csl_json_to_zotero_item(zot_instance, csl_json, "10.48550/arXiv.2603.14473")

    assert item["itemType"] == "preprint"
    assert item["title"] == "AI Can Learn Scientific Taste"
    assert item["libraryCatalog"] == "DOI.org (AI Agent)"
    assert item.get("repository") == "arXiv"


@pytest.mark.live
def test_map_csl_json_sanitizes_abstract_markup_and_spaces(zot_instance):
    csl_json = {
        "type": "article",
        "title": "Markup Test",
        "container-title": "Test Journal",
        "abstract": "<jats:title>Abstract</jats:title>\n<jats:p>Hello\u00A0world.</jats:p>",
    }

    item = doi_utils.map_csl_json_to_zotero_item(zot_instance, csl_json, "10.1000/test")

    assert item["abstractNote"] == "Abstract Hello world."


# ---------------------------------------------------------------------------
# Live doi.org network tests
# ---------------------------------------------------------------------------

@pytest.mark.live
def test_fetch_csl_json_for_doi_returns_json():
    """Hits the real doi.org content-negotiation endpoint."""
    data = doi_utils.fetch_csl_json_for_doi(STABLE_DOI)
    assert isinstance(data, dict)
    assert "title" in data


@pytest.mark.live
def test_fetch_csl_json_for_doi_handles_http_errors():
    """A non-existent DOI path should surface as a DOIError wrapping an HTTP error."""
    with pytest.raises(doi_utils.DOIError, match="HTTP"):
        doi_utils.fetch_csl_json_for_doi("10.1000/doesnotexist.xyz.fake.abc.123")


# ---------------------------------------------------------------------------
# Duplicate-lookup test (real Zotero API)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def temp_doi_item(zot_instance):
    """Creates a Zotero item with a known DOI and removes it after the test."""
    template = zot_instance.item_template("journalArticle")
    template["title"] = "Temporary DOI Lookup Test Item"
    template["DOI"] = STABLE_DOI
    resp = zot_instance.create_items([template])
    assert resp.get("success"), f"Failed to create temp DOI item: {resp}"
    item_key = resp["success"]["0"]
    yield {"key": item_key, "doi": STABLE_DOI}
    try:
        zot_instance.delete_item(zot_instance.item(item_key))
    except Exception:
        pass


@pytest.mark.live
def test_find_existing_item_by_doi_uses_direct_lookup(zot_instance, temp_doi_item):
    """find_existing_item_by_doi locates an item that exists in the real library."""
    item = doi_utils.find_existing_item_by_doi(zot_instance, temp_doi_item["doi"])
    assert item is not None
    assert item["key"] == temp_doi_item["key"]


# ── Mock tests (no API credentials required) ─────────────────────────────

def test_mock_map_csl_json_core_fields(mock_zot_instance):
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
    }
    item = doi_utils.map_csl_json_to_zotero_item(mock_zot_instance, csl_json, "10.1016/j.test.2026")
    assert item["itemType"] == "journalArticle"
    assert item["title"] == "Testing DOI Imports: A Practical Guide"
    assert item["shortTitle"] == "Testing DOI Imports"
    assert item["DOI"] == "10.1016/j.test.2026"
    assert item["publicationTitle"] == "Journal of Testing"
    assert item["ISSN"] == "1234-5678"
    assert item["abstractNote"] == "Summary"
    assert item["date"] == "2026-03-30"


def test_mock_map_csl_json_edited_book_to_book(mock_zot_instance):
    csl_json = {
        "type": "edited-book",
        "title": "Edited Volume",
        "publisher": "Example Press",
        "issued": {"date-parts": [[2025, 3, 28]]},
        "author": [{"family": "He", "given": "Jiani"}],
    }
    item = doi_utils.map_csl_json_to_zotero_item(mock_zot_instance, csl_json, "10.1515/test")
    assert item["itemType"] == "book"
    assert item["title"] == "Edited Volume"
    assert item["date"] == "2025-03-28"


def test_mock_map_csl_json_journal_article(mock_zot_instance):
    csl_json = {
        "type": "journal-article",
        "title": "Journal Article Title",
        "container-title": "Test Journal",
        "volume": "171",
        "page": "103784",
        "issued": {"date-parts": [[2026, 5]]},
        "author": [{"family": "Yang", "given": "Linyu"}],
    }
    item = doi_utils.map_csl_json_to_zotero_item(mock_zot_instance, csl_json, "10.1016/test")
    assert item["itemType"] == "journalArticle"
    assert item["publicationTitle"] == "Test Journal"
    assert item["volume"] == "171"
    assert item["pages"] == "103784"
    assert item["date"] == "2026-05"


def test_mock_map_csl_json_generic_article_to_journal(mock_zot_instance):
    csl_json = {
        "type": "article",
        "title": "Generic Article",
        "container-title": "Some Journal",
        "page": "1-25",
        "issued": {"date-parts": [[2026, 3, 25]]},
    }
    item = doi_utils.map_csl_json_to_zotero_item(mock_zot_instance, csl_json, "10.1017/test")
    assert item["itemType"] == "journalArticle"
    assert item["publicationTitle"] == "Some Journal"


def test_mock_map_csl_json_short_title_from_delimiter(mock_zot_instance):
    csl_json = {
        "type": "journal-article",
        "title": "When is a Frontier? Nostalgia and Aspirations",
    }
    item = doi_utils.map_csl_json_to_zotero_item(mock_zot_instance, csl_json, "10.1000/test")
    assert item["shortTitle"] == "When is a Frontier?"


def test_mock_map_csl_json_explicit_short_title(mock_zot_instance):
    csl_json = {
        "type": "book",
        "title": "Long Form Title",
        "subtitle": ["Subtitle"],
        "short-title": ["Short Form"],
    }
    item = doi_utils.map_csl_json_to_zotero_item(mock_zot_instance, csl_json, "10.1000/test")
    assert item["title"] == "Long Form Title: Subtitle"
    assert item["shortTitle"] == "Short Form"


def test_mock_map_csl_json_arxiv_to_preprint(mock_zot_instance):
    csl_json = {
        "type": "article",
        "title": "AI Can Learn Scientific Taste",
        "publisher": "arXiv",
        "URL": "https://arxiv.org/abs/2603.14473",
        "issued": {"date-parts": [[2026]]},
        "author": [{"family": "Tong", "given": "Jingqi"}],
    }
    item = doi_utils.map_csl_json_to_zotero_item(mock_zot_instance, csl_json, "10.48550/arXiv.2603.14473")
    assert item["itemType"] == "preprint"
    assert item.get("repository") == "arXiv"


def test_mock_map_csl_json_sanitizes_abstract(mock_zot_instance):
    csl_json = {
        "type": "article",
        "title": "Markup Test",
        "container-title": "Test Journal",
        "abstract": "<jats:title>Abstract</jats:title>\n<jats:p>Hello\u00A0world.</jats:p>",
    }
    item = doi_utils.map_csl_json_to_zotero_item(mock_zot_instance, csl_json, "10.1000/test")
    assert item["abstractNote"] == "Abstract Hello world."
