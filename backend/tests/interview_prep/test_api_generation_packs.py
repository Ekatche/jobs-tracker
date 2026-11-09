"""Tests d'intégration pour la génération des packs d'audience, questions et annulation."""

from unittest.mock import AsyncMock, patch
from bson import ObjectId
import pytest

from app.models import (
    AudiencePackHiringManager,
    AudiencePackRecruiter,
    AudiencePackTechPanel,
    StorySlot,
)
from tests.interview_prep.conftest import (
    _seed_bank_story,
    _slot_dict,
    make_bank_story_model,
    mock_user_id,
)


@pytest.mark.asyncio
async def test_generate_cancelled_writes_nothing(client, override_auth, test_db):
    offer_id = ObjectId()
    db = test_db
    await db.candidate_profile.update_one(
        {"user_id": mock_user_id},
        {"$set": {"user_id": mock_user_id, "skills": ["Python"], "experiences": []}},
        upsert=True,
    )
    await db.job_offers.insert_one({"_id": offer_id, "title": "Senior Python", "company": "Alpha Corp"})

    s1 = await _seed_bank_story(db, title="S1")
    insert_result = await db.interview_preps.insert_one({
        "offer_id": str(offer_id),
        "user_id": mock_user_id,
        "stories": [],
        "story_slots": [_slot_dict(s1["id"], requirement="R1")],
        "anticipated_questions": [],
    })
    before = await db.interview_preps.find_one({"_id": insert_result.inserted_id})

    n1 = make_bank_story_model(offer_id, title="N1")
    new_slot = StorySlot(requirement="R1", story_id=n1.id, fit="strong")

    with patch("app.routers.interview_prep.require_user_quota", return_value=True), \
            patch("app.routers.interview_prep.build_story_slots", new_callable=AsyncMock) as mock_build, \
            patch("app.routers.interview_prep._generation_cancelled", new_callable=AsyncMock, return_value=True):
        mock_build.return_value = ([new_slot], [n1])
        res = client.post(f"/offers/{str(offer_id)}/interview-prep/generate/stories")

    assert res.status_code == 499
    assert await db.star_stories.count_documents({"id": n1.id}) == 0
    stored_prep = await db.interview_preps.find_one({"_id": insert_result.inserted_id})
    assert stored_prep["story_slots"] == before["story_slots"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path_suffix, patch_target, return_value",
    [
        (
            "generate/audience-packs",
            "app.routers.interview_prep.generate_audience_packs",
            (
                AudiencePackRecruiter(pitch_30s="P"),
                AudiencePackHiringManager(strategic_alignment="S"),
                AudiencePackTechPanel(),
            ),
        ),
        (
            "generate/questions",
            "app.routers.interview_prep.generate_anticipated_questions",
            [],
        ),
        (
            "generate/reverse-questions",
            "app.routers.interview_prep.generate_reverse_questions",
            [],
        ),
    ],
)
async def test_generate_endpoints_set_on_insert_story_slots_empty(
    client, override_auth, test_db, path_suffix, patch_target, return_value
):
    offer_id = ObjectId()
    db = test_db
    await db.candidate_profile.update_one(
        {"user_id": mock_user_id},
        {"$set": {"user_id": mock_user_id, "skills": ["Python"], "experiences": []}},
        upsert=True,
    )
    await db.job_offers.insert_one({"_id": offer_id, "title": "Senior Python", "company": "Alpha Corp"})
    assert await db.interview_preps.count_documents({"offer_id": str(offer_id)}) == 0

    with patch("app.routers.interview_prep.require_user_quota", return_value=True), \
            patch(patch_target, new_callable=AsyncMock) as mock_generate:
        mock_generate.return_value = return_value
        res = client.post(f"/offers/{str(offer_id)}/interview-prep/{path_suffix}")

    assert res.status_code == 200
    doc = await db.interview_preps.find_one({"offer_id": str(offer_id)})
    assert doc is not None
    assert doc["story_slots"] == []
    assert "stories" not in doc


@pytest.mark.asyncio
async def test_cancelled_generate_all_stops_before_next_module(client, override_auth, test_db):
    offer_id = ObjectId()
    db = test_db
    await db.candidate_profile.update_one(
        {"user_id": mock_user_id},
        {"$set": {"user_id": mock_user_id, "skills": ["Python"], "experiences": [{"company": "Alpha Corp"}]}},
        upsert=True,
    )
    await db.job_offers.insert_one({"_id": offer_id, "title": "Senior Python", "company": "Alpha Corp"})

    with patch("app.routers.interview_prep.require_user_quota", return_value=True), \
            patch("app.routers.interview_prep.build_story_slots", new_callable=AsyncMock) as mock_build, \
            patch("app.routers.interview_prep.generate_audience_packs", new_callable=AsyncMock) as mock_packs, \
            patch("app.routers.interview_prep.generate_anticipated_questions", new_callable=AsyncMock) as mock_questions, \
            patch("app.routers.interview_prep.generate_reverse_questions", new_callable=AsyncMock) as mock_reverse, \
            patch("starlette.requests.Request.is_disconnected", new_callable=AsyncMock, return_value=True):
        mock_build.return_value = ([], [])
        mock_packs.return_value = (
            AudiencePackRecruiter(pitch_30s="P"),
            AudiencePackHiringManager(strategic_alignment="S"),
            AudiencePackTechPanel(),
        )
        mock_questions.return_value = []
        mock_reverse.return_value = []
        res = client.post(f"/offers/{str(offer_id)}/interview-prep/generate/all")

    assert res.status_code == 499
    mock_build.assert_called_once()
    mock_packs.assert_not_called()
    mock_questions.assert_not_called()
    mock_reverse.assert_not_called()
    assert await db.interview_preps.count_documents({"offer_id": str(offer_id)}) == 0


