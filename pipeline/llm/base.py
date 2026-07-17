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
    "tldr": "TL;DR (one sentence)",
    "problem": "Problem / question",
    "methods": "Methods",
    "findings": "Key findings",
    "why": "Why it matters",
    "limitations": "Limitations",
    "takeaway": "Takeaway",
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
        kwargs = {f: str(data.get(f, "")).strip() for f in SUMMARY_FIELDS}
        return cls(provider=provider, model=model, **kwargs)


SYSTEM_PROMPT = (
    "You are a careful scientific writer creating a faithful, plain-language "
    "summary of a bioinformatics research paper for a technically literate but "
    "non-specialist audience. Summarize ONLY what the paper states. Do not add "
    "facts, numbers, or claims that are not in the provided text. If the paper "
    "does not address a section, say so briefly rather than inventing content. "
    "Write in your own words — do not copy sentences verbatim."
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
    lines.append("")
    lines.append("Respond with only the JSON object.")
    return "\n".join(lines)


class Summarizer(Protocol):
    """Every provider implements this. name/model are for provenance."""

    name: str
    model: str

    def summarize(self, *, title: str, venue: Optional[str], text: str) -> Summary:
        ...
