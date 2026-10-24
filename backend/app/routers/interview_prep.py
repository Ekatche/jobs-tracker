import logging
from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.database import get_database
from app.models import (
    AnticipatedQuestion,
    AudiencePackHiringManager,
    AudiencePackRecruiter,
    AudiencePackTechPanel,
    BankStory,
    InterviewPrep,
    ReverseQuestion,
    StoryFacts,
    StoryOrigin,
    StorySlot,
    UserModel,
    utcnow_with_timezone,
    ApiUsageAction,
)
from app.services.interview_prep_service import (
    RequirementPick,
    build_story_slots,
    evaluate_practice_answer,
    export_interview_prep_markdown,
    generate_anticipated_questions,
    generate_audience_packs,
    generate_reverse_questions,
    write_stories_for_requirements,
)
from app.services.star_bank import (
    bank_story_ids,
    ensure_prep_migrated,
    get_bank_story,
    hydrate_prep,
    load_bank,
    slots_with_stories,
)
from app.services.star_bank_rules import guess_experience
from app.services.usage_tracker import require_user_quota
from app.utils import serialize_mongodb_doc

logger = logging.getLogger(__name__)

interview_prep_router = APIRouter(tags=["interview-prep"])


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


async def _get_prep_or_empty(db, offer_id: str, user_id: str) -> Dict[str, Any]:
    """Retrieve existing interview prep doc (lazily migrated to the story bank) or return an empty draft structure."""
    user_query = {"$or": [{"user_id": str(user_id)}, {"user_id": ObjectId(user_id)}]} if ObjectId.is_valid(user_id) else {"user_id": str(user_id)}
    offer_query = {"$or": [{"offer_id": str(offer_id)}, {"offer_id": ObjectId(offer_id)}]} if ObjectId.is_valid(offer_id) else {"offer_id": str(offer_id)}

    query = {"$and": [user_query, offer_query]}
    existing = await db["interview_preps"].find_one(query)
    if existing:
        return await ensure_prep_migrated(db, existing)

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
        "created_at": utcnow_with_timezone(),
        "updated_at": utcnow_with_timezone(),
    }


async def _prep_response(db, prep: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Serialize a kit with its story-bank facts joined in, for every route that returns the kit."""
    return serialize_mongodb_doc(await hydrate_prep(db, prep, user_id))


async def _get_profile_and_offer(db, offer_id: str, user_id: str) -> tuple[Dict[str, Any], Dict[str, Any], Optional[Dict[str, Any]]]:
    """Helper to fetch profile, offer and evaluation."""
    user_query = {"$or": [{"user_id": str(user_id)}, {"user_id": ObjectId(user_id)}]} if ObjectId.is_valid(user_id) else {"user_id": str(user_id)}
    profile = await db["candidate_profile"].find_one(user_query)
    if not profile:
        raise HTTPException(status_code=400, detail="Profil candidat introuvable. Veuillez compléter votre profil d'abord.")

    if not ObjectId.is_valid(offer_id):
        raise HTTPException(status_code=400, detail="ID d'offre invalide.")
    offer = await db["job_offers"].find_one({"_id": ObjectId(offer_id)})
    if not offer:
        raise HTTPException(status_code=404, detail="Offre d'emploi introuvable.")

    offer_query = {"$or": [{"offer_id": str(offer_id)}, {"offer_id": ObjectId(offer_id)}]}
    evaluation = await db["offer_evaluations"].find_one({"$and": [user_query, offer_query]})

    return profile, offer, evaluation


async def _generation_cancelled(request: Request, module: str) -> bool:
    """True when the client aborted during the LLM call: its result must not overwrite the prep."""
    if await request.is_disconnected():
        logger.info("Génération %s annulée par le client : résultat ignoré", module)
        return True
    return False


async def _detach_missing_stories(db, user_id: str, slots: List[StorySlot]) -> List[StorySlot]:
    """Remet en manque toute ligne dont l'histoire n'est plus dans la banque.

    La banque a pu changer pendant l'appel IA (histoire supprimée ou fusionnée
    depuis le panneau) : même forme que `delete_bank_story` (`story_id=None`,
    `fit="gap"`, angle vidé), pour ne jamais écrire de référence pendante.
    """
    existing_ids = await bank_story_ids(db, user_id)
    return [
        slot
        if slot.story_id is None or slot.story_id in existing_ids
        else slot.model_copy(update={"story_id": None, "fit": "gap", "angle": "", "angle_edited": False})
        for slot in slots
    ]


@interview_prep_router.get("/offers/{offer_id}/interview-prep")
async def get_interview_prep(
    offer_id: str,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Retrieve existing interview prep for the offer, or an empty shell."""
    prep = await _get_prep_or_empty(db, offer_id, str(current_user.id))
    return await _prep_response(db, prep, str(current_user.id))


