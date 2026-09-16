import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.role_normalizer import (
    cosine_similarity,
    ensure_role_aliases_indexes,
    normalize_role,
)


def test_cosine_similarity_edge_cases():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == -1.0
    assert cosine_similarity([], []) == 0.0
    assert cosine_similarity([1.0], [1.0, 2.0]) == 0.0
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


@pytest.mark.asyncio
async def test_normalize_role_empty_input():
    res = await normalize_role("   ")
    assert res == ""
    res_none = await normalize_role(None)
    assert res_none == ""


@pytest.mark.asyncio
async def test_normalize_role_fast_path():
    """Fast path: rôle trouvé directement dans variants, aucun appel embedding."""
    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(
        return_value={"canonical": "Data Engineer", "variants": ["data engineer", "ingénieur data"]}
    )
    mock_db = {"role_aliases": mock_collection}

    with patch("litellm.aembedding") as mock_embed:
        result = await normalize_role("Ingénieur Data", db=mock_db)

    assert result == "Data Engineer"
    mock_collection.find_one.assert_called_once_with({"variants": "ingénieur data"})
    mock_embed.assert_not_called()


@pytest.mark.asyncio
async def test_normalize_role_slow_path_match():
    """Slow path: non trouvé dans variants, embedding calculé et similarité >= 0.85 -> match."""
    mock_collection = MagicMock()
    # Fast path misses
    mock_collection.find_one = AsyncMock(return_value=None)

    # Existing roles in MongoDB
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(
        return_value=[
            {
                "_id": "id_ai",
                "canonical": "AI Engineer",
                "embedding": [1.0, 0.0, 0.0],
                "variants": ["ai engineer"],
            },
            {
                "_id": "id_ds",
                "canonical": "Data Scientist",
                "embedding": [0.0, 1.0, 0.0],
                "variants": ["data scientist"],
            },
        ]
    )
    mock_collection.find.return_value = mock_cursor
    mock_collection.update_one = AsyncMock()

    mock_db = {"role_aliases": mock_collection}

    # Vector closely aligned with [1.0, 0.0, 0.0] -> score ~ 0.95 >= 0.85
    fake_resp = MagicMock()
    fake_resp.data = [{"embedding": [0.95, 0.05, 0.0]}]

    with patch("litellm.aembedding", AsyncMock(return_value=fake_resp)) as mock_embed:
        result = await normalize_role("Ingénieur IA", db=mock_db)

    assert result == "AI Engineer"
    mock_embed.assert_called_once()
    mock_collection.update_one.assert_called_once_with(
        {"_id": "id_ai"},
        {"$addToSet": {"variants": "ingénieur ia"}},
    )


@pytest.mark.asyncio
async def test_normalize_role_slow_path_new_role():
    """Slow path: non trouvé dans variants, similarité max < 0.85 -> nouveau rôle créé."""
    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(return_value=None)

    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(
        return_value=[
            {
                "_id": "id_ds",
                "canonical": "Data Scientist",
                "embedding": [1.0, 0.0, 0.0],
                "variants": ["data scientist"],
            }
        ]
    )
    mock_collection.find.return_value = mock_cursor
    mock_collection.insert_one = AsyncMock()

    mock_db = {"role_aliases": mock_collection}

    # Orthogonal vector -> score 0.0 < 0.85
    fake_resp = MagicMock()
    fake_resp.data = [{"embedding": [0.0, 1.0, 0.0]}]

    with patch("litellm.aembedding", AsyncMock(return_value=fake_resp)):
        result = await normalize_role("DevOps Specialist", db=mock_db)

    assert result == "DevOps Specialist"
    mock_collection.insert_one.assert_called_once()
    inserted_doc = mock_collection.insert_one.call_args[0][0]
    assert inserted_doc["canonical"] == "DevOps Specialist"
    assert inserted_doc["variants"] == ["devops specialist"]


@pytest.mark.asyncio
async def test_normalize_role_exception_fallback():
    """Fallback: si MongoDB ou litellm lève une erreur, renvoie le rôle brut nettoyé."""
    mock_collection = MagicMock()
    mock_collection.find_one = AsyncMock(side_effect=Exception("Database connection timeout"))
    mock_db = {"role_aliases": mock_collection}

    result = await normalize_role("  Cloud Architect  ", db=mock_db)
    assert result == "Cloud Architect"


@pytest.mark.asyncio
async def test_ensure_role_aliases_indexes():
    """Vérifie la création des index idempotents."""
    mock_collection = MagicMock()
    mock_collection.create_index = AsyncMock()
    mock_db = {"role_aliases": mock_collection}

    await ensure_role_aliases_indexes(db=mock_db)
    assert mock_collection.create_index.call_count == 2
    mock_collection.create_index.assert_any_call("variants")
    mock_collection.create_index.assert_any_call("canonical", unique=True)
