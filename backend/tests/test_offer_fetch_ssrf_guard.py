"""Garde SSRF des récupérations d'offres.

L'URL d'une candidature est saisie par l'utilisateur, puis téléchargée par le
backend (régénération de la description) : une adresse interne ne doit jamais
être contactée, ni directement, ni au détour d'une redirection.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from urllib.parse import urlsplit

import httpx
import pytest

from app.llm.utils import fetch_documents
from app.services import pdf_job_offer
from app.services.profile.urls import block_non_public_browser_requests

INTERNAL_URLS = [
    "http://127.0.0.1:8080/admin",
    "http://169.254.169.254/latest/meta-data/",
    "http://[::1]/offre.pdf",
    "http://10.0.0.5/offre",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("url", INTERNAL_URLS)
async def test_fetch_documents_never_contacts_internal_host(monkeypatch, url):
    contacted = []

    async def record(target, *args, **kwargs):
        contacted.append(target)
        return {"status": "failed"}

    monkeypatch.setattr("app.services.ats.router.extract_ats_or_jsonld_offer", record)
    monkeypatch.setattr("app.services.pdf_job_offer.extract_pdf_job_offer", record)
    monkeypatch.setattr("job_crawler.crawler1.get_filtered_markdown", record)

    assert await fetch_documents(url) == []
    assert contacted == []


def _mock_client_class(handler):
    class MockClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs.pop("transport", None)
            super().__init__(*args, transport=httpx.MockTransport(handler), **kwargs)

    return MockClient


@pytest.mark.asyncio
async def test_pdf_download_refuses_redirect_to_internal_host(monkeypatch):
    seen = []

    def handler(request):
        seen.append(str(request.url))
        if request.url.host == "93.184.216.34":
            return httpx.Response(302, headers={"location": "http://127.0.0.1/secret.pdf"})
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF-" + b"0" * 64)

    monkeypatch.setattr(pdf_job_offer.httpx, "AsyncClient", _mock_client_class(handler))

    assert await pdf_job_offer.download_pdf_bytes("http://93.184.216.34/offre.pdf") is None
    assert seen == ["http://93.184.216.34/offre.pdf"]


@pytest.mark.asyncio
async def test_pdf_content_check_refuses_internal_host(monkeypatch):
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, headers={"content-type": "application/pdf"})

    monkeypatch.setattr(pdf_job_offer.httpx, "AsyncClient", _mock_client_class(handler))

    assert await pdf_job_offer.check_is_pdf_content("http://127.0.0.1:8080/offre") is False
    assert seen == []


@pytest.mark.asyncio
async def test_ats_jsonld_fetch_refuses_redirect_to_internal_host(monkeypatch):
    from app.services.ats import router

    seen = []
    job_posting = (
        '<script type="application/ld+json">{"@type": "JobPosting", "title": "Secret",'
        ' "description": "secret-interne", "hiringOrganization": {"name": "Interne"}}</script>'
    )

    def handler(request):
        seen.append(str(request.url))
        if request.url.host == "93.184.216.34":
            return httpx.Response(302, headers={"location": "http://127.0.0.1/admin"})
        return httpx.Response(200, text=job_posting)

    monkeypatch.setattr(router.httpx, "AsyncClient", _mock_client_class(handler))

    assert await router.extract_ats_or_jsonld_offer("http://93.184.216.34/offre") is None
    assert seen == ["http://93.184.216.34/offre"]


class _FakeRoute:
    def __init__(self, url):
        self.request = SimpleNamespace(url=url)
        self.outcome = None

    async def abort(self, *args, **kwargs):
        self.outcome = "abort"

    async def fallback(self, *args, **kwargs):
        self.outcome = "fallback"


class _FakePage:
    def __init__(self):
        self.routes = []

    async def route(self, pattern, handler):
        self.routes.append((pattern, handler))


@pytest.mark.asyncio
async def test_browser_guard_aborts_internal_requests_only():
    page = _FakePage()
    assert await block_non_public_browser_requests(page, context=None, config=None) is page
    [(pattern, guard)] = page.routes
    assert pattern == "**/*"

    outcomes = {}
    for url in INTERNAL_URLS + ["http://93.184.216.34/app.js"]:
        route = _FakeRoute(url)
        await guard(route)
        outcomes[url] = route.outcome

    assert outcomes == {**{u: "abort" for u in INTERNAL_URLS}, "http://93.184.216.34/app.js": "fallback"}


def _crawl_result(url, redirected_url):
    result = MagicMock()
    result.url = url
    result.redirected_url = redirected_url
    result.success = True
    result.status_code = 200
    result.markdown = SimpleNamespace(fit_markdown="secret-interne " * 20, raw_markdown="secret-interne " * 20)
    result.html = "<p>secret-interne</p>"
    result.error_message = None
    result.metadata = {}
    result.extracted_content = '[{"poste": "Secret", "entreprise": "Interne", "description": "secret-interne"}]'
    return result


def _patch_crawler(monkeypatch, crawler):
    context = AsyncMock()
    context.__aenter__.return_value = crawler
    context.__aexit__.return_value = None
    monkeypatch.setattr("job_crawler.crawler1.AsyncWebCrawler", MagicMock(return_value=context))


def _fake_crawler():
    crawler = AsyncMock()
    crawler.crawler_strategy = MagicMock()
    return crawler


@pytest.mark.asyncio
async def test_filtered_markdown_drops_page_redirected_to_internal_host(monkeypatch):
    from job_crawler.crawler1 import get_filtered_markdown

    crawler = _fake_crawler()
    crawler.arun.return_value = _crawl_result("http://93.184.216.34/offre", "http://127.0.0.1/admin")
    _patch_crawler(monkeypatch, crawler)

    result = await get_filtered_markdown("http://93.184.216.34/offre", api_key="dummy")

    assert result["status"] == "failed"
    assert "secret-interne" not in str(result.get("filtered_markdown"))
    crawler.crawler_strategy.set_hook.assert_called_once_with(
        "on_page_context_created", block_non_public_browser_requests
    )


@pytest.mark.asyncio
async def test_crawl_and_extract_drops_page_redirected_to_internal_host(monkeypatch):
    from job_crawler.crawler1 import crawl_and_extract_jobs_optimized

    crawler = _fake_crawler()
    crawler.arun_many.return_value = [_crawl_result("http://93.184.216.34/offre", "http://127.0.0.1/admin")]
    _patch_crawler(monkeypatch, crawler)

    output = await crawl_and_extract_jobs_optimized(["http://93.184.216.34/offre"], api_key="dummy")

    assert output["offers"] == []
    assert crawler.arun_many.await_count == 1
    crawler.crawler_strategy.set_hook.assert_called_once_with(
        "on_page_context_created", block_non_public_browser_requests
    )


@pytest.mark.asyncio
async def test_collect_website_drops_page_redirected_to_internal_host(monkeypatch):
    from app.services.profile.collectors import website

    async def no_sitemap(url):
        return None

    monkeypatch.setattr(website, "_default_fetch", no_sitemap)

    class Crawler:
        async def arun_many(self, urls):
            return [
                SimpleNamespace(url="http://93.184.216.34", redirected_url="http://93.184.216.34/", markdown="# Accueil"),
                SimpleNamespace(
                    url="http://93.184.216.34/experience",
                    redirected_url="http://169.254.169.254/latest/meta-data/",
                    markdown="secret-interne",
                ),
            ]

    captured = {}

    async def extract(markdown_by_url):
        captured.update(markdown_by_url)
        return {"projects": [], "experiences": []}

    await website.collect_website("http://93.184.216.34", crawler=Crawler(), extract=extract)

    assert captured == {"http://93.184.216.34": "# Accueil"}


async def _proxy_listening(proxy_url):
    if not proxy_url:
        return False
    target = urlsplit(proxy_url)
    try:
        _, writer = await asyncio.open_connection(target.hostname, target.port)
    except OSError:
        return False
    writer.close()
    return True


def _patch_crawler_class(monkeypatch, target, crawler):
    """Remplace `AsyncWebCrawler` ; note, à l'ouverture du navigateur, sa config et si son proxy écoute."""
    opened = []

    def factory(*args, config=None, **kwargs):
        async def enter():
            listening = await _proxy_listening(getattr(config, "proxy", None))
            opened.append(SimpleNamespace(listening=listening, config=config))
            return crawler

        context = MagicMock()
        context.__aenter__ = AsyncMock(side_effect=enter)
        context.__aexit__ = AsyncMock(return_value=None)
        return context

    monkeypatch.setattr(target, factory)
    return opened


