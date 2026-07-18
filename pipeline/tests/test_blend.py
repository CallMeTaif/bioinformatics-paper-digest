"""Two-lane blend: preprints must not be crowded out by recent journal papers."""
import datetime as _dt

from pipeline.sources.base import Paper
from pipeline.run import blend_lanes

_TODAY = _dt.date.today().isoformat()


def _established(cites, i):
    return Paper(title=f"est{i}", doi=f"10.1/e{i}", is_preprint=False,
                cited_by_count=cites, publication_date=_TODAY)


def _preprint(i):
    return Paper(title=f"pre{i}", doi=f"10.2/p{i}", is_preprint=True,
                 publication_date=_TODAY)


def test_blend_includes_preprints_despite_more_established():
    papers = [_established(100 - i, i) for i in range(10)] + [_preprint(i) for i in range(10)]
    out = blend_lanes(papers, 8, fresh_ratio=0.5)
    assert any(p.is_preprint for p in out), "fresh lane got crowded out"
    assert any(not p.is_preprint for p in out), "established lane missing"


def test_blend_established_sorted_by_citations():
    papers = [_established(5, 0), _established(50, 1), _established(20, 2)]
    out = blend_lanes(papers, 3)
    est = [p for p in out if not p.is_preprint]
    assert est[0].cited_by_count == 50  # highest-cited first


def test_blend_respects_n():
    papers = [_established(1, i) for i in range(5)] + [_preprint(i) for i in range(5)]
    assert len(blend_lanes(papers, 4)) == 4


def test_blend_handles_only_established():
    papers = [_established(3, i) for i in range(3)]
    out = blend_lanes(papers, 5)
    assert len(out) == 3 and all(not p.is_preprint for p in out)
