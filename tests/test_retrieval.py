
import pytest

from src.processing.schema import NormalizedRecord
from src.rag.retrieval import RetrievalAgent, _cosine_similarity, _keyword_score


def make_record(**overrides) -> NormalizedRecord:
    defaults = dict(
        record_id="rec-1",
        source="grantconnect",
        title="Hospitality Small Business Grant",
        description="Grant for hospitality businesses recovering from natural disasters.",
        eligibility="Must be a hospitality business with fewer than 20 employees.",
        amount="$10,000",
        deadline="2026-12-01",
        category="hospitality",
        state_or_territory="VIC",
        url="https://example.com/grant-1",
        ingested_at="2026-09-01T12:00:00",
    )
    defaults.update(overrides)
    return NormalizedRecord(**defaults)


@pytest.fixture
def records():
    return [
        make_record(
            record_id="rec-1",
            title="Hospitality Small Business Grant",
            description="Grant for hospitality businesses recovering from natural disasters.",
            category="hospitality",
            state_or_territory="VIC",
            url="https://example.com/grant-1",
        ),
        make_record(
            record_id="rec-2",
            title="Manufacturing Export Grant",
            description="Grant supporting manufacturing businesses expanding into export markets.",
            eligibility="Manufacturing businesses with export plans.",
            category="manufacturing",
            state_or_territory="NSW",
            url="https://example.com/grant-2",
        ),
        make_record(
            record_id="rec-3",
            title="Fair Work Pay Rate Guidance",
            description="Guidance on minimum pay rates and award coverage for hospitality employers.",
            eligibility=None,
            amount=None,
            category="compliance",
            state_or_territory=None,
            url="https://example.com/compliance-1",
        ),
    ]


def test_keyword_score_rewards_overlap():
    score_relevant = _keyword_score("hospitality grant", "hospitality small business grant")
    score_irrelevant = _keyword_score("hospitality grant", "manufacturing export scheme")
    assert score_relevant > score_irrelevant


def test_keyword_score_empty_query_is_zero():
    assert _keyword_score("", "hospitality grant") == 0.0


def test_cosine_similarity_identical_vectors():
    assert _cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors():
    assert _cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_handles_zero_vector():
    assert _cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_retrieve_keyword_fallback_ranks_relevant_record_first(records):
    agent = RetrievalAgent(records)
    results = agent.retrieve("hospitality grant for small business", top_k=2)
    assert results
    assert results[0][0].record_id == "rec-1"


def test_retrieve_respects_top_k(records):
    agent = RetrievalAgent(records)
    results = agent.retrieve("grant business hospitality manufacturing", top_k=1)
    assert len(results) == 1


def test_retrieve_with_embedding_fn_uses_cosine_similarity(records):
    # Fake embedding function: encodes presence of "grant" / "pay" as a 2d vector.
    def fake_embed(text: str):
        text = text.lower()
        return [1.0 if "grant" in text else 0.0, 1.0 if "pay" in text else 0.0]

    agent = RetrievalAgent(records, embedding_fn=fake_embed)
    results = agent.retrieve("pay rates for employees", top_k=1)
    assert results[0][0].record_id == "rec-3"


def test_retrieve_returns_empty_for_no_records():
    agent = RetrievalAgent([])
    assert agent.retrieve("anything") == []


def test_retrieve_excludes_zero_score_records(records):
    agent = RetrievalAgent(records)
    results = agent.retrieve("zzzzznonsensequery", top_k=5)
    assert results == []


def test_retrieve_caches_record_embeddings(records):
    calls = []

    def counting_embed(text: str):
        calls.append(text)
        return [1.0]

    agent = RetrievalAgent(records, embedding_fn=counting_embed)
    agent.retrieve("first query")
    agent.retrieve("second query")

    # 2 query embeddings + one embedding per record (cached across calls).
    assert calls.count("first query") == 1
    assert calls.count("second query") == 1
    assert len(calls) == 2 + len(records)
