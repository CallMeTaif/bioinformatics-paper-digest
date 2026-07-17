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

_ROOT = Path(__file__).resolve().parents[2]
LOCAL_JSON = _ROOT / "web" / "src" / "data" / "papers.json"


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


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
    LOCAL_JSON.write_text(json.dumps(merged, indent=2, ensure_ascii=False))
    print(f"[publish] wrote {len(merged)} records ({added} new) -> {LOCAL_JSON.relative_to(_ROOT)}")
    return added


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
    use_supabase = (
        bool(config.SUPABASE_URL) and bool(config.SUPABASE_SERVICE_KEY) and not config.DRY_RUN
    )
    if use_supabase:
        return _save_supabase(records)
    return _save_local(records)
