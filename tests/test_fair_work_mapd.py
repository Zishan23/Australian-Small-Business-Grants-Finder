"""Tests for the Fair Work MAPD scraper's parsing logic.

These test the search results HTML parsing and pay rate text parsing
directly against static fixtures/strings, since hitting the live
fwc.gov.au site in tests would be slow, flaky, and impolite to run
repeatedly, and fabricating a real PDF file is unnecessary: the text
extracted from a PDF (or an HTML page) is parsed by parse_award_text,
which is tested here against plain strings, kept separate from the
PDF-byte-extraction step (FairWorkMapdIngester._extract_pdf_text),
which is mocked out instead. Once the selectors have been verified
against real fwc.gov.au HTML, update these fixtures to match the
actual markup shape.
"""

from src.ingestion.sources.fair_work_mapd import FairWorkMapdIngester, parse_award_text

SEARCH_RESULTS_HTML = """
<html><body>
<div class="search-results">
  <a href="/documents/awards/retail-award-pay-rates.pdf">Retail Award pay rates</a>
  <a href="/document-search/result/clerks-award-summary">Clerks Award summary</a>
</div>
</body></html>
"""

AWARD_PDF_TEXT = """
General Retail Industry Award 2020
Classification         Rate
Level 1 $24.36 per hour
Level 2 $25.11 per hour
Level 3 - $26.73 per hour
Retail Supervisor $850.10 per week
"""

CLERKS_AWARD_HTML = """
<html><body>
<h1>Clerks Award summary</h1>
<p>Level 2 $28.90 per hour applies to general clerical duties.</p>
</body></html>
"""


def test_extract_document_links_finds_pdf_and_result_links():
    ingester = FairWorkMapdIngester()
    links = ingester._extract_document_links(SEARCH_RESULTS_HTML)

    assert any(link.endswith("retail-award-pay-rates.pdf") for link in links)
    assert any("clerks-award-summary" in link for link in links)


def test_extract_document_links_returns_absolute_urls():
    ingester = FairWorkMapdIngester()
    links = ingester._extract_document_links(SEARCH_RESULTS_HTML)

    assert all(link.startswith("https://www.fwc.gov.au") for link in links)


def test_parse_award_text_extracts_hourly_and_weekly_rates():
    parsed = parse_award_text(AWARD_PDF_TEXT)
    rates = parsed["pay_rates"]

    assert {"classification": "Level 1", "amount": 24.36, "period": "hour"} in rates
    assert {"classification": "Level 2", "amount": 25.11, "period": "hour"} in rates
    assert {"classification": "Level 3", "amount": 26.73, "period": "hour"} in rates
    assert {
        "classification": "Retail Supervisor",
        "amount": 850.10,
        "period": "week",
    } in rates


def test_parse_award_text_returns_empty_list_for_no_matches():
    assert parse_award_text("No pay rate information on this page.") == {
        "pay_rates": []
    }


def test_parse_award_text_handles_empty_string():
    assert parse_award_text("") == {"pay_rates": []}


def test_fetch_document_parses_html_result(monkeypatch):
    ingester = FairWorkMapdIngester()

    class _FakeResponse:
        status_code = 200
        text = CLERKS_AWARD_HTML
        content = b""

    monkeypatch.setattr(
        ingester.session, "get", lambda *args, **kwargs: _FakeResponse()
    )

    detail = ingester._fetch_document(
        "https://www.fwc.gov.au/document-search/result/clerks-award-summary"
    )

    assert detail["title"] == "Clerks Award summary"
    assert detail["document_type"] == "html"
    assert {"classification": "Level 2", "amount": 28.90, "period": "hour"} in detail[
        "pay_rates"
    ]


def test_fetch_document_extracts_pdf_text_via_helper(monkeypatch):
    ingester = FairWorkMapdIngester()

    class _FakeResponse:
        status_code = 200
        text = ""
        content = b"%PDF-fake-bytes"

    monkeypatch.setattr(
        ingester.session, "get", lambda *args, **kwargs: _FakeResponse()
    )
    monkeypatch.setattr(
        FairWorkMapdIngester, "_extract_pdf_text", staticmethod(lambda pdf_bytes: AWARD_PDF_TEXT)
    )

    detail = ingester._fetch_document(
        "https://www.fwc.gov.au/documents/awards/retail-award-pay-rates.pdf"
    )

    assert detail["document_type"] == "pdf"
    assert len(detail["pay_rates"]) == 4


def test_fetch_document_returns_none_on_non_200(monkeypatch):
    ingester = FairWorkMapdIngester()

    class _FakeResponse:
        status_code = 404
        text = ""
        content = b""

    monkeypatch.setattr(
        ingester.session, "get", lambda *args, **kwargs: _FakeResponse()
    )

    assert (
        ingester._fetch_document(
            "https://www.fwc.gov.au/document-search/result/missing"
        )
        is None
    )
