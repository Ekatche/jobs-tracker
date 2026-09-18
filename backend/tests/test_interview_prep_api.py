import pytest
from unittest.mock import AsyncMock, patch
from bson import ObjectId
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.database import get_database
from app.models import (
    StarRStory,
    AudiencePackRecruiter,
    AudiencePackHiringManager,
    AudiencePackTechPanel,
    AnticipatedQuestion,
    ReverseQuestion,
    UserModel,
)
from main import app

client = TestClient(app)

mock_user_id = str(ObjectId())
mock_user = UserModel(
    id=mock_user_id,
    username="testcandidate",
    email="candidate@test.com",
    hashed_password="fakehashpassword",
)


@pytest.fixture
def override_auth():
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_get_interview_prep_unauthorized():
    res = client.get(f"/offers/{ObjectId()}/interview-prep")
    assert res.status_code in [401, 403]


@pytest.mark.asyncio
async def test_get_interview_prep_empty(override_auth):
    offer_id = str(ObjectId())
    res = client.get(f"/offers/{offer_id}/interview-prep")
    assert res.status_code == 200
    data = res.json()
    assert data["offer_id"] == offer_id
    assert data["stories"] == []
    assert data["anticipated_questions"] == []


@pytest.mark.asyncio
async def test_generate_stories_endpoint(override_auth):
    offer_id = ObjectId()
    db = await get_database()

    # Seed mock candidate profile and offer
    await db.candidate_profiles.update_one(
        {"user_id": mock_user_id},
        {"$set": {"user_id": mock_user_id, "skills": ["Python", "Docker"], "experiences": [{"company": "Alpha Corp"}]}},
        upsert=True,
    )
    await db.job_offers.update_one(
        {"_id": offer_id},
        {"$set": {"_id": offer_id, "title": "Senior Python", "company": "Alpha Corp", "description": "Need Python"}},
        upsert=True,
    )

    mock_generated_story = StarRStory(
        title="[Scalabilité] Pipeline",
        theme="Architecture",
        target_requirement="Python",
        situation="Charge élevée",
        task="Optimiser",
        action="AsyncIO",
        result="+50%",
        reflection="Refaire plus tôt",
        key_tags=["python"],
    )

    with patch("app.routers.interview_prep.require_user_quota", return_value=True):
        with patch("app.routers.interview_prep.generate_star_stories", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = [mock_generated_story]
            res = client.post(f"/offers/{str(offer_id)}/interview-prep/generate/stories")

    assert res.status_code == 200
    data = res.json()
    assert len(data["stories"]) == 1
    assert data["stories"][0]["title"] == "[Scalabilité] Pipeline"


@pytest.mark.asyncio
async def test_update_and_export_interview_prep(override_auth):
    offer_id = ObjectId()
    db = await get_database()

    await db.job_offers.update_one(
        {"_id": offer_id},
        {"$set": {"_id": offer_id, "title": "Staff Engineer", "company": "Beta Inc"}},
        upsert=True,
    )

    update_payload = {
        "stories": [
            {
                "title": "[Leadership] Mentor",
                "theme": "Management",
                "target_requirement": "Mentorat",
                "situation": "3 juniors",
                "task": "Former",
                "action": "Pair programming",
                "result": "Autonomie",
                "reflection": "Patience",
                "key_tags": ["mentorat"],
            }
        ],
        "recruiter_pack": {
            "pitch_30s": "Pitch test...",
            "comp_strategy": {"volunteer": "marché", "avoid": "aucun"},
            "red_flags_they_screen_for": ["absence"],
            "key_questions_to_ask_recruiter": ["timing"],
        },
    }

    # PUT
    put_res = client.put(f"/offers/{str(offer_id)}/interview-prep", json=update_payload)
    assert put_res.status_code == 200
    assert len(put_res.json()["stories"]) == 1

    # GET export
    export_res = client.get(f"/offers/{str(offer_id)}/interview-prep/export")
    assert export_res.status_code == 200
    assert "text/markdown" in export_res.headers["content-type"]
    assert "# Kit de Préparation d'Entretien" in export_res.text
    assert "[Leadership] Mentor" in export_res.text
