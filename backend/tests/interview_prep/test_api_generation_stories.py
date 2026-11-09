"""Tests d'intégration pour la génération des histoires et synchronisation de la banque."""

from unittest.mock import AsyncMock, patch
from bson import ObjectId
import pytest

from app.models import AnticipatedQuestion, StarRStory, StorySlot
from tests.interview_prep.conftest import (
    _seed_bank_story,
    _slot_dict,
    make_bank_story_model,
    mock_user_id,
)


@pytest.mark.asyncio
async def test_generate_stories_endpoint(client, override_auth, test_db):
    offer_id = ObjectId()
    db = test_db

    await db.candidate_profile.update_one(
        {"user_id": mock_user_id},
        {"$set": {"user_id": mock_user_id, "skills": ["Python", "Docker"], "experiences": [{"company": "Alpha Corp"}]}},
        upsert=True,
    )

    await db.job_offers.update_one(
        {"_id": offer_id},
        {"$set": {"_id": offer_id, "title": "Senior Python", "company": "Alpha Corp", "description": "Need Python"}},
        upsert=True,
    )

    new_story = make_bank_story_model(offer_id, title="[Scalabilité] Pipeline")
    new_slot = StorySlot(requirement="Python", story_id=new_story.id, fit="strong")

    with patch("app.routers.interview_prep.require_user_quota", return_value=True):
        with patch("app.routers.interview_prep.build_story_slots", new_callable=AsyncMock) as mock_build:
            mock_build.return_value = ([new_slot], [new_story])
            res = client.post(f"/offers/{str(offer_id)}/interview-prep/generate/stories")

    assert res.status_code == 200
    data = res.json()
    assert len(data["story_slots"]) == 1
    assert data["story_slots"][0]["story"]["title"] == "[Scalabilité] Pipeline"
    assert await db.star_stories.count_documents({"id": new_story.id}) == 1


@pytest.mark.asyncio
async def test_generate_stories_clears_stale_story_links(client, override_auth, test_db):
    offer_id = ObjectId()
    db = test_db
    await db.candidate_profile.update_one(
        {"user_id": mock_user_id},
        {"$set": {"user_id": mock_user_id, "skills": ["Python"], "experiences": [{"company": "Alpha Corp"}]}},
        upsert=True,
    )
    await db.job_offers.insert_one({"_id": offer_id, "title": "Senior Python", "company": "Alpha Corp"})

    old_story = StarRStory(
        title="Ancienne", theme="T", target_requirement="R",
        situation="S", task="T", action="A", result="R", reflection="R", key_tags=[],
    )
    linked = AnticipatedQuestion(
        category="behavioral", question="Parlez d'un échec", why_it_will_be_asked="JD", mapped_story_id=old_story.id
    )
    unlinked = AnticipatedQuestion(category="technical", question="Expliquez asyncio", why_it_will_be_asked="JD")
    await db.interview_preps.insert_one({
        "offer_id": str(offer_id),
        "user_id": mock_user_id,
        "stories": [old_story.model_dump()],
        "anticipated_questions": [linked.model_dump(), unlinked.model_dump()],
    })

    new_story = make_bank_story_model(offer_id, title="Nouvelle")
    new_slot = StorySlot(requirement="R", story_id=new_story.id, fit="strong")

    with patch("app.routers.interview_prep.require_user_quota", return_value=True):
        with patch("app.routers.interview_prep.build_story_slots", new_callable=AsyncMock) as mock_build:
            mock_build.return_value = ([new_slot], [new_story])
            res = client.post(f"/offers/{str(offer_id)}/interview-prep/generate/stories")

    assert res.status_code == 200
    questions = res.json()["anticipated_questions"]
    assert [q["question"] for q in questions] == ["Parlez d'un échec", "Expliquez asyncio"]
    assert all(q["mapped_story_id"] is None for q in questions)


@pytest.mark.asyncio
async def test_generate_stories_on_unmigrated_kit_keeps_legacy_stories_in_bank(client, override_auth, test_db):
    offer_id = ObjectId()
    db = test_db
    await db.candidate_profile.update_one(
        {"user_id": mock_user_id},
        {"$set": {"user_id": mock_user_id, "skills": ["Python"], "experiences": []}},
        upsert=True,
    )
    await db.job_offers.insert_one({"_id": offer_id, "title": "Senior Python", "company": "Alpha Corp"})

    s1 = StarRStory(
        title="Une", theme="T", target_requirement="R1",
        situation="S1", task="T", action="A", result="R", reflection="", key_tags=[],
    )
    s2 = StarRStory(
        title="Deux", theme="T", target_requirement="R2",
        situation="S2", task="T", action="A", result="R", reflection="", key_tags=[],
    )
    legacy_stories = [s1.model_dump(), s2.model_dump()]
    insert_result = await db.interview_preps.insert_one({
        "offer_id": str(offer_id),
        "user_id": mock_user_id,
        "stories": legacy_stories,
        "anticipated_questions": [],
    })

    new_story = make_bank_story_model(offer_id, title="Fraîche")
    new_slot = StorySlot(requirement="R1", story_id=new_story.id, fit="strong")

    with patch("app.routers.interview_prep.require_user_quota", return_value=True):
        with patch("app.routers.interview_prep.build_story_slots", new_callable=AsyncMock) as mock_build:
            mock_build.return_value = ([new_slot], [new_story])
            res = client.post(f"/offers/{str(offer_id)}/interview-prep/generate/stories")

    assert res.status_code == 200
    assert await db.star_stories.count_documents({"id": {"$in": [s1.id, s2.id]}}) == 2
    stored = await db.interview_preps.find_one({"_id": insert_result.inserted_id})
    assert stored["stories"] == legacy_stories


