"""Fixtures partagées pour les tests du pipeline de collecte et d'enrichissement."""

from unittest.mock import AsyncMock, MagicMock
import pytest

# Re-export root conftest symbols to prevent sys.modules['conftest'] collision in pytest
try:
    from tests.conftest import DATABASE_NAME, MONGO_URI
except ImportError:
    pass


@pytest.fixture(autouse=True)
def mock_external_pipeline_deps(monkeypatch):
    """Garantit une exécution 100% déterministe et hors-réseau / hors-BDD."""
    import app.tasks.job_offers_collectors as joc

    class FakeResolver:
        def __init__(self, *args, **kwargs):
            pass

        async def resolve(self, offer):
            offer.setdefault("sector", "tech")
            offer.setdefault("company_size", "startup")

    monkeypatch.setattr(joc, "CompanyResolver", FakeResolver)
    monkeypatch.setattr(joc, "normalize_role", AsyncMock(side_effect=lambda role: role))


def make_crawl_result(url, markdown, extracted_content, html="", success=True):
    res = MagicMock()
    res.url = url
    res.markdown = markdown
    res.extracted_content = extracted_content
    res.html = html
    res.success = success
    return res


def make_jobposting_html(valid_through, visible_text=""):
    import json

    jsonld = json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "JobPosting",
            "title": "Data Analyst",
            "hiringOrganization": {"name": "Orbital"},
            "validThrough": valid_through,
            "description": "<p>Analyse des données de production.</p>",
        }
    )
    return (
        f'<html><head><script type="application/ld+json">{jsonld}</script></head>'
        f"<body><h1>Data Analyst</h1><p>{visible_text}</p></body></html>"
    )


def mock_collect_pipeline(monkeypatch, collectors, crawled, structured):
    """Prépare les mocks communs pour tester le pipeline collect_and_save_offers."""
    monkeypatch.setattr(collectors, "get_urls_for_query", AsyncMock(return_value=["https://example.com/1"]))
    if isinstance(crawled, Exception):
        monkeypatch.setattr(collectors, "crawl_urls_for_offers", AsyncMock(side_effect=crawled))
    elif isinstance(crawled, AsyncMock):
        monkeypatch.setattr(collectors, "crawl_urls_for_offers", crawled)
    else:
        monkeypatch.setattr(collectors, "crawl_urls_for_offers", AsyncMock(return_value=crawled))
    monkeypatch.setattr(collectors, "collect_structured_offers", AsyncMock(return_value=structured))
    monkeypatch.setattr(collectors, "summarize_ats_offer_description", AsyncMock(return_value="résumé"))
    enrich = AsyncMock(side_effect=lambda offers, query: offers)
    monkeypatch.setattr(collectors, "enrich_offers", enrich)
    monkeypatch.setattr(collectors, "clean_duplicate_offers", AsyncMock(side_effect=lambda offers: offers))
    monkeypatch.setattr(
        collectors, "save_offers_to_database", AsyncMock(return_value={"saved": 0, "updated": 0, "offer_ids": []})
    )
    monkeypatch.setattr(collectors, "tag_new_offers", AsyncMock())
    monkeypatch.setattr(collectors, "cleanup_resources", AsyncMock())
    monkeypatch.setattr(collectors, "get_database", AsyncMock(return_value={}))
    return enrich

