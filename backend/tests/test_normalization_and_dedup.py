import sys
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.normalization import (
    clean_job_title_syntax,
    extract_seniority,
    jaccard_description_similarity,
    are_offers_duplicates,
    company_match_strength,
    get_source_priority,
    merge_multidiffusion_offers,
    deduplicate_and_merge_offers,
    normalize_offer_fields,
    detect_contract_type,
)
from app.models import JobOfferCreate, JobOfferResponse
from app.services.offer_dedup import find_duplicate_pairs, merge_duplicate_offers, pick_survivor


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


class TestCrossBoardCompanyAndCityVariants:
    """Même offre publiée sur plusieurs job boards avec un nom d'entreprise ou une ville écrits autrement."""

    def test_company_variant_strong_match_ignores_spacing_and_accents(self):
        assert company_match_strength("BackMarket", "Back Market") == "strong"
        assert company_match_strength("Néosoft", "Neosoft") == "strong"
        assert company_match_strength("Orange", "Orano") is None
        assert company_match_strength("Non spécifié", "Non spécifié") is None

        o1 = {"entreprise": "BackMarket", "poste": "Data Engineer", "localisation": "Paris",
              "url": "https://www.linkedin.com/jobs/view/1"}
        o2 = {"entreprise": "Back Market", "poste": "Data Engineer (H/F)", "localisation": "Paris",
              "url": "https://www.welcometothejungle.com/fr/companies/back-market/jobs/2"}
        assert are_offers_duplicates(o1, o2) is True

    def test_company_variant_weak_match_merges_with_close_descriptions(self):
        assert company_match_strength("JEMS", "Jems Group") == "weak"

        same_title = (
            {"entreprise": "JEMS", "poste": "Data Engineer", "localisation": "Lyon",
             "url": "https://www.linkedin.com/jobs/view/3", "description": CONTROLLING_DESC},
            {"entreprise": "Jems Group", "poste": "Data Engineer", "localisation": "Lyon",
             "url": "https://www.hellowork.com/fr-fr/emplois/4.html", "description": CONTROLLING_DESC},
        )
        assert are_offers_duplicates(*same_title) is True

        gendered_title = (
            {"entreprise": "JEMS", "poste": "Contrôleur de gestion/Contrôleuse de gestion",
             "localisation": "Lyon", "url": "https://www.linkedin.com/jobs/view/5",
             "description": CONTROLLING_DESC},
            {"entreprise": "Jems Group", "poste": "Contrôleur de Gestion", "localisation": "Lyon",
             "url": "https://www.hellowork.com/fr-fr/emplois/6.html",
             "description": CONTROLLING_DESC + " Poste basé à Lyon."},
        )
        assert are_offers_duplicates(*gendered_title) is True

    def test_company_variant_weak_match_rejected_without_close_descriptions(self):
        o1 = {"entreprise": "JEMS", "poste": "Data Engineer", "localisation": "Lyon",
              "url": "https://www.linkedin.com/jobs/view/7", "description": CONTROLLING_DESC}
        o2 = {"entreprise": "Jems Group", "poste": "Data Engineer", "localisation": "Lyon",
              "url": "https://www.hellowork.com/fr-fr/emplois/8.html", "description": ACCOUNTING_DESC}
        assert are_offers_duplicates(o1, o2) is False

        no_description = (
            {"entreprise": "Orange", "poste": "Data Engineer", "localisation": "Paris", "url": "https://a.example/9"},
            {"entreprise": "Orange Business", "poste": "Data Engineer", "localisation": "Paris",
             "url": "https://b.example/10"},
        )
        assert are_offers_duplicates(*no_description) is False

    def test_deduplicate_and_merge_offers_company_variant(self):
        offers = [
            {"entreprise": "BackMarket", "poste": "Data Engineer", "localisation": "Paris",
             "url": "https://www.linkedin.com/jobs/view/11"},
            {"entreprise": "Doctolib", "poste": "Data Engineer", "localisation": "Paris",
             "url": "https://www.linkedin.com/jobs/view/12"},
            {"entreprise": "Back Market", "poste": "Data Engineer", "localisation": "Paris",
             "url": "https://jobs.lever.co/backmarket/13"},
        ]
        result = deduplicate_and_merge_offers(offers)
        assert len(result) == 2
        merged = next(o for o in result if o["url"] == "https://jobs.lever.co/backmarket/13")
        assert merged["alternative_urls"] == ["https://www.linkedin.com/jobs/view/11"]

    def test_are_offers_duplicates_city_apostrophe(self):
        o1 = {"entreprise": "Crédit Agricole", "poste": "Chargé d'affaires", "localisation": "Champagne-Au-Mont-D'Or",
              "url": "https://www.linkedin.com/jobs/view/14"}
        o2 = {"entreprise": "Crédit Agricole", "poste": "Chargé d'affaires", "localisation": "Champagne-Au-Mont-D’Or",
              "url": "https://fr.indeed.com/viewjob?jk=15"}
        assert are_offers_duplicates(o1, o2) is True

    def test_are_offers_duplicates_city_region_suffix(self):
        o1 = {"entreprise": "Devoteam", "poste": "Senior Data Engineer Snowflake",
              "localisation": "Lyon, Auvergne-Rhône-Alpes, France",
              "url": "https://jobs.smartrecruiters.com/Devoteam/16"}
        o2 = {"entreprise": "Devoteam", "poste": "Senior Data Engineer Snowflake", "localisation": "Lyon",
              "url": "https://www.linkedin.com/jobs/view/17"}
        assert are_offers_duplicates(o1, o2) is True

        o3 = dict(o2, localisation="Paris, Île-de-France, France", url="https://www.linkedin.com/jobs/view/18")
        assert are_offers_duplicates(o1, o3) is False


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

    def test_merge_raw_data_keeps_one_record_per_source(self):
        # LinkedIn seul donne job_level, Indeed seul le salaire chiffré : les deux doivent survivre
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

    def test_merge_raw_data_replaces_legacy_flat_copy(self):
        # Ancien format : copie à plat de l'offre normalisée, remplacée par les enregistrements d'origine
        legacy = {"entreprise": "Alan", "poste": "Data Engineer", "url": "https://www.linkedin.com/jobs/view/1",
                  "raw_data": {"poste": "Data Engineer", "ats_platform": "linkedin"}}
        incoming = {"entreprise": "Alan", "poste": "Data Engineer", "url": "https://www.linkedin.com/jobs/view/1",
                    "raw_data": {"linkedin": {"job_level": "mid-senior level"}}}

        assert merge_multidiffusion_offers(legacy, incoming)["raw_data"] == {"linkedin": {"job_level": "mid-senior level"}}
        # Sans enregistrement d'origine des deux côtés, l'ancien raw_data reste en place
        no_record = {key: value for key, value in incoming.items() if key != "raw_data"}
        assert merge_multidiffusion_offers(legacy, no_record)["raw_data"] == legacy["raw_data"]

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


