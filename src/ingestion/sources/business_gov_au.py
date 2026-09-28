"""Ingester for business.gov.au grants and programs listings.

business.gov.au does not publish a public API for its grants finder,
so this ingester scrapes the public listing and detail pages, the
same approach used for GrantConnect, ATO guidance, and Fair Work
MAPD.

Listing page: https://business.gov.au/grants-and-programs
Each result is expected to link to a detail page under the same
site, e.g.:
    https://business.gov.au/grants-and-programs/<grant-slug>

The selectors below are a first pass based on the general shape of a
government grants finder listing (a list/grid of cards, each linking
to a detail page with a title, a description, and a set of labeled
fields such as Eligibility, Closing date, and What you get).
business.gov.au could not be reached from the development sandbox
this module was written in, so treat the selectors as a starting
point: run this against the live site, inspect the actual HTML, and
adjust _extract_grant_links and _extract_labeled_fields if the real
markup differs (in particular, the listing page may be JavaScript
rendered or paginated via query params rather than plain links, in
which case this will need a different pagination strategy).
"""

import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from src.ingestion.sources.base import BaseSourceIngester, RawRecord

BASE_URL = "https://business.gov.au"
LISTING_URL = f"{BASE_URL}/grants-and-programs"
REQUEST_DELAY_SECONDS = 1.0
USER_AGENT = "au-small-business-grants-finder/0.1 (personal portfolio project)"


class BusinessGovAuIngester(BaseSourceIngester):
    source_name = "business_gov_au"

    def __init__(self, max_pages: int | None = None):
        # Safety cap so a pagination assumption that turns out wrong
        # cannot loop forever. None means keep going until a page
        # returns no results.
        self.max_pages = max_pages
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def fetch(self) -> list[RawRecord]:
        """Scrape the grants and programs listing page and each detail page.

        Follows pagination (assumed to be a `?page=` query parameter,
        matching the pattern used elsewhere on the site) until a page
        returns no grant links, then fetches every linked detail page
        for eligibility and closing date information.
        """
        records: list[RawRecord] = []
        page = 1

        while self.max_pages is None or page <= self.max_pages:
            listing_url = LISTING_URL if page == 1 else f"{LISTING_URL}?page={page}"
            response = self.session.get(listing_url, timeout=30)
            response.raise_for_status()

            grant_links = self._extract_grant_links(response.text)
            if not grant_links:
                break

            for grant_url in grant_links:
                time.sleep(REQUEST_DELAY_SECONDS)
                detail = self._fetch_detail(grant_url)
                if detail:
                    records.append(RawRecord.create(self.source_name, detail))

            page += 1
            time.sleep(REQUEST_DELAY_SECONDS)

        return records

    def _extract_grant_links(self, html: str) -> list[str]:
        """Find every grant detail link on a listing page.

        Grant cards are expected to link to pages under
        /grants-and-programs/<slug>, distinct from the listing page
        itself.
        """
        soup = BeautifulSoup(html, "lxml")
        links = set()
        for anchor in soup.select('a[href*="/grants-and-programs/"]'):
            href = anchor.get("href")
            if not href:
                continue
            absolute = urljoin(BASE_URL, href)
            if absolute.rstrip("/") == LISTING_URL.rstrip("/"):
                continue
            links.add(absolute)
        return sorted(links)

    def _fetch_detail(self, url: str) -> dict | None:
        """Fetch and parse a single grant detail page."""
        response = self.session.get(url, timeout=30)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "lxml")
        title = self._text_or_none(soup.select_one("h1"))
        description = self._text_or_none(
            soup.select_one('[class*="description"], [class*="summary"]')
        )
        fields = self._extract_labeled_fields(soup)

        return {
            "url": url,
            "title": title,
            "description": description,
            "eligibility": fields.get("eligibility") or fields.get("who can apply"),
            "closing_date": fields.get("closing date") or fields.get("close date"),
            "what_you_get": fields.get("what you get") or fields.get("amount"),
            "raw_fields": fields,
        }

    @staticmethod
    def _text_or_none(tag) -> str | None:
        if tag is None:
            return None
        text = tag.get_text(strip=True)
        return text or None

    @staticmethod
    def _extract_labeled_fields(soup: BeautifulSoup) -> dict:
        """Pull label/value pairs out of the detail page.

        Grant detail pages present fields such as Eligibility, Closing
        date, and What you get as labeled pairs, typically either a
        definition list (dt/dd) or a two column table. Collecting
        every such pair generically, keyed by lowercased label text,
        is more resilient to markup changes than guessing exact class
        names.
        """
        fields: dict[str, str] = {}

        for dt in soup.select("dt"):
            dd = dt.find_next_sibling("dd")
            if dd:
                label = dt.get_text(strip=True).lower().rstrip(":")
                fields[label] = dd.get_text(strip=True)

        for row in soup.select("tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) == 2:
                label = cells[0].get_text(strip=True).lower().rstrip(":")
                value = cells[1].get_text(strip=True)
                if label and value:
                    fields.setdefault(label, value)

        return fields
