import pytest
from unittest.mock import AsyncMock, MagicMock
from app.database import create_job_offers_indexes


@pytest.mark.asyncio
async def test_create_job_offers_indexes_includes_matched_user_ids():
    mock_collection = MagicMock()
    mock_collection.create_index = AsyncMock()
    mock_db = {"job_offers": mock_collection}

    await create_job_offers_indexes(mock_db)

    called_fields = [call.args[0] for call in mock_collection.create_index.call_args_list]
    assert "matched_user_ids" in called_fields
