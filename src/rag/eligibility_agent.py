"""EligibilityAgent: builds grant-eligibility framed answers.

Frames its answer around eligibility criteria, deadlines, and grant
amounts. Uses an injectable ``generate_fn`` (typically a bound
``BedrockClient.generate``) to produce the answer text; when none is
given, falls back to a deterministic, dependency free templated answer
built from the retrieved records so this class works, and is fully
testable, without any LLM at all.
"""

from __future__ import annotations

from typing import Callable, List, Optional, Tuple

from src.processing.schema import NormalizedRecord

GenerateFn = Callable[[str, str], str]


class EligibilityAgent:
    """Answers grant-eligibility questions from retrieved records."""

    name = "eligibility_agent"

    def __init__(self, generate_fn: Optional[GenerateFn] = None) -> None:
        self._generate_fn = generate_fn

    def answer(
        self,
        question: str,
        retrieved: List[Tuple[NormalizedRecord, float]],
    ) -> str:
        if not retrieved:
            return (
                "I could not find any grants matching your question. Try "
                "rephrasing with your industry, location, or business size."
            )
        if self._generate_fn is not None:
            context = self._build_context(retrieved)
            return self._generate_fn(question, context)
        return self._fallback_answer(retrieved)

    def _build_context(self, retrieved: List[Tuple[NormalizedRecord, float]]) -> str:
        lines = []
        for record, _score in retrieved:
            lines.append(
                f"- {record.title} (source: {record.source}): "
                f"eligibility={record.eligibility or 'not specified'}, "
                f"deadline={record.deadline or 'not specified'}, "
                f"amount={record.amount or 'not specified'}"
            )
        return "\n".join(lines)

    def _fallback_answer(
        self, retrieved: List[Tuple[NormalizedRecord, float]]
    ) -> str:
        top = retrieved[0][0]
        parts = [f"Based on the grants I found, {top.title} looks most relevant."]
        if top.eligibility:
            parts.append(f"Eligibility: {top.eligibility}.")
        if top.deadline:
            parts.append(f"Deadline: {top.deadline}.")
        if top.amount:
            parts.append(f"Amount: {top.amount}.")
        if len(retrieved) > 1:
            others = ", ".join(record.title for record, _score in retrieved[1:])
            parts.append(f"Other potentially relevant grants: {others}.")
        return " ".join(parts)
