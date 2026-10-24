"""Une offre à laquelle on a postulé ne doit pas perdre ses données (offre, évaluation, kit d'entretien)."""
import uuid
from datetime import datetime, timezone

import pymongo
import pytest
from bson import ObjectId

from app.auth import get_current_user
from app.models import ApplicationStatus, UserModel, UserRole
from conftest import DATABASE_NAME, MONGO_URI
from main import app

USER_ID = str(ObjectId())
OTHER_USER_ID = str(ObjectId())


def _override_user(role):
    user = UserModel(id=USER_ID, username="owner", email="owner@test.com", hashed_password="x", role=role)
    app.dependency_overrides[get_current_user] = lambda: user


@pytest.fixture
def db():
    mongo = pymongo.MongoClient(MONGO_URI)
    yield mongo[DATABASE_NAME]
    mongo.close()


@pytest.fixture
def as_user():
    _override_user(UserRole.USER)
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def as_admin():
    _override_user(UserRole.ADMIN)
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _insert_offer(db):
    key = uuid.uuid4().hex
    return db.job_offers.insert_one({
        "poste": "Ingénieur IA",
        "entreprise": "Acme",
        "url": f"https://example.com/offre/{key}",
        "unique_key": key,
    }).inserted_id


def _insert_application(db, user_id, offer_id):
    now = datetime.now(timezone.utc)
    return db.applications.insert_one({
        "user_id": user_id,
        "offer_id": offer_id,
        "company": "Acme",
        "position": "Ingénieur IA",
        "location": "Paris",
        "url": f"https://example.com/postule/{uuid.uuid4().hex}",
        "status": ApplicationStatus.APPLIED.value,
        "application_date": now,
        "created_at": now,
    }).inserted_id


def test_delete_offer_requires_authentication(client, db):
    offer_id = _insert_offer(db)

    res = client.delete(f"/job-offers/{offer_id}")

    assert res.status_code in (401, 403)
    assert db.job_offers.find_one({"_id": offer_id}) is not None


def test_delete_and_soft_delete_forbidden_for_non_admin(client, db, as_user):
    offer_id = _insert_offer(db)

    assert client.delete(f"/job-offers/{offer_id}").status_code == 403
    assert client.patch(f"/job-offers/{offer_id}/soft-delete").status_code == 403
    offer = db.job_offers.find_one({"_id": offer_id})
    assert offer is not None and not offer.get("is_deleted")


def test_admin_delete_keeps_offer_linked_to_application(client, db, as_admin):
    offer_id = _insert_offer(db)
    _insert_application(db, OTHER_USER_ID, str(offer_id))

    res = client.delete(f"/job-offers/{offer_id}")

    assert res.status_code == 200
    offer = db.job_offers.find_one({"_id": offer_id})
    assert offer["is_deleted"] is True
    assert offer["pipeline_stage"] == "expired"


def test_admin_delete_removes_unlinked_offer(client, db, as_admin):
    offer_id = _insert_offer(db)

    res = client.delete(f"/job-offers/{offer_id}")

    assert res.status_code == 200
    assert db.job_offers.find_one({"_id": offer_id}) is None


def test_link_offer_moves_evaluation_and_prep_to_repaired_offer(client, db, as_user):
    """Offre disparue : la réparation par link-offer garde l'évaluation et le kit de l'utilisateur."""
    dead_offer_id = str(ObjectId())
    app_id = _insert_application(db, USER_ID, dead_offer_id)
    db.offer_evaluations.insert_one({"user_id": USER_ID, "offer_id": dead_offer_id, "score": 4.2})
    db.interview_preps.insert_one({"user_id": USER_ID, "offer_id": dead_offer_id, "stories": [{"title": "Pipeline"}]})
    db.offer_evaluations.insert_one({"user_id": OTHER_USER_ID, "offer_id": dead_offer_id, "score": 1.0})

    res = client.post(f"/applications/{app_id}/link-offer")

    assert res.status_code == 200, res.text
    new_offer_id = res.json()["offer_id"]
    assert new_offer_id != dead_offer_id
    assert db.job_offers.find_one({"_id": ObjectId(new_offer_id)}) is not None
    assert db.offer_evaluations.find_one({"user_id": USER_ID, "offer_id": new_offer_id})["score"] == 4.2
    assert db.interview_preps.find_one({"user_id": USER_ID, "offer_id": new_offer_id})["stories"] == [{"title": "Pipeline"}]
    # Les données d'un autre compte ne suivent pas.
    assert db.offer_evaluations.find_one({"user_id": OTHER_USER_ID, "offer_id": dead_offer_id})["score"] == 1.0


def test_link_offer_never_overwrites_existing_data_on_target_offer(client, db, as_user):
    """Si l'utilisateur a déjà une évaluation sur l'offre retrouvée, l'ancienne ne l'écrase pas."""
    target_offer_id = _insert_offer(db)
    target = db.job_offers.find_one({"_id": target_offer_id})
    dead_offer_id = str(ObjectId())
    app_id = _insert_application(db, USER_ID, dead_offer_id)
    db.applications.update_one({"_id": app_id}, {"$set": {"url": target["url"]}})
    db.offer_evaluations.insert_one({"user_id": USER_ID, "offer_id": dead_offer_id, "score": 2.0})
    db.offer_evaluations.insert_one({"user_id": USER_ID, "offer_id": str(target_offer_id), "score": 4.8})

    res = client.post(f"/applications/{app_id}/link-offer")

    assert res.status_code == 200, res.text
    assert res.json()["offer_id"] == str(target_offer_id)
    assert db.offer_evaluations.count_documents({"user_id": USER_ID, "offer_id": str(target_offer_id)}) == 1
    assert db.offer_evaluations.find_one({"user_id": USER_ID, "offer_id": str(target_offer_id)})["score"] == 4.8
