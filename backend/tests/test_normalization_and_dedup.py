import sys
import os
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.normalization import (
    clean_job_title_syntax,
    extract_seniority,
    jaccard_description_similarity,
    are_offers_duplicates,
    get_source_priority,
    merge_multidiffusion_offers,
    deduplicate_and_merge_offers,
)
from app.models import JobOfferCreate, JobOfferResponse


class TestLayer1SyntaxCleanup:
    def test_clean_legal_mentions(self):
        titles = [
            ("Data Scientist (H/F)", "Data Scientist"),
            ("Data Scientist (F/H)", "Data Scientist"),
            ("Data Scientist H/F", "Data Scientist"),
            ("Data Scientist Homme / Femme", "Data Scientist"),
            ("Ingénieur IA (M/F/D)", "Ingénieur IA"),
        ]
        for raw, expected in titles:
            assert clean_job_title_syntax(raw) == expected

    def test_clean_contract_types(self):
        titles = [
            ("Lead Data Engineer - CDI", "Lead Data Engineer"),
            ("Data Analyst CDD", "Data Analyst"),
            ("Stage Data Science", "Data Science"),
            ("Alternance Machine Learning", "Machine Learning"),
        ]
        for raw, expected in titles:
            assert clean_job_title_syntax(raw) == expected

    def test_clean_bracket_tags_and_emojis(self):
        raw = "🚀 [LYON] Senior ML Engineer (H/F) - CDI [URGENT] 🔥"
        cleaned = clean_job_title_syntax(raw)
        assert cleaned == "Senior ML Engineer"

    def test_clean_location_and_remote_suffixes(self):
        titles = [
            ("Backend Engineer - Paris", "Backend Engineer"),
            ("Fullstack Developer | Remote", "Fullstack Developer"),
            ("Data Engineer (Lyon)", "Data Engineer"),
            ("DevOps Engineer - Télétravail", "DevOps Engineer"),
        ]
        for raw, expected in titles:
            assert clean_job_title_syntax(raw) == expected

    def test_handles_empty_or_none(self):
        assert clean_job_title_syntax(None) == "Non spécifié"
        assert clean_job_title_syntax("") == "Non spécifié"
        assert clean_job_title_syntax("   ") == "Non spécifié"


class TestLayer2SeniorityExtraction:
    def test_seniority_from_title(self):
        assert extract_seniority("Senior Data Scientist") == "senior"
        assert extract_seniority("Lead DevOps Engineer") == "lead"
        assert extract_seniority("Junior Python Developer") == "junior"
        assert extract_seniority("Stage / Intern Data Science") == "intern"
        assert extract_seniority("VP Engineering") == "director"
        assert extract_seniority("Data Scientist Confirmé") == "mid"

    def test_seniority_fallback_to_description(self):
        title = "Data Scientist"
        desc = "Nous recrutons un profil Senior avec plus de 5 ans d'expérience sur Python et GCP."
        assert extract_seniority(title, desc) == "senior"

    def test_seniority_none_when_unspecified(self):
        assert extract_seniority("Data Scientist", "Poste au sein de notre équipe data.") is None


class TestLayer3SimilarityAndJaccard:
    def test_jaccard_description_similarity(self):
        desc1 = (
            "Nous recherchons un Data Scientist passionné pour concevoir des modèles de machine learning "
            "en production sur Google Cloud Platform avec Python, PyTorch, Docker et Kubernetes."
        )
        desc2 = (
            "Nous recherchons un Data Scientist talentueux pour concevoir des modèles de machine learning "
            "en production sur Google Cloud Platform avec Python, PyTorch, Docker et FastAPI."
        )
        score = jaccard_description_similarity(desc1, desc2)
        assert score > 0.60

        diff_desc = (
            "Comptable unique en charge de la gestion des factures fournisseurs, des fiches de paie "
            "et des déclarations fiscales trimestrielles sous Excel et Sage."
        )
        assert jaccard_description_similarity(desc1, diff_desc) == 0.0

    def test_are_offers_duplicates_by_title_and_company(self):
        o1 = {
            "entreprise": "Doctolib SAS",
            "poste": "Data Scientist (H/F) - CDI",
            "localisation": "Paris",
            "url": "https://fr.indeed.com/viewjob?jk=123",
        }
        o2 = {
            "entreprise": "Doctolib",
            "poste": "Data Scientist",
            "localisation": "Paris",
            "url": "https://boards.greenhouse.io/doctolib/jobs/456",
        }
        assert are_offers_duplicates(o1, o2) is True

    def test_are_offers_duplicates_rejects_different_cities(self):
        o1 = {
            "entreprise": "Doctolib",
            "poste": "Data Scientist",
            "localisation": "Lyon",
            "url": "https://site1.com",
        }
        o2 = {
            "entreprise": "Doctolib",
            "poste": "Data Scientist",
            "localisation": "Marseille",
            "url": "https://site2.com",
        }
        assert are_offers_duplicates(o1, o2) is False


