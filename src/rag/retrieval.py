"""RetrievalAgent: finds the NormalizedRecords most relevant to a query.

Retrieval strategy
------------------
There is no real vector store in this environment, and no verified
Bedrock access to generate real embeddings with. Rather than fabricate
similarity scores from an embedding call that can't be exercised here,
:class:`RetrievalAgent` defaults to a transparent, dependency free
keyword/TF style scorer over each record's text fields (see
``_keyword_score``). This is a deliberately honest fallback: it is not
as good as real semantic search, but it is deterministic, and its
behavior under test is exactly its behavior in production, which a
mocked embedding call cannot promise.

Swapping in real Bedrock embeddings later needs no changes to callers:
pass an ``embedding_fn`` (e.g. a bound ``BedrockClient.embed``) into the
constructor and retrieval switches to cosine similarity over embeddings.
Both code paths return the same ``(NormalizedRecord, score)`` shape, so
``RagQueryOrchestrator`` and the agents never need to know which one is
active.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from src.processing.schema import NormalizedRecord

EmbeddingFn = Callable[[str], List[float]]

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> List[str]:
    return _WORD_RE.findall(text.lower())


def _record_text(record: NormalizedRecord) -> str:
    """Concatenate the record's searchable text fields."""
    parts = [
        record.title,
        record.description,
        record.eligibility or "",
        record.category or "",
        record.state_or_territory or "",
    ]
    return " ".join(p for p in parts if p)


def _keyword_score(query: str, text: str) -> float:
    """A small term-overlap score between ``query`` and ``text``.

    Not real TF-IDF - there is no fixed, stable corpus to compute a
    meaningful inverse document frequency from (records are ingested and
    added continuously), so this uses plain term-frequency overlap,
    normalized by the number of distinct query terms. Deterministic,
    dependency free, and easy to reason about in tests.
    """
    query_terms = Counter(_tokenize(query))
    if not query_terms:
        return 0.0
    text_terms = Counter(_tokenize(text))
    overlap = sum(
        q_count * text_terms[term]
        for term, q_count in query_terms.items()
        if term in text_terms
    )
    return overlap / len(query_terms)


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity between two vectors, without a numpy dependency."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class RetrievalAgent:
    """Finds the NormalizedRecords most relevant to a query.

    Defaults to keyword scoring. Pass ``embedding_fn`` to switch to
    cosine similarity over embeddings (e.g. a bound
    ``BedrockClient.embed`` in production, or a fake vector function in
    tests).
    """

    def __init__(
        self,
        records: Sequence[NormalizedRecord],
        embedding_fn: Optional[EmbeddingFn] = None,
    ) -> None:
        self._records: List[NormalizedRecord] = list(records)
        self._embedding_fn = embedding_fn
        self._embedding_cache: Dict[str, List[float]] = {}

    @property
    def records(self) -> List[NormalizedRecord]:
        return self._records

    def retrieve(
        self, query: str, top_k: int = 5
    ) -> List[Tuple[NormalizedRecord, float]]:
        """Return up to ``top_k`` (record, score) pairs, highest score first.

        Records that score exactly 0 (no overlap / no similarity at all)
        are dropped rather than padded in, since a 0 score means the
        record has no evidence of relevance to the query.
        """
        if not self._records:
            return []
        if self._embedding_fn is not None:
            scored = self._retrieve_by_embedding(query)
        else:
            scored = self._retrieve_by_keyword(query)
        scored = [pair for pair in scored if pair[1] > 0]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]

    def _retrieve_by_keyword(
        self, query: str
    ) -> List[Tuple[NormalizedRecord, float]]:
        return [(r, _keyword_score(query, _record_text(r))) for r in self._records]

    def _retrieve_by_embedding(
        self, query: str
    ) -> List[Tuple[NormalizedRecord, float]]:
        assert self._embedding_fn is not None
        query_vec = self._embedding_fn(query)
        scored: List[Tuple[NormalizedRecord, float]] = []
        for record in self._records:
            vec = self._embedding_cache.get(record.record_id)
            if vec is None:
                vec = self._embedding_fn(_record_text(record))
                self._embedding_cache[record.record_id] = vec
            scored.append((record, _cosine_similarity(query_vec, vec)))
        return scored
