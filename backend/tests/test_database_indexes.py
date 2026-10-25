import pytest
from unittest.mock import AsyncMock, MagicMock
from app.database import create_company_profiles_indexes, create_job_offers_indexes, create_offer_scoring_indexes


@pytest.mark.asyncio
async def test_create_job_offers_indexes_includes_matched_user_ids():
    mock_collection = MagicMock()
    mock_collection.create_index = AsyncMock()
    mock_db = {"job_offers": mock_collection}

    await create_job_offers_indexes(mock_db)

    called_fields = [call.args[0] for call in mock_collection.create_index.call_args_list]
    assert "matched_user_ids" in called_fields


@pytest.mark.asyncio
async def test_create_company_profiles_indexes_unique_name():
    mock_collection = MagicMock()
    mock_collection.create_index = AsyncMock()
    mock_db = {"company_profiles": mock_collection}

    await create_company_profiles_indexes(mock_db)

    mock_collection.create_index.assert_awaited_once_with("company_name_normalized", unique=True)


@pytest.mark.asyncio
async def test_create_offer_scoring_indexes_unique_offer_id_model():
    mock_embeddings_collection = MagicMock()
    mock_embeddings_collection.create_index = AsyncMock()
    mock_relevance_collection = MagicMock()
    mock_relevance_collection.create_index = AsyncMock()
    mock_db = {"offer_embeddings": mock_embeddings_collection, "offer_relevance": mock_relevance_collection}

    await create_offer_scoring_indexes(mock_db)

    mock_embeddings_collection.create_index.assert_awaited_once_with(
        [("offer_id", 1), ("model", 1)], unique=True
    )


@pytest.mark.asyncio
async def test_create_offer_scoring_indexes_creates_offer_relevance_indexes():
    mock_embeddings_collection = MagicMock()
    mock_embeddings_collection.create_index = AsyncMock()
    mock_relevance_collection = MagicMock()
    mock_relevance_collection.create_index = AsyncMock()
    mock_db = {"offer_embeddings": mock_embeddings_collection, "offer_relevance": mock_relevance_collection}

    await create_offer_scoring_indexes(mock_db)

    calls = mock_relevance_collection.create_index.call_args_list
    unique_call = next(c for c in calls if c.args == ([("user_id", 1), ("offer_id", 1)],))
    assert unique_call.kwargs == {"unique": True}

    sort_call = next(c for c in calls if c.args == ([("user_id", 1), ("score", -1)],))
    assert sort_call.kwargs == {}
