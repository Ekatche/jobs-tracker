import pytest
from app.models import CandidatePreferences, CandidateProfile, RemotePolicy, UserModel
from app.services.profile.merge import build_profile_from_sources


def test_candidate_preferences_defaults():
    pref = CandidatePreferences()
    assert pref.target_roles == []
    assert pref.remote_policy == RemotePolicy.FLEXIBLE
    assert pref.min_salary is None
    assert pref.currency == "EUR"
    assert pref.contract_types == []
    assert pref.excluded_keywords == []


def test_candidate_preferences_custom():
    pref = CandidatePreferences(
        target_roles=["Machine Learning Engineer", "Data Scientist"],
        seniority_level="lead",
        locations=["Lyon", "Remote"],
        remote_policy=RemotePolicy.FULL_REMOTE,
        min_salary=65000,
        target_salary=75000,
        currency="EUR",
        contract_types=["CDI"],
        notice_period="1 mois",
        work_authorization="Citoyen UE",
        excluded_keywords=["PHP", "Stage"],
        preferred_industries=["IA", "Santé"],
    )
    assert len(pref.target_roles) == 2
    assert pref.remote_policy == RemotePolicy.FULL_REMOTE
    assert pref.min_salary == 65000
    assert "PHP" in pref.excluded_keywords


def test_candidate_profile_with_preferences():
    profile = CandidateProfile(
        user_id="507f1f77bcf86cd799439011",
        headline="AI Tech Lead",
        preferences=CandidatePreferences(
            target_roles=["AI Engineer"],
            locations=["Lyon"],
            remote_policy=RemotePolicy.HYBRID,
        ),
    )
    assert profile.preferences.target_roles == ["AI Engineer"]
    assert profile.preferences.remote_policy == RemotePolicy.HYBRID
    assert profile.preferences.locations == ["Lyon"]


def test_merge_profile_preserves_preferences():
    sources = {
        "cv": {
            "headline": "Data Scientist",
            "skills": {"Languages": ["Python", "SQL"]},
        },
        "manual": {
            "preferences": {
                "target_roles": ["Data Engineer"],
                "locations": ["Paris"],
                "remote_policy": "full_remote",
                "min_salary": 60000,
            }
        },
    }
    derived, conflicts = build_profile_from_sources(sources)
    assert "preferences" in derived
    assert derived["preferences"]["target_roles"] == ["Data Engineer"]
    assert derived["preferences"]["min_salary"] == 60000


