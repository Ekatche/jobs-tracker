import logging
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.database import get_database
from app.models import (
    AnticipatedQuestion,
    AudiencePackHiringManager,
    AudiencePackRecruiter,
    AudiencePackTechPanel,
    InterviewPrep,
    ReverseQuestion,
    StarRStory,
    UserModel,
    utcnow_with_timezone,
    ApiUsageAction,
)
from app.services.interview_prep_service import (
    export_interview_prep_markdown,
    generate_anticipated_questions,
    generate_audience_packs,
    generate_reverse_questions,
    generate_star_stories,
)
from app.services.usage_tracker import require_user_quota
from app.utils import serialize_mongodb_doc

logger = logging.getLogger(__name__)

interview_prep_router = APIRouter(tags=["interview-prep"])


class UpdateInterviewPrepRequest(BaseModel):
    stories: Optional[List[StarRStory]] = None
    recruiter_pack: Optional[AudiencePackRecruiter] = None
    hm_pack: Optional[AudiencePackHiringManager] = None
    tech_pack: Optional[AudiencePackTechPanel] = None
    anticipated_questions: Optional[List[AnticipatedQuestion]] = None
    reverse_questions: Optional[List[ReverseQuestion]] = None


async def _get_prep_or_empty(db, offer_id: str, user_id: str) -> Dict[str, Any]:
    """Retrieve existing interview prep doc or return an empty draft structure."""
    user_query = {"$or": [{"user_id": str(user_id)}, {"user_id": ObjectId(user_id)}]} if ObjectId.is_valid(user_id) else {"user_id": str(user_id)}
    offer_query = {"$or": [{"offer_id": str(offer_id)}, {"offer_id": ObjectId(offer_id)}]} if ObjectId.is_valid(offer_id) else {"offer_id": str(offer_id)}

    query = {"$and": [user_query, offer_query]}
    existing = await db["interview_preps"].find_one(query)
    if existing:
        return existing

    return {
        "offer_id": str(offer_id),
        "user_id": str(user_id),
        "stories": [],
        "recruiter_pack": None,
        "hm_pack": None,
        "tech_pack": None,
        "anticipated_questions": [],
        "reverse_questions": [],
        "created_at": utcnow_with_timezone(),
        "updated_at": utcnow_with_timezone(),
    }


async def _get_profile_and_offer(db, offer_id: str, user_id: str) -> tuple[Dict[str, Any], Dict[str, Any], Optional[Dict[str, Any]]]:
    """Helper to fetch profile, offer and evaluation."""
    user_query = {"$or": [{"user_id": str(user_id)}, {"user_id": ObjectId(user_id)}]} if ObjectId.is_valid(user_id) else {"user_id": str(user_id)}
    profile = await db["candidate_profiles"].find_one(user_query)
    if not profile:
        raise HTTPException(status_code=400, detail="Profil candidat introuvable. Veuillez compléter votre profil d'abord.")

    if not ObjectId.is_valid(offer_id):
        raise HTTPException(status_code=400, detail="ID d'offre invalide.")
    offer = await db["job_offers"].find_one({"_id": ObjectId(offer_id)})
    if not offer:
        raise HTTPException(status_code=404, detail="Offre d'emploi introuvable.")

    eval_query = {"$or": [{"offer_id": str(offer_id)}, {"offer_id": ObjectId(offer_id)}]}
    evaluation = await db["offer_evaluations"].find_one(eval_query)

    return profile, offer, evaluation