@pytest.mark.asyncio
async def test_generate_all_sets_story_slots_not_stories(client, override_auth, test_db):
    offer_id = ObjectId()
    db = test_db
    await db.candidate_profile.update_one(
        {"user_id": mock_user_id},
        {"$set": {"user_id": mock_user_id, "skills": ["Python"], "experiences": []}},
        upsert=True,
    )
    await db.job_offers.insert_one({"_id": offer_id, "title": "Senior Python", "company": "Alpha Corp"})

    insert_result = await db.interview_preps.insert_one({
        "offer_id": str(offer_id),
        "user_id": mock_user_id,
        "stories": ["X"],
        "story_slots": [],
        "anticipated_questions": [],
    })
    before = await db.interview_preps.find_one({"_id": insert_result.inserted_id})

    n1 = make_bank_story_model(offer_id, title="N1")
    new_slot = StorySlot(requirement="R1", story_id=n1.id, fit="strong")

    with patch("app.routers.interview_prep.require_user_quota", return_value=True), \
            patch("app.routers.interview_prep.build_story_slots", new_callable=AsyncMock) as mock_build, \
            patch("app.routers.interview_prep.generate_audience_packs", new_callable=AsyncMock) as mock_packs, \
            patch("app.routers.interview_prep.generate_anticipated_questions", new_callable=AsyncMock) as mock_questions, \
            patch("app.routers.interview_prep.generate_reverse_questions", new_callable=AsyncMock) as mock_reverse:
        mock_build.return_value = ([new_slot], [n1])
        mock_packs.return_value = (
            AudiencePackRecruiter(pitch_30s="P"),
            AudiencePackHiringManager(strategic_alignment="S"),
            AudiencePackTechPanel(),
        )
        mock_questions.return_value = []
        mock_reverse.return_value = []
        res = client.post(f"/offers/{str(offer_id)}/interview-prep/generate/all")

    assert res.status_code == 200
    stored = await db.interview_preps.find_one({"_id": insert_result.inserted_id})
    assert stored["stories"] == before["stories"]
    assert stored["story_slots"][0]["story_id"] == n1.id
    assert await db.star_stories.count_documents({"id": n1.id}) == 1


@pytest.mark.asyncio
async def test_generate_all_turns_row_of_story_deleted_meanwhile_into_gap(client, override_auth, test_db):
    offer_id = ObjectId()
    db = test_db
    await db.candidate_profile.update_one(
        {"user_id": mock_user_id},
        {"$set": {"user_id": mock_user_id, "skills": ["Python"], "experiences": []}},
        upsert=True,
    )
    await db.job_offers.insert_one({"_id": offer_id, "title": "Senior Python", "company": "Alpha Corp"})
    s1 = await _seed_bank_story(db, title="S1")
    insert_result = await db.interview_preps.insert_one({
        "offer_id": str(offer_id),
        "user_id": mock_user_id,
        "story_slots": [],
        "anticipated_questions": [],
    })

    new_slot = StorySlot(requirement="R1", story_id=s1["id"], fit="strong", angle="Angle IA")

    async def _delete_story_during_llm(**kwargs):
        await kwargs["db"].star_stories.delete_one({"id": s1["id"]})
        return [new_slot], []

    with patch("app.routers.interview_prep.require_user_quota", return_value=True), \
            patch("app.routers.interview_prep.build_story_slots", new_callable=AsyncMock) as mock_build, \
            patch("app.routers.interview_prep.generate_audience_packs", new_callable=AsyncMock) as mock_packs, \
            patch("app.routers.interview_prep.generate_anticipated_questions", new_callable=AsyncMock) as mock_questions, \
            patch("app.routers.interview_prep.generate_reverse_questions", new_callable=AsyncMock) as mock_reverse:
        mock_build.side_effect = _delete_story_during_llm
        mock_packs.return_value = (
            AudiencePackRecruiter(pitch_30s="P"),
            AudiencePackHiringManager(strategic_alignment="S"),
            AudiencePackTechPanel(),
        )
        mock_questions.return_value = []
        mock_reverse.return_value = []
        res = client.post(f"/offers/{str(offer_id)}/interview-prep/generate/all")

    assert res.status_code == 200
    stored = await db.interview_preps.find_one({"_id": insert_result.inserted_id})
    row = stored["story_slots"][0]
    assert (row["story_id"], row["fit"], row["angle"], row["angle_edited"]) == (None, "gap", "", False)
