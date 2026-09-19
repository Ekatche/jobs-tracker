from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import pytest
from bson import ObjectId
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.database import get_database
from app.models import (
    ActionQuotaUsage,
    ApiUsageAction,
    ApiUsageRecord,
    UserModel,
    UserQuotaSummary,
    UserTier,
)
from app.services.usage_tracker import (
    TIER_MONTHLY_LIMITS,
    check_user_quota,
    estimate_llm_cost,
    get_user_monthly_usage,
    record_api_usage,
    require_user_quota,
)
from main import app

TEST_USER_ID = "507f1f77bcf86cd799439011"


# --- Unit Tests: Models & Enums ---

def test_user_tier_enum():
    assert UserTier.FREE == "free"
    assert UserTier.ADVANCED == "advanced"
    assert UserTier.PRO == "pro"


def test_user_model_default_tier():
    user = UserModel(
        username="testuser",
        email="test@example.com",
        hashed_password="secret_hash",
    )
    assert user.tier == UserTier.FREE


def test_api_usage_record_creation():
    record = ApiUsageRecord(
        user_id=TEST_USER_ID,
        action=ApiUsageAction.COVER_LETTER,
        models_used=["openai/gpt-5.6-luna", "gemini/gemini-3.8-flash"],
        input_tokens=1500,
        output_tokens=500,
        total_tokens=2000,
        estimated_cost_usd=0.007,
        latency_ms=1200,
        success=True,
    )
    assert record.user_id == TEST_USER_ID
    assert record.action == ApiUsageAction.COVER_LETTER
    assert record.total_tokens == 2000
    assert record.estimated_cost_usd == 0.007
    assert record.latency_ms == 1200
    assert record.created_at is not None


# --- Unit Tests: Cost Estimation ---

def test_estimate_llm_cost():
    # gpt-5.6-luna: input 0.002 / 1k, output 0.006 / 1k
    # 1000 input ($0.002) + 1000 output ($0.006) = $0.008
    cost = estimate_llm_cost("gpt-5.6-luna", 1000, 1000)
    assert cost == 0.008

    # With provider prefix
    cost_prefixed = estimate_llm_cost("openai/gpt-5.6-luna", 1000, 1000)
    assert cost_prefixed == 0.008

    # gemini-3.8-flash: input 0.00075 / 1k, output 0.00375 / 1k (tarif Standard vérifié
    # sur ai.google.dev/gemini-api/docs/pricing, valable jusqu'au 31/12/2026)
    # 1000 input ($0.00075) + 1000 output ($0.00375) = $0.0045
    cost_gemini = estimate_llm_cost("gemini/gemini-3.8-flash", 1000, 1000)
    assert cost_gemini == 0.0045

    # Unknown model falls back to default
    cost_unknown = estimate_llm_cost("unknown-model", 1000, 1000)
    assert cost_unknown > 0


# --- Unit Tests: Service Logic (Async) ---

@pytest.mark.asyncio
async def test_record_api_usage():
    mock_db = MagicMock()
    inserted_id = ObjectId()
    mock_db["api_usage"].insert_one = AsyncMock(return_value=MagicMock(inserted_id=inserted_id))

    record = await record_api_usage(
        db=mock_db,
        user_id=TEST_USER_ID,
        action=ApiUsageAction.EVALUATION,
        models_used=["gpt-5-nano"],
        input_tokens=1000,
        output_tokens=200,
        latency_ms=450,
    )

    assert record.user_id == TEST_USER_ID
    assert record.action == ApiUsageAction.EVALUATION
    assert record.total_tokens == 1200
    assert record.estimated_cost_usd > 0
    mock_db["api_usage"].insert_one.assert_called_once()


@pytest.mark.asyncio
async def test_get_user_monthly_usage_free_tier():
    mock_db = MagicMock()

    # Mock user document
    mock_db["users"].find_one = AsyncMock(return_value={"_id": ObjectId(TEST_USER_ID), "tier": "free"})

    # Mock aggregate cursor for usage
    async def mock_aggregate_cursor(pipeline):
        yield {"_id": "cover_letter", "count": 3, "total_tokens": 6000, "total_cost": 0.03}
        yield {"_id": "evaluation", "count": 5, "total_tokens": 10000, "total_cost": 0.01}

    mock_db["api_usage"].aggregate = MagicMock(return_value=mock_aggregate_cursor([]))

    summary = await get_user_monthly_usage(mock_db, TEST_USER_ID, year=2026, month=9)

    assert summary.tier == UserTier.FREE
    assert summary.year == 2026
    assert summary.month == 9
    assert summary.total_tokens == 16000
    assert summary.total_cost_usd == 0.04

    # Check cover_letter quota (free tier limit = 5, used = 3, remaining = 2)
    cl_usage = summary.usage["cover_letter"]
    assert cl_usage.used == 3
    assert cl_usage.monthly_limit == 5
    assert cl_usage.remaining == 2

    # Check interview_prep quota (free tier limit = 1, used = 0, remaining = 1)
    ip_usage = summary.usage["interview_prep"]
    assert ip_usage.used == 0
    assert ip_usage.monthly_limit == 1
    assert ip_usage.remaining == 1


