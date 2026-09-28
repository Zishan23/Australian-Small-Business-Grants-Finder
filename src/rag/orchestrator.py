"""RagQueryOrchestrator: the real QueryOrchestrator implementation.

Classifies each question as eligibility, compliance, or mixed with a
small heuristic (``classify_question``), retrieves relevant
NormalizedRecords via :class:`~src.rag.retrieval.RetrievalAgent`, routes
to :class:`~src.rag.eligibility_agent.EligibilityAgent` and/or
:class:`~src.rag.compliance_agent.ComplianceAgent`, and assembles a real
:class:`~src.rag.interface.QueryResult` (``is_mock=False``) with
citations built from the retrieved records.

Any Bedrock call (embeddings or generation) is made only through an
injected :class:`~src.rag.bedrock_client.BedrockClient`, so this class -
and every test of it - never touches AWS.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from src.processing.schema import NormalizedRecord
from src.rag.bedrock_client import BedrockClient
from src.rag.compliance_agent import ComplianceAgent
from src.rag.eligibility_agent import EligibilityAgent
from src.rag.interface import Citation, QueryOrchestrator, QueryResult
from src.rag.retrieval import RetrievalAgent

# Simple keyword based routing. Deliberately small and testable in
# isolation (see classify_question) rather than baked into the
# orchestrator, so the heuristic can be swapped for something smarter
# (e.g. a Bedrock classification call) later without touching routing
# or answer-assembly logic.
ELIGIBILITY_KEYWORDS = {
    "grant",
    "grants",
    "eligible",
    "eligibility",
    "qualify",
    "qualifies",
    "funding",
    "application",
    "fund",
    "program",
    "scheme",
}
COMPLIANCE_KEYWORDS = {
    "tax",
    "taxes",
    "ato",
    "compliance",
    "pay",
    "wage",
    "wages",
    "award",
    "fair work",
    "super",
    "superannuation",
    "obligation",
    "obligations",
    "employee",
    "employer",
    "payroll",
}


def classify_question(question: str) -> str:
    """Classify a question as ``"eligibility"``, ``"compliance"``, or ``"mixed"``.

    Counts keyword hits against two fixed sets and picks whichever side
    has hits and the other doesn't. When both sides have hits, or
    neither does, this returns ``"mixed"`` - either the question
    genuinely spans both concerns, or it's too generic to tell, and in
    both cases giving both agents a chance to answer is the safer
    default over silently picking one.
    """
    text = question.lower()
    eligibility_hit = any(keyword in text for keyword in ELIGIBILITY_KEYWORDS)
    compliance_hit = any(keyword in text for keyword in COMPLIANCE_KEYWORDS)

    if eligibility_hit and not compliance_hit:
        return "eligibility"
    if compliance_hit and not eligibility_hit:
        return "compliance"
    return "mixed"


class RagQueryOrchestrator(QueryOrchestrator):
    """Real, Bedrock backed (when configured) QueryOrchestrator implementation."""

    def __init__(
        self,
        records: Sequence[NormalizedRecord],
        bedrock_client: Optional[BedrockClient] = None,
        retrieval_agent: Optional[RetrievalAgent] = None,
        eligibility_agent: Optional[EligibilityAgent] = None,
        compliance_agent: Optional[ComplianceAgent] = None,
        top_k: int = 5,
    ) -> None:
        """Build the orchestrator.

        ``bedrock_client`` is optional and injectable: pass a real
        ``BedrockClient`` in production to get embedding based retrieval
        and LLM generated answers, a fake/mock in tests, or omit it
        entirely to fall back to the dependency free keyword retrieval
        and templated answers (see retrieval.py's module docstring).
        Passing pre-built ``retrieval_agent``/``eligibility_agent``/
        ``compliance_agent`` instances overrides ``bedrock_client`` for
        that component, which is mainly useful in tests.
        """
        embedding_fn = bedrock_client.embed if bedrock_client is not None else None
        generate_fn = bedrock_client.generate if bedrock_client is not None else None

        self._retrieval_agent = retrieval_agent or RetrievalAgent(
            records, embedding_fn=embedding_fn
        )
        self._eligibility_agent = eligibility_agent or EligibilityAgent(generate_fn)
        self._compliance_agent = compliance_agent or ComplianceAgent(generate_fn)
        self._top_k = top_k

    def query(self, question: str) -> QueryResult:
        classification = classify_question(question)
        retrieved = self._retrieval_agent.retrieve(question, top_k=self._top_k)

        agents_used: List[str] = ["retrieval_agent"]
        answer_parts: List[str] = []

        if classification in ("eligibility", "mixed"):
            answer_parts.append(self._eligibility_agent.answer(question, retrieved))
            agents_used.append(self._eligibility_agent.name)
        if classification in ("compliance", "mixed"):
            answer_parts.append(self._compliance_agent.answer(question, retrieved))
            agents_used.append(self._compliance_agent.name)

        answer = (
            "\n\n".join(answer_parts)
            if answer_parts
            else "I could not find relevant information for that question."
        )

        citations = [
            Citation(
                source=record.source,
                title=record.title,
                url=record.url,
                snippet=(record.description or "")[:280] or None,
                record_id=record.record_id,
            )
            for record, _score in retrieved
        ]

        return QueryResult(
            answer=answer,
            citations=citations,
            agents_used=agents_used,
            is_mock=False,
        )
