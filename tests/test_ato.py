"""Tests for the ATO small business guidance scraper's parsing logic.

These test the HTML parsing functions directly against static
fixtures, since hitting the live ato.gov.au site in tests would be
slow, flaky, and impolite to run repeatedly. Once the selectors have
been verified against real ATO HTML, update these fixtures to match
the actual markup shape.
"""

from bs4 import BeautifulSoup

from src.ingestion.sources.ato import AtoIngester

HUB_HTML = """
<html><body>
<nav>
  <a href="/about-ato/contact-us">Contact us</a>
</nav>
<div class="content">
  <a href="/businesses-and-organisations/small-business/gst">GST for small business</a>
  <a href="/businesses-and-organisations/small-business/payg-instalments">PAYG instalments</a>
  <a href="/businesses-and-organisations/small-business">Small business home</a>
</div>
</body></html>
"""

TOPIC_HTML = """
<html><body>
<h1>GST for small business</h1>
<h2>Registering for GST</h2>
<p>You must register for GST if your turnover is $75,000 or more.</p>
<h2>Record keeping</h2>
<p>Keep records of all sales and purchases for five years.</p>
</body></html>
"""


def test_extract_topic_links_keeps_only_small_business_paths():
    ingester = AtoIngester()
    links = ingester._extract_topic_links(HUB_HTML)

    assert len(links) == 2
    assert any("small-business/gst" in link for link in links)
    assert any("small-business/payg-instalments" in link for link in links)
    assert all("contact-us" not in link for link in links)


def test_extract_topic_links_excludes_hub_self_link():
    ingester = AtoIngester()
    links = ingester._extract_topic_links(HUB_HTML)

    assert all(not link.rstrip("/").endswith("/small-business") for link in links)


def test_extract_sections_groups_body_text_under_headings():
    soup = BeautifulSoup(TOPIC_HTML, "lxml")
    sections = AtoIngester._extract_sections(soup)

    assert sections["Registering for GST"] == (
        "You must register for GST if your turnover is $75,000 or more."
    )
    assert sections["Record keeping"] == (
        "Keep records of all sales and purchases for five years."
    )


def test_match_topics_finds_gst_and_record_keeping():
    topics = AtoIngester._match_topics(
        "Registering for GST turnover thresholds and record keeping obligations"
    )

    assert "gst" in topics
    assert "record_keeping" in topics
    assert "superannuation" not in topics


def test_fetch_topic_builds_record_payload(monkeypatch):
    ingester = AtoIngester()

    class _FakeResponse:
        status_code = 200
        text = TOPIC_HTML

    monkeypatch.setattr(
        ingester.session, "get", lambda *args, **kwargs: _FakeResponse()
    )

    detail = ingester._fetch_topic(
        "https://www.ato.gov.au/businesses-and-organisations/small-business/gst"
    )

    assert detail["title"] == "GST for small business"
    assert "Registering for GST" in detail["sections"]
    assert "gst" in detail["topics"]


def test_fetch_topic_returns_none_on_non_200(monkeypatch):
    ingester = AtoIngester()

    class _FakeResponse:
        status_code = 500
        text = ""

    monkeypatch.setattr(
        ingester.session, "get", lambda *args, **kwargs: _FakeResponse()
    )

    assert ingester._fetch_topic("https://www.ato.gov.au/businesses-and-organisations/small-business/gst") is None
