import json
import os
import re
from typing import Any
from datetime import datetime, timezone
from urllib import error, parse, request


DOI_CSL_ACCEPT_HEADER = "application/vnd.citationstyles.csl+json"
DOI_CACHE_FILE = os.path.join(os.path.expanduser("~"), ".config", "zotcli", "doi_cache.json")
DOI_LIBRARY_CATALOG = "DOI.org (AI Agent)"
DOI_URL_PREFIX_RE = re.compile(
    r"^(?:doi:\s*|https?://(?:dx\.)?doi\.org/)",
    re.IGNORECASE,
)
DOI_VALID_RE = re.compile(r"^10\.\S+/\S+$", re.IGNORECASE)
TAG_RE = re.compile(r"<[^>]+>")

CSL_TO_ZOTERO_ITEM_TYPE = {
    "article-journal": "journalArticle",
    "journal-article": "journalArticle",
    "paper-conference": "conferencePaper",
    "chapter": "bookSection",
    "book": "book",
    "edited-book": "book",
    "report": "report",
    "thesis": "thesis",
    "webpage": "webpage",
    "post-weblog": "webpage",
    "article-magazine": "magazineArticle",
    "article-newspaper": "newspaperArticle",
}

CONTAINER_TITLE_FIELD_MAP = {
    "journalArticle": "publicationTitle",
    "magazineArticle": "publicationTitle",
    "newspaperArticle": "publicationTitle",
    "bookSection": "bookTitle",
}


class DOIError(Exception):
    """Raised when DOI input or lookup fails."""


def clean_doi(raw_doi: str) -> str:
    """Return a bare DOI string while preserving the original case."""
    cleaned = parse.unquote(raw_doi or "").strip()
    cleaned = DOI_URL_PREFIX_RE.sub("", cleaned).strip()
    cleaned = cleaned.rstrip("/")

    if not cleaned or not DOI_VALID_RE.match(cleaned):
        raise DOIError(f"Invalid DOI: {raw_doi}")

    return cleaned


def normalize_doi(raw_doi: str) -> str:
    """Return a canonical lowercase bare DOI string for internal matching."""
    return clean_doi(raw_doi).lower()


