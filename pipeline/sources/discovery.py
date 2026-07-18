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


def _merge(into: dict[str, Paper], papers: list[Paper]) -> None:
    for p in papers:
        key = p.dedup_key()
        existing = into.get(key)
        if existing is None:
            into[key] = p
            continue
        # Collapse preprint + published: keep the non-preprint (peer-reviewed).
        if existing.is_preprint and not p.is_preprint:
            into[key] = p


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