class TestNormalizeOfferFields:
    def test_extract_stage_from_title_when_contract_missing(self):
        offer = {
            "poste": "Stage Développeur Python Fullstack H/F",
            "entreprise": "TechCorp",
            "type_contrat": None,
        }
        normalized = normalize_offer_fields(offer)
        assert normalized["type_contrat"] == "Stage"
        assert normalized["poste"] == "Développeur Python Fullstack"

    def test_extract_alternance_from_title(self):
        offer = {
            "poste": "Alternance Data Scientist - Paris",
            "entreprise": "DataCo",
            "type_contrat": "Non spécifié",
        }
        normalized = normalize_offer_fields(offer)
        assert normalized["type_contrat"] == "Alternance"
        assert normalized["poste"] == "Data Scientist"

    def test_preserve_existing_contract_if_present(self):
        offer = {
            "poste": "Développeur Python Freelance",
            "entreprise": "DevCo",
            "type_contrat": "CDI",
        }
        normalized = normalize_offer_fields(offer)
        assert normalized["type_contrat"] == "CDI"


class TestDetectContractType:
    """Un stage ou une alternance doit être étiqueté pour que « Mes contrats ciblés » l'écarte,
    sans jamais étiqueter à tort un CDI, qui serait alors masqué."""

    def test_contract_from_title_stage_prefix(self):
        # Cas réel LinkedIn : la source dit « fulltime », seul l'intitulé brut dit « Stage »
        assert detect_contract_type("", "Stage Data Science (F/H/X)") == "Stage"

    def test_contract_from_title_alternance(self):
        assert detect_contract_type("Non spécifié", "Alternance - Data scientist H/F") == "Alternance"

    def test_contract_from_title_stage_or_alternance(self):
        assert detect_contract_type(None, "Data Analyst (stage ou alternance)") == "Stage / Alternance"

    def test_contract_from_description_sentence_start_stagiaire(self):
        description = "Rejoignez notre équipe R&D. Le stagiaire Data Scientist participera au déploiement des modèles."
        assert detect_contract_type("", "Data Science", description) == "Stage"

    def test_contract_from_description_stage_duration(self):
        description = "Stage de 3 à 4 mois à partir de mars, gratification selon la grille en vigueur."
        assert detect_contract_type("", "Data Analyst", description) == "Stage"

    def test_contract_from_description_apprentissage(self):
        description = "Poste à pourvoir en contrat d'apprentissage de 24 mois."
        assert detect_contract_type("", "Data Engineer", description) == "Alternance"

    def test_contract_not_inferred_from_optional_mention(self):
        description = "Le poste peut éventuellement prendre la forme d'un stage de fin d'études ou d'une alternance."
        assert detect_contract_type("", "Data Scientist", description) == "Non spécifié"

    def test_contract_not_inferred_from_startup_stage(self):
        assert detect_contract_type("", "Data Engineer - Early-stage startup") == "Non spécifié"
        assert detect_contract_type("", "ML Engineer, Seed stage fintech") == "Non spécifié"

    def test_contract_not_inferred_when_mentoring_interns(self):
        description = "Vous encadrerez le stagiaire de l'équipe ainsi que des alternants."
        assert detect_contract_type("", "Lead Data Scientist", description) == "Non spécifié"

    def test_contract_not_inferred_from_machine_learning(self):
        assert detect_contract_type("", "Ingénieur apprentissage automatique") == "Non spécifié"

    def test_contract_source_permanent_is_cdi(self):
        assert detect_contract_type("Permanent contract", "Data Scientist") == "CDI"
        assert detect_contract_type("Contrat à durée indéterminée", "Data Scientist") == "CDI"
        assert detect_contract_type("CDD / Temporaire", "Data Scientist") == "CDD"

    def test_contract_from_title_stage_overrides_source(self):
        # Cas réel SmartRecruiters : un stage déclaré CDI par l'ATS
        title = "Stage - IA et management opérationnel en ingénierie - Industrie"
        assert detect_contract_type("CDI", title) == "Stage"

    def test_contract_source_wins_over_other_title_keywords(self):
        assert detect_contract_type("CDI", "Data Engineer Freelance") == "CDI"

    def test_contract_source_unknown_value_kept(self):
        assert detect_contract_type("Temps partiel", "Data Analyst") == "Temps partiel"
        assert detect_contract_type("None", "Data Analyst") == "Non spécifié"


