"""Combine all discovery sources into one deduplicated candidate pool.

Two lanes (spec §5): OpenAlex is the 'established' lane (has citations); bioRxiv
and medRxiv are the 'fresh' preprint lane. On a DOI collision we collapse the
preprint into the published version (prefer the peer-reviewed record).
"""
from __future__ import annotations

from typing import Optional

import httpx

from .base import Paper
from .openalex import discover as discover_openalex, DEFAULT_SEED_TERMS
from .rxiv import discover as discover_rxiv


def _prefer(a: Paper, b: Paper) -> Paper:
    """Pick the better of two duplicates: peer-reviewed over preprint, then
    more-cited, then the one that has a DOI."""
    if a.is_preprint != b.is_preprint:
        return a if not a.is_preprint else b
    if (a.cited_by_count or 0) != (b.cited_by_count or 0):
        return a if (a.cited_by_count or 0) > (b.cited_by_count or 0) else b
    return a if a.doi else b


def _merge(into: dict[str, Paper], papers: list[Paper]) -> None:
    # Key by normalized TITLE so versioned duplicates (same title, different
    # per-version DOIs — e.g. Zenodo/bioRxiv versions) collapse into one entry.
    for p in papers:
        key = p.title_key()
        existing = into.get(key)
        into[key] = p if existing is None else _prefer(existing, p)


def discover_all(
    *,
    mailto: str = "",
    per_term: int = 10,
    include_preprints: bool = True,
    preprint_days_back: int = 14,
    client: Optional[httpx.Client] = None,
) -> list[Paper]:
    own = client is None
    client = client or httpx.Client(timeout=30.0)
    pool: dict[str, Paper] = {}
    try:
        oa = discover_openalex(DEFAULT_SEED_TERMS, per_term=per_term, mailto=mailto, client=client)
        _merge(pool, oa)
        n_oa = len(pool)
        if include_preprints:
            for server in ("biorxiv", "medrxiv"):
                try:
                    pre = discover_rxiv(server, days_back=preprint_days_back, client=client)
                except Exception as e:  # noqa: BLE001 — a preprint source failure isn't fatal
                    print(f"[discover] {server} failed: {type(e).__name__}: {str(e)[:80]}")
                    continue
                _merge(pool, pre)
        print(f"[discover] openalex={n_oa}, +preprints -> {len(pool)} unique candidates")
    finally:
        if own:
            client.close()
    return list(pool.values())
