"""Public contract for the multi agent RAG query layer.

The website (and any other future caller: a CLI, a scheduled digest
email, etc.) should depend only on this module, never on the
internals of individual agents or on which LLM/vector store backend
is wired up. That lets the RAG implementation and the website be
built in parallel against a stable interface.

`build_default_orchestrator()` is the one factory function callers
should use. Today it returns `MockQueryOrchestrator`, which produces
plausible, clearly-labeled fake answers from the same data shapes
the real orchestrator will use, so the website can be built and
demoed before Bedrock is wired up. Once the real orchestrator
(backed by retrieval over normalized records + Bedrock) lands, this
factory switches to it and nothing above this module needs to
change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Citation:
    """One retrieved source backing part of an answer."""

    record_id: str
    title: str
    url: str
    source: str
    #: Short excerpt from the record backing this citation, when available.
    snippet: str | None = None


@dataclass
class QueryResult:
    """The result of answering one user question."""

    answer: str
    citations: list[Citation] = field(default_factory=list)
    #: Which internal agents contributed, for transparency in the UI
    #: (e.g. ["eligibility", "retrieval"]).
    agents_used: list[str] = field(default_factory=list)
    #: True when this came from a mock/demo backend rather than a
    #: real retrieval + generation pipeline. The website should show
    #: this to users so a demo answer is never mistaken for a real one.
    is_mock: bool = False


class QueryOrchestrator(ABC):
    """Entry point the website and other callers use to ask a question."""

    @abstractmethod
    def query(self, question: str) -> QueryResult:
        raise NotImplementedError


class MockQueryOrchestrator(QueryOrchestrator):
    """Deterministic canned-response orchestrator for local demo use.

    Recognizes a few keywords in the question so the demo UI has
    something plausible to show (grant-shaped answer vs a
    compliance-shaped answer) without needing real data, Bedrock
    access, or AWS credentials.
    """

    def query(self, question: str) -> QueryResult:
        q = question.lower()

        if any(word in q for word in ("award", "pay rate", "wage", "employee", "hire")):
            return QueryResult(
                answer=(
                    "This is a demo answer. Once the real pipeline is wired up, "
                    "this would summarize relevant Fair Work Modern Award pay "
                    "rates and employment conditions for your situation, with "
                    "citations to the source award documents."
                ),
                citations=[
                    Citation(
                        record_id="fair_work_mapd:demo",
                        title="[Demo] Modern Award pay rate example",
                        url="https://www.fwc.gov.au/document-search",
                        source="fair_work_mapd",
                    )
                ],
                agents_used=["compliance"],
                is_mock=True,
            )

        if any(word in q for word in ("tax", "gst", "payg", "ato", "super")):
            return QueryResult(
                answer=(
                    "This is a demo answer. Once the real pipeline is wired up, "
                    "this would summarize the relevant ATO guidance for your "
                    "small business tax or compliance question, with citations."
                ),
                citations=[
                    Citation(
                        record_id="ato:demo",
                        title="[Demo] ATO small business guidance example",
                        url="https://www.ato.gov.au/businesses-and-organisations/small-business",
                        source="ato",
                    )
                ],
                agents_used=["compliance"],
                is_mock=True,
            )

        return QueryResult(
            answer=(
                "This is a demo answer. Once the real pipeline is wired up, "
                "this would list grants you may be eligible for, with "
                "eligibility criteria, deadlines, and source links, based on "
                "what you told us about your business."
            ),
            citations=[
                Citation(
                    record_id="grantconnect:demo",
                    title="[Demo] Small Business Grant example",
                    url="https://www.grants.gov.au/Go/List",
                    source="grantconnect",
                )
            ],
            agents_used=["eligibility", "retrieval"],
            is_mock=True,
        )


def build_default_orchestrator() -> QueryOrchestrator:
    """Factory used by the website and other callers.

    Returns the mock orchestrator until the real one is implemented
    and wired in here; callers never need to change when that swap
    happens.
    """

    return MockQueryOrchestrator()
