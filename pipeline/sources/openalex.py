"""OpenAlex discovery — the spine of the pipeline (no API key required).

Runs one search per seed term (broad-bioinformatics), keeps open-access
articles, reconstructs abstracts, normalizes to Paper, and dedups by DOI.
"""
from __future__ import annotations

import datetime as _dt
from typing import Iterable, Optional

import httpx

from .base import Paper

API = "https://api.openalex.org/works"

# Trimmed payload — only fields the pipeline actually uses.
_SELECT = ",".join(
    [
        "id", "doi", "title", "display_name", "publication_date", "type",
        "authorships", "primary_location", "best_oa_location", "open_access",
        "cited_by_count", "abstract_inverted_index", "ids",
    ]
)

# Good broad seeds for discovery. Kept short on purpose: each is one API call.
DEFAULT_SEED_TERMS = [
    "bioinformatics",
    "computational biology",
    "genomics sequencing",
    "single-cell transcriptomics",
    "protein structure prediction",
    "deep learning genomics",
    "metagenomics microbiome",
    "systems biology network",
]

_PREPRINT_VENUES = {"biorxiv", "medrxiv", "arxiv", "research square", "preprints.org"}


def _reconstruct_abstract(inv: Optional[dict]) -> Optional[str]:
    """OpenAlex ships abstracts as an inverted index {word: [positions]}."""
    if not inv:
        return None
    positions: list[tuple[int, str]] = []
    for word, idxs in inv.items():
        for i in idxs:
            positions.append((i, word))
    if not positions:
        return None
    positions.sort()
    return " ".join(word for _, word in positions)


def _pick_location(work: dict) -> dict:
    return work.get("best_oa_location") or work.get("primary_location") or {}


def _to_paper(work: dict) -> Paper:
    loc = _pick_location(work)
    src = (loc.get("source") or {}) if isinstance(loc, dict) else {}
    venue = src.get("display_name")
    is_preprint = (
        work.get("type") == "preprint"
        or (venue or "").strip().lower() in _PREPRINT_VENUES
        or (src.get("type") == "repository")
    )
    ids = work.get("ids") or {}
    oa = work.get("open_access") or {}
    authors = [
        (a.get("author") or {}).get("display_name", "")
        for a in (work.get("authorships") or [])
    ]
    landing = loc.get("landing_page_url") if isinstance(loc, dict) else None
    return Paper(
        doi=work.get("doi"),
        title=work.get("title") or work.get("display_name") or "",
        authors=[a for a in authors if a],
        venue=venue,
        publication_date=work.get("publication_date"),
        source="openalex",
        is_preprint=bool(is_preprint),
        oa_status=oa.get("oa_status"),
        license=loc.get("license") if isinstance(loc, dict) else None,
        original_url=landing or work.get("doi"),
        pdf_original_url=loc.get("pdf_url") if isinstance(loc, dict) else None,
        abstract=_reconstruct_abstract(work.get("abstract_inverted_index")),
        cited_by_count=work.get("cited_by_count", 0) or 0,
        pmid=(ids.get("pmid") or "").rsplit("/", 1)[-1] or None if ids.get("pmid") else None,
        pmcid=(ids.get("pmcid") or "").rsplit("/", 1)[-1] or None if ids.get("pmcid") else None,
        openalex_id=work.get("id"),
        raw={},
    )


def discover(
    seed_terms: Iterable[str] = DEFAULT_SEED_TERMS,
    *,
    from_date: Optional[str] = None,
    days_back: int = 120,
    per_term: int = 25,
    mailto: str = "",
    client: Optional[httpx.Client] = None,
) -> list[Paper]:
    """Discover open-access articles across seed terms; dedup by DOI/title.

    from_date overrides days_back when given ('YYYY-MM-DD').
    """
    if from_date is None:
        from_date = (
            _dt.date.today() - _dt.timedelta(days=days_back)
        ).isoformat()

    own_client = client is None
    client = client or httpx.Client(timeout=30.0, headers={"User-Agent": f"paper-digest ({mailto})"})
    seen: dict[str, Paper] = {}
    try:
        for term in seed_terms:
            params = {
                "search": term,
                "filter": f"open_access.is_oa:true,from_publication_date:{from_date},type:article",
                "sort": "relevance_score:desc",
                "per_page": str(per_term),
                "select": _SELECT,
            }
            if mailto:
                params["mailto"] = mailto
            try:
                resp = client.get(API, params=params)
                resp.raise_for_status()
            except httpx.HTTPError as e:
                # One bad term shouldn't sink the whole run.
                print(f"[openalex] term {term!r} failed: {e}")
                continue
            for work in resp.json().get("results", []):
                paper = _to_paper(work)
                if not paper.title:
                    continue
                key = paper.dedup_key()
                # Prefer the record we already have unless the new one has a DOI.
                if key not in seen:
                    seen[key] = paper
    finally:
        if own_client:
            client.close()
    return list(seen.values())


if __name__ == "__main__":
    import sys
    papers = discover(per_term=5, mailto=sys.argv[1] if len(sys.argv) > 1 else "")
    print(f"discovered {len(papers)} unique papers")
    for p in papers[:10]:
        flag = " [preprint]" if p.is_preprint else ""
        host = "host" if p.is_hostable else "link"
        print(f"- {p.title[:70]!r} | {p.venue} | {p.license}/{host} | cites={p.cited_by_count}{flag}")
