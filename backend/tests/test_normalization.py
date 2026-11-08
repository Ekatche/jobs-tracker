"""Tests unitaires pour les fonctions de normalisation de texte, URLs et métadonnées d'offres."""

from datetime import datetime, timezone
import pytest

from app.models import JobOfferCreate, JobOfferResponse
from app.services.normalization import (
    clean_html_entities_and_tags,
    clean_job_title_syntax,
    detect_contract_type,
    extract_company_from_url,
    extract_seniority,
    normalize_city,
    normalize_company,
    normalize_offer_fields,
    normalize_position,
    optimize_crawl_url,
    restore_canonical_job_url,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("44000 Nantes", "Nantes"),
        ("Lyon - 01", "Lyon"),
        ("Paris (75)", "Paris"),
        ("LYON 03", "Lyon"),
        (None, "Non spécifié"),
        ("", "Non spécifié"),
    ],
)
def test_normalize_city(raw, expected):
    assert normalize_city(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Acme SAS", "ACME"),
        ("Google LLC", "GOOGLE"),
        ("Tech Solutions SARL", "TECH SOLUTIONS"),
        (None, "Non spécifié"),
    ],
)
def test_normalize_company(raw, expected):
    assert normalize_company(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Data Scientist (H/F)", "DATA SCIENTIST"),
        ("Ingénieur Devops / Cloud H/F", "CLOUD DEVOPS INGÉNIEUR"),
        (None, "Non spécifié"),
    ],
)
def test_normalize_position(raw, expected):
    assert normalize_position(raw) == expected


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://galderma.wd3.myworkdayjobs.com/fr-FR/External/job/Alby/Data-Analyst_JR014026-1", "Galderma"),
        ("https://boards.greenhouse.io/stripe/jobs/123", "Stripe"),
        ("https://jobs.lever.co/datadog/456", "Datadog"),
        ("https://jobs.smartrecruiters.com/boschgroup/789", "Boschgroup"),
        ("https://www.welcometothejungle.com/fr/companies/alan/jobs/123", "Alan"),
        ("https://swile.recruitee.com/o/lead-dev", "Swile"),
        ("https://carrieres.totalenergies.com/offres/123", "Totalenergies"),
        ("https://jobs.ashbyhq.com/openai/12345", "Openai"),
        ("https://acme.bamboohr.com/careers/123", "Acme"),
        ("https://apply.workable.com/qonto/j/ABC123/", "Qonto"),
        ("https://qonto.workable.com/j/ABC123", "Qonto"),
        ("https://alan.jobs.personio.de/job/987", "Alan"),
        ("https://jobs.personio.de/alan/job/987", "Alan"),
        ("https://danone.jobs2web.com/job/123", "Danone"),
        ("https://airbus.taleo.net/careersection/jobdetail.ftl?job=123", "Airbus"),
        ("https://careers-totalenergies.icims.com/jobs/123", "Totalenergies"),
        ("https://swile.teamtailor.com/jobs/123", "Swile"),
        # Agrégateurs -> None
        ("https://candidat.francetravail.fr/offres/recherche/detail/184ABCD", None),
        ("https://www.linkedin.com/jobs/view/12345", None),
        ("https://www.apec.fr/candidat/detail-offre/123", None),
        ("https://fr.indeed.com/viewjob?jk=123", None),
        (None, None),
        ("", None),
    ],
)
def test_extract_company_from_url(url, expected):
    assert extract_company_from_url(url) == expected


