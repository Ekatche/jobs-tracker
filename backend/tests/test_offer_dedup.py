"""Tests unitaires et d'intégration pour le calcul des clés uniques, déduplication et fusion d'offres."""

from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId
import pytest

from app.services.normalization import (
    are_offers_duplicates,
    company_match_strength,
    compute_unique_key,
    deduplicate_and_merge_offers,
    get_source_priority,
    jaccard_description_similarity,
    merge_multidiffusion_offers,
)
from app.services.offer_dedup import find_duplicate_pairs, merge_duplicate_offers, pick_survivor


CONTROLLING_DESC = (
    "Nous recherchons un Contrôleur de gestion pour piloter les budgets, analyser les écarts mensuels, "
    "préparer les clôtures trimestrielles, construire les tableaux de bord financiers sous Excel et Power BI, "
    "accompagner les directions opérationnelles et fiabiliser les prévisions de trésorerie du groupe."
)
ACCOUNTING_DESC = (
    "Comptable unique en charge de la gestion des factures fournisseurs, des fiches de paie, des déclarations "
    "fiscales, du rapprochement bancaire, des immobilisations, de la TVA collectée et déductible, des notes "
    "de frais et de la relation avec le cabinet d'expertise sous Sage."
)


def test_compute_unique_key():
    key1 = compute_unique_key("Acme SAS", "Data Scientist (H/F)", "Lyon - 01")
    key2 = compute_unique_key("Acme", "Data Scientist", "44000 Lyon")
    assert key1 == key2

    key_url1 = compute_unique_key("Acme", "Data Scientist", url="https://acme.com/jobs/123/")
    key_url2 = compute_unique_key("Acme SAS", "Data Scientist H/F", url="https://acme.com/jobs/123")
    assert key_url1 == key_url2

    # Clé cross-source (WTTJ vs LinkedIn)
    key_wttj = compute_unique_key(
        "Deloitte", "Ai Engineer / Scientist Confirmé F/h", "Lyon",
        url="https://www.welcometothejungle.com/fr/companies/deloitte/jobs/ai-engineer-scientist-confirme-f-h_lyon",
    )
    key_linkedin = compute_unique_key(
        "Deloitte", "AI Engineer / Scientist confirmé", "Lyon",
        url="https://fr.linkedin.com/jobs/view/ai-engineer-scientist-confirm%C3%A9-f-h-at-deloitte-4463883002",
    )
    assert key_wttj == key_linkedin
    assert key_wttj == "deloitte|ai confirmé engineer scientist|lyon"


def test_jaccard_description_similarity():
    desc1 = (
        "Nous recherchons un Data Scientist passionné pour concevoir des modèles de machine learning "
        "en production sur Google Cloud Platform avec Python, PyTorch, Docker et Kubernetes."
    )
    desc2 = (
        "Nous recherchons un Data Scientist talentueux pour concevoir des modèles de machine learning "
        "en production sur Google Cloud Platform avec Python, PyTorch, Docker et FastAPI."
    )
    assert jaccard_description_similarity(desc1, desc2) > 0.60
    assert jaccard_description_similarity(desc1, ACCOUNTING_DESC) == 0.0


def test_are_offers_duplicates_by_title_company_and_city():
    o1 = {"entreprise": "Doctolib SAS", "poste": "Data Scientist (H/F) - CDI", "localisation": "Paris", "url": "https://indeed.com/1"}
    o2 = {"entreprise": "Doctolib", "poste": "Data Scientist", "localisation": "Paris", "url": "https://greenhouse.io/2"}
    assert are_offers_duplicates(o1, o2) is True

    # Villes distinctes rejetées
    o3 = {"entreprise": "Doctolib", "poste": "Data Scientist", "localisation": "Lyon", "url": "https://site1.com"}
    o4 = {"entreprise": "Doctolib", "poste": "Data Scientist", "localisation": "Marseille", "url": "https://site2.com"}
    assert are_offers_duplicates(o3, o4) is False


