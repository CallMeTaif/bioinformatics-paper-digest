"""Crossref license selection + proprietary-URL normalization."""
from pipeline.sources.base import Paper, normalize_license
from pipeline.sources.crossref import _best_license, enrich_license


def test_best_license_prefers_version_of_record():
    entries = [
        {"content-version": "am", "URL": "https://creativecommons.org/licenses/by-nc/4.0/"},
        {"content-version": "vor", "URL": "https://creativecommons.org/licenses/by/4.0/"},
    ]
    assert _best_license(entries) == "cc-by"  # vor wins over am


def test_best_license_none_when_no_known():
    entries = [{"content-version": "vor", "URL": "https://example.com/unspecified"}]
    # a bare non-CC URL normalizes to 'proprietary', which is a known (non-hostable) value
    assert _best_license(entries) == "proprietary"


def test_best_license_empty():
    assert _best_license([]) is None


def test_normalize_proprietary_url():
    assert normalize_license("http://www.elsevier.com/open-access/userlicense/1.0/") == "proprietary"
    p = Paper(title="x", license="http://www.elsevier.com/open-access/userlicense/1.0/")
    assert p.license == "proprietary" and p.is_hostable is False


def test_enrich_license_noop_without_doi():
    p = Paper(title="x", license="cc-by")  # no DOI
    # Should not raise and should not need a client call.
    enrich_license(p, client=None)  # type: ignore[arg-type]
    assert p.license == "cc-by"
