"""Tests d'intégration pour la modification manuelle ou IA des slots d'histoires et la gestion des conflits concurrents."""

from unittest.mock import AsyncMock, patch
from bson import ObjectId
import pytest

from app.models import StoryFacts, StorySlot
from tests.interview_prep.conftest import (
    _seed_bank_story,
    _slot_dict,
    make_bank_story_model,
    mock_user_id,
)


async def _seed_write_scenario(db, extra_slots=()):
    """Profil, offre et kit dont la première ligne est en manque, suivie de `extra_slots`."""
    offer_id = ObjectId()
    await db.candidate_profile.update_one(
        {"user_id": mock_user_id},
        {"$set": {"user_id": mock_user_id, "skills": ["Python"], "experiences": []}},
        upsert=True,
    )
    await db.job_offers.insert_one({"_id": offer_id, "title": "Senior Python", "company": "Alpha Corp"})
    gap_slot = _slot_dict(None, requirement="R1", fit="gap")
    insert_result = await db.interview_preps.insert_one({
        "offer_id": str(offer_id),
        "user_id": mock_user_id,
        "story_slots": [gap_slot, *extra_slots],
        "anticipated_questions": [],
    })
    return offer_id, insert_result.inserted_id, gap_slot


@pytest.mark.asyncio
async def test_write_slot_only_on_gap(client, override_auth, test_db):
    offer_id = ObjectId()
    db = test_db
    await db.job_offers.insert_one({"_id": offer_id, "title": "Senior Python", "company": "Alpha Corp"})
    s1 = await _seed_bank_story(db, title="S1")
    strong_slot = _slot_dict(s1["id"], requirement="R1", fit="strong")
    await db.interview_preps.insert_one({
        "offer_id": str(offer_id),
        "user_id": mock_user_id,
        "story_slots": [strong_slot],
        "anticipated_questions": [],
    })

    res = client.post(f"/offers/{str(offer_id)}/interview-prep/slots/{strong_slot['id']}/write")
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_write_slot_fills_gap_and_adds_story_to_bank(client, override_auth, test_db):
    offer_id = ObjectId()
    db = test_db
    await db.candidate_profile.update_one(
        {"user_id": mock_user_id},
        {"$set": {"user_id": mock_user_id, "skills": ["Python"], "experiences": []}},
        upsert=True,
    )
    await db.job_offers.insert_one({"_id": offer_id, "title": "Senior Python", "company": "Alpha Corp"})
    gap_slot = _slot_dict(None, requirement="R1", fit="gap")
    await db.interview_preps.insert_one({
        "offer_id": str(offer_id),
        "user_id": mock_user_id,
        "story_slots": [gap_slot],
        "anticipated_questions": [],
    })

    n1 = make_bank_story_model(offer_id, title="N1")
    new_slot = StorySlot(id=gap_slot["id"], requirement="R1", story_id=n1.id, fit="strong")

    with patch("app.routers.interview_prep.require_user_quota", return_value=True), \
            patch("app.routers.interview_prep.write_stories_for_requirements", new_callable=AsyncMock) as mock_write:
        mock_write.return_value = [(new_slot, n1)]
        res = client.post(f"/offers/{str(offer_id)}/interview-prep/slots/{gap_slot['id']}/write")

    assert res.status_code == 200
    row = next(r for r in res.json()["story_slots"] if r["id"] == gap_slot["id"])
    assert (row["story_id"], row["fit"]) == (n1.id, "strong")
    stored = await db.star_stories.find_one({"id": n1.id})
    assert stored["origin"]["kind"] == "generated"