def test_company_and_city_variants():
    assert company_match_strength("BackMarket", "Back Market") == "strong"
    assert company_match_strength("Néosoft", "Neosoft") == "strong"
    assert company_match_strength("Orange", "Orano") is None
    assert company_match_strength("JEMS", "Jems Group") == "weak"

    # Match faible accepté si descriptions très proches
    same_desc = (
        {"entreprise": "JEMS", "poste": "Data Engineer", "localisation": "Lyon", "url": "https://a.com", "description": CONTROLLING_DESC},
        {"entreprise": "Jems Group", "poste": "Data Engineer", "localisation": "Lyon", "url": "https://b.com", "description": CONTROLLING_DESC},
    )
    assert are_offers_duplicates(*same_desc) is True

    # Match faible rejeté si descriptions différentes
    diff_desc = (
        {"entreprise": "JEMS", "poste": "Data Engineer", "localisation": "Lyon", "url": "https://a.com", "description": CONTROLLING_DESC},
        {"entreprise": "Jems Group", "poste": "Data Engineer", "localisation": "Lyon", "url": "https://b.com", "description": ACCOUNTING_DESC},
    )
    assert are_offers_duplicates(*diff_desc) is False

    # Ville avec apostrophe ou suffixe régional
    ca1 = {"entreprise": "Crédit Agricole", "poste": "Chargé", "localisation": "Champagne-Au-Mont-D'Or", "url": "https://a.com"}
    ca2 = {"entreprise": "Crédit Agricole", "poste": "Chargé", "localisation": "Champagne-Au-Mont-D’Or", "url": "https://b.com"}
    assert are_offers_duplicates(ca1, ca2) is True

    dev1 = {"entreprise": "Devoteam", "poste": "Data Engineer", "localisation": "Lyon, Auvergne-Rhône-Alpes, France", "url": "https://a.com"}
    dev2 = {"entreprise": "Devoteam", "poste": "Data Engineer", "localisation": "Lyon", "url": "https://b.com"}
    assert are_offers_duplicates(dev1, dev2) is True


@pytest.mark.parametrize(
    "url, expected_priority",
    [
        ("https://boards.greenhouse.io/job/123", 100),
        ("https://jobs.lever.co/company/456", 100),
        ("https://welcometothejungle.com/fr/companies/corp/jobs/789", 80),
        ("https://www.linkedin.com/jobs/view/111", 50),
        ("https://fr.indeed.com/viewjob?jk=222", 50),
    ],
)
def test_get_source_priority(url, expected_priority):
    assert get_source_priority(url) == expected_priority


def test_merge_multidiffusion_offers_promotes_ats_and_merges_metadata():
    wttj = {
        "poste": "Ai Engineer / Scientist Confirmé F/h",
        "entreprise": "Deloitte",
        "localisation": "Lyon",
        "url": "https://www.welcometothejungle.com/fr/companies/deloitte/jobs/ai-engineer",
        "evaluation": {"score": 5.0, "match": "Excellent"},
        "user_interaction": "saved",
        "description": "Court descriptif WTTJ",
        "competences_cles": ["Python", "PyTorch"],
    }
    linkedin = {
        "poste": "AI Engineer / Scientist confirmé",
        "entreprise": "Deloitte",
        "localisation": "Lyon",
        "url": "https://fr.linkedin.com/jobs/view/ai-engineer",
        "description": "Descriptif beaucoup plus long et détaillé issu de LinkedIn avec tous les éléments...",
        "competences_cles": ["Python", "MLOps", "Docker"],
    }
    merged = merge_multidiffusion_offers(wttj, linkedin)
    assert merged["url"] == wttj["url"]
    assert linkedin["url"] in merged["alternative_urls"]
    assert merged["evaluation"] == {"score": 5.0, "match": "Excellent"}
    assert merged["user_interaction"] == "saved"
    assert set(merged["competences_cles"]) == {"Python", "PyTorch", "MLOps", "Docker"}
    assert merged["description"] == linkedin["description"]


def test_merge_raw_data_preserves_per_source_records():
    in_db = {
        "entreprise": "Alan", "poste": "Data Engineer", "url": "https://www.linkedin.com/jobs/view/1",
        "raw_data": {"linkedin": {"job_level": "mid-senior level"}, "indeed": {"min_amount": 40000}},
    }
    incoming = {
        "entreprise": "Alan", "poste": "Data Engineer", "url": "https://fr.indeed.com/viewjob?jk=1",
        "raw_data": {"indeed": {"min_amount": 45000, "company_industry": "Assurance"}},
    }
    merged = merge_multidiffusion_offers(in_db, incoming)
    assert merged["raw_data"] == {
        "linkedin": {"job_level": "mid-senior level"},
        "indeed": {"min_amount": 45000, "company_industry": "Assurance"},
    }


