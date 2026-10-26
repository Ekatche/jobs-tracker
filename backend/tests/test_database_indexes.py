from unittest.mock import AsyncMock, MagicMock

import pymongo
import pytest

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
    mock_relevance_collection.drop_index = AsyncMock()
    mock_db = {
        "offer_embeddings": mock_embeddings_collection,
        "offer_relevance": mock_relevance_collection,
    }

    await create_offer_scoring_indexes(mock_db)

    mock_embeddings_collection.create_index.assert_awaited_once_with(
        [("offer_id", 1), ("model", 1)], unique=True
    )


@pytest.mark.asyncio
async def test_create_offer_scoring_indexes_creates_offer_relevance_unique_index():
    mock_embeddings_collection = MagicMock()
    mock_embeddings_collection.create_index = AsyncMock()
    mock_relevance_collection = MagicMock()
    mock_relevance_collection.create_index = AsyncMock()
    mock_relevance_collection.drop_index = AsyncMock()
    mock_db = {
        "offer_embeddings": mock_embeddings_collection,
        "offer_relevance": mock_relevance_collection,
    }

    await create_offer_scoring_indexes(mock_db)

    mock_relevance_collection.create_index.assert_awaited_once_with(
        [("user_id", 1), ("offer_id", 1)], unique=True
    )


@pytest.mark.asyncio
async def test_create_offer_scoring_indexes_drops_legacy_sort_index():
    """M13 : l'ancien index de tri `(user_id, score)` n'est plus créé, et une
    base migrée avant ce correctif doit le voir supprimé de façon idempotente."""
    mock_embeddings_collection = MagicMock()
    mock_embeddings_collection.create_index = AsyncMock()
    mock_relevance_collection = MagicMock()
    mock_relevance_collection.create_index = AsyncMock()
    mock_relevance_collection.drop_index = AsyncMock()
    mock_db = {
        "offer_embeddings": mock_embeddings_collection,
        "offer_relevance": mock_relevance_collection,
    }

    await create_offer_scoring_indexes(mock_db)

    mock_relevance_collection.drop_index.assert_awaited_once_with("user_id_1_score_-1")


@pytest.mark.asyncio
async def test_create_offer_scoring_indexes_idempotent_on_real_db(test_db):
    """Contre la vraie base de test : créer l'ancien index à la main, puis
    appeler `create_offer_scoring_indexes` deux fois — l'ancien index
    disparaît, les deux index attendus restent, et le second appel ne lève
    aucune erreur (drop_index sur un index déjà absent)."""
    collection = test_db["offer_relevance"]
    try:
        await collection.create_index(
            [("user_id", pymongo.ASCENDING), ("score", pymongo.DESCENDING)]
        )

        await create_offer_scoring_indexes(test_db)
        await create_offer_scoring_indexes(
            test_db
        )  # idempotence : pas d'erreur au 2e appel

        index_names = set((await collection.index_information()).keys())
        assert "user_id_1_score_-1" not in index_names
        assert "user_id_1_offer_id_1" in index_names

        embeddings_index_names = set(
            (await test_db["offer_embeddings"].index_information()).keys()
        )
        assert "offer_id_1_model_1" in embeddings_index_names
    finally:
        await collection.drop_index("user_id_1_offer_id_1")
        await test_db["offer_embeddings"].drop_index("offer_id_1_model_1")
