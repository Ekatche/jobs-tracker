import uuid

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
    BankStory,
    PracticeAttempt,
    StoryFacts,
    StoryOrigin,
    StorySlot,
    UserModel,
    utcnow_with_timezone,
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


async def _seed_bank_story(db, **overrides):
    """Insère une histoire de la banque directement en base ; renvoie son dict brut."""
    now = utcnow_with_timezone()
    story = {
        "id": str(uuid.uuid4()),
        "user_id": mock_user_id,
        "title": "Histoire banque",
        "theme": "Général",
        "situation": "S",
        "task": "T",
        "action": "A",
        "result": "R",
        "reflection": "",
        "key_tags": [],
        "experience": None,
        "origin": {"kind": "manual", "offer_id": None},
        "discarded_versions": [],
        "not_duplicate_of": [],
        "created_at": now,
        "updated_at": now,
    }
    story.update(overrides)
    await db.star_stories.insert_one(story)
    return story


def _slot_dict(story_id, requirement="Exigence", slot_id=None, fit="strong", **overrides):
    """Une ligne `story_slots` brute, prête à être insérée dans `interview_preps`."""
    slot = {
        "id": slot_id or str(uuid.uuid4()),
        "requirement": requirement,
        "story_id": story_id,
        "fit": fit,
        "angle": "",
        "angle_edited": False,
    }
    slot.update(overrides)
    return slot


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


def _bank_story_model(offer_id, **overrides):
    defaults = dict(
        user_id=mock_user_id,
        title="Histoire",
        situation="S",
        task="T",
        action="A",
        result="R",
        origin=StoryOrigin(kind="generated", offer_id=str(offer_id)),
    )
    defaults.update(overrides)
    return BankStory(**defaults)


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

    new_story = _bank_story_model(offer_id, title="[Scalabilité] Pipeline")
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

    new_story = _bank_story_model(offer_id, title="Nouvelle")
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
    """Un kit jamais rouvert depuis le déploiement, régénéré directement : ses histoires
    d'origine entrent dans la banque avant que ses lignes soient remplacées."""
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

    new_story = _bank_story_model(offer_id, title="Fraîche")
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
    """Régénérer un kit déjà migré n'efface jamais une histoire de la banque."""
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

    n1 = _bank_story_model(offer_id, title="N1")
    new_slot = StorySlot(requirement="R1", story_id=n1.id, fit="strong")

    with patch("app.routers.interview_prep.require_user_quota", return_value=True):
        with patch("app.routers.interview_prep.build_story_slots", new_callable=AsyncMock) as mock_build:
            mock_build.return_value = ([new_slot], [n1])
            res = client.post(f"/offers/{str(offer_id)}/interview-prep/generate/stories")

    assert res.status_code == 200
    assert await db.star_stories.count_documents({"id": s1["id"]}) == 1
    assert await db.star_stories.count_documents({"id": n1.id}) == 1


