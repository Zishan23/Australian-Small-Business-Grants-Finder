"""Tests for the business.gov.au scraper's parsing logic.

These test the HTML parsing functions directly against static
fixtures, since hitting the live business.gov.au site in tests would
be slow, flaky, and impolite to run repeatedly. Once the selectors
have been verified against real business.gov.au HTML, update these
fixtures to match the actual markup shape.
"""

from bs4 import BeautifulSoup

from src.ingestion.sources.business_gov_au import BusinessGovAuIngester

LISTING_HTML = """
<html><body>
<div class="grants-list">
  <a href="/grants-and-programs/energy-efficiency-grants">Energy Efficiency Grants</a>
  <a href="/grants-and-programs/export-market-development-grant">Export Market Development Grant</a>
  <a href="/grants-and-programs">Back to grants and programs</a>
</div>
</body></html>
"""

DETAIL_HTML = """
<html><body>
<h1>Energy Efficiency Grants</h1>
<div class="description">Funding to help small businesses cut energy costs.</div>
<dl>
  <dt>Eligibility</dt><dd>Businesses with fewer than 20 employees</dd>
  <dt>Closing Date</dt><dd>15 March 2027</dd>
  <dt>What you get</dt><dd>Up to $50,000</dd>
</dl>
</body></html>
"""


def test_extract_grant_links_finds_detail_links():
    ingester = BusinessGovAuIngester()
    links = ingester._extract_grant_links(LISTING_HTML)

    assert len(links) == 2
    assert any("energy-efficiency-grants" in link for link in links)
    assert any("export-market-development-grant" in link for link in links)


def test_extract_grant_links_excludes_listing_page_self_link():
    ingester = BusinessGovAuIngester()
    links = ingester._extract_grant_links(LISTING_HTML)

    assert all(not link.rstrip("/").endswith("/grants-and-programs") for link in links)


def test_extract_grant_links_returns_absolute_urls():
    ingester = BusinessGovAuIngester()
    links = ingester._extract_grant_links(LISTING_HTML)

    assert all(link.startswith("https://business.gov.au") for link in links)


def test_extract_labeled_fields_reads_definition_list():
    soup = BeautifulSoup(DETAIL_HTML, "lxml")
    fields = BusinessGovAuIngester._extract_labeled_fields(soup)

    assert fields["eligibility"] == "Businesses with fewer than 20 employees"
    assert fields["closing date"] == "15 March 2027"
    assert fields["what you get"] == "Up to $50,000"


def test_fetch_detail_maps_fields_into_record_payload(monkeypatch):
    ingester = BusinessGovAuIngester()

    class _FakeResponse:
        status_code = 200
        text = DETAIL_HTML

    monkeypatch.setattr(
        ingester.session, "get", lambda *args, **kwargs: _FakeResponse()
    )

    detail = ingester._fetch_detail(
        "https://business.gov.au/grants-and-programs/energy-efficiency-grants"
    )

    assert detail["title"] == "Energy Efficiency Grants"
    assert detail["description"] == (
        "Funding to help small businesses cut energy costs."
    )
    assert detail["eligibility"] == "Businesses with fewer than 20 employees"
    assert detail["closing_date"] == "15 March 2027"
    assert detail["what_you_get"] == "Up to $50,000"


def test_fetch_detail_returns_none_on_non_200(monkeypatch):
    ingester = BusinessGovAuIngester()

    class _FakeResponse:
        status_code = 404
        text = ""

    monkeypatch.setattr(
        ingester.session, "get", lambda *args, **kwargs: _FakeResponse()
    )

    assert ingester._fetch_detail("https://business.gov.au/grants-and-programs/missing") is None
