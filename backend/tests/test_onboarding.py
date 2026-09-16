from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.database import get_database
from app.models import UserModel, UserResponse, UserTier
from main import app

TEST_USER_ID = "507f1f77bcf86cd799439011"


def test_user_model_onboarding_completed_default():
    user = UserModel(
        username="newuser",
        email="newuser@example.com",
        hashed_password="hash",
    )
    assert user.onboarding_completed is False


def test_user_response_onboarding_completed_field():
    resp = UserResponse(
        id=TEST_USER_ID,
        username="newuser",
        email="newuser@example.com",
        onboarding_completed=True,
        created_at=datetime.now(timezone.utc),
    )
    assert resp.onboarding_completed is True


def test_complete_onboarding_endpoint():
    mock_db = MagicMock()
    user_oid = ObjectId(TEST_USER_ID)

    current_user = UserModel(
        id=TEST_USER_ID,
        username="newuser",
        email="newuser@example.com",
        hashed_password="hash",
        onboarding_completed=False,
    )

    updated_doc = {
        "_id": user_oid,
        "username": "newuser",
        "email": "newuser@example.com",
        "full_name": None,
        "disabled": False,
        "tier": "free",
        "onboarding_completed": True,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    mock_db["users"].update_one = AsyncMock(return_value=MagicMock())
    mock_db["users"].find_one = AsyncMock(return_value=updated_doc)

    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: current_user

    client = TestClient(app)
    response = client.post("/users/complete-onboarding")

    assert response.status_code == 200
    data = response.json()
    assert data["onboarding_completed"] is True
    assert data["username"] == "newuser"
    mock_db["users"].update_one.assert_called_once()

    app.dependency_overrides.clear()