@interview_prep_router.post("/offers/{offer_id}/interview-prep/generate/stories")
async def generate_stories_endpoint(
    offer_id: str,
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Generate or regenerate the story-bank rows (story_slots) for this offer."""
    user_id = str(current_user.id)
    await require_user_quota(db, current_user.id, ApiUsageAction.INTERVIEW_PREP)
    profile, offer, evaluation = await _get_profile_and_offer(db, offer_id, user_id)

    # _get_prep_or_empty migre les histoires héritées dans la banque avant tout remplacement.
    prep = await _get_prep_or_empty(db, offer_id, user_id)
    bank = await load_bank(db, user_id)
    previous_slots = [StorySlot(**s) for s in prep.get("story_slots") or []]
    slots, new_stories = await build_story_slots(
        db=db,
        user_id=user_id,
        profile=profile,
        offer=offer,
        evaluation=evaluation,
        bank=bank,
        previous_slots=previous_slots,
    )
    if await _generation_cancelled(request, "stories"):
        return Response(status_code=499)

    if new_stories:
        await db["star_stories"].insert_many([s.model_dump() for s in new_stories])

    slots = await _detach_missing_stories(db, user_id, slots)

    user_query = {"$or": [{"user_id": str(current_user.id)}, {"user_id": ObjectId(current_user.id)}]}
    offer_query = {"$or": [{"offer_id": str(offer_id)}, {"offer_id": ObjectId(offer_id)}]}
    query = {"$and": [user_query, offer_query]}

    # Questions relues après l'appel IA : une fusion faite entre-temps a pu les rediriger.
    current = await db["interview_preps"].find_one(query)
    questions = (current or {}).get("anticipated_questions") or []

    # New/changed slots can drop a story id: unlink any question that pointed to it.
    story_ids = {slot.story_id for slot in slots if slot.story_id}
    for q in questions:
        if q.get("mapped_story_id") not in story_ids:
            q["mapped_story_id"] = None

    now = utcnow_with_timezone()

    update_doc = {
        "$set": {
            "story_slots": [s.model_dump() for s in slots],
            "anticipated_questions": questions,
            "updated_at": now,
        },
        "$setOnInsert": {
            "offer_id": str(offer_id),
            "user_id": user_id,
            "recruiter_pack": None,
            "hm_pack": None,
            "tech_pack": None,
            "reverse_questions": [],
            "created_at": now,
        },
    }
    await db["interview_preps"].update_one(query, update_doc, upsert=True)
    updated = await db["interview_preps"].find_one(query)
    return await _prep_response(db, updated, user_id)


@interview_prep_router.post("/offers/{offer_id}/interview-prep/generate/audience-packs")
async def generate_audience_packs_endpoint(
    offer_id: str,
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Generate or regenerate Recruiter, HM, and Tech panel packs."""
    await require_user_quota(db, current_user.id, ApiUsageAction.INTERVIEW_PREP)
    profile, offer, evaluation = await _get_profile_and_offer(db, offer_id, str(current_user.id))

    recruiter, hm, tech = await generate_audience_packs(
        db=db,
        user_id=str(current_user.id),
        profile=profile,
        offer=offer,
        evaluation=evaluation,
    )
    if await _generation_cancelled(request, "audience-packs"):
        return Response(status_code=499)

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
            "story_slots": [],
            "anticipated_questions": [],
            "reverse_questions": [],
            "created_at": now,
        },
    }
    await db["interview_preps"].update_one(query, update_doc, upsert=True)
    updated = await db["interview_preps"].find_one(query)
    return await _prep_response(db, updated, str(current_user.id))


