"""Verifier schema, prompt, gate, and the Verifier protocol (spec §6).

The verifier receives the ORIGINAL paper text plus the DRAFT summary and checks
that every claim in the summary is supported by the source. It returns a
faithfulness verdict; the gate decides publish vs review-queue.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Protocol, Optional, Any

from .base import Summary, SUMMARY_FIELDS

VERDICTS = ("pass", "flag")


@dataclass
class Verdict:
    verdict: str = "flag"          # 'pass' | 'flag'
    score: float = 0.0             # 0..1 faithfulness/quality
    confidence: float = 0.0        # 0..1 how sure the verifier is
    unsupported_claims: list[str] = field(default_factory=list)
    notes: str = ""
    provider: str = ""
    model: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_fields(cls, data: dict[str, Any], *, provider: str, model: str) -> "Verdict":
        verdict = str(data.get("verdict", "flag")).strip().lower()
        if verdict not in VERDICTS:
            verdict = "flag"
        def _num(key: str) -> float:
            try:
                return max(0.0, min(1.0, float(data.get(key, 0.0))))
            except (TypeError, ValueError):
                return 0.0
        claims = data.get("unsupported_claims") or []
        if not isinstance(claims, list):
            claims = [str(claims)]
        return cls(
            verdict=verdict,
            score=_num("score"),
            confidence=_num("confidence"),
            unsupported_claims=[str(c) for c in claims][:20],
            notes=str(data.get("notes", "")).strip(),
            provider=provider,
            model=model,
        )


def passes_gate(v: Verdict, *, threshold: float) -> bool:
    """Auto-publish a high-confidence pass. The verifier is instructed to set
    verdict='flag' whenever a genuine unsupported claim exists, so the verdict +
    scores already encode that — we don't also hard-block on the (informational)
    claims list, which would over-flag on minor defensible paraphrases."""
    return (
        v.verdict == "pass"
        and v.score >= threshold
        and v.confidence >= threshold
    )


SYSTEM_PROMPT_VERIFY = (
    "You are a meticulous scientific fact-checker. You are given the full text "
    "of a research paper and an AI-generated summary of it. Your job is to "
    "judge whether the summary is FAITHFUL to the paper. "
    "A genuine problem (a hallucination) is a specific fact, number, method, "
    "dataset, or finding stated in the summary that is absent from — or "
    "contradicted by — the paper. Reasonable paraphrases, interpretive framing, "
    "and generic statements are NOT problems; do not flag them. "
    "Judge accuracy only, never writing style. "
    "If the summary contains one or more genuine hallucinations, set verdict to "
    "'flag'; otherwise set it to 'pass'."
)


def build_verify_prompt(*, title: str, source_text: str, summary: Summary,
                        max_chars: int = 120_000) -> str:
    body = (source_text or "")[:max_chars]
    summary_block = "\n".join(f"{f.upper()}: {getattr(summary, f)}" for f in SUMMARY_FIELDS)
    return "\n".join(
        [
            f"PAPER TITLE: {title}",
            "",
            "PAPER TEXT (source of truth, may be truncated):",
            body,
            "",
            "AI-GENERATED SUMMARY TO VERIFY:",
            summary_block,
            "",
            "Return a JSON object with EXACTLY these keys:",
            '  "verdict": "pass" or "flag" ("flag" if any genuine hallucination exists)',
            '  "score": number 0..1  (overall faithfulness)',
            '  "confidence": number 0..1  (how sure you are)',
            '  "unsupported_claims": array of short strings — ONLY genuine hallucinations (invented/contradicted specific facts, numbers, methods, or findings). Do NOT list defensible paraphrases or interpretation. Empty array if none.',
            '  "notes": one short sentence explaining the verdict',
            "",
            "Respond with only the JSON object.",
        ]
    )


class Verifier(Protocol):
    name: str
    model: str

    def verify(self, *, title: str, source_text: str, summary: Summary) -> Verdict:
        ...
