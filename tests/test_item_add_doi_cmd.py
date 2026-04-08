import json
import uuid
import pytest

from pyzotero_cli.zot_cli import zot

pytestmark = pytest.mark.usefixtures("isolated_config")

# A stable, well-known open-access DOI used across most tests.
STABLE_DOI = "10.7717/peerj.4375"

# A second DOI used when two distinct DOIs are needed in the same test,
# e.g. to pre-populate the library with an "already-exists" entry.
EXISTING_DOI = "10.1371/journal.pcbi.1003149"


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def cleanup_doi_items(zot_instance):
    """Collects item keys created during a test and removes them after."""
    created_keys = []
    yield created_keys
    for key in created_keys:
        try:
            zot_instance.delete_item(zot_instance.item(key))
        except Exception:
            pass


@pytest.fixture(scope="function")
def ensure_stable_doi_absent(zot_instance):
    """Delete any pre-existing STABLE_DOI items so duplicate-check tests start clean."""
    def _purge():
        items = zot_instance.items(q=STABLE_DOI, qmode="everything", limit=50)
        for item in items:
            if item.get("data", {}).get("DOI", "").lower() == STABLE_DOI.lower():
                try:
                    zot_instance.delete_item(item)
                except Exception:
                    pass
    _purge()
    yield
    _purge()


@pytest.fixture(scope="function")
def pre_existing_doi_item(zot_instance):
    """
    Creates a Zotero item with EXISTING_DOI directly via the API to simulate
    a pre-existing entry the duplicate-check tests can detect.
    """
    template = zot_instance.item_template("journalArticle")
    template["title"] = "Pre-existing DOI Test Item"
    template["DOI"] = EXISTING_DOI
    resp = zot_instance.create_items([template])
    assert resp.get("success"), f"Failed to create pre-existing item: {resp}"
    item_key = resp["success"]["0"]
    yield {"key": item_key, "doi": EXISTING_DOI}
    try:
        zot_instance.delete_item(zot_instance.item(item_key))
    except Exception:
        pass


@pytest.fixture(scope="function")
def temp_collection(runner, active_profile_with_real_credentials):
    """Creates a temporary Zotero collection and removes it after the test."""
    name = f"pytest_doi_col_{uuid.uuid4().hex[:8]}"
    create_result = runner.invoke(zot, ["collections", "create", "--name", name])
    assert create_result.exit_code == 0, f"Collection create failed: {create_result.output}"
    collection_key = json.loads(create_result.output)["success"]["0"]
    yield collection_key
    runner.invoke(zot, ["collections", "delete", collection_key, "--force"])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.live
def test_item_add_doi_creates_item(
    runner, active_profile_with_real_credentials, zot_instance, cleanup_doi_items
):
    result = runner.invoke(zot, ["items", "add-doi", STABLE_DOI])

    assert result.exit_code == 0
    output = json.loads(result.output)
    assert len(output) == 1
    assert output[0]["status"] == "created"
    assert output[0]["doi"] == STABLE_DOI

    item_key = output[0]["item_key"]
    cleanup_doi_items.append(item_key)

    item = zot_instance.item(item_key)
    assert item["data"]["DOI"].lower() == STABLE_DOI.lower()
    tags = [t["tag"] for t in item["data"].get("tags", [])]
    assert "Added by AI Agent" in tags


@pytest.mark.live
def test_item_add_doi_preserves_input_case_in_output_and_storage(
    runner, active_profile_with_real_credentials, zot_instance, cleanup_doi_items
):
    """URL-form input with an uppercased DOI path is stripped and case is preserved."""
    uppercased_url = "https://doi.org/" + STABLE_DOI.upper()

    result = runner.invoke(zot, ["items", "add-doi", uppercased_url])

    assert result.exit_code == 0
    output = json.loads(result.output)
    assert output[0]["doi"] == STABLE_DOI.upper()

    item_key = output[0]["item_key"]
    cleanup_doi_items.append(item_key)

    item = zot_instance.item(item_key)
    assert item["data"]["DOI"] == STABLE_DOI.upper()


@pytest.mark.live
def test_item_add_doi_handles_exists_and_failure_in_batch(
    runner,
    active_profile_with_real_credentials,
    zot_instance,
    cleanup_doi_items,
    ensure_stable_doi_absent,
    pre_existing_doi_item,
):
    result = runner.invoke(
        zot,
        [
            "items", "add-doi", "--check-duplicate",
            EXISTING_DOI,   # already in library
            STABLE_DOI,     # new item
            "not-a-doi",    # invalid — fails at clean_doi before any network call
        ],
    )

    assert result.exit_code == 1
    output = json.loads(result.output)

    assert output[0]["doi"] == EXISTING_DOI
    assert output[0]["status"] == "exists"
    assert output[0]["item_key"] == pre_existing_doi_item["key"]

    assert output[1]["status"] == "created"
    cleanup_doi_items.append(output[1]["item_key"])

    assert output[2]["doi"] == "not-a-doi"
    assert output[2]["status"] == "failed"


@pytest.mark.live
def test_item_add_doi_default_creates_without_duplicate_check(
    runner,
    active_profile_with_real_credentials,
    zot_instance,
    cleanup_doi_items,
    pre_existing_doi_item,
):
    """Without --check-duplicate a DOI that already exists is imported again."""
    result = runner.invoke(zot, ["items", "add-doi", EXISTING_DOI])

    assert result.exit_code == 0
    output = json.loads(result.output)
    assert output[0]["status"] == "created"

    new_key = output[0]["item_key"]
    cleanup_doi_items.append(new_key)

    assert new_key != pre_existing_doi_item["key"]
    # Both the pre-existing item and the newly created duplicate should be present.
    zot_instance.item(new_key)
    zot_instance.item(pre_existing_doi_item["key"])


