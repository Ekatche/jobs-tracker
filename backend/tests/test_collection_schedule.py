"""Créneaux de collecte (DAG `collect_job_offers_granular`) exposés au front :
prochaine recherche d'offres et profil créé depuis la dernière collecte."""
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pymongo
import pytest
from bson import ObjectId

from app.auth import get_current_user
from app.models import UserModel, UserRole
from app.services.collection_schedule import (
    COLLECTION_CRON,
    next_collection_at,
    previous_collection_at,
)
from conftest import DATABASE_NAME, MONGO_URI
from main import app

UTC = timezone.utc


def _at(day, hour, minute=0):
    # Octobre 2026 : le 26 est un lundi, le 30 un vendredi.
    return datetime(2026, 10, day, hour, minute, tzinfo=UTC)


@pytest.mark.parametrize(
    "now,expected",
    [
        (_at(26, 6, 59), _at(26, 7)),
        (_at(26, 7), _at(26, 16)),
        (_at(26, 12), _at(26, 16)),
        (_at(26, 16, 30), _at(27, 7)),
        (_at(30, 16, 1), datetime(2026, 11, 2, 7, tzinfo=UTC)),
        (datetime(2026, 10, 31, 10, tzinfo=UTC), datetime(2026, 11, 2, 7, tzinfo=UTC)),
    ],
)
def test_next_collection_is_strictly_after_now(now, expected):
    assert next_collection_at(now) == expected


@pytest.mark.parametrize(
    "now,expected",
    [
        (_at(26, 7), _at(26, 7)),
        (_at(26, 15, 59), _at(26, 7)),
        (_at(27, 6), _at(26, 16)),
        (datetime(2026, 11, 2, 6, tzinfo=UTC), _at(30, 16)),
    ],
)
def test_previous_collection_is_at_or_before_now(now, expected):
    assert previous_collection_at(now) == expected


def test_naive_datetime_is_read_as_utc():
    assert next_collection_at(datetime(2026, 10, 26, 8)) == _at(26, 16)


def test_cron_matches_collection_dag():
    """Les heures annoncées au candidat doivent suivre le cron réel du DAG."""
    dag_file = Path(__file__).resolve().parents[2] / "airflow" / "dags" / "collect_job_offers.py"
    if not dag_file.exists():
        pytest.skip("DAG Airflow absent de cet environnement")
    match = re.search(r'schedule="([^"]+)"', dag_file.read_text())
    assert match and match.group(1) == COLLECTION_CRON


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


@pytest.fixture
def user_id():
    uid = str(ObjectId())
    app.dependency_overrides[get_current_user] = lambda: UserModel(
        id=uid, username=f"user_{uid[:6]}", email=f"{uid[:6]}@test.com", hashed_password="x", role=UserRole.USER
    )
    yield uid
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def db():
    mongo = pymongo.MongoClient(MONGO_URI)
    yield mongo[DATABASE_NAME]
    mongo.close()


def _insert_profile(db, user_id, created_at):
    profile_id = ObjectId.from_datetime(created_at)
    db["candidate_profile"].insert_one({"_id": profile_id, "user_id": ObjectId(user_id)})
    return profile_id


@requires_mongo
def test_schedule_flags_profile_created_after_last_collection(client, db, user_id):
    before = datetime.now(UTC)
    profile_id = _insert_profile(db, user_id, before)
    try:
        body = client.get("/job-offers/collection/schedule").json()
    finally:
        db["candidate_profile"].delete_one({"_id": profile_id})
    after = datetime.now(UTC)
    assert body["awaiting_first_collection"] is True
    next_at = datetime.fromisoformat(body["next_collection_at"].replace("Z", "+00:00"))
    # Un créneau peut tomber entre les deux lectures de l'horloge.
    assert next_at in {next_collection_at(before), next_collection_at(after)}


@requires_mongo
def test_schedule_does_not_flag_profile_older_than_last_collection(client, db, user_id):
    profile_id = _insert_profile(db, user_id, datetime.now(UTC) - timedelta(days=7))
    try:
        body = client.get("/job-offers/collection/schedule").json()
    finally:
        db["candidate_profile"].delete_one({"_id": profile_id})
    assert body["awaiting_first_collection"] is False


@requires_mongo
def test_schedule_without_profile_is_not_awaiting(client, user_id):
    res = client.get("/job-offers/collection/schedule")
    assert res.status_code == 200
    assert res.json()["awaiting_first_collection"] is False
