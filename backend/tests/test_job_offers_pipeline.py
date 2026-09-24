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


@pytest.mark.asyncio
async def test_apply_user_interaction_filters_saved_and_status():
    from unittest.mock import AsyncMock, MagicMock
    from bson import ObjectId
    from app.routers.job_offers import apply_user_interaction_filters
    from app.models import UserModel

    user = UserModel(
        id="650000000000000000000001",
        username="testuser",
        email="test@example.com",
        hashed_password="fakehashedpassword",
    )

    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[
        {"offer_id": "650000000000000000000010", "status": "saved"},
        {"offer_id": "650000000000000000000020", "status": "applied"},
        {"offer_id": "650000000000000000000030", "status": "hidden"},
    ])
    mock_db.__getitem__.return_value.find.return_value = mock_cursor

    # 1. Test only_saved = True
    match_f, inter_map, empty = await apply_user_interaction_filters(
        match_filter={},
        db=mock_db,
        current_user=user,
        only_saved=True,
    )
    assert not empty
    assert inter_map["650000000000000000000010"] == "saved"
    assert ObjectId("650000000000000000000010") in match_f["_id"]["$in"]
    assert ObjectId("650000000000000000000020") not in match_f["_id"]["$in"]

    # 2. Test interaction_status = "applied"
    match_f_app, _, empty_app = await apply_user_interaction_filters(
        match_filter={},
        db=mock_db,
        current_user=user,
        interaction_status="applied",
    )
    assert not empty_app
    assert ObjectId("650000000000000000000020") in match_f_app["_id"]["$in"]

    # 3. Test hidden exclusion when not requested
    match_f_all, _, _ = await apply_user_interaction_filters(
        match_filter={},
        db=mock_db,
        current_user=user,
    )
    assert ObjectId("650000000000000000000030") in match_f_all["_id"]["$nin"]


def test_deterministic_sorting_keys():
    # Documents with identical created_at must be strictly ordered by _id descending
    same_dt = datetime(2026, 9, 17, 10, 0, 0, tzinfo=timezone.utc)
    docs = [
        {"_id": "002", "created_at": same_dt, "poste": "B"},
        {"_id": "003", "created_at": same_dt, "poste": "C"},
        {"_id": "001", "created_at": same_dt, "poste": "A"},
    ]
    # Emulate MongoDB sort {"created_at": -1, "_id": -1}
    sorted_docs = sorted(docs, key=lambda d: (d["created_at"], d["_id"]), reverse=True)
    ids = [d["_id"] for d in sorted_docs]
    assert ids == ["003", "002", "001"]