@pytest.mark.asyncio
async def test_check_user_quota_limits():
    mock_db = MagicMock()
    mock_db["users"].find_one = AsyncMock(return_value={"_id": ObjectId(TEST_USER_ID), "tier": "free"})

    # When user has used 5/5 cover letters (Free limit is 5)
    async def cursor_limit_reached(pipeline):
        yield {"_id": "cover_letter", "count": 5, "total_tokens": 10000, "total_cost": 0.05}

    def get_cursor(*args, **kwargs):
        return cursor_limit_reached(args)

    mock_db["api_usage"].aggregate = MagicMock(side_effect=get_cursor)

    allowed, used, limit = await check_user_quota(mock_db, TEST_USER_ID, ApiUsageAction.COVER_LETTER)
    assert allowed is False
    assert used == 5
    assert limit == 5

    # Default behavior: blocking is disabled (no HTTPException raised)
    await require_user_quota(mock_db, TEST_USER_ID, ApiUsageAction.COVER_LETTER)

    # When blocking is explicitly enabled, raises 429
    import os
    from unittest.mock import patch
    with patch.dict(os.environ, {"DISABLE_QUOTA_BLOCKING": "false"}):
        with pytest.raises(HTTPException) as exc_info:
            await require_user_quota(mock_db, TEST_USER_ID, ApiUsageAction.COVER_LETTER)
        assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_pro_tier_unlimited_quota():
    mock_db = MagicMock()
    mock_db["users"].find_one = AsyncMock(return_value={"_id": ObjectId(TEST_USER_ID), "tier": "pro"})

    # Even with 1000 letters used
    async def cursor_pro(pipeline):
        yield {"_id": "cover_letter", "count": 1000, "total_tokens": 2000000, "total_cost": 10.0}

    mock_db["api_usage"].aggregate = MagicMock(return_value=cursor_pro([]))

    allowed, used, limit = await check_user_quota(mock_db, TEST_USER_ID, ApiUsageAction.COVER_LETTER)
    assert allowed is True
    assert used == 1000
    assert limit is None


# --- Integration Tests: Router Endpoints ---

@pytest.fixture
def client_with_auth():
    mock_db = MagicMock()
    test_user = UserModel(
        id=TEST_USER_ID,
        username="demouser",
        email="demo@example.com",
        hashed_password="hash",
        tier=UserTier.FREE,
    )

    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: test_user

    client = TestClient(app)
    yield client, mock_db

    app.dependency_overrides.clear()


def test_get_available_tiers(client_with_auth):
    client, _ = client_with_auth
    response = client.get("/usage/tiers")
    assert response.status_code == 200
    data = response.json()
    assert "free" in data
    assert "advanced" in data
    assert "pro" in data
    assert data["free"]["limits"]["cover_letter"] == 5
    assert data["pro"]["limits"]["cover_letter"] is None


def test_get_my_usage_summary(client_with_auth):
    client, mock_db = client_with_auth
    mock_db["users"].find_one = AsyncMock(return_value={"_id": ObjectId(TEST_USER_ID), "tier": "free"})

    async def mock_cursor(pipeline):
        yield {"_id": "cover_letter", "count": 2, "total_tokens": 4000, "total_cost": 0.02}

    mock_db["api_usage"].aggregate = MagicMock(return_value=mock_cursor([]))

    response = client.get("/usage/me/summary?year=2026&month=9")
    assert response.status_code == 200
    data = response.json()
    assert data["tier"] == "free"
    assert data["year"] == 2026
    assert data["month"] == 9
    assert data["usage"]["cover_letter"]["used"] == 2
    assert data["usage"]["cover_letter"]["remaining"] == 3


def test_get_my_usage_records(client_with_auth):
    client, mock_db = client_with_auth

    sample_doc = {
        "_id": ObjectId(),
        "user_id": TEST_USER_ID,
        "action": "cover_letter",
        "models_used": ["gpt-5.6-luna"],
        "input_tokens": 1000,
        "output_tokens": 300,
        "total_tokens": 1300,
        "estimated_cost_usd": 0.005,
        "latency_ms": 800,
        "success": True,
        "error_message": None,
        "metadata": {},
        "created_at": datetime.now(timezone.utc),
    }

    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor

    async def cursor_iter():
        yield sample_doc

    mock_cursor.__aiter__ = lambda self: cursor_iter()
    mock_db["api_usage"].find.return_value = mock_cursor

    response = client.get("/usage/me?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["action"] == "cover_letter"
    assert data[0]["user_id"] == TEST_USER_ID
