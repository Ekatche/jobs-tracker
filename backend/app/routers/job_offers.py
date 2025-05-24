from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from bson import ObjectId
from datetime import datetime, timedelta, timezone

from ..models import JobOfferResponse
from ..database import get_database

job_offers_router = APIRouter(prefix="/job-offers", tags=["job-offers"])


@job_offers_router.get("/", response_model=List[JobOfferResponse])
async def get_job_offers(
    keywords: Optional[str] = Query(None, description="Mots-clés à rechercher"),
    location: Optional[str] = Query(None, description="Localisation"),
    company: Optional[str] = Query(None, description="Entreprise"),
    limit: int = Query(50, le=100),
    skip: int = Query(0, ge=0),
    db=Depends(get_database),
):
    """Récupère les offres d'emploi avec filtres optionnels"""
    query_filter = {}

    if keywords:
        query_filter["poste"] = {"$regex": keywords, "$options": "i"}
    if location:
        query_filter["localisation"] = {"$regex": location, "$options": "i"}
    if company:
        query_filter["entreprise"] = {"$regex": company, "$options": "i"}

    cursor = (
        db["job_offers"]
        .find(query_filter)
        .skip(skip)
        .limit(limit)
        .sort("created_at", -1)
    )
    offers = await cursor.to_list(length=limit)

    for offer in offers:
        offer["id"] = str(offer["_id"])
        del offer["_id"]

    return offers


@job_offers_router.get("/{offer_id}", response_model=JobOfferResponse)
async def get_job_offer(offer_id: str, db=Depends(get_database)):
    """Récupère une offre d'emploi par son ID"""
    if not ObjectId.is_valid(offer_id):
        raise HTTPException(status_code=400, detail="ID invalide")

    offer = await db["job_offers"].find_one({"_id": ObjectId(offer_id)})
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")

    offer["id"] = str(offer["_id"])
    del offer["_id"]
    return offer


@job_offers_router.delete("/{offer_id}")
async def delete_job_offer(offer_id: str, db=Depends(get_database)):
    """Supprime une offre d'emploi"""
    if not ObjectId.is_valid(offer_id):
        raise HTTPException(status_code=400, detail="ID invalide")

    result = await db["job_offers"].delete_one({"_id": ObjectId(offer_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Offre non trouvée")

    return {"message": "Offre supprimée"}


@job_offers_router.get("/stats/summary")
async def get_offers_stats(db=Depends(get_database)):
    """Récupère les statistiques des offres d'emploi"""
    total_offers = await db["job_offers"].count_documents({})
    recent_offers = await db["job_offers"].count_documents(
        {"created_at": {"$gte": datetime.now(timezone.utc) - timedelta(days=7)}}
    )

    pipeline = [
        {
            "$addFields": {
                "site": {
                    "$let": {
                        "vars": {
                            "domain": {
                                "$arrayElemAt": [
                                    {
                                        "$split": [
                                            {
                                                "$arrayElemAt": [
                                                    {"$split": ["$url", "://"]},
                                                    1,
                                                ]
                                            },
                                            "/",
                                        ]
                                    },
                                    0,
                                ]
                            }
                        },
                        "in": {
                            "$cond": {
                                "if": {
                                    "$regexMatch": {
                                        "input": "$$domain",
                                        "regex": "^www\\.",
                                    }
                                },
                                "then": {"$substr": ["$$domain", 4, -1]},
                                "else": "$$domain",
                            }
                        },
                    }
                }
            }
        },
        {"$group": {"_id": "$site", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]
    top_companies = await db["job_offers"].aggregate(pipeline).to_list(length=10)

    return {
        "total_offers": total_offers,
        "recent_offers": recent_offers,
        "top_companies": top_companies,
    }
