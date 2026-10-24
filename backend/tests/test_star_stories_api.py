import uuid
from unittest.mock import patch

import pytest
from bson import ObjectId

from app.auth import get_current_user
from app.models import UserModel, utcnow_with_timezone
from main import app

pytestmark = pytest.mark.asyncio

mock_user_id = str(ObjectId())
mock_user = UserModel(
    id=mock_user_id,
    username="starbankcandidate",
    email="starbank@test.com",
    hashed_password="fakehashpassword",
)


@pytest.fixture
def override_auth():
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


def _bank_story(**overrides):
    now = utcnow_with_timezone()
    story = {
        "id": str(uuid.uuid4()),
        "user_id": mock_user_id,
        "title": "Histoire test",
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
    return story


async def _seed_story(db, **overrides):
    story = _bank_story(**overrides)
    await db.star_stories.insert_one(story)
    return story


def _slot(story_id, requirement="Exigence", **overrides):
    slot = {
        "id": str(uuid.uuid4()),
        "requirement": requirement,
        "story_id": story_id,
        "fit": "strong",
        "angle": "",
        "angle_edited": False,
    }
    slot.update(overrides)
    return slot


async def _seed_prep(db, offer_id, slots, questions=()):
    now = utcnow_with_timezone()
    doc = {
        "offer_id": str(offer_id),
        "user_id": mock_user_id,
        "stories": [],
        "story_slots": list(slots),
        "recruiter_pack": None,
        "hm_pack": None,
        "tech_pack": None,
        "anticipated_questions": list(questions),
        "reverse_questions": [],
        "practice_attempts": [],
        "created_at": now,
        "updated_at": now,
    }
    result = await db.interview_preps.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def test_list_groups_by_profile_experience(client, override_auth, test_db):
    await test_db.candidate_profile.update_one(
        {"user_id": mock_user_id},
        {"$set": {"user_id": mock_user_id, "experiences": [{"company": "Alpha Corp", "role": "Data Engineer", "start": "2022-01"}]}},
        upsert=True,
    )
    await _seed_story(test_db, experience={"company": "Alpha Corp", "role": "Data Engineer", "start": None})
    await _seed_story(test_db, experience=None)

    body = client.get("/star-stories").json()
    assert [g["label"] for g in body["groups"]] == ["Data Engineer · Alpha Corp", "Sans expérience rattachée"]
    assert body["count"] == 2


async def test_patch_facts_propagates_to_other_kits_without_llm(client, override_auth, test_db):
    story = await _seed_story(test_db)
    sid = story["id"]
    offer_a, offer_b = str(ObjectId()), str(ObjectId())
    await _seed_prep(test_db, offer_a, [_slot(sid)])
    await _seed_prep(test_db, offer_b, [_slot(sid)])

    with patch("app.services.interview_prep_service.acompletion") as llm:
        res = client.patch(f"/star-stories/{sid}", json={"result": "−45 %"})
        assert res.status_code == 200
        llm.assert_not_called()

    for offer in (offer_a, offer_b):
        data = client.get(f"/offers/{offer}/interview-prep").json()
        assert data["story_slots"][0]["story"]["result"] == "−45 %"


@pytest.mark.parametrize("angle_edited", [False, True])
async def test_patch_number_masks_stale_ai_angle_in_other_kit(client, override_auth, test_db, angle_edited):
    """Un chiffre corrigé dans la banque depuis le kit A : l'angle IA du kit B qui citait
    l'ancien chiffre le masque à la lecture. Un angle écrit à la main reste intact."""
    story = await _seed_story(test_db, result="Coûts réduits de 40 %")
    sid = story["id"]
    angle_b = "Montrer la baisse de 40 % des coûts"
    offer_a, offer_b = str(ObjectId()), str(ObjectId())
    await _seed_prep(test_db, offer_a, [_slot(sid)])
    await _seed_prep(test_db, offer_b, [_slot(sid, angle=angle_b, angle_edited=angle_edited)])

    res = client.patch(f"/star-stories/{sid}", json={"result": "Coûts réduits de 35 %"})
    assert res.status_code == 200

    row = client.get(f"/offers/{offer_b}/interview-prep").json()["story_slots"][0]
    if angle_edited:
        assert row["angle"] == angle_b
    else:
        assert "[à chiffrer]" in row["angle"]
        assert "40" not in row["angle"]
    stored = await test_db.interview_preps.find_one({"offer_id": offer_b, "user_id": mock_user_id})
    assert stored["story_slots"][0]["angle"] == angle_b  # masquage à la lecture, aucune écriture


async def test_patch_explicit_null_is_422_and_writes_nothing(client, override_auth, test_db):
    """`null` explicite sur un fait requis : 422 sans écriture, la banque reste lisible."""
    story = await _seed_story(test_db, title="Titre intact")
    sid = story["id"]

    res = client.patch(f"/star-stories/{sid}", json={"title": None})
    assert res.status_code == 422
    assert res.json()["detail"] == "Champ obligatoire : title."

    listing = client.get("/star-stories")
    assert listing.status_code == 200
    titles = {s["id"]: s["title"] for g in listing.json()["groups"] for s in g["stories"]}
    assert titles[sid] == "Titre intact"

    # Seul `experience` accepte `null` : c'est le détachement d'une expérience.
    assert client.patch(f"/star-stories/{sid}", json={"experience": None}).status_code == 200


async def test_patch_experience_attaches_story(client, override_auth, test_db):
    await test_db.candidate_profile.update_one(
        {"user_id": mock_user_id},
        {"$set": {"user_id": mock_user_id, "experiences": [{"company": "Alpha Corp", "role": "Data Engineer", "start": "2022-01"}]}},
        upsert=True,
    )
    story = await _seed_story(test_db, experience=None)
    sid = story["id"]

    res = client.patch(f"/star-stories/{sid}", json={"experience": {"company": "Alpha Corp", "role": "Data Engineer"}})
    assert res.status_code == 200

    body = client.get("/star-stories").json()
    assert body["groups"][0]["stories"][0]["id"] == sid


async def test_usage_lists_kits(client, override_auth, test_db):
    story = await _seed_story(test_db)
    sid = story["id"]
    offer_a, offer_b = str(ObjectId()), str(ObjectId())
    await test_db.job_offers.insert_one({"_id": ObjectId(offer_a), "poste": "Data Engineer", "entreprise": "Alpha Corp"})
    await test_db.job_offers.insert_one({"_id": ObjectId(offer_b), "poste": "Backend Engineer", "entreprise": "Beta SAS"})
    await _seed_prep(test_db, offer_a, [_slot(sid)])
    await _seed_prep(test_db, offer_b, [_slot(sid)])

    body = client.get(f"/star-stories/{sid}/usage").json()
    assert {k["offer_id"] for k in body["kits"]} == {offer_a, offer_b}


async def test_delete_turns_rows_into_gap_and_unlinks_questions(client, override_auth, test_db):
    story = await _seed_story(test_db)
    sid = story["id"]
    other_story = await _seed_story(test_db)
    other_sid = other_story["id"]

    offer_a, offer_b = str(ObjectId()), str(ObjectId())
    question_id = str(uuid.uuid4())
    questions = [
        {
            "id": question_id,
            "category": "behavioral",
            "question": "Racontez un pilotage difficile.",
            "why_it_will_be_asked": "x",
            "mapped_story_id": sid,
            "key_points_to_cover": [],
        }
    ]
    await _seed_prep(test_db, offer_a, [_slot(sid)], questions=questions)
    await _seed_prep(test_db, offer_b, [_slot(sid)])

    res = client.delete(f"/star-stories/{sid}")
    assert res.json() == {"affected_kits": 2}

    row = client.get(f"/offers/{offer_a}/interview-prep").json()["story_slots"][0]
    assert (row["story_id"], row["fit"], row["angle"], row["story"]) == (None, "gap", "", None)

    prep_a = await test_db.interview_preps.find_one({"offer_id": offer_a, "user_id": mock_user_id})
    assert prep_a["anticipated_questions"][0]["mapped_story_id"] is None

    assert await test_db.star_stories.count_documents({"id": other_sid}) == 1


async def test_delete_counts_kits_referenced_only_by_questions(client, override_auth, test_db):
    """Une question peut rester mappée à une histoire dont la ligne a déjà été retirée
    du kit (DELETE slot ne touche pas aux questions) : ce kit doit quand même être
    détecté et compté par DELETE /star-stories/{id}."""
    story = await _seed_story(test_db)
    sid = story["id"]
    other_story = await _seed_story(test_db)
    other_sid = other_story["id"]

    def _question(mapped_story_id):
        return {
            "id": str(uuid.uuid4()),
            "category": "behavioral",
            "question": "Racontez un pilotage difficile.",
            "why_it_will_be_asked": "x",
            "mapped_story_id": mapped_story_id,
            "key_points_to_cover": [],
        }

    # Ligne déjà supprimée (plus aucun story_slot vers sid), question encore mappée.
    offer_question_only = str(ObjectId())
    await _seed_prep(test_db, offer_question_only, [], questions=[_question(sid)])

    # Référencée des deux côtés : ne doit compter qu'une fois.
    offer_both = str(ObjectId())
    await _seed_prep(test_db, offer_both, [_slot(sid)], questions=[_question(sid)])

    # Kit témoin, sans rapport avec sid : ne doit pas être compté.
    offer_unrelated = str(ObjectId())
    await _seed_prep(test_db, offer_unrelated, [_slot(other_sid)], questions=[_question(other_sid)])

    res = client.delete(f"/star-stories/{sid}")
    assert res.json() == {"affected_kits": 2}

    prep_question_only = await test_db.interview_preps.find_one({"offer_id": offer_question_only, "user_id": mock_user_id})
    assert prep_question_only["anticipated_questions"][0]["mapped_story_id"] is None

    prep_both = await test_db.interview_preps.find_one({"offer_id": offer_both, "user_id": mock_user_id})
    assert prep_both["anticipated_questions"][0]["mapped_story_id"] is None
    row = prep_both["story_slots"][0]
    assert (row["story_id"], row["fit"], row["angle"], row["angle_edited"]) == (None, "gap", "", False)

    prep_unrelated = await test_db.interview_preps.find_one({"offer_id": offer_unrelated, "user_id": mock_user_id})
    assert prep_unrelated["anticipated_questions"][0]["mapped_story_id"] == other_sid


async def test_other_users_story_is_404_everywhere(client, override_auth, test_db):
    foreign_uid = str(ObjectId())
    foreign_story = await _seed_story(test_db, user_id=foreign_uid, result="original")
    foreign = foreign_story["id"]

    offer_a = str(ObjectId())
    slot_id = str(uuid.uuid4())
    await _seed_prep(test_db, offer_a, [_slot(None, requirement="Exigence", id=slot_id, fit="gap")])

    assert client.patch(f"/star-stories/{foreign}", json={"result": "x"}).status_code == 404
    assert client.get(f"/star-stories/{foreign}/usage").status_code == 404
    assert client.delete(f"/star-stories/{foreign}").status_code == 404
    assert client.put(f"/offers/{offer_a}/interview-prep/slots/{slot_id}", json={"story_id": foreign}).status_code == 404
    assert (await test_db.star_stories.find_one({"id": foreign}))["result"] != "x"


async def test_put_slot_story_sets_manual_and_resets_angle(client, override_auth, test_db):
    story2 = await _seed_story(test_db)
    sid2 = story2["id"]
    offer_a = str(ObjectId())
    slot_id = str(uuid.uuid4())
    await _seed_prep(
        test_db,
        offer_a,
        [_slot(None, requirement="Exigence", id=slot_id, fit="gap", angle="ancien angle", angle_edited=True)],
    )

    res = client.put(f"/offers/{offer_a}/interview-prep/slots/{slot_id}", json={"story_id": sid2})
    row = res.json()["story_slots"][0]
    assert (row["story_id"], row["fit"], row["angle"], row["angle_edited"]) == (sid2, "manual", "", False)


async def test_put_slot_angle_and_requirement_touch_only_the_row(client, override_auth, test_db):
    story = await _seed_story(test_db)
    sid = story["id"]
    offer_a = str(ObjectId())
    slot_id = str(uuid.uuid4())
    await _seed_prep(test_db, offer_a, [_slot(sid, requirement="Exigence initiale", id=slot_id)])

    story_before = await test_db.star_stories.find_one({"id": sid})

    res = client.put(
        f"/offers/{offer_a}/interview-prep/slots/{slot_id}",
        json={"angle": "Coordination", "requirement": "Piloter 5 personnes"},
    )
    row = res.json()["story_slots"][0]
    assert (row["angle"], row["angle_edited"], row["requirement"]) == ("Coordination", True, "Piloter 5 personnes")

    story_after = await test_db.star_stories.find_one({"id": sid})
    assert story_after["updated_at"] == story_before["updated_at"]


async def test_delete_slot_keeps_bank_story(client, override_auth, test_db):
    story = await _seed_story(test_db)
    sid = story["id"]
    offer_a = str(ObjectId())
    slot_id = str(uuid.uuid4())
    await _seed_prep(test_db, offer_a, [_slot(sid, id=slot_id)])

    res = client.delete(f"/offers/{offer_a}/interview-prep/slots/{slot_id}")
    assert res.json()["story_slots"] == []
    assert await test_db.star_stories.count_documents({"id": sid}) == 1


async def _seed_duplicate_scenario(test_db):
    """Deux histoires quasi identiques (même titre, même entreprise unique à cet
    appel pour ne jamais se faire apparier avec les restes d'un autre test dans
    cette base partagée sans nettoyage entre tests) : `a` ("−60 %") dans kit1
    seul, `b` ("−45 %") dans kit1 et kit2 (avec une question mappée vers `b`
    dans kit2)."""
    company = f"Corp {uuid.uuid4().hex[:8]}"
    experience = {"company": company, "role": None, "start": None}
    a = (await _seed_story(test_db, title="Migration pipeline facturation", result="−60 %", experience=experience))["id"]
    b = (await _seed_story(test_db, title="Migration pipeline facturation", result="−45 %", experience=experience))["id"]
    offer1, offer2 = str(ObjectId()), str(ObjectId())
    question_id = str(uuid.uuid4())
    await _seed_prep(test_db, offer1, [_slot(a), _slot(b)])
    await _seed_prep(
        test_db,
        offer2,
        [_slot(b)],
        questions=[
            {
                "id": question_id,
                "category": "behavioral",
                "question": "Racontez un pilotage difficile.",
                "why_it_will_be_asked": "x",
                "mapped_story_id": b,
                "key_points_to_cover": [],
            }
        ],
    )
    return a, b, offer1, offer2


async def test_merge_moves_discarded_facts_and_redirects(client, override_auth, test_db):
    a, b, offer1, offer2 = await _seed_duplicate_scenario(test_db)

    kept = client.post(f"/star-stories/{a}/merge", json={"discard_id": b}).json()
    assert kept["discarded_versions"][0]["facts"]["result"] == "−45 %"
    assert kept["discarded_versions"][0]["source_story_id"] == b
    assert await test_db.star_stories.count_documents({"id": b}) == 0

    kit2 = client.get(f"/offers/{offer2}/interview-prep").json()
    assert kit2["story_slots"][0]["story_id"] == a
    assert kit2["anticipated_questions"][0]["mapped_story_id"] == a


async def test_merge_same_id_is_400(client, override_auth, test_db):
    a, _b, _offer1, _offer2 = await _seed_duplicate_scenario(test_db)
    assert client.post(f"/star-stories/{a}/merge", json={"discard_id": a}).status_code == 400


async def test_merge_twice_is_404_and_keeps_data(client, override_auth, test_db):
    a, b, _offer1, _offer2 = await _seed_duplicate_scenario(test_db)

    client.post(f"/star-stories/{a}/merge", json={"discard_id": b})
    assert client.post(f"/star-stories/{a}/merge", json={"discard_id": b}).status_code == 404
    assert len((await test_db.star_stories.find_one({"id": a}))["discarded_versions"]) == 1


async def test_merge_kit_holding_both_points_both_rows_to_kept(client, override_auth, test_db):
    a, b, offer1, _offer2 = await _seed_duplicate_scenario(test_db)

    client.post(f"/star-stories/{a}/merge", json={"discard_id": b})
    assert [r["story_id"] for r in client.get(f"/offers/{offer1}/interview-prep").json()["story_slots"]] == [a, a]


async def test_not_duplicate_hides_pair(client, override_auth, test_db):
    a, b, offer1, _offer2 = await _seed_duplicate_scenario(test_db)

    assert client.get(f"/offers/{offer1}/interview-prep").json()["duplicates"] != []
    client.post(f"/star-stories/{a}/not-duplicate", json={"other_id": b})
    assert client.get(f"/offers/{offer1}/interview-prep").json()["duplicates"] == []


async def test_not_duplicate_same_id_is_400(client, override_auth, test_db):
    a, _b, _offer1, _offer2 = await _seed_duplicate_scenario(test_db)
    assert client.post(f"/star-stories/{a}/not-duplicate", json={"other_id": a}).status_code == 400


async def test_restore_discarded_version_swaps_facts(client, override_auth, test_db):
    a, b, _offer1, _offer2 = await _seed_duplicate_scenario(test_db)

    kept = client.post(f"/star-stories/{a}/merge", json={"discard_id": b}).json()
    vid = kept["discarded_versions"][0]["id"]
    restored = client.post(f"/star-stories/{a}/restore", json={"version_id": vid}).json()
    assert restored["result"] == "−45 %"
    assert [v["facts"]["result"] for v in restored["discarded_versions"]] == ["−60 %"]


async def test_merge_foreign_story_is_404(client, override_auth, test_db):
    a, _b, _offer1, _offer2 = await _seed_duplicate_scenario(test_db)
    foreign_uid = str(ObjectId())
    foreign = (await _seed_story(test_db, user_id=foreign_uid))["id"]
    assert client.post(f"/star-stories/{a}/merge", json={"discard_id": foreign}).status_code == 404


async def test_restore_unknown_version_is_404(client, override_auth, test_db):
    story = await _seed_story(test_db)
    sid = story["id"]
    assert client.post(f"/star-stories/{sid}/restore", json={"version_id": str(uuid.uuid4())}).status_code == 404
