"""License-gated PDF hosting (spec §12).

We host our own copy of a paper's PDF **only** when its license permits
redistribution (CC0 / CC-BY / CC-BY-SA). Everything else stays link-only.

The licence check happens here, at the moment of upload, so a non-permitted PDF
cannot be hosted even if a caller asks for it.
"""
from __future__ import annotations

from typing import Optional

import httpx

from .. import config
from ..sources.base import Paper
from ..sources.pdf import download_pdf


def _object_path(paper: Paper, slug: str) -> str:
    return f"{slug}.pdf"


def public_url(path: str) -> str:
    base = config.SUPABASE_URL.rstrip("/")
    return f"{base}/storage/v1/object/public/{config.SUPABASE_PDF_BUCKET}/{path}"


def host_pdf(paper: Paper, slug: str, *, client: httpx.Client) -> Optional[str]:
    """Upload the paper's PDF to storage and return its public URL.

    Returns None (link-only) when: the licence doesn't permit redistribution,
    there's no PDF URL, storage isn't configured, or the download/upload fails.
    """
    # 1) the copyright gate — the one rule that must never be bypassed
    if not paper.is_hostable:
        return None
    if not paper.pdf_original_url:
        return None
    if not (config.SUPABASE_URL and config.SUPABASE_SERVICE_KEY):
        return None

    # 2) fetch the PDF
    content = download_pdf(paper.pdf_original_url, client=client)
    if not content:
        return None

    # 3) upload to the public bucket (upsert so re-runs are idempotent)
    path = _object_path(paper, slug)
    url = (f"{config.SUPABASE_URL.rstrip('/')}/storage/v1/object/"
           f"{config.SUPABASE_PDF_BUCKET}/{path}")
    headers = {
        "Authorization": f"Bearer {config.SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/pdf",
        "x-upsert": "true",
    }
    try:
        resp = client.post(url, headers=headers, content=content)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        print(f"[pdf-host] upload failed for {slug}: {str(e)[:100]}")
        return None
    return public_url(path)