@pytest.mark.parametrize(
    "raw_url, expected_url",
    [
        ("https://fr.linkedin.com/jobs/view/4463811288", "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/4463811288"),
        ("https://www.linkedin.com/jobs/view/data-scientist-at-klanik-4463811288?position=1", "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/4463811288"),
        ("https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/4463811288", "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/4463811288"),
        ("https://fr.indeed.com/viewjob?jk=40a89e89e93a1394", "https://fr.indeed.com/m/viewjob?jk=40a89e89e93a1394"),
        ("https://www.indeed.com/rc/clk?jk=abc123xyz&from=vjs", "https://www.indeed.com/m/viewjob?jk=abc123xyz"),
        ("https://fr.indeed.com/m/viewjob?jk=40a89e89e93a1394", "https://fr.indeed.com/m/viewjob?jk=40a89e89e93a1394"),
        ("https://www.welcometothejungle.com/fr/companies/alan/jobs/123", "https://www.welcometothejungle.com/fr/companies/alan/jobs/123"),
        (None, ""),
        ("", ""),
    ],
)
def test_optimize_crawl_url(raw_url, expected_url):
    assert optimize_crawl_url(raw_url) == expected_url


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/4463811288", "https://www.linkedin.com/jobs/view/4463811288"),
        ("https://fr.indeed.com/m/viewjob?jk=40a89e89e93a1394", "https://fr.indeed.com/viewjob?jk=40a89e89e93a1394"),
        ("https://www.welcometothejungle.com/fr/companies/alan/jobs/123", "https://www.welcometothejungle.com/fr/companies/alan/jobs/123"),
    ],
)
def test_restore_canonical_job_url(url, expected):
    assert restore_canonical_job_url(url) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Junior Data Scientist / ML Engineer (R&amp;D)", "Junior Data Scientist / ML Engineer (R&D)"),
        ("Ingénieur &lt;Cloud&gt; &amp; DevOps", "Ingénieur <Cloud> & DevOps"),
        ("Lead&#39;s Team &quot;AI&quot;", "Lead's Team \"AI\""),
        ("<strong>Data Analyst</strong>", "Data Analyst"),
        ("Espace\u00a0insécable\u200b", "Espace insécable"),
        (None, ""),
        ("", ""),
    ],
)
def test_clean_html_entities_and_tags(raw, expected):
    assert clean_html_entities_and_tags(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Data Scientist (H/F)", "Data Scientist"),
        ("Data Scientist (F/H)", "Data Scientist"),
        ("Data Scientist H/F", "Data Scientist"),
        ("Data Scientist Homme / Femme", "Data Scientist"),
        ("Ingénieur IA (M/F/D)", "Ingénieur IA"),
        ("Lead Data Engineer - CDI", "Lead Data Engineer"),
        ("Data Analyst CDD", "Data Analyst"),
        ("Stage Data Science", "Data Science"),
        ("Alternance Machine Learning", "Machine Learning"),
        ("🚀 [LYON] Senior ML Engineer (H/F) - CDI [URGENT] 🔥", "Senior ML Engineer"),
        ("Backend Engineer - Paris", "Backend Engineer"),
        ("Fullstack Developer | Remote", "Fullstack Developer"),
        ("Data Engineer (Lyon)", "Data Engineer"),
        ("DevOps Engineer - Télétravail", "DevOps Engineer"),
        ("Junior Data Scientist / ML Engineer (R&amp;D)", "Junior Data Scientist / ML Engineer (R&D)"),
        ("<h3>Data Engineer</h3> (H/F)", "Data Engineer"),
        ("Data Scientist (H/F) ()", "Data Scientist"),
        ("ML Engineer [ ]", "ML Engineer"),
        ("Data Analyst (CDI) (Paris)", "Data Analyst"),
        ("Data Trust & AI Governance Manager (H/F/NB)", "Data Trust & AI Governance Manager"),
        ("Data Scientist – Remote", "Data Scientist"),
        ("Data Scientist - -", "Data Scientist"),
        (None, "Non spécifié"),
        ("", "Non spécifié"),
        ("   ", "Non spécifié"),
    ],
)
def test_clean_job_title_syntax(raw, expected):
    assert clean_job_title_syntax(raw) == expected


@pytest.mark.parametrize(
    "title, description, expected",
    [
        ("Senior Data Scientist", None, "senior"),
        ("Lead DevOps Engineer", None, "lead"),
        ("Junior Python Developer", None, "junior"),
        ("Stage / Intern Data Science", None, "intern"),
        ("VP Engineering", None, "director"),
        ("Data Scientist Confirmé", None, "mid"),
        ("Data Scientist", "Nous recrutons un profil Senior avec plus de 5 ans d'expérience.", "senior"),
        ("Data Scientist", "Poste au sein de notre équipe data.", None),
    ],
)
def test_extract_seniority(title, description, expected):
    assert extract_seniority(title, description) == expected


