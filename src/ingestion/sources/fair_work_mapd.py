"""Ingester for Fair Work Commission Modern Awards Pay Database (MAPD).

MAPD covers modern award pay rates and employment conditions, which
are relevant compliance information for small businesses hiring
staff. Content is a mix of web pages and PDF award documents.
"""

from src.ingestion.sources.base import BaseSourceIngester, RawRecord

MAPD_BASE_URL = "https://www.fwc.gov.au/document-search"


class FairWorkMapdIngester(BaseSourceIngester):
    source_name = "fair_work_mapd"

    def fetch(self) -> list[RawRecord]:
        """Fetch modern award pay and conditions data.

        TODO: implement scraping of the MAPD search results and PDF
        text extraction for award documents (e.g. using pdfplumber
        or similar) to pull out pay rates and conditions relevant to
        small business categories.
        """
        raise NotImplementedError("Fair Work MAPD fetch logic not yet implemented")
