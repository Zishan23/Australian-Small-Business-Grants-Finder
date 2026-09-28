
from src.processing.schema import NormalizedRecord
from src.rag.compliance_agent import ComplianceAgent
from src.rag.eligibility_agent import EligibilityAgent


def make_record(**overrides) -> NormalizedRecord:
    defaults = dict(
        record_id="rec-1",
        source="ato",
        title="Minimum Wage Guidance",
        description="Guidance on minimum pay rates for hospitality staff.",
        eligibility=None,
        amount=None,
        deadline=None,
        category="compliance",
        state_or_territory=None,
        url="https://example.com/rec-1",
        ingested_at="2026-09-01T12:00:00",
    )
    defaults.update(overrides)
    return NormalizedRecord(**defaults)


def test_eligibility_agent_uses_injected_generate_fn():
    calls = []

    def fake_generate(question, context):
        calls.append((question, context))
        return "generated eligibility answer"

    agent = EligibilityAgent(generate_fn=fake_generate)
    record = make_record(
        title="Hospitality Grant",
        eligibility="Fewer than 20 employees",
        deadline="2026-12-01",
        amount="$5,000",
    )
    answer = agent.answer("Am I eligible?", [(record, 1.0)])

    assert answer == "generated eligibility answer"
    assert calls[0][0] == "Am I eligible?"
    assert "Hospitality Grant" in calls[0][1]


def test_eligibility_agent_fallback_without_generate_fn():
    agent = EligibilityAgent()
    record = make_record(
        title="Hospitality Grant",
        eligibility="Fewer than 20 employees",
        deadline="2026-12-01",
        amount="$5,000",
    )
    answer = agent.answer("Am I eligible?", [(record, 1.0)])
    assert "Hospitality Grant" in answer
    assert "Fewer than 20 employees" in answer
    assert "$5,000" in answer


def test_eligibility_agent_no_records_returns_helpful_message():
    agent = EligibilityAgent()
    answer = agent.answer("Am I eligible?", [])
    assert "could not find" in answer.lower()


def test_eligibility_agent_fallback_lists_other_records():
    agent = EligibilityAgent()
    top = make_record(record_id="rec-1", title="Hospitality Grant")
    other = make_record(record_id="rec-2", title="Manufacturing Grant")
    answer = agent.answer("Am I eligible?", [(top, 1.0), (other, 0.5)])
    assert "Manufacturing Grant" in answer


def test_compliance_agent_uses_injected_generate_fn():
    def fake_generate(question, context):
        return "generated compliance answer"

    agent = ComplianceAgent(generate_fn=fake_generate)
    record = make_record(title="Minimum Wage Guidance")
    answer = agent.answer("What pay rate applies?", [(record, 1.0)])
    assert answer == "generated compliance answer"


def test_compliance_agent_fallback_without_generate_fn():
    agent = ComplianceAgent()
    record = make_record(
        title="Minimum Wage Guidance", description="Award pay rates for hospitality."
    )
    answer = agent.answer("What pay rate applies?", [(record, 1.0)])
    assert "Minimum Wage Guidance" in answer
    assert "Award pay rates for hospitality." in answer


def test_compliance_agent_no_records_returns_helpful_message():
    agent = ComplianceAgent()
    answer = agent.answer("What pay rate applies?", [])
    assert "could not find" in answer.lower()
