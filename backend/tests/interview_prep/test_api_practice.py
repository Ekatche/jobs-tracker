"""Tests d'intégration pour l'API du mode practice d'entretien (historique d'essais, mise à jour, isolation multi-utilisateurs)."""

from unittest.mock import AsyncMock, patch
from bson import ObjectId
import pytest

from app.models import (
    AnticipatedQuestion,
    PracticeAttempt,
    StarRStory,
)
from tests.interview_prep.conftest import (
    _seed_bank_story,
    _slot_dict,
    mock_user_id,
)


def _practice_attempt(**kwargs):
    return PracticeAttempt(
        question_id=kwargs["question"].id,
        question=kwargs["question"].question,
        answer=kwargs["answer"],
        overall_score=3.0,
        improved_answer="Version retravaillée",
    )


async def _seed_practice_prep(db, user_id=mock_user_id):
    """Profil, offre et kit avec une question liée à une histoire et une question libre."""
    offer_id = ObjectId()
    await db.candidate_profile.update_one(
        {"user_id": mock_user_id},
        {"$set": {"user_id": mock_user_id, "skills": ["Python"], "experiences": [{"company": "Alpha Corp"}]}},
        upsert=True,
    )
    await db.job_offers.insert_one({"_id": offer_id, "title": "Senior Python", "company": "Alpha Corp"})
    story = StarRStory(
        title="Migration", theme="T", target_requirement="R",
        situation="S", task="T", action="A", result="R", reflection="R", key_tags=[],
    )
    linked = AnticipatedQuestion(
        category="behavioral", question="Parlez d'une migration", why_it_will_be_asked="JD", mapped_story_id=story.id
    )
    free = AnticipatedQuestion(category="technical", question="Expliquez asyncio", why_it_will_be_asked="JD")
    await db.interview_preps.insert_one({
        "offer_id": str(offer_id),
        "user_id": user_id,
        "stories": [story.model_dump()],
        "anticipated_questions": [linked.model_dump(), free.model_dump()],
    })
    return offer_id, story, linked, free


def _seeded_attempt(question):
    return PracticeAttempt(
        question_id=question.id, question=question.question, answer="R", overall_score=3.0, improved_answer="V"
    ).model_dump()


@pytest.mark.asyncio
async def test_practice_appends_attempt_to_history(client, override_auth, test_db):
    offer_id, story, linked, _ = await _seed_practice_prep(test_db)

    with patch("app.routers.interview_prep.require_user_quota", return_value=True), \
            patch("app.routers.interview_prep.evaluate_practice_answer", new_callable=AsyncMock) as mock_eval:
        mock_eval.side_effect = _practice_attempt
        url = f"/offers/{str(offer_id)}/interview-prep/practice"
        first = client.post(url, json={"question_id": linked.id, "answer": "Réponse 1"})
        second = client.post(url, json={"question_id": linked.id, "answer": "Réponse 2"})

    assert first.status_code == 200
    assert second.status_code == 200
    attempts = second.json()["practice_attempts"]
    assert [a["answer"] for a in attempts] == ["Réponse 1", "Réponse 2"]
    assert all(a["question_id"] == linked.id for a in attempts)
    assert mock_eval.call_args.kwargs["story"].id == story.id
    assert mock_eval.call_args.kwargs["answer"] == "Réponse 2"

    export_res = client.get(f"/offers/{str(offer_id)}/interview-prep/export")
    assert export_res.status_code == 200


