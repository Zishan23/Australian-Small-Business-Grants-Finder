"""Ingestion pipeline orchestrator.

This is the entry point invoked by the weekly ECS Fargate task. It
runs each configured source ingester, then hands raw records off to
S3 storage. Failures in one source should not block the others; each
is wrapped and reported independently so a single bad source doesn't
take down the whole weekly run.
"""

import logging
from datetime import datetime, timezone

from src.ingestion.sources.ato import AtoIngester
from src.ingestion.sources.base import BaseSourceIngester
from src.ingestion.sources.business_gov_au import BusinessGovAuIngester
from src.ingestion.sources.data_gov_au import DataGovAuIngester
from src.ingestion.sources.fair_work_mapd import FairWorkMapdIngester
from src.ingestion.sources.grantconnect import GrantConnectIngester
from src.ingestion.utils import write_raw_records_to_s3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SOURCE_INGESTERS: list[type[BaseSourceIngester]] = [
    GrantConnectIngester,
    DataGovAuIngester,
    BusinessGovAuIngester,
    AtoIngester,
    FairWorkMapdIngester,
]


def run_pipeline(bucket_name: str) -> dict[str, str]:
    """Run every configured source ingester and store raw output.

    Returns a dict mapping source_name to a status string, so the
    caller (e.g. an ECS task entrypoint) can decide whether to raise
    an SNS alert for partial failures.
    """
    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    results: dict[str, str] = {}

    for ingester_cls in SOURCE_INGESTERS:
        ingester = ingester_cls()
        try:
            records = ingester.run()
            write_raw_records_to_s3(
                bucket_name=bucket_name,
                source_name=ingester.source_name,
                run_date=run_date,
                records=records,
            )
            results[ingester.source_name] = f"ok ({len(records)} records)"
            logger.info("Ingested %s records from %s", len(records), ingester.source_name)
        except Exception as exc:  # noqa: BLE001 - intentionally broad, per-source isolation
            results[ingester.source_name] = f"failed: {exc}"
            logger.exception("Ingestion failed for source %s", ingester.source_name)

    return results


if __name__ == "__main__":
    import os

    bucket = os.environ.get("RAW_DATA_BUCKET", "au-grants-finder-raw")
    run_results = run_pipeline(bucket)
    for source_name, status in run_results.items():
        print(f"{source_name}: {status}")
