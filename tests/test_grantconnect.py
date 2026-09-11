"""Tests for the GrantConnect scraper's parsing logic.

These test the HTML parsing functions directly against static
fixtures, since hitting the live GrantConnect site in tests would be
slow, flaky, and impolite to run repeatedly. Once the selectors have
been verified against real GrantConnect HTML, update these fixtures
to match the actual markup shape.
"""

from src.ingestion.sources.grantconnect import GrantConnectIngester

LISTING_HTML = """
<html><body>
<div class="search-results">
  <a href="/Go/Show?GoUuid=aaa-111">Sample Grant One</a>
  <a href="/Go/Show?GoUuid=bbb-222">Sample Grant Two</a>
</div>
</body></html>
"""

DETAIL_HTML = """
<html><body>
<h1>Sample Grant One</h1>
<div class="description">A grant for testing purposes.</div>
<dl>
  <dt>Agency</dt><dd>Department of Testing</dd>
  <dt>Category</dt><dd>Small Business</dd>
  <dt>Closing Date</dt><dd>31 December 2026</dd>
</dl>
</body></html>
"""


def test_extract_go_links_finds_all_detail_links():
    ingester = GrantConnectIngester()
    links = ingester._extract_go_links(LISTING_HTML)

    assert len(links) == 2
    assert any("GoUuid=aaa-111" in link for link in links)
    assert any("GoUuid=bbb-222" in link for link in links)


def test_extract_go_links_returns_absolute_urls():
    ingester = GrantConnectIngester()
    links = ingester._extract_go_links(LISTING_HTML)

    assert all(link.startswith("https://www.grants.gov.au") for link in links)


def test_extract_labeled_fields_reads_definition_list():
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(DETAIL_HTML, "lxml")
    fields = GrantConnectIngester._extract_labeled_fields(soup)

    assert fields["agency"] == "Department of Testing"
    assert fields["category"] == "Small Business"
    assert fields["closing date"] == "31 December 2026"
