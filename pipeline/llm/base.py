"""Summary schema, prompt, and the Summarizer protocol.

The fixed 7-section template (spec §6) is the contract every provider must fill.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Protocol, Optional, Any

# Order matters: this is the on-page reading order and the JSON key order.
SUMMARY_FIELDS = [
    "tldr",         # one line
    "problem",      # problem / question
    "methods",      # methods
    "findings",     # key findings
    "why",          # why it matters
    "limitations",  # limitations
    "takeaway",     # takeaway
]

_FIELD_LABELS = {
    "tldr": "TL;DR — ONE sentence naming the single most important CONCRETE finding (not just the topic)",
    "problem": "Problem / question — the specific gap or question the paper tackles, and why it's hard",
    "methods": "Methods — the actual approach: name the key techniques, tools, models, datasets, organisms, and the scale (e.g. sample sizes, dataset size)",
    "findings": "Key findings — the concrete results: the specific outcomes with the actual numbers and named entities (genes, pathways, metrics) the paper reports, not a vague gist (2-4 sentences)",
    "why": "Why it matters — the specific advance or real-world / scientific implication",
    "limitations": "Limitations — the specific caveats, biases, or constraints the paper itself notes",
    "takeaway": "Takeaway — the one concrete thing a reader should remember",
}


@dataclass
class Summary:
    tldr: str = ""
    problem: str = ""
    methods: str = ""
    findings: str = ""
    why: str = ""
    limitations: str = ""
    takeaway: str = ""
    # classification the model returns alongside the summary (it has already read
    # the paper, so this is far better than keyword matching and costs nothing extra)
    topic: str = ""       # one of topics.CANONICAL_TAGS
    difficulty: str = ""  # one of topics.DIFFICULTY_LEVELS
    # provenance so the site/DB can show which model wrote it
    model: str = ""
    provider: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def is_complete(self) -> bool:
        return all(getattr(self, f).strip() for f in SUMMARY_FIELDS)

    @classmethod
    def from_fields(cls, data: dict[str, Any], *, provider: str, model: str) -> "Summary":
        from ..topics import is_canonical_tag, DIFFICULTY_LEVELS

        kwargs = {f: str(data.get(f, "")).strip() for f in SUMMARY_FIELDS}
        # Only accept classifications from the closed vocabularies; anything else
        # is dropped so the caller falls back to the heuristic.
        topic = str(data.get("topic", "")).strip().lower()
        difficulty = str(data.get("difficulty", "")).strip().lower()
        return cls(
            provider=provider,
            model=model,
            topic=topic if is_canonical_tag(topic) else "",
            difficulty=difficulty if difficulty in DIFFICULTY_LEVELS else "",
            **kwargs,
        )


SYSTEM_PROMPT = (
    "You are a careful scientific writer creating a faithful, plain-language "
    "summary of a research paper for a technically literate but non-specialist "
    "audience.\n"
    "FAITHFULNESS: Summarize ONLY what the paper states. Never add facts, numbers, "
    "or claims that are not in the provided text. If the paper does not address a "
    "section, say so briefly rather than inventing content. Write in your own words "
    "— do not copy sentences verbatim.\n"
    "SPECIFICITY: Be concrete, not generic. Name the actual methods, tools, "
    "datasets, organisms, and genes / proteins / pathways involved, and include the "
    "key quantitative results (sample sizes, effect sizes, accuracy, fold-changes, "
    "p-values) exactly as the paper reports them. A reader should come away knowing "
    "what the paper actually found and how — not merely its topic. Avoid vague "
    "filler such as 'various methods', 'significant improvements', or 'important "
    "implications': state WHICH methods, HOW MUCH improvement, and WHICH "
    "implications. Whenever you must choose, prefer a specific detail from the paper "
    "over a general statement."
)


def build_user_prompt(*, title: str, venue: Optional[str], text: str,
                      max_chars: int = 120_000) -> str:
    """Assemble the summarization prompt. text is full text (preferred) or abstract."""
    body = text[:max_chars]
    lines = [
        f"TITLE: {title}",
        f"VENUE: {venue or 'unknown'}",
        "",
        "PAPER TEXT (may be truncated):",
        body,
        "",
        "Return a JSON object with EXACTLY these string keys, no others:",
    ]
    for f in SUMMARY_FIELDS:
        lines.append(f'  "{f}": {_FIELD_LABELS[f]}')
    from ..topics import CANONICAL_TAGS, DIFFICULTY_LEVELS

    lines.append(f'  "topic": the single best-fitting subfield, chosen ONLY from '
                 f'this list: {", ".join(CANONICAL_TAGS)}')
    lines.append(f'  "difficulty": how much background a reader needs, one of: '
                 f'{", ".join(DIFFICULTY_LEVELS)} '
                 f'("intro" = accessible review/primer, "advanced" = assumes '
                 f'specialist knowledge)')
    lines.append("")
    lines.append("Respond with only the JSON object.")
    return "\n".join(lines)


class Summarizer(Protocol):
    """Every provider implements this. name/model are for provenance."""

    name: str
    model: str

    def summarize(self, *, title: str, venue: Optional[str], text: str) -> Summary:
        ...
