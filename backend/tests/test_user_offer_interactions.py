from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId
import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.database import get_database
from app.models import UserModel
from app.routers.job_offers import apply_user_interaction_filters, restrict_to_profile_offers
from main import app

USER_A_ID = "507f1f77bcf86cd799439011"
USER_B_ID = "507f1f77bcf86cd799439022"
OFFER_1_ID = "507f1f77bcf86cd799439033"
OFFER_2_ID = "507f1f77bcf86cd799439044"


@pytest.fixture
def mock_user_a():
    return UserModel(
        _id=USER_A_ID,
        username="user_a",
        email="usera@example.com",
        hashed_password="fake_hashed_pw",
        disabled=False,
    )


@pytest.fixture
def mock_user_b():
    return UserModel(
        _id=USER_B_ID,
        username="user_b",
        email="userb@example.com",
        hashed_password="fake_hashed_pw",
        disabled=False,
    )


# ==============================================================================
# 1. Unit Tests for apply_user_interaction_filters
# ==============================================================================

@pytest.mark.asyncio
async def test_apply_filters_anonymous_regular():
    match_filter = {"is_deleted": False}
    db = MagicMock()

    filter_res, inter_map, should_empty = await apply_user_interaction_filters(
        match_filter=match_filter,
        db=db,
        current_user=None,
        only_saved=False,
        include_hidden=False,
    )
    assert should_empty is False
    assert inter_map == {}
    assert filter_res == {"is_deleted": False}


@pytest.mark.asyncio
async def test_apply_filters_anonymous_only_saved_returns_empty():
    match_filter = {"is_deleted": False}
    db = MagicMock()

    _, _, should_empty = await apply_user_interaction_filters(
        match_filter=match_filter,
        db=db,
        current_user=None,
        only_saved=True,
    )
    assert should_empty is True


@pytest.mark.asyncio
async def test_apply_filters_user_hidden_offers_excluded(mock_user_a):
    match_filter = {"is_deleted": False}
    db = MagicMock()
    interactions_col = MagicMock()
    interactions_col.find = MagicMock(return_value=MagicMock(
        to_list=AsyncMock(return_value=[
            {"user_id": USER_A_ID, "offer_id": OFFER_1_ID, "status": "hidden"}
        ])
    ))
    db.__getitem__.side_effect = lambda name: interactions_col if name == "user_offer_interactions" else MagicMock()

    filter_res, inter_map, should_empty = await apply_user_interaction_filters(
        match_filter=match_filter,
        db=db,
        current_user=mock_user_a,
        include_hidden=False,
    )
    assert should_empty is False
    assert inter_map[OFFER_1_ID] == "hidden"
    assert filter_res["_id"] == {"$nin": [ObjectId(OFFER_1_ID)]}


@pytest.mark.asyncio
async def test_apply_filters_user_only_saved(mock_user_a):
    match_filter = {"is_deleted": False}
    db = MagicMock()
    interactions_col = MagicMock()
    interactions_col.find = MagicMock(return_value=MagicMock(
        to_list=AsyncMock(return_value=[
            {"user_id": USER_A_ID, "offer_id": OFFER_2_ID, "status": "saved"}
        ])
    ))
    db.__getitem__.side_effect = lambda name: interactions_col if name == "user_offer_interactions" else MagicMock()

    filter_res, _, should_empty = await apply_user_interaction_filters(
        match_filter=match_filter,
        db=db,
        current_user=mock_user_a,
        only_saved=True,
    )
    assert should_empty is False
    assert filter_res["_id"] == {"$in": [ObjectId(OFFER_2_ID)]}


@pytest.mark.asyncio
async def test_apply_filters_user_min_score_matching(mock_user_a):
    match_filter = {"is_deleted": False}
    db = MagicMock()
    interactions_col = MagicMock()
    interactions_col.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
    evals_col = MagicMock()
    evals_col.find = MagicMock(return_value=MagicMock(
        to_list=AsyncMock(return_value=[
            {"user_id": USER_A_ID, "offer_id": OFFER_1_ID, "score": 4.5}
        ])
    ))
    def mock_db_getitem(name):
        if name == "user_offer_interactions":
            return interactions_col
        if name == "offer_evaluations":
            return evals_col
        return MagicMock()
    db.__getitem__.side_effect = mock_db_getitem

    filter_res, _, should_empty = await apply_user_interaction_filters(
        match_filter=match_filter,
        db=db,
        current_user=mock_user_a,
        min_score=4.0,
    )
    assert should_empty is False
    assert filter_res["_id"] == {"$in": [ObjectId(OFFER_1_ID)]}


# ==============================================================================
# 2. Endpoint Tests: Set, Get & Clear Interaction
# ==============================================================================

def test_set_user_offer_interaction_saved(mock_user_a):
    mock_db = MagicMock()
    offers_col = MagicMock()
    offers_col.find_one = AsyncMock(return_value={"_id": ObjectId(OFFER_1_ID), "poste": "Dev"})
    interactions_col = MagicMock()
    interactions_col.update_one = AsyncMock(return_value=MagicMock(upserted_id=None, modified_count=1))
    interactions_col.find_one = AsyncMock(return_value={
        "_id": ObjectId(),
        "user_id": USER_A_ID,
        "offer_id": OFFER_1_ID,
        "status": "saved",
        "notes": "Top job",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })

    def mock_db_getitem(name):
        if name == "job_offers":
            return offers_col
        if name == "user_offer_interactions":
            return interactions_col
        return MagicMock()
    mock_db.__getitem__.side_effect = mock_db_getitem

    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: mock_user_a
    try:
        client = TestClient(app)
        res = client.post(f"/job-offers/{OFFER_1_ID}/interaction", json={"status": "saved", "notes": "Top job"})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "saved"
        assert data["offer_id"] == OFFER_1_ID
        assert data["user_id"] == USER_A_ID
    finally:
        app.dependency_overrides.clear()


