"""ComplianceAgent: builds pay-rate/tax-obligation framed answers.

Frames its answer around pay rates, awards, and tax/superannuation
obligations rather than eligibility criteria. Mirrors
:class:`~src.rag.eligibility_agent.EligibilityAgent`'s injectable
``generate_fn`` / deterministic fallback design.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from src.processing.schema import NormalizedRecord

GenerateFn = Callable[[str, str], str]


class ComplianceAgent:
    """Answers pay-rate/tax-obligation compliance questions from retrieved records."""

    name = "compliance_agent"

    def __init__(self, generate_fn: Optional[GenerateFn] = None) -> None:
        self._generate_fn = generate_fn

    def answer(
        self,
        question: str,
        retrieved: List[Tuple[NormalizedRecord, float]],
    ) -> str:
        if not retrieved:
            return (
                "I could not find compliance guidance matching your question. "
                "Try mentioning the award, industry, or obligation you're asking about."
            )
        if self._generate_fn is not None:
            context = self._build_context(retrieved)
            return self._generate_fn(question, context)
        return self._fallback_answer(retrieved)

    def _build_context(self, retrieved: List[Tuple[NormalizedRecord, float]]) -> str:
        lines = []
        for record, _score in retrieved:
            lines.append(
                f"- {record.title} (source: {record.source}): {record.description}"
            )
        return "\n".join(lines)

    def _fallback_answer(
        self, retrieved: List[Tuple[NormalizedRecord, float]]
    ) -> str:
        top = retrieved[0][0]
        parts = [
            f"For compliance obligations, {top.title} is the most relevant "
            f"guidance I found."
        ]
        if top.description:
            parts.append(top.description)
        if len(retrieved) > 1:
            others = ", ".join(record.title for record, _score in retrieved[1:])
            parts.append(f"Other relevant guidance: {others}.")
        parts.append(
            "This is general guidance, not tax or legal advice - confirm "
            "specifics with the ATO or Fair Work Commission before acting."
        )
        return " ".join(parts)
