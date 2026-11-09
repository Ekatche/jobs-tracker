"""Tests d'intégration de l'API Interview Prep pour le cycle de vie, les permissions et l'export markdown."""

from unittest.mock import AsyncMock, patch
from bson import ObjectId
import pytest

from tests.interview_prep.conftest import (
    _seed_bank_story,
    _slot_dict,
    mock_user_id,
)


def test_get_interview_prep_unauthorized(client):
    res = client.get(f"/offers/{ObjectId()}/interview-prep")
    assert res.status_code in [401, 403]


@pytest.mark.asyncio
async def test_get_interview_prep_empty(client, override_auth):
    offer_id = str(ObjectId())
    res = client.get(f"/offers/{offer_id}/interview-prep")
    assert res.status_code == 200
    data = res.json()
    assert data["offer_id"] == offer_id
    assert data["stories"] == []
    assert data["anticipated_questions"] == []
    assert data["story_slots"] == []


@pytest.mark.asyncio
async def test_update_and_export_interview_prep(client, override_auth, test_db):
    offer_id = ObjectId()
    db = test_db

    await db.job_offers.update_one(
        {"_id": offer_id},
        {"$set": {"_id": offer_id, "title": "Staff Engineer", "company": "Beta Inc"}},
        upsert=True,
    )

    s1 = await _seed_bank_story(db, title="Mentor", result="3 juniors autonomes")
    await db.interview_preps.insert_one({
        "offer_id": str(offer_id),
        "user_id": mock_user_id,
        "story_slots": [_slot_dict(s1["id"], requirement="Mentorat", fit="strong")],
        "anticipated_questions": [],
    })

    update_payload = {
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
    assert "stories" not in put_res.json()
    assert put_res.json()["recruiter_pack"]["pitch_30s"] == "Pitch test..."

    # GET export
    export_res = client.get(f"/offers/{str(offer_id)}/interview-prep/export")
    assert export_res.status_code == 200
    assert "text/markdown" in export_res.headers["content-type"]
    assert "# Kit de Préparation d'Entretien" in export_res.text
    assert "Mentorat" in export_res.text
    assert "3 juniors autonomes" in export_res.text


@pytest.mark.asyncio
async def test_questions_receive_slot_stories(client, override_auth, test_db):
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
        "story_slots": [
            _slot_dict(s1["id"], requirement="R1"),
            _slot_dict(None, requirement="R2", fit="gap"),
        ],
        "anticipated_questions": [],
    })

    with patch("app.routers.interview_prep.require_user_quota", return_value=True), \
            patch("app.routers.interview_prep.generate_anticipated_questions", new_callable=AsyncMock) as mock_q:
        mock_q.return_value = []
        res = client.post(f"/offers/{str(offer_id)}/interview-prep/generate/questions")

    assert res.status_code == 200
    assert [s.id for s in mock_q.await_args.kwargs["stories"]] == [s1["id"]]


@pytest.mark.asyncio
async def test_questions_dedupes_slots_pointing_to_same_story(client, override_auth, test_db):
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
        "story_slots": [
            _slot_dict(s1["id"], requirement="R1"),
            _slot_dict(s1["id"], requirement="R2"),
        ],
        "anticipated_questions": [],
    })

    with patch("app.routers.interview_prep.require_user_quota", return_value=True), \
            patch("app.routers.interview_prep.generate_anticipated_questions", new_callable=AsyncMock) as mock_q:
        mock_q.return_value = []
        res = client.post(f"/offers/{str(offer_id)}/interview-prep/generate/questions")

    assert res.status_code == 200
    assert len(mock_q.await_args.kwargs["stories"]) == 1