@interview_prep_router.post("/offers/{offer_id}/interview-prep/generate/questions")
async def generate_questions_endpoint(
    offer_id: str,
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Generate or regenerate anticipated behavioral and technical questions."""
    await require_user_quota(db, current_user.id, ApiUsageAction.INTERVIEW_PREP)
    profile, offer, evaluation = await _get_profile_and_offer(db, offer_id, str(current_user.id))

    existing = await _get_prep_or_empty(db, offer_id, str(current_user.id))
    pairs = await slots_with_stories(db, str(current_user.id), existing.get("story_slots") or [])
    seen_story_ids: set = set()
    stories: List[BankStory] = []
    for _, story in pairs:
        if story is not None and story.id not in seen_story_ids:
            seen_story_ids.add(story.id)
            stories.append(story)

    questions = await generate_anticipated_questions(
        db=db,
        user_id=str(current_user.id),
        profile=profile,
        offer=offer,
        evaluation=evaluation,
        stories=stories,
    )
    if await _generation_cancelled(request, "questions"):
        return Response(status_code=499)

    now = utcnow_with_timezone()
    user_query = {"$or": [{"user_id": str(current_user.id)}, {"user_id": ObjectId(current_user.id)}]}
    offer_query = {"$or": [{"offer_id": str(offer_id)}, {"offer_id": ObjectId(offer_id)}]}
    query = {"$and": [user_query, offer_query]}

    update_doc = {
        "$set": {
            "anticipated_questions": [q.model_dump() for q in questions],
            # New questions get fresh ids: attempts on the old ones would be orphans.
            "practice_attempts": [],
            "updated_at": now,
        },
        "$setOnInsert": {
            "offer_id": str(offer_id),
            "user_id": str(current_user.id),
            "story_slots": [],
            "recruiter_pack": None,
            "hm_pack": None,
            "tech_pack": None,
            "reverse_questions": [],
            "created_at": now,
        },
    }
    await db["interview_preps"].update_one(query, update_doc, upsert=True)
    updated = await db["interview_preps"].find_one(query)
    return await _prep_response(db, updated, str(current_user.id))


@interview_prep_router.post("/offers/{offer_id}/interview-prep/generate/reverse-questions")
async def generate_reverse_questions_endpoint(
    offer_id: str,
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Generate or regenerate reverse questions to audit the employer."""
    await require_user_quota(db, current_user.id, ApiUsageAction.INTERVIEW_PREP)
    _, offer, evaluation = await _get_profile_and_offer(db, offer_id, str(current_user.id))

    rev_questions = await generate_reverse_questions(
        db=db,
        user_id=str(current_user.id),
        offer=offer,
        evaluation=evaluation,
    )
    if await _generation_cancelled(request, "reverse-questions"):
        return Response(status_code=499)

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
            "story_slots": [],
            "recruiter_pack": None,
            "hm_pack": None,
            "tech_pack": None,
            "anticipated_questions": [],
            "created_at": now,
        },
    }
    await db["interview_preps"].update_one(query, update_doc, upsert=True)
    updated = await db["interview_preps"].find_one(query)
    return await _prep_response(db, updated, str(current_user.id))


