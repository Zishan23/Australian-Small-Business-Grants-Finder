"""Ingester for data.gov.au, accessed via its CKAN API.

data.gov.au is Australia's federal open data portal. Relevant
datasets here are those tagged with grants, small business, or
compliance related categories.
"""

from src.ingestion.sources.base import BaseSourceIngester, RawRecord

CKAN_API_BASE = "https://data.gov.au/api/3/action"


class DataGovAuIngester(BaseSourceIngester):
    source_name = "data_gov_au"

    def __init__(self, search_terms: list[str] | None = None):
        self.search_terms = search_terms or ["small business grants", "compliance"]

    def fetch(self) -> list[RawRecord]:
        """Query the CKAN package_search endpoint for relevant datasets.

        TODO: implement requests.get calls against
        f"{CKAN_API_BASE}/package_search" with the configured search
        terms, paginate through results, and wrap each dataset record
        in a RawRecord.
        """
        raise NotImplementedError("data.gov.au fetch logic not yet implemented")
