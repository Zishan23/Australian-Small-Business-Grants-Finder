"""Tests for the per source normalizers in src/processing/normalize.py.

Each test feeds a realistic-per-source raw payload dict (matching the
shape each ingester's fetch()/detail method builds, or is documented
to build for the still-stub sources) and asserts the resulting
NormalizedRecord's fields.
"""

from src.processing.normalize import (
    normalize_ato_record,
    normalize_business_gov_au_record,
    normalize_data_gov_au_record,
    normalize_fair_work_mapd_record,
    normalize_grantconnect_record,
    normalize_record,
)
from src.processing.schema import NormalizedRecord, make_record_id


def test_normalize_grantconnect_record_maps_known_fields():
    payload = {
        "url": "https://www.grants.gov.au/Go/Show?GoUuid=aaa-111",
        "title": "Sample Grant One",
        "description": "A grant for testing purposes.",
        "agency": "Department of Testing",
        "category": "Small Business",
        "closing_date": "31 December 2026",
        "estimated_value": "$50,000",
        "raw_fields": {
            "agency": "Department of Testing",
            "category": "Small Business",
            "closing date": "31 December 2026",
            "eligibility": "Businesses with fewer than 20 employees",
        },
    }

    record = normalize_grantconnect_record(payload, fetched_at="2026-09-01T00:00:00+00:00")

    assert isinstance(record, NormalizedRecord)
    assert record.source == "grantconnect"
    assert record.title == "Sample Grant One"
    assert record.description == "A grant for testing purposes."
    assert record.eligibility == "Businesses with fewer than 20 employees"
    assert record.amount == "$50,000"
    assert record.deadline == "31 December 2026"
    assert record.category == "Small Business"
    assert record.url == payload["url"]
    assert record.ingested_at == "2026-09-01T00:00:00+00:00"
    assert record.record_id == make_record_id("grantconnect", payload["url"])
    assert record.raw == payload


def test_normalize_grantconnect_record_defaults_missing_fields_to_none():
    payload = {"url": "https://www.grants.gov.au/Go/Show?GoUuid=bbb-222"}

    record = normalize_grantconnect_record(payload)

    assert record.title is None
    assert record.description is None
    assert record.eligibility is None
    assert record.amount is None
    assert record.deadline is None
    assert record.category is None
    assert record.state_or_territory is None
    assert record.ingested_at is None


def test_normalize_data_gov_au_record_maps_ckan_package():
    payload = {
        "id": "pkg-1234",
        "name": "small-business-grants-dataset",
        "title": "Small Business Grants Dataset",
        "notes": "A dataset describing small business grants.",
        "organization": {"title": "Department of Industry"},
        "tags": [{"name": "grants"}, {"name": "small-business"}],
    }

    record = normalize_data_gov_au_record(payload, fetched_at="2026-09-01T00:00:00+00:00")

    assert record.source == "data_gov_au"
    assert record.title == "Small Business Grants Dataset"
    assert record.description == "A dataset describing small business grants."
    assert record.category == "grants"
    assert record.state_or_territory == "Department of Industry"
    assert record.url == "https://data.gov.au/dataset/small-business-grants-dataset"
    assert record.eligibility is None
    assert record.amount is None
    assert record.deadline is None
    assert record.record_id == make_record_id("data_gov_au", "pkg-1234")


def test_normalize_data_gov_au_record_handles_missing_optional_fields():
    payload = {"id": "pkg-5678", "name": "another-dataset", "title": "Another Dataset"}

    record = normalize_data_gov_au_record(payload)

    assert record.description is None
    assert record.category is None
    assert record.state_or_territory is None
    assert record.url == "https://data.gov.au/dataset/another-dataset"


def test_normalize_business_gov_au_record_maps_expected_fields():
    payload = {
        "url": "https://business.gov.au/grants-and-programs/sample-program",
        "title": "Sample Business Program",
        "description": "Helps small businesses grow.",
        "eligibility": "Sole traders and small companies",
        "amount": "Up to $10,000",
        "deadline": "2026-11-30",
        "category": "Growth",
        "state_or_territory": "VIC",
    }

    record = normalize_business_gov_au_record(payload)

    assert record.source == "business_gov_au"
    assert record.title == "Sample Business Program"
    assert record.description == "Helps small businesses grow."
    assert record.eligibility == "Sole traders and small companies"
    assert record.amount == "Up to $10,000"
    assert record.deadline == "2026-11-30"
    assert record.category == "Growth"
    assert record.state_or_territory == "VIC"
    assert record.url == payload["url"]
    assert record.record_id == make_record_id("business_gov_au", payload["url"])


def test_normalize_business_gov_au_record_defaults_missing_fields_to_none():
    record = normalize_business_gov_au_record({})

    assert record.title is None
    assert record.eligibility is None
    assert record.amount is None
    assert record.deadline is None
    assert record.url is None


def test_normalize_ato_record_maps_guidance_page():
    payload = {
        "url": "https://www.ato.gov.au/businesses-and-organisations/small-business/gst",
        "title": "GST for small business",
        "content": "How to register for and report GST.",
        "topic": "GST",
    }

    record = normalize_ato_record(payload)

    assert record.source == "ato"
    assert record.title == "GST for small business"
    assert record.description == "How to register for and report GST."
    assert record.category == "GST"
    assert record.eligibility is None
    assert record.amount is None
    assert record.deadline is None
    assert record.state_or_territory is None
    assert record.record_id == make_record_id("ato", payload["url"])


def test_normalize_fair_work_mapd_record_maps_award_payload():
    payload = {
        "url": "https://www.fwc.gov.au/document-search/award/MA000100",
        "award_name": "General Retail Industry Award",
        "summary": "Modern award covering the retail industry.",
        "pay_rate": "$25.41 per hour",
        "conditions": "Applies to employers in the retail industry",
        "classification": "Retail",
    }

    record = normalize_fair_work_mapd_record(payload)

    assert record.source == "fair_work_mapd"
    assert record.title == "General Retail Industry Award"
    assert record.description == "Modern award covering the retail industry."
    assert record.amount == "$25.41 per hour"
    assert record.eligibility == "Applies to employers in the retail industry"
    assert record.category == "Retail"
    assert record.state_or_territory is None
    assert record.deadline is None
    assert record.record_id == make_record_id("fair_work_mapd", payload["url"])


def test_normalize_fair_work_mapd_record_defaults_category_when_missing():
    record = normalize_fair_work_mapd_record({"url": "https://www.fwc.gov.au/document-search/award/MA000200"})

    assert record.category == "modern_award"


def test_normalize_record_dispatches_by_source_name():
    payload = {"url": "https://www.grants.gov.au/Go/Show?GoUuid=ccc-333", "title": "Dispatch Test"}

    record = normalize_record("grantconnect", payload)

    assert record.source == "grantconnect"
    assert record.title == "Dispatch Test"


def test_normalize_record_raises_for_unknown_source():
    import pytest

    with pytest.raises(KeyError):
        normalize_record("unknown_source", {"title": "x"})


def test_make_record_id_is_deterministic_and_namespaced():
    id_one = make_record_id("grantconnect", "https://example.com/a")
    id_two = make_record_id("grantconnect", "https://example.com/a")
    id_three = make_record_id("data_gov_au", "https://example.com/a")

    assert id_one == id_two
    assert id_one != id_three
    assert id_one.startswith("grantconnect#")


def test_make_record_id_handles_missing_natural_key():
    record_id = make_record_id("ato", None)

    assert record_id.startswith("ato#")
