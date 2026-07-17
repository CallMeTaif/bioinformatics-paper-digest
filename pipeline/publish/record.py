"""Turn a (Paper + Summary) into the persisted row shape (mirrors papers table).

Also enforces the PDF-hosting decision: hosted_pdf_path stays null in Phase 1
(we link, don't host yet), but can_host records whether the license *would*
allow hosting, so Phase 2 can act on it without re-deriving the rule.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Optional

from ..sources.base import Paper
from ..llm.base import Summary
from ..topics import tag_for_text


def slugify(title: str, doi: Optional[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (title or "paper").lower()).strip("-")[:60]
    # short stable suffix from DOI (or title) to guarantee uniqueness
    seed = (doi or title or "").encode("utf-8")
    suffix = hashlib.sha1(seed).hexdigest()[:6]
    return f"{base}-{suffix}".strip("-")


def _difficulty(paper: Paper) -> str:
    """Light Phase 1 heuristic; a real classifier is a later refinement."""
    text = f"{paper.title} {paper.abstract or ''}".lower()
    if any(w in text for w in ("review", "perspective", "primer", "introduction to")):
        return "intro"
    if paper.is_preprint or any(w in text for w in ("theorem", "manifold", "stochastic")):
        return "advanced"
    return "intermediate"


def build_record(paper: Paper, summary: Summary) -> dict[str, Any]:
    tag, accent = tag_for_text(f"{paper.title} {paper.abstract or ''}")
    return {
        "slug": slugify(paper.title, paper.doi),
        "doi": paper.doi,
        "title": paper.title,
        "authors": paper.authors,
        "venue": paper.venue,
        "publication_date": paper.publication_date,
        "source": paper.source,
        "is_preprint": paper.is_preprint,
        "oa_status": paper.oa_status,
        "license": paper.license,
        "original_url": paper.original_url,
        "pdf_original_url": paper.pdf_original_url,
        "hosted_pdf_path": None,           # Phase 1 links only; never host yet
        "can_host": paper.is_hostable,     # license verdict for Phase 2
        "abstract": paper.abstract,
        "subfield_tags": [tag],
        "tag_accent": accent,              # nucleotide color slot for the UI
        "difficulty_level": _difficulty(paper),
        "summary": summary.to_dict(),
        "summary_provider": summary.provider,
        "used_full_text": bool(paper.full_text),
        "verifier_score": None,            # Phase 2
        "verifier_verdict": None,          # Phase 2
        "status": "published",
    }