@pytest.mark.asyncio
async def test_manual_story_on_no_experience_row(client, override_auth, test_db):
    offer_id = ObjectId()
    db = test_db
    await db.candidate_profile.update_one(
        {"user_id": mock_user_id},
        {"$set": {"user_id": mock_user_id, "skills": ["Python"], "experiences": [{"company": "Alpha Corp"}]}},
        upsert=True,
    )
    await db.job_offers.insert_one({"_id": offer_id, "title": "Senior Python", "company": "Alpha Corp"})
    noexp_slot = _slot_dict(None, requirement="R1", fit="no_experience")
    await db.interview_preps.insert_one({
        "offer_id": str(offer_id),
        "user_id": mock_user_id,
        "story_slots": [noexp_slot],
        "anticipated_questions": [],
    })

    facts = StoryFacts(
        title="Histoire manuelle", situation="S", task="T", action="A", result="R",
    )

    with patch("app.routers.interview_prep.write_stories_for_requirements", new_callable=AsyncMock) as mock_write:
        res = client.post(
            f"/offers/{str(offer_id)}/interview-prep/slots/{noexp_slot['id']}/manual-story",
            json=facts.model_dump(),
        )

    assert res.status_code == 200
    mock_write.assert_not_called()
    row = next(r for r in res.json()["story_slots"] if r["id"] == noexp_slot["id"])
    assert row["fit"] == "manual"
    assert row["story"]["origin"]["kind"] == "manual"


@pytest.mark.asyncio
async def test_write_slot_keeps_concurrent_edit_of_other_row(client, override_auth, test_db):
    s1 = await _seed_bank_story(test_db, title="S1")
    other_slot = _slot_dict(s1["id"], requirement="R2", angle="Angle IA")
    offer_id, prep_id, gap_slot = await _seed_write_scenario(test_db, extra_slots=[other_slot])

    n1 = make_bank_story_model(offer_id, title="N1")
    new_slot = StorySlot(id=gap_slot["id"], requirement="R1", story_id=n1.id, fit="strong")

    async def _edit_other_row_during_llm(**kwargs):
        await kwargs["db"].interview_preps.update_one(
            {"_id": prep_id, "story_slots.id": other_slot["id"]},
            {"$set": {"story_slots.$.angle": "Angle retouché", "story_slots.$.angle_edited": True}},
        )
        return [(new_slot, n1)]

    with patch("app.routers.interview_prep.require_user_quota", return_value=True), \
            patch("app.routers.interview_prep.write_stories_for_requirements", new_callable=AsyncMock) as mock_write:
        mock_write.side_effect = _edit_other_row_during_llm
        res = client.post(f"/offers/{str(offer_id)}/interview-prep/slots/{gap_slot['id']}/write")

    assert res.status_code == 200
    stored = await test_db.interview_preps.find_one({"_id": prep_id})
    rows = {s["id"]: s for s in stored["story_slots"]}
    assert (rows[other_slot["id"]]["angle"], rows[other_slot["id"]]["angle_edited"]) == ("Angle retouché", True)
    assert rows[gap_slot["id"]]["story_id"] == n1.id


@pytest.mark.asyncio
@pytest.mark.parametrize("concurrent_change", ["ligne supprimée", "histoire posée"])
async def test_write_slot_conflict_keeps_written_story_in_bank(client, override_auth, test_db, concurrent_change):
    chosen = await _seed_bank_story(test_db, title="Choisie")
    offer_id, prep_id, gap_slot = await _seed_write_scenario(test_db)

    n1 = make_bank_story_model(offer_id, title="N1")
    new_slot = StorySlot(id=gap_slot["id"], requirement="R1", story_id=n1.id, fit="strong")

    async def _change_target_row_during_llm(**kwargs):
        preps = kwargs["db"].interview_preps
        if concurrent_change == "ligne supprimée":
            await preps.update_one({"_id": prep_id}, {"$pull": {"story_slots": {"id": gap_slot["id"]}}})
        else:
            await preps.update_one(
                {"_id": prep_id, "story_slots.id": gap_slot["id"]},
                {"$set": {"story_slots.$.story_id": chosen["id"], "story_slots.$.fit": "manual"}},
            )
        return [(new_slot, n1)]

    with patch("app.routers.interview_prep.require_user_quota", return_value=True), \
            patch("app.routers.interview_prep.write_stories_for_requirements", new_callable=AsyncMock) as mock_write:
        mock_write.side_effect = _change_target_row_during_llm
        res = client.post(f"/offers/{str(offer_id)}/interview-prep/slots/{gap_slot['id']}/write")

    assert res.status_code == 409
    assert res.json()["detail"] == (
        "La ligne a changé pendant l'écriture ; l'histoire écrite a été ajoutée à ta banque."
    )
    assert await test_db.star_stories.count_documents({"id": n1.id}) == 1
    stored = await test_db.interview_preps.find_one({"_id": prep_id})
    rows = {s["id"]: s for s in stored["story_slots"]}
    if concurrent_change == "ligne supprimée":
        assert gap_slot["id"] not in rows
    else:
        assert (rows[gap_slot["id"]]["story_id"], rows[gap_slot["id"]]["fit"]) == (chosen["id"], "manual")


