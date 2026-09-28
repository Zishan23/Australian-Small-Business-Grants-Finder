"""Processing pipeline orchestrator.

This is the step that runs after ingestion (src/ingestion/pipeline.py)
has written raw/{source}/{date}/records.jsonl to S3. For a given
run_date it reads each source's raw records back out of S3, maps
them into the common NormalizedRecord schema via
src/processing/normalize.py, and writes the result both to the
processed S3 zone (processed/{source}/{date}/records.jsonl, newline
delimited JSON) and to DynamoDB (keyed by record_id) for fast
lookups. See docs/architecture.md's "Data flow" steps 3-4.

Mirrors src/ingestion/pipeline.py's style: failures for one source
are caught and reported independently so a bad source doesn't take
down the whole run.
"""

import json
import logging
import os
from datetime import datetime, timezone

import boto3

from src.processing.normalize import normalize_record
from src.processing.schema import NormalizedRecord

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SOURCE_NAMES: list[str] = [
    "grantconnect",
    "data_gov_au",
    "business_gov_au",
    "ato",
    "fair_work_mapd",
]

DEFAULT_TABLE_NAME = "au-grants-finder-processed"

_s3_client = None
_dynamodb_resource = None


def get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3")
    return _s3_client


def get_dynamodb_resource():
    global _dynamodb_resource
    if _dynamodb_resource is None:
        _dynamodb_resource = boto3.resource("dynamodb")
    return _dynamodb_resource


def read_raw_records_from_s3(bucket_name: str, source_name: str, run_date: str) -> list[dict]:
    """Read raw/{source_name}/{run_date}/records.jsonl back from S3.

    Returns the parsed JSON objects as written by
    src/ingestion/utils.py's write_raw_records_to_s3, i.e. dicts with
    "source", "payload", and "fetched_at" keys. Blank lines are
    skipped defensively.
    """
    key = f"raw/{source_name}/{run_date}/records.jsonl"
    response = get_s3_client().get_object(Bucket=bucket_name, Key=key)
    body = response["Body"].read().decode("utf-8")
    return [json.loads(line) for line in body.splitlines() if line.strip()]


def write_normalized_records_to_s3(
    bucket_name: str,
    source_name: str,
    run_date: str,
    records: list[NormalizedRecord],
) -> None:
    """Write NormalizedRecord objects to S3 as newline delimited JSON.

    Key layout: processed/{source_name}/{run_date}/records.jsonl
    """
    key = f"processed/{source_name}/{run_date}/records.jsonl"
    body = "\n".join(json.dumps(record.to_dict()) for record in records)
    get_s3_client().put_object(Bucket=bucket_name, Key=key, Body=body.encode("utf-8"))


def write_normalized_records_to_dynamodb(table_name: str, records: list[NormalizedRecord]) -> None:
    """Batch write NormalizedRecord objects to DynamoDB, keyed by record_id.

    Uses the resource level Table.batch_writer(), which handles
    batching (max 25 items per request) and retries for unprocessed
    items automatically.
    """
    table = get_dynamodb_resource().Table(table_name)
    with table.batch_writer(overwrite_by_pkeys=["record_id"]) as batch:
        for record in records:
            batch.put_item(Item=record.to_dict())


def run_processing_pipeline(
    raw_bucket_name: str,
    processed_bucket_name: str,
    table_name: str | None = None,
    run_date: str | None = None,
    source_names: list[str] | None = None,
) -> dict[str, str]:
    """Normalize and store every configured source for one run_date.

    Returns a dict mapping source_name to a status string, mirroring
    src/ingestion/pipeline.py's run_pipeline, so the caller can decide
    whether a partial failure warrants an SNS alert.
    """
    run_date = run_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    table_name = table_name or os.environ.get("PROCESSED_TABLE_NAME", DEFAULT_TABLE_NAME)
    source_names = source_names or SOURCE_NAMES

    results: dict[str, str] = {}

    for source_name in source_names:
        try:
            raw_records = read_raw_records_from_s3(raw_bucket_name, source_name, run_date)
            normalized_records = [
                normalize_record(
                    source_name,
                    raw_record.get("payload") or {},
                    fetched_at=raw_record.get("fetched_at"),
                )
                for raw_record in raw_records
            ]

            write_normalized_records_to_s3(processed_bucket_name, source_name, run_date, normalized_records)
            write_normalized_records_to_dynamodb(table_name, normalized_records)

            results[source_name] = f"ok ({len(normalized_records)} records)"
            logger.info("Normalized %s records for %s", len(normalized_records), source_name)
        except Exception as exc:  # noqa: BLE001 - intentionally broad, per-source isolation
            results[source_name] = f"failed: {exc}"
            logger.exception("Processing failed for source %s", source_name)

    return results


if __name__ == "__main__":
    raw_bucket = os.environ.get("RAW_DATA_BUCKET", "au-grants-finder-raw")
    processed_bucket = os.environ.get("PROCESSED_DATA_BUCKET", "au-grants-finder-processed")
    run_results = run_processing_pipeline(raw_bucket, processed_bucket)
    for source_name, status in run_results.items():
        print(f"{source_name}: {status}")
