"""Tests for the data.gov.au CKAN ingester.

These mock HTTP responses rather than calling the live API, so
pagination and deduplication can be checked quickly and without
depending on network access or data.gov.au availability.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from src.ingestion.sources.data_gov_au import DataGovAuIngester, PACKAGE_SEARCH_URL


def _ckan_page(*packages: dict) -> dict:
    """Build a minimal CKAN package_search JSON body."""
    return {
        "success": True,
        "result": {
            "count": len(packages),
            "results": list(packages),
        },
    }


def _mock_response(json_body: dict, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_body
    if status_code >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(
            f"{status_code} error"
        )
    else:
        response.raise_for_status.return_value = None
    return response


def test_fetch_paginates_until_short_page():
    """A full page followed by a short page should stop pagination."""
    page1 = _ckan_page({"id": "a"}, {"id": "b"})
    page2 = _ckan_page({"id": "c"})  # fewer than rows=2 → stop

    responses = [_mock_response(page1), _mock_response(page2)]

    ingester = DataGovAuIngester(search_terms=["grants"], rows=2)

    with patch.object(ingester.session, "get", side_effect=responses) as mock_get:
        records = ingester.fetch()

    assert [r.payload["id"] for r in records] == ["a", "b", "c"]
    assert mock_get.call_count == 2
    mock_get.assert_any_call(
        PACKAGE_SEARCH_URL,
        params={"q": "grants", "start": 0, "rows": 2},
        timeout=30,
    )
    mock_get.assert_any_call(
        PACKAGE_SEARCH_URL,
        params={"q": "grants", "start": 2, "rows": 2},
        timeout=30,
    )


def test_fetch_deduplicates_across_search_terms():
    """The same package id matching two terms should appear once."""
    shared = {"id": "shared-pkg", "title": "Shared Dataset"}
    only_first = {"id": "first-only", "title": "First Only"}
    only_second = {"id": "second-only", "title": "Second Only"}

    responses = [
        _mock_response(_ckan_page(shared, only_first)),
        _mock_response(_ckan_page(shared, only_second)),
    ]

    ingester = DataGovAuIngester(
        search_terms=["small business grants", "compliance"],
        rows=100,
    )

    with patch.object(ingester.session, "get", side_effect=responses):
        records = ingester.fetch()

    ids = [r.payload["id"] for r in records]
    assert ids == ["shared-pkg", "first-only", "second-only"]
    assert all(r.source == "data_gov_au" for r in records)


def test_fetch_skips_packages_without_id():
    """Results missing an id cannot be deduplicated and are dropped."""
    responses = [
        _mock_response(_ckan_page({"title": "No Id"}, {"id": "kept"})),
    ]
    ingester = DataGovAuIngester(search_terms=["grants"], rows=100)

    with patch.object(ingester.session, "get", side_effect=responses):
        records = ingester.fetch()

    assert [r.payload["id"] for r in records] == ["kept"]


def test_fetch_raises_on_http_error():
    """HTTP failures should surface via raise_for_status()."""
    bad = _mock_response({}, status_code=500)
    ingester = DataGovAuIngester(search_terms=["grants"], rows=10)

    with patch.object(ingester.session, "get", return_value=bad):
        with pytest.raises(requests.HTTPError):
            ingester.fetch()
