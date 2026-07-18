"""bioRxiv + medRxiv preprint discovery — the 'fresh' lane (no API key).

The rxiv 'details' API returns recent preprints by date range, including a
jatsxml URL we can parse for full text directly (reusing the JATS parser), so
these papers don't depend on Europe PMC.

Preprints are NOT peer-reviewed — every Paper here has is_preprint=True.
"""
from __future__ import annotations

import datetime as _dt
from typing import Optional

import httpx

from .base import Paper, normalize_license
from ..topics import INCLUDE_KEYWORDS

API = "https://api.biorxiv.org/details/{server}/{frm}/{to}/{cursor}"

# Categories that fit the broad-bioinformatics scope; anything outside these is
# kept only if it keyword-matches. Lowercased for comparison.
RELEVANT_CATEGORIES = {
    "bioinformatics", "genomics", "genetics", "systems biology",
    "synthetic biology", "computational biology", "molecular biology",
    "evolutionary biology", "microbiology", "cancer biology",
    "genetic and genomic medicine", "health informatics",
}


def _authors(raw: str) -> list[str]:
    # "Last, F.; Last, F." -> ["Last, F.", ...]
    return [a.strip() for a in (raw or "").split(";") if a.strip()]


def _on_topic(rec: dict) -> bool:
    cat = (rec.get("category") or "").strip().lower()
    if cat in RELEVANT_CATEGORIES:
        return True
    blob = f"{rec.get('title', '')} {rec.get('abstract', '')}".lower()
    return any(k.lower() in blob for k in INCLUDE_KEYWORDS)


def _to_paper(rec: dict, server: str) -> Paper:
    doi = rec.get("doi")
    lic = (rec.get("license") or "").replace("_", "-")  # bioRxiv uses cc_by etc.
    return Paper(
        doi=doi,
        title=(rec.get("title") or "").strip(),
        authors=_authors(rec.get("authors", "")),
        venue="bioRxiv" if server == "biorxiv" else "medRxiv",
        publication_date=rec.get("date"),
        source=server,
        is_preprint=True,
        oa_status="preprint",
        license=normalize_license(lic),
        original_url=f"https://doi.org/{doi}" if doi else None,
        abstract=(rec.get("abstract") or "").strip() or None,
        full_text_url=rec.get("jatsxml") or None,
        cited_by_count=0,
        raw={},
    )


def discover(
    server: str = "biorxiv",
    *,
    days_back: int = 14,
    max_pages: int = 8,
    client: Optional[httpx.Client] = None,
) -> list[Paper]:
    """Recent on-topic preprints from bioRxiv or medRxiv. Dedups by DOI+version."""
    today = _dt.date.today()
    frm = (today - _dt.timedelta(days=days_back)).isoformat()
    to = today.isoformat()

    own = client is None
    client = client or httpx.Client(timeout=30.0)
    seen: dict[str, Paper] = {}
    try:
        for page in range(max_pages):
            url = API.format(server=server, frm=frm, to=to, cursor=page * 30)
            try:
                resp = client.get(url)
                resp.raise_for_status()
            except httpx.HTTPError as e:
                print(f"[{server}] page {page} failed: {e}")
                break
            data = resp.json()
            coll = data.get("collection") or []
            if not coll:
                break
            for rec in coll:
                if not _on_topic(rec):
                    continue
                paper = _to_paper(rec, server)
                if not paper.title:
                    continue
                # Collapse multiple versions of the same preprint (keep latest seen).
                key = paper.dedup_key()
                seen[key] = paper
            # Stop early once the date window is exhausted.
            msg = (data.get("messages") or [{}])[0]
            if (page + 1) * 30 >= int(msg.get("total", 0) or 0):
                break
    finally:
        if own:
            client.close()
    return list(seen.values())


def discover_biorxiv(**kw) -> list[Paper]:
    return discover("biorxiv", **kw)


def discover_medrxiv(**kw) -> list[Paper]:
    return discover("medrxiv", **kw)


if __name__ == "__main__":
    for srv in ("biorxiv", "medrxiv"):
        papers = discover(srv, days_back=10, max_pages=4)
        print(f"\n=== {srv}: {len(papers)} on-topic preprints ===")
        for p in papers[:8]:
            host = "host" if p.is_hostable else "link"
            print(f"- {p.title[:65]!r} | {p.license}/{host} | {p.publication_date}")
