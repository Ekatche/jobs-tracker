import uuid

import pytest
from bson import ObjectId

from app.models import utcnow_with_timezone
from app.services.star_bank import (
    ensure_prep_migrated,
    get_bank_story,
    hydrate_prep,
    load_bank,
)

pytestmark = pytest.mark.asyncio


def _legacy_story(**overrides):
    story = {
        "id": str(uuid.uuid4()),
        "title": "Histoire test",
        "theme": "Général",
        "target_requirement": "Exigence",
        "situation": "Situation",
        "task": "Tâche",
        "action": "Action",
        "result": "Résultat",
        "reflection": "",
        "key_tags": [],
    }
    story.update(overrides)
    return story


async def _seed_prep(db, user_id, offer_id, stories, questions=()):
    now = utcnow_with_timezone()
    doc = {
        "offer_id": str(offer_id),
        "user_id": str(user_id),
        "stories": list(stories),
        "recruiter_pack": None,
        "hm_pack": None,
        "tech_pack": None,
        "anticipated_questions": list(questions),
        "reverse_questions": [],
        "practice_attempts": [],
        "created_at": now,
        "updated_at": now,
    }
    result = await db["interview_preps"].insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def test_migration_keeps_ids_and_creates_slots(test_db):
    uid = str(ObjectId())
    oid = str(ObjectId())
    s1 = _legacy_story(target_requirement="Piloter", situation="Chez Alpha Corp, le pipeline était lent.")
    s2 = _legacy_story(target_requirement="Fiabiliser", situation="Chez Beta SAS, les tests manquaient.")
    questions = [
        {
            "id": str(uuid.uuid4()),
            "category": "behavioral",
            "question": "Racontez un pilotage difficile.",
            "why_it_will_be_asked": "x",
            "mapped_story_id": s1["id"],
            "key_points_to_cover": [],
        }
    ]
    seeded = await _seed_prep(test_db, uid, oid, [s1, s2], questions)

    prep = await ensure_prep_migrated(test_db, seeded)

    bank_ids = {s.id for s in await load_bank(test_db, uid)}
    assert bank_ids == {s1["id"], s2["id"]}
    assert [(s["requirement"], s["story_id"], s["fit"], s["angle"]) for s in prep["story_slots"]] == [
        ("Piloter", s1["id"], "strong", ""),
        ("Fiabiliser", s2["id"], "strong", ""),
    ]
    stored = await test_db.interview_preps.find_one({"_id": seeded["_id"]})
    assert stored["stories"] == seeded["stories"]  # copie de sûreté intacte
    assert stored["anticipated_questions"][0]["mapped_story_id"] == s1["id"]
    assert (await get_bank_story(test_db, uid, s1["id"])).origin.kind == "migrated"


async def test_migration_is_idempotent(test_db):
    uid = str(ObjectId())
    oid = str(ObjectId())
    s1 = _legacy_story()
    s2 = _legacy_story()
    seeded = await _seed_prep(test_db, uid, oid, [s1, s2])

    await ensure_prep_migrated(test_db, seeded)
    again = await test_db.interview_preps.find_one({"_id": seeded["_id"]})
    await ensure_prep_migrated(test_db, again)

    assert await test_db.star_stories.count_documents({"user_id": uid}) == 2
    assert len((await test_db.interview_preps.find_one({"_id": seeded["_id"]}))["story_slots"]) == 2


async def test_migration_tolerates_legacy_story_without_id_or_optional_fields(test_db):
    uid = str(ObjectId())
    oid = str(ObjectId())
    legacy = {"title": "Ancienne", "situation": "S", "task": "T", "action": "A", "result": "R"}
    # ni id, ni theme, ni reflection, ni key_tags

    prep = await ensure_prep_migrated(test_db, await _seed_prep(test_db, uid, oid, [legacy]))

    assert len(prep["story_slots"]) == 1 and prep["story_slots"][0]["story_id"]
    story = await get_bank_story(test_db, uid, prep["story_slots"][0]["story_id"])
    assert (story.theme, story.reflection, story.key_tags) == ("Général", "", [])


async def test_migration_attaches_experience_from_situation(test_db):
    uid = str(ObjectId())
    oid = str(ObjectId())
    await test_db.candidate_profile.insert_one(
        {
            "user_id": uid,
            "experiences": [{"company": "Alpha Corp", "role": "Data Engineer", "start": "2022-01"}],
        }
    )
    legacy = _legacy_story(situation="Chez Alpha Corp, le pipeline était lent.")

    prep = await ensure_prep_migrated(test_db, await _seed_prep(test_db, uid, oid, [legacy]))

    story = await get_bank_story(test_db, uid, prep["story_slots"][0]["story_id"])
    assert story.experience.company == "Alpha Corp"


async def test_hydrate_joins_facts_and_counts_kits(test_db):
    uid = str(ObjectId())
    oid_a = str(ObjectId())
    oid_b = str(ObjectId())
    s1 = _legacy_story(result="−60 %")
    seeded_a = await _seed_prep(test_db, uid, oid_a, [s1])
    prep_a = await ensure_prep_migrated(test_db, seeded_a)
    shared_story_id = prep_a["story_slots"][0]["story_id"]

    # Deuxième kit déjà migré dont la ligne pointe vers la même histoire.
    second_doc = await _seed_prep(test_db, uid, oid_b, [])
    await test_db.interview_preps.update_one(
        {"_id": second_doc["_id"]},
        {
            "$set": {
                "story_slots": [
                    {
                        "id": str(uuid.uuid4()),
                        "requirement": "Autre exigence",
                        "story_id": shared_story_id,
                        "fit": "strong",
                        "angle": "",
                        "angle_edited": False,
                    }
                ]
            }
        },
    )

    hydrated = await hydrate_prep(test_db, prep_a, uid)
    row = hydrated["story_slots"][0]
    assert row["story"]["result"] == "−60 %" and row["story"]["used_in_kits"] == 2
    assert hydrated["bank_count"] == 1
    assert hydrated["duplicates"] == []


async def test_hydrate_hides_other_users_story(test_db):
    uid = str(ObjectId())
    other_uid = str(ObjectId())
    story_id = str(uuid.uuid4())
    now = utcnow_with_timezone()
    await test_db.star_stories.insert_one(
        {
            "id": story_id,
            "user_id": other_uid,
            "title": "Histoire d'un autre",
            "theme": "Général",
            "situation": "S",
            "task": "T",
            "action": "A",
            "result": "R",
            "reflection": "",
            "key_tags": [],
            "experience": None,
            "origin": {"kind": "migrated", "offer_id": None},
            "discarded_versions": [],
            "not_duplicate_of": [],
            "created_at": now,
            "updated_at": now,
        }
    )
    prep = {
        "story_slots": [
            {
                "id": str(uuid.uuid4()),
                "requirement": "Exigence",
                "story_id": story_id,
                "fit": "strong",
                "angle": "",
                "angle_edited": False,
            }
        ]
    }

    hydrated = await hydrate_prep(test_db, prep, uid)
    assert hydrated["story_slots"][0]["story"] is None
