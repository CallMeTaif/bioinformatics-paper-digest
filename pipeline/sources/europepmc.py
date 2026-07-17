"""Europe PMC full-text fetch (no API key required).

Given a DOI (or PMCID), find the open-access full text and return clean,
section-structured plain text for the summarizer. JATS XML is parsed with the
stdlib xml.etree — no lxml dependency.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Optional

import httpx

from .base import Paper

SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
# Full text lives at /rest/{PMCID}/fullTextXML (PMCID keeps its 'PMC' prefix).
FULLTEXT = "https://www.ebi.ac.uk/europepmc/webservices/rest/{pid}/fullTextXML"

# Below this, a "full text" is really just an abstract/stub — not worth
# summarizing as full text. Such papers fall back to abstract-only or are skipped.
MIN_FULLTEXT_CHARS = 1500


def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _text_of(elem: ET.Element) -> str:
    """All descendant text of an element, whitespace-collapsed."""
    parts = list(elem.itertext())
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def find_record(
    *, doi: Optional[str] = None, pmcid: Optional[str] = None,
    client: httpx.Client,
) -> Optional[dict]:
    """Look up the Europe PMC 'core' record to get PMCID + OA flags."""
    if pmcid:
        query = f"PMCID:{pmcid}"
    elif doi:
        query = f'DOI:"{doi}"'
    else:
        return None
    params = {"query": query, "resultType": "core", "format": "json", "pageSize": "1"}
    try:
        resp = client.get(SEARCH, params=params)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        print(f"[europepmc] search failed for {query}: {e}")
        return None
    results = (resp.json().get("resultList") or {}).get("result") or []
    return results[0] if results else None


def parse_jats(xml_str: str) -> dict:
    """Extract title, abstract, and body sections from JATS full-text XML."""
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError as e:
        print(f"[europepmc] JATS parse error: {e}")
        return {"sections": [], "full_text": "", "abstract": None}

    def find_all(parent: ET.Element, name: str) -> list[ET.Element]:
        return [e for e in parent.iter() if _strip_ns(e.tag) == name]

    # Abstract (front matter)
    abstract = None
    for ab in find_all(root, "abstract"):
        abstract = _text_of(ab)
        break

    # Body sections
    sections: list[tuple[str, str]] = []
    bodies = find_all(root, "body")
    if bodies:
        for sec in find_all(bodies[0], "sec"):
            title_el = next((c for c in sec if _strip_ns(c.tag) == "title"), None)
            title = _text_of(title_el) if title_el is not None else ""
            paras = [_text_of(p) for p in sec if _strip_ns(p.tag) == "p"]
            body = " ".join(t for t in paras if t)
            if title or body:
                sections.append((title, body))

    parts = []
    if abstract:
        parts.append("ABSTRACT\n" + abstract)
    for title, body in sections:
        header = title.upper() if title else "SECTION"
        parts.append(f"{header}\n{body}".strip())
    full_text = "\n\n".join(p for p in parts if p.strip())
    return {"sections": sections, "full_text": full_text, "abstract": abstract}


def fetch_fulltext(*, pmcid: str, client: httpx.Client) -> Optional[dict]:
    url = FULLTEXT.format(pid=pmcid)
    try:
        resp = client.get(url)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        print(f"[europepmc] fulltext fetch failed for {pmcid}: {e}")
        return None
    return parse_jats(resp.text)


def enrich_fulltext(paper: Paper, *, client: Optional[httpx.Client] = None) -> Paper:
    """Attach full_text to a Paper when Europe PMC has open-access full text.

    Returns the same Paper (mutated). Leaves full_text=None when unavailable —
    the caller decides whether to fall back to the abstract or skip.
    """
    own = client is None
    client = client or httpx.Client(timeout=45.0)
    try:
        rec = find_record(doi=paper.doi, pmcid=paper.pmcid, client=client)
        if not rec:
            return paper
        pmcid = rec.get("pmcid") or paper.pmcid
        paper.pmcid = pmcid
        paper.pmid = rec.get("pmid") or paper.pmid
        in_epmc = rec.get("inEPMC") == "Y" or rec.get("isOpenAccess") == "Y"
        if not pmcid or not in_epmc:
            return paper
        parsed = fetch_fulltext(pmcid=pmcid, client=client)
        if parsed and len(parsed["full_text"]) >= MIN_FULLTEXT_CHARS:
            paper.full_text = parsed["full_text"]
        # Even when the body is too thin to use as full text, keep a better abstract.
        if parsed and not paper.abstract and parsed.get("abstract"):
            paper.abstract = parsed["abstract"]
    finally:
        if own:
            client.close()
    return paper


if __name__ == "__main__":
    import sys
    from .base import Paper as P

    test_doi = sys.argv[1] if len(sys.argv) > 1 else "10.1371/journal.pcbi.1011771"
    p = P(doi=test_doi, title="test")
    enrich_fulltext(p)
    if p.full_text:
        print(f"PMCID={p.pmcid} full_text chars={len(p.full_text)}")
        print("--- first 600 chars ---")
        print(p.full_text[:600])
    else:
        print(f"No open-access full text found for DOI {test_doi} (PMCID={p.pmcid})")
