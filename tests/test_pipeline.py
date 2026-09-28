"""Tests for the ingestion pipeline orchestrator.

These focus on the orchestrator's behavior (failure isolation between
sources), not on the individual scrapers, since those depend on live
external sites/APIs and are tested separately with static fixtures
in their own test modules.
"""

from unittest.mock import patch

from src.ingestion.pipeline import run_pipeline
from src.ingestion.sources.base import RawRecord


def test_run_pipeline_runs_every_source_and_reports_ok():
    """Every configured source is stubbed here so this test stays
    offline; it checks that the orchestrator calls each ingester and
    records an "ok" status with the returned record count.
    """
    sample = [RawRecord.create("grantconnect", {"title": "Sample"})]
    data_gov_sample = [RawRecord.create("data_gov_au", {"id": "pkg-1"})]
    business_gov_sample = [
        RawRecord.create("business_gov_au", {"title": "Sample Grant"})
    ]
    ato_sample = [RawRecord.create("ato", {"title": "GST for small business"})]
    fair_work_sample = [RawRecord.create("fair_work_mapd", {"title": "Retail Award"})]

    with patch("src.ingestion.pipeline.write_raw_records_to_s3"), patch(
        "src.ingestion.pipeline.GrantConnectIngester.fetch",
        return_value=sample,
    ), patch(
        "src.ingestion.pipeline.DataGovAuIngester.fetch",
        return_value=data_gov_sample,
    ), patch(
        "src.ingestion.pipeline.BusinessGovAuIngester.fetch",
        return_value=business_gov_sample,
    ), patch(
        "src.ingestion.pipeline.AtoIngester.fetch",
        return_value=ato_sample,
    ), patch(
        "src.ingestion.pipeline.FairWorkMapdIngester.fetch",
        return_value=fair_work_sample,
    ):
        results = run_pipeline(bucket_name="test-bucket")

    assert len(results) == 5
    assert all(status.startswith("ok") for status in results.values())
    assert results["business_gov_au"] == "ok (1 records)"
    assert results["ato"] == "ok (1 records)"
    assert results["fair_work_mapd"] == "ok (1 records)"


def test_run_pipeline_isolates_source_failures():
    """A failure in one source should not stop the others from being
    attempted, and should be reflected in the results dict.
    """
    sample = [RawRecord.create("grantconnect", {"title": "Sample"})]
    data_gov_sample = [RawRecord.create("data_gov_au", {"id": "pkg-1"})]
    business_gov_sample = [
        RawRecord.create("business_gov_au", {"title": "Sample Grant"})
    ]

    with patch("src.ingestion.pipeline.write_raw_records_to_s3"):
        with patch(
            "src.ingestion.pipeline.GrantConnectIngester.fetch",
            return_value=sample,
        ), patch(
            "src.ingestion.pipeline.DataGovAuIngester.fetch",
            return_value=data_gov_sample,
        ), patch(
            "src.ingestion.pipeline.BusinessGovAuIngester.fetch",
            return_value=business_gov_sample,
        ), patch(
            "src.ingestion.pipeline.AtoIngester.fetch",
            side_effect=RuntimeError("ato.gov.au unreachable"),
        ), patch(
            "src.ingestion.pipeline.FairWorkMapdIngester.fetch",
            side_effect=RuntimeError("fwc.gov.au unreachable"),
        ):
            results = run_pipeline(bucket_name="test-bucket")

    assert len(results) == 5
    assert results["grantconnect"].startswith("ok")
    assert results["data_gov_au"].startswith("ok")
    assert results["business_gov_au"].startswith("ok")
    assert "failed" in results["ato"]
    assert "failed" in results["fair_work_mapd"]