@pytest.mark.live
def test_item_add_doi_adds_created_item_to_collection(
    runner,
    active_profile_with_real_credentials,
    zot_instance,
    cleanup_doi_items,
    temp_collection,
):
    result = runner.invoke(
        zot, ["items", "add-doi", "--collection", temp_collection, STABLE_DOI]
    )

    assert result.exit_code == 0
    output = json.loads(result.output)
    assert output[0]["status"] == "created"

    item_key = output[0]["item_key"]
    cleanup_doi_items.append(item_key)

    item = zot_instance.item(item_key)
    assert temp_collection in item["data"]["collections"]
    tags = [t["tag"] for t in item["data"].get("tags", [])]
    assert "Added by AI Agent" in tags


@pytest.mark.live
def test_item_add_doi_rejects_local_mode(runner, active_profile_with_real_credentials):
    result = runner.invoke(zot, ["--local", "items", "add-doi", STABLE_DOI])

    assert result.exit_code == 2
    assert "not available with --local" in result.output


@pytest.mark.live
def test_item_add_doi_keys_output_format(
    runner, active_profile_with_real_credentials, zot_instance, cleanup_doi_items
):
    result = runner.invoke(zot, ["items", "add-doi", "--output", "keys", STABLE_DOI])

    assert result.exit_code == 0
    item_key = result.output.strip()
    assert len(item_key) > 0
    cleanup_doi_items.append(item_key)


@pytest.mark.live
def test_item_add_doi_table_output_format(
    runner, active_profile_with_real_credentials, zot_instance, cleanup_doi_items
):
    result = runner.invoke(zot, ["items", "add-doi", "--output", "table", STABLE_DOI])

    assert result.exit_code == 0
    assert "DOI" in result.output
    assert "Status" in result.output
    assert "Error" in result.output
    assert "created" in result.output

    # No item key in table output; find the created item to register for cleanup.
    matching = zot_instance.items(q=STABLE_DOI, qmode="everything", limit=10)
    for it in matching:
        if it.get("data", {}).get("DOI", "").lower() == STABLE_DOI.lower():
            cleanup_doi_items.append(it["key"])
            break


# ── Mock tests (no API credentials required) ─────────────────────────────

from unittest.mock import patch as _mock_patch

MOCK_CSL_JSON = {
    "type": "article-journal",
    "title": "Mock DOI Article",
    "container-title": ["Journal of Mock Tests"],
    "issued": {"date-parts": [[2026, 1, 15]]},
    "author": [{"family": "Mock", "given": "Author"}],
}


def test_mock_add_doi_single(runner, mock_active_profile, mock_zotero_patched):
    """Test items add-doi creates item from DOI."""
    with _mock_patch("pyzotero_cli.item_cmds.doi_utils.fetch_csl_json_for_doi", return_value=MOCK_CSL_JSON):
        result = runner.invoke(zot, ['items', 'add-doi', '10.1000/mock.test'])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["status"] == "created"
    assert data[0]["item_key"] is not None


def test_mock_add_doi_multiple(runner, mock_active_profile, mock_zotero_patched):
    """Test items add-doi with multiple DOIs."""
    with _mock_patch("pyzotero_cli.item_cmds.doi_utils.fetch_csl_json_for_doi", return_value=MOCK_CSL_JSON):
        result = runner.invoke(zot, ['items', 'add-doi', '10.1000/mock.one', '10.1000/mock.two'])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 2
    assert all(r["status"] == "created" for r in data)


def test_mock_add_doi_keys_output(runner, mock_active_profile, mock_zotero_patched):
    """Test items add-doi --output keys."""
    with _mock_patch("pyzotero_cli.item_cmds.doi_utils.fetch_csl_json_for_doi", return_value=MOCK_CSL_JSON):
        result = runner.invoke(zot, ['items', 'add-doi', '10.1000/mock.test', '--output', 'keys'])
    assert result.exit_code == 0
    lines = result.output.strip().split('\n')
    assert len(lines) >= 1
    assert lines[0].startswith("MOCK")


def test_mock_add_doi_table_output(runner, mock_active_profile, mock_zotero_patched):
    """Test items add-doi --output table."""
    with _mock_patch("pyzotero_cli.item_cmds.doi_utils.fetch_csl_json_for_doi", return_value=MOCK_CSL_JSON):
        result = runner.invoke(zot, ['items', 'add-doi', '10.1000/mock.test', '--output', 'table'])
    assert result.exit_code == 0
    assert "created" in result.output


def test_mock_add_doi_local_rejected(runner, mock_active_profile, mock_zotero_patched):
    """Test items add-doi rejects --local mode."""
    result = runner.invoke(zot, ['--local', 'items', 'add-doi', '10.1000/mock.test'])
    assert result.exit_code != 0
    assert "not available with --local" in result.output


def test_mock_add_doi_with_collection(runner, mock_active_profile, mock_zotero_patched):
    """Test items add-doi --collection assigns to collection."""
    with _mock_patch("pyzotero_cli.item_cmds.doi_utils.fetch_csl_json_for_doi", return_value=MOCK_CSL_JSON):
        result = runner.invoke(zot, ['items', 'add-doi', '10.1000/mock.test', '--collection', 'N7W92H48'])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data[0]["status"] == "created"