def test_deduplicate_and_merge_offers_trio():
    offers = [
        {"entreprise": "Qonto", "poste": "[PARIS] Lead Data Analyst (H/F) - CDI", "localisation": "Paris",
         "url": "https://www.linkedin.com/jobs/view/100", "salaire": "Non spécifié", "competences_cles": ["SQL"]},
        {"entreprise": "Qonto SAS", "poste": "Lead Data Analyst", "localisation": "Paris",
         "url": "https://boards.greenhouse.io/qonto/jobs/200", "salaire": "65k€ - 80k€", "competences_cles": ["SQL", "dbt", "Snowflake"]},
        {"entreprise": "Qonto", "poste": "Lead Data Analyst - Paris 🚀", "localisation": "Paris",
         "url": "https://fr.indeed.com/viewjob?jk=300", "salaire": "Non spécifié", "competences_cles": ["Tableau"]},
    ]
    result = deduplicate_and_merge_offers(offers)
    assert len(result) == 1
    winner = result[0]
    assert winner["url"] == "https://boards.greenhouse.io/qonto/jobs/200"
    assert winner["salaire"] == "65k€ - 80k€"
    assert set(winner["alternative_urls"]) == {
        "https://www.linkedin.com/jobs/view/100",
        "https://fr.indeed.com/viewjob?jk=300",
    }
    assert {"Snowflake", "Tableau"}.issubset(set(winner["competences_cles"]))


def test_pick_survivor_and_find_duplicate_pairs():
    doc1 = {"_id": ObjectId("6aaa8ed40a4a13cc5c4a7b51")}
    doc2 = {"_id": ObjectId("6aaa8ed40a4a13cc5c4a7b52")}
    assert pick_survivor(doc1, doc2, {str(doc2["_id"])}) == (doc2, doc1)
    assert pick_survivor(doc1, doc2, {str(doc1["_id"])}) == (doc1, doc2)
    assert pick_survivor(doc1, doc2, {"6aaa8ed40a4a13cc5c4a7b51", "6aaa8ed40a4a13cc5c4a7b52"}) is None

    offers = [
        {"_id": 1, "entreprise": "BackMarket", "poste": "Data Engineer", "localisation": "Paris",
         "url": "https://linkedin.com/1", "canonical_key": "backmarket|data engineer|paris"},
        {"_id": 2, "entreprise": "Back Market", "poste": "Data Engineer", "localisation": "Paris",
         "url": "https://lever.co/2", "canonical_key": "back market|data engineer|paris"},
        {"_id": 3, "entreprise": "Doctolib", "poste": "Data Engineer", "localisation": "Paris",
         "url": "https://linkedin.com/3", "canonical_key": "doctolib|data engineer|paris"},
    ]
    pairs = find_duplicate_pairs(offers)
    assert [(a["_id"], b["_id"]) for a, b in pairs] == [(1, 2)]


@pytest.mark.asyncio
async def test_merge_duplicate_offers_keeps_loser_url_and_city_split():
    wttj = "https://www.welcometothejungle.com/fr/companies/capgemini/jobs/data-scientist_lyon"
    linkedin = "https://www.linkedin.com/jobs/view/4100000001"
    a = {"_id": ObjectId(), "entreprise": "Capgemini", "poste": "Data Scientist", "localisation": "Lyon", "url": wttj}
    b = {"_id": ObjectId(), "entreprise": "Capgemini", "poste": "Data Scientist", "localisation": "Lyon", "url": linkedin}
    c = {"_id": ObjectId(), "entreprise": "Capgemini", "poste": "Data Scientist", "localisation": "Paris",
         "url": "https://fr.indeed.com/viewjob?jk=4100000002"}

    offers = MagicMock()
    offers.find.return_value.to_list = AsyncMock(return_value=[a, b, c])
    offers.delete_one = AsyncMock()
    offers.update_one = AsyncMock()
    applications = MagicMock()
    applications.distinct = AsyncMock(return_value=[str(b["_id"])])
    unreferenced = MagicMock()
    unreferenced.distinct = AsyncMock(return_value=[])
    interactions = MagicMock()
    interactions.find.return_value.to_list = AsyncMock(return_value=[])
    db = {
        "job_offers": offers,
        "applications": applications,
        "offer_evaluations": unreferenced,
        "interview_preps": unreferenced,
        "user_offer_interactions": interactions,
    }

    result = await merge_duplicate_offers(db, apply=True)
    offers.delete_one.assert_awaited_once_with({"_id": a["_id"]})
    survivor_sets = [call.args[1]["$set"] for call in offers.update_one.await_args_list if call.args[0] == {"_id": b["_id"]}]
    assert len(survivor_sets) == 1
    assert {survivor_sets[0]["url"], *survivor_sets[0]["alternative_urls"]} == {wttj, linkedin}
    assert result == {"merged": 1, "skipped_referenced": 0, "stale_keys": 1}
