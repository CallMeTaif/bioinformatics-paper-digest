"""License normalization + PDF-hosting gate — the copyright-critical logic (§12)."""
import pytest

from pipeline.sources.base import Paper, normalize_license, normalize_doi


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("cc-by", "cc-by"),
        ("CC-BY", "cc-by"),
        ("https://creativecommons.org/licenses/by/4.0/", "cc-by"),
        ("cc-by-sa", "cc-by-sa"),
        ("cc0", "cc0"),
        ("https://creativecommons.org/publicdomain/zero/1.0/", "cc0"),
        ("cc-by-nc", "cc-by-nc"),
        ("cc-by-nc-nd", "cc-by-nc-nd"),
        ("publisher-specific-oa", "other-oa"),
        (None, "unknown"),
        ("", "unknown"),
    ],
)
def test_normalize_license(raw, expected):
    assert normalize_license(raw) == expected


@pytest.mark.parametrize(
    "license_str,hostable",
    [
        ("cc-by", True),
        ("cc-by-sa", True),
        ("cc0", True),
        ("cc-by-nc", False),      # NC is NOT hostable by default (§12)
        ("cc-by-nc-nd", False),
        ("other-oa", False),
        ("unknown", False),
        (None, False),
    ],
)
def test_is_hostable(license_str, hostable):
    p = Paper(title="x", license=license_str)
    assert p.is_hostable is hostable


def test_normalize_doi_strips_prefixes():
    assert normalize_doi("https://doi.org/10.1/AbC") == "10.1/abc"
    assert normalize_doi("doi:10.2/x") == "10.2/x"
    assert normalize_doi(None) is None


def test_dedup_key_prefers_doi():
    a = Paper(title="Same Title", doi="https://doi.org/10.1/x")
    b = Paper(title="Same Title", doi="10.1/X")
    assert a.dedup_key() == b.dedup_key()  # case/prefix-insensitive DOI match


def test_dedup_key_title_fallback_when_no_doi():
    a = Paper(title="Some  Paper   Title")
    b = Paper(title="some paper title")
    assert a.dedup_key() == b.dedup_key()
