"""Tests unitaires pour l'orchestration du collecteur d'offres et les endpoints associés."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId
import pytest

from tests.pipeline.conftest import mock_collect_pipeline


@pytest.mark.asyncio
async def test_crawl_skips_offers_expired_on_ats(monkeypatch):
    import app.tasks.job_offers_collectors as collectors
    import app.services.ats.router as ats_router

    expired = "https://job-boards.greenhouse.io/acme/jobs/1"
    unknown = "https://example.com/jobs/2"

    async def fake_extract(url, client=None):
        if url == expired:
            raise ats_router.ExpiredOfferError(url)
        return None

    fallback_crawl = AsyncMock(return_value=[{"poste": "Data Engineer", "url": unknown}])
    monkeypatch.setattr(ats_router, "extract_ats_or_jsonld_offer", fake_extract)
    monkeypatch.setattr(collectors, "get_job_offers_from_query", fallback_crawl)

    offers = await collectors.crawl_urls_for_offers([expired, unknown])

    fallback_crawl.assert_awaited_once_with([unknown])
    assert offers == [{"poste": "Data Engineer", "url": unknown}]


@pytest.mark.asyncio
async def test_collect_and_save_offers_tags_new_offers(monkeypatch):
    import app.tasks.job_offers_collectors as collectors

    fake_offer_ids = [ObjectId("650000000000000000000040")]

    monkeypatch.setattr(collectors, "get_urls_for_query", AsyncMock(return_value=["https://example.com/1"]))
    monkeypatch.setattr(collectors, "crawl_urls_for_offers", AsyncMock(return_value=[{"poste": "Data Engineer"}]))
    monkeypatch.setattr(collectors, "enrich_offers", AsyncMock(return_value=[{"poste": "Data Engineer"}]))
    monkeypatch.setattr(collectors, "clean_duplicate_offers", AsyncMock(return_value=[{"poste": "Data Engineer"}]))
    monkeypatch.setattr(
        collectors,
        "save_offers_to_database",
        AsyncMock(return_value={"saved": 1, "updated": 0, "offer_ids": fake_offer_ids}),
    )
    mock_tag_new_offers = AsyncMock()
    monkeypatch.setattr(collectors, "tag_new_offers", mock_tag_new_offers)
    monkeypatch.setattr(collectors, "cleanup_resources", AsyncMock())
    monkeypatch.setattr(collectors, "get_database", AsyncMock(return_value={"job_offers": None}))
    monkeypatch.setattr(collectors, "collect_structured_offers", AsyncMock(return_value=[]))

    result = await collectors.collect_and_save_offers("data engineer lyon")

    assert result == {"saved": 1, "updated": 0, "offer_ids": fake_offer_ids}
    mock_tag_new_offers.assert_awaited_once()
    assert mock_tag_new_offers.call_args.args[0] == fake_offer_ids


@pytest.mark.asyncio
async def test_collect_merges_structured_offers_and_drops_foreign_search_offers(monkeypatch):
    import app.tasks.job_offers_collectors as collectors

    crawled = [
        {"poste": "ML Engineer", "localisation": "Non spécifié",
         "url": "https://workday.wd5.myworkdayjobs.com/fr-CA/Workday/job/ML-Engineer_JR-1"},
        {"poste": "Data Scientist", "localisation": "Lyon", "url": "https://www.hellowork.com/fr-fr/emplois/1.html"},
    ]
    structured = [{"poste": "Data Scientist", "description": "brut", "url": "https://www.indeed.fr/viewjob?jk=1"}]
    enrich = mock_collect_pipeline(monkeypatch, collectors, crawled, structured)

    await collectors.collect_and_save_offers("Je recherche un poste de Data Scientist proche de Lyon (CDI)")

    merged = enrich.call_args.args[0]
    assert [o["url"] for o in merged] == [
        "https://www.hellowork.com/fr-fr/emplois/1.html",
        "https://www.indeed.fr/viewjob?jk=1",
    ]
    assert merged[1]["description"] == "résumé"


@pytest.mark.asyncio
async def test_collect_skips_web_search_when_disabled(monkeypatch):
    import app.tasks.job_offers_collectors as collectors

    structured = [{"poste": "Data Scientist", "description": "brut", "url": "https://www.indeed.fr/viewjob?jk=1"}]
    enrich = mock_collect_pipeline(monkeypatch, collectors, [], structured)

    await collectors.collect_and_save_offers(
        "Je recherche un poste de Data Scientist proche de Lyon (CDI)", use_web_search=False
    )

    collectors.get_urls_for_query.assert_not_awaited()
    collectors.crawl_urls_for_offers.assert_not_awaited()
    assert [o["url"] for o in enrich.call_args.args[0]] == ["https://www.indeed.fr/viewjob?jk=1"]


@pytest.mark.parametrize(
    "dt, expected",
    [
        (datetime(2026, 10, 23, 7, 0, tzinfo=timezone.utc), True),
        (datetime(2026, 10, 23, 16, 0, tzinfo=timezone.utc), False),
        (datetime(2026, 10, 23, 18, 0, tzinfo=timezone(timedelta(hours=2))), False),
    ],
)
def test_is_web_search_run_only_for_morning_run(dt, expected):
    from app.tasks.job_offers_collectors import is_web_search_run

    assert is_web_search_run(dt) is expected


@pytest.mark.asyncio
async def test_collect_keeps_structured_offers_when_search_fails(monkeypatch):
    import app.tasks.job_offers_collectors as collectors

    structured = [{"poste": "Data Scientist", "description": "brut", "url": "https://www.indeed.fr/viewjob?jk=1"}]
    enrich = mock_collect_pipeline(monkeypatch, collectors, RuntimeError("tavily down"), structured)

    await collectors.collect_and_save_offers("Je recherche un poste de Data Scientist proche de Lyon (CDI)")

    assert [o["url"] for o in enrich.call_args.args[0]] == ["https://www.indeed.fr/viewjob?jk=1"]


@pytest.mark.asyncio
async def test_collect_raises_when_search_fails_without_structured_offers(monkeypatch):
    import app.tasks.job_offers_collectors as collectors

    mock_collect_pipeline(monkeypatch, collectors, RuntimeError("tavily down"), [])

    with pytest.raises(RuntimeError, match="tavily down"):
        await collectors.collect_and_save_offers("Je recherche un poste de Data Scientist proche de Lyon (CDI)")


@pytest.mark.asyncio
async def test_collect_drops_known_and_structured_urls_before_crawl(monkeypatch):
    import app.tasks.job_offers_collectors as collectors

    tavily_urls = [
        "https://www.linkedin.com/jobs/view/12345678",
        "https://example.com/already-in-db",
        "https://example.com/brand-new-job",
    ]
    structured = [
        {"poste": "Data Scientist", "description": "brut", "url": "https://fr.linkedin.com/jobs/view/ds-12345678"}
    ]

    class FakeCursor:
        def __init__(self, docs):
            self._it = iter(docs)

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self._it)
            except StopIteration:
                raise StopAsyncIteration

    class FakeColl:
        def find(self, q, proj=None):
            return FakeCursor([{"url": "https://example.com/already-in-db", "alternative_urls": []}])

    crawl_mock = AsyncMock(
        return_value=[{"poste": "Brand New Job", "localisation": "Lyon", "url": "https://example.com/brand-new-job"}]
    )
    mock_collect_pipeline(monkeypatch, collectors, crawl_mock, structured)
    monkeypatch.setattr(collectors, "get_urls_for_query", AsyncMock(return_value=tavily_urls))
    monkeypatch.setattr(collectors, "get_database", AsyncMock(return_value={"job_offers": FakeColl()}))

    await collectors.collect_and_save_offers("Je recherche un poste de Data Scientist proche de Lyon (CDI)")

    crawl_mock.assert_awaited_once_with(["https://example.com/brand-new-job"])


def test_get_job_offers_scoped_to_profile_by_default(client):
    from app.auth import get_current_user
    from app.database import get_database
    from main import app
    from app.models import UserModel

    user = UserModel(
        id="650000000000000000000099",
        username="tester",
        email="profileonly@example.com",
        hashed_password="x",
    )

    captured = {}
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[])

    def aggregate_side_effect(pipeline):
        captured["match"] = pipeline[0]["$match"]
        return mock_cursor

    mock_offers_collection = MagicMock()
    mock_offers_collection.aggregate = MagicMock(side_effect=aggregate_side_effect)

    class FakeDB(dict):
        def __missing__(self, key):
            generic = MagicMock()
            generic_cursor = MagicMock()
            generic_cursor.to_list = AsyncMock(return_value=[])
            generic.find = MagicMock(return_value=generic_cursor)
            self[key] = generic
            return generic

    mock_db = FakeDB()
    mock_db["job_offers"] = mock_offers_collection

    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: user

    try:
        response = client.get("/job-offers/")
        assert response.status_code == 200
        assert captured["match"]["matched_user_ids"] == str(user.id)
    finally:
        app.dependency_overrides.clear()


def test_get_job_offers_requires_login(client):
    from app.auth import get_current_user
    from main import app

    app.dependency_overrides.pop(get_current_user, None)
    assert client.get("/job-offers/").status_code == 401
    assert client.get("/job-offers/count/").status_code == 401

