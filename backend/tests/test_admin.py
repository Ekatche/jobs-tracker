# backend/tests/test_admin.py
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId
import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.database import get_database
from app.models import UserModel, UserRole, UserTier
from main import app

ADMIN_ID = "507f1f77bcf86cd799439011"
USER_ID = "507f1f77bcf86cd799439022"


@pytest.fixture
def mock_admin():
    return UserModel(
        _id=ADMIN_ID,
        username="admin_user",
        email="admin@example.com",
        hashed_password="fake_hashed_pw",
        role=UserRole.ADMIN,
        tier=UserTier.PRO,
        disabled=False,
    )


@pytest.fixture
def mock_normal_user():
    return UserModel(
        _id=USER_ID,
        username="john_doe",
        email="john.doe@example.com",
        full_name="John Doe",
        hashed_password="fake_hashed_pw",
        role=UserRole.USER,
        tier=UserTier.FREE,
        disabled=False,
    )


def test_admin_endpoints_forbidden_for_normal_user(mock_normal_user):
    app.dependency_overrides[get_current_user] = lambda: mock_normal_user
    client = TestClient(app)

    res = client.get("/admin/stats/costs")
    assert res.status_code == 403
    assert "Accès réservé aux administrateurs" in res.json()["detail"]

    res_users = client.get("/admin/users")
    assert res_users.status_code == 403

    app.dependency_overrides.clear()


def test_admin_cost_summary(mock_admin):
    mock_db = MagicMock()
    api_usage_col = MagicMock()

    # Mock aggregate
    def mock_aggregate_to_list(pipeline):
        # Determine which pipeline
        if any("$unwind" in step for step in pipeline):
            # Model pipeline
            return [
                {
                    "_id": "gemini-3.8-flash",
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "total_tokens": 1500,
                    "cost_usd": 0.005,
                    "requests_count": 2,
                }
            ]
        elif any("$group" in step and step["$group"]["_id"] == "$action" for step in pipeline):
            # Action pipeline
            return [
                {
                    "_id": "evaluation",
                    "total_tokens": 1500,
                    "cost_usd": 0.005,
                    "requests_count": 2,
                }
            ]
        else:
            # Global pipeline
            return [
                {
                    "_id": None,
                    "total_cost": 0.005,
                    "total_tokens": 1500,
                    "total_requests": 2,
                    "unique_users": [USER_ID],
                }
            ]

    def mock_aggregate(pipeline):
        cursor = MagicMock()
        cursor.to_list = AsyncMock(side_effect=lambda length: mock_aggregate_to_list(pipeline))
        return cursor

    api_usage_col.aggregate = mock_aggregate
    mock_db.__getitem__.side_effect = lambda name: api_usage_col if name == "api_usage" else MagicMock()

    app.dependency_overrides[get_current_user] = lambda: mock_admin
    app.dependency_overrides[get_database] = lambda: mock_db
    client = TestClient(app)

    res = client.get("/admin/stats/costs?period=7d")
    assert res.status_code == 200
    data = res.json()
    assert data["period"] == "7d"
    assert data["total_cost_usd"] == 0.005
    assert data["total_tokens"] == 1500
    assert data["active_users_count"] == 1
    assert len(data["model_breakdown"]) == 1
    assert data["model_breakdown"][0]["model"] == "gemini-3.8-flash"
    assert len(data["action_breakdown"]) == 1
    assert data["action_breakdown"][0]["action"] == "evaluation"

    app.dependency_overrides.clear()


