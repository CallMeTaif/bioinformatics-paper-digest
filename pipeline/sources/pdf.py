"""Download an open-access PDF and extract its text (full-text fallback).

Many recent papers have no machine-readable JATS full text but DO have a
downloadable open PDF (arXiv, Nature, etc.). Extracting that text lets the
summarizer work from the whole paper instead of just the abstract. Some
publishers block automated download (403) — those fail gracefully.
"""
from __future__ import annotations

import io
import re
from typing import Optional

import httpx

# Polite UA — some publishers 403 a bare client.
_UA = "bioinformatics-paper-digest/0.1 (research summarizer; ai.taif.alharbi@gmail.com)"
_MAX_PDF_BYTES = 30 * 1024 * 1024   # skip absurdly large PDFs
MIN_PDF_TEXT_CHARS = 2000           # below this, treat as failed extraction


def _looks_like_pdf(content: bytes, content_type: str) -> bool:
    return content[:5] == b"%PDF-" or "application/pdf" in (content_type or "").lower()


def extract_pdf_text(url: str, *, client: httpx.Client) -> Optional[str]:
    """Return cleaned full text from a PDF URL, or None if unavailable/too short."""
    try:
        resp = client.get(url, headers={"User-Agent": _UA})
        resp.raise_for_status()
    except httpx.HTTPError:
        return None
    content = resp.content
    if len(content) > _MAX_PDF_BYTES or not _looks_like_pdf(content, resp.headers.get("content-type", "")):
        return None
    try:
        import pypdf  # type: ignore
        reader = pypdf.PdfReader(io.BytesIO(content))
        parts = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:  # noqa: BLE001 — one bad page shouldn't sink the doc
                continue
        text = re.sub(r"[ \t]+", " ", "\n".join(parts)).strip()
    except Exception:  # noqa: BLE001 — encrypted/corrupt/unsupported PDF
        return None
    return text if len(text) >= MIN_PDF_TEXT_CHARS else None