class TestLayer4SourceHierarchyAndMerging:
    def test_get_source_priority(self):
        assert get_source_priority("https://boards.greenhouse.io/job/123") == 100
        assert get_source_priority("https://jobs.lever.co/company/456") == 100
        assert get_source_priority("https://welcometothejungle.com/fr/companies/corp/jobs/789") == 80
        assert get_source_priority("https://www.linkedin.com/jobs/view/111") == 50
        assert get_source_priority("https://fr.indeed.com/viewjob?jk=222") == 50

    def test_merge_multidiffusion_promotes_ats_url_and_consolidates_rich_fields(self):
        aggregator_offer = {
            "entreprise": "Alan",
            "poste": "Senior Software Engineer (H/F) - CDI 🚀",
            "localisation": "Paris",
            "type_contrat": "Non spécifié",
            "salaire": "Non spécifié",
            "url": "https://fr.indeed.com/viewjob?jk=999",
            "description": "Courte description scraping Indeed.",
            "competences_cles": ["Python"],
        }
        ats_offer = {
            "entreprise": "Alan",
            "poste": "Senior Software Engineer",
            "localisation": "Paris",
            "type_contrat": "CDI",
            "salaire": "75k€ - 85k€",
            "url": "https://jobs.lever.co/alan/abc-123",
            "description": "Description complète et détaillée avec tous les critères techniques d'Alan.",
            "competences_cles": ["Python", "Kubernetes", "PostgreSQL"],
        }

        merged = merge_multidiffusion_offers(aggregator_offer, ats_offer)

        # ATS URL wins as primary
        assert merged["url"] == "https://jobs.lever.co/alan/abc-123"
        # Indeed URL appended to alternatives
        assert "https://fr.indeed.com/viewjob?jk=999" in merged["alternative_urls"]
        # Salary and contract preserved from ATS
        assert merged["salaire"] == "75k€ - 85k€"
        assert merged["type_contrat"] == "CDI"
        # Richer description kept
        assert "Description complète et détaillée" in merged["description"]
        # Skills merged
        assert "Kubernetes" in merged["competences_cles"]
        assert "Python" in merged["competences_cles"]

    def test_deduplicate_and_merge_offers_trio(self):
        offers = [
            {
                "entreprise": "Qonto",
                "poste": "[PARIS] Lead Data Analyst (H/F) - CDI",
                "localisation": "Paris",
                "url": "https://www.linkedin.com/jobs/view/100",
                "salaire": "Non spécifié",
                "competences_cles": ["SQL"],
            },
            {
                "entreprise": "Qonto SAS",
                "poste": "Lead Data Analyst",
                "localisation": "Paris",
                "url": "https://boards.greenhouse.io/qonto/jobs/200",
                "salaire": "65k€ - 80k€",
                "competences_cles": ["SQL", "dbt", "Snowflake"],
            },
            {
                "entreprise": "Qonto",
                "poste": "Lead Data Analyst - Paris 🚀",
                "localisation": "Paris",
                "url": "https://fr.indeed.com/viewjob?jk=300",
                "salaire": "Non spécifié",
                "competences_cles": ["Tableau"],
            },
        ]

        result = deduplicate_and_merge_offers(offers)
        assert len(result) == 1
        winner = result[0]
        assert winner["url"] == "https://boards.greenhouse.io/qonto/jobs/200"
        assert winner["poste"] == "Lead Data Analyst"
        assert winner["salaire"] == "65k€ - 80k€"
        assert set(winner["alternative_urls"]) == {
            "https://www.linkedin.com/jobs/view/100",
            "https://fr.indeed.com/viewjob?jk=300",
        }
        assert "Snowflake" in winner["competences_cles"]
        assert "Tableau" in winner["competences_cles"]


class TestModelCompatibility:
    def test_job_offer_models_include_new_fields(self):
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
