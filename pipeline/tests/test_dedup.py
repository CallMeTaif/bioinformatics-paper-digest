"""Title-based dedup collapses versioned duplicates (different DOIs, same title)."""
from pipeline.sources.base import Paper
from pipeline.sources.discovery import _merge, _prefer
from pipeline.publish.store import _collapse_by_title


def test_merge_collapses_versioned_dois():
    # Same title, different Zenodo-style per-version DOIs -> one entry.
    a = Paper(title="Same Paper Title", doi="10.5281/zenodo.1", is_preprint=True)
    b = Paper(title="Same Paper Title", doi="10.5281/zenodo.2", is_preprint=True)
    pool: dict = {}
    _merge(pool, [a, b])
    assert len(pool) == 1


def test_merge_prefers_published_over_preprint():
    pre = Paper(title="X", doi="10.1/pre", is_preprint=True)
    pub = Paper(title="X", doi="10.1/pub", is_preprint=False, cited_by_count=5)
    pool: dict = {}
    _merge(pool, [pre, pub])
    assert list(pool.values())[0].is_preprint is False


def test_prefer_higher_citations_when_same_type():
    a = Paper(title="X", doi="10.1/a", cited_by_count=3)
    b = Paper(title="X", doi="10.1/b", cited_by_count=30)
    assert _prefer(a, b).cited_by_count == 30


def test_store_collapse_by_title_keeps_first():
    recs = [
        {"title": "Dup Title", "slug": "a", "is_preprint": True},
        {"title": "dup   title", "slug": "b", "is_preprint": True},  # same normalized
        {"title": "Other", "slug": "c"},
    ]
    out = _collapse_by_title(recs)
    assert len(out) == 2
    assert out[0]["slug"] == "a"  # first occurrence kept
