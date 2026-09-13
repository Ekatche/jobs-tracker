import pytest
from datetime import datetime, timezone, timedelta
from app.services.normalization import compute_unique_key, normalize_company, normalize_position, normalize_city
from app.services.job_offers import clean_job_offer_duplicates, normalize_text_for_comparison, fast_similarity_check


def test_clean_job_offer_duplicates_deduplication():
    offers = [
        {
            "_id": "1",
            "entreprise": "Capgemini",
            "poste": "Data Scientist (H/F)",
            "localisation": "Lyon",
            "created_at": datetime(2026, 9, 1, 10, 0, 0, tzinfo=timezone.utc),
            "url": "https://capgemini.com/jobs/1",
        },
        {
            "_id": "2",
            "entreprise": "Capgemini SAS",
            "poste": "Data Scientist",
            "localisation": "69001 Lyon",
            "created_at": datetime(2026, 9, 1, 11, 0, 0, tzinfo=timezone.utc),
            "url": "https://capgemini.com/jobs/1?source=indeed",
        },
        {
            "_id": "3",
            "entreprise": "TotalEnergies",
            "poste": "DevOps Engineer",
            "localisation": "Paris",
            "created_at": datetime(2026, 9, 1, 9, 0, 0, tzinfo=timezone.utc),
            "url": "https://totalenergies.com/jobs/2",
        },
    ]

    cleaned = clean_job_offer_duplicates(offers, company_similarity_threshold=0.75, position_similarity_threshold=0.75)
    assert len(cleaned) == 2
    # Capgemini and TotalEnergies kept
    companies = {o["entreprise"] for o in cleaned}
    assert "TotalEnergies" in companies


def test_tombstone_priority_sorting():
    # Verify that in a duplicate group, a tombstone (is_deleted = True) wins
    group = [
        {
            "company": "SNCF",
            "position": "Data Analyst",
            "is_deleted": False,
            "created_at": datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc),
            "url": "https://sncf.com/jobs/1",
        },
        {
            "company": "SNCF",
            "position": "Data Analyst",
            "is_deleted": True,
            "created_at": datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc),
            "url": "https://sncf.com/jobs/1",
        },
    ]

    def priority_sort_key(offer):
        is_tombstone = bool(offer.get("is_deleted"))
        created_date = offer.get("created_at")
        if isinstance(created_date, datetime):
            created_date_str = created_date.isoformat()
        else:
            created_date_str = str(created_date or "")
        has_good_url = bool(offer.get("url") and str(offer["url"]).startswith("http"))
        return (is_tombstone, has_good_url, created_date_str)

    sorted_group = sorted(group, key=priority_sort_key, reverse=True)
    assert sorted_group[0]["is_deleted"] is True


def test_defensive_date_sorting_exact_duplicates():
    # Group with missing or string dates should sort safely without throwing
    docs = [
        {"id": 1, "created_at": "2026-09-01T10:00:00Z"},
        {"id": 2, "created_at": datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)},
        {"id": 3, "created_at": None},
    ]

    def safe_date_sort(d):
        val = d.get("created_at")
        if isinstance(val, datetime):
            return val
        if isinstance(val, str):
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            except Exception:
                pass
        return datetime.min.replace(tzinfo=timezone.utc)

    sorted_docs = sorted(docs, key=safe_date_sort, reverse=True)
    assert sorted_docs[0]["id"] == 2
    assert sorted_docs[1]["id"] == 1
    assert sorted_docs[2]["id"] == 3


def test_enrich_job_offer_data_valid_and_rejected():
    from app.tasks.job_offers_collectors import enrich_offers_sync

    raw_offers = [
        {
            "poste": "Data Scientist",
            "entreprise": "FIDUCIAL",
            "description": "Nous recrutons un Data Scientist pour piloter nos projets IA et machine learning à Lyon.",
            "localisation": "Lyon",
            "type_contrat": "CDI",
            "salaire": "45k€ - 55k€",
            "mode_travail": "Hybride",
            "competences_cles": ["Python", "PyTorch", "SQL"],
            "url": "https://fiducial.fr/jobs/123",
        },
        {
            # Expired / Dummy offer that must be rejected
            "poste": "Non spécifié",
            "entreprise": "Non spécifié",
            "description": "Non spécifié",
            "localisation": "Non spécifié",
            "url": "https://apec.fr/expired",
        },
        {
            # Missing company offer that must be rejected
            "poste": "Lead Data Engineer",
            "entreprise": "",
            "description": "Description...",
        },
    ]

    enriched = enrich_offers_sync(raw_offers, "query test")
    assert len(enriched) == 1
    valid = enriched[0]
    assert valid["poste"] == "Data Scientist"
    assert valid["entreprise"] == "FIDUCIAL"
    assert "piloter nos projets IA" in valid["description"]
    assert valid["type_contrat"] == "CDI"
    assert valid["competences_cles"] == ["Python", "PyTorch", "SQL"]
    assert valid["is_deleted"] is False


