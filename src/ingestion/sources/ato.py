"""Ingester for ATO small business tax compliance guidance.

The ATO does not expose a public API for its guidance content, so
this ingester scrapes relevant small business tax and compliance
pages from ato.gov.au.
"""

from src.ingestion.sources.base import BaseSourceIngester, RawRecord

ATO_SMALL_BUSINESS_URL = "https://www.ato.gov.au/businesses-and-organisations/small-business"


class AtoIngester(BaseSourceIngester):
    source_name = "ato"

    def fetch(self) -> list[RawRecord]:
        """Scrape ATO small business guidance pages.

        TODO: implement scraping of the small business section,
        following internal links to relevant compliance topics
        (GST, PAYG, superannuation, record keeping).
        """
        raise NotImplementedError("ATO fetch logic not yet implemented")
