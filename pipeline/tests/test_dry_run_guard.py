"""A dry run must never write to the published library.

Regression guard: a CI dry-run once committed mock placeholder summaries to the
live site because DRY_RUN only gated paid APIs, not the store.
"""
import json

from pipeline.publish import store


def _rec(title="A paper"):
    return {"slug": "s1", "title": title, "status": "published", "summary_provider": "mock"}


def test_dry_run_writes_nothing(tmp_path, monkeypatch):
    target = tmp_path / "papers.json"
    monkeypatch.setattr(store, "LOCAL_JSON", target)
    monkeypatch.setattr(store.config, "DRY_RUN", True)
    monkeypatch.setattr(store.config, "SUPABASE_URL", "")
    monkeypatch.setattr(store.config, "SUPABASE_SERVICE_KEY", "")

    added = store.save_records([_rec()])

    assert added == 0
    assert not target.exists(), "dry run must not create/modify the library"


def test_real_run_does_write(tmp_path, monkeypatch):
    target = tmp_path / "papers.json"
    monkeypatch.setattr(store, "LOCAL_JSON", target)
    monkeypatch.setattr(store.config, "DRY_RUN", False)
    monkeypatch.setattr(store.config, "SUPABASE_URL", "")
    monkeypatch.setattr(store.config, "SUPABASE_SERVICE_KEY", "")

    added = store.save_records([_rec("Real paper")])

    assert added == 1
    saved = json.loads(target.read_text())
    assert saved[0]["title"] == "Real paper"
