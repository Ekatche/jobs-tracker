"""Fixtures partagées des tests de l'API offres (pertinence, tri, filtres).

Module au nom unique, importé explicitement : pas de `conftest.py` de sous-dossier
(sans `__init__.py`, il prendrait le nom de module `conftest` et casserait les
`from conftest import ...` du reste de la suite).

Seed direct dans `job_offers` et `offer_relevance` sur la base de test locale
(127.0.0.1:27018, cf. conftest.py). Les tests qui en dépendent portent
`requires_mongo` et sont ignorés si cette base ne répond pas."""
import uuid
from datetime import datetime, timedelta, timezone

import pymongo
import pytest
from bson import ObjectId

from app.auth import get_current_user
from app.models import UserModel, UserRole
from app.services.offer_scoring.score import level_for
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


def _make_user(user_id):
    return UserModel(
        id=user_id,
        username=f"user_{user_id[:6]}",
        email=f"{user_id[:6]}@test.com",
        hashed_password="x",
        role=UserRole.USER,
    )


def _override_user(user_id):
    app.dependency_overrides[get_current_user] = lambda: _make_user(user_id)


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


def _insert_offer(db, *, poste, created_at, sector=None, company_size=None, localisation=None, entreprise="Acme"):
    key = uuid.uuid4().hex
    doc = {
        "poste": poste,
        "entreprise": entreprise,
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
    if localisation is not None:
        doc["localisation"] = localisation
    return db.job_offers.insert_one(doc).inserted_id


def _insert_relevance(db, user_id, offer_id, score, failed_conditions=None, unknown_components=None):
    db.offer_relevance.insert_one(
        {
            "user_id": user_id,
            "offer_id": str(offer_id),
            "score": score,
            "level": level_for(score),
            "failed_conditions": failed_conditions or [],
            "breakdown": {},
            "unknown_components": unknown_components or [],
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
    _insert_relevance(db, USER_A_ID, a3, 30, failed_conditions=["contract"], unknown_components=["sector"])
    # A4 : pas de document offer_relevance (garde d'interaction / avant premier rematch).

    offer_ids = [a1, a2, a3, a4]
    try:
        yield {"a1": a1, "a2": a2, "a3": a3, "a4": a4}
    finally:
        db.job_offers.delete_many({"_id": {"$in": offer_ids}})
        db.offer_relevance.delete_many({"offer_id": {"$in": [str(oid) for oid in offer_ids]}})
