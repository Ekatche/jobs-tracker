"""Tests d'enrichissement, déduplication et inférence de données d'offres."""

from datetime import datetime, timezone
import pytest

from app.services.job_offers import clean_job_offer_duplicates
from app.tasks.job_offers_collectors import enrich_offers_sync
from job_crawler.crawler1 import JobOffer


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
    companies = {o["entreprise"] for o in cleaned}
    assert "TotalEnergies" in companies


def test_defensive_date_sorting_exact_duplicates():
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
            "poste": "Non spécifié",
            "entreprise": "Non spécifié",
            "description": "Non spécifié",
            "localisation": "Non spécifié",
            "url": "https://apec.fr/expired",
        },
        {
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
    raw_offers = [
        {
            "poste": "Data Analyst",
            "entreprise": "Non spécifié",
            "description": "Analyse de données cliniques et reporting.",
            "localisation": "Alby-sur-Chéran",
            "url": "https://galderma.wd3.myworkdayjobs.com/fr-FR/External/job/Alby/Data-Analyst_JR014026-1",
        },
        {
            "poste": "Data Engineer",
            "entreprise": "",
            "description": "Conception d'APIs distribuées et scalables.",
            "url": "https://boards.greenhouse.io/stripe/jobs/987654",
        },
        {
            "poste": "DevOps Engineer",
            "entreprise": "Non spécifié",
            "description": "Maintenance infrastructure.",
            "url": "https://candidat.francetravail.fr/offres/recherche/detail/0000000",
        },
    ]

    enriched = enrich_offers_sync(raw_offers, "query test")
    assert len(enriched) == 2
    assert next(o for o in enriched if o["poste"] == "Data Analyst")["entreprise"] == "Galderma"
    assert next(o for o in enriched if o["poste"] == "Data Engineer")["entreprise"] == "Stripe"


def test_enrich_infers_contract_from_raw_title():
    raw_offers = [
        {
            "poste": "Stage Data Science (F/H/X)",
            "entreprise": "Solvay",
            "description": "Le stagiaire Data Scientist participera au déploiement des modèles.",
            "localisation": "Lyon",
            "type_contrat": "",
            "url": "https://www.linkedin.com/jobs/view/4481312374/",
        },
    ]

    enriched = enrich_offers_sync(raw_offers, "query test")
    assert len(enriched) == 1
    assert enriched[0]["poste"] == "Data Science"
    assert enriched[0]["type_contrat"] == "Stage"


def test_enrich_raw_data_keyed_by_source():
    linkedin_row = {"title": "Data Engineer", "job_level": "mid-senior level", "job_function": "Engineering"}
    raw_offers = [
        {
            "poste": "Data Engineer",
            "entreprise": "Alan",
            "description": "Pipelines de données pour l'assurance santé.",
            "localisation": "Paris",
            "url": "https://www.linkedin.com/jobs/view/1/",
            "ats_platform": "linkedin",
            "source_record": linkedin_row,
        },
        {
            "poste": "Data Analyst",
            "entreprise": "Qonto",
            "description": "Analyse des parcours clients.",
            "localisation": "Paris",
            "url": "https://qonto.com/careers/2",
        },
    ]

    enriched = enrich_offers_sync(raw_offers, "query test")
    assert enriched[0]["raw_data"] == {"linkedin": linkedin_row}
    assert enriched[1]["raw_data"] == {"llm_crawl": raw_offers[1]}
    assert all("source_record" not in offer for offer in enriched)