def test_put_preferences_endpoint(client):
    from unittest.mock import AsyncMock, MagicMock
    from bson import ObjectId
    from app.auth import get_current_user
    from app.database import get_database
    from main import app

    user_id = "60c72b2f9b1d8b2bad7f1234"
    stored = {"user_id": user_id, "headline": "Dev", "experiences": []}

    async def find_one(_query):
        return dict(stored) if stored else None

    async def update_one(_filter, update, upsert=False):
        stored.update(update.get("$set", {}))
        stored.setdefault("_id", ObjectId())
        return MagicMock()

    collection = MagicMock()
    collection.find_one = AsyncMock(side_effect=find_one)
    collection.update_one = AsyncMock(side_effect=update_one)
    db = MagicMock()
    db.__getitem__.return_value = collection

    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: UserModel(
        id=user_id, username="tester", email="t@example.com", hashed_password="x"
    )

    try:
        payload = {
            "target_roles": ["Data Engineer", "MLOps Engineer"],
            "seniority_level": "senior",
            "locations": ["Paris", "Lyon"],
            "remote_policy": "hybrid",
            "min_salary": 65000,
            "target_salary": 75000,
            "currency": "EUR",
            "contract_types": ["CDI"],
            "notice_period": "3 mois",
            "work_authorization": "Citoyen UE",
            "excluded_keywords": ["PHP", "Stage"],
            "preferred_industries": ["Tech", "Finance"],
        }
        response = client.put("/profile/candidate/preferences", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "preferences" in data
        assert data["preferences"]["target_roles"] == ["Data Engineer", "MLOps Engineer"]
        assert data["preferences"]["remote_policy"] == "hybrid"
        assert data["preferences"]["min_salary"] == 65000

        assert data["preferences"]["seniority_level"] == "senior"
        assert data["preferences"]["seniority_levels"] == ["senior"]

        # Verify GET /profile/candidate returns the persisted preferences
        get_res = client.get("/profile/candidate")
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert get_data["preferences"]["target_roles"] == ["Data Engineer", "MLOps Engineer"]
        assert get_data["preferences"]["locations"] == ["Paris", "Lyon"]
        assert get_data["preferences"]["remote_policy"] == "hybrid"
    finally:
        app.dependency_overrides.clear()


def test_candidate_preferences_multi_seniority():
    # Multi-seniority initialization
    pref = CandidatePreferences(
        target_roles=["Data Engineer"],
        seniority_levels=["mid", "senior"],
    )
    assert pref.seniority_levels == ["mid", "senior"]
    assert pref.seniority_level == "mid"  # Backward compatibility primary level

    # Backward compatibility: setting single seniority_level populates seniority_levels
    pref_legacy = CandidatePreferences(seniority_level="lead")
    assert pref_legacy.seniority_levels == ["lead"]
    assert pref_legacy.seniority_level == "lead"


def test_put_preferences_triggers_rematch_on_target_roles_change():
    from unittest.mock import AsyncMock, MagicMock, patch
    from bson import ObjectId
    from app.auth import get_current_user
    from app.database import get_database
    from main import app

    user_id = "60c72b2f9b1d8b2bad7f5678"
    stored = {"user_id": user_id, "headline": "Dev", "experiences": [], "sources": {}}

    async def find_one(_query):
        return dict(stored) if stored else None

    async def update_one(_filter, update, upsert=False):
        stored.update(update.get("$set", {}))
        stored.setdefault("_id", ObjectId())
        return MagicMock()

    collection = MagicMock()
    collection.find_one = AsyncMock(side_effect=find_one)
    collection.update_one = AsyncMock(side_effect=update_one)
    db = MagicMock()
    db.__getitem__.return_value = collection

    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: UserModel(
        id=user_id, username="tester", email="t3@example.com", hashed_password="x"
    )

    try:
        with patch("app.routers.cover_letters.rematch_user", AsyncMock()) as mock_rematch:
            payload = {"target_roles": ["Data Engineer"], "locations": ["Lyon"]}
            from fastapi.testclient import TestClient
            test_client = TestClient(app)
            response = test_client.put("/profile/candidate/preferences", json=payload)
            assert response.status_code == 200
            mock_rematch.assert_called_once()
            assert mock_rematch.call_args.args[0] == user_id
    finally:
        app.dependency_overrides.clear()


def test_put_preferences_no_rematch_when_matching_fields_unchanged():
    from unittest.mock import AsyncMock, MagicMock, patch
    from bson import ObjectId
    from app.auth import get_current_user
    from app.database import get_database
    from main import app
    from fastapi.testclient import TestClient

    user_id = "60c72b2f9b1d8b2bad7f9999"
    initial_payload = {"target_roles": ["Data Engineer"], "locations": ["Lyon"], "notice_period": "1 mois"}
    stored = {
        "user_id": user_id,
        "headline": "Dev",
        "experiences": [],
        "sources": {"manual": {"preferences": dict(initial_payload)}},
    }

    async def find_one(_query):
        return dict(stored) if stored else None

    async def update_one(_filter, update, upsert=False):
        stored.update(update.get("$set", {}))
        stored.setdefault("_id", ObjectId())
        return MagicMock()

    collection = MagicMock()
    collection.find_one = AsyncMock(side_effect=find_one)
    collection.update_one = AsyncMock(side_effect=update_one)
    db = MagicMock()
    db.__getitem__.return_value = collection

    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: UserModel(
        id=user_id, username="tester", email="t4@example.com", hashed_password="x"
    )

    try:
        with patch("app.routers.cover_letters.rematch_user", AsyncMock()) as mock_rematch:
            # Seul notice_period change, pas target_roles/locations/remote_policy
            payload = {"target_roles": ["Data Engineer"], "locations": ["Lyon"], "notice_period": "3 mois"}
            test_client = TestClient(app)
            response = test_client.put("/profile/candidate/preferences", json=payload)
            assert response.status_code == 200
            mock_rematch.assert_not_called()
    finally:
        app.dependency_overrides.clear()

