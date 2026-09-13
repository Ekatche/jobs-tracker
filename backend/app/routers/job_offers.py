from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from bson import ObjectId
from datetime import datetime, timezone
from ..models import JobOfferResponse
from ..database import get_database
from ..services.normalization import normalize_city, normalize_company, extract_domain

job_offers_router = APIRouter(prefix="/job-offers", tags=["job-offers"])


@job_offers_router.get("/", response_model=List[JobOfferResponse])
async def get_job_offers(
    keywords: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    limit: int = Query(16, ge=1, le=100),
    skip: int = Query(0, ge=0),
    db=Depends(get_database),
):
    """Récupère les offres d'emploi avec pagination et déduplication"""
    try:
        collection = db["job_offers"]

        # ✅ ÉTAPE 1: Construire le filtre de base (exclure les supprimées)
        match_filter = {
            "$or": [{"is_deleted": {"$exists": False}}, {"is_deleted": False}]
        }

        # Ajouter les filtres de recherche
        if keywords:
            match_filter["$and"] = match_filter.get("$and", [])
            match_filter["$and"].append(
                {
                    "$or": [
                        {"poste": {"$regex": keywords, "$options": "i"}},
                        {"description": {"$regex": keywords, "$options": "i"}},
                        {"entreprise": {"$regex": keywords, "$options": "i"}},
                    ]
                }
            )

        if location:
            match_filter["localisation"] = {"$regex": location, "$options": "i"}

        if company:
            match_filter["entreprise"] = {"$regex": company, "$options": "i"}

        # ✅ ÉTAPE 2: Pipeline d'agrégation avec déduplication
        pipeline = [
            # Filtrer selon les critères
            {"$match": match_filter},
            # Trier d'abord par date de création descendante pour que $first prenne le plus récent
            {"$sort": {"created_at": -1}},
            # ✅ DÉDUPLICATION par groupe d'entreprise + poste + localisation
            {
                "$addFields": {
                    "dedup_key": {
                        "$ifNull": [
                            "$unique_key",
                            {
                                "$concat": [
                                    {"$toLower": {"$ifNull": ["$entreprise", ""]}},
                                    "|||",
                                    {"$toLower": {"$ifNull": ["$poste", ""]}},
                                    "|||",
                                    {"$toLower": {"$ifNull": ["$localisation", ""]}},
                                ]
                            },
                        ]
                    }
                }
            },
            # Grouper par clé de déduplication et garder le plus récent
            {
                "$group": {
                    "_id": "$dedup_key",
                    "offer": {"$first": "$$ROOT"},
                    "count": {"$sum": 1},
                }
            },
            # Récupérer l'offre originale
            {"$replaceRoot": {"newRoot": "$offer"}},
            # Supprimer le champ temporaire
            {"$unset": "dedup_key"},
            # ✅ ÉTAPE 3: Trier par date de création pour l'ordre final de pagination
            {"$sort": {"created_at": -1}},
            # ✅ ÉTAPE 4: Appliquer la pagination APRÈS déduplication
            {"$skip": skip},
            {"$limit": limit},
        ]

        # Exécuter la requête
        cursor = collection.aggregate(pipeline)
        offers = await cursor.to_list(length=None)

        # Formatter les résultats
        formatted_offers = []
        for offer in offers:
            offer["id"] = str(offer["_id"])
            del offer["_id"]
            formatted_offers.append(offer)

        return formatted_offers

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {e}")


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