@pytest.mark.asyncio
async def test_write_slot_conflict_without_written_story(client, override_auth, test_db):
    offer_id, prep_id, gap_slot = await _seed_write_scenario(test_db)
    no_story_slot = StorySlot(id=gap_slot["id"], requirement="R1", story_id=None, fit="gap")

    async def _delete_target_row_during_llm(**kwargs):
        await kwargs["db"].interview_preps.update_one(
            {"_id": prep_id}, {"$pull": {"story_slots": {"id": gap_slot["id"]}}}
        )
        return [(no_story_slot, None)]

    with patch("app.routers.interview_prep.require_user_quota", return_value=True), \
            patch("app.routers.interview_prep.write_stories_for_requirements", new_callable=AsyncMock) as mock_write:
        mock_write.side_effect = _delete_target_row_during_llm
        res = client.post(f"/offers/{str(offer_id)}/interview-prep/slots/{gap_slot['id']}/write")

    assert res.status_code == 409
    assert res.json()["detail"] == "La ligne a changé pendant l'écriture."


@pytest.mark.asyncio
async def test_write_slot_does_not_restore_row_deleted_meanwhile(client, override_auth, test_db):
    s1 = await _seed_bank_story(test_db, title="S1")
    other_slot = _slot_dict(s1["id"], requirement="R2")
    offer_id, prep_id, gap_slot = await _seed_write_scenario(test_db, extra_slots=[other_slot])

    n1 = make_bank_story_model(offer_id, title="N1")
    new_slot = StorySlot(id=gap_slot["id"], requirement="R1", story_id=n1.id, fit="strong")

    async def _delete_other_row_during_llm(**kwargs):
        await kwargs["db"].interview_preps.update_one(
            {"_id": prep_id}, {"$pull": {"story_slots": {"id": other_slot["id"]}}}
        )
        return [(new_slot, n1)]

    with patch("app.routers.interview_prep.require_user_quota", return_value=True), \
            patch("app.routers.interview_prep.write_stories_for_requirements", new_callable=AsyncMock) as mock_write:
        mock_write.side_effect = _delete_other_row_during_llm
        res = client.post(f"/offers/{str(offer_id)}/interview-prep/slots/{gap_slot['id']}/write")

    assert res.status_code == 200
    stored = await test_db.interview_preps.find_one({"_id": prep_id})
    assert [s["id"] for s in stored["story_slots"]] == [gap_slot["id"]]
    assert stored["story_slots"][0]["story_id"] == n1.id


@pytest.mark.asyncio
async def test_put_slot_null_story_turns_row_into_gap_writable_by_ai(client, override_auth, test_db):
    s1 = await _seed_bank_story(test_db, title="S1")
    strong_slot = _slot_dict(s1["id"], requirement="R2", fit="strong", angle="Angle", angle_edited=True)
    offer_id, prep_id, _gap_slot = await _seed_write_scenario(test_db, extra_slots=[strong_slot])

    put_res = client.put(
        f"/offers/{str(offer_id)}/interview-prep/slots/{strong_slot['id']}", json={"story_id": None}
    )

    assert put_res.status_code == 200
    row = next(r for r in put_res.json()["story_slots"] if r["id"] == strong_slot["id"])
    assert (row["story_id"], row["fit"], row["angle"], row["angle_edited"], row["story"]) == (
        None, "gap", "", False, None
    )

    n1 = make_bank_story_model(offer_id, title="N1")
    new_slot = StorySlot(id=strong_slot["id"], requirement="R2", story_id=n1.id, fit="strong")
    with patch("app.routers.interview_prep.require_user_quota", return_value=True), \
            patch("app.routers.interview_prep.write_stories_for_requirements", new_callable=AsyncMock) as mock_write:
        mock_write.return_value = [(new_slot, n1)]
        write_res = client.post(f"/offers/{str(offer_id)}/interview-prep/slots/{strong_slot['id']}/write")

    assert write_res.status_code == 200

