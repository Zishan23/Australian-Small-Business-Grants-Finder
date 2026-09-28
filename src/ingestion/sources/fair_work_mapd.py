"""Ingester for Fair Work Commission Modern Awards Pay Database (MAPD).

MAPD covers modern award pay rates and employment conditions, which
are relevant compliance information for small businesses hiring
staff. Content is a mix of search result web pages and PDF award
documents, so this ingester scrapes the document search results and
extracts text from any linked PDFs.

Search page: https://www.fwc.gov.au/document-search

The selectors below are a first pass based on the general shape of a
government document search page (a list of result links, some of
which point at PDF documents rather than HTML pages).
fwc.gov.au could not be reached from the development sandbox this
module was written in, so treat the selectors as a starting point:
run this against the live site, inspect the actual HTML and result
link structure, and adjust _extract_document_links and
_extract_labeled_fields if the real markup differs. In particular,
the query parameters used to filter document-search to modern award
pay rate schedules are a guess (`q=modern award pay rates`) and
should be checked against how the live search form actually submits.
"""

import io
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from src.ingestion.sources.base import BaseSourceIngester, RawRecord

BASE_URL = "https://www.fwc.gov.au"
SEARCH_URL = f"{BASE_URL}/document-search"
REQUEST_DELAY_SECONDS = 1.0
USER_AGENT = "au-small-business-grants-finder/0.1 (personal portfolio project)"
DEFAULT_QUERY = "modern award pay rates"

# Matches lines such as "Level 3 $27.45 per hour" or "Grade 2 - $850.10 per week".
PAY_RATE_LINE_RE = re.compile(
    r"(?P<classification>[A-Za-z][A-Za-z0-9 /()&\-]*?)\s*[-:]?\s*"
    r"\$(?P<amount>\d+(?:\.\d{1,2})?)\s*per\s*(?P<period>hour|week|annum|year)",
    re.IGNORECASE,
)


class FairWorkMapdIngester(BaseSourceIngester):
    source_name = "fair_work_mapd"

    def __init__(self, query: str = DEFAULT_QUERY, max_pages: int | None = None):
        # Safety cap so a pagination assumption that turns out wrong
        # cannot loop forever. None means keep going until a page
        # returns no results.
        self.query = query
        self.max_pages = max_pages
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def fetch(self) -> list[RawRecord]:
        """Fetch modern award pay and conditions data from MAPD search results."""
        records: list[RawRecord] = []
        page = 1

        while self.max_pages is None or page <= self.max_pages:
            params = {"q": self.query}
            if page > 1:
                params["page"] = page
            response = self.session.get(SEARCH_URL, params=params, timeout=30)
            response.raise_for_status()

            document_links = self._extract_document_links(response.text)
            if not document_links:
                break

            for doc_url in document_links:
                time.sleep(REQUEST_DELAY_SECONDS)
                detail = self._fetch_document(doc_url)
                if detail:
                    records.append(RawRecord.create(self.source_name, detail))

            page += 1
            time.sleep(REQUEST_DELAY_SECONDS)

        return records

    def _extract_document_links(self, html: str) -> list[str]:
        """Find every result link on a document-search results page."""
        soup = BeautifulSoup(html, "lxml")
        links = set()
        for anchor in soup.select('a[href*=".pdf"], .search-results a[href]'):
            href = anchor.get("href")
            if href:
                links.add(urljoin(BASE_URL, href))
        return sorted(links)

    def _fetch_document(self, url: str) -> dict | None:
        """Fetch a single search result, handling both PDF and HTML documents."""
        response = self.session.get(url, timeout=30)
        if response.status_code != 200:
            return None

        if url.lower().endswith(".pdf"):
            text = self._extract_pdf_text(response.content)
            title = None
        else:
            soup = BeautifulSoup(response.text, "lxml")
            title = self._text_or_none(soup.select_one("h1"))
            # Newline separated (rather than space joined) so that
            # parse_award_text's line oriented pay rate pattern sees
            # the same kind of line boundaries it would in PDF text,
            # instead of one long run-on line of page text.
            text = soup.get_text("\n", strip=True)

        parsed = parse_award_text(text)

        return {
            "url": url,
            "title": title,
            "document_type": "pdf" if url.lower().endswith(".pdf") else "html",
            "pay_rates": parsed["pay_rates"],
            "raw_text_excerpt": text[:2000] if text else None,
        }

    @staticmethod
    def _extract_pdf_text(pdf_bytes: bytes) -> str:
        """Extract text from a PDF award document's raw bytes.

        Kept as a thin wrapper around pdfplumber so the actual text
        parsing logic (parse_award_text, module level) can be unit
        tested against a plain string without needing to construct a
        real PDF file.
        """
        import pdfplumber

        text_parts = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for pdf_page in pdf.pages:
                page_text = pdf_page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts)

    @staticmethod
    def _text_or_none(tag) -> str | None:
        if tag is None:
            return None
        text = tag.get_text(strip=True)
        return text or None


def parse_award_text(text: str) -> dict:
    """Parse pay rates out of extracted award document/page text.

    This is deliberately separate from PDF byte extraction
    (FairWorkMapdIngester._extract_pdf_text) so it can be unit tested
    directly against a synthetic/mocked text string, without needing
    to fabricate a real PDF file. The pattern below is a first pass
    based on how modern award pay rate schedules commonly phrase a
    classification/rate pair (e.g. "Level 3 $27.45 per hour"); real
    award documents should be checked against this regex once one can
    actually be fetched, since formatting varies between awards.
    """
    if not text:
        return {"pay_rates": []}

    pay_rates = [
        {
            "classification": match.group("classification").strip(),
            "amount": float(match.group("amount")),
            "period": match.group("period").lower(),
        }
        for match in PAY_RATE_LINE_RE.finditer(text)
    ]

    return {"pay_rates": pay_rates}
