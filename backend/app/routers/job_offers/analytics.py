import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, Query

from ...auth import get_current_user
from ...database import get_database
from ...models import CollectionScheduleResponse, UserModel, UserOfferInteractionResponse

router = APIRouter()


def _pkg():
    return sys.modules[__package__]


def _top_websites_pipeline() -> list[dict]:
    domain_expr = {
        "$arrayElemAt": [
            {"$split": [{"$arrayElemAt": [{"$split": ["$url", "://"]}, 1]}, "/"]},
            0,
        ]
    }
    stripped = {
        "$cond": {
            "if": {"$regexMatch": {"input": "$$domain", "regex": "^www\\."}},
            "then": {"$substr": ["$$domain", 4, -1]},
            "else": "$$domain",
        }
    }
    return [
        {
            "$addFields": {
                "normalized_site": {"$toLower": {"$let": {"vars": {"domain": domain_expr}, "in": stripped}}}
            }
        },
        {"$match": {"normalized_site": {"$nin": [None, ""]}}},
        {"$group": {"_id": "$normalized_site", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]


async def _aggregate_normalized_top(db, field: str, normalizer) -> list[dict]:
    cursor = db["job_offers"].find({field: {"$exists": True, "$nin": [None, ""]}}, {field: 1})
    docs = await cursor.to_list(length=None)
    counts: dict[str, int] = {}
    for doc in docs:
        if doc.get(field):
            normalized = normalizer(doc[field])
            counts[normalized] = counts.get(normalized, 0) + 1
    return [
        {"_id": name, "count": count}
        for name, count in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10]
    ]


@router.get("/user/interactions", response_model=List[UserOfferInteractionResponse])
async def list_user_offer_interactions(
    status: Optional[str] = Query(None),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Liste les interactions d'offres de l'utilisateur connecté (saved, hidden, applied, etc.)."""
    query: dict[str, Any] = {"user_id": str(current_user.id)}
    if status:
        query["status"] = status

    interactions = await db["user_offer_interactions"].find(query).sort("updated_at", -1).to_list(
        length=200
    )
    result = []
    for doc in interactions:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
        result.append(UserOfferInteractionResponse(**doc))
    return result


@router.get("/analytics/skill-gaps")
async def get_jd_skill_gaps(
    min_score: float = Query(0.0, ge=0.0, le=5.0),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
) -> Dict[str, Any]:
    """Aggregate recurring missing JD requirements across the user's offer evaluations."""
    user_id_str = str(current_user.id)
    user_id_filter: List[Dict[str, Any]] = [{"user_id": user_id_str}]
    if ObjectId.is_valid(user_id_str):
        user_id_filter.append({"user_id": ObjectId(user_id_str)})

    evals = await db["offer_evaluations"].find({"$or": user_id_filter}).to_list(length=5000)
    return _pkg().compute_jd_skill_gaps(evals, min_score=min_score)


@router.get("/stats/summary")
async def get_offers_stats(db=Depends(get_database)):
    """Récupère les statistiques des offres d'emploi."""
    pkg = _pkg()
    total_offers = await db["job_offers"].count_documents({})
    top_companies = await _aggregate_normalized_top(db, "entreprise", pkg.normalize_company)
    top_cities = await _aggregate_normalized_top(db, "localisation", pkg.normalize_city)
    top_websites = await db["job_offers"].aggregate(_top_websites_pipeline()).to_list(length=10)

    return {
        "total_offers": total_offers,
        "top_websites": top_websites,
        "top_companies": top_companies,
        "top_cities": top_cities,
    }


@router.get("/collection/schedule", response_model=CollectionScheduleResponse)
async def get_collection_schedule(
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Prochaine collecte d'offres, et profil créé depuis la dernière.

    `candidate_profile` n'a pas de `created_at` : l'horodatage de son `_id` en tient lieu.
    """
    pkg = _pkg()
    now = datetime.now(timezone.utc)
    profile = await db["candidate_profile"].find_one(
        {"user_id": ObjectId(str(current_user.id))}, {"_id": 1}
    )
    awaiting = bool(
        profile
        and isinstance(profile["_id"], ObjectId)
        and profile["_id"].generation_time > pkg.previous_collection_at(now)
    )
    return CollectionScheduleResponse(
        next_collection_at=pkg.next_collection_at(now),
        awaiting_first_collection=awaiting,
    )
