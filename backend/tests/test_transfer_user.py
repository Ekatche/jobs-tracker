"""Transfert d'un compte (par email) d'une base Mongo vers une autre :
`scripts/transfer_user.py`. Deux bases temporaires (source, cible) créées et
supprimées par test, jamais la base de test partagée."""

import uuid
from datetime import datetime, timezone

import motor.motor_asyncio
import pytest
from bson import ObjectId
from conftest import DATABASE_NAME, MONGO_URI

from scripts.transfer_user import TransferError, dump_bundle, export_user, import_user, load_bundle, remap_ids

EMAIL = "candidate@example.test"


@pytest.fixture
async def src_dst():
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
    suffix = uuid.uuid4().hex[:8]
    names = (f"{DATABASE_NAME}_xfer_src_{suffix}", f"{DATABASE_NAME}_xfer_dst_{suffix}")
    try:
        yield client[names[0]], client[names[1]]
    finally:
        for name in names:
            await client.drop_database(name)
        client.close()


async def _seed_source(src) -> dict:
    """Un compte complet côté source ; renvoie les identifiants utiles aux assertions."""
    user_id = ObjectId()
    user_str = str(user_id)
    offer_applied = ObjectId()
    offer_seen = ObjectId()
    offer_same_key = ObjectId()
    offer_matched = ObjectId()
    offer_unrelated = ObjectId()
    application_id = ObjectId()

    await src.users.insert_one(
        {
            "_id": user_id,
            "username": "candidate",
            "email": EMAIL,
            "full_name": "Candidate Test",
            "hashed_password": "source-hash",
            "role": "admin",
            "cv_url": f"/uploads/cv_{user_str}_abc.pdf",
            "onboarding_completed": True,
            "disabled": True,
            "created_at": datetime(2026, 9, 1, tzinfo=timezone.utc),
        }
    )
    await src.job_offers.insert_many(
        [
            {
                "_id": offer_applied,
                "url": "https://example.test/applied",
                "poste": "Data Analyst",
                "matched_user_ids": [user_str, "someone-else"],
                "evaluation_score": 4.2,
            },
            {"_id": offer_seen, "url": "https://example.test/seen", "poste": "Data Engineer"},
            {
                "_id": offer_same_key,
                "url": "https://example.test/same-key-source",
                "unique_key": "acme|data scientist|lyon",
            },
            {"_id": offer_matched, "url": "https://example.test/matched", "matched_user_ids": [user_str]},
            {"_id": offer_unrelated, "url": "https://example.test/unrelated", "matched_user_ids": ["someone-else"]},
        ]
    )
    await src.candidate_profile.insert_one(
        {"user_id": user_id, "preferences": {"target_roles": ["Data Analyst"], "locations": ["Lyon"]}}
    )
    await src.applications.insert_one(
        {"_id": application_id, "user_id": user_str, "offer_id": str(offer_applied), "status": "applied"}
    )
    await src.cover_letters.insert_one({"user_id": user_id, "application_id": application_id, "content": "Lettre"})
    await src.tailored_resumes.insert_one(
        {"user_id": user_id, "offer_id": offer_applied, "application_id": application_id}
    )
    await src.star_stories.insert_one(
        {"id": "story-uuid-1", "user_id": user_str, "origin": {"offer_id": str(offer_applied)}}
    )
    await src.user_offer_interactions.insert_many(
        [
            {"user_id": user_str, "offer_id": str(offer_seen), "status": "saved"},
            {"user_id": user_str, "offer_id": str(offer_same_key), "status": "saved"},
        ]
    )
    await src.api_usage.insert_one({"user_id": user_str, "action": "evaluation", "tokens": 10})

    return {
        "user_id": user_id,
        "application_id": application_id,
        "offer_applied": offer_applied,
        "offer_matched": offer_matched,
        "offer_unrelated": offer_unrelated,
    }


async def _roundtrip(src, email=EMAIL) -> dict:
    """Export puis passage par le fichier JSON, comme entre les deux machines."""
    return load_bundle(dump_bundle(await export_user(src, email)))