def test_clear_user_offer_interaction_none(mock_user_a):
    mock_db = MagicMock()
    offers_col = MagicMock()
    offers_col.find_one = AsyncMock(return_value={"_id": ObjectId(OFFER_1_ID), "poste": "Dev"})
    interactions_col = MagicMock()
    interactions_col.delete_many = AsyncMock(return_value=MagicMock(deleted_count=1))

    def mock_db_getitem(name):
        if name == "job_offers":
            return offers_col
        if name == "user_offer_interactions":
            return interactions_col
        return MagicMock()
    mock_db.__getitem__.side_effect = mock_db_getitem

    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: mock_user_a
    try:
        client = TestClient(app)
        res = client.post(f"/job-offers/{OFFER_1_ID}/interaction", json={"status": "none"})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "none"
        interactions_col.delete_many.assert_called_once()
    finally:
        app.dependency_overrides.clear()


def test_get_user_offer_interaction_default_none(mock_user_a):
    mock_db = MagicMock()
    interactions_col = MagicMock()
    interactions_col.find_one = AsyncMock(return_value=None)
    mock_db.__getitem__.side_effect = lambda name: interactions_col if name == "user_offer_interactions" else MagicMock()

    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: mock_user_a
    try:
        client = TestClient(app)
        res = client.get(f"/job-offers/{OFFER_1_ID}/interaction")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "none"
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# 3. Multi-Tenant Isolation Verification
# ==============================================================================

def test_multi_tenant_isolation_user_a_hiding_offer_does_not_hide_from_user_b(mock_user_a, mock_user_b):
    """
    Vérifie qu'une offre masquée par User A apparaît toujours pour User B et en anonyme.
    """
    mock_db = MagicMock()
    interactions_col = MagicMock()

    # User A has OFFER_1_ID hidden. User B has no interactions.
    def mock_interactions_find(query):
        cursor = MagicMock()
        if query.get("user_id") == USER_A_ID:
            cursor.to_list = AsyncMock(return_value=[
                {"user_id": USER_A_ID, "offer_id": OFFER_1_ID, "status": "hidden"}
            ])
        else:
            cursor.to_list = AsyncMock(return_value=[])
        return cursor

    interactions_col.find.side_effect = mock_interactions_find

    offers_col = MagicMock()
    # Mock aggregate
    offer_doc = {
        "_id": ObjectId(OFFER_1_ID),
        "poste": "Python Backend Engineer",
        "entreprise": "Acme Corp",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    def mock_aggregate(pipeline):
        cursor = MagicMock()
        cursor.to_list = AsyncMock(return_value=[dict(offer_doc)])
        return cursor
    offers_col.aggregate.side_effect = mock_aggregate

    evals_col = MagicMock()
    evals_col.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))

    def mock_db_getitem(name):
        if name == "job_offers":
            return offers_col
        if name == "user_offer_interactions":
            return interactions_col
        if name == "offer_evaluations":
            return evals_col
        return MagicMock()

    mock_db.__getitem__.side_effect = mock_db_getitem
    app.dependency_overrides[get_database] = lambda: mock_db

    try:
        client = TestClient(app)

        # 1. User A request -> OFFER_1_ID is in hidden list, match_filter gets $nin, returns empty
        app.dependency_overrides[get_current_user] = lambda: mock_user_a
        # In this mock, when User A calls, aggregate match_filter has $nin for OFFER_1_ID
        res_a = client.get("/job-offers/")
        assert res_a.status_code == 200
        # Check call args of aggregate:
        call_pipeline_a = offers_col.aggregate.call_args[0][0]
        match_filter_a = call_pipeline_a[0]["$match"]
        assert ObjectId(OFFER_1_ID) in match_filter_a["_id"]["$nin"]

        # 2. User B request -> OFFER_1_ID is NOT hidden, match_filter does NOT exclude it!
        app.dependency_overrides[get_current_user] = lambda: mock_user_b
        res_b = client.get("/job-offers/")
        assert res_b.status_code == 200
        call_pipeline_b = offers_col.aggregate.call_args[0][0]
        match_filter_b = call_pipeline_b[0]["$match"]
        assert "_id" not in match_filter_b

        # 3. Anonymous request -> refused, offers require login
        app.dependency_overrides.pop(get_current_user, None)
        res_anon = client.get("/job-offers/")
        assert res_anon.status_code == 401

    finally:
        app.dependency_overrides.clear()


def test_restrict_to_profile_offers_scopes_logged_user(mock_user_a):
    f = restrict_to_profile_offers({}, mock_user_a)
    assert f["matched_user_ids"] == USER_A_ID


@pytest.mark.parametrize("only_saved,status", [(True, None), (False, "applied")])
def test_restrict_to_profile_offers_keeps_user_lists(mock_user_a, only_saved, status):
    f = restrict_to_profile_offers({}, mock_user_a, only_saved, status)
    assert "matched_user_ids" not in f


def test_restrict_to_profile_offers_anonymous_untouched():
    assert restrict_to_profile_offers({}, None) == {}
