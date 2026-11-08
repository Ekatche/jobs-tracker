"""Tests de persistance en base, déduplication inter-sources et filtres d'interaction."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId
import pytest

from app.models import UserModel
from app.routers.job_offers import apply_user_interaction_filters
from app.tasks.job_offers_collectors import save_offers_to_database


@pytest.mark.asyncio
async def test_apply_user_interaction_filters_saved_and_status():
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

    # 1. only_saved = True
    match_f, inter_map, _, empty = await apply_user_interaction_filters(
        match_filter={}, db=mock_db, current_user=user, only_saved=True
    )
    assert not empty
    assert inter_map["650000000000000000000010"] == "saved"
    assert ObjectId("650000000000000000000010") in match_f["_id"]["$in"]
    assert ObjectId("650000000000000000000020") not in match_f["_id"]["$in"]

    # 2. interaction_status = "applied"
    match_f_app, _, _, empty_app = await apply_user_interaction_filters(
        match_filter={}, db=mock_db, current_user=user, interaction_status="applied"
    )
    assert not empty_app
    assert ObjectId("650000000000000000000020") in match_f_app["_id"]["$in"]

    # 3. hidden exclusion par défaut
    match_f_all, _, _, _ = await apply_user_interaction_filters(
        match_filter={}, db=mock_db, current_user=user
    )
    assert ObjectId("650000000000000000000030") in match_f_all["_id"]["$nin"]


def test_deterministic_sorting_keys():
    same_dt = datetime(2026, 9, 17, 10, 0, 0, tzinfo=timezone.utc)
    docs = [
        {"_id": "002", "created_at": same_dt, "poste": "B"},
        {"_id": "003", "created_at": same_dt, "poste": "C"},
        {"_id": "001", "created_at": same_dt, "poste": "A"},
    ]
    sorted_docs = sorted(docs, key=lambda d: (d["created_at"], d["_id"]), reverse=True)
    assert [d["_id"] for d in sorted_docs] == ["003", "002", "001"]


@pytest.mark.asyncio
async def test_save_offers_to_database_cross_source_dedup(monkeypatch):
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
    mock_collection.find_one = AsyncMock(return_value=existing_wttj_doc)
    mock_collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_collection.insert_one = AsyncMock()

    monkeypatch.setattr("app.tasks.job_offers_collectors.get_database", AsyncMock(return_value={"job_offers": mock_collection}))

    incoming_linkedin_offer = {
        "poste": "AI Engineer / Scientist confirmé",
        "entreprise": "Deloitte",
        "localisation": "Lyon",
        "url": "https://fr.linkedin.com/jobs/view/ai-engineer-scientist-confirm%C3%A9-f-h-at-deloitte-4463883002",
        "description": "Détails complets de l'offre LinkedIn",
    }

    res = await save_offers_to_database([incoming_linkedin_offer])
    assert res["updated"] == 1
    assert res["saved"] == 0
    assert mock_collection.update_one.called
    assert not mock_collection.insert_one.called

    call_args = mock_collection.update_one.call_args
    assert call_args[0][0] == {"_id": existing_wttj_doc["_id"]}
    assert call_args[0][1]["$set"]["url"] == existing_wttj_doc["url"]
    assert incoming_linkedin_offer["url"] in call_args[0][1]["$set"]["alternative_urls"]


@pytest.mark.asyncio
async def test_save_offers_to_database_returns_offer_ids_on_update_and_insert(monkeypatch):
    mock_collection = MagicMock()
    inserted_id = ObjectId("6aaa8ed40a4a13cc5c4a7b30")
    existing_id = ObjectId("6aaa8ed40a4a13cc5c4a7b1f")

    # Update scenario
    mock_collection.find_one = AsyncMock(return_value={"_id": existing_id, "unique_key": "k"})
    mock_collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    monkeypatch.setattr("app.tasks.job_offers_collectors.get_database", AsyncMock(return_value={"job_offers": mock_collection}))

    res_up = await save_offers_to_database([{"poste": "Dev", "entreprise": "A", "localisation": "Paris", "url": "https://a.fr/1"}])
    assert res_up["offer_ids"] == [existing_id]

    # Insert scenario
    mock_collection.find_one = AsyncMock(return_value=None)
    mock_collection.distinct = AsyncMock(return_value=[])

    async def insert_one(doc):
        doc["_id"] = inserted_id
        return MagicMock()

    mock_collection.insert_one = AsyncMock(side_effect=insert_one)
    res_ins = await save_offers_to_database([{"poste": "Dev", "entreprise": "New", "localisation": "Paris", "url": "https://new.fr/1"}])
    assert res_ins["saved"] == 1
    assert res_ins["offer_ids"] == [inserted_id]


@pytest.mark.asyncio
async def test_save_offers_to_database_company_variant_updates_existing(monkeypatch):
    existing_doc = {
        "_id": ObjectId("6aaa8ed40a4a13cc5c4a7b41"),
        "poste": "Data Engineer",
        "entreprise": "BackMarket",
        "localisation": "Paris",
        "url": "https://www.linkedin.com/jobs/view/4400000001",
        "unique_key": "backmarket|data engineer|paris",
        "created_at": datetime(2026, 10, 20, 9, 0, 0, tzinfo=timezone.utc),
    }

    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(return_value=None)
    mock_collection.distinct = AsyncMock(return_value=["BackMarket", "Doctolib"])
    mock_find_cursor = MagicMock()
    mock_find_cursor.to_list = AsyncMock(return_value=[existing_doc])
    mock_collection.find = MagicMock(return_value=mock_find_cursor)
    mock_collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_collection.insert_one = AsyncMock()

    monkeypatch.setattr("app.tasks.job_offers_collectors.get_database", AsyncMock(return_value={"job_offers": mock_collection}))

    incoming_offer = {
        "poste": "Data Engineer (H/F)",
        "entreprise": "Back Market",
        "localisation": "Paris",
        "url": "https://www.welcometothejungle.com/fr/companies/back-market/jobs/data-engineer_paris",
    }

    res = await save_offers_to_database([incoming_offer])
    assert res["updated"] == 1
    assert not mock_collection.insert_one.called
    assert res["offer_ids"] == [existing_doc["_id"]]


@pytest.mark.asyncio
async def test_save_offers_insert_carries_resolved_sector(monkeypatch):
    class FakeResolver:
        def __init__(self, *args, **kwargs):
            pass

        async def resolve(self, offer):
            offer["sector"] = "finance_insurance"
            offer["company_size"] = "eti"

    mock_col = MagicMock()
    mock_col.find_one = AsyncMock(return_value=None)
    mock_col.distinct = AsyncMock(return_value=[])

    async def insert_one(doc):
        doc["_id"] = ObjectId("6aaa8ed40a4a13cc5c4a7b60")
        return MagicMock()

    mock_col.insert_one = AsyncMock(side_effect=insert_one)

    monkeypatch.setattr("app.tasks.job_offers_collectors.get_database", AsyncMock(return_value={"job_offers": mock_col}))
    monkeypatch.setattr("app.tasks.job_offers_collectors.CompanyResolver", FakeResolver)

    offer = {"poste": "Contrôleur de gestion", "entreprise": "BNP Paribas", "localisation": "Paris", "url": "https://x.fr/1"}
    res = await save_offers_to_database([offer])

    assert res["saved"] == 1
    inserted = mock_col.insert_one.call_args.args[0]
    assert inserted["sector"] == "finance_insurance"
    assert inserted["company_size"] == "eti"


@pytest.mark.asyncio
async def test_save_offers_update_keeps_existing_sector(monkeypatch):
    existing_doc = {
        "_id": ObjectId("6aaa8ed40a4a13cc5c4a7b51"),
        "poste": "Contrôleur de gestion",
        "entreprise": "BNP Paribas",
        "localisation": "Paris",
        "url": "https://www.hellowork.com/fr-fr/emplois/1.html",
        "unique_key": "bnp paribas|controleur de gestion|paris",
        "sector": "finance_insurance",
        "company_size": "eti",
        "raw_data": {"linkedin": {"job_level": "associate"}},
    }

    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(return_value=existing_doc)
    mock_collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_collection.insert_one = AsyncMock()

    lookup = AsyncMock(return_value=(None, None))
    infer = AsyncMock(return_value={"sector": None, "company_size": None})
    monkeypatch.setattr("app.tasks.job_offers_collectors.get_database", AsyncMock(return_value={"job_offers": mock_collection}))
    monkeypatch.setattr("app.services.company_profiles.lookup_company_size", lookup)
    monkeypatch.setattr("app.services.company_profiles.infer_company_attributes", infer)

    incoming_offer = {
        "poste": "Contrôleur de gestion",
        "entreprise": "BNP Paribas",
        "localisation": "Paris",
        "url": "https://www.hellowork.com/fr-fr/emplois/1.html",
        "raw_data": {"hellowork": {"job_url": "https://www.hellowork.com/fr-fr/emplois/1.html"}},
    }

    res = await save_offers_to_database([incoming_offer])
    assert res["updated"] == 1
    update = mock_collection.update_one.call_args.args[1]["$set"]
    assert update["sector"] == "finance_insurance"
    assert update["company_size"] == "eti"
    lookup.assert_not_awaited()
    infer.assert_not_awaited()


@pytest.mark.asyncio
async def test_save_offers_survives_company_resolver_failure(monkeypatch):
    class FailingResolver:
        def __init__(self, *args, **kwargs):
            pass

        async def resolve(self, offer):
            raise RuntimeError("company_profiles indisponible")

    mock_col = MagicMock()
    mock_col.find_one = AsyncMock(return_value=None)
    mock_col.distinct = AsyncMock(return_value=[])

    async def insert_one(doc):
        doc["_id"] = ObjectId("6aaa8ed40a4a13cc5c4a7b60")
        return MagicMock()

    mock_col.insert_one = AsyncMock(side_effect=insert_one)

    monkeypatch.setattr("app.tasks.job_offers_collectors.get_database", AsyncMock(return_value={"job_offers": mock_col}))
    monkeypatch.setattr("app.tasks.job_offers_collectors.CompanyResolver", FailingResolver)

    offer = {"poste": "FP&A Analyst", "entreprise": "Danone", "localisation": "Paris", "url": "https://x.fr/2"}
    res = await save_offers_to_database([offer])
    assert res["saved"] == 1
    assert mock_col.insert_one.called