def test_remap_ids_keeps_each_field_type_and_walks_nested_values():
    old, new, other = ObjectId(), ObjectId(), ObjectId()
    doc = {
        "as_oid": old,
        "as_str": str(old),
        "nested": [{"deep": old}],
        "text": "texte libre",
        "other": other,
        str(old): "clé",
    }

    result = remap_ids(doc, {str(old): str(new)})

    assert result["as_oid"] == new and isinstance(result["as_oid"], ObjectId)
    assert result["as_str"] == str(new) and isinstance(result["as_str"], str)
    assert result["nested"][0]["deep"] == new
    assert result["text"] == "texte libre"
    assert result["other"] == other
    assert result[str(new)] == "clé" and str(old) not in result


async def test_transfer_copies_user_data_with_new_ids_and_consistent_references(src_dst):
    src, dst = src_dst
    ids = await _seed_source(src)
    existing_seen = ObjectId()
    existing_same_key = ObjectId()
    await dst.job_offers.insert_many(
        [
            {"_id": existing_seen, "url": "https://example.test/seen"},
            {"_id": existing_same_key, "url": "https://example.test/other", "unique_key": "acme|data scientist|lyon"},
        ]
    )

    summary = await import_user(dst, await _roundtrip(src), apply=True, password_hash="hash-from-prompt")

    user = await dst.users.find_one({"email": EMAIL})
    new_id = user["_id"]
    new_str = str(new_id)
    assert new_id != ids["user_id"]
    assert summary.new_user_id == new_str
    assert user["hashed_password"] == "hash-from-prompt"
    assert user["disabled"] is False
    assert user["onboarding_completed"] is True
    assert "role" not in user and "cv_url" not in user

    profile = await dst.candidate_profile.find_one({"user_id": new_id})
    assert profile["preferences"]["locations"] == ["Lyon"]

    application = await dst.applications.find_one({"user_id": new_str})
    assert application["_id"] != ids["application_id"]
    assert application["offer_id"] == str(ids["offer_applied"])

    letter = await dst.cover_letters.find_one({"user_id": new_id})
    assert letter["application_id"] == application["_id"]

    resume = await dst.tailored_resumes.find_one({"user_id": new_id})
    assert resume["offer_id"] == ids["offer_applied"]
    assert resume["application_id"] == application["_id"]

    story = await dst.star_stories.find_one({"user_id": new_str})
    assert story["id"] == "story-uuid-1"
    assert story["origin"]["offer_id"] == str(ids["offer_applied"])

    interactions = await dst.user_offer_interactions.find({"user_id": new_str}).to_list(length=None)
    assert {doc["offer_id"] for doc in interactions} == {str(existing_seen), str(existing_same_key)}

    inserted = await dst.job_offers.find_one({"_id": ids["offer_applied"]})
    assert inserted["matched_user_ids"] == []
    assert "evaluation_score" not in inserted
    assert await dst.job_offers.find_one({"_id": ids["offer_matched"]}) is not None
    assert await dst.job_offers.find_one({"_id": ids["offer_unrelated"]}) is None
    assert await dst.job_offers.count_documents({}) == 4

    assert await dst.api_usage.count_documents({}) == 0
    assert summary.offers_existing == 2
    assert summary.offers_new == 2
    assert summary.counts["applications"] == 1


async def test_import_dry_run_writes_nothing(src_dst):
    src, dst = src_dst
    await _seed_source(src)

    summary = await import_user(dst, await _roundtrip(src), apply=False, password_hash=None)

    assert summary.counts["applications"] == 1
    assert summary.offers_new == 4
    assert await dst.list_collection_names() == []


async def test_import_refuses_an_email_already_in_target(src_dst):
    src, dst = src_dst
    await _seed_source(src)
    await dst.users.insert_one({"username": "someone", "email": EMAIL})

    with pytest.raises(TransferError):
        await import_user(dst, await _roundtrip(src), apply=True, password_hash="hash")

    assert await dst.applications.count_documents({}) == 0
    assert await dst.job_offers.count_documents({}) == 0


async def test_import_apply_requires_a_new_password_hash(src_dst):
    src, dst = src_dst
    await _seed_source(src)

    with pytest.raises(TransferError):
        await import_user(dst, await _roundtrip(src), apply=True, password_hash=None)


async def test_export_refuses_an_unknown_email(src_dst):
    src, _ = src_dst

    with pytest.raises(TransferError):
        await export_user(src, "nobody@example.test")
