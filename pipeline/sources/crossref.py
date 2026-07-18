"""Crossref enrichment — authoritative license metadata (spec §4).

Crossref is the canonical DOI registry; its license field is the most reliable
signal for whether we may host a paper's PDF. We use it to firm up paper.license
(and fill venue/date if missing) before the copyright gate decides host vs link.
"""
from __future__ import annotations

from typing import Optional

import httpx

from .base import Paper, normalize_license

API = "https://api.crossref.org/works/{doi}"

# Prefer the license attached to the published version of record, then the
# accepted manuscript, then anything else.
_VERSION_RANK = {"vor": 0, "am": 1, "tdm": 2, "unspecified": 3}


def _best_license(entries: list[dict]) -> Optional[str]:
    """Pick the most authoritative license URL and normalize it; None if none map
    to a known license."""
    for entry in sorted(entries, key=lambda e: _VERSION_RANK.get(e.get("content-version"), 9)):
        norm = normalize_license(entry.get("URL"))
        if norm not in ("unknown", "other-oa"):
            return norm
    return None


def enrich_license(paper: Paper, *, client: httpx.Client, mailto: str = "") -> Paper:
    """Set paper.license from Crossref when it gives a clearer answer, and fill
    venue/publication_date if missing. No-op when the paper has no DOI."""
    if not paper.doi:
        return paper
    params = {"mailto": mailto} if mailto else None
    try:
        resp = client.get(API.format(doi=paper.doi), params=params)
        resp.raise_for_status()
        msg = resp.json().get("message") or {}
    except (httpx.HTTPError, ValueError):
        return paper

    lic = _best_license(msg.get("license") or [])
    # Crossref is authoritative: adopt its license unless it found none and we
    # already have a hostable one (don't downgrade a good local value to unknown).
    if lic and lic != paper.license:
        paper.license = lic

    if not paper.venue:
        ct = msg.get("container-title") or []
        if ct:
            paper.venue = ct[0]
    if not paper.publication_date:
        parts = ((msg.get("published") or {}).get("date-parts") or [[]])[0]
        if len(parts) >= 3:
            paper.publication_date = f"{parts[0]:04d}-{parts[1]:02d}-{parts[2]:02d}"
    return paper


if __name__ == "__main__":
    import sys
    from .base import Paper as P
    doi = sys.argv[1] if len(sys.argv) > 1 else "10.1093/bioinformatics/btac001"
    p = P(doi=doi, title="test", license="unknown")
    with httpx.Client(timeout=20.0) as c:
        enrich_license(p, client=c, mailto="ai.taif.alharbi@gmail.com")
    print(f"license={p.license} hostable={p.is_hostable} venue={p.venue} date={p.publication_date}")