def fetch_csl_json_for_doi(doi: str, timeout: int = 10) -> dict[str, Any]:
    """Fetch CSL JSON metadata for a DOI using DOI content negotiation."""
    url = f"https://doi.org/{parse.quote(doi, safe='/')}"
    req = request.Request(
        url,
        headers={
            "Accept": DOI_CSL_ACCEPT_HEADER,
            "User-Agent": "pyzotero-cli/doi-import",
        },
    )

    try:
        with request.urlopen(req, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
    except error.HTTPError as exc:
        raise DOIError(f"DOI lookup failed with HTTP {exc.code}") from exc
    except error.URLError as exc:
        raise DOIError(f"DOI lookup failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise DOIError("DOI lookup timed out") from exc

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise DOIError("DOI lookup returned invalid JSON") from exc

    if not isinstance(data, dict):
        raise DOIError("DOI lookup returned an unexpected payload")

    return data


def find_cached_item_by_doi(zot_client: Any, normalized_doi: str) -> dict[str, Any] | None:
    """Return a cached item for a DOI if the cache entry is still valid."""
    cache_key = _library_cache_key(zot_client)
    if not cache_key:
        return None

    cache = _load_doi_cache()
    item_key = cache.get(cache_key, {}).get(normalized_doi)
    if not item_key:
        return None

    try:
        item = zot_client.item(item_key)
        if isinstance(item, list):
            item = item[0] if item else None
        if not isinstance(item, dict):
            _remove_cached_doi(cache_key, normalized_doi)
            return None
        item_doi = item.get("data", {}).get("DOI")
        if isinstance(item_doi, str) and normalize_doi(item_doi) == normalized_doi:
            return item
    except Exception:
        pass

    _remove_cached_doi(cache_key, normalized_doi)
    return None


def cache_item_key_for_doi(zot_client: Any, normalized_doi: str, item_key: str | None) -> None:
    """Persist a DOI -> item key mapping for fast future duplicate checks."""
    cache_key = _library_cache_key(zot_client)
    if not cache_key or not item_key:
        return

    cache = _load_doi_cache()
    library_cache = cache.setdefault(cache_key, {})
    library_cache[normalized_doi] = item_key
    _save_doi_cache(cache)


def find_existing_item_by_doi(zot_client: Any, normalized_doi: str, timeout: float = 1.5, limit: int = 10) -> dict[str, Any] | None:
    """
    Best-effort duplicate lookup for a DOI.

    Uses a direct Zotero Web API request with a short timeout to avoid the slower
    default pyzotero search path blocking DOI imports for several seconds.
    Falls back to zot_client.items() when the client does not expose the fields
    needed to construct a direct API request, which keeps tests and mocks simple.
    """
    if not hasattr(zot_client, "library_id") or not hasattr(zot_client, "library_type"):
        candidate_items = zot_client.items(q=normalized_doi, qmode="everything", limit=limit)
        return _match_existing_item(candidate_items, normalized_doi)

    library_type = getattr(zot_client, "library_type", "")
    library_id = getattr(zot_client, "library_id", "")
    api_path_map = {
        "user": "users",
        "users": "users",
        "group": "groups",
        "groups": "groups",
    }
    api_path = api_path_map.get(library_type)
    if not api_path or not library_id:
        return None

    query = parse.urlencode(
        {
            "q": normalized_doi,
            "qmode": "everything",
            "limit": limit,
        }
    )
    url = f"https://api.zotero.org/{api_path}/{library_id}/items?{query}"
    headers = {"User-Agent": "pyzotero-cli/doi-import"}
    api_key = getattr(zot_client, "api_key", None)
    if api_key:
        headers["Zotero-API-Key"] = api_key

    req = request.Request(url, headers=headers)
    try:
        with request.urlopen(req, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
        candidate_items = json.loads(payload)
    except (TimeoutError, error.URLError, error.HTTPError, json.JSONDecodeError):
        return None

    return _match_existing_item(candidate_items, normalized_doi)


def map_csl_json_to_zotero_item(zot_client: Any, csl_json: dict[str, Any], doi: str) -> dict[str, Any]:
    """Map CSL JSON metadata into a Zotero item payload."""
    item_type = _determine_zotero_item_type(csl_json)
    template = zot_client.item_template(item_type)
    if not isinstance(template, dict):
        raise DOIError(f"Could not create Zotero template for item type '{item_type}'")

    full_title, short_title = _extract_titles(csl_json)
    if not full_title:
        raise DOIError("DOI metadata did not include a title")

    template["title"] = full_title
    template["DOI"] = doi
    if short_title and "shortTitle" in template:
        template["shortTitle"] = short_title
    if "libraryCatalog" in template:
        template["libraryCatalog"] = DOI_LIBRARY_CATALOG

    field_mappings = {
        "URL": "url",
        "language": "language",
        "volume": "volume",
        "issue": "issue",
        "page": "pages",
        "publisher": "publisher",
    }
    for csl_key, zotero_key in field_mappings.items():
        value = _first_string(csl_json.get(csl_key))
        if value and zotero_key in template:
            template[zotero_key] = value

    abstract_value = _sanitize_abstract(csl_json.get("abstract"))
    if abstract_value and "abstractNote" in template:
        template["abstractNote"] = abstract_value

    if item_type == "preprint":
        publisher = _first_string(csl_json.get("publisher"))
        if publisher and "repository" in template:
            template["repository"] = publisher

    if template.get("url") and "accessDate" in template:
        template["accessDate"] = _current_access_date()

    for csl_key in ("ISSN", "ISBN"):
        value = _first_string(csl_json.get(csl_key))
        if value and csl_key in template:
            template[csl_key] = value

    date_value = _format_csl_date(csl_json.get("issued"))
    if date_value and "date" in template:
        template["date"] = date_value

    container_title = _first_string(csl_json.get("container-title"))
    container_field = CONTAINER_TITLE_FIELD_MAP.get(item_type)
    if container_title and container_field and container_field in template:
        template[container_field] = container_title

    template["creators"] = _map_creators(zot_client, item_type, csl_json)

    return template


def _determine_zotero_item_type(csl_json: dict[str, Any]) -> str:
    csl_type = csl_json.get("type")
    publisher = _first_string(csl_json.get("publisher")).lower()
    url = _first_string(csl_json.get("URL")).lower()
    container_title = _first_string(csl_json.get("container-title"))

    if csl_type == "article" and (publisher == "arxiv" or "arxiv.org" in url):
        return "preprint"
    if csl_type == "article" and container_title:
        return "journalArticle"

    return CSL_TO_ZOTERO_ITEM_TYPE.get(csl_type, "document")


def _extract_titles(csl_json: dict[str, Any]) -> tuple[str, str]:
    title = _first_string(csl_json.get("title"))
    subtitle = _first_string(csl_json.get("subtitle"))
    explicit_short_title = _first_string(csl_json.get("short-title"))

    full_title = title
    if title and subtitle:
        full_title = f"{title}: {subtitle}"

    short_title = explicit_short_title
    if not short_title and title and subtitle:
        short_title = title
    if not short_title and title:
        short_title = _derive_short_title(title)

    return full_title, short_title


def _first_string(value: Any) -> str:
    if isinstance(value, str):
        return normalize_space(value)
    if isinstance(value, list):
        for entry in value:
            if isinstance(entry, str) and normalize_space(entry):
                return normalize_space(entry)
    return ""


def _current_access_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _derive_short_title(title: str) -> str:
    if ": " in title:
        return title.split(": ", 1)[0].strip()
    for delimiter in ("? ", "! ", "？", "！"):
        if delimiter in title:
            head = title.split(delimiter, 1)[0].strip()
            if delimiter in {"? ", "？"}:
                return f"{head}?"
            if delimiter in {"! ", "！"}:
                return f"{head}!"
    for delimiter in (" - ", " – ", " — "):
        if delimiter in title:
            head = title.split(delimiter, 1)[0].strip()
            return head
    return ""


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u00A0", " ")).strip()


def _sanitize_abstract(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = TAG_RE.sub(" ", value)
    return normalize_space(cleaned)


def _format_csl_date(issued_value: Any) -> str:
    if not isinstance(issued_value, dict):
        return ""

    date_parts = issued_value.get("date-parts")
    if not isinstance(date_parts, list) or not date_parts:
        return ""

    first_part = date_parts[0]
    if not isinstance(first_part, list) or not first_part:
        return ""

    cleaned_parts: list[str] = []
    for part in first_part[:3]:
        if not isinstance(part, int):
            break
        if len(cleaned_parts) == 0:
            cleaned_parts.append(f"{part:04d}")
        else:
            cleaned_parts.append(f"{part:02d}")
    return "-".join(cleaned_parts)


def _map_creators(zot_client: Any, item_type: str, csl_json: dict[str, Any]) -> list[dict[str, str]]:
    allowed_creator_types = _get_allowed_creator_types(zot_client, item_type)
    creators: list[dict[str, str]] = []
    for csl_role, creator_type in (
        ("author", "author"),
        ("editor", "editor"),
        ("translator", "translator"),
    ):
        if creator_type not in allowed_creator_types:
            continue
        role_entries = csl_json.get(csl_role, [])
        if not isinstance(role_entries, list):
            continue
        for person in role_entries:
            creator = _map_person_to_creator(person, creator_type)
            if creator:
                creators.append(creator)
    return creators


def _get_allowed_creator_types(zot_client: Any, item_type: str) -> set[str]:
    try:
        creator_types = zot_client.item_creator_types(itemtype=item_type)
    except Exception:
        return {"author", "editor", "translator"}

    allowed: set[str] = set()
    if isinstance(creator_types, list):
        for entry in creator_types:
            if isinstance(entry, dict):
                creator_type = entry.get("creatorType")
                if isinstance(creator_type, str) and creator_type:
                    allowed.add(creator_type)

    if not allowed:
        return {"author", "editor", "translator"}
    return allowed


def _map_person_to_creator(person: Any, creator_type: str) -> dict[str, str] | None:
    if not isinstance(person, dict):
        return None

    family_name = str(person.get("family") or "").strip()
    given_name = str(person.get("given") or "").strip()
    literal_name = str(person.get("literal") or "").strip()

    creator: dict[str, str] = {"creatorType": creator_type}
    if family_name or given_name:
        creator["lastName"] = family_name
        creator["firstName"] = given_name
        return creator
    if literal_name:
        creator["name"] = literal_name
        return creator
    return None


def _match_existing_item(candidate_items: Any, normalized_doi: str) -> dict[str, Any] | None:
    if not isinstance(candidate_items, list):
        return None

    for item in candidate_items:
        if not isinstance(item, dict):
            continue
        item_doi = item.get("data", {}).get("DOI")
        if not isinstance(item_doi, str):
            continue
        try:
            if normalize_doi(item_doi) == normalized_doi:
                return item
        except DOIError:
            continue
    return None


def _library_cache_key(zot_client: Any) -> str | None:
    library_id = getattr(zot_client, "library_id", None)
    library_type = getattr(zot_client, "library_type", None)
    if not library_id or not library_type:
        return None
    return f"{library_type}:{library_id}"


def _load_doi_cache() -> dict[str, dict[str, str]]:
    try:
        with open(DOI_CACHE_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        pass
    return {}


def _save_doi_cache(cache: dict[str, dict[str, str]]) -> None:
    try:
        os.makedirs(os.path.dirname(DOI_CACHE_FILE), exist_ok=True)
        with open(DOI_CACHE_FILE, "w", encoding="utf-8") as handle:
            json.dump(cache, handle, indent=2, ensure_ascii=False)
    except OSError:
        pass


def _remove_cached_doi(cache_key: str, normalized_doi: str) -> None:
    cache = _load_doi_cache()
    library_cache = cache.get(cache_key)
    if not isinstance(library_cache, dict):
        return
    if normalized_doi not in library_cache:
        return
    del library_cache[normalized_doi]
    if not library_cache:
        del cache[cache_key]
    _save_doi_cache(cache)
