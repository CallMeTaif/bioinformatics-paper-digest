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
from .sources.discovery import discover_all
from .sources.fulltext import resolve_fulltext
from .llm import get_summarizer, get_verifier, get_prescreener
from .publish import build_record, save_records

# Preprints often lack fetchable full text while fresh; allow an abstract-only
# summary when the abstract is substantial enough to be worth summarizing.
MIN_ABSTRACT_CHARS = 600


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

    # 1) discover (OpenAlex established lane + bioRxiv/medRxiv fresh lane), then rank
    papers = discover_all(mailto=mailto, per_term=pool_per_term)
    ranked = sorted(papers, key=_score, reverse=True)

    # 2) abstract pre-screen — a cheap model drops off-topic/weak papers BEFORE we
    #    pay to fetch full text and summarize. Runs on the top MAX_CANDIDATES.
    if config.PRESCREEN_ENABLED:
        pool = ranked[: config.MAX_CANDIDATES]
        screener = get_prescreener()
        print(f"[prescreen] {screener.name}:{screener.model} screening {len(pool)} abstracts",
              flush=True)
        try:
            decisions = screener.screen(pool)
        except Exception as e:  # noqa: BLE001 — fail open: a screen failure keeps all
            print(f"[prescreen] failed ({type(e).__name__}: {str(e)[:80]}) — keeping all", flush=True)
            decisions = None
        if decisions:
            kept = [p for p, d in zip(pool, decisions) if d.keep]
            dropped = len(pool) - len(kept)
            print(f"[prescreen] kept {len(kept)}, dropped {dropped} off-topic/weak", flush=True)
            # Preserve rank order among kept; append any un-screened tail as fallback.
            ranked = kept + ranked[config.MAX_CANDIDATES:]

    # 3) resolve full text; keep papers we can summarize (full text, or a
    #    substantial abstract for fresh preprints without fetchable full text).
    full_text_papers = []
    with httpx.Client(timeout=45.0, follow_redirects=True) as c:
        for paper in ranked:
            resolve_fulltext(paper, client=c)
            has_ft = bool(paper.full_text)
            has_abs = bool(paper.abstract) and len(paper.abstract) >= MIN_ABSTRACT_CHARS
            if has_ft or has_abs:
                full_text_papers.append(paper)
                src = f"{len(paper.full_text):>6}c full" if has_ft else f"{len(paper.abstract):>6}c abstract"
                pre = " [preprint]" if paper.is_preprint else ""
                print(f"[fulltext] OK  ({src})  {paper.title[:52]}{pre}")
            if len(full_text_papers) >= limit:
                break
    print(f"[fulltext] {len(full_text_papers)} summarizable papers (target {limit})")

    if not full_text_papers:
        print("[run] nothing summarizable this run — nothing to publish.")
        return 0

    # 4) summarize -> verify -> gate (one failure/timeout must not sink the batch)
    summarizer = get_summarizer()
    verifier = get_verifier()
    print(f"[summarize] provider: {summarizer.name}:{summarizer.model}", flush=True)
    print(f"[verify]    provider: {verifier.name}:{verifier.model} "
          f"(threshold {config.VERIFY_THRESHOLD})", flush=True)
    records = []
    n_pub = n_flag = 0
    for i, paper in enumerate(full_text_papers, 1):
        text = paper.full_text or paper.abstract or ""
        print(f"[{i}/{len(full_text_papers)}] {paper.title[:55]} ...", flush=True)
        try:
            summary = summarizer.summarize(title=paper.title, venue=paper.venue, text=text)
        except Exception as e:  # noqa: BLE001
            print(f"    SKIPPED summarize ({type(e).__name__}: {str(e)[:100]})", flush=True)
            continue
        try:
            verdict = verifier.verify(title=paper.title, source_text=text, summary=summary)
        except Exception as e:  # noqa: BLE001 — a verify failure flags, never auto-publishes
            print(f"    verify failed ({type(e).__name__}: {str(e)[:80]}) — flagging", flush=True)
            from .llm import Verdict
            verdict = Verdict(verdict="flag", notes=f"verify error: {type(e).__name__}",
                              provider=verifier.name, model=verifier.model)
        rec = build_record(paper, summary, verdict, verify_threshold=config.VERIFY_THRESHOLD)
        records.append(rec)
        if rec["status"] == "published":
            n_pub += 1
        else:
            n_flag += 1
        print(f"    {rec['status']:9} verdict={verdict.verdict} "
              f"score={verdict.score:.2f} conf={verdict.confidence:.2f}", flush=True)

    # 5) publish (published + flagged both persisted; the site shows only published)
    added = save_records(records)
    print(f"=== done: {added} record(s) written — {n_pub} published, {n_flag} flagged for review ===")
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
