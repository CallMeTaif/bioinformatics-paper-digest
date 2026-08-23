"""One-off: re-summarize already-published papers with the CURRENT prompt, so
existing entries benefit when the summarizer prompt improves. Re-fetches full
text, re-runs summarize + verify, and updates web/src/data/papers.json in place.

Safety: a paper's summary is replaced ONLY when the new one PASSES verification —
it never downgrades a good entry to a flagged one. Stable fields (slug,
date_posted, hosted PDF) are preserved.

Usage:
  python -m pipeline.resummarize <slug>    # one paper
  python -m pipeline.resummarize all       # every published paper
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

from . import config
from .sources.base import Paper
from .sources.fulltext import resolve_fulltext
from .llm import get_summarizer, get_verifier
from .publish.record import build_record

PAPERS = Path(__file__).resolve().parents[1] / "web" / "src" / "data" / "papers.json"


def _paper_from_record(r: dict) -> Paper:
    return Paper(
        doi=r.get("doi"), title=r.get("title", ""), authors=r.get("authors") or [],
        venue=r.get("venue"), publication_date=r.get("publication_date"),
        source=r.get("source", "openalex"), is_preprint=r.get("is_preprint", False),
        oa_status=r.get("oa_status"), license=r.get("license", "unknown"),
        original_url=r.get("original_url"), pdf_original_url=r.get("pdf_original_url"),
        hosted_pdf_path=r.get("hosted_pdf_path"), abstract=r.get("abstract"),
    )


def resummarize_one(r: dict, summarizer, verifier) -> dict | None:
    paper = _paper_from_record(r)
    with httpx.Client(timeout=45.0, follow_redirects=True) as c:
        resolve_fulltext(paper, client=c)
    text = paper.full_text or paper.abstract or r.get("abstract") or ""
    if not text:
        print("  no text available — skipping")
        return None
    summary = summarizer.summarize(title=paper.title, venue=paper.venue, text=text)
    verdict = verifier.verify(title=paper.title, source_text=text, summary=summary)
    fresh = build_record(paper, summary, verdict, verify_threshold=config.VERIFY_THRESHOLD)
    if fresh.get("status") != "published":
        print(f"  new summary flagged (score {verdict.score:.2f}) — keeping the old one")
        return None
    fresh["date_posted"] = r.get("date_posted")
    for k in ("hosted_pdf_path", "can_host"):
        if r.get(k) is not None:
            fresh[k] = r[k]
    print(f"  updated ✓  full_text={bool(paper.full_text)}  score {verdict.score:.2f}")
    return fresh


def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else ""
    if not target:
        print("usage: python -m pipeline.resummarize <slug|all>")
        return
    data = json.loads(PAPERS.read_text())
    summarizer, verifier = get_summarizer(), get_verifier()
    print(f"summarizer={summarizer.name}:{summarizer.model}  verifier={verifier.name}:{verifier.model}\n")
    changed = 0
    for i, r in enumerate(data):
        if target != "all" and r.get("slug") != target:
            continue
        print(f"[{r['title'][:64]}]")
        fresh = resummarize_one(r, summarizer, verifier)
        if fresh:
            data[i] = fresh
            changed += 1
    if changed:
        PAPERS.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"\nwrote {changed} updated paper(s) to papers.json")
    else:
        print("\nno changes written")


if __name__ == "__main__":
    main()
