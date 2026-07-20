"""PDF hosting must be gated by licence — the copyright-critical path (§12)."""
import httpx
import pytest

from pipeline.sources.base import Paper
from pipeline.publish import pdf_host


class FakeClient:
    """Records calls; returns a valid PDF on GET and success on POST."""
    def __init__(self):
        self.posted = []

    def get(self, url, headers=None):
        return httpx.Response(200, content=b"%PDF-1.7 fake",
                              headers={"content-type": "application/pdf"},
                              request=httpx.Request("GET", url))

    def post(self, url, headers=None, content=None):
        self.posted.append(url)
        return httpx.Response(200, json={}, request=httpx.Request("POST", url))


@pytest.fixture(autouse=True)
def _storage_configured(monkeypatch):
    monkeypatch.setattr(pdf_host.config, "SUPABASE_URL", "https://x.supabase.co")
    monkeypatch.setattr(pdf_host.config, "SUPABASE_SERVICE_KEY", "svc-key")
    monkeypatch.setattr(pdf_host.config, "SUPABASE_PDF_BUCKET", "pdfs")


@pytest.mark.parametrize("lic", ["cc-by", "cc-by-sa", "cc0"])
def test_hosts_when_licence_permits(lic):
    p = Paper(title="T", license=lic, pdf_original_url="http://x/y.pdf")
    c = FakeClient()
    url = pdf_host.host_pdf(p, "slug", client=c)
    assert url and url.endswith("/pdfs/slug.pdf")
    assert len(c.posted) == 1


@pytest.mark.parametrize("lic", ["cc-by-nc", "cc-by-nc-nd", "proprietary", "unknown", "other-oa"])
def test_never_hosts_when_licence_forbids(lic):
    p = Paper(title="T", license=lic, pdf_original_url="http://x/y.pdf")
    c = FakeClient()
    assert pdf_host.host_pdf(p, "slug", client=c) is None
    assert c.posted == [], "must not upload a non-redistributable PDF"


def test_no_pdf_url_means_no_host():
    p = Paper(title="T", license="cc-by")  # hostable licence but nothing to fetch
    c = FakeClient()
    assert pdf_host.host_pdf(p, "slug", client=c) is None
    assert c.posted == []


def test_skips_when_storage_not_configured(monkeypatch):
    monkeypatch.setattr(pdf_host.config, "SUPABASE_URL", "")
    p = Paper(title="T", license="cc-by", pdf_original_url="http://x/y.pdf")
    c = FakeClient()
    assert pdf_host.host_pdf(p, "slug", client=c) is None


def test_upload_failure_falls_back_to_link_only():
    class Failing(FakeClient):
        def post(self, url, headers=None, content=None):
            raise httpx.HTTPError("500")
    p = Paper(title="T", license="cc-by", pdf_original_url="http://x/y.pdf")
    assert pdf_host.host_pdf(p, "slug", client=Failing()) is None


def test_non_pdf_download_is_rejected():
    class HtmlClient(FakeClient):
        def get(self, url, headers=None):
            return httpx.Response(200, content=b"<html>paywall</html>",
                                  headers={"content-type": "text/html"},
                                  request=httpx.Request("GET", url))
    p = Paper(title="T", license="cc-by", pdf_original_url="http://x/y.pdf")
    c = HtmlClient()
    assert pdf_host.host_pdf(p, "slug", client=c) is None
    assert c.posted == []
