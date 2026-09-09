"""Shared interface for all data source ingesters.

Each source (GrantConnect, data.gov.au, business.gov.au, ATO, Fair Work
Commission MAPD) implements this interface so the pipeline can treat
them interchangeably.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class RawRecord:
    """A single raw record pulled from a source, before normalization."""

    source: str
    payload: dict[str, Any]
    fetched_at: str

    @classmethod
    def create(cls, source: str, payload: dict[str, Any]) -> "RawRecord":
        return cls(
            source=source,
            payload=payload,
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )


class BaseSourceIngester(ABC):
    """Base class every source ingester must implement."""

    #: Short identifier used in S3 keys and logging, e.g. "grantconnect"
    source_name: str = "base"

    @abstractmethod
    def fetch(self) -> list[RawRecord]:
        """Fetch raw records from the source.

        Implementations should handle pagination and rate limiting
        internally and return a flat list of RawRecord objects.
        """
        raise NotImplementedError

    def run(self) -> list[RawRecord]:
        """Entry point called by the pipeline orchestrator."""
        return self.fetch()
