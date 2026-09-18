import uuid
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.database import get_database
from app.models import UserModel, UserTier
from main import app

client = TestClient(app)

unique_suffix = str(uuid.uuid4())[:8]
mock_user_id = str(ObjectId())
mock_user = UserModel(
    id=mock_user_id,
    username=f"tieruser_{unique_suffix}",
    email=f"tier_{unique_suffix}@test.com",
    hashed_password="fakehashpassword",
)


@pytest.fixture
def override_auth():
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_update_user_tier(override_auth):
    db = await get_database()
    await db.users.update_one(
        {"_id": ObjectId(mock_user_id)},
        {"$set": {"_id": ObjectId(mock_user_id), "username": mock_user.username, "email": mock_user.email, "tier": "free"}},
        upsert=True,
    )

    res = client.put("/usage/me/tier", json={"tier": "advanced"})
    assert res.status_code == 200
    data = res.json()
    assert data["tier"] == "advanced"

    # Verify via summary endpoint
    res_summary = client.get("/usage/me/summary")
    assert res_summary.status_code == 200
    assert res_summary.json()["tier"] == "advanced"