@pytest.mark.asyncio
async def test_save_offers_to_database_cross_source_dedup(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock
    from bson import ObjectId
    from app.tasks.job_offers_collectors import save_offers_to_database

    existing_wttj_doc = {
        "_id": ObjectId("6aaa8ed40a4a13cc5c4a7b1f"),
        "poste": "Ai Engineer / Scientist Confirmé F/h",
        "entreprise": "Deloitte",
        "localisation": "Lyon",
        "url": "https://www.welcometothejungle.com/fr/companies/deloitte/jobs/ai-engineer-scientist-confirme-f-h_lyon",
        "unique_key": "deloitte|ai confirmé engineer scientist|lyon",
        "evaluation": {"score": 5.0, "match": "Excellent"},
        "user_interaction": "saved",
        "created_at": datetime(2026, 9, 16, 12, 0, 0, tzinfo=timezone.utc),
    }

    mock_collection = MagicMock()
    # find_one returns the existing document when matching unique_key
    mock_collection.find_one = AsyncMock(return_value=existing_wttj_doc)
    mock_collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_collection.insert_one = AsyncMock()

    mock_db = {"job_offers": mock_collection}

    async def mock_get_database():
        return mock_db

    monkeypatch.setattr("app.tasks.job_offers_collectors.get_database", mock_get_database)

    incoming_linkedin_offer = {
        "poste": "AI Engineer / Scientist confirmé",
        "entreprise": "Deloitte",
        "localisation": "Lyon",
        "url": "https://fr.linkedin.com/jobs/view/ai-engineer-scientist-confirm%C3%A9-f-h-at-deloitte-4463883002",
        "description": "Détails complets de l'offre LinkedIn",
    }

    res = await save_offers_to_database([incoming_linkedin_offer])

    # Should update the existing document, not insert a duplicate
    assert res["updated"] == 1
    assert res["saved"] == 0
    assert mock_collection.update_one.called
    assert not mock_collection.insert_one.called

    # Check updated fields
    call_args = mock_collection.update_one.call_args
    filter_arg = call_args[0][0]
    update_arg = call_args[0][1]["$set"]

    assert filter_arg == {"_id": existing_wttj_doc["_id"]}
    assert update_arg["url"] == existing_wttj_doc["url"]  # WTTJ stays primary
    assert incoming_linkedin_offer["url"] in update_arg["alternative_urls"]
    assert update_arg["evaluation"] == existing_wttj_doc["evaluation"]


@pytest.mark.asyncio
async def test_save_offers_to_database_returns_offer_ids_on_update(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock
    from bson import ObjectId
    from app.tasks.job_offers_collectors import save_offers_to_database

    existing_doc = {
        "_id": ObjectId("6aaa8ed40a4a13cc5c4a7b1f"),
        "poste": "Ai Engineer / Scientist Confirmé F/h",
        "entreprise": "Deloitte",
        "localisation": "Lyon",
        "url": "https://www.welcometothejungle.com/fr/companies/deloitte/jobs/ai-engineer-scientist-confirme-f-h_lyon",
        "unique_key": "deloitte|ai confirmé engineer scientist|lyon",
        "created_at": datetime(2026, 9, 16, 12, 0, 0, tzinfo=timezone.utc),
    }

    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(return_value=existing_doc)
    mock_collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_collection.insert_one = AsyncMock()

    mock_db = {"job_offers": mock_collection}

    async def mock_get_database():
        return mock_db

    monkeypatch.setattr("app.tasks.job_offers_collectors.get_database", mock_get_database)

    incoming_offer = {
        "poste": "AI Engineer / Scientist confirmé",
        "entreprise": "Deloitte",
        "localisation": "Lyon",
        "url": "https://fr.linkedin.com/jobs/view/ai-engineer-scientist-confirm%C3%A9-f-h-at-deloitte-4463883002",
        "description": "Détails complets de l'offre LinkedIn",
    }

    res = await save_offers_to_database([incoming_offer])

    assert res["updated"] == 1
    assert res["offer_ids"] == [existing_doc["_id"]]


@pytest.mark.asyncio
async def test_save_offers_to_database_returns_offer_ids_on_insert(monkeypatch):
    from unittest.mock import AsyncMock, MagicMock
    from bson import ObjectId
    from app.tasks.job_offers_collectors import save_offers_to_database

    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(return_value=None)
    mock_find_cursor = MagicMock()
    mock_find_cursor.to_list = AsyncMock(return_value=[])
    mock_collection.find = MagicMock(return_value=mock_find_cursor)

    inserted_id = ObjectId("6aaa8ed40a4a13cc5c4a7b30")

    async def insert_one(doc):
        doc["_id"] = inserted_id
        return MagicMock()

    mock_collection.insert_one = AsyncMock(side_effect=insert_one)

    mock_db = {"job_offers": mock_collection}

    async def mock_get_database():
        return mock_db

    monkeypatch.setattr("app.tasks.job_offers_collectors.get_database", mock_get_database)

    incoming_offer = {
        "poste": "MLOps Engineer",
        "entreprise": "NewCompany",
        "localisation": "Paris",
        "url": "https://newcompany.com/jobs/99",
        "description": "Nouvelle offre",
    }

    res = await save_offers_to_database([incoming_offer])

    assert res["saved"] == 1
    assert res["offer_ids"] == [inserted_id]


@pytest.mark.asyncio
async def test_collect_and_save_offers_tags_new_offers(monkeypatch):
    from unittest.mock import AsyncMock
    from bson import ObjectId
    import app.tasks.job_offers_collectors as collectors

    fake_offer_ids = [ObjectId("650000000000000000000040")]

    monkeypatch.setattr(collectors, "get_urls_for_query", AsyncMock(return_value=["https://example.com/1"]))
    monkeypatch.setattr(collectors, "crawl_urls_for_offers", AsyncMock(return_value=[{"poste": "Data Engineer"}]))
    monkeypatch.setattr(collectors, "enrich_offers", AsyncMock(return_value=[{"poste": "Data Engineer"}]))
    monkeypatch.setattr(collectors, "clean_duplicate_offers", AsyncMock(return_value=[{"poste": "Data Engineer"}]))
    monkeypatch.setattr(
        collectors,
        "save_offers_to_database",
        AsyncMock(return_value={"saved": 1, "updated": 0, "offer_ids": fake_offer_ids}),
    )
    mock_tag_new_offers = AsyncMock()
    monkeypatch.setattr(collectors, "tag_new_offers", mock_tag_new_offers)
    monkeypatch.setattr(collectors, "cleanup_resources", AsyncMock())
    monkeypatch.setattr(collectors, "get_database", AsyncMock(return_value={"job_offers": None}))

    result = await collectors.collect_and_save_offers("data engineer lyon")

    assert result == {"saved": 1, "updated": 0, "offer_ids": fake_offer_ids}
    mock_tag_new_offers.assert_awaited_once()
    assert mock_tag_new_offers.call_args.args[0] == fake_offer_ids


def test_get_job_offers_scoped_to_profile_by_default(client):
    from unittest.mock import AsyncMock, MagicMock
    from app.auth import get_current_user
    from app.database import get_database
    from main import app
    from app.models import UserModel

    user = UserModel(
        id="650000000000000000000099",
        username="tester",
        email="profileonly@example.com",
        hashed_password="x",
    )

    captured = {}

    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[])

    def aggregate_side_effect(pipeline):
        captured["match"] = pipeline[0]["$match"]
        return mock_cursor

    mock_offers_collection = MagicMock()
    mock_offers_collection.aggregate = MagicMock(side_effect=aggregate_side_effect)

    class FakeDB(dict):
        def __missing__(self, key):
            generic = MagicMock()
            generic_cursor = MagicMock()
            generic_cursor.to_list = AsyncMock(return_value=[])
            generic.find = MagicMock(return_value=generic_cursor)
            self[key] = generic
            return generic

    mock_db = FakeDB()
    mock_db["job_offers"] = mock_offers_collection

    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: user

    try:
        response = client.get("/job-offers/")
        assert response.status_code == 200
        assert captured["match"]["matched_user_ids"] == str(user.id)
    finally:
        app.dependency_overrides.clear()


def test_get_job_offers_requires_login(client):
    from app.auth import get_current_user
    from main import app

    app.dependency_overrides.pop(get_current_user, None)
    assert client.get("/job-offers/").status_code == 401
    assert client.get("/job-offers/count/").status_code == 401

