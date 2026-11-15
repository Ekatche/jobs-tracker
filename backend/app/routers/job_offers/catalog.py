import sys
from typing import List, Literal, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query

from ...auth import get_current_user
from ...database import get_database
from ...models import JobOfferResponse, UserModel
from ...services.company_profiles import COMPANY_SIZES, SECTORS
from ...services.offer_scoring.constants import RELEVANCE_LEVELS
from .pipeline import DEDUP_KEY_STAGE

router = APIRouter()


def _pkg():
    return sys.modules[__package__]


def _base_active_filter() -> dict:
    return {"$or": [{"is_deleted": {"$exists": False}}, {"is_deleted": False}]}


@router.get("/", response_model=List[JobOfferResponse])
async def get_job_offers(
    keywords: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    contract_type: Optional[str] = Query(None),
    work_mode: Optional[str] = Query(None),
    days_recent: Optional[int] = Query(None),
    interaction_status: Optional[str] = Query(None),
    only_saved: bool = Query(False),
    include_hidden: bool = Query(False),
    unseen_only: bool = Query(False),
    min_score: Optional[float] = Query(None),
    sort: Literal["relevance", "recent"] = Query("recent"),
    sector: Optional[List[Literal[*SECTORS]]] = Query(None),
    company_size: Optional[List[Literal[*COMPANY_SIZES]]] = Query(None),
    relevance_level: Optional[List[Literal[*RELEVANCE_LEVELS]]] = Query(None),
    limit: int = Query(16, ge=1, le=100),
    skip: int = Query(0, ge=0),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Récupère les offres d'emploi avec pagination, déduplication et statut d'interaction."""
    pkg = _pkg()
    try:
        match_filter, interaction_map, seen_map, should_return_empty = (
            await pkg.apply_user_interaction_filters(
                match_filter=_base_active_filter(),
                db=db,
                current_user=current_user,
                only_saved=only_saved,
                include_hidden=include_hidden,
                min_score=min_score,
                interaction_status=interaction_status,
                unseen_only=unseen_only,
            )
        )
        if should_return_empty:
            return []

        match_filter = pkg._apply_search_filters(
            match_filter,
            keywords=keywords,
            location=location,
            company=company,
            contract_type=contract_type,
            work_mode=work_mode,
            sector=sector,
            company_size=company_size,
            days_recent=days_recent,
            current_user=current_user,
            only_saved=only_saved,
            interaction_status=interaction_status,
        )

        pipeline = pkg._build_list_pipeline(
            match_filter,
            sort=sort,
            current_user=current_user,
            skip=skip,
            limit=limit,
            relevance_level=relevance_level,
        )
        offers = await db["job_offers"].aggregate(pipeline).to_list(length=None)

        page_offer_ids = [str(offer["_id"]) for offer in offers]
        eval_score_map: dict = {}
        if current_user and page_offer_ids:
            eval_docs = await db["offer_evaluations"].find(
                {"user_id": str(current_user.id), "offer_id": {"$in": page_offer_ids}},
                {"offer_id": 1, "score": 1},
            ).to_list(length=None)
            eval_score_map = {doc["offer_id"]: doc.get("score") for doc in eval_docs}

        formatted_offers = []
        for offer in offers:
            oid_str = str(offer["_id"])
            offer["id"] = oid_str
            del offer["_id"]
            offer.pop("evaluation_score", None)
            if current_user:
                offer["user_interaction"] = interaction_map.get(oid_str)
                offer["seen"] = seen_map.get(oid_str, False)
                if oid_str in eval_score_map:
                    offer["evaluation_score"] = eval_score_map[oid_str]
            else:
                offer["user_interaction"] = None
                offer["seen"] = False
            formatted_offers.append(offer)

        return formatted_offers
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {e}")


@router.get("/count/")
async def get_job_offers_count(
    keywords: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    contract_type: Optional[str] = Query(None),
    work_mode: Optional[str] = Query(None),
    days_recent: Optional[int] = Query(None),
    interaction_status: Optional[str] = Query(None),
    only_saved: bool = Query(False),
    include_hidden: bool = Query(False),
    unseen_only: bool = Query(False),
    min_score: Optional[float] = Query(None),
    sort: Literal["relevance", "recent"] = Query("recent"),
    sector: Optional[List[Literal[*SECTORS]]] = Query(None),
    company_size: Optional[List[Literal[*COMPANY_SIZES]]] = Query(None),
    relevance_level: Optional[List[Literal[*RELEVANCE_LEVELS]]] = Query(None),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Compte les offres d'emploi dédupliquées en tenant compte des filtres multi-tenant."""
    pkg = _pkg()
    try:
        match_filter, _, _, should_return_empty = await pkg.apply_user_interaction_filters(
            match_filter=_base_active_filter(),
            db=db,
            current_user=current_user,
            only_saved=only_saved,
            include_hidden=include_hidden,
            min_score=min_score,
            interaction_status=interaction_status,
            unseen_only=unseen_only,
        )
        if should_return_empty:
            return {"total": 0}

        match_filter = pkg._apply_search_filters(
            match_filter,
            keywords=keywords,
            location=location,
            company=company,
            contract_type=contract_type,
            work_mode=work_mode,
            sector=sector,
            company_size=company_size,
            days_recent=days_recent,
            current_user=current_user,
            only_saved=only_saved,
            interaction_status=interaction_status,
        )

        count_pipeline = [
            {"$match": match_filter},
            DEDUP_KEY_STAGE,
            {"$group": {"_id": "$dedup_key", "count": {"$sum": 1}}},
            {"$count": "total"},
        ]

        if current_user and relevance_level:
            count_pipeline[1:1] = [{"$sort": {"created_at": -1, "_id": -1}}]
            count_pipeline[-2:] = [
                {"$group": {"_id": "$dedup_key", "offer_id": {"$first": "$_id"}}},
                {"$project": {"_id": "$offer_id"}},
                *pkg.relevance_lookup_stages(str(current_user.id)),
                pkg._relevance_level_match(relevance_level),
                {"$count": "total"},
            ]

        result = await db["job_offers"].aggregate(count_pipeline).to_list(length=1)
        return {"total": result[0]["total"] if result else 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {e}")


@router.get("/{offer_id}", response_model=JobOfferResponse)
async def get_job_offer(
    offer_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Récupère une offre d'emploi par son ID avec état d'interaction personnalisé."""
    if not ObjectId.is_valid(offer_id):
        raise HTTPException(status_code=400, detail="ID invalide")

    offer = await db["job_offers"].find_one({"_id": ObjectId(offer_id)})
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")

    offer["id"] = str(offer["_id"])
    del offer["_id"]
    offer.pop("evaluation_score", None)

    if current_user:
        uid_str = str(current_user.id)
        oid_str = str(offer_id)
        interaction = await db["user_offer_interactions"].find_one(
            {"user_id": uid_str, "offer_id": oid_str}
        )
        offer["user_interaction"] = interaction.get("status") if interaction else None
        offer["seen"] = interaction.get("seen", False) if interaction else False

        evaluation = await db["offer_evaluations"].find_one(
            {"user_id": uid_str, "offer_id": oid_str}
        )
        if evaluation:
            offer["evaluation_score"] = evaluation.get("score")

        relevance = await db["offer_relevance"].find_one(
            {"user_id": uid_str, "offer_id": oid_str}
        )
        offer["failed_conditions"] = relevance.get("failed_conditions", []) if relevance else []
        offer["unknown_components"] = relevance.get("unknown_components", []) if relevance else []
        offer["relevance_level"] = relevance.get("level") if relevance else None
    else:
        offer["user_interaction"] = None
        offer["seen"] = False

    return offer
