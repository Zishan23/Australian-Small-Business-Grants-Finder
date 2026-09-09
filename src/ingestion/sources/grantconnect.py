"""Ingester for GrantConnect (grants.gov.au).

GrantConnect publishes current and forecast Australian Government
grant opportunities. This module is responsible only for fetching raw
data; normalization happens in src/processing.
"""

from src.ingestion.sources.base import BaseSourceIngester, RawRecord


class GrantConnectIngester(BaseSourceIngester):
    source_name = "grantconnect"

    # TODO: confirm the exact API endpoint and auth requirements.
    # GrantConnect has historically exposed data via an OCDS
    # (Open Contracting Data Standard) feed and/or a search API.
    BASE_URL = "https://www.grants.gov.au"

    def fetch(self) -> list[RawRecord]:
        """Fetch current grant opportunities from GrantConnect.

        TODO: implement pagination and request logic once the exact
        API contract is confirmed.
        """
        raise NotImplementedError("GrantConnect fetch logic not yet implemented")