@pytest.mark.parametrize(
    "source_contract, title, description, expected",
    [
        ("", "Stage Data Science (F/H/X)", None, "Stage"),
        ("Non spécifié", "Alternance - Data scientist H/F", None, "Alternance"),
        (None, "Data Analyst (stage ou alternance)", None, "Stage / Alternance"),
        ("", "Data Science", "Le stagiaire Data Scientist participera au déploiement.", "Stage"),
        ("", "Data Analyst", "Stage de 3 à 4 mois à partir de mars.", "Stage"),
        ("", "Data Engineer", "Poste à pourvoir en contrat d'apprentissage de 24 mois.", "Alternance"),
        ("", "Data Scientist", "Le poste peut éventuellement prendre la forme d'un stage.", "Non spécifié"),
        ("", "Data Engineer - Early-stage startup", None, "Non spécifié"),
        ("", "ML Engineer, Seed stage fintech", None, "Non spécifié"),
        ("", "Lead Data Scientist", "Vous encadrerez le stagiaire de l'équipe.", "Non spécifié"),
        ("", "Ingénieur apprentissage automatique", None, "Non spécifié"),
        ("Permanent contract", "Data Scientist", None, "CDI"),
        ("Contrat à durée indéterminée", "Data Scientist", None, "CDI"),
        ("CDD / Temporaire", "Data Scientist", None, "CDD"),
        ("CDI", "Stage - IA et management opérationnel", None, "Stage"),
        ("CDI", "Data Engineer Freelance", None, "CDI"),
        ("Temps partiel", "Data Analyst", None, "Temps partiel"),
        ("None", "Data Analyst", None, "Non spécifié"),
    ],
)
def test_detect_contract_type(source_contract, title, description, expected):
    assert detect_contract_type(source_contract, title, description) == expected


def test_normalize_offer_fields_and_contract_inference():
    polluted = {
        "poste": "Junior Data Scientist / ML Engineer (R&amp;D) (H/F)",
        "entreprise": "Recupere Metals &amp; Co",
        "localisation": "Paris (75) &amp; Remote",
        "description": "<p>Superbe poste de <strong>Data Scientist</strong> chez Recupere Metals &amp; Co.</p>",
        "type_contrat": "CDI &amp; Plein temps",
        "salaire": "45k&euro; - 55k&euro;",
        "mode_travail": "Hybride &amp; Flexible",
        "url": "https://recuperemetals.com/jobs/1",
    }
    cleaned = normalize_offer_fields(polluted)
    assert cleaned["poste"] == "Junior Data Scientist / ML Engineer (R&D)"
    assert cleaned["entreprise"] == "Recupere Metals & Co"
    assert cleaned["localisation"] == "Paris & Remote"
    assert "<p>" not in cleaned["description"]
    assert cleaned["type_contrat"] == "CDI"
    assert "€" in cleaned["salaire"]
    assert cleaned["unique_key"] is not None

    stage_offer = {"poste": "Stage Développeur Python Fullstack H/F", "entreprise": "TechCorp", "type_contrat": None}
    assert normalize_offer_fields(stage_offer)["type_contrat"] == "Stage"

    alt_offer = {"poste": "Alternance Data Scientist - Paris", "entreprise": "DataCo", "type_contrat": "Non spécifié"}
    assert normalize_offer_fields(alt_offer)["type_contrat"] == "Alternance"

    cdi_offer = {"poste": "Développeur Python Freelance", "entreprise": "DevCo", "type_contrat": "CDI"}
    assert normalize_offer_fields(cdi_offer)["type_contrat"] == "CDI"


def test_job_offer_models_include_new_fields():
    now = datetime.now(timezone.utc)
    create_payload = {
        "poste": "Senior Data Scientist",
        "entreprise": "Acme",
        "canonical_title": "Data Scientist",
        "seniority_level": "senior",
        "alternative_urls": ["https://indeed.com/1", "https://linkedin.com/2"],
    }
    create_model = JobOfferCreate(**create_payload)
    assert create_model.canonical_title == "Data Scientist"
    assert create_model.seniority_level == "senior"
    assert len(create_model.alternative_urls) == 2

    response_payload = {
        "id": "60d5ecb8b5c9c8e1d4e8b9f1",
        "poste": "Senior Data Scientist",
        "entreprise": "Acme",
        "canonical_title": "Data Scientist",
        "seniority_level": "senior",
        "alternative_urls": ["https://indeed.com/1"],
        "created_at": now,
        "updated_at": now,
    }
    response_model = JobOfferResponse(**response_payload)
    assert response_model.canonical_title == "Data Scientist"
    assert response_model.seniority_level == "senior"
    assert response_model.alternative_urls == ["https://indeed.com/1"]
