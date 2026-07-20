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
from .sources.crossref import enrich_license
from .llm import get_summarizer, get_verifier, get_prescreener
from .publish import build_record, save_records, posted_keys, host_pdf
from .publish.record import slugify

# Preprints often lack fetchable full text while fresh; allow an abstract-only
# summary when the abstract is substantial enough to be worth summarizing.
MIN_ABSTRACT_CHARS = 600


def _recency(paper) -> float:
    """0..1, newer within a year scores higher."""
    if not paper.publication_date:
        return 0.0
    try:
        days = (_dt.date.today() - _dt.date.fromisoformat(paper.publication_date)).days
    except ValueError:
        return 0.0
    return max(0.0, 1.0 - days / 365.0)


def _score(paper) -> float:
    """Single blended rank (citations + recency). Still used for tie-breaks."""
    return ((paper.cited_by_count or 0) ** 0.5) + 3.0 * _recency(paper)


def blend_lanes(papers, n: int, *, fresh_ratio: float = 0.5):
    """Two-lane blend (spec §5): interleave an 'established' lane (peer-reviewed,
    ranked by citations then recency) with a 'fresh' lane (preprints, ranked by
    recency), so the pool mixes proven work with hot-off-the-press preprints.
    Without this, one recency-weighted pool lets recent journal papers crowd out
    every preprint before they're ever screened."""
    established = sorted(
        (p for p in papers if not p.is_preprint),
        key=lambda p: (p.cited_by_count or 0, _recency(p)), reverse=True,
    )
    fresh = sorted(
        (p for p in papers if p.is_preprint), key=_recency, reverse=True,
    )
    out, ei, fi = [], 0, 0
    want_fresh = max(1, round(n * fresh_ratio))
    while len(out) < n and (ei < len(established) or fi < len(fresh)):
        # roughly (1 - fresh_ratio) established : fresh_ratio fresh
        took = 0
        while took < 2 and ei < len(established) and len(out) < n:
            out.append(established[ei]); ei += 1; took += 1
        if fi < len(fresh) and len(out) < n and (len([p for p in out if p.is_preprint]) < want_fresh):
            out.append(fresh[fi]); fi += 1
    # top up from whichever lane still has entries
    for lane in (established[ei:], fresh[fi:]):
        for p in lane:
            if len(out) >= n:
                break
            out.append(p)
    return out[:n]


def run(*, limit: int, pool_per_term: int, mailto: str) -> int:
    print(f"=== pipeline run {_dt.datetime.now().isoformat(timespec='seconds')} "
          f"(DRY_RUN={config.DRY_RUN}) ===")

    # 1) discover (OpenAlex established lane + bioRxiv/medRxiv fresh lane), then
    #    blend the two lanes so preprints and proven work both get represented.
    papers = discover_all(mailto=mailto, per_term=pool_per_term)

    # Skip papers already in the library so re-runs don't re-summarize (or repost)
    # them — makes repeated/scheduled runs cheap and idempotent (spec §5).
    already = posted_keys()
    if already:
        fresh = [p for p in papers if p.doi not in already and p.title_key() not in already]
        print(f"[dedup] skipped {len(papers) - len(fresh)} already-published; "
              f"{len(fresh)} new candidates", flush=True)
        papers = fresh

    ranked = blend_lanes(papers, max(config.MAX_CANDIDATES, limit * 3))
    n_pre = sum(p.is_preprint for p in ranked[: config.MAX_CANDIDATES])
    print(f"[rank] two-lane blend: {n_pre} preprints in top {config.MAX_CANDIDATES}", flush=True)

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

    # 3b) Crossref: authoritative license for the copyright/host gate (few calls).
    with httpx.Client(timeout=20.0) as c:
        for paper in full_text_papers:
            enrich_license(paper, client=c, mailto=config.CROSSREF_MAILTO)
    hostable = sum(p.is_hostable for p in full_text_papers)
    print(f"[license] {hostable}/{len(full_text_papers)} papers host-eligible (rest link-only)",
          flush=True)

    # 3c) Host our own PDF copy — ONLY for redistribution-permitting licences.
    #     A dry run never uploads; failures fall back to link-only.
    if hostable and not config.DRY_RUN:
        with httpx.Client(timeout=60.0, follow_redirects=True) as c:
            for paper in full_text_papers:
                if not paper.is_hostable:
                    continue
                hosted = host_pdf(paper, slugify(paper.title, paper.doi), client=c)
                if hosted:
                    paper.hosted_pdf_path = hosted
                    print(f"[pdf-host] hosted {paper.title[:48]}", flush=True)

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
