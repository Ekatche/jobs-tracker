import sys
from typing import List

from fastapi import APIRouter, Depends, Request, Response

from app.auth import get_current_user
from app.database import get_database
from app.models import ApiUsageAction, BankStory, StorySlot, UserModel

from .helpers import (
    build_prep_scope_query,
    deduplicate_stories_for_questions,
    detach_missing_stories,
    prep_response,
    upsert_prep_section,
)

router = APIRouter()


def _pkg():
    return sys.modules[__package__]


def _unlink_dropped_questions(questions: list[dict], slots: List[StorySlot]) -> list[dict]:
    story_ids = {slot.story_id for slot in slots if slot.story_id}
    for q in questions:
        if q.get("mapped_story_id") not in story_ids:
            q["mapped_story_id"] = None
    return questions


@router.post("/offers/{offer_id}/interview-prep/generate/stories")
async def generate_stories_endpoint(
    offer_id: str,
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Generate or regenerate the story-bank rows (story_slots) for this offer."""
    pkg = _pkg()
    user_id = str(current_user.id)
    await pkg.require_user_quota(db, current_user.id, ApiUsageAction.INTERVIEW_PREP)
    profile, offer, evaluation = await pkg._get_profile_and_offer(db, offer_id, user_id)

    prep = await pkg._get_prep_or_empty(db, offer_id, user_id)
    bank = await pkg.load_bank(db, user_id)
    previous_slots = [StorySlot(**s) for s in prep.get("story_slots") or []]
    slots, new_stories = await pkg.build_story_slots(
        db=db, user_id=user_id, profile=profile, offer=offer,
        evaluation=evaluation, bank=bank, previous_slots=previous_slots,
    )
    if await pkg._generation_cancelled(request, "stories"):
        return Response(status_code=499)

    if new_stories:
        await db["star_stories"].insert_many([s.model_dump() for s in new_stories])

    slots = await detach_missing_stories(db, user_id, slots)
    current = await db["interview_preps"].find_one(build_prep_scope_query(offer_id, user_id))
    questions = _unlink_dropped_questions((current or {}).get("anticipated_questions") or [], slots)

    updated = await upsert_prep_section(
        db,
        offer_id,
        user_id,
        set_fields={
            "story_slots": [s.model_dump() for s in slots],
            "anticipated_questions": questions,
        },
        set_on_insert_defaults={
            "recruiter_pack": None, "hm_pack": None,
            "tech_pack": None, "reverse_questions": [],
        },
    )
    return await prep_response(db, updated, user_id)


@router.post("/offers/{offer_id}/interview-prep/generate/audience-packs")
async def generate_audience_packs_endpoint(
    offer_id: str,
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Generate or regenerate Recruiter, HM, and Tech panel packs."""
    pkg = _pkg()
    user_id = str(current_user.id)
    await pkg.require_user_quota(db, current_user.id, ApiUsageAction.INTERVIEW_PREP)
    profile, offer, evaluation = await pkg._get_profile_and_offer(db, offer_id, user_id)

    recruiter, hm, tech = await pkg.generate_audience_packs(
        db=db, user_id=user_id, profile=profile, offer=offer, evaluation=evaluation,
    )
    if await pkg._generation_cancelled(request, "audience-packs"):
        return Response(status_code=499)

    updated = await upsert_prep_section(
        db,
        offer_id,
        user_id,
        set_fields={
            "recruiter_pack": recruiter.model_dump(),
            "hm_pack": hm.model_dump(),
            "tech_pack": tech.model_dump(),
        },
        set_on_insert_defaults={
            "story_slots": [], "anticipated_questions": [], "reverse_questions": [],
        },
    )
    return await prep_response(db, updated, user_id)


@router.post("/offers/{offer_id}/interview-prep/generate/questions")
async def generate_questions_endpoint(
    offer_id: str,
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Generate or regenerate anticipated behavioral and technical questions."""
    pkg = _pkg()
    user_id = str(current_user.id)
    await pkg.require_user_quota(db, current_user.id, ApiUsageAction.INTERVIEW_PREP)
    profile, offer, evaluation = await pkg._get_profile_and_offer(db, offer_id, user_id)

    existing = await pkg._get_prep_or_empty(db, offer_id, user_id)
    pairs = await pkg.slots_with_stories(db, user_id, existing.get("story_slots") or [])
    seen_ids: set = set()
    stories: List[BankStory] = []
    for _, story in pairs:
        if story is not None and story.id not in seen_ids:
            seen_ids.add(story.id)
            stories.append(story)

    questions = await pkg.generate_anticipated_questions(
        db=db, user_id=user_id, profile=profile,
        offer=offer, evaluation=evaluation, stories=stories,
    )
    if await pkg._generation_cancelled(request, "questions"):
        return Response(status_code=499)

    updated = await upsert_prep_section(
        db,
        offer_id,
        user_id,
        set_fields={
            "anticipated_questions": [q.model_dump() for q in questions],
            "practice_attempts": [],
        },
        set_on_insert_defaults={
            "story_slots": [], "recruiter_pack": None,
            "hm_pack": None, "tech_pack": None, "reverse_questions": [],
        },
    )
    return await prep_response(db, updated, user_id)


@router.post("/offers/{offer_id}/interview-prep/generate/reverse-questions")
async def generate_reverse_questions_endpoint(
    offer_id: str,
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Generate or regenerate reverse questions to audit the employer."""
    pkg = _pkg()
    user_id = str(current_user.id)
    await pkg.require_user_quota(db, current_user.id, ApiUsageAction.INTERVIEW_PREP)
    _, offer, evaluation = await pkg._get_profile_and_offer(db, offer_id, user_id)

    rev_questions = await pkg.generate_reverse_questions(
        db=db, user_id=user_id, offer=offer, evaluation=evaluation,
    )
    if await pkg._generation_cancelled(request, "reverse-questions"):
        return Response(status_code=499)

    updated = await upsert_prep_section(
        db,
        offer_id,
        user_id,
        set_fields={"reverse_questions": [rq.model_dump() for rq in rev_questions]},
        set_on_insert_defaults={
            "story_slots": [], "recruiter_pack": None,
            "hm_pack": None, "tech_pack": None, "anticipated_questions": [],
        },
    )
    return await prep_response(db, updated, user_id)


@router.post("/offers/{offer_id}/interview-prep/generate/all")
async def generate_all_endpoint(
    offer_id: str,
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Generate all 4 interview prep modules sequentially."""
    pkg = _pkg()
    user_id = str(current_user.id)
    await pkg.require_user_quota(db, current_user.id, ApiUsageAction.INTERVIEW_PREP)
    profile, offer, evaluation = await pkg._get_profile_and_offer(db, offer_id, user_id)

    prep = await pkg._get_prep_or_empty(db, offer_id, user_id)
    bank = await pkg.load_bank(db, user_id)
    previous_slots = [StorySlot(**s) for s in prep.get("story_slots") or []]
    slots, new_stories = await pkg.build_story_slots(
        db=db, user_id=user_id, profile=profile, offer=offer,
        evaluation=evaluation, bank=bank, previous_slots=previous_slots,
    )
    if await pkg._generation_cancelled(request, "all (stories)"):
        return Response(status_code=499)

    recruiter, hm, tech = await pkg.generate_audience_packs(
        db=db, user_id=user_id, profile=profile, offer=offer, evaluation=evaluation,
    )
    if await pkg._generation_cancelled(request, "all (audience-packs)"):
        return Response(status_code=499)

    bank_by_id = {story.id: story for story in bank}
    for story in new_stories:
        bank_by_id[story.id] = story
    stories_for_questions = deduplicate_stories_for_questions(slots, bank_by_id)

    questions = await pkg.generate_anticipated_questions(
        db=db, user_id=user_id, profile=profile,
        offer=offer, evaluation=evaluation, stories=stories_for_questions,
    )
    if await pkg._generation_cancelled(request, "all (questions)"):
        return Response(status_code=499)

    rev_questions = await pkg.generate_reverse_questions(
        db=db, user_id=user_id, offer=offer, evaluation=evaluation,
    )
    if await pkg._generation_cancelled(request, "all (reverse-questions)"):
        return Response(status_code=499)

    if new_stories:
        await db["star_stories"].insert_many([s.model_dump() for s in new_stories])

    slots = await detach_missing_stories(db, user_id, slots)
    question_docs = _unlink_dropped_questions([q.model_dump() for q in questions], slots)

    updated = await upsert_prep_section(
        db,
        offer_id,
        user_id,
        set_fields={
            "story_slots": [s.model_dump() for s in slots],
            "recruiter_pack": recruiter.model_dump(),
            "hm_pack": hm.model_dump(),
            "tech_pack": tech.model_dump(),
            "anticipated_questions": question_docs,
            "reverse_questions": [rq.model_dump() for rq in rev_questions],
            "practice_attempts": [],
        },
        set_on_insert_defaults={},
    )
    return await prep_response(db, updated, user_id)