class TestRetroactiveDedupSafety:
    """Le script rétroactif ne doit jamais supprimer une offre liée à une candidature, une évaluation ou un kit."""

    def test_pick_survivor_keeps_referenced_offer(self):
        from bson import ObjectId

        doc1 = {"_id": ObjectId("6aaa8ed40a4a13cc5c4a7b51")}
        doc2 = {"_id": ObjectId("6aaa8ed40a4a13cc5c4a7b52")}

        assert pick_survivor(doc1, doc2, {str(doc2["_id"])}) == (doc2, doc1)
        assert pick_survivor(doc1, doc2, {str(doc1["_id"])}) == (doc1, doc2)
        assert pick_survivor(doc1, doc2, set()) == (doc1, doc2)

    def test_pick_survivor_skips_pair_when_both_referenced(self):
        doc1 = {"_id": "a1"}
        doc2 = {"_id": "b2"}
        assert pick_survivor(doc1, doc2, {"a1", "b2"}) is None

    def test_find_duplicate_pairs_across_company_variants(self):
        offers = [
            {"_id": 1, "entreprise": "BackMarket", "poste": "Data Engineer", "localisation": "Paris",
             "url": "https://www.linkedin.com/jobs/view/21", "canonical_key": "backmarket|data engineer|paris"},
            {"_id": 2, "entreprise": "Back Market", "poste": "Data Engineer", "localisation": "Paris",
             "url": "https://jobs.lever.co/backmarket/22", "canonical_key": "back market|data engineer|paris"},
            {"_id": 3, "entreprise": "Doctolib", "poste": "Data Engineer", "localisation": "Paris",
             "url": "https://www.linkedin.com/jobs/view/23", "canonical_key": "doctolib|data engineer|paris"},
        ]
        pairs = find_duplicate_pairs(offers)
        assert [(a["_id"], b["_id"]) for a, b in pairs] == [(1, 2)]

    @pytest.mark.asyncio
    async def test_merge_duplicate_offers_keeps_loser_url_and_city_split(self):
        """Le nettoyage nocturne fusionne comme l'insertion : même ville seulement, URL du doublon conservée."""
        from bson import ObjectId

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

        # B, liée à une candidature, survit ; C (Paris) n'est jamais fusionnée avec les offres de Lyon
        offers.delete_one.assert_awaited_once_with({"_id": a["_id"]})
        survivor_sets = [
            call.args[1]["$set"] for call in offers.update_one.await_args_list if call.args[0] == {"_id": b["_id"]}
        ]
        assert len(survivor_sets) == 1
        assert {survivor_sets[0]["url"], *survivor_sets[0]["alternative_urls"]} == {wttj, linkedin}
        assert result == {"merged": 1, "skipped_referenced": 0, "stale_keys": 1}
