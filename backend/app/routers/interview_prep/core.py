import sys
from typing import Any, Dict

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Response

from app.auth import get_current_user
from app.database import get_database
from app.models import AnticipatedQuestion, ApiUsageAction, InterviewPrep, UserModel, utcnow_with_timezone

from .helpers import (
    PracticeAnswerRequest,
    UpdateInterviewPrepRequest,
    build_prep_scope_query,
    prep_response,
)

router = APIRouter()


def _pkg():
    return sys.modules[__package__]


@router.get("/offers/{offer_id}/interview-prep")
async def get_interview_prep(
    offer_id: str,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Retrieve existing interview prep for the offer, or an empty shell."""
    pkg = _pkg()
    prep = await pkg._get_prep_or_empty(db, offer_id, str(current_user.id))
    return await prep_response(db, prep, str(current_user.id))


@router.post("/offers/{offer_id}/interview-prep/practice")
async def practice_answer_endpoint(
    offer_id: str,
    payload: PracticeAnswerRequest,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Score a practice answer to an anticipated question and append it to attempt history."""
    pkg = _pkg()
    user_id = str(current_user.id)
    await pkg.require_user_quota(db, current_user.id, ApiUsageAction.INTERVIEW_PREP)
    _, offer, evaluation = await pkg._get_profile_and_offer(db, offer_id, user_id)

    existing = await pkg._get_prep_or_empty(db, offer_id, user_id)
    question = next(
        (q for q in existing.get("anticipated_questions") or [] if q.get("id") == payload.question_id),
        None,
    )
    if question is None:
        raise HTTPException(status_code=404, detail="Question introuvable dans le kit.")
    story = await pkg.get_bank_story(db, user_id, question.get("mapped_story_id"))

    attempt = await pkg.evaluate_practice_answer(
        db=db,
        user_id=user_id,
        offer=offer,
        evaluation=evaluation,
        question=AnticipatedQuestion(**question),
        answer=payload.answer,
        story=story,
    )

    query = build_prep_scope_query(offer_id, user_id)
    await db["interview_preps"].update_one(
        query,
        {
            "$push": {"practice_attempts": attempt.model_dump()},
            "$set": {"updated_at": utcnow_with_timezone()},
        },
    )
    updated = await db["interview_preps"].find_one(query)
    return await prep_response(db, updated, user_id)


@router.put("/offers/{offer_id}/interview-prep")
async def update_interview_prep(
    offer_id: str,
    payload: UpdateInterviewPrepRequest,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Save manual edits made by the candidate to any section of their prep kit."""
    user_id = str(current_user.id)
    now = utcnow_with_timezone()
    query = build_prep_scope_query(offer_id, user_id)

    update_fields: Dict[str, Any] = {"updated_at": now}
    update_doc: Dict[str, Any] = {
        "$set": update_fields,
        "$setOnInsert": {"offer_id": str(offer_id), "user_id": user_id, "created_at": now},
    }
    if payload.recruiter_pack is not None:
        update_fields["recruiter_pack"] = payload.recruiter_pack.model_dump()
    if payload.hm_pack is not None:
        update_fields["hm_pack"] = payload.hm_pack.model_dump()
    if payload.tech_pack is not None:
        update_fields["tech_pack"] = payload.tech_pack.model_dump()
    if payload.anticipated_questions is not None:
        update_fields["anticipated_questions"] = [q.model_dump() for q in payload.anticipated_questions]
        kept_ids = [q.id for q in payload.anticipated_questions]
        update_doc["$pull"] = {"practice_attempts": {"question_id": {"$nin": kept_ids}}}
    if payload.reverse_questions is not None:
        update_fields["reverse_questions"] = [rq.model_dump() for rq in payload.reverse_questions]

    await db["interview_preps"].update_one(query, update_doc, upsert=True)
    updated = await db["interview_preps"].find_one(query)
    return await prep_response(db, updated, user_id)


@router.get("/offers/{offer_id}/interview-prep/export")
async def export_interview_prep(
    offer_id: str,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Export the complete prep notes in clean Markdown format."""
    pkg = _pkg()
    user_id = str(current_user.id)
    prep_doc = await pkg._get_prep_or_empty(db, offer_id, user_id)

    offer_doc = {}
    if ObjectId.is_valid(offer_id):
        offer_doc = await db["job_offers"].find_one({"_id": ObjectId(offer_id)}) or {}

    slots = await pkg.slots_with_stories(db, user_id, prep_doc.get("story_slots") or [])
    prep = InterviewPrep(**prep_doc)
    markdown_content = pkg.export_interview_prep_markdown(prep, offer_doc, slots)

    company_slug = "".join(
        c if c.isalnum() else "_" for c in offer_doc.get("company", "interview")
    ).lower()
    return Response(
        content=markdown_content,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="prep_{company_slug}_{offer_id[:6]}.md"',
        },
    )
