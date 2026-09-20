import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
from fastapi.testclient import TestClient
from main import app
from app.auth import get_current_user
from app.database import get_database
from app.models import UserModel
from app.routers.cover_letters import _suggested_roles_profile_hash


@pytest.fixture(autouse=True)
def _clean_dependency_overrides():
    """Les overrides de ce fichier ne doivent pas fuiter vers les autres modules de test."""
    snapshot = dict(app.dependency_overrides)
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(snapshot)


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


def test_regenerate_endpoint_sets_pending_instead_of_deleting(client):
    app_id = ObjectId()
    apps_coll = MagicMock()
    apps_coll.find_one = AsyncMock(return_value={"_id": app_id, "user_id": ObjectId(MOCK_USER_ID)})

    letters_coll = MagicMock()
    letters_coll.delete_one = AsyncMock()
    letters_coll.update_one = AsyncMock()

    colls = {"applications": apps_coll, "cover_letters": letters_coll}
    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda k: colls[k]

    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_database] = lambda: mock_db

    with patch("app.routers.cover_letters._generate_cover_letter_bg"):
        res = client.post(f"/applications/{app_id}/cover-letter/regenerate")

    assert res.status_code == 200
    letters_coll.delete_one.assert_not_called()
    letters_coll.update_one.assert_called_once()
    args = letters_coll.update_one.call_args[0]
    assert args[1]["$set"]["status"] == "pending"


def test_suggested_roles_full_cache_hit_skips_llm_and_taxonomy_calls(client):
    """Un cache complet (hash + suggestions) doit éviter tout appel LLM/embedding."""
    profile = {
        "_id": ObjectId(),
        "user_id": ObjectId(MOCK_USER_ID),
        "headline": "Data Engineer",
        "experiences": [],
    }
    profile_hash = _suggested_roles_profile_hash(profile)
    profile["suggested_roles_cache"] = {
        "hash": profile_hash,
        "raw_roles": ["Data Engineer"],
        "suggestions": ["Data Engineer", "Ingénieur Data"],
    }

    mock_db = MagicMock()
    mock_db["candidate_profile"].find_one = AsyncMock(return_value=profile)
    mock_db["candidate_profile"].update_one = AsyncMock()

    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_database] = lambda: mock_db

    with patch(
        "app.routers.cover_letters.suggest_role_titles_from_profile", new_callable=AsyncMock
    ) as mock_llm, patch(
        "app.routers.cover_letters.match_taxonomy_role", new_callable=AsyncMock
    ) as mock_taxonomy, patch(
        "app.routers.cover_letters.require_user_quota", new_callable=AsyncMock
    ) as mock_quota:
        res = client.get("/profile/candidate/suggested-roles")

    assert res.status_code == 200
    assert res.json() == {"roles": ["Data Engineer", "Ingénieur Data"]}
    mock_llm.assert_not_called()
    mock_taxonomy.assert_not_called()
    mock_quota.assert_not_called()
    mock_db["candidate_profile"].update_one.assert_not_called()


def test_suggested_roles_cache_miss_persists_suggestions_for_reuse(client):
    """Un miss de cache doit calculer les suggestions ET les persister pour le prochain appel."""
    profile = {
        "_id": ObjectId(),
        "user_id": ObjectId(MOCK_USER_ID),
        "headline": "Data Engineer",
        "experiences": [],
    }

    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[])

    mock_db = MagicMock()
    mock_db["candidate_profile"].find_one = AsyncMock(return_value=profile)
    mock_db["candidate_profile"].update_one = AsyncMock()
    mock_db["role_aliases"].find.return_value = mock_cursor

    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_database] = lambda: mock_db

    with patch(
        "app.routers.cover_letters.suggest_role_titles_from_profile",
        new_callable=AsyncMock,
        return_value={"roles": [], "_usage": None},
    ), patch(
        "app.routers.cover_letters.match_taxonomy_role",
        new_callable=AsyncMock,
        return_value="Data Engineer",
    ), patch(
        "app.routers.cover_letters.require_user_quota", new_callable=AsyncMock
    ):
        res = client.get("/profile/candidate/suggested-roles")

    assert res.status_code == 200
    assert res.json() == {"roles": ["Data Engineer"]}

    mock_db["candidate_profile"].update_one.assert_called_once()
    args = mock_db["candidate_profile"].update_one.call_args[0]
    cached = args[1]["$set"]["suggested_roles_cache"]
    assert cached["suggestions"] == ["Data Engineer"]
    assert cached["hash"] == _suggested_roles_profile_hash(profile)
