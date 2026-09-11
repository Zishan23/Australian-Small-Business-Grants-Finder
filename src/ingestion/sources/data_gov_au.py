"""Ingester for data.gov.au, accessed via its CKAN API.

data.gov.au is Australia's federal open data portal. Relevant
datasets here are those tagged with grants, small business, or
compliance related categories. Unlike GrantConnect, this source has
a real public API (CKAN package_search), so no HTML scraping is
needed.
"""

from typing import Any

import requests

from src.ingestion.sources.base import BaseSourceIngester, RawRecord

CKAN_API_BASE = "https://data.gov.au/api/3/action"
PACKAGE_SEARCH_URL = f"{CKAN_API_BASE}/package_search"
USER_AGENT = "au-small-business-grants-finder/0.1 (personal portfolio project)"
# CKAN's default page size; keep it modest so each request stays small.
DEFAULT_ROWS = 100


class DataGovAuIngester(BaseSourceIngester):
    source_name = "data_gov_au"

    def __init__(
        self,
        search_terms: list[str] | None = None,
        rows: int = DEFAULT_ROWS,
    ):
        self.search_terms = search_terms or ["small business grants", "compliance"]
        self.rows = rows
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def fetch(self) -> list[RawRecord]:
        """Query package_search for each term and return unique datasets.

        The same dataset can match more than one search term, so results
        are deduplicated by CKAN package id before wrapping in RawRecord.
        """
        seen_ids: set[str] = set()
        records: list[RawRecord] = []

        for term in self.search_terms:
            for package in self._search_all_pages(term):
                package_id = package.get("id")
                if not package_id or package_id in seen_ids:
                    continue
                seen_ids.add(package_id)
                records.append(RawRecord.create(self.source_name, package))

        return records

    def _search_all_pages(self, term: str) -> list[dict[str, Any]]:
        """Paginate package_search for one query until a short page.

        CKAN uses start/rows offsets. Stop when a page returns fewer
        results than requested, which means there is nothing left.
        """
        packages: list[dict[str, Any]] = []
        start = 0

        while True:
            page = self._search_page(term=term, start=start, rows=self.rows)
            packages.extend(page)
            if len(page) < self.rows:
                break
            start += self.rows

        return packages

    def _search_page(self, term: str, start: int, rows: int) -> list[dict[str, Any]]:
        """Fetch a single page of package_search results for a term."""
        response = self.session.get(
            PACKAGE_SEARCH_URL,
            params={"q": term, "start": start, "rows": rows},
            timeout=30,
        )
        response.raise_for_status()

        body = response.json()
        result = body.get("result") or {}
        return list(result.get("results") or [])
