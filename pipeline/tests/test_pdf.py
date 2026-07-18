"""PDF extractor guards (offline: no real download)."""
import httpx

from pipeline.sources.pdf import _looks_like_pdf, extract_pdf_text


def test_looks_like_pdf_by_magic_bytes():
    assert _looks_like_pdf(b"%PDF-1.7 ...", "") is True


def test_looks_like_pdf_by_content_type():
    assert _looks_like_pdf(b"garbage", "application/pdf; charset=binary") is True


def test_rejects_html_masquerading():
    assert _looks_like_pdf(b"<!DOCTYPE html>", "text/html") is False


def test_extract_returns_none_on_non_pdf(monkeypatch):
    # A 200 that returns HTML (e.g. a publisher paywall page) must yield None.
    class FakeResp:
        content = b"<html>not a pdf</html>"
        headers = {"content-type": "text/html"}
        def raise_for_status(self): pass

    class FakeClient:
        def get(self, url, headers=None): return FakeResp()

    assert extract_pdf_text("http://x/y.pdf", client=FakeClient()) is None


def test_extract_returns_none_on_http_error(monkeypatch):
    class FakeClient:
        def get(self, url, headers=None):
            raise httpx.HTTPError("403")
    assert extract_pdf_text("http://x/y.pdf", client=FakeClient()) is None
