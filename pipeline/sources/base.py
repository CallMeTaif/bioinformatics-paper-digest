"""Normalized paper record shared by every source.

Every source module must return `Paper` objects so the rest of the pipeline
(dedup, ranking, summarize, publish) never cares where a paper came from.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


def normalize_doi(doi: Optional[str]) -> Optional[str]:
    """Lowercase, strip URL prefixes, so the same paper dedups across sources."""
    if not doi:
        return None
    d = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if d.startswith(prefix):
            d = d[len(prefix):]
    return d or None


# License strings that permit hosting the PDF. Mirror of the DB allowlist in
# supabase/schema.sql (§12). The publish step is the enforcement point; this
# constant lets the pipeline decide without a DB round-trip.
HOSTABLE_LICENSES = {"cc0", "cc-by", "cc-by-sa"}


def normalize_license(raw: Optional[str]) -> str:
    """Map assorted provider license strings to our vocabulary."""
    if not raw:
        return "unknown"
    r = raw.strip().lower()
    # OpenAlex/Crossref use forms like 'cc-by', 'cc-by-nc', 'cc0', or URLs.
    if "creativecommons.org/publicdomain" in r or r in {"cc0", "cc-0"}:
        return "cc0"
    if "cc-by-nc-nd" in r or "by-nc-nd" in r:
        return "cc-by-nc-nd"
    if "cc-by-nc-sa" in r or "by-nc-sa" in r:
        return "cc-by-nc-sa"
    if "cc-by-nc" in r or "by-nc" in r:
        return "cc-by-nc"
    if "cc-by-sa" in r or "by-sa" in r:
        return "cc-by-sa"
    if "cc-by" in r or "by/" in r or r == "cc-by":
        return "cc-by"
    if r in {"public-domain", "publicdomain"}:
        return "cc0"
    if r in {"publisher-specific-oa", "publisher-specific", "other-oa", "unspecified-oa"}:
        return "other-oa"
    if r.startswith(("http://", "https://")):
        return "proprietary"  # a non-CC license URL (e.g. publisher user license)
    return r  # keep whatever it is; treated as non-hostable unless in allowlist


@dataclass
class Paper:
    # --- identity / dedup ---
    doi: Optional[str] = None
    title: str = ""
    # --- bibliographic ---
    authors: list[str] = field(default_factory=list)
    venue: Optional[str] = None
    publication_date: Optional[str] = None  # ISO 'YYYY-MM-DD'
    source: str = "openalex"
    is_preprint: bool = False
    # --- open access / license ---
    oa_status: Optional[str] = None
    license: str = "unknown"
    original_url: Optional[str] = None
    pdf_original_url: Optional[str] = None
    # --- content ---
    abstract: Optional[str] = None
    full_text: Optional[str] = None  # filled by a full-text source (Europe PMC)
    full_text_url: Optional[str] = None  # direct JATS XML URL (e.g. bioRxiv/medRxiv)
    # --- ranking signals (not persisted directly) ---
    cited_by_count: int = 0
    # --- cross-source identifiers to help enrichment ---
    pmid: Optional[str] = None
    pmcid: Optional[str] = None
    openalex_id: Optional[str] = None
    # --- anything provider-specific we want to keep around ---
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.doi = normalize_doi(self.doi)
        self.license = normalize_license(self.license)

    @property
    def is_hostable(self) -> bool:
        """True only if the license permits us to redistribute the PDF."""
        return self.license in HOSTABLE_LICENSES

    def dedup_key(self) -> str:
        """DOI when present, else a title-based fallback."""
        if self.doi:
            return self.doi
        return self.title_key()

    def title_key(self) -> str:
        """Normalized title — collapses versioned duplicates (e.g. Zenodo/preprint
        versions with different per-version DOIs but the same title)."""
        return "title:" + " ".join((self.title or "").lower().split())

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("raw", None)  # keep provider blob out of persisted rows
        return d