@pytest.mark.asyncio
async def test_regenerate_never_deletes_bank_story(client, override_auth, test_db):
    offer_id = ObjectId()
    db = test_db
    await db.candidate_profile.update_one(
        {"user_id": mock_user_id},
        {"$set": {"user_id": mock_user_id, "skills": ["Python"], "experiences": []}},
        upsert=True,
    )
    await db.job_offers.insert_one({"_id": offer_id, "title": "Senior Python", "company": "Alpha Corp"})

    s1 = await _seed_bank_story(db, title="S1")
    await db.interview_preps.insert_one({
        "offer_id": str(offer_id),
        "user_id": mock_user_id,
        "stories": [],
        "story_slots": [_slot_dict(s1["id"], requirement="R1")],
        "anticipated_questions": [],
    })

    n1 = make_bank_story_model(offer_id, title="N1")
    new_slot = StorySlot(requirement="R1", story_id=n1.id, fit="strong")

    with patch("app.routers.interview_prep.require_user_quota", return_value=True):
        with patch("app.routers.interview_prep.build_story_slots", new_callable=AsyncMock) as mock_build:
            mock_build.return_value = ([new_slot], [n1])
            res = client.post(f"/offers/{str(offer_id)}/interview-prep/generate/stories")

    assert res.status_code == 200
    assert await db.star_stories.count_documents({"id": s1["id"]}) == 1
    assert await db.star_stories.count_documents({"id": n1.id}) == 1


@pytest.mark.asyncio
async def test_generate_stories_uses_only_current_user_evaluation(client, override_auth, test_db):
    offer_id = ObjectId()
    db = test_db
    await db.candidate_profile.update_one(
        {"user_id": mock_user_id},
        {"$set": {"user_id": mock_user_id, "skills": ["Python"], "experiences": [{"company": "Alpha Corp"}]}},
        upsert=True,
    )
    await db.job_offers.insert_one({"_id": offer_id, "title": "Senior Python", "company": "Alpha Corp"})
    await db.offer_evaluations.insert_one(
        {"user_id": str(ObjectId()), "offer_id": str(offer_id), "score": 1.0}
    )
    await db.offer_evaluations.insert_one(
        {"user_id": mock_user_id, "offer_id": str(offer_id), "score": 4.5}
    )

    with patch("app.routers.interview_prep.require_user_quota", return_value=True):
        with patch("app.routers.interview_prep.build_story_slots", new_callable=AsyncMock) as mock_build:
            mock_build.return_value = ([], [])
            res = client.post(f"/offers/{str(offer_id)}/interview-prep/generate/stories")

    assert res.status_code == 200
    evaluation = mock_build.call_args.kwargs["evaluation"]
    assert evaluation["user_id"] == mock_user_id
    assert evaluation["score"] == 4.5


@pytest.mark.asyncio
async def test_generate_stories_turns_row_of_story_deleted_meanwhile_into_gap(client, override_auth, test_db):
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

    with patch("app.routers.interview_prep.require_user_quota", return_value=True):
        with patch("app.routers.interview_prep.build_story_slots", new_callable=AsyncMock) as mock_build:
            mock_build.side_effect = _delete_story_during_llm
            res = client.post(f"/offers/{str(offer_id)}/interview-prep/generate/stories")

    assert res.status_code == 200
    stored = await db.interview_preps.find_one({"_id": insert_result.inserted_id})
    row = stored["story_slots"][0]
    assert (row["story_id"], row["fit"], row["angle"], row["angle_edited"]) == (None, "gap", "", False)


@pytest.mark.asyncio
async def test_generate_stories_rereads_questions_after_llm(client, override_auth, test_db):
    offer_id = ObjectId()
    db = test_db
    await db.candidate_profile.update_one(
        {"user_id": mock_user_id},
        {"$set": {"user_id": mock_user_id, "skills": ["Python"], "experiences": []}},
        upsert=True,
    )
    await db.job_offers.insert_one({"_id": offer_id, "title": "Senior Python", "company": "Alpha Corp"})
    kept = await _seed_bank_story(db, title="Gardée")
    discarded = await _seed_bank_story(db, title="Écartée")
    question = AnticipatedQuestion(
        category="behavioral", question="Parlez d'une migration", why_it_will_be_asked="JD",
        mapped_story_id=discarded["id"],
    )
    insert_result = await db.interview_preps.insert_one({
        "offer_id": str(offer_id),
        "user_id": mock_user_id,
        "story_slots": [_slot_dict(discarded["id"], requirement="R1")],
        "anticipated_questions": [question.model_dump()],
    })

    new_slot = StorySlot(requirement="R1", story_id=kept["id"], fit="strong")

    async def _redirect_question_during_llm(**kwargs):
        await kwargs["db"].interview_preps.update_one(
            {"_id": insert_result.inserted_id},
            {"$set": {"anticipated_questions.0.mapped_story_id": kept["id"]}},
        )
        return [new_slot], []

    with patch("app.routers.interview_prep.require_user_quota", return_value=True):
        with patch("app.routers.interview_prep.build_story_slots", new_callable=AsyncMock) as mock_build:
            mock_build.side_effect = _redirect_question_during_llm
            res = client.post(f"/offers/{str(offer_id)}/interview-prep/generate/stories")

    assert res.status_code == 200
    stored = await db.interview_preps.find_one({"_id": insert_result.inserted_id})
    assert stored["anticipated_questions"][0]["mapped_story_id"] == kept["id"]
