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