@job_offers_router.patch("/{offer_id}/soft-delete")
async def soft_delete_job_offer(offer_id: str, db=Depends(get_database)):
    """Effectue un soft delete d'une offre d'emploi (marque comme supprimée)"""
    if not ObjectId.is_valid(offer_id):
        raise HTTPException(status_code=400, detail="ID invalide")

    offer = await db["job_offers"].find_one({"_id": ObjectId(offer_id)})

    # Vérifier que l'offre existe
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")

    # Vérifier si l'offre n'est pas déjà supprimée
    if offer.get("is_deleted", False):
        raise HTTPException(status_code=400, detail="Offre déjà supprimée")

    # Mettre à jour l'offre avec le soft delete
    update_fields = {
        "is_deleted": True,
        "deleted_date": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    result = await db["job_offers"].update_one(
        {"_id": ObjectId(offer_id)}, {"$set": update_fields}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=500, detail="Erreur lors de la suppression")

    # Récupérer l'offre mise à jour
    updated_offer = await db["job_offers"].find_one({"_id": ObjectId(offer_id)})
    updated_offer["id"] = str(updated_offer["_id"])
    del updated_offer["_id"]

    return {"message": "Offre marquée comme supprimée", "offer": updated_offer}


@job_offers_router.delete("/{offer_id}")
async def delete_job_offer(offer_id: str, db=Depends(get_database)):
    """Supprime une offre d'emploi"""
    if not ObjectId.is_valid(offer_id):
        raise HTTPException(status_code=400, detail="ID invalide")

    result = await db["job_offers"].delete_one({"_id": ObjectId(offer_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Offre non trouvée")

    return {"message": "Offre supprimée"}


@job_offers_router.post("/{offer_id}/regenerate-description")
async def regenerate_offer_description_endpoint(offer_id: str, db=Depends(get_database)):
    """Régénère la description d'une offre d'emploi (et gère les liens morts/expirés)"""
    if not ObjectId.is_valid(offer_id):
        raise HTTPException(status_code=400, detail="ID invalide")

    offer = await db["job_offers"].find_one({"_id": ObjectId(offer_id)})
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")

    from ..tasks.regenerate_descriptions import regenerate_single_offer

    res = await regenerate_single_offer(offer, db=db)
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error", "Erreur de régénération"))

    # Récupérer l'offre mise à jour
    updated_offer = await db["job_offers"].find_one({"_id": ObjectId(offer_id)})
    if updated_offer:
        updated_offer["id"] = str(updated_offer["_id"])
        del updated_offer["_id"]

    return {
        "message": "Description régénérée avec succès",
        "is_active": res.get("is_active", True),
        "status": res.get("status"),
        "description": res.get("description"),
        "offer": updated_offer,
    }


@job_offers_router.get("/stats/summary")
async def get_offers_stats(db=Depends(get_database)):
    """Récupère les statistiques des offres d'emploi"""

    # Total des offres
    total_offers = await db["job_offers"].count_documents({})

    # TOP WEBSITES - Pipeline simplifié
    website_pipeline = [
        {
            "$addFields": {
                "normalized_site": {
                    "$toLower": {
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
            }
        },
        {"$match": {"normalized_site": {"$nin": [None, ""]}}},
        {"$group": {"_id": "$normalized_site", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]

    # TOP COMPANIES - Traitement côté Python
    # Récupérer toutes les entreprises
    companies_cursor = db["job_offers"].find(
        {"entreprise": {"$exists": True, "$nin": [None, ""]}}, {"entreprise": 1}
    )
    companies_data = await companies_cursor.to_list(length=None)

    # Normaliser côté Python
    company_counts = {}
    for doc in companies_data:
        if doc.get("entreprise"):
            normalized = normalize_company(doc["entreprise"])
            company_counts[normalized] = company_counts.get(normalized, 0) + 1

    # Trier et limiter
    top_companies = [
        {"_id": company, "count": count}
        for company, count in sorted(
            company_counts.items(), key=lambda x: x[1], reverse=True
        )[:10]
    ]

    # TOP CITIES - Traitement côté Python
    # Récupérer toutes les localisations
    cities_cursor = db["job_offers"].find(
        {"localisation": {"$exists": True, "$nin": [None, ""]}}, {"localisation": 1}
    )
    cities_data = await cities_cursor.to_list(length=None)

    # Normaliser côté Python
    city_counts = {}
    for doc in cities_data:
        if doc.get("localisation"):
            normalized = normalize_city(doc["localisation"])
            city_counts[normalized] = city_counts.get(normalized, 0) + 1

    # Trier et limiter
    top_cities = [
        {"_id": city, "count": count}
        for city, count in sorted(
            city_counts.items(), key=lambda x: x[1], reverse=True
        )[:10]
    ]

    # Exécuter le pipeline pour les websites
    top_websites = await db["job_offers"].aggregate(website_pipeline).to_list(length=10)

    return {
        "total_offers": total_offers,
        "top_websites": top_websites,
        "top_companies": top_companies,
        "top_cities": top_cities,
    }


@job_offers_router.get("/count/")
async def get_job_offers_count(
    keywords: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    db=Depends(get_database),
):
    """Compte les offres d'emploi dédupliquées"""
    try:
        collection = db["job_offers"]

        # ✅ MÊME LOGIQUE: Construire le filtre de base
        match_filter = {
            "$or": [{"is_deleted": {"$exists": False}}, {"is_deleted": False}]
        }

        # Ajouter les filtres de recherche
        if keywords:
            match_filter["$and"] = match_filter.get("$and", [])
            match_filter["$and"].append(
                {
                    "$or": [
                        {"poste": {"$regex": keywords, "$options": "i"}},
                        {"description": {"$regex": keywords, "$options": "i"}},
                        {"entreprise": {"$regex": keywords, "$options": "i"}},
                    ]
                }
            )

        if location:
            match_filter["localisation"] = {"$regex": location, "$options": "i"}

        if company:
            match_filter["entreprise"] = {"$regex": company, "$options": "i"}

        # ✅ PIPELINE pour compter les offres dédupliquées
        count_pipeline = [
            {"$match": match_filter},
            # Déduplication
            {
                "$addFields": {
                    "dedup_key": {
                        "$concat": [
                            {"$toLower": {"$ifNull": ["$entreprise", ""]}},
                            "|||",
                            {"$toLower": {"$ifNull": ["$poste", ""]}},
                            "|||",
                            {"$toLower": {"$ifNull": ["$localisation", ""]}},
                        ]
                    }
                }
            },
            # Grouper par clé de déduplication
            {"$group": {"_id": "$dedup_key", "count": {"$sum": 1}}},
            # Compter le nombre de groupes uniques
            {"$count": "total"},
        ]

        cursor = collection.aggregate(count_pipeline)
        result = await cursor.to_list(length=1)

        total = result[0]["total"] if result else 0

        return {"total": total}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {e}")
