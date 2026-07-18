"""Resolve the best available full text for a Paper, from any source.

Order: a direct JATS URL (bioRxiv/medRxiv jatsxml — best effort, often 404s for
fresh preprints) → Europe PMC by DOI. If neither yields usable full text, the
paper keeps only its abstract and the caller may summarize from that.
"""
from __future__ import annotations

from typing import Optional

import httpx

from .base import Paper
from .europepmc import enrich_fulltext, parse_jats, MIN_FULLTEXT_CHARS
from .pdf import extract_pdf_text


def resolve_fulltext(paper: Paper, *, client: Optional[httpx.Client] = None) -> Paper:
    own = client is None
    client = client or httpx.Client(timeout=45.0, follow_redirects=True)
    try:
        # 1) direct JATS URL (preprints). Best effort — many 404 while fresh.
        if paper.full_text_url:
            try:
                r = client.get(paper.full_text_url)
                r.raise_for_status()
                parsed = parse_jats(r.text)
                if parsed and len(parsed["full_text"]) >= MIN_FULLTEXT_CHARS:
                    paper.full_text = parsed["full_text"]
                    if not paper.abstract and parsed.get("abstract"):
                        paper.abstract = parsed["abstract"]
                    return paper
            except httpx.HTTPError:
                pass  # fall through
        # 2) Europe PMC by DOI (also fills full_text when available).
        enrich_fulltext(paper, client=client)
        if paper.full_text:
            return paper
        # 3) open-access PDF: download + extract text (covers recent papers with
        #    no JATS but a downloadable PDF, e.g. arXiv/Nature). 403 fails safely.
        if paper.pdf_original_url:
            text = extract_pdf_text(paper.pdf_original_url, client=client)
            if text:
                paper.full_text = text
    finally:
        if own:
            client.close()
    return paper
