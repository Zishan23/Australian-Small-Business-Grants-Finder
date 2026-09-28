
from src.processing.schema import NormalizedRecord
from src.rag.orchestrator import RagQueryOrchestrator, classify_question


def make_record(**overrides) -> NormalizedRecord:
    defaults = dict(
        record_id="rec-1",
        source="grantconnect",
        title="Hospitality Small Business Grant",
        description="Grant for hospitality businesses.",
        eligibility="Fewer than 20 employees",
        amount="$10,000",
        deadline="2026-12-01",
        category="hospitality",
        state_or_territory="VIC",
        url="https://example.com/rec-1",
        ingested_at="2026-09-01T12:00:00",
    )
    defaults.update(overrides)
    return NormalizedRecord(**defaults)


def test_classify_question_eligibility():
    assert classify_question("What grants am I eligible for?") == "eligibility"


def test_classify_question_compliance():
    assert (
        classify_question("What pay rate do I need to pay employees under Fair Work?")
        == "compliance"
    )


def test_classify_question_mixed_when_both_present():
    q = "Am I eligible for any grants and what tax obligations apply?"
    assert classify_question(q) == "mixed"


def test_classify_question_mixed_when_neither_present():
    assert classify_question("Tell me about small businesses in Victoria") == "mixed"


def test_orchestrator_routes_to_eligibility_agent_only():
    record = make_record()
    orchestrator = RagQueryOrchestrator(records=[record])
    result = orchestrator.query("What grants am I eligible for as a hospitality business?")

    assert result.is_mock is False
    assert "eligibility_agent" in result.agents_used
    assert "compliance_agent" not in result.agents_used
    assert result.citations
    assert result.citations[0].record_id == "rec-1"
    assert result.citations[0].url == record.url


def test_orchestrator_routes_to_compliance_agent_only():
    record = make_record(
        record_id="rec-2",
        title="Minimum Wage Guidance",
        description="Pay rate guidance for hospitality staff.",
        category="compliance",
        eligibility=None,
        amount=None,
        deadline=None,
        url="https://example.com/rec-2",
    )
    orchestrator = RagQueryOrchestrator(records=[record])
    result = orchestrator.query("What pay rate and tax obligations apply to my employees?")

    assert "compliance_agent" in result.agents_used
    assert "eligibility_agent" not in result.agents_used


def test_orchestrator_mixed_question_uses_both_agents():
    records = [
        make_record(record_id="rec-1"),
        make_record(
            record_id="rec-2",
            title="Minimum Wage Guidance",
            description="Pay rate guidance.",
            category="compliance",
            eligibility=None,
            amount=None,
            deadline=None,
            url="https://example.com/rec-2",
        ),
    ]
    orchestrator = RagQueryOrchestrator(records=records)
    result = orchestrator.query("Am I eligible for grants and what are my tax obligations?")
    assert "eligibility_agent" in result.agents_used
    assert "compliance_agent" in result.agents_used


def test_orchestrator_no_matching_records_returns_result_without_citations():
    orchestrator = RagQueryOrchestrator(records=[])
    result = orchestrator.query("What grants am I eligible for?")
    assert result.citations == []
    assert result.is_mock is False


def test_orchestrator_citations_built_from_retrieved_records():
    record = make_record()
    orchestrator = RagQueryOrchestrator(records=[record])
    result = orchestrator.query("What grants am I eligible for as a hospitality business?")

    citation = result.citations[0]
    assert citation.source == record.source
    assert citation.title == record.title
    assert citation.url == record.url
    assert citation.record_id == record.record_id


def test_orchestrator_injects_bedrock_client_for_embed_and_generate():
    generate_calls = []
    embed_calls = []

    class FakeBedrockClient:
        def embed(self, text):
            embed_calls.append(text)
            return [1.0]

        def generate(self, question, context):
            generate_calls.append((question, context))
            return "fake generated answer"

    record = make_record()
    orchestrator = RagQueryOrchestrator(records=[record], bedrock_client=FakeBedrockClient())
    result = orchestrator.query("What grants am I eligible for?")

    assert "fake generated answer" in result.answer
    assert generate_calls
    assert embed_calls
