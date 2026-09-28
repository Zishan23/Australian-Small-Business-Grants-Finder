"""Common normalized record schema.

This is the fixed contract between the processing layer
(src/processing/normalize.py, src/processing/pipeline.py) and the
downstream RAG/retrieval layer (src/rag/). Every source normalizer
must produce instances of NormalizedRecord below.

Its shape follows the "Common record schema (draft)" in
docs/architecture.md as closely as possible, plus a record_id
primary key (used as the DynamoDB partition key) and a raw payload
passthrough for traceability/debugging.
"""

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any


def make_record_id(source: str, natural_key: str | None) -> str:
    """Deterministically derive a stable, source namespaced record id.

    `natural_key` should be the most stable identifying value
    available on the raw record (typically its detail page URL, or a
    source specific id such as a CKAN package id). Hashing keeps the
    id short and filesystem/S3/DynamoDB key safe regardless of what
    the natural key looks like, while staying deterministic so
    re-processing the same raw record yields the same record_id
    (making DynamoDB writes naturally idempotent).

    A missing natural key still produces a stable id (namespaced
    under the source) rather than raising, since some raw payloads
    genuinely have nothing better to key on.
    """
    key_material = f"{source}:{natural_key or ''}"
    digest = hashlib.sha256(key_material.encode("utf-8")).hexdigest()
    return f"{source}#{digest[:24]}"


@dataclass
class NormalizedRecord:
    """A single record in the common schema, ready for the processed
    S3 zone, DynamoDB, and downstream chunking/embedding.
    """

    record_id: str
    source: str
    title: str | None
    description: str | None
    eligibility: str | None
    amount: str | None
    deadline: str | None
    category: str | None
    state_or_territory: str | None
    url: str | None
    ingested_at: str | None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
