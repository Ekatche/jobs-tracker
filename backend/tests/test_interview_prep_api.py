import pytest
from unittest.mock import AsyncMock, patch
from bson import ObjectId

from app.auth import get_current_user
from app.models import (
    StarRStory,
    AudiencePackRecruiter,
    AudiencePackHiringManager,
    AudiencePackTechPanel,
    AnticipatedQuestion,
    PracticeAttempt,
    UserModel,
)
from main import app

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


@pytest.mark.asyncio
async def test_generate_stories_endpoint(client, override_auth, test_db):
    offer_id = ObjectId()
    db = test_db

    # Seed mock candidate profile and offer
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
async def test_generate_stories_clears_stale_story_links(client, override_auth, test_db):
    """Régénérer les histoires ne doit pas laisser une question liée à une histoire disparue."""
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

    new_story = StarRStory(
        title="Nouvelle", theme="T", target_requirement="R",
        situation="S", task="T", action="A", result="R", reflection="R", key_tags=[],
    )
    with patch("app.routers.interview_prep.require_user_quota", return_value=True):
        with patch("app.routers.interview_prep.generate_star_stories", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = [new_story]
            res = client.post(f"/offers/{str(offer_id)}/interview-prep/generate/stories")

    assert res.status_code == 200
    questions = res.json()["anticipated_questions"]
    assert [q["question"] for q in questions] == ["Parlez d'un échec", "Expliquez asyncio"]
    assert all(q["mapped_story_id"] is None for q in questions)


@pytest.mark.asyncio
async def test_update_and_export_interview_prep(client, override_auth, test_db):
    offer_id = ObjectId()
    db = test_db

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


@pytest.mark.asyncio
async def test_generate_stories_uses_only_current_user_evaluation(client, override_auth, test_db):
    """Une évaluation d'un autre compte sur la même offre ne doit jamais être utilisée."""
    offer_id = ObjectId()
    db = test_db
    await db.candidate_profile.update_one(
        {"user_id": mock_user_id},
        {"$set": {"user_id": mock_user_id, "skills": ["Python"], "experiences": [{"company": "Alpha Corp"}]}},
        upsert=True,
    )
    await db.job_offers.insert_one({"_id": offer_id, "title": "Senior Python", "company": "Alpha Corp"})
    # Inséré en premier : un find_one sans filtre utilisateur le renverrait.
    await db.offer_evaluations.insert_one(
        {"user_id": str(ObjectId()), "offer_id": str(offer_id), "score": 1.0}
    )
    await db.offer_evaluations.insert_one(
        {"user_id": mock_user_id, "offer_id": str(offer_id), "score": 4.5}
    )

    with patch("app.routers.interview_prep.require_user_quota", return_value=True):
        with patch("app.routers.interview_prep.generate_star_stories", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = []
            res = client.post(f"/offers/{str(offer_id)}/interview-prep/generate/stories")

    assert res.status_code == 200
    evaluation = mock_gen.call_args.kwargs["evaluation"]
    assert evaluation["user_id"] == mock_user_id
    assert evaluation["score"] == 4.5


@pytest.mark.asyncio
async def test_cancelled_stories_generation_keeps_existing_stories(client, override_auth, test_db):
    """Le client a annulé pendant l'appel IA : le résultat est jeté, les histoires actuelles restent."""
    offer_id = ObjectId()
    db = test_db
    await db.candidate_profile.update_one(
        {"user_id": mock_user_id},
        {"$set": {"user_id": mock_user_id, "skills": ["Python"], "experiences": [{"company": "Alpha Corp"}]}},
        upsert=True,
    )
    await db.job_offers.insert_one({"_id": offer_id, "title": "Senior Python", "company": "Alpha Corp"})
    kept_story = StarRStory(
        title="Corrigée à la main", theme="T", target_requirement="R",
        situation="S", task="T", action="A", result="R", reflection="R", key_tags=[],
    )
    await db.interview_preps.insert_one({
        "offer_id": str(offer_id),
        "user_id": mock_user_id,
        "stories": [kept_story.model_dump()],
        "anticipated_questions": [],
    })

    new_story = StarRStory(
        title="Nouvelle", theme="T", target_requirement="R",
        situation="S", task="T", action="A", result="R", reflection="R", key_tags=[],
    )
    with patch("app.routers.interview_prep.require_user_quota", return_value=True), \
            patch("app.routers.interview_prep.generate_star_stories", new_callable=AsyncMock) as mock_gen, \
            patch("starlette.requests.Request.is_disconnected", new_callable=AsyncMock, return_value=True):
        mock_gen.return_value = [new_story]
        res = client.post(f"/offers/{str(offer_id)}/interview-prep/generate/stories")

    assert res.status_code == 499
    mock_gen.assert_called_once()
    prep = await db.interview_preps.find_one({"offer_id": str(offer_id), "user_id": mock_user_id})
    assert [s["title"] for s in prep["stories"]] == ["Corrigée à la main"]


@pytest.mark.asyncio
async def test_cancelled_generate_all_stops_before_next_module(client, override_auth, test_db):
    """Tout générer annulé : aucune section suivante n'est générée et rien n'est écrit."""
    offer_id = ObjectId()
    db = test_db
    await db.candidate_profile.update_one(
        {"user_id": mock_user_id},
        {"$set": {"user_id": mock_user_id, "skills": ["Python"], "experiences": [{"company": "Alpha Corp"}]}},
        upsert=True,
    )
    await db.job_offers.insert_one({"_id": offer_id, "title": "Senior Python", "company": "Alpha Corp"})

    with patch("app.routers.interview_prep.require_user_quota", return_value=True), \
            patch("app.routers.interview_prep.generate_star_stories", new_callable=AsyncMock) as mock_stories, \
            patch("app.routers.interview_prep.generate_audience_packs", new_callable=AsyncMock) as mock_packs, \
            patch("app.routers.interview_prep.generate_anticipated_questions", new_callable=AsyncMock) as mock_questions, \
            patch("app.routers.interview_prep.generate_reverse_questions", new_callable=AsyncMock) as mock_reverse, \
            patch("starlette.requests.Request.is_disconnected", new_callable=AsyncMock, return_value=True):
        mock_stories.return_value = []
        mock_packs.return_value = (
            AudiencePackRecruiter(pitch_30s="P"),
            AudiencePackHiringManager(strategic_alignment="S"),
            AudiencePackTechPanel(),
        )
        mock_questions.return_value = []
        mock_reverse.return_value = []
        res = client.post(f"/offers/{str(offer_id)}/interview-prep/generate/all")

    assert res.status_code == 499
    mock_stories.assert_called_once()
    mock_packs.assert_not_called()
    mock_questions.assert_not_called()
    mock_reverse.assert_not_called()
    assert await db.interview_preps.count_documents({"offer_id": str(offer_id)}) == 0


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
    """La question n'existe que dans le kit d'un autre compte : rien n'est noté ni écrit."""
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



def _seeded_attempt(question):
    return PracticeAttempt(
        question_id=question.id, question=question.question, answer="R", overall_score=3.0, improved_answer="V"
    ).model_dump()


@pytest.mark.asyncio
async def test_practice_attempts_cleared_when_questions_regenerated(client, override_auth, test_db):
    """Les nouvelles questions ont de nouveaux id : aucun essai ne doit rester orphelin."""
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
    """Retirer une question à la main efface ses essais et garde ceux des autres."""
    offer_id, _, linked, free = await _seed_practice_prep(test_db)
    await test_db.interview_preps.update_one(
        {"offer_id": str(offer_id), "user_id": mock_user_id},
        {"$set": {"practice_attempts": [_seeded_attempt(linked), _seeded_attempt(free)]}},
    )

    res = client.put(f"/offers/{str(offer_id)}/interview-prep", json={"anticipated_questions": [free.model_dump()]})

    assert res.status_code == 200
    assert [a["question_id"] for a in res.json()["practice_attempts"]] == [free.id]

    # Kit encore inexistant : le $pull ne bloque pas la création.
    fresh = client.put(f"/offers/{str(ObjectId())}/interview-prep", json={"anticipated_questions": [free.model_dump()]})
    assert fresh.status_code == 200
