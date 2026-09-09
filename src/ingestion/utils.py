"""Shared utilities for the ingestion pipeline."""

import json

import boto3

from src.ingestion.sources.base import RawRecord

_s3_client = None


def get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3")
    return _s3_client


def write_raw_records_to_s3(
    bucket_name: str,
    source_name: str,
    run_date: str,
    records: list[RawRecord],
) -> None:
    """Write a list of RawRecord objects to S3 as newline delimited JSON.

    Key layout: raw/{source_name}/{run_date}/records.jsonl
    """
    key = f"raw/{source_name}/{run_date}/records.jsonl"
    body = "\n".join(
        json.dumps(
            {
                "source": r.source,
                "payload": r.payload,
                "fetched_at": r.fetched_at,
            }
        )
        for r in records
    )
    get_s3_client().put_object(Bucket=bucket_name, Key=key, Body=body.encode("utf-8"))
