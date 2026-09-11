"""Tests for the ingestion pipeline orchestrator.

These focus on the orchestrator's behavior (failure isolation between
sources), not on the individual scrapers, since those depend on live
external sites/APIs and will be tested separately with recorded
fixtures once implemented.
"""

from unittest.mock import patch

from src.ingestion.pipeline import run_pipeline
from src.ingestion.sources.base import RawRecord


def test_run_pipeline_isolates_source_failures():
    """A failure in one source should not stop the others from being
    attempted, and should be reflected in the results dict.
    """
    sample = [RawRecord.create("grantconnect", {"title": "Sample"})]

    data_gov_sample = [RawRecord.create("data_gov_au", {"id": "pkg-1"})]

    with patch("src.ingestion.pipeline.write_raw_records_to_s3"):
        # Implemented sources are stubbed so this test stays offline.
        # Remaining sources still raise NotImplementedError.
        with patch(
            "src.ingestion.pipeline.GrantConnectIngester.fetch",
            return_value=sample,
        ), patch(
            "src.ingestion.pipeline.DataGovAuIngester.fetch",
            return_value=data_gov_sample,
        ):
            results = run_pipeline(bucket_name="test-bucket")

    assert len(results) == 5
    assert results["grantconnect"].startswith("ok")
    assert results["data_gov_au"].startswith("ok")
    assert all(
        "failed" in status
        for name, status in results.items()
        if name not in ("grantconnect", "data_gov_au")
    )