def test_crawler_job_offer_pydantic_model():
    from job_crawler.crawler1 import JobOffer

    offer = JobOffer(
        poste="MLOps Engineer",
        entreprise="Sanofi",
        description="Gestion du cycle de vie des modèles ML et monitoring de production.",
        localisation="Lyon",
        competences_cles=["Kubernetes", "MLflow", "Python"],
    )
    assert offer.poste == "MLOps Engineer"
    assert offer.entreprise == "Sanofi"
    assert "Gestion du cycle de vie" in offer.description
    assert offer.salaire == "Non spécifié"


def test_enrich_job_offer_data_url_company_fallback():
    from app.tasks.job_offers_collectors import enrich_offers_sync

    raw_offers = [
        {
            # Offer where company was missing in DOM but present in Workday URL (the 11 rejected offers case)
            "poste": "Data Analyst",
            "entreprise": "Non spécifié",
            "description": "Analyse de données cliniques et reporting.",
            "localisation": "Alby-sur-Chéran",
            "url": "https://galderma.wd3.myworkdayjobs.com/fr-FR/External/job/Alby/Data-Analyst_JR014026-1",
        },
        {
            # Offer where company was missing in DOM but present in Greenhouse URL.
            # Le poste doit rester dans le domaine data/IA : le gate de pertinence
            # de enrich_offers rejette les intitulés hors-domaine avant l'enrichissement.
            "poste": "Data Engineer",
            "entreprise": "",
            "description": "Conception d'APIs distribuées et scalables.",
            "url": "https://boards.greenhouse.io/stripe/jobs/987654",
        },
        {
            # Offer with missing company on an aggregator URL (must NOT fallback to aggregator name, must be rejected)
            "poste": "DevOps Engineer",
            "entreprise": "Non spécifié",
            "description": "Maintenance infrastructure.",
            "url": "https://candidat.francetravail.fr/offres/recherche/detail/0000000",
        },
    ]

    enriched = enrich_offers_sync(raw_offers, "query test")
    assert len(enriched) == 2

    galderma_offer = next(o for o in enriched if o["poste"] == "Data Analyst")
    assert galderma_offer["entreprise"] == "Galderma"

    stripe_offer = next(o for o in enriched if o["poste"] == "Data Engineer")
    assert stripe_offer["entreprise"] == "Stripe"


def test_crawler_dead_or_expired_detection():
    from job_crawler.crawler1 import _is_dead_or_expired, _offer_grounded_in_page, MIN_PAGE_TEXT_CHARS

    class DummyResult:
        def __init__(self, status_code=200, redirected_url="", html=""):
            self.status_code = status_code
            self.redirected_url = redirected_url
            self.html = html

    # HTTP 404 / 410
    assert _is_dead_or_expired(DummyResult(status_code=404), "any content") is True
    assert _is_dead_or_expired(DummyResult(status_code=410), "") is True

    # Redirected to error page (must require delimiters for 404, not plain substring inside offer ID)
    assert _is_dead_or_expired(DummyResult(redirected_url="https://site.com/404"), "") is True
    assert _is_dead_or_expired(DummyResult(redirected_url="https://site.com/error?code=404"), "") is True
    assert _is_dead_or_expired(DummyResult(redirected_url="https://site.com/jobs/page_404_not_found"), "") is True
    assert _is_dead_or_expired(DummyResult(redirected_url="https://candidat.francetravail.fr/detail-offre-inexistante"), "") is True
    assert _is_dead_or_expired(DummyResult(redirected_url="https://hellowork.com/fr-fr/emplois/83404858.html"), "Contenu valide d'offre") is False

    # Expired text in markdown
    assert _is_dead_or_expired(DummyResult(), "Cette offre n'est plus disponible sur notre plateforme.") is True

    # HTML scan: only on short pages (< MIN_PAGE_TEXT_CHARS) to avoid false positives in SPA JS bundles
    long_page_text = "Description détaillée du poste " * 25  # > 500 chars
    short_page_text = "Squelette vide"
    assert len(long_page_text) >= MIN_PAGE_TEXT_CHARS
    assert len(short_page_text) < MIN_PAGE_TEXT_CHARS

    # "erreur 404" in HTML on a short page -> dead link detected
    assert _is_dead_or_expired(DummyResult(html="<div>erreur 404 - page introuvable</div>"), short_page_text) is True
    # "erreur 404" in HTML bundle on a full page with valid text -> NOT a dead link
    assert _is_dead_or_expired(DummyResult(html="<script>var err = 'erreur 404';</script>"), long_page_text) is False

    # Active valid page
    assert _is_dead_or_expired(DummyResult(), "Nous recherchons un Data Scientist passionné par le NLP.") is False

    # Grounding check:
    # 1) If company is from URL fallback, poste MUST be found in page_text (non-circular grounding)
    offer_url_company = {
        "poste": "Data Analyst",
        "entreprise": "Galderma",
    }
    # Poste found -> grounded
    assert _offer_grounded_in_page(
        offer_url_company,
        "Offre d'emploi : nous recherchons un Data Analyst senior pour nos équipes.",
        url="https://galderma.wd3.myworkdayjobs.com/job/123",
    ) is True
    # Poste NOT found -> rejected to avoid hallucination
    assert _offer_grounded_in_page(
        offer_url_company,
        "Texte générique sans aucune mention du poste recherché.",
        url="https://galderma.wd3.myworkdayjobs.com/job/123",
    ) is False

    # 2) If company is in page DOM text -> grounded even without poste
    offer_dom_company = {
        "poste": "Lead Engineer",
        "entreprise": "Galderma",
    }
    assert _offer_grounded_in_page(
        offer_dom_company,
        "Bienvenue chez Galderma, leader mondial en dermatologie.",
        url=None,
    ) is True


