"""Offre créée ou retrouvée depuis une candidature : même recherche de doublon que l'insertion."""
import pytest
from bson import ObjectId
from unittest.mock import AsyncMock, MagicMock

from app.routers.applications import _ensure_offer_for_application


def make_db(find_one=None, distinct=None, candidates=None):
    offers = MagicMock()
    offers.find_one = AsyncMock(side_effect=find_one or (lambda query: None))
    offers.distinct = AsyncMock(return_value=distinct or [])
    offers.find.return_value.to_list = AsyncMock(return_value=candidates or [])
    offers.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
    offers.update_one = AsyncMock()
    applications = MagicMock()
    applications.update_one = AsyncMock()
    return {"job_offers": offers, "applications": applications}


def app_doc(**fields):
    doc = {
        "company": "Capgemini",
        "position": "Data Scientist",
        "location": "Lyon",
        "url": "https://www.welcometothejungle.com/fr/companies/capgemini/jobs/data-scientist",
        "description": "Analyse de données et modèles prédictifs.",
    }
    doc.update(fields)
    return doc


@pytest.mark.asyncio
async def test_manual_offer_found_by_alternative_url():
    url = "https://www.linkedin.com/jobs/view/4100000001"
    existing = {"_id": ObjectId(), "url": "https://fr.indeed.com/viewjob?jk=1", "alternative_urls": [url], "description": "Déjà là"}
    db = make_db(find_one=lambda query: existing if {"alternative_urls": url} in query.get("$or", []) else None)

    offer_id = await _ensure_offer_for_application(str(ObjectId()), app_doc(url=url), db)

    assert offer_id == str(existing["_id"])
    db["job_offers"].insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_manual_offer_key_uses_cleaned_title():
    existing = {"_id": ObjectId(), "description": "Déjà là"}
    key = {"unique_key": "capgemini|data scientist|lyon"}
    db = make_db(find_one=lambda query: existing if key in query.get("$or", []) else None)

    offer_id = await _ensure_offer_for_application(str(ObjectId()), app_doc(position="Data Scientist (CDI)"), db)

    assert offer_id == str(existing["_id"])
    db["job_offers"].insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_manual_offer_matches_company_variant():
    candidate = {
        "_id": ObjectId(),
        "entreprise": "Back Market",
        "poste": "Data Scientist",
        "localisation": "Lyon",
        "url": "https://www.backmarket.fr/jobs/data-scientist",
        "description": "Déjà là",
    }
    db = make_db(distinct=["Back Market", "Autre"], candidates=[candidate])

    offer_id = await _ensure_offer_for_application(str(ObjectId()), app_doc(company="BackMarket"), db)

    assert offer_id == str(candidate["_id"])
    db["job_offers"].find.assert_called_once_with({"entreprise": {"$in": ["Back Market"]}})
    db["job_offers"].insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_manual_offer_without_location_is_not_france():
    db = make_db()

    await _ensure_offer_for_application(str(ObjectId()), app_doc(location=None), db)

    inserted = db["job_offers"].insert_one.await_args.args[0]
    assert inserted["localisation"] is None
    assert inserted["unique_key"] == "capgemini|data scientist|non-specifie"


@pytest.mark.asyncio
async def test_manual_offer_without_company_is_never_keyed():
    db = make_db()

    await _ensure_offer_for_application(str(ObjectId()), app_doc(company=""), db)

    inserted = db["job_offers"].insert_one.await_args.args[0]
    assert "unique_key" not in inserted
    assert inserted["entreprise"] == "Non spécifié"
    for call in db["job_offers"].find_one.await_args_list:
        assert all("unique_key" not in condition for condition in call.args[0]["$or"])
    db["job_offers"].distinct.assert_not_awaited()
