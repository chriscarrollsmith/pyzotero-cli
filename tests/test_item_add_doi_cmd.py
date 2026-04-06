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


def test_item_add_doi_rejects_local_mode(runner, active_profile_with_real_credentials):
    result = runner.invoke(zot, ["--local", "items", "add-doi", STABLE_DOI])

    assert result.exit_code == 2
    assert "not available with --local" in result.output


def test_item_add_doi_keys_output_format(
    runner, active_profile_with_real_credentials, zot_instance, cleanup_doi_items
):
    result = runner.invoke(zot, ["items", "add-doi", "--output", "keys", STABLE_DOI])

    assert result.exit_code == 0
    item_key = result.output.strip()
    assert len(item_key) > 0
    cleanup_doi_items.append(item_key)


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