def test_admin_list_users_pseudonymization(mock_admin):
    mock_db = MagicMock()
    users_col = MagicMock()
    now = datetime.now(timezone.utc)

    user_doc = {
        "_id": ObjectId(USER_ID),
        "username": "john_doe",
        "email": "john.doe@example.com",
        "full_name": "John Doe",
        "tier": "free",
        "role": "user",
        "disabled": False,
        "created_at": now,
    }

    cursor = MagicMock()
    cursor.sort = MagicMock(return_value=cursor)
    cursor.to_list = AsyncMock(return_value=[user_doc])
    users_col.find = MagicMock(return_value=cursor)

    api_usage_col = MagicMock()
    usage_cursor = MagicMock()
    usage_cursor.to_list = AsyncMock(return_value=[
        {
            "_id": USER_ID,
            "total_cost": 0.0123,
            "total_tokens": 3000,
            "total_requests": 5,
            "last_active": now,
        }
    ])
    api_usage_col.aggregate = MagicMock(return_value=usage_cursor)

    def mock_db_getitem(name):
        if name == "users":
            return users_col
        if name == "api_usage":
            return api_usage_col
        return MagicMock()

    mock_db.__getitem__.side_effect = mock_db_getitem

    app.dependency_overrides[get_current_user] = lambda: mock_admin
    app.dependency_overrides[get_database] = lambda: mock_db
    client = TestClient(app)

    res = client.get("/admin/users")
    assert res.status_code == 200
    users_list = res.json()
    assert len(users_list) == 1
    u = users_list[0]
    # Vérification pseudonymisation RGPD
    assert u["pseudonym_email"] == "j***e@example.com"
    assert u["pseudonym_name"] == "J. D."
    assert u["tier"] == "free"
    assert u["total_cost_usd"] == 0.0123
    assert u["total_tokens"] == 3000

    app.dependency_overrides.clear()


def test_admin_update_tier(mock_admin):
    mock_db = MagicMock()
    users_col = MagicMock()
    now = datetime.now(timezone.utc)

    user_doc = {
        "_id": ObjectId(USER_ID),
        "username": "john_doe",
        "email": "john.doe@example.com",
        "tier": "advanced",
        "role": "user",
        "disabled": False,
        "created_at": now,
    }

    users_col.find_one = AsyncMock(return_value=user_doc)
    users_col.update_one = AsyncMock(return_value=MagicMock())

    api_usage_col = MagicMock()
    usage_cursor = MagicMock()
    usage_cursor.to_list = AsyncMock(return_value=[])
    api_usage_col.aggregate = MagicMock(return_value=usage_cursor)

    def mock_db_getitem(name):
        if name == "users":
            return users_col
        if name == "api_usage":
            return api_usage_col
        return MagicMock()

    mock_db.__getitem__.side_effect = mock_db_getitem

    app.dependency_overrides[get_current_user] = lambda: mock_admin
    app.dependency_overrides[get_database] = lambda: mock_db
    client = TestClient(app)

    res = client.put(f"/admin/users/{USER_ID}/tier", json={"tier": "advanced"})
    assert res.status_code == 200
    assert res.json()["tier"] == "advanced"
    users_col.update_one.assert_called_once()

    app.dependency_overrides.clear()


def test_admin_toggle_status_cannot_disable_self(mock_admin):
    app.dependency_overrides[get_current_user] = lambda: mock_admin
    client = TestClient(app)

    res = client.put(f"/admin/users/{ADMIN_ID}/status", json={"disabled": True})
    assert res.status_code == 400
    assert "Impossible de désactiver votre propre compte" in res.json()["detail"]

    app.dependency_overrides.clear()


def test_admin_delete_user_gdpr(mock_admin):
    mock_db = MagicMock()
    users_col = MagicMock()
    users_col.find_one = AsyncMock(return_value={"_id": ObjectId(USER_ID), "email": "john.doe@example.com"})
    users_col.delete_one = AsyncMock(return_value=MagicMock())

    generic_col = MagicMock()
    generic_col.delete_many = AsyncMock()
    generic_col.update_many = AsyncMock()
    generic_col.delete_one = AsyncMock()

    def mock_db_getitem(name):
        if name == "users":
            return users_col
        return generic_col

    mock_db.__getitem__.side_effect = mock_db_getitem

    app.dependency_overrides[get_current_user] = lambda: mock_admin
    app.dependency_overrides[get_database] = lambda: mock_db
    client = TestClient(app)

    # Tentative d'auto-suppression
    res_self = client.delete(f"/admin/users/{ADMIN_ID}/gdpr")
    assert res_self.status_code == 400
    assert "Impossible de supprimer votre propre compte" in res_self.json()["detail"]

    # Suppression RGPD légitime d'un autre utilisateur
    res = client.delete(f"/admin/users/{USER_ID}/gdpr")
    assert res.status_code == 200
    assert "supprimées et anonymisées" in res.json()["message"]
    users_col.delete_one.assert_called_once()
    generic_col.update_many.assert_called_once()

    app.dependency_overrides.clear()
