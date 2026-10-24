import uuid

import pytest
from bson import ObjectId

from app.models import utcnow_with_timezone
from migrate_star_stories_to_bank import (
    MigrationInvariantError,
    check_invariant,
    migrate,
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


async def _seed_prep(db, user_id, offer_id, stories):
    now = utcnow_with_timezone()
    doc = {
        "offer_id": str(offer_id),
        "user_id": str(user_id),
        "stories": list(stories),
        "recruiter_pack": None,
        "hm_pack": None,
        "tech_pack": None,
        "anticipated_questions": [],
        "reverse_questions": [],
        "practice_attempts": [],
        "created_at": now,
        "updated_at": now,
    }
    result = await db["interview_preps"].insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def test_dry_run_writes_nothing(test_db):
    uid = str(ObjectId())
    oid = str(ObjectId())
    prep = await _seed_prep(test_db, uid, oid, [_legacy_story(), _legacy_story()])

    report = await migrate(test_db, apply=False)

    assert report[uid]["kits_to_migrate"] == 1
    assert report[uid]["kit_stories"] == 2
    assert await test_db.star_stories.count_documents({"user_id": uid}) == 0
    stored = await test_db.interview_preps.find_one({"_id": prep["_id"]})
    assert "story_slots" not in stored


async def test_apply_migrates_and_reports(test_db):
    uid = str(ObjectId())
    oid = str(ObjectId())
    await _seed_prep(test_db, uid, oid, [_legacy_story(), _legacy_story()])

    report = await migrate(test_db, apply=True)

    assert (
        report[uid]["kits_to_migrate"],
        report[uid]["bank_stories"],
        report[uid]["kits_with_slots"],
    ) == (1, 2, 1)
    # Les deux histoires migrées sont `_legacy_story()` sans override : même
    # titre "Histoire test", aucune entreprise -> `find_duplicate_pairs` les
    # détecte à raison comme une paire possible (Task 4, pencher vers
    # « proposer plus »). Avant le câblage de `possible_duplicates` sur la
    # vraie heuristique, ce champ était figé à 0 ; ce test vérifiait alors un
    # placeholder, pas un comportement.
    assert report[uid]["possible_duplicates"] == 1


async def test_apply_twice_creates_nothing_more(test_db):
    uid = str(ObjectId())
    oid = str(ObjectId())
    await _seed_prep(test_db, uid, oid, [_legacy_story(), _legacy_story()])

    await migrate(test_db, apply=True)
    second = await migrate(test_db, apply=True)

    assert second[uid]["bank_stories"] == 2
    assert second[uid]["kits_to_migrate"] == 0


async def test_check_invariant_raises_when_story_missing_from_bank(test_db):
    uid = str(ObjectId())
    oid = str(ObjectId())
    story_id = str(uuid.uuid4())
    prep = await _seed_prep(test_db, uid, oid, [_legacy_story(id=story_id)])
    await test_db.interview_preps.update_one(
        {"_id": prep["_id"]},
        {
            "$set": {
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
        },
    )
    stored = await test_db.interview_preps.find_one({"_id": prep["_id"]})

    with pytest.raises(MigrationInvariantError):
        await check_invariant(test_db, [stored])


async def test_check_invariant_checks_legacy_id_not_slot_story_id(test_db):
    """Régression : une ligne peut pointer vers une histoire présente dans la
    banque tout en laissant orpheline l'id de l'histoire héritée d'origine
    (celle que `mapped_story_id` des questions anticipées référence). Si
    `check_invariant` comparait `story_slots[].story_id` à lui-même via la
    banque, ce cas tautologique passerait à tort."""
    uid = str(ObjectId())
    oid = str(ObjectId())
    legacy_id = str(uuid.uuid4())  # jamais entré dans la banque
    bank_story_id = str(uuid.uuid4())  # présent dans la banque, id différent
    now = utcnow_with_timezone()
    await test_db.star_stories.insert_one(
        {
            "id": bank_story_id,
            "user_id": uid,
            "title": "Histoire en banque",
            "theme": "Général",
            "situation": "S",
            "task": "T",
            "action": "A",
            "result": "R",
            "reflection": "",
            "key_tags": [],
            "experience": None,
            "origin": {"kind": "migrated", "offer_id": oid},
            "discarded_versions": [],
            "not_duplicate_of": [],
            "created_at": now,
            "updated_at": now,
        }
    )
    prep = await _seed_prep(test_db, uid, oid, [_legacy_story(id=legacy_id)])
    await test_db.interview_preps.update_one(
        {"_id": prep["_id"]},
        {
            "$set": {
                "story_slots": [
                    {
                        "id": str(uuid.uuid4()),
                        "requirement": "Exigence",
                        "story_id": bank_story_id,
                        "fit": "strong",
                        "angle": "",
                        "angle_edited": False,
                    }
                ]
            }
        },
    )
    stored = await test_db.interview_preps.find_one({"_id": prep["_id"]})

    with pytest.raises(MigrationInvariantError):
        await check_invariant(test_db, [stored])
