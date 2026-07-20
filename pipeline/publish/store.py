"""Persist records to the active sink.

Local JSON sink (default until Supabase is wired) writes web/src/data/papers.json,
which the Astro site imports directly at build time. Same record shape as the DB
so switching sinks changes nothing downstream.
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any

from .. import config
from ..sources.base import normalize_doi

_ROOT = Path(__file__).resolve().parents[2]
LOCAL_JSON = _ROOT / "web" / "src" / "data" / "papers.json"


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _title_key(title: str) -> str:
    return " ".join((title or "").lower().split())


def posted_keys() -> set[str]:
    """Identifiers (normalized DOIs + title keys) already in the store, so the
    pipeline can skip re-summarizing papers it has published before.

    Reads Supabase when configured, else the local JSON. Missing/empty -> set().
    """
    keys: set[str] = set()
    records: list[dict[str, Any]] = []
    if config.USE_SUPABASE_DB and config.SUPABASE_URL and config.SUPABASE_SERVICE_KEY:
        try:
            import httpx
            url = f"{config.SUPABASE_URL.rstrip('/')}/rest/v1/papers"
            headers = {
                "apikey": config.SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {config.SUPABASE_SERVICE_KEY}",
            }
            with httpx.Client(timeout=20.0) as c:
                r = c.get(url, headers=headers, params={"select": "doi,title"})
                r.raise_for_status()
                records = r.json()
        except Exception as e:  # noqa: BLE001 — fall back to local on any failure
            print(f"[dedup] Supabase read failed ({type(e).__name__}); using local")
            records = []
    if not records and LOCAL_JSON.exists():
        try:
            records = json.loads(LOCAL_JSON.read_text())
        except json.JSONDecodeError:
            records = []
    for r in records:
        doi = normalize_doi(r.get("doi"))
        if doi:
            keys.add(doi)
        title = r.get("title")
        if title:
            keys.add("title:" + _title_key(title))
    return keys


def _save_local(records: list[dict[str, Any]]) -> int:
    LOCAL_JSON.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict[str, Any]] = []
    if LOCAL_JSON.exists():
        try:
            existing = json.loads(LOCAL_JSON.read_text())
        except json.JSONDecodeError:
            existing = []

    by_slug: dict[str, dict[str, Any]] = {r["slug"]: r for r in existing}
    added = 0
    for r in records:
        if r["slug"] not in by_slug:
            added += 1
        r.setdefault("date_posted", _now_iso())
        by_slug[r["slug"]] = {**by_slug.get(r["slug"], {}), **r}

    merged = sorted(
        by_slug.values(), key=lambda r: r.get("date_posted") or "", reverse=True
    )
    merged = _collapse_by_title(merged)
    LOCAL_JSON.write_text(json.dumps(merged, indent=2, ensure_ascii=False))
    try:  # display-only nicety; never let it break the save
        where = LOCAL_JSON.relative_to(_ROOT)
    except ValueError:
        where = LOCAL_JSON
    print(f"[publish] wrote {len(merged)} records ({added} new) -> {where}")
    return added


def _collapse_by_title(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop cross-run versioned duplicates (same normalized title, different
    slug) — e.g. a preprint published in one run and its journal version later.
    Keeps the first occurrence (newest, since records are date-sorted)."""
    seen: set[str] = set()
    out = []
    for r in records:
        key = " ".join((r.get("title") or "").lower().split())
        if key and key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _save_supabase(records: list[dict[str, Any]]) -> int:
    import httpx

    url = f"{config.SUPABASE_URL.rstrip('/')}/rest/v1/papers"
    headers = {
        "apikey": config.SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {config.SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    payload = []
    for r in records:
        row = {k: v for k, v in r.items() if k != "date_posted"}
        row["date_posted"] = r.get("date_posted") or _now_iso()
        payload.append(row)

    with httpx.Client(timeout=30.0) as c:
        resp = c.post(url, headers=headers, params={"on_conflict": "slug"}, json=payload)
        resp.raise_for_status()
    print(f"[publish] upserted {len(payload)} records -> Supabase")
    return len(payload)


def save_records(records: list[dict[str, Any]]) -> int:
    """Write records to whichever sink is active. Returns count added/upserted."""
    if not records:
        print("[publish] nothing to save")
        return 0
    # A dry run must never mutate the published library — it uses mock models,
    # so persisting its output would put placeholder summaries on the live site.
    if config.DRY_RUN:
        print(f"[publish] DRY_RUN — would save {len(records)} record(s); writing nothing:")
        for r in records:
            print(f"           - [{r.get('status')}] {r.get('title', '')[:60]}")
        return 0
    use_supabase = (
        config.USE_SUPABASE_DB
        and bool(config.SUPABASE_URL) and bool(config.SUPABASE_SERVICE_KEY)
        and not config.DRY_RUN
    )
    if use_supabase:
        return _save_supabase(records)
    return _save_local(records)
