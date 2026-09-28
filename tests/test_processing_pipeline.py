"""Tests for the processing pipeline orchestrator.

Mirrors tests/test_pipeline.py's style: mock S3 get/put and DynamoDB
directly rather than hitting real AWS, and assert that a failure for
one source (e.g. a source whose raw records.jsonl is missing or
malformed) does not stop the others from being processed.
"""

import json
from unittest.mock import MagicMock, patch

from src.processing.pipeline import run_processing_pipeline
from src.processing.schema import make_record_id


def _raw_jsonl_body(source: str, payloads: list[dict]) -> bytes:
    lines = [
        json.dumps({"source": source, "payload": payload, "fetched_at": "2026-09-01T00:00:00+00:00"})
        for payload in payloads
    ]
    return "\n".join(lines).encode("utf-8")


def test_run_processing_pipeline_normalizes_and_writes_each_source():
    grantconnect_payloads = [
        {"url": "https://www.grants.gov.au/Go/Show?GoUuid=aaa-111", "title": "Sample Grant"}
    ]
    data_gov_au_payloads = [{"id": "pkg-1", "name": "pkg-one", "title": "Sample Dataset"}]

    def fake_get_object(Bucket, Key):
        if "grantconnect" in Key:
            body = _raw_jsonl_body("grantconnect", grantconnect_payloads)
        elif "data_gov_au" in Key:
            body = _raw_jsonl_body("data_gov_au", data_gov_au_payloads)
        else:
            raise RuntimeError("NoSuchKey")
        return {"Body": MagicMock(read=MagicMock(return_value=body))}

    mock_s3 = MagicMock()
    mock_s3.get_object.side_effect = fake_get_object

    mock_table = MagicMock()
    mock_batch_writer_ctx = MagicMock()
    mock_batch_writer_ctx.__enter__.return_value = MagicMock()
    mock_table.batch_writer.return_value = mock_batch_writer_ctx
    mock_dynamodb = MagicMock()
    mock_dynamodb.Table.return_value = mock_table

    with patch("src.processing.pipeline.get_s3_client", return_value=mock_s3), patch(
        "src.processing.pipeline.get_dynamodb_resource", return_value=mock_dynamodb
    ):
        results = run_processing_pipeline(
            raw_bucket_name="raw-bucket",
            processed_bucket_name="processed-bucket",
            table_name="processed-table",
            run_date="2026-09-01",
        )

    assert len(results) == 5
    assert results["grantconnect"] == "ok (1 records)"
    assert results["data_gov_au"] == "ok (1 records)"
    assert all(
        "failed" in status
        for name, status in results.items()
        if name not in ("grantconnect", "data_gov_au")
    )

    # Processed records were written to the S3 processed zone for both
    # successful sources.
    put_keys = [call.kwargs["Key"] for call in mock_s3.put_object.call_args_list]
    assert "processed/grantconnect/2026-09-01/records.jsonl" in put_keys
    assert "processed/data_gov_au/2026-09-01/records.jsonl" in put_keys

    grantconnect_put = next(
        call for call in mock_s3.put_object.call_args_list
        if call.kwargs["Key"] == "processed/grantconnect/2026-09-01/records.jsonl"
    )
    written_record = json.loads(grantconnect_put.kwargs["Body"].decode("utf-8"))
    assert written_record["title"] == "Sample Grant"
    assert written_record["record_id"] == make_record_id(
        "grantconnect", "https://www.grants.gov.au/Go/Show?GoUuid=aaa-111"
    )

    # DynamoDB was written to via batch_writer for both successful
    # sources (one Table()/batch_writer() call per source).
    assert mock_dynamodb.Table.call_count == 2
    mock_dynamodb.Table.assert_called_with("processed-table")


def test_run_processing_pipeline_isolates_source_failures():
    """A read/normalization failure for one source should not stop the
    others, mirroring tests/test_pipeline.py's isolation test for the
    ingestion pipeline.
    """
    ok_payloads = [{"url": "https://www.grants.gov.au/Go/Show?GoUuid=zzz-999", "title": "OK Grant"}]

    def fake_get_object(Bucket, Key):
        if "grantconnect" in Key:
            body = _raw_jsonl_body("grantconnect", ok_payloads)
            return {"Body": MagicMock(read=MagicMock(return_value=body))}
        raise RuntimeError("NoSuchKey: object does not exist")

    mock_s3 = MagicMock()
    mock_s3.get_object.side_effect = fake_get_object

    mock_table = MagicMock()
    mock_batch_writer_ctx = MagicMock()
    mock_batch_writer_ctx.__enter__.return_value = MagicMock()
    mock_table.batch_writer.return_value = mock_batch_writer_ctx
    mock_dynamodb = MagicMock()
    mock_dynamodb.Table.return_value = mock_table

    with patch("src.processing.pipeline.get_s3_client", return_value=mock_s3), patch(
        "src.processing.pipeline.get_dynamodb_resource", return_value=mock_dynamodb
    ):
        results = run_processing_pipeline(
            raw_bucket_name="raw-bucket",
            processed_bucket_name="processed-bucket",
            run_date="2026-09-01",
        )

    assert results["grantconnect"].startswith("ok")
    assert all(
        "failed" in status for name, status in results.items() if name != "grantconnect"
    )
    # Only the successful source should have reached DynamoDB.
    assert mock_dynamodb.Table.call_count == 1


def test_run_processing_pipeline_defaults_run_date_and_table_name():
    mock_s3 = MagicMock()
    mock_s3.get_object.side_effect = RuntimeError("NoSuchKey")
    mock_dynamodb = MagicMock()

    with patch("src.processing.pipeline.get_s3_client", return_value=mock_s3), patch(
        "src.processing.pipeline.get_dynamodb_resource", return_value=mock_dynamodb
    ):
        results = run_processing_pipeline(
            raw_bucket_name="raw-bucket",
            processed_bucket_name="processed-bucket",
        )

    # No run_date/table_name given, but the pipeline should still run
    # every configured source (all failing here, since S3 is empty)
    # rather than raising before it gets that far.
    assert len(results) == 5
    assert all("failed" in status for status in results.values())
