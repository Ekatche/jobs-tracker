"""Les erreurs de quota/crédits des fournisseurs LLM arrivent dans l'app avec
le fournisseur nommé, au lieu d'un 500 générique."""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import litellm
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.database import get_database
from app.models import UserModel
from app.routers.applications import _generate_cover_letter_bg
from main import app

job_trackers_path = Path(__file__).parent.parent / "job_trackers" / "src" / "job_trackers"
if str(job_trackers_path) not in sys.path:
    sys.path.insert(0, str(job_trackers_path))

USER_ID = "60c72b2f9b1d8b2bad7f8888"
USER = UserModel(id=USER_ID, username="quota", email="quota@example.com", hashed_password="pw")


def _openai_credits_error():
    return litellm.RateLimitError(
        message="You exceeded your current quota. {'code': 'insufficient_quota'}",
        llm_provider="openai", model="gpt-5.6-terra",
    )


def _db(colls):
    db = MagicMock()
    db.__getitem__.side_effect = lambda k: colls[k]
    return db


@pytest.fixture
def api():
    snapshot = dict(app.dependency_overrides)
    app.dependency_overrides[get_current_user] = lambda: USER
    yield TestClient(app)
    app.dependency_overrides.clear()
    app.dependency_overrides.update(snapshot)


def _assert_openai_credits(res):
    assert res.status_code == 402, res.text
    detail = res.json()["detail"]
    assert "OpenAI" in detail
    assert "gpt-5.6-terra" in detail


def test_tailored_cv_reports_provider_credits(api):
    colls = {
        "candidate_profile": MagicMock(find_one=AsyncMock(return_value={"_id": ObjectId(), "skills": []})),
        "job_offers": MagicMock(find_one=AsyncMock(return_value={"_id": ObjectId(), "title": "Dev"})),
        "offer_evaluations": MagicMock(find_one=AsyncMock(return_value=None)),
    }
    app.dependency_overrides[get_database] = lambda: _db(colls)
    with patch("app.routers.resumes.require_user_quota", new_callable=AsyncMock), \
         patch("app.routers.resumes.generate_tailored_cv_content",
               new=AsyncMock(side_effect=_openai_credits_error())):
        res = api.post("/resumes/generate", json={"offer_id": str(ObjectId())})
    _assert_openai_credits(res)


def test_interview_prep_reports_provider_credits(api):
    app.dependency_overrides[get_database] = lambda: MagicMock()
    with patch("app.routers.interview_prep.require_user_quota", new_callable=AsyncMock), \
         patch("app.routers.interview_prep._get_profile_and_offer",
               new=AsyncMock(return_value=({}, {}, None))), \
         patch("app.routers.interview_prep.generate_star_stories",
               new=AsyncMock(side_effect=_openai_credits_error())):
        res = api.post(f"/offers/{ObjectId()}/interview-prep/generate/stories")
    _assert_openai_credits(res)


def test_offer_evaluation_reports_provider_credits(api):
    app.dependency_overrides[get_database] = lambda: MagicMock()
    with patch("app.routers.job_offers.evaluate_offer_two_pass",
               new=AsyncMock(side_effect=_openai_credits_error())):
        res = api.post(f"/job-offers/{ObjectId()}/evaluate")
    _assert_openai_credits(res)


def test_application_scoring_reports_provider_credits(api):
    offer_id = ObjectId()
    colls = {
        "applications": MagicMock(find_one=AsyncMock(return_value={
            "_id": ObjectId(), "user_id": USER_ID, "offer_id": str(offer_id),
        })),
        "job_offers": MagicMock(find_one=AsyncMock(return_value={"_id": offer_id})),
    }
    app.dependency_overrides[get_database] = lambda: _db(colls)
    with patch("app.routers.applications.evaluate_offer_two_pass",
               new=AsyncMock(side_effect=_openai_credits_error())):
        res = api.post(f"/applications/{ObjectId()}/evaluate")
    _assert_openai_credits(res)


def test_non_llm_error_still_returns_generic_500(api):
    colls = {
        "candidate_profile": MagicMock(find_one=AsyncMock(return_value={"_id": ObjectId(), "skills": []})),
        "job_offers": MagicMock(find_one=AsyncMock(return_value={"_id": ObjectId(), "title": "Dev"})),
        "offer_evaluations": MagicMock(find_one=AsyncMock(return_value=None)),
    }
    app.dependency_overrides[get_database] = lambda: _db(colls)
    with patch("app.routers.resumes.require_user_quota", new_callable=AsyncMock), \
         patch("app.routers.resumes.generate_tailored_cv_content",
               new=AsyncMock(side_effect=RuntimeError("boom"))):
        res = api.post("/resumes/generate", json={"offer_id": str(ObjectId())})
    assert res.status_code == 500


@pytest.mark.asyncio
async def test_cover_letter_failure_names_the_provider():
    app_id, user_id, letter_id = ObjectId(), ObjectId(), ObjectId()
    letters = MagicMock(
        find_one=AsyncMock(return_value=None),
        insert_one=AsyncMock(return_value=MagicMock(inserted_id=letter_id)),
        update_one=AsyncMock(),
    )
    colls = {
        "cover_letters": letters,
        "applications": MagicMock(find_one=AsyncMock(return_value={"_id": app_id, "description": "Desc"})),
        "candidate_profile": MagicMock(find_one=AsyncMock(return_value={"skills": []})),
        "users": MagicMock(find_one=AsyncMock(return_value={"full_name": "A B"})),
    }
    with patch("cover_letter_crew.run_letter_pipeline_async",
               new=AsyncMock(side_effect=_openai_credits_error())):
        await _generate_cover_letter_bg(app_id, user_id, _db(colls))

    error = letters.update_one.call_args.args[1]["$set"]["error"]
    assert "OpenAI" in error
    assert "Crédits épuisés" in error


def test_website_import_reports_provider_credits(api):
    app.dependency_overrides[get_database] = lambda: MagicMock()
    with patch("app.routers.cover_letters.validate_public_url_async",
               new=AsyncMock(return_value="https://example.com")), \
         patch("app.routers.cover_letters.collect_website",
               new=AsyncMock(side_effect=_openai_credits_error())):
        res = api.post("/profile/candidate/sources/website", json={"url": "https://example.com"})
    _assert_openai_credits(res)
