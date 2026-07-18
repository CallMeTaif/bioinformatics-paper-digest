"""Abstract pre-screen (spec §5): a CHEAP model reads only the abstracts of the
top candidates and keeps the genuinely substantive, on-topic bioinformatics ones
— so we never pay the summarizer/verifier to process weak or off-topic papers.

One batched call rates all candidates at once (cheap).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Optional

from ..sources.base import Paper
from ..topics import SCOPE_DESCRIPTION, INCLUDE_KEYWORDS


@dataclass
class ScreenDecision:
    keep: bool = True
    score: float = 0.5      # 0..1 substance + on-topic relevance
    reason: str = ""


def _clamp(x) -> float:
    try:
        return max(0.0, min(1.0, float(x)))
    except (TypeError, ValueError):
        return 0.0


class Prescreener(Protocol):
    name: str
    model: str

    def screen(self, papers: list[Paper]) -> list[ScreenDecision]:
        """Return one decision per input paper, in the same order."""
        ...


class MockPrescreener:
    """Offline keyword screen — keeps a paper if its title/abstract mentions any
    in-scope term. Gives real filtering value without a key."""

    name = "mock"
    model = "keyword"

    def screen(self, papers: list[Paper]) -> list[ScreenDecision]:
        needles = [k.lower() for k in INCLUDE_KEYWORDS]
        out = []
        for p in papers:
            blob = f"{p.title} {p.abstract or ''}".lower()
            hits = sum(1 for n in needles if n in blob)
            keep = hits > 0
            out.append(ScreenDecision(
                keep=keep,
                score=min(1.0, hits / 3.0),
                reason=f"{hits} in-scope keyword match(es)" if keep else "no in-scope keywords",
            ))
        return out


def build_prescreen_prompt(papers: list[Paper], *, abstract_chars: int = 1500) -> str:
    lines = [
        "You are screening candidate papers for a digest with this scope:",
        SCOPE_DESCRIPTION,
        "",
        "For each candidate, decide whether it is genuinely substantive research or "
        "a useful methods/review paper that fits the scope. Drop off-topic papers, "
        "thin/marketing pieces, and papers only tangentially related to bioinformatics.",
        "",
        "CANDIDATES:",
    ]
    for i, p in enumerate(papers):
        abst = (p.abstract or "(no abstract)")[:abstract_chars]
        lines.append(f"[{i}] TITLE: {p.title}\n    VENUE: {p.venue or '?'}\n    ABSTRACT: {abst}")
    lines += [
        "",
        'Return a JSON object: {"results": [{"index": int, "keep": true/false, '
        '"score": 0..1 relevance, "reason": "short"}]} with one entry per candidate index.',
        "Respond with only the JSON object.",
    ]
    return "\n".join(lines)


class GeminiPrescreener:
    def __init__(self, *, api_key: str, model: str):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required for the Gemini pre-screen")
        from google import genai  # type: ignore

        self._genai = genai
        self._client = genai.Client(api_key=api_key)
        self.name = "google"
        self.model = model

    def screen(self, papers: list[Paper]) -> list[ScreenDecision]:
        from google.genai import types  # type: ignore
        from .gemini import _parse_json_object, timeout_for_text

        if not papers:
            return []
        prompt = build_prescreen_prompt(papers)
        resp = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
                http_options=types.HttpOptions(timeout=int(timeout_for_text(prompt) * 1000)),
            ),
        )
        data = _parse_json_object(resp.text or "")
        results = data.get("results") if isinstance(data, dict) else None
        # Default to keep-all if the model returns something unexpected (fail open,
        # since the summarizer+verifier are the real quality gate downstream).
        decisions = [ScreenDecision(keep=True, score=0.5, reason="unparsed") for _ in papers]
        if isinstance(results, list):
            for r in results:
                try:
                    idx = int(r.get("index"))
                except (TypeError, ValueError):
                    continue
                if 0 <= idx < len(decisions):
                    decisions[idx] = ScreenDecision(
                        keep=bool(r.get("keep", True)),
                        score=_clamp(r.get("score", 0.5)),
                        reason=str(r.get("reason", ""))[:200],
                    )
        return decisions