@interview_prep_router.get("/offers/{offer_id}/interview-prep")
async def get_interview_prep(
    offer_id: str,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Retrieve existing interview prep for the offer, or an empty shell."""
    prep = await _get_prep_or_empty(db, offer_id, str(current_user.id))
    return serialize_mongodb_doc(prep)


@interview_prep_router.post("/offers/{offer_id}/interview-prep/generate/stories")
async def generate_stories_endpoint(
    offer_id: str,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Generate or regenerate STAR+R stories for this offer."""
    await require_user_quota(str(current_user.id), ApiUsageAction.INTERVIEW_PREP)
    profile, offer, evaluation = await _get_profile_and_offer(db, offer_id, str(current_user.id))

    stories = await generate_star_stories(
        user_id=str(current_user.id),
        profile=profile,
        offer=offer,
        evaluation=evaluation,
    )

    now = utcnow_with_timezone()
    user_query = {"$or": [{"user_id": str(current_user.id)}, {"user_id": ObjectId(current_user.id)}]}
    offer_query = {"$or": [{"offer_id": str(offer_id)}, {"offer_id": ObjectId(offer_id)}]}
    query = {"$and": [user_query, offer_query]}

    update_doc = {
        "$set": {
            "stories": [s.model_dump() for s in stories],
            "updated_at": now,
        },
        "$setOnInsert": {
            "offer_id": str(offer_id),
            "user_id": str(current_user.id),
            "recruiter_pack": None,
            "hm_pack": None,
            "tech_pack": None,
            "anticipated_questions": [],
            "reverse_questions": [],
            "created_at": now,
        },
    }
    await db["interview_preps"].update_one(query, update_doc, upsert=True)
    updated = await db["interview_preps"].find_one(query)
    return serialize_mongodb_doc(updated)


@interview_prep_router.post("/offers/{offer_id}/interview-prep/generate/audience-packs")
async def generate_audience_packs_endpoint(
    offer_id: str,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Generate or regenerate Recruiter, HM, and Tech panel packs."""
    await require_user_quota(str(current_user.id), ApiUsageAction.INTERVIEW_PREP)
    profile, offer, evaluation = await _get_profile_and_offer(db, offer_id, str(current_user.id))

    recruiter, hm, tech = await generate_audience_packs(
        user_id=str(current_user.id),
        profile=profile,
        offer=offer,
        evaluation=evaluation,
    )

    now = utcnow_with_timezone()
    user_query = {"$or": [{"user_id": str(current_user.id)}, {"user_id": ObjectId(current_user.id)}]}
    offer_query = {"$or": [{"offer_id": str(offer_id)}, {"offer_id": ObjectId(offer_id)}]}
    query = {"$and": [user_query, offer_query]}

    update_doc = {
        "$set": {
            "recruiter_pack": recruiter.model_dump(),
            "hm_pack": hm.model_dump(),
            "tech_pack": tech.model_dump(),
            "updated_at": now,
        },
        "$setOnInsert": {
            "offer_id": str(offer_id),
            "user_id": str(current_user.id),
            "stories": [],
            "anticipated_questions": [],
            "reverse_questions": [],
            "created_at": now,
        },
    }
    await db["interview_preps"].update_one(query, update_doc, upsert=True)
    updated = await db["interview_preps"].find_one(query)
    return serialize_mongodb_doc(updated)


@interview_prep_router.post("/offers/{offer_id}/interview-prep/generate/questions")
async def generate_questions_endpoint(
    offer_id: str,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Generate or regenerate anticipated behavioral and technical questions."""
    await require_user_quota(str(current_user.id), ApiUsageAction.INTERVIEW_PREP)
    profile, offer, evaluation = await _get_profile_and_offer(db, offer_id, str(current_user.id))

    existing = await _get_prep_or_empty(db, offer_id, str(current_user.id))
    stories = [StarRStory(**s) for s in existing.get("stories", [])]

    questions = await generate_anticipated_questions(
        user_id=str(current_user.id),
        profile=profile,
        offer=offer,
        evaluation=evaluation,
        stories=stories,
    )

    now = utcnow_with_timezone()
    user_query = {"$or": [{"user_id": str(current_user.id)}, {"user_id": ObjectId(current_user.id)}]}
    offer_query = {"$or": [{"offer_id": str(offer_id)}, {"offer_id": ObjectId(offer_id)}]}
    query = {"$and": [user_query, offer_query]}

    update_doc = {
        "$set": {
            "anticipated_questions": [q.model_dump() for q in questions],
            "updated_at": now,
        },
        "$setOnInsert": {
            "offer_id": str(offer_id),
            "user_id": str(current_user.id),
            "stories": [],
            "recruiter_pack": None,
            "hm_pack": None,
            "tech_pack": None,
            "reverse_questions": [],
            "created_at": now,
        },
    }
    await db["interview_preps"].update_one(query, update_doc, upsert=True)
    updated = await db["interview_preps"].find_one(query)
    return serialize_mongodb_doc(updated)


@interview_prep_router.post("/offers/{offer_id}/interview-prep/generate/reverse-questions")
async def generate_reverse_questions_endpoint(
    offer_id: str,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Generate or regenerate reverse questions to audit the employer."""
    await require_user_quota(str(current_user.id), ApiUsageAction.INTERVIEW_PREP)
    _, offer, evaluation = await _get_profile_and_offer(db, offer_id, str(current_user.id))

    rev_questions = await generate_reverse_questions(
        user_id=str(current_user.id),
        offer=offer,
        evaluation=evaluation,
    )

    now = utcnow_with_timezone()
    user_query = {"$or": [{"user_id": str(current_user.id)}, {"user_id": ObjectId(current_user.id)}]}
    offer_query = {"$or": [{"offer_id": str(offer_id)}, {"offer_id": ObjectId(offer_id)}]}
    query = {"$and": [user_query, offer_query]}

    update_doc = {
        "$set": {
            "reverse_questions": [rq.model_dump() for rq in rev_questions],
            "updated_at": now,
        },
        "$setOnInsert": {
            "offer_id": str(offer_id),
            "user_id": str(current_user.id),
            "stories": [],
            "recruiter_pack": None,
            "hm_pack": None,
            "tech_pack": None,
            "anticipated_questions": [],
            "created_at": now,
        },
    }
    await db["interview_preps"].update_one(query, update_doc, upsert=True)
    updated = await db["interview_preps"].find_one(query)
    return serialize_mongodb_doc(updated)


@interview_prep_router.post("/offers/{offer_id}/interview-prep/generate/all")
async def generate_all_endpoint(
    offer_id: str,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Generate all 4 modules in sequence for full convenience."""
    await require_user_quota(str(current_user.id), ApiUsageAction.INTERVIEW_PREP)
    profile, offer, evaluation = await _get_profile_and_offer(db, offer_id, str(current_user.id))

    stories = await generate_star_stories(
        user_id=str(current_user.id),
        profile=profile,
        offer=offer,
        evaluation=evaluation,
    )
    recruiter, hm, tech = await generate_audience_packs(
        user_id=str(current_user.id),
        profile=profile,
        offer=offer,
        evaluation=evaluation,
    )
    questions = await generate_anticipated_questions(
        user_id=str(current_user.id),
        profile=profile,
        offer=offer,
        evaluation=evaluation,
        stories=stories,
    )
    rev_questions = await generate_reverse_questions(
        user_id=str(current_user.id),
        offer=offer,
        evaluation=evaluation,
    )

    now = utcnow_with_timezone()
    user_query = {"$or": [{"user_id": str(current_user.id)}, {"user_id": ObjectId(current_user.id)}]}
    offer_query = {"$or": [{"offer_id": str(offer_id)}, {"offer_id": ObjectId(offer_id)}]}
    query = {"$and": [user_query, offer_query]}

    doc = {
        "offer_id": str(offer_id),
        "user_id": str(current_user.id),
        "stories": [s.model_dump() for s in stories],
        "recruiter_pack": recruiter.model_dump(),
        "hm_pack": hm.model_dump(),
        "tech_pack": tech.model_dump(),
        "anticipated_questions": [q.model_dump() for q in questions],
        "reverse_questions": [rq.model_dump() for rq in rev_questions],
        "created_at": now,
        "updated_at": now,
    }
    await db["interview_preps"].update_one(query, {"$set": doc}, upsert=True)
    updated = await db["interview_preps"].find_one(query)
    return serialize_mongodb_doc(updated)


@interview_prep_router.put("/offers/{offer_id}/interview-prep")
async def update_interview_prep(
    offer_id: str,
    payload: UpdateInterviewPrepRequest,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Save manual edits made by the candidate to any section of their prep kit."""
    now = utcnow_with_timezone()
    user_query = {"$or": [{"user_id": str(current_user.id)}, {"user_id": ObjectId(current_user.id)}]}
    offer_query = {"$or": [{"offer_id": str(offer_id)}, {"offer_id": ObjectId(offer_id)}]}
    query = {"$and": [user_query, offer_query]}

    update_fields: Dict[str, Any] = {"updated_at": now}
    if payload.stories is not None:
        update_fields["stories"] = [s.model_dump() for s in payload.stories]
    if payload.recruiter_pack is not None:
        update_fields["recruiter_pack"] = payload.recruiter_pack.model_dump()
    if payload.hm_pack is not None:
        update_fields["hm_pack"] = payload.hm_pack.model_dump()
    if payload.tech_pack is not None:
        update_fields["tech_pack"] = payload.tech_pack.model_dump()
    if payload.anticipated_questions is not None:
        update_fields["anticipated_questions"] = [q.model_dump() for q in payload.anticipated_questions]
    if payload.reverse_questions is not None:
        update_fields["reverse_questions"] = [rq.model_dump() for rq in payload.reverse_questions]

    await db["interview_preps"].update_one(
        query,
        {
            "$set": update_fields,
            "$setOnInsert": {
                "offer_id": str(offer_id),
                "user_id": str(current_user.id),
                "created_at": now,
            },
        },
        upsert=True,
    )
    updated = await db["interview_preps"].find_one(query)
    return serialize_mongodb_doc(updated)


@interview_prep_router.get("/offers/{offer_id}/interview-prep/export")
async def export_interview_prep(
    offer_id: str,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Export the complete prep notes in clean Markdown format."""
    user_query = {"$or": [{"user_id": str(current_user.id)}, {"user_id": ObjectId(current_user.id)}]}
    offer_query = {"$or": [{"offer_id": str(offer_id)}, {"offer_id": ObjectId(offer_id)}]}
    query = {"$and": [user_query, offer_query]}

    prep_doc = await db["interview_preps"].find_one(query)
    if not prep_doc:
        prep_doc = await _get_prep_or_empty(db, offer_id, str(current_user.id))

    offer_doc = {}
    if ObjectId.is_valid(offer_id):
        offer_doc = await db["job_offers"].find_one({"_id": ObjectId(offer_id)}) or {}

    prep = InterviewPrep(**prep_doc)
    markdown_content = export_interview_prep_markdown(prep, offer_doc)

    company_slug = "".join(c if c.isalnum() else "_" for c in offer_doc.get("company", "interview")).lower()
    return Response(
        content=markdown_content,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="prep_{company_slug}_{offer_id[:6]}.md"',
        },
    )
