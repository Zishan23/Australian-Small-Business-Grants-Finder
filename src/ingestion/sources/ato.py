"""Ingester for ATO small business tax compliance guidance.

The ATO does not publish a public API for its guidance content, so
this ingester scrapes the small business section of ato.gov.au: the
hub page, plus the topic pages it links to that cover the compliance
areas most relevant to a small business (GST, PAYG withholding/
instalments, superannuation, and record keeping).

Hub page: https://www.ato.gov.au/businesses-and-organisations/small-business

The selectors below are a first pass based on the general shape of an
ATO guidance hub page (a page of link cards/lists pointing at topic
pages, each topic page built from a heading plus a series of
sub-heading/body sections). ato.gov.au could not be reached from the
development sandbox this module was written in, so treat the
selectors as a starting point: run this against the live site,
inspect the actual HTML, and adjust _extract_topic_links and
_extract_sections if the real markup differs.
"""

import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from src.ingestion.sources.base import BaseSourceIngester, RawRecord

BASE_URL = "https://www.ato.gov.au"
HUB_URL = f"{BASE_URL}/businesses-and-organisations/small-business"
REQUEST_DELAY_SECONDS = 1.0
USER_AGENT = "au-small-business-grants-finder/0.1 (personal portfolio project)"

# Keywords used to flag which compliance topic a page is about. A page
# can match more than one (e.g. a page mentions both GST and record
# keeping), so this collects every match rather than picking one.
TOPIC_KEYWORDS = {
    "gst": ["gst", "goods and services tax"],
    "payg": ["payg", "pay as you go"],
    "superannuation": ["super", "superannuation"],
    "record_keeping": ["record keeping", "records you need to keep", "recordkeeping"],
}


class AtoIngester(BaseSourceIngester):
    source_name = "ato"

    def __init__(self, max_pages: int | None = None):
        # Safety cap on the number of topic pages followed from the
        # hub, so a bad assumption about the hub's link structure
        # cannot make this crawl an unbounded part of ato.gov.au.
        self.max_pages = max_pages
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def fetch(self) -> list[RawRecord]:
        """Scrape the small business hub page and its linked topic pages."""
        response = self.session.get(HUB_URL, timeout=30)
        response.raise_for_status()

        topic_links = self._extract_topic_links(response.text)
        if self.max_pages is not None:
            topic_links = topic_links[: self.max_pages]

        records: list[RawRecord] = []
        for topic_url in topic_links:
            time.sleep(REQUEST_DELAY_SECONDS)
            detail = self._fetch_topic(topic_url)
            if detail:
                records.append(RawRecord.create(self.source_name, detail))

        return records

    def _extract_topic_links(self, html: str) -> list[str]:
        """Find links from the hub page into small business topic pages.

        Only links that stay under the same
        /businesses-and-organisations/small-business/ path are kept,
        which excludes navigation/footer links elsewhere on the site.
        """
        soup = BeautifulSoup(html, "lxml")
        prefix = "/businesses-and-organisations/small-business"
        links = set()
        for anchor in soup.select("a[href]"):
            href = anchor.get("href")
            if not href:
                continue
            absolute = urljoin(BASE_URL, href)
            if prefix not in absolute:
                continue
            if absolute.rstrip("/") == HUB_URL.rstrip("/"):
                continue
            links.add(absolute)
        return sorted(links)

    def _fetch_topic(self, url: str) -> dict | None:
        """Fetch and parse a single small business guidance topic page."""
        response = self.session.get(url, timeout=30)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, "lxml")
        title = self._text_or_none(soup.select_one("h1"))
        sections = self._extract_sections(soup)
        full_text = " ".join(sections.values())

        return {
            "url": url,
            "title": title,
            "sections": sections,
            "topics": self._match_topics(f"{title or ''} {full_text}"),
        }

    @staticmethod
    def _text_or_none(tag) -> str | None:
        if tag is None:
            return None
        text = tag.get_text(strip=True)
        return text or None

    @staticmethod
    def _extract_sections(soup: BeautifulSoup) -> dict[str, str]:
        """Pull heading/body sections out of a guidance page.

        ATO guidance pages are structured as a series of h2 (or h3)
        sub-headings each followed by body content. Collecting the
        text between one heading and the next, keyed by the heading
        text, is more resilient to markup/CSS class changes than
        targeting a specific content container.
        """
        sections: dict[str, str] = {}
        for heading in soup.select("h2, h3"):
            heading_text = heading.get_text(strip=True)
            if not heading_text:
                continue

            body_parts = []
            for sibling in heading.find_next_siblings():
                if sibling.name in ("h1", "h2", "h3"):
                    break
                text = sibling.get_text(strip=True)
                if text:
                    body_parts.append(text)

            if body_parts:
                sections[heading_text] = " ".join(body_parts)

        return sections

    @staticmethod
    def _match_topics(text: str) -> list[str]:
        """Return every compliance topic whose keywords appear in text."""
        lowered = text.lower()
        return sorted(
            topic
            for topic, keywords in TOPIC_KEYWORDS.items()
            if any(keyword in lowered for keyword in keywords)
        )