@pytest.mark.asyncio
async def test_generate_cancelled_writes_nothing(client, override_auth, test_db):
    """Le client annule pendant l'appel IA : aucune histoire ni ligne n'est écrite."""
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

    n1 = _bank_story_model(offer_id, title="N1")
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
async def test_update_and_export_interview_prep(client, override_auth, test_db):
    """Le PUT ne porte plus `stories` ; l'export restitue l'exigence et le résultat d'une ligne du kit."""
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
    """La route questions passe au service les histoires des lignes du kit, dans l'ordre, sans doublon ni trou."""
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
    """Deux lignes du kit pointant vers la même histoire ne doivent compter qu'une fois."""
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
    assert [s.id for s in mock_q.await_args.kwargs["stories"]] == [s1["id"]]


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
    """Appelées sur une offre sans kit existant, les trois routes de génération doivent
    insérer `story_slots: []` via `$setOnInsert` — jamais l'ancien champ `stories`."""
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
        with patch("app.routers.interview_prep.build_story_slots", new_callable=AsyncMock) as mock_build:
            mock_build.return_value = ([], [])
            res = client.post(f"/offers/{str(offer_id)}/interview-prep/generate/stories")

    assert res.status_code == 200
    evaluation = mock_build.call_args.kwargs["evaluation"]
    assert evaluation["user_id"] == mock_user_id
    assert evaluation["score"] == 4.5


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
    """`generate/all` écrit `story_slots` sans jamais toucher à la copie de sûreté `stories`."""
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

    n1 = _bank_story_model(offer_id, title="N1")
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
async def test_write_slot_only_on_gap(client, override_auth, test_db):
    """Écrire une histoire sur une ligne qui n'est pas en manque renvoie 409."""
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
    """Écrire une histoire sur une ligne en manque l'ajoute à la banque et met à jour la ligne."""
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

    n1 = _bank_story_model(offer_id, title="N1")
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
    """Ajouter une histoire manuelle sur une ligne `no_experience` sans appel IA, avec origin manual."""
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
async def test_write_slot_keeps_concurrent_edit_of_other_row(client, override_auth, test_db):
    """Pendant l'appel IA, l'angle d'une autre ligne est modifié à la main : l'écriture ne
    met à jour que sa propre ligne, sans réécrire l'instantané lu avant l'appel."""
    s1 = await _seed_bank_story(test_db, title="S1")
    other_slot = _slot_dict(s1["id"], requirement="R2", angle="Angle IA")
    offer_id, prep_id, gap_slot = await _seed_write_scenario(test_db, extra_slots=[other_slot])

    n1 = _bank_story_model(offer_id, title="N1")
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
    """La ligne visée est supprimée ou reçoit une histoire pendant l'appel IA : 409, la
    modification concurrente est conservée et l'histoire écrite reste dans la banque."""
    chosen = await _seed_bank_story(test_db, title="Choisie")
    offer_id, prep_id, gap_slot = await _seed_write_scenario(test_db)

    n1 = _bank_story_model(offer_id, title="N1")
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
    """Ligne supprimée pendant un appel IA qui n'a écrit aucune histoire : 409 au détail court."""
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
    """Une autre ligne supprimée pendant l'appel IA ne réapparaît pas après l'écriture."""
    s1 = await _seed_bank_story(test_db, title="S1")
    other_slot = _slot_dict(s1["id"], requirement="R2")
    offer_id, prep_id, gap_slot = await _seed_write_scenario(test_db, extra_slots=[other_slot])

    n1 = _bank_story_model(offer_id, title="N1")
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
    """Détacher l'histoire d'une ligne (`story_id: null`) la remet en manque : l'écriture IA l'accepte."""
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

    n1 = _bank_story_model(offer_id, title="N1")
    new_slot = StorySlot(id=strong_slot["id"], requirement="R2", story_id=n1.id, fit="strong")
    with patch("app.routers.interview_prep.require_user_quota", return_value=True), \
            patch("app.routers.interview_prep.write_stories_for_requirements", new_callable=AsyncMock) as mock_write:
        mock_write.return_value = [(new_slot, n1)]
        write_res = client.post(f"/offers/{str(offer_id)}/interview-prep/slots/{strong_slot['id']}/write")

    assert write_res.status_code == 200


@pytest.mark.asyncio
async def test_generate_stories_turns_row_of_story_deleted_meanwhile_into_gap(client, override_auth, test_db):
    """Une histoire de la banque supprimée pendant l'appel IA ne laisse pas de référence
    pendante : la nouvelle ligne qui la pointait passe en manque."""
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
            patch("app.routers.interview_prep.build_story_slots", new_callable=AsyncMock) as mock_build:
        mock_build.side_effect = _delete_story_during_llm
        res = client.post(f"/offers/{str(offer_id)}/interview-prep/generate/stories")

    assert res.status_code == 200
    stored = await db.interview_preps.find_one({"_id": insert_result.inserted_id})
    row = stored["story_slots"][0]
    assert (row["story_id"], row["fit"], row["angle"], row["angle_edited"]) == (None, "gap", "", False)


@pytest.mark.asyncio
async def test_generate_stories_rereads_questions_after_llm(client, override_auth, test_db):
    """Une question redirigée pendant l'appel IA (fusion d'histoires) garde sa nouvelle cible :
    les questions sont relues après l'appel, pas reprises de l'instantané d'avant."""
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

    with patch("app.routers.interview_prep.require_user_quota", return_value=True), \
            patch("app.routers.interview_prep.build_story_slots", new_callable=AsyncMock) as mock_build:
        mock_build.side_effect = _redirect_question_during_llm
        res = client.post(f"/offers/{str(offer_id)}/interview-prep/generate/stories")

    assert res.status_code == 200
    stored = await db.interview_preps.find_one({"_id": insert_result.inserted_id})
    assert stored["anticipated_questions"][0]["mapped_story_id"] == kept["id"]


@pytest.mark.asyncio
async def test_generate_all_turns_row_of_story_deleted_meanwhile_into_gap(client, override_auth, test_db):
    """Même garde que generate/stories pour « Tout générer » : aucune ligne écrite ne pointe
    vers une histoire supprimée de la banque pendant la génération."""
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
async def test_practice_reads_up_to_date_facts_from_bank(client, override_auth, test_db):
    """practice lit l'histoire par `get_bank_story` : un fait corrigé dans la banque après
    la génération des questions est pris en compte, sans régénérer le kit."""
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