@pytest.mark.asyncio
async def test_practice_reads_up_to_date_facts_from_bank(client, override_auth, test_db):
    offer_id = ObjectId()
    db = test_db
    await db.candidate_profile.update_one(
        {"user_id": mock_user_id},
        {"$set": {"user_id": mock_user_id, "skills": ["Python"], "experiences": []}},
        upsert=True,
    )
    await db.job_offers.insert_one({"_id": offer_id, "title": "Senior Python", "company": "Alpha Corp"})

    s1 = await _seed_bank_story(db, title="S1", result="Avant correction")
    question = AnticipatedQuestion(
        category="behavioral", question="Parlez d'une migration", why_it_will_be_asked="JD",
        mapped_story_id=s1["id"],
    )
    await db.interview_preps.insert_one({
        "offer_id": str(offer_id),
        "user_id": mock_user_id,
        "story_slots": [_slot_dict(s1["id"], requirement="R1")],
        "anticipated_questions": [question.model_dump()],
    })

    patch_res = client.patch(f"/star-stories/{s1['id']}", json={"result": "−45 %"})
    assert patch_res.status_code == 200

    with patch("app.routers.interview_prep.require_user_quota", return_value=True), \
            patch("app.routers.interview_prep.evaluate_practice_answer", new_callable=AsyncMock) as mock_eval:
        mock_eval.side_effect = _practice_attempt
        res = client.post(
            f"/offers/{str(offer_id)}/interview-prep/practice",
            json={"question_id": question.id, "answer": "Réponse"},
        )

    assert res.status_code == 200
    assert mock_eval.await_args.kwargs["story"].result == "−45 %"


@pytest.mark.asyncio
async def test_practice_unknown_question_returns_404(client, override_auth, test_db):
    offer_id, _, linked, _ = await _seed_practice_prep(test_db)
    url = f"/offers/{str(offer_id)}/interview-prep/practice"

    with patch("app.routers.interview_prep.require_user_quota", return_value=True), \
            patch("app.routers.interview_prep.evaluate_practice_answer", new_callable=AsyncMock) as mock_eval:
        unknown = client.post(url, json={"question_id": "inconnue", "answer": "Réponse"})
        too_long = client.post(url, json={"question_id": linked.id, "answer": "x" * 6001})

    assert unknown.status_code == 404
    assert unknown.json()["detail"] == "Question introuvable dans le kit."
    assert too_long.status_code == 422
    mock_eval.assert_not_called()


@pytest.mark.asyncio
async def test_practice_ignores_other_users_prep(client, override_auth, test_db):
    other_user_id = str(ObjectId())
    offer_id, _, linked, _ = await _seed_practice_prep(test_db, user_id=other_user_id)

    with patch("app.routers.interview_prep.require_user_quota", return_value=True), \
            patch("app.routers.interview_prep.evaluate_practice_answer", new_callable=AsyncMock) as mock_eval:
        res = client.post(
            f"/offers/{str(offer_id)}/interview-prep/practice",
            json={"question_id": linked.id, "answer": "Réponse"},
        )

    assert res.status_code == 404
    mock_eval.assert_not_called()
    other = await test_db.interview_preps.find_one({"offer_id": str(offer_id), "user_id": other_user_id})
    assert "practice_attempts" not in other


@pytest.mark.asyncio
async def test_practice_attempts_cleared_when_questions_regenerated(client, override_auth, test_db):
    offer_id, _, linked, _ = await _seed_practice_prep(test_db)
    await test_db.interview_preps.update_one(
        {"offer_id": str(offer_id), "user_id": mock_user_id},
        {"$set": {"practice_attempts": [_seeded_attempt(linked)]}},
    )
    new_question = AnticipatedQuestion(category="technical", question="Nouvelle", why_it_will_be_asked="JD")

    with patch("app.routers.interview_prep.require_user_quota", return_value=True), \
            patch("app.routers.interview_prep.generate_anticipated_questions", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = [new_question]
        res = client.post(f"/offers/{str(offer_id)}/interview-prep/generate/questions")

    assert res.status_code == 200
    assert [q["id"] for q in res.json()["anticipated_questions"]] == [new_question.id]
    assert res.json()["practice_attempts"] == []


@pytest.mark.asyncio
async def test_practice_attempts_kept_for_remaining_questions_on_update(client, override_auth, test_db):
    offer_id, _, linked, free = await _seed_practice_prep(test_db)
    await test_db.interview_preps.update_one(
        {"offer_id": str(offer_id), "user_id": mock_user_id},
        {"$set": {"practice_attempts": [_seeded_attempt(linked), _seeded_attempt(free)]}},
    )

    res = client.put(f"/offers/{str(offer_id)}/interview-prep", json={"anticipated_questions": [free.model_dump()]})

    assert res.status_code == 200
    assert [a["question_id"] for a in res.json()["practice_attempts"]] == [free.id]

    fresh = client.put(f"/offers/{str(ObjectId())}/interview-prep", json={"anticipated_questions": [free.model_dump()]})
    assert fresh.status_code == 200

