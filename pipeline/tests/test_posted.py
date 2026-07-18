"""posted_keys() reads the store and yields DOI + title identifiers to skip."""
import json

from pipeline.publish import store


def test_posted_keys_reads_local(tmp_path, monkeypatch):
    f = tmp_path / "papers.json"
    f.write_text(json.dumps([
        {"doi": "https://doi.org/10.1/AbC", "title": "Some  Cool   Title"},
        {"doi": None, "title": "No DOI Paper"},
    ]))
    monkeypatch.setattr(store, "LOCAL_JSON", f)
    monkeypatch.setattr(store.config, "SUPABASE_URL", "")
    monkeypatch.setattr(store.config, "SUPABASE_SERVICE_KEY", "")

    keys = store.posted_keys()
    assert "10.1/abc" in keys                # normalized DOI (lowercased, prefix-stripped by store)
    assert "title:some cool title" in keys   # normalized title key
    assert "title:no doi paper" in keys


def test_posted_keys_empty_when_no_store(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "LOCAL_JSON", tmp_path / "missing.json")
    monkeypatch.setattr(store.config, "SUPABASE_URL", "")
    monkeypatch.setattr(store.config, "SUPABASE_SERVICE_KEY", "")
    assert store.posted_keys() == set()
