"""Tests de l'API offres : tri optionnel par pertinence, conditions non remplies,
filtres secteur et taille (Task 7).

Seed direct dans `job_offers` et `offer_relevance` sur la base de test locale
(127.0.0.1:27018, cf. conftest.py) — pas de passage par le matcher (Task 6).
Le module est marqué `skipif` si cette base ne répond pas, sauf le premier
test, qui est pur (aucune connexion Mongo)."""
import uuid
from datetime import datetime, timedelta, timezone

import pymongo
import pytest
from bson import ObjectId

from app.auth import get_current_user
from app.models import UserModel, UserRole
from app.routers.job_offers import relevance_lookup_stages
from conftest import DATABASE_NAME, MONGO_URI
from main import app


def _mongo_test_db_available() -> bool:
    try:
        client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        client.close()
        return True
    except Exception:
        return False


requires_mongo = pytest.mark.skipif(
    not _mongo_test_db_available(),
    reason="Base Mongo de test indisponible (127.0.0.1:27018, container job-tracker-mongo_test-1)",
)


USER_A_ID = str(ObjectId())
USER_B_ID = str(ObjectId())


def _override_user(user_id):
    user = UserModel(
        id=user_id,
        username=f"user_{user_id[:6]}",
        email=f"{user_id[:6]}@test.com",
        hashed_password="x",
        role=UserRole.USER,
    )
    app.dependency_overrides[get_current_user] = lambda: user


@pytest.fixture
def db():
    mongo = pymongo.MongoClient(MONGO_URI)
    yield mongo[DATABASE_NAME]
    mongo.close()


@pytest.fixture
def as_user_a():
    _override_user(USER_A_ID)
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def as_user_b():
    _override_user(USER_B_ID)
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _insert_offer(db, *, poste, created_at, sector=None, company_size=None):
    key = uuid.uuid4().hex
    doc = {
        "poste": poste,
        "entreprise": "Acme",
        "url": f"https://example.com/offre/{key}",
        "unique_key": key,
        "created_at": created_at,
        # Les offres A sont aussi rattachées à B : B n'a simplement pas de
        # document offer_relevance (cf. test_relevance_is_per_user).
        "matched_user_ids": [USER_A_ID, USER_B_ID],
    }
    if sector is not None:
        doc["sector"] = sector
    if company_size is not None:
        doc["company_size"] = company_size
    return db.job_offers.insert_one(doc).inserted_id


def _insert_relevance(db, user_id, offer_id, score, failed_conditions=None):
    db.offer_relevance.insert_one(
        {
            "user_id": user_id,
            "offer_id": str(offer_id),
            "score": score,
            "level": "x",
            "failed_conditions": failed_conditions or [],
            "breakdown": {},
            "unknown_components": [],
            "updated_at": datetime.now(timezone.utc),
        }
    )


@pytest.fixture
def seeded_offers(db):
    """A1 (score 82, la plus ancienne) .. A4 (sans offer_relevance, la plus récente).

    Nettoyage en teardown : la base de test est partagée entre tous les tests du
    module (pas de reset par test), et la liste `/job-offers/` ne filtre pas sur
    autre chose que `matched_user_ids` — sans ce nettoyage, les offres d'un test
    polluent le suivant.
    """
    base = datetime.now(timezone.utc) - timedelta(days=10)
    a1 = _insert_offer(db, poste="A1", created_at=base)
    a2 = _insert_offer(db, poste="A2", created_at=base + timedelta(days=1))
    a3 = _insert_offer(
        db, poste="A3", created_at=base + timedelta(days=2), sector="tech_it", company_size="pme"
    )
    a4 = _insert_offer(db, poste="A4", created_at=base + timedelta(days=3))

    _insert_relevance(db, USER_A_ID, a1, 82)
    _insert_relevance(db, USER_A_ID, a2, 65)
    _insert_relevance(db, USER_A_ID, a3, 30, failed_conditions=["geo"])
    # A4 : pas de document offer_relevance (garde d'interaction / avant premier rematch).

    offer_ids = [a1, a2, a3, a4]
    try:
        yield {"a1": a1, "a2": a2, "a3": a3, "a4": a4}
    finally:
        db.job_offers.delete_many({"_id": {"$in": offer_ids}})
        db.offer_relevance.delete_many({"offer_id": {"$in": [str(oid) for oid in offer_ids]}})


def test_relevance_lookup_filters_by_current_user():
    """Pure : le sous-pipeline du $lookup filtre bien sur l'utilisateur courant."""
    stages = relevance_lookup_stages("u1")
    lookup_stage = next(s for s in stages if "$lookup" in s)
    assert lookup_stage["$lookup"]["from"] == "offer_relevance"
    sub_pipeline = lookup_stage["$lookup"]["pipeline"]
    match_stage = next(s for s in sub_pipeline if "$match" in s)
    assert match_stage["$match"] == {"user_id": "u1"}


@requires_mongo
def test_list_defaults_to_recent_order(client, db, as_user_a, seeded_offers):
    res = client.get("/job-offers/")

    assert res.status_code == 200, res.text
    postes = [o["poste"] for o in res.json()]
    assert postes == ["A4", "A3", "A2", "A1"]


@requires_mongo
def test_sort_relevance_orders_by_score_then_recency(client, db, as_user_a, seeded_offers):
    res = client.get("/job-offers/", params={"sort": "relevance"})

    assert res.status_code == 200, res.text
    postes = [o["poste"] for o in res.json()]
    assert postes == ["A1", "A2", "A3", "A4"]


@requires_mongo
def test_failed_conditions_exposed(client, db, as_user_a, seeded_offers):
    res = client.get("/job-offers/")

    assert res.status_code == 200, res.text
    by_poste = {o["poste"]: o for o in res.json()}
    assert by_poste["A3"]["failed_conditions"] == ["geo"]
    assert by_poste["A4"]["failed_conditions"] == []


@requires_mongo
def test_count_returns_total(client, db, as_user_a, seeded_offers):
    assert client.get("/job-offers/count/").json() == {"total": 4}
    assert client.get("/job-offers/count/", params={"sort": "relevance"}).json() == {"total": 4}


@requires_mongo
def test_relevance_is_per_user(client, db, as_user_b, seeded_offers):
    """B est rattaché aux mêmes offres mais n'a aucun document offer_relevance."""
    res = client.get("/job-offers/")
    assert res.status_code == 200, res.text
    assert all(o["failed_conditions"] == [] for o in res.json())

    res_rel = client.get("/job-offers/", params={"sort": "relevance"})
    assert res_rel.status_code == 200, res_rel.text
    postes = [o["poste"] for o in res_rel.json()]
    assert postes == ["A4", "A3", "A2", "A1"]


@requires_mongo
def test_filter_by_sector_and_company_size(client, db, as_user_a, seeded_offers):
    res = client.get("/job-offers/", params={"sector": "tech_it", "company_size": "pme"})
    assert res.status_code == 200, res.text
    assert [o["poste"] for o in res.json()] == ["A3"]

    count_res = client.get(
        "/job-offers/count/", params={"sector": "tech_it", "company_size": "pme"}
    )
    assert count_res.json() == {"total": 1}

    invalid_res = client.get("/job-offers/", params={"sector": "fintech"})
    assert invalid_res.status_code == 422


@requires_mongo
def test_response_has_no_internal_fields(client, db, as_user_a, seeded_offers):
    res = client.get("/job-offers/", params={"sort": "relevance"})

    assert res.status_code == 200, res.text
    for offer in res.json():
        assert not any(key.startswith("_") for key in offer)
