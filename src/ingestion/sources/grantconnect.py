"""Ingester for GrantConnect (grants.gov.au).

GrantConnect does not publish a public REST API. This is a common
point of confusion because the United States equivalent, grants.gov,
does have one; the Australian system does not. The only reliable way
to pull Grant Opportunity data here is to scrape the public listing
and detail pages, the same approach used for business.gov.au, ATO
guidance, and Fair Work MAPD.

Listing page: https://www.grants.gov.au/Go/List
Each result links to a detail page shaped like:
    https://www.grants.gov.au/Go/Show?GoUuid=<uuid>

The selectors below are a first pass based on the page's visible
content and the general listing/detail page shape (a title, a
description, and a set of labeled fields such as Agency, Category,
and Closing Date). GrantConnect could not be reached from the
development sandbox this module was written in, so treat the
selectors as a starting point: run this against the live site,
inspect the actual HTML, and adjust _extract_go_links and
_extract_labeled_fields if the real markup differs.
"""

import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from src.ingestion.sources.base import BaseSourceIngester, RawRecord

BASE_URL = "https://www.grants.gov.au"
LIST_URL = f"{BASE_URL}/Go/List"
REQUEST_DELAY_SECONDS = 1.0
USER_AGENT = "au-small-business-grants-finder/0.1 (personal portfolio project)"


class GrantConnectIngester(BaseSourceIngester):
    source_name = "grantconnect"

    def __init__(self, max_pages: int | None = None):
        # Safety cap so a pagination assumption that turns out wrong
        # cannot loop forever. None means keep going until a page
        # returns no results.
        self.max_pages = max_pages
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def fetch(self) -> list[RawRecord]:
        records: list[RawRecord] = []
        page = 1

        while self.max_pages is None or page <= self.max_pages:
            listing_url = LIST_URL if page == 1 else f"{LIST_URL}?page={page}"
            response = self.session.get(listing_url, timeout=30)
            response.raise_for_status()

            go_links = self._extract_go_links(response.text)
            if not go_links:
                break

            for go_url in go_links:
                time.sleep(REQUEST_DELAY_SECONDS)
                detail = self._fetch_detail(go_url)
                if detail:
                    records.append(RawRecord.create(self.source_name, detail))

            page += 1
            time.sleep(REQUEST_DELAY_SECONDS)

        return records

    def _extract_go_links(self, html: str) -> list[str]:
        """Find every Grant Opportunity detail link on a listing page."""
        soup = BeautifulSoup(html, "lxml")
        links = set()
        for anchor in soup.select('a[href*="Go/Show"]'):
            href = anchor.get("href")
            if href:
                links.add(urljoin(BASE_URL, href))
        return sorted(links)

    def _fetch_detail(self, url: str) -> dict | None:
        """Fetch and parse a single Grant Opportunity detail page."""
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
            "agency": fields.get("agency"),
            "category": fields.get("category") or fields.get("segment"),
            "closing_date": fields.get("closing date") or fields.get("close date"),
            "estimated_value": fields.get("estimated total grant value")
            or fields.get("total funding"),
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

        GO detail pages present fields such as Agency, Category, and
        Closing Date as labeled pairs, typically either a definition
        list (dt/dd) or a two column table. Collecting every such pair
        generically, keyed by lowercased label text, is more resilient
        to markup changes than guessing exact class names.
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
