"""Per source normalizers.

Each raw source (src/ingestion/sources/*.py) produces a payload dict
with its own shape. The functions below map each of those shapes
into the common NormalizedRecord schema (src/processing/schema.py)
so the rest of the pipeline (S3 processed zone, DynamoDB, chunking
and embedding) can treat every source identically.

business_gov_au, ato, and fair_work_mapd are still stub ingesters
(their fetch() raises NotImplementedError as of this writing), so
their normalizers below are written defensively against the payload
shape described in each ingester's module docstring/TODO rather than
against a confirmed real payload. They fall back to None for any
field that cannot be found under any of the candidate keys checked,
which keeps this normalization layer decoupled from the exact key
names that ingester ends up using: once that scraper is implemented
with a specific payload shape, only the candidate key lists here
(or the source's own dict) may need a follow-up tweak, not the
overall contract.
"""

from typing import Any

from src.processing.schema import NormalizedRecord, make_record_id


def _first(payload: dict[str, Any], *keys: str) -> Any:
    """Return the first present, truthy value for any of `keys`."""
    for key in keys:
        value = payload.get(key)
        if value:
            return value
    return None


def normalize_grantconnect_record(payload: dict[str, Any], fetched_at: str | None = None) -> NormalizedRecord:
    """Normalize a GrantConnect (grants.gov.au) detail payload.

    Raw shape, per src/ingestion/sources/grantconnect.py's
    _fetch_detail: url, title, description, agency, category,
    closing_date, estimated_value, raw_fields (a dict of every
    labeled field found on the detail page, keyed by lowercased
    label).
    """
    raw_fields = payload.get("raw_fields") or {}
    url = payload.get("url")

    return NormalizedRecord(
        record_id=make_record_id("grantconnect", url),
        source="grantconnect",
        title=payload.get("title"),
        description=payload.get("description"),
        eligibility=raw_fields.get("eligibility") or raw_fields.get("eligible applicants"),
        amount=payload.get("estimated_value"),
        deadline=payload.get("closing_date"),
        category=payload.get("category"),
        state_or_territory=raw_fields.get("location") or raw_fields.get("state"),
        url=url,
        ingested_at=fetched_at,
        raw=payload,
    )


def normalize_data_gov_au_record(payload: dict[str, Any], fetched_at: str | None = None) -> NormalizedRecord:
    """Normalize a data.gov.au CKAN package_search result.

    Raw shape: a CKAN package dict, e.g. id, name, title, notes
    (CKAN's field for a dataset's description), organization (a
    dict with a "title"), tags (a list of dicts with "name"), and
    resources. There is no grant specific eligibility/amount/deadline
    concept for a dataset, so those stay None.
    """
    package_id = payload.get("id")
    package_name = payload.get("name")
    url = f"https://data.gov.au/dataset/{package_name}" if package_name else None

    organization = payload.get("organization") or {}
    tags = payload.get("tags") or []
    category = tags[0].get("name") if tags and isinstance(tags[0], dict) else None

    return NormalizedRecord(
        record_id=make_record_id("data_gov_au", package_id or url),
        source="data_gov_au",
        title=payload.get("title"),
        description=payload.get("notes"),
        eligibility=None,
        amount=None,
        deadline=None,
        category=category,
        state_or_territory=organization.get("title") if isinstance(organization, dict) else None,
        url=url,
        ingested_at=fetched_at,
        raw=payload,
    )


def normalize_business_gov_au_record(payload: dict[str, Any], fetched_at: str | None = None) -> NormalizedRecord:
    """Normalize a business.gov.au grants/programs listing payload.

    business_gov_au.py's fetch() is still a stub (TODO: scrape
    business.gov.au/grants-and-programs, following detail pages for
    eligibility and deadline). This mirrors the field names its
    module docstring calls out, with a few likely alternate keys
    checked defensively since the real scraper has not been written
    yet.
    """
    url = _first(payload, "url", "link")

    return NormalizedRecord(
        record_id=make_record_id("business_gov_au", url),
        source="business_gov_au",
        title=payload.get("title"),
        description=_first(payload, "description", "summary"),
        eligibility=_first(payload, "eligibility", "who_can_apply"),
        amount=_first(payload, "amount", "funding_amount", "estimated_value"),
        deadline=_first(payload, "deadline", "closing_date"),
        category=payload.get("category"),
        state_or_territory=_first(payload, "state_or_territory", "state", "location"),
        url=url,
        ingested_at=fetched_at,
        raw=payload,
    )


def normalize_ato_record(payload: dict[str, Any], fetched_at: str | None = None) -> NormalizedRecord:
    """Normalize an ATO small business guidance payload.

    ato.py's fetch() is still a stub (TODO: scrape the small business
    guidance section for topics like GST, PAYG, superannuation, and
    record keeping). Guidance pages are compliance content rather
    than grant listings, so eligibility/amount/deadline don't apply
    and stay None; the guidance topic (GST, PAYG, etc.) is mapped to
    category.
    """
    url = _first(payload, "url", "link")

    return NormalizedRecord(
        record_id=make_record_id("ato", url),
        source="ato",
        title=payload.get("title"),
        description=_first(payload, "description", "summary", "content"),
        eligibility=None,
        amount=None,
        deadline=None,
        category=_first(payload, "category", "topic"),
        state_or_territory=None,
        url=url,
        ingested_at=fetched_at,
        raw=payload,
    )


def normalize_fair_work_mapd_record(payload: dict[str, Any], fetched_at: str | None = None) -> NormalizedRecord:
    """Normalize a Fair Work Commission MAPD payload.

    fair_work_mapd.py's fetch() is still a stub (TODO: scrape MAPD
    search results and extract pay rates/conditions from award PDFs).
    Modern awards are federal, so state_or_territory stays None;
    the award's pay rate is mapped to amount and its
    conditions/description text to eligibility, which is an
    imperfect fit (awards don't have "eligibility" in the grant
    sense) but keeps pay/condition text out of the free text
    description field.
    """
    url = _first(payload, "url", "link")

    return NormalizedRecord(
        record_id=make_record_id("fair_work_mapd", url),
        source="fair_work_mapd",
        title=_first(payload, "title", "award_name"),
        description=_first(payload, "description", "summary"),
        eligibility=_first(payload, "conditions", "coverage"),
        amount=_first(payload, "pay_rate", "amount"),
        deadline=None,
        category=_first(payload, "category", "classification") or "modern_award",
        state_or_territory=None,
        url=url,
        ingested_at=fetched_at,
        raw=payload,
    )


_NORMALIZERS = {
    "grantconnect": normalize_grantconnect_record,
    "data_gov_au": normalize_data_gov_au_record,
    "business_gov_au": normalize_business_gov_au_record,
    "ato": normalize_ato_record,
    "fair_work_mapd": normalize_fair_work_mapd_record,
}


def normalize_record(source: str, payload: dict[str, Any], fetched_at: str | None = None) -> NormalizedRecord:
    """Dispatch to the right per source normalizer by source name.

    Raises KeyError for an unrecognized source name, so an unexpected
    source surfaces immediately rather than silently falling through
    to a generic mapping that would likely mis-map fields.
    """
    try:
        normalizer = _NORMALIZERS[source]
    except KeyError as exc:
        raise KeyError(f"No normalizer registered for source '{source}'") from exc
    return normalizer(payload, fetched_at=fetched_at)