@pytest.mark.asyncio
async def test_crawler_preserves_user_facing_urls_with_optimization():
    from unittest.mock import AsyncMock, patch, MagicMock
    from job_crawler.crawler1 import crawl_and_extract_jobs_optimized

    raw_user_url = "https://fr.linkedin.com/jobs/view/data-scientist-at-klanik-4463811288"
    mock_result = MagicMock()
    mock_result.url = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/4463811288"
    mock_result.redirected_url = ""
    mock_result.success = True

    mock_result.status_code = 200
    mock_result.markdown = "Description du poste Data Scientist chez Klanik " * 15
    mock_result.html = "<div>HTML</div>"
    mock_result.error_message = None
    mock_result.extracted_content = (
        '[{"poste": "Data Scientist", "entreprise": "Klanik", "description": "Data Scientist chez Klanik"}]'
    )

    mock_crawler = AsyncMock()
    mock_crawler.arun_many.return_value = [mock_result]
    mock_crawler_context = AsyncMock()
    mock_crawler_context.__aenter__.return_value = mock_crawler
    mock_crawler_context.__aexit__.return_value = None

    with patch("job_crawler.crawler1.AsyncWebCrawler", return_value=mock_crawler_context):
        result = await crawl_and_extract_jobs_optimized([raw_user_url], api_key="dummy")

    # Verify arun_many received the optimized guest URL
    called_urls = mock_crawler.arun_many.call_args.kwargs.get("urls")
    assert called_urls == ["https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/4463811288"]

    # Verify output preserves original user-facing URL
    assert len(result["offers"]) == 1
    offer = result["offers"][0]
    assert offer["url"] == raw_user_url
    assert offer["source_url"] == raw_user_url
    assert result["crawl_results"][0]["url"] == raw_user_url


def test_structured_description_preservation():
    from app.tasks.job_offers_collectors import enrich_offers_sync

    structured_desc = (
        "**Contexte & Enjeux** :\n"
        "Au sein de l'équipe Data & AI, vous intervenez sur des projets de computer vision appliqués à l'industrie.\n\n"
        "**Missions principales** :\n"
        "- Développer et optimiser des modèles de Deep Learning (PyTorch, OpenCV)\n"
        "- Déployer des pipelines d'inférence en temps réel sur Kubernetes\n"
        "- Collaborer avec les équipes produit et MLOps\n\n"
        "**Profil recherché** :\n"
        "Diplôme d'ingénieur ou Master 2 avec 3+ ans d'expérience en Data Science / Computer Vision.\n\n"
        "**Stack & Outils** :\n"
        "Python, PyTorch, Docker, Kubernetes, MLflow, Git\n\n"
        "**Avantages & Modalités** :\n"
        "CDI, 2 jours de télétravail/semaine, rémunération 50k€-60k€."
    )

    raw_offers = [
        {
            "poste": "Computer Vision Engineer",
            "entreprise": "Agixis",
            "description": structured_desc,
            "localisation": "Lyon",
            "type_contrat": "CDI",
            "salaire": "50k€-60k€",
            "mode_travail": "Hybride",
            "competences_cles": ["Python", "PyTorch", "Kubernetes"],
            "url": "https://agixis.com/jobs/123",
        }
    ]

    enriched = enrich_offers_sync(raw_offers, "Computer Vision Lyon")
    assert len(enriched) == 1
    saved_desc = enriched[0]["description"]
    assert "**Contexte & Enjeux** :" in saved_desc
    assert "**Missions principales** :" in saved_desc
    assert "- Développer et optimiser des modèles" in saved_desc
    assert "**Profil recherché** :" in saved_desc
    assert "**Stack & Outils** :" in saved_desc
    assert "**Avantages & Modalités** :" in saved_desc




