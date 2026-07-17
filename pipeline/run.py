"""Pipeline entrypoint (Phase 1).

  discover (OpenAlex) -> enrich full text (Europe PMC) -> keep full-text papers
  -> summarize -> build records -> publish (local JSON or Supabase)

Phase 1 has no verifier and no LLM pre-screen yet; those arrive in Phase 2.
Because Europe PMC full-text yield is only ~30%, we discover a larger pool and
filter down to papers that actually have full text before summarizing.
"""
from __future__ import annotations

import argparse
import datetime as _dt

import httpx

from . import config
from .sources.openalex import discover, DEFAULT_SEED_TERMS
from .sources.europepmc import enrich_fulltext
from .llm import get_summarizer
from .publish import build_record, save_records


def _score(paper) -> float:
    """Simple blended rank: log-ish citation weight + recency bonus."""
    cites = paper.cited_by_count or 0
    recency = 0.0
    if paper.publication_date:
        try:
            days = (_dt.date.today() - _dt.date.fromisoformat(paper.publication_date)).days
            recency = max(0.0, 1.0 - days / 365.0)  # newer within a year scores higher
        except ValueError:
            pass
    return (cites ** 0.5) + 3.0 * recency


def run(*, limit: int, pool_per_term: int, mailto: str) -> int:
    print(f"=== pipeline run {_dt.datetime.now().isoformat(timespec='seconds')} "
          f"(DRY_RUN={config.DRY_RUN}) ===")

    # 1) discover
    papers = discover(DEFAULT_SEED_TERMS, per_term=pool_per_term, mailto=mailto)
    print(f"[discover] {len(papers)} unique open-access candidates")

    # 2) enrich with full text; keep only those that have usable full text
    full_text_papers = []
    with httpx.Client(timeout=45.0) as c:
        # Rank first so we try the most promising papers and can stop early.
        for paper in sorted(papers, key=_score, reverse=True):
            enrich_fulltext(paper, client=c)
            if paper.full_text:
                full_text_papers.append(paper)
                print(f"[fulltext] OK  ({len(paper.full_text):>6}c)  {paper.title[:60]}")
            if len(full_text_papers) >= limit:
                break
    print(f"[fulltext] {len(full_text_papers)} papers with usable full text (target {limit})")

    if not full_text_papers:
        print("[run] no full-text papers this run — nothing to publish.")
        return 0

    # 3) summarize (one failure/timeout must not sink the whole batch)
    summarizer = get_summarizer()
    print(f"[summarize] using provider: {summarizer.name}:{summarizer.model}", flush=True)
    records = []
    for i, paper in enumerate(full_text_papers, 1):
        print(f"[summarize] {i}/{len(full_text_papers)} {paper.title[:55]} ...", flush=True)
        try:
            summary = summarizer.summarize(
                title=paper.title, venue=paper.venue,
                text=paper.full_text or paper.abstract or "",
            )
        except Exception as e:  # noqa: BLE001 — keep going on any per-paper error
            print(f"[summarize]   SKIPPED ({type(e).__name__}: {str(e)[:120]})", flush=True)
            continue
        records.append(build_record(paper, summary))
        print(f"[summarize]   ok", flush=True)

    # 4) publish
    added = save_records(records)
    print(f"=== done: {added} new record(s) ===")
    return added


def main() -> None:
    ap = argparse.ArgumentParser(description="Bioinformatics Paper Digest pipeline")
    ap.add_argument("--limit", type=int, default=config.PUBLISH_PER_RUN,
                    help="how many papers to publish this run")
    ap.add_argument("--pool", type=int, default=8,
                    help="OpenAlex results per seed term (bigger pool = more full-text hits)")
    ap.add_argument("--mailto", default=config.OPENALEX_MAILTO)
    args = ap.parse_args()
    run(limit=args.limit, pool_per_term=args.pool, mailto=args.mailto)


if __name__ == "__main__":
    main()
