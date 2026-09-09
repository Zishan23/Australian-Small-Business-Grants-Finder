"""Ingester for business.gov.au grants and programs listings.

business.gov.au does not expose a public API for its grants finder,
so this ingester scrapes the publicly listed grants and programs
pages.
"""

from src.ingestion.sources.base import BaseSourceIngester, RawRecord

GRANTS_LISTING_URL = "https://business.gov.au/grants-and-programs"


class BusinessGovAuIngester(BaseSourceIngester):
    source_name = "business_gov_au"

    def fetch(self) -> list[RawRecord]:
        """Scrape the grants and programs listing page.

        TODO: implement requests + BeautifulSoup parsing of the
        listing page, following pagination and individual grant
        detail pages for eligibility and deadline details. Respect
        robots.txt and add a reasonable delay between requests.
        """
        raise NotImplementedError("business.gov.au fetch logic not yet implemented")
