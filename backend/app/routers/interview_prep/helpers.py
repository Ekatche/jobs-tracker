import logging
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import HTTPException, Request

from app.models import (
    AnticipatedQuestion,
    AudiencePackHiringManager,
    AudiencePackRecruiter,
    AudiencePackTechPanel,
    BankStory,
    ReverseQuestion,
    StorySlot,
    utcnow_with_timezone,
)
from pydantic import BaseModel, Field
from app.services.star_bank import bank_story_ids, ensure_prep_migrated, hydrate_prep
from app.utils import serialize_mongodb_doc

logger = logging.getLogger(__name__)


class UpdateInterviewPrepRequest(BaseModel):
    recruiter_pack: Optional[AudiencePackRecruiter] = None
    hm_pack: Optional[AudiencePackHiringManager] = None
    tech_pack: Optional[AudiencePackTechPanel] = None
    anticipated_questions: Optional[List[AnticipatedQuestion]] = None
    reverse_questions: Optional[List[ReverseQuestion]] = None


class PracticeAnswerRequest(BaseModel):
    question_id: str = Field(..., min_length=1, max_length=64)
    answer: str = Field(..., min_length=1, max_length=6000)


class UpdateStorySlotRequest(BaseModel):
    story_id: Optional[str] = None
    requirement: Optional[str] = None
    angle: Optional[str] = None


def build_prep_scope_query(offer_id: str, user_id: str) -> Dict[str, Any]:
    """Build Mongo filter matching (user_id, offer_id) as either string or ObjectId."""
    user_query = (
        {"$or": [{"user_id": str(user_id)}, {"user_id": ObjectId(user_id)}]}
        if ObjectId.is_valid(user_id)
        else {"user_id": str(user_id)}
    )
    offer_query = (
        {"$or": [{"offer_id": str(offer_id)}, {"offer_id": ObjectId(offer_id)}]}
        if ObjectId.is_valid(offer_id)
        else {"offer_id": str(offer_id)}
    )
    return {"$and": [user_query, offer_query]}


async def get_prep_or_empty(db, offer_id: str, user_id: str) -> Dict[str, Any]:
    """Retrieve existing interview prep doc (migrated to bank) or an empty draft shell."""
    query = build_prep_scope_query(offer_id, user_id)
    existing = await db["interview_preps"].find_one(query)
    if existing:
        return await ensure_prep_migrated(db, existing)

    now = utcnow_with_timezone()
    return {
        "offer_id": str(offer_id),
        "user_id": str(user_id),
        "stories": [],
        "story_slots": [],
        "recruiter_pack": None,
        "hm_pack": None,
        "tech_pack": None,
        "anticipated_questions": [],
        "reverse_questions": [],
        "created_at": now,
        "updated_at": now,
    }


async def prep_response(db, prep: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Serialize a prep kit with joined story-bank facts."""
    return serialize_mongodb_doc(await hydrate_prep(db, prep, user_id))


async def get_profile_and_offer(
    db, offer_id: str, user_id: str
) -> tuple[Dict[str, Any], Dict[str, Any], Optional[Dict[str, Any]]]:
    """Fetch candidate profile, job offer, and optional evaluation for generation."""
    user_query = (
        {"$or": [{"user_id": str(user_id)}, {"user_id": ObjectId(user_id)}]}
        if ObjectId.is_valid(user_id)
        else {"user_id": str(user_id)}
    )
    profile = await db["candidate_profile"].find_one(user_query)
    if not profile:
        raise HTTPException(
            status_code=400,
            detail="Profil candidat introuvable. Veuillez compléter votre profil d'abord.",
        )

    if not ObjectId.is_valid(offer_id):
        raise HTTPException(status_code=400, detail="ID d'offre invalide.")
    offer = await db["job_offers"].find_one({"_id": ObjectId(offer_id)})
    if not offer:
        raise HTTPException(status_code=404, detail="Offre d'emploi introuvable.")

    offer_query = {"$or": [{"offer_id": str(offer_id)}, {"offer_id": ObjectId(offer_id)}]}
    evaluation = await db["offer_evaluations"].find_one({"$and": [user_query, offer_query]})
    return profile, offer, evaluation


async def generation_cancelled(request: Request, module: str) -> bool:
    """Return True when the client aborted during an LLM call."""
    if await request.is_disconnected():
        logger.info("Génération %s annulée par le client : résultat ignoré", module)
        return True
    return False


async def detach_missing_stories(db, user_id: str, slots: List[StorySlot]) -> List[StorySlot]:
    """Reset any slot pointing to a deleted/merged bank story back to gap state."""
    existing_ids = await bank_story_ids(db, user_id)
    return [
        slot
        if slot.story_id is None or slot.story_id in existing_ids
        else slot.model_copy(
            update={"story_id": None, "fit": "gap", "angle": "", "angle_edited": False}
        )
        for slot in slots
    ]


async def upsert_prep_section(
    db,
    offer_id: str,
    user_id: str,
    set_fields: Dict[str, Any],
    set_on_insert_defaults: Dict[str, Any],
) -> Dict[str, Any]:
    """Upsert generated fields into `interview_preps` and return the updated doc."""
    now = utcnow_with_timezone()
    query = build_prep_scope_query(offer_id, user_id)
    update_doc = {
        "$set": {**set_fields, "updated_at": now},
        "$setOnInsert": {
            "offer_id": str(offer_id),
            "user_id": str(user_id),
            **set_on_insert_defaults,
            "created_at": now,
        },
    }
    await db["interview_preps"].update_one(query, update_doc, upsert=True)
    return await db["interview_preps"].find_one(query)


def deduplicate_stories_for_questions(
    slots: List[StorySlot],
    bank_by_id: Dict[str, BankStory],
) -> List[BankStory]:
    """Collect unique bank stories referenced by slots in slot display order."""
    seen: set = set()
    stories: List[BankStory] = []
    for slot in slots:
        if slot.story_id and slot.story_id not in seen:
            seen.add(slot.story_id)
            story = bank_by_id.get(slot.story_id)
            if story is not None:
                stories.append(story)
    return stories
