import sys
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.auth import get_current_user
from app.database import get_database
from app.models import ApiUsageAction, BankStory, StoryFacts, StoryOrigin, UserModel, utcnow_with_timezone

from .helpers import UpdateStorySlotRequest, prep_response

router = APIRouter()


def _pkg():
    return sys.modules[__package__]


@router.put("/offers/{offer_id}/interview-prep/slots/{slot_id}")
async def update_interview_prep_slot(
    offer_id: str,
    slot_id: str,
    payload: UpdateStorySlotRequest,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Update a single story-slot row atomically (`$[s]`)."""
    pkg = _pkg()
    user_id = str(current_user.id)
    prep = await pkg._get_prep_or_empty(db, offer_id, user_id)
    if not any(s.get("id") == slot_id for s in prep.get("story_slots") or []):
        raise HTTPException(status_code=404, detail="Ligne introuvable.")

    changes = payload.model_dump(exclude_unset=True)
    slot_changes: Dict[str, Any] = {}
    detaching = "story_id" in changes and changes["story_id"] is None

    if detaching:
        slot_changes.update(story_id=None, fit="gap", angle="", angle_edited=False)
    elif "story_id" in changes:
        story = await pkg.get_bank_story(db, user_id, changes["story_id"])
        if story is None:
            raise HTTPException(status_code=404, detail="Histoire introuvable.")
        slot_changes.update(story_id=changes["story_id"], fit="manual")
        if "angle" not in changes:
            slot_changes.update(angle="", angle_edited=False)

    if "requirement" in changes:
        slot_changes["requirement"] = changes["requirement"]

    if "angle" in changes and not detaching:
        slot_changes["angle"] = changes["angle"]
        slot_changes["angle_edited"] = True

    set_doc: Dict[str, Any] = {
        f"story_slots.$[s].{field}": value for field, value in slot_changes.items()
    }
    set_doc["updated_at"] = utcnow_with_timezone()
    result = await db["interview_preps"].update_one(
        {"_id": prep["_id"], "story_slots.id": slot_id},
        {"$set": set_doc},
        array_filters=[{"s.id": slot_id}] if slot_changes else None,
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Ligne introuvable.")
    updated = await db["interview_preps"].find_one({"_id": prep["_id"]})
    return await prep_response(db, updated, user_id)


@router.delete("/offers/{offer_id}/interview-prep/slots/{slot_id}")
async def delete_interview_prep_slot(
    offer_id: str,
    slot_id: str,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Remove a row from the kit without touching the story bank or anticipated questions."""
    pkg = _pkg()
    user_id = str(current_user.id)
    prep = await pkg._get_prep_or_empty(db, offer_id, user_id)
    if not any(s.get("id") == slot_id for s in prep.get("story_slots") or []):
        raise HTTPException(status_code=404, detail="Ligne introuvable.")

    result = await db["interview_preps"].update_one(
        {"_id": prep["_id"], "story_slots.id": slot_id},
        {
            "$pull": {"story_slots": {"id": slot_id}},
            "$set": {"updated_at": utcnow_with_timezone()},
        },
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Ligne introuvable.")
    updated = await db["interview_preps"].find_one({"_id": prep["_id"]})
    return await prep_response(db, updated, user_id)


@router.post("/offers/{offer_id}/interview-prep/slots/{slot_id}/write")
async def write_interview_prep_slot(
    offer_id: str,
    slot_id: str,
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Generate an AI story for a `gap` slot and store it in the story bank."""
    pkg = _pkg()
    user_id = str(current_user.id)
    prep = await pkg._get_prep_or_empty(db, offer_id, user_id)
    slot = next((s for s in prep.get("story_slots") or [] if s.get("id") == slot_id), None)
    if slot is None:
        raise HTTPException(status_code=404, detail="Ligne introuvable.")

    if slot.get("fit") != "gap":
        raise HTTPException(status_code=409, detail="Cette ligne n'est pas en manque.")

    await pkg.require_user_quota(db, current_user.id, ApiUsageAction.INTERVIEW_PREP)
    profile, offer, evaluation = await pkg._get_profile_and_offer(db, offer_id, user_id)

    written = await pkg.write_stories_for_requirements(
        db=db,
        user_id=user_id,
        profile=profile,
        offer=offer,
        evaluation=evaluation,
        picks=[pkg.RequirementPick(requirement=slot.get("requirement", ""), covered=True)],
    )
    new_slot, new_story = written[0]

    if await pkg._generation_cancelled(request, "slot-write"):
        return Response(status_code=499)

    if new_story is not None:
        await db["star_stories"].insert_one(new_story.model_dump())

    result = await db["interview_preps"].update_one(
        {
            "_id": prep["_id"],
            "story_slots": {"$elemMatch": {"id": slot_id, "fit": "gap", "story_id": None}},
        },
        {
            "$set": {
                "story_slots.$.story_id": new_slot.story_id,
                "story_slots.$.fit": new_slot.fit,
                "story_slots.$.angle": new_slot.angle,
                "story_slots.$.angle_edited": False,
                "updated_at": utcnow_with_timezone(),
            }
        },
    )
    if result.matched_count == 0:
        detail = (
            "La ligne a changé pendant l'écriture ; l'histoire écrite a été ajoutée à ta banque."
            if new_story is not None
            else "La ligne a changé pendant l'écriture."
        )
        raise HTTPException(status_code=409, detail=detail)
    updated = await db["interview_preps"].find_one({"_id": prep["_id"]})
    return await prep_response(db, updated, user_id)


@router.post("/offers/{offer_id}/interview-prep/slots/{slot_id}/manual-story")
async def manual_story_interview_prep_slot(
    offer_id: str,
    slot_id: str,
    payload: StoryFacts,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Write a manual STAR+R story for an empty slot (no AI, no quota)."""
    pkg = _pkg()
    user_id = str(current_user.id)
    prep = await pkg._get_prep_or_empty(db, offer_id, user_id)
    slot = next((s for s in prep.get("story_slots") or [] if s.get("id") == slot_id), None)
    if slot is None:
        raise HTTPException(status_code=404, detail="Ligne introuvable.")

    if slot.get("story_id"):
        raise HTTPException(status_code=409, detail="Cette ligne a déjà une histoire.")

    profile, _, _ = await pkg._get_profile_and_offer(db, offer_id, user_id)
    new_story = BankStory(
        **payload.model_dump(),
        user_id=user_id,
        origin=StoryOrigin(kind="manual", offer_id=str(offer_id)),
        experience=pkg.guess_experience(payload.situation, profile.get("experiences") or []),
    )
    await db["star_stories"].insert_one(new_story.model_dump())

    result = await db["interview_preps"].update_one(
        {
            "_id": prep["_id"],
            "story_slots": {"$elemMatch": {"id": slot_id, "story_id": None}},
        },
        {
            "$set": {
                "story_slots.$.story_id": new_story.id,
                "story_slots.$.fit": "manual",
                "story_slots.$.angle": "",
                "story_slots.$.angle_edited": False,
                "updated_at": utcnow_with_timezone(),
            }
        },
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=409, detail="Cette ligne a déjà une histoire.")
    updated = await db["interview_preps"].find_one({"_id": prep["_id"]})
    return await prep_response(db, updated, user_id)