@interview_prep_router.post("/offers/{offer_id}/interview-prep/generate/all")
async def generate_all_endpoint(
    offer_id: str,
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Generate all 4 modules in sequence for full convenience."""
    user_id = str(current_user.id)
    await require_user_quota(db, current_user.id, ApiUsageAction.INTERVIEW_PREP)
    profile, offer, evaluation = await _get_profile_and_offer(db, offer_id, user_id)

    # _get_prep_or_empty migre les histoires héritées dans la banque avant tout remplacement.
    prep = await _get_prep_or_empty(db, offer_id, user_id)
    bank = await load_bank(db, user_id)
    previous_slots = [StorySlot(**s) for s in prep.get("story_slots") or []]
    slots, new_stories = await build_story_slots(
        db=db,
        user_id=user_id,
        profile=profile,
        offer=offer,
        evaluation=evaluation,
        bank=bank,
        previous_slots=previous_slots,
    )
    if await _generation_cancelled(request, "all (stories)"):
        return Response(status_code=499)

    recruiter, hm, tech = await generate_audience_packs(
        db=db,
        user_id=user_id,
        profile=profile,
        offer=offer,
        evaluation=evaluation,
    )
    if await _generation_cancelled(request, "all (audience-packs)"):
        return Response(status_code=499)

    # Histoires des nouvelles lignes (banque chargée + nouvelles écritures), dans l'ordre des lignes,
    # sans doublon ni trou (une ligne sans histoire n'apporte rien au contexte des questions).
    bank_by_id = {story.id: story for story in bank}
    for story in new_stories:
        bank_by_id[story.id] = story
    seen_story_ids: set = set()
    stories_for_questions: List[BankStory] = []
    for slot in slots:
        if slot.story_id and slot.story_id not in seen_story_ids:
            seen_story_ids.add(slot.story_id)
            story = bank_by_id.get(slot.story_id)
            if story is not None:
                stories_for_questions.append(story)

    questions = await generate_anticipated_questions(
        db=db,
        user_id=user_id,
        profile=profile,
        offer=offer,
        evaluation=evaluation,
        stories=stories_for_questions,
    )
    if await _generation_cancelled(request, "all (questions)"):
        return Response(status_code=499)
    rev_questions = await generate_reverse_questions(
        db=db,
        user_id=user_id,
        offer=offer,
        evaluation=evaluation,
    )
    if await _generation_cancelled(request, "all (reverse-questions)"):
        return Response(status_code=499)

    if new_stories:
        await db["star_stories"].insert_many([s.model_dump() for s in new_stories])

    slots = await _detach_missing_stories(db, user_id, slots)

    # Même règle de dé-liaison que generate/stories, appliquée aux nouvelles questions générées.
    story_ids = {slot.story_id for slot in slots if slot.story_id}
    question_docs = [q.model_dump() for q in questions]
    for q in question_docs:
        if q.get("mapped_story_id") not in story_ids:
            q["mapped_story_id"] = None

    now = utcnow_with_timezone()
    user_query = {"$or": [{"user_id": str(current_user.id)}, {"user_id": ObjectId(current_user.id)}]}
    offer_query = {"$or": [{"offer_id": str(offer_id)}, {"offer_id": ObjectId(offer_id)}]}
    query = {"$and": [user_query, offer_query]}

    update_doc = {
        "$set": {
            "story_slots": [s.model_dump() for s in slots],
            "recruiter_pack": recruiter.model_dump(),
            "hm_pack": hm.model_dump(),
            "tech_pack": tech.model_dump(),
            "anticipated_questions": question_docs,
            "reverse_questions": [rq.model_dump() for rq in rev_questions],
            "practice_attempts": [],
            "updated_at": now,
        },
        "$setOnInsert": {
            "offer_id": str(offer_id),
            "user_id": user_id,
            "created_at": now,
        },
    }
    await db["interview_preps"].update_one(query, update_doc, upsert=True)
    updated = await db["interview_preps"].find_one(query)
    return await _prep_response(db, updated, user_id)


@interview_prep_router.post("/offers/{offer_id}/interview-prep/practice")
async def practice_answer_endpoint(
    offer_id: str,
    payload: PracticeAnswerRequest,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Score a practice answer to an anticipated question and append it to the attempt history."""
    await require_user_quota(db, current_user.id, ApiUsageAction.INTERVIEW_PREP)
    _, offer, evaluation = await _get_profile_and_offer(db, offer_id, str(current_user.id))

    existing = await _get_prep_or_empty(db, offer_id, str(current_user.id))
    question = next(
        (q for q in existing.get("anticipated_questions") or [] if q.get("id") == payload.question_id), None
    )
    if question is None:
        raise HTTPException(status_code=404, detail="Question introuvable dans le kit.")
    story = await get_bank_story(db, str(current_user.id), question.get("mapped_story_id"))

    attempt = await evaluate_practice_answer(
        db=db,
        user_id=str(current_user.id),
        offer=offer,
        evaluation=evaluation,
        question=AnticipatedQuestion(**question),
        answer=payload.answer,
        story=story,
    )

    user_query = {"$or": [{"user_id": str(current_user.id)}, {"user_id": ObjectId(current_user.id)}]}
    offer_query = {"$or": [{"offer_id": str(offer_id)}, {"offer_id": ObjectId(offer_id)}]}
    query = {"$and": [user_query, offer_query]}
    await db["interview_preps"].update_one(
        query,
        {"$push": {"practice_attempts": attempt.model_dump()}, "$set": {"updated_at": utcnow_with_timezone()}},
    )
    updated = await db["interview_preps"].find_one(query)
    return await _prep_response(db, updated, str(current_user.id))


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
    update_doc: Dict[str, Any] = {
        "$set": update_fields,
        "$setOnInsert": {
            "offer_id": str(offer_id),
            "user_id": str(current_user.id),
            "created_at": now,
        },
    }
    if payload.recruiter_pack is not None:
        update_fields["recruiter_pack"] = payload.recruiter_pack.model_dump()
    if payload.hm_pack is not None:
        update_fields["hm_pack"] = payload.hm_pack.model_dump()
    if payload.tech_pack is not None:
        update_fields["tech_pack"] = payload.tech_pack.model_dump()
    if payload.anticipated_questions is not None:
        update_fields["anticipated_questions"] = [q.model_dump() for q in payload.anticipated_questions]
        # Attempts on a removed question go with it.
        kept_ids = [q.id for q in payload.anticipated_questions]
        update_doc["$pull"] = {"practice_attempts": {"question_id": {"$nin": kept_ids}}}
    if payload.reverse_questions is not None:
        update_fields["reverse_questions"] = [rq.model_dump() for rq in payload.reverse_questions]

    await db["interview_preps"].update_one(query, update_doc, upsert=True)
    updated = await db["interview_preps"].find_one(query)
    return await _prep_response(db, updated, str(current_user.id))


@interview_prep_router.get("/offers/{offer_id}/interview-prep/export")
async def export_interview_prep(
    offer_id: str,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Export the complete prep notes in clean Markdown format."""
    user_id = str(current_user.id)
    prep_doc = await _get_prep_or_empty(db, offer_id, user_id)

    offer_doc = {}
    if ObjectId.is_valid(offer_id):
        offer_doc = await db["job_offers"].find_one({"_id": ObjectId(offer_id)}) or {}

    slots = await slots_with_stories(db, user_id, prep_doc.get("story_slots") or [])
    prep = InterviewPrep(**prep_doc)
    markdown_content = export_interview_prep_markdown(prep, offer_doc, slots)

    company_slug = "".join(c if c.isalnum() else "_" for c in offer_doc.get("company", "interview")).lower()
    return Response(
        content=markdown_content,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="prep_{company_slug}_{offer_id[:6]}.md"',
        },
    )


@interview_prep_router.put("/offers/{offer_id}/interview-prep/slots/{slot_id}")
async def update_interview_prep_slot(
    offer_id: str,
    slot_id: str,
    payload: UpdateStorySlotRequest,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Modifie une ligne du kit (histoire pointée, exigence, angle propre à l'offre).

    Choisir une histoire de la banque (`story_id`) passe la ligne en fit
    "manual" et remet l'angle à zéro, sauf si `angle` est envoyé dans le même
    appel. Détacher l'histoire (`story_id: null`) remet la ligne en manque
    (fit "gap", angle vidé, `angle` envoyé ignoré), comme la suppression d'une
    histoire de la banque. Envoyer `angle` seul marque la ligne comme modifiée
    à la main sans toucher à la banque.

    Seuls les champs changés de cette ligne sont écrits (`$[s]`) : une
    modification concurrente d'une autre ligne n'est jamais écrasée.
    """
    user_id = str(current_user.id)
    prep = await _get_prep_or_empty(db, offer_id, user_id)
    if not any(s.get("id") == slot_id for s in prep.get("story_slots") or []):
        raise HTTPException(status_code=404, detail="Ligne introuvable.")

    changes = payload.model_dump(exclude_unset=True)
    slot_changes: Dict[str, Any] = {}
    detaching = "story_id" in changes and changes["story_id"] is None

    if detaching:
        slot_changes.update(story_id=None, fit="gap", angle="", angle_edited=False)
    elif "story_id" in changes:
        story = await get_bank_story(db, user_id, changes["story_id"])
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

    set_doc: Dict[str, Any] = {f"story_slots.$[s].{field}": value for field, value in slot_changes.items()}
    set_doc["updated_at"] = utcnow_with_timezone()
    # Un identifiant `$[s]` inutilisé fait échouer l'update : pas d'array_filters sans champ de ligne.
    result = await db["interview_preps"].update_one(
        {"_id": prep["_id"], "story_slots.id": slot_id},
        {"$set": set_doc},
        array_filters=[{"s.id": slot_id}] if slot_changes else None,
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Ligne introuvable.")
    updated = await db["interview_preps"].find_one({"_id": prep["_id"]})
    return await _prep_response(db, updated, user_id)


@interview_prep_router.delete("/offers/{offer_id}/interview-prep/slots/{slot_id}")
async def delete_interview_prep_slot(
    offer_id: str,
    slot_id: str,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Retire une ligne du kit. N'affecte ni la banque ni les questions anticipées.

    `$pull` de cette seule ligne : les autres lignes ne sont jamais réécrites.
    """
    user_id = str(current_user.id)
    prep = await _get_prep_or_empty(db, offer_id, user_id)
    if not any(s.get("id") == slot_id for s in prep.get("story_slots") or []):
        raise HTTPException(status_code=404, detail="Ligne introuvable.")

    result = await db["interview_preps"].update_one(
        {"_id": prep["_id"], "story_slots.id": slot_id},
        {"$pull": {"story_slots": {"id": slot_id}}, "$set": {"updated_at": utcnow_with_timezone()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Ligne introuvable.")
    updated = await db["interview_preps"].find_one({"_id": prep["_id"]})
    return await _prep_response(db, updated, user_id)


@interview_prep_router.post("/offers/{offer_id}/interview-prep/slots/{slot_id}/write")
async def write_interview_prep_slot(
    offer_id: str,
    slot_id: str,
    request: Request,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Écrit par IA une histoire pour une ligne en manque (`fit == "gap"`) et l'ajoute à la banque.

    409 si la ligne n'est pas en manque : elle a déjà une adéquation (forte,
    partielle, transférable, manuelle) ou aucune expérience rattachée.

    L'appel IA dure 10 à 30 s : au retour, seule cette ligne est écrite, et
    seulement si elle est encore en manque sans histoire. Sinon (supprimée ou
    remplie entre-temps) 409, et l'histoire déjà écrite reste dans la banque.
    """
    user_id = str(current_user.id)
    prep = await _get_prep_or_empty(db, offer_id, user_id)
    slot = next((s for s in prep.get("story_slots") or [] if s.get("id") == slot_id), None)
    if slot is None:
        raise HTTPException(status_code=404, detail="Ligne introuvable.")

    if slot.get("fit") != "gap":
        raise HTTPException(status_code=409, detail="Cette ligne n'est pas en manque.")

    await require_user_quota(db, current_user.id, ApiUsageAction.INTERVIEW_PREP)
    profile, offer, evaluation = await _get_profile_and_offer(db, offer_id, user_id)

    written = await write_stories_for_requirements(
        db=db,
        user_id=user_id,
        profile=profile,
        offer=offer,
        evaluation=evaluation,
        picks=[RequirementPick(requirement=slot.get("requirement", ""), covered=True)],
    )
    new_slot, new_story = written[0]

    if await _generation_cancelled(request, "slot-write"):
        return Response(status_code=499)

    if new_story is not None:
        await db["star_stories"].insert_one(new_story.model_dump())

    result = await db["interview_preps"].update_one(
        {"_id": prep["_id"], "story_slots": {"$elemMatch": {"id": slot_id, "fit": "gap", "story_id": None}}},
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
    return await _prep_response(db, updated, user_id)


@interview_prep_router.post("/offers/{offer_id}/interview-prep/slots/{slot_id}/manual-story")
async def manual_story_interview_prep_slot(
    offer_id: str,
    slot_id: str,
    payload: StoryFacts,
    current_user: UserModel = Depends(get_current_user),
    db=Depends(get_database),
):
    """Écrit à la main une histoire pour une ligne du kit : pas d'IA, pas de quota.

    409 si la ligne a déjà une histoire (`story_id`) : il faut d'abord la
    détacher (PUT de la ligne avec `story_id: null`) avant d'en écrire une
    nouvelle à la main. Seule cette ligne est écrite, et seulement si elle
    est toujours sans histoire ; sinon 409, l'histoire insérée reste dans la
    banque.
    """
    user_id = str(current_user.id)
    prep = await _get_prep_or_empty(db, offer_id, user_id)
    slot = next((s for s in prep.get("story_slots") or [] if s.get("id") == slot_id), None)
    if slot is None:
        raise HTTPException(status_code=404, detail="Ligne introuvable.")

    if slot.get("story_id"):
        raise HTTPException(status_code=409, detail="Cette ligne a déjà une histoire.")

    profile, _, _ = await _get_profile_and_offer(db, offer_id, user_id)

    new_story = BankStory(
        **payload.model_dump(),
        user_id=user_id,
        origin=StoryOrigin(kind="manual", offer_id=str(offer_id)),
        experience=guess_experience(payload.situation, profile.get("experiences") or []),
    )
    await db["star_stories"].insert_one(new_story.model_dump())

    result = await db["interview_preps"].update_one(
        {"_id": prep["_id"], "story_slots": {"$elemMatch": {"id": slot_id, "story_id": None}}},
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
    return await _prep_response(db, updated, user_id)
