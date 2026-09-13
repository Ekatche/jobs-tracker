import pytest
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId
from fastapi.testclient import TestClient
from main import app
from app.auth import get_current_user
from app.database import get_database
from app.models import UserModel

MOCK_USER_ID = "60c72b2f9b1d8b2bad7f9999"
mock_current_user = UserModel(
    id=MOCK_USER_ID,
    username="testengineer",
    email="test@example.com",
    hashed_password="pw"
)

def test_get_cover_letter_unauthorized(client):
    # Without dependency override, calling endpoint without auth returns 401
    app.dependency_overrides.pop(get_current_user, None)
    res = client.get(f"/applications/{ObjectId()}/cover-letter")
    assert res.status_code == 401

def test_get_candidate_profile_unauthorized(client):
    app.dependency_overrides.pop(get_current_user, None)
    res = client.get("/profile/candidate")
    assert res.status_code == 401

def test_get_cover_letter_not_found(client):
    app_id = ObjectId()
    apps_coll = MagicMock()
    apps_coll.find_one = AsyncMock(return_value={"_id": app_id, "user_id": ObjectId(MOCK_USER_ID)})

    letters_coll = MagicMock()
    letters_coll.find_one = AsyncMock(return_value=None)

    colls = {"applications": apps_coll, "cover_letters": letters_coll}
    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda k: colls[k]

    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_database] = lambda: mock_db

    res = client.get(f"/applications/{app_id}/cover-letter")
    assert res.status_code == 200
    assert res.json() == {"status": "none"}

def test_put_and_get_candidate_profile_mocked(client):
    stored_profile = {}

    async def mock_find_one(query):
        return stored_profile if stored_profile else None

    async def mock_update_one(filter_query, update_data, upsert=False):
        stored_profile.update(update_data["$set"])
        stored_profile["_id"] = ObjectId()
        stored_profile["user_id"] = ObjectId(MOCK_USER_ID)
        return MagicMock()

    mock_db = MagicMock()
    mock_db["candidate_profile"].find_one = AsyncMock(side_effect=mock_find_one)
    mock_db["candidate_profile"].update_one = AsyncMock(side_effect=mock_update_one)

    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_database] = lambda: mock_db

    payload = {
        "headline": "Lead Data Engineer",
        "summary": "Expert Nextflow et Rust",
        "experiences": [
            {
                "company": "Biomérieux",
                "role": "Data Engineer",
                "start": "2022",
                "stack": ["Python", "Nextflow"]
            }
        ]
    }
    put_res = client.put("/profile/candidate", json=payload)
    assert put_res.status_code == 200
    assert put_res.json()["headline"] == "Lead Data Engineer"

    get_res = client.get("/profile/candidate")
    assert get_res.status_code == 200
    assert get_res.json()["headline"] == "Lead Data Engineer"

def test_edit_cover_letter_mocked(client):
    app_id = ObjectId()
    letter_doc = {
        "_id": ObjectId(),
        "user_id": ObjectId(MOCK_USER_ID),
        "application_id": app_id,
        "status": "ready",
        "current_version": 1,
        "versions": [{"n": 1, "body": "Original letter", "origin": "generated"}],
    }

    letters_coll = MagicMock()
    letters_coll.find_one = AsyncMock(return_value=letter_doc)
    letters_coll.update_one = AsyncMock()

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda k: letters_coll

    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_database] = lambda: mock_db

    patch_res = client.patch(f"/applications/{app_id}/cover-letter", json={"body": "Edited version by user"})
    assert patch_res.status_code == 200
    assert letters_coll.update_one.called