@pytest.mark.asyncio
async def test_filtered_markdown_browser_runs_behind_public_only_proxy(monkeypatch):
    from job_crawler.crawler1 import get_filtered_markdown

    crawler = _fake_crawler()
    crawler.arun.return_value = _crawl_result("http://93.184.216.34/offre", "http://93.184.216.34/offre")
    opened = _patch_crawler_class(monkeypatch, "job_crawler.crawler1.AsyncWebCrawler", crawler)

    await get_filtered_markdown("http://93.184.216.34/offre", api_key="dummy")

    assert [o.listening for o in opened] == [True]
    assert opened[0].config.verbose is False  # clone() de crawl4ai 0.6.3 ne recopie pas verbose


@pytest.mark.asyncio
async def test_crawl_and_extract_browser_runs_behind_public_only_proxy(monkeypatch):
    from job_crawler.crawler1 import crawl_and_extract_jobs_optimized

    crawler = _fake_crawler()
    crawler.arun_many.return_value = [_crawl_result("http://93.184.216.34/offre", "http://127.0.0.1/admin")]
    opened = _patch_crawler_class(monkeypatch, "job_crawler.crawler1.AsyncWebCrawler", crawler)

    await crawl_and_extract_jobs_optimized(["http://93.184.216.34/offre"], api_key="dummy")

    assert [o.listening for o in opened] == [True]


@pytest.mark.asyncio
async def test_collect_website_browser_runs_behind_public_only_proxy(monkeypatch):
    from app.services.profile.collectors import website

    async def no_sitemap(url):
        return None

    monkeypatch.setattr(website, "_default_fetch", no_sitemap)
    crawler = _fake_crawler()
    crawler.arun_many.return_value = [
        SimpleNamespace(url="http://93.184.216.34", redirected_url="http://93.184.216.34", markdown="# Accueil")
    ]
    opened = _patch_crawler_class(monkeypatch, "crawl4ai.AsyncWebCrawler", crawler)

    async def extract(markdown_by_url):
        return {"projects": [], "experiences": []}

    await website.collect_website("http://93.184.216.34", extract=extract)

    assert [o.listening for o in opened] == [True]


@pytest.mark.asyncio
async def test_offer_verification_browser_runs_behind_public_only_proxy(monkeypatch):
    from app.tasks.verify_job_offers import check_url_headless_js

    crawler = _fake_crawler()
    crawler.arun.return_value = SimpleNamespace(success=False, error_message="simulé")
    opened = _patch_crawler_class(monkeypatch, "crawl4ai.AsyncWebCrawler", crawler)

    assert (await check_url_headless_js("http://93.184.216.34/offre"))["status"] == "unknown"
    assert [o.listening for o in opened] == [True]
