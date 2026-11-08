import json
import logging
import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.sources import jobboards
from app.tasks.job_offers_collectors import build_search_queries


@pytest.mark.asyncio
async def test_rotation_covers_all_roles_and_contracts_without_growing_daily_budget():
    profiles = [{"preferences": {"target_roles": [f"Role {i}" for i in range(6)], "locations": ["Lyon"], "contract_types": ["CDI", "CDD"]}}]
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=profiles)
    db = MagicMock()
    db["candidate_profile"].find.return_value = cursor
    with patch("app.tasks.job_offers_collectors.get_database", AsyncMock(return_value=db)), patch(
        "app.services.role_normalizer.normalize_role", AsyncMock(side_effect=lambda role, db: role)
    ):
        batches = [await build_search_queries(rotation_day=day) for day in range(4)]
    assert all(len(batch) == 3 for batch in batches)
    assert len({query for batch in batches for query in batch}) == 12


@pytest.mark.asyncio
async def test_rotation_serves_profiles_beyond_global_limit():
    profiles = [{"preferences": {"target_roles": [f"Role {i}"], "locations": ["Lyon"]}} for i in range(10)]
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=profiles)
    db = MagicMock()
    db["candidate_profile"].find.return_value = cursor
    with patch("app.tasks.job_offers_collectors.get_database", AsyncMock(return_value=db)), patch(
        "app.services.role_normalizer.normalize_role", AsyncMock(side_effect=lambda role, db: role)
    ):
        batches = [await build_search_queries(rotation_day=day) for day in range(3)]
    assert all(len(batch) == 8 for batch in batches)
    assert len({query for batch in batches for query in batch}) == 10


@pytest.mark.asyncio
async def test_source_events_distinguish_empty_and_error(caplog):
    def scrape(site, role, city):
        if site == "indeed":
            raise RuntimeError("unavailable")
        return []

    with patch.object(jobboards, "_scrape_site", side_effect=scrape), caplog.at_level(logging.INFO):
        assert await jobboards.fetch_jobboard_offers("Data Engineer", "Lyon", None) == []
    events = [json.loads(record.message.split("collection_source ", 1)[1]) for record in caplog.records if "collection_source " in record.message]
    assert any(event["source"] == "indeed" and event["status"] == "error" for event in events)


@pytest.mark.parametrize("error,rows,status", [(None, [], "empty"), ("blocked", [], "error"), ("blocked", [{"title": "Role", "job_url": "https://example.com/1"}], "partial_failure")])
def test_jobspy_events_report_data_and_errors(monkeypatch, caplog, error, rows, status):
    result = MagicMock()
    result.attrs = {"errors": {"indeed": error}}
    result.to_dict.return_value = rows
    monkeypatch.setitem(sys.modules, "jobspy", types.SimpleNamespace(scrape_jobs=lambda **kwargs: result))
    with caplog.at_level(logging.INFO):
        offers = jobboards._scrape_site("indeed", "Role", "Lyon")
    event = next(json.loads(record.message.split("collection_source ", 1)[1]) for record in caplog.records if "collection_source " in record.message)
    assert event["status"] == status
    assert event["found"] == len(offers) == len(rows)
