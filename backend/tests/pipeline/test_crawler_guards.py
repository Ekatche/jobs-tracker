"""Tests des gardes du crawler (offres mortes/closes, ancrage LLM, JSON-LD, métriques)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.tasks.job_offers_collectors import enrich_offers_sync
from job_crawler.crawler1 import (
    MIN_PAGE_TEXT_CHARS,
    _is_dead_or_expired,
    _offer_grounded_in_page,
    crawl_and_extract_jobs_optimized,
)
from tests.pipeline.conftest import make_crawl_result, make_jobposting_html


async def _run_crawler_on(results):
    mock_crawler = AsyncMock()
    mock_crawler.crawler_strategy = MagicMock()
    mock_crawler.arun_many.return_value = results
    mock_crawler_context = AsyncMock()
    mock_crawler_context.__aenter__.return_value = mock_crawler
    mock_crawler_context.__aexit__.return_value = None

    with patch("job_crawler.crawler1.AsyncWebCrawler", return_value=mock_crawler_context):
        output = await crawl_and_extract_jobs_optimized([r.url for r in results], api_key="dummy")
    return output, mock_crawler


def test_crawler_dead_or_expired_detection():
    class DummyResult:
        def __init__(self, status_code=200, redirected_url="", html=""):
            self.status_code = status_code
            self.redirected_url = redirected_url
            self.html = html

    # HTTP 404 / 410
    assert _is_dead_or_expired(DummyResult(status_code=404), "any content") is True
    assert _is_dead_or_expired(DummyResult(status_code=410), "") is True

    # Redirection vers 404
    assert _is_dead_or_expired(DummyResult(redirected_url="https://site.com/404"), "") is True
    assert _is_dead_or_expired(DummyResult(redirected_url="https://site.com/error?code=404"), "") is True
    assert _is_dead_or_expired(DummyResult(redirected_url="https://candidat.francetravail.fr/detail-offre-inexistante"), "") is True
    assert _is_dead_or_expired(DummyResult(redirected_url="https://hellowork.com/fr-fr/emplois/83404858.html"), "Contenu valide d'offre") is False

    # Mention textuelle d'expiration
    assert _is_dead_or_expired(DummyResult(), "Cette offre n'est plus disponible sur notre plateforme.") is True

    # Scan HTML uniquement sur pages courtes (< MIN_PAGE_TEXT_CHARS)
    long_page_text = "Description détaillée du poste " * 25
    short_page_text = "Squelette vide"
    assert len(long_page_text) >= MIN_PAGE_TEXT_CHARS
    assert len(short_page_text) < MIN_PAGE_TEXT_CHARS

    assert _is_dead_or_expired(DummyResult(html="<div>erreur 404 - page introuvable</div>"), short_page_text) is True
    assert _is_dead_or_expired(DummyResult(html="<script>var err = 'erreur 404';</script>"), long_page_text) is False
    assert _is_dead_or_expired(DummyResult(), "Nous recherchons un Data Scientist passionné par le NLP.") is False

    # Ancrage : fallback URL -> le poste DOIT figurer dans la page
    offer_url_company = {"poste": "Data Analyst", "entreprise": "Galderma"}
    assert _offer_grounded_in_page(offer_url_company, "Offre : nous recherchons un Data Analyst senior.", url="https://galderma.wd3.myworkdayjobs.com/job/123") is True
    assert _offer_grounded_in_page(offer_url_company, "Texte générique sans poste.", url="https://galderma.wd3.myworkdayjobs.com/job/123") is False

    # Entreprise trouvée dans le DOM -> ancrée
    offer_dom_company = {"poste": "Lead Engineer", "entreprise": "Galderma"}
    assert _offer_grounded_in_page(offer_dom_company, "Bienvenue chez Galderma, leader mondial.", url=None) is True


@pytest.mark.asyncio
async def test_crawler_preserves_user_facing_urls_with_optimization():
    raw_user_url = "https://fr.linkedin.com/jobs/view/data-scientist-at-klanik-4463811288"
    mock_result = MagicMock()
    mock_result.url = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/4463811288"
    mock_result.redirected_url = ""
    mock_result.success = True
    mock_result.status_code = 200
    mock_result.markdown = "Description du poste Data Scientist chez Klanik " * 15
    mock_result.html = "<div>HTML</div>"
    mock_result.error_message = None
    mock_result.extracted_content = '[{"poste": "Data Scientist", "entreprise": "Klanik", "description": "Data Scientist chez Klanik"}]'

    mock_crawler = AsyncMock()
    mock_crawler.crawler_strategy = MagicMock()
    mock_crawler.arun_many.return_value = [mock_result]
    mock_crawler_context = AsyncMock()
    mock_crawler_context.__aenter__.return_value = mock_crawler
    mock_crawler_context.__aexit__.return_value = None

    with patch("job_crawler.crawler1.AsyncWebCrawler", return_value=mock_crawler_context):
        result = await crawl_and_extract_jobs_optimized([raw_user_url], api_key="dummy")

    assert mock_crawler.arun_many.call_args.kwargs.get("urls") == ["https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/4463811288"]
    assert len(result["offers"]) == 1
    assert result["offers"][0]["url"] == raw_user_url
    assert result["offers"][0]["source_url"] == raw_user_url


@pytest.mark.asyncio
async def test_crawler_metrics_by_domain_and_status():
    long_text = "Description complète du poste Data Scientist chez Acme, équipe IA. " * 10
    generic_text = "Rejoignez nos équipes, découvrez nos métiers et nos valeurs. " * 10
    results = [
        make_crawl_result("https://www.acme.com/jobs/1", long_text, '[{"poste": "Data Scientist", "entreprise": "Acme", "error": false}]'),
        make_crawl_result("https://acme.com/jobs/2", long_text, '[{"index": 0, "error": true, "tags": ["error"], "content": "RateLimitError: quota"}]'),
        make_crawl_result("https://jobs.example.org/offre/3", generic_text, '[{"poste": "Chef de projet", "entreprise": "Globex"}]'),
        make_crawl_result("https://www.hellowork.com/fr-fr/emplois/123.html", "Offre expirée — découvrez nos autres annonces.", None),
    ]

    output, _ = await _run_crawler_on(results)
    summary = output["summary"]
    assert summary["by_domain"]["acme.com"] == {"success": 1, "llm_error": 1}
    assert summary["by_domain"]["jobs.example.org"] == {"grounding_rejected": 1}
    assert summary["by_domain"]["hellowork.com"] == {"dead_link": 1}
    assert summary["successful_crawls"] == 1
    assert summary["dead_links"] == 1


@pytest.mark.asyncio
async def test_crawler_keeps_grounded_offer_on_short_page():
    short_text = ("Poste : Data Engineer chez Lumen à Lyon, CDI, télétravail partiel. " * 3)[:200]
    extraction = '[{"poste": "Data Engineer", "entreprise": "Lumen"}]'

    output, mock_crawler = await _run_crawler_on([make_crawl_result("https://lumen.example/jobs/42", short_text, extraction)])
    assert [o["poste"] for o in output["offers"]] == ["Data Engineer"]
    assert output["crawl_results"][0]["status"] == "success"
    assert mock_crawler.arun_many.call_count == 1

    output_empty, _ = await _run_crawler_on([make_crawl_result("https://lumen.example/jobs/43", "", extraction)])
    assert output_empty["offers"] == []
    assert output_empty["crawl_results"][0]["status"] == "empty_content"


@pytest.mark.asyncio
async def test_crawler_jsonld_fallback_guards_closed_offers():
    page_text = "Rejoignez une équipe engagée sur des sujets variés et stimulants. " * 10
    future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    past = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    open_url = "https://orbital.example/jobs/1"
    expired_url = "https://orbital.example/jobs/2"
    filled_url = "https://orbital.example/jobs/3"

    output, _ = await _run_crawler_on(
        [
            make_crawl_result(open_url, page_text, "[]", html=make_jobposting_html(future)),
            make_crawl_result(expired_url, page_text, "[]", html=make_jobposting_html(past)),
            make_crawl_result(filled_url, page_text, "[]", html=make_jobposting_html(future, "Ce poste a été pourvu.")),
        ]
    )

    assert len(output["offers"]) == 1
    offer = output["offers"][0]
    assert (offer["poste"], offer["entreprise"]) == ("Data Analyst", "Orbital")
    assert offer["ats_platform"] == "json_ld"
    assert output["summary"]["jsonld_fallback"] == 1


def test_crawler_grounding_normalized_text():
    def grounded(poste, entreprise, page_text):
        return _offer_grounded_in_page({"poste": poste, "entreprise": entreprise}, page_text)

    assert grounded("Chargé d'études", "", "Poste : Chargé d’études marketing (H/F)") is True
    assert grounded("Data Engineer - Senior", "", "Offre Data Engineer – Senior à Lyon") is True
    assert grounded("Ingenieur Donnees", "", "Nous recrutons un Ingénieur Données confirmé") is True
    assert grounded("Data Engineer", "", "Nous recrutons des Data Engineers") is True
    assert grounded("", "AXA", "Une taxation simplifiée pour les indépendants") is False
    assert grounded("", "AXA", "Rejoignez AXA France à Nanterre") is True


def test_structured_description_preservation():
    structured_desc = (
        "**Contexte & Enjeux** :\n"
        "Au sein de l'équipe Data & AI, vous intervenez sur des projets de computer vision.\n\n"
        "**Missions principales** :\n"
        "- Développer et optimiser des modèles de Deep Learning (PyTorch, OpenCV)\n\n"
        "**Profil recherché** :\n"
        "Diplôme d'ingénieur avec 3+ ans d'expérience.\n\n"
        "**Stack & Outils** :\n"
        "Python, PyTorch, Docker, Kubernetes"
    )
    raw_offers = [
        {
            "poste": "Computer Vision Engineer",
            "entreprise": "Agixis",
            "description": structured_desc,
            "localisation": "Lyon",
            "type_contrat": "CDI",
            "url": "https://agixis.com/jobs/123",
        }
    ]
    enriched = enrich_offers_sync(raw_offers, "Computer Vision Lyon")
    assert len(enriched) == 1
    saved_desc = enriched[0]["description"]
    assert "**Contexte & Enjeux** :" in saved_desc
    assert "**Missions principales** :" in saved_desc
    assert "**Profil recherché** :" in saved_desc
    assert "**Stack & Outils** :" in saved_desc
