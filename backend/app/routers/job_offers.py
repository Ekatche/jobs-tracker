import re
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from ..models import (
    JobOfferResponse,
    OfferEvaluationResponse,
    UserModel,
    UserOfferInteractionRequest,
    UserOfferInteractionResponse,
)
from ..database import get_database
from ..auth import get_current_user, get_current_user_optional
from ..services.normalization import normalize_city, normalize_company
from ..services.evaluation.evaluator import evaluate_offer_two_pass

job_offers_router = APIRouter(prefix="/job-offers", tags=["job-offers"])


GENERIC_ROLE_MODIFIERS = {
    "responsable",
    "directeur",
    "directrice",
    "chef",
    "manager",
    "charge",
    "chargée",
    "chargee",
    "assistant",
    "assistante",
    "coordinateur",
    "coordinatrice",
    "consultant",
    "consultante",
    "junior",
    "senior",
    "lead",
    "head",
    "officer",
    "analyst",
    "analyste",
    "espace",
    "pole",
    "pôle",
    "service",
    "departement",
    "secteur",
    "centre",
    "hub",
    "unite",
    "unité",
    "metier",
    "métier",
    "specialise",
    "spécialisé",
    "specialisee",
    "spécialisée",
    "permanent",
    "permanente",
}

STOPWORDS = {
    "de",
    "du",
    "des",
    "le",
    "la",
    "les",
    "un",
    "une",
    "en",
    "pour",
    "et",
    "ou",
    "au",
    "aux",
    "par",
    "sur",
    "dans",
    "avec",
    "sans",
    "sous",
    "chez",
    "d",
    "l",
    "h",
    "f",
    "a",
    "à",
}


def _stem_keyword(w: str) -> str:
    """Racine lexicale tolérante aux accords de genre/nombre et pluriel."""
    if w.startswith("animat"):
        return "animat"
    if w.startswith("educat") or w.startswith("éducat"):
        return r"(?:éducat|educat)"
    if w.startswith("jeun"):
        return "jeun"
    if w.startswith("enfant"):
        return "enfant"
    if w.startswith("periscol") or w.startswith("périscol"):
        return r"(?:périscol|periscol)"
    if w.startswith("developp") or w.startswith("développ"):
        return r"(?:développ|developp)"
    return re.escape(w)


def _build_keywords_filter(keywords: str) -> dict:
    """Construit un filtre de recherche tolérant, précis et sans dilution par des mots génériques."""
    clean_kw = keywords.strip()
    if not clean_kw:
        return {}

    if "|" in clean_kw:
        return {
            "$or": [
                {"poste": {"$regex": clean_kw, "$options": "i"}},
                {"description": {"$regex": clean_kw, "$options": "i"}},
                {"entreprise": {"$regex": clean_kw, "$options": "i"}},
                {"competences_cles": {"$regex": clean_kw, "$options": "i"}},
            ]
        }

    words = re.findall(r"[a-zA-ZÀ-ÿ0-9]+", clean_kw.lower())
    meaningful = [w for w in words if len(w) >= 2 and w not in STOPWORDS]
    if not meaningful:
        return {"poste": {"$regex": re.escape(clean_kw), "$options": "i"}}

    domain_words = [w for w in meaningful if w not in GENERIC_ROLE_MODIFIERS]
    modifier_words = [w for w in meaningful if w in GENERIC_ROLE_MODIFIERS]

    or_branches = []

    # 1. Correspondance exacte sur le titre du poste
    or_branches.append({"poste": {"$regex": re.escape(clean_kw), "$options": "i"}})

    if domain_words:
        domain_patterns = [_stem_keyword(w) for w in domain_words]

        # 2. Présence de TOUS les termes du domaine dans l'intitulé ou les compétences
        domain_and_poste = [
            {
                "$or": [
                    {"poste": {"$regex": dp, "$options": "i"}},
                    {"competences_cles": {"$regex": dp, "$options": "i"}},
                ]
            }
            for dp in domain_patterns
        ]
        or_branches.append({"$and": domain_and_poste})

        # 3. Si des modificateurs de rôle sont aussi présents (ex: 'responsable' + 'jeunesse'),
        # on requiert la présence conjointe des mots du domaine et du rôle
        if modifier_words:
            combined_and = [
                {
                    "$or": [
                        {"poste": {"$regex": _stem_keyword(m), "$options": "i"}},
                        {"description": {"$regex": _stem_keyword(m), "$options": "i"}},
                    ]
                }
                for m in modifier_words
            ]
            combined_and.extend(
                [
                    {
                        "$or": [
                            {"poste": {"$regex": dp, "$options": "i"}},
                            {"competences_cles": {"$regex": dp, "$options": "i"}},
                        ]
                    }
                    for dp in domain_patterns
                ]
            )
            or_branches.append({"$and": combined_and})
    else:
        # Aucun terme de domaine spécifique, que des modificateurs (ex: recherche "responsable")
        mod_patterns = [_stem_keyword(w) for w in modifier_words]
        or_branches.append({"poste": {"$regex": "|".join(mod_patterns), "$options": "i"}})

    return {"$or": or_branches}


async def apply_user_interaction_filters(
    match_filter: dict,
    db,
    current_user: Optional[UserModel],
    only_saved: bool = False,
    include_hidden: bool = False,
    min_score: Optional[float] = None,
    interaction_status: Optional[str] = None,
) -> tuple[dict, dict, bool]:
    """
    Applique les filtres multi-tenant (masquées, sauvegardées, statut d'interaction, score IA minimum) au filtre MongoDB.
    Renvoie (match_filter_mis_à_jour, interaction_map, should_return_empty).
    """
    target_status = "saved" if only_saved else interaction_status

    interaction_map = {}
    if not current_user:
        if target_status or min_score is not None:
            return match_filter, interaction_map, True
        return match_filter, interaction_map, False

    user_id_str = str(current_user.id)
    user_interactions = await db["user_offer_interactions"].find({"user_id": user_id_str}).to_list(length=None)
    interaction_map = {doc["offer_id"]: doc.get("status") for doc in user_interactions}

    allowed_oids = None

    # 1. Filtre par statut d'interaction (saved, applied, etc.)
    if target_status:
        matching_oids = [
            ObjectId(oid)
            for oid, st in interaction_map.items()
            if st == target_status and ObjectId.is_valid(oid)
        ]
        if not matching_oids:
            return match_filter, interaction_map, True
        allowed_oids = set(matching_oids)

    # 2. Filtre par score IA minimum (Two-Pass)
    if min_score is not None:
        evals = await db["offer_evaluations"].find(
            {"user_id": user_id_str, "score": {"$gte": min_score}},
            {"offer_id": 1},
        ).to_list(length=None)
        score_oids = [
            ObjectId(doc["offer_id"])
            for doc in evals
            if doc.get("offer_id") and ObjectId.is_valid(doc["offer_id"])
        ]
        if not score_oids:
            return match_filter, interaction_map, True
        if allowed_oids is None:
            allowed_oids = set(score_oids)
        else:
            allowed_oids = allowed_oids.intersection(set(score_oids))
            if not allowed_oids:
                return match_filter, interaction_map, True

    # 3. Exclusion des offres masquées par l'utilisateur
    excluded_oids = set()
    if not include_hidden and target_status != "hidden":
        for oid, st in interaction_map.items():
            if st == "hidden" and ObjectId.is_valid(oid):
                excluded_oids.add(ObjectId(oid))

    if allowed_oids is not None:
        allowed_oids = allowed_oids - excluded_oids
        if not allowed_oids:
            return match_filter, interaction_map, True
        match_filter["_id"] = {"$in": list(allowed_oids)}
    elif excluded_oids:
        match_filter["_id"] = {"$nin": list(excluded_oids)}

    return match_filter, interaction_map, False


@job_offers_router.get("/", response_model=List[JobOfferResponse])
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
    min_score: Optional[float] = Query(None),
    limit: int = Query(16, ge=1, le=100),
    skip: int = Query(0, ge=0),
    db=Depends(get_database),
    current_user: Optional[UserModel] = Depends(get_current_user_optional),
):
    """Récupère les offres d'emploi avec pagination, déduplication et statut d'interaction multi-tenant."""
    try:
        collection = db["job_offers"]

        # ✅ ÉTAPE 1: Construire le filtre de base (exclure les supprimées globales)
        match_filter = {
            "$or": [{"is_deleted": {"$exists": False}}, {"is_deleted": False}]
        }

        # Multi-tenant user filters
        match_filter, interaction_map, should_return_empty = await apply_user_interaction_filters(
            match_filter=match_filter,
            db=db,
            current_user=current_user,
            only_saved=only_saved,
            include_hidden=include_hidden,
            min_score=min_score,
            interaction_status=interaction_status,
        )
        if should_return_empty:
            return []

        # Ajouter les filtres de recherche
        if keywords:
            kw_filter = _build_keywords_filter(keywords)
            if kw_filter:
                match_filter["$and"] = match_filter.get("$and", [])
                match_filter["$and"].append(kw_filter)

        if location:
            match_filter["localisation"] = {"$regex": location, "$options": "i"}

        if company:
            match_filter["entreprise"] = {"$regex": company, "$options": "i"}

        if contract_type:
            match_filter["type_contrat"] = {"$regex": contract_type, "$options": "i"}

        if work_mode:
            match_filter["mode_travail"] = {"$regex": work_mode, "$options": "i"}

        if days_recent and days_recent > 0:
            threshold_dt = datetime.now(timezone.utc) - timedelta(days=days_recent)
            iso_str = threshold_dt.isoformat()
            match_filter["$and"] = match_filter.get("$and", [])
            match_filter["$and"].append(
                {
                    "$or": [
                        {"created_at": {"$gte": threshold_dt}},
                        {"created_at": {"$gte": iso_str}},
                    ]
                }
            )

        # ✅ ÉTAPE 2: Pipeline d'agrégation avec déduplication et tri déterministe (tiebreaker _id)
        pipeline = [
            {"$match": match_filter},
            {"$sort": {"created_at": -1, "_id": -1}},
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
            {
                "$group": {
                    "_id": "$dedup_key",
                    "offer": {"$first": "$$ROOT"},
                    "count": {"$sum": 1},
                }
            },
            {"$replaceRoot": {"newRoot": "$offer"}},
            {"$unset": "dedup_key"},
            {"$sort": {"created_at": -1, "_id": -1}},
            {"$skip": skip},
            {"$limit": limit},
        ]

        cursor = collection.aggregate(pipeline)
        offers = await cursor.to_list(length=None)

        # Récupérer les scores d'évaluation pour la page
        page_offer_ids = [str(offer["_id"]) for offer in offers]
        eval_score_map = {}
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
            if current_user:
                offer["user_interaction"] = interaction_map.get(oid_str)
                if oid_str in eval_score_map:
                    offer["evaluation_score"] = eval_score_map[oid_str]
            else:
                offer["user_interaction"] = None
            formatted_offers.append(offer)

        return formatted_offers

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {e}")


@job_offers_router.get("/user/interactions", response_model=List[UserOfferInteractionResponse])
async def list_user_offer_interactions(
    status: Optional[str] = Query(None),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Liste les interactions d'offres de l'utilisateur connecté (saved, hidden, applied, etc.)."""
    query = {"user_id": str(current_user.id)}
    if status:
        query["status"] = status

    cursor = db["user_offer_interactions"].find(query).sort("updated_at", -1)
    interactions = await cursor.to_list(length=200)
    result = []
    for doc in interactions:
        doc["id"] = str(doc["_id"])
        del doc["_id"]
        result.append(UserOfferInteractionResponse(**doc))
    return result


@job_offers_router.get("/{offer_id}", response_model=JobOfferResponse)
async def get_job_offer(
    offer_id: str,
    db=Depends(get_database),
    current_user: Optional[UserModel] = Depends(get_current_user_optional),
):
    """Récupère une offre d'emploi par son ID avec état d'interaction personnalisé"""
    if not ObjectId.is_valid(offer_id):
        raise HTTPException(status_code=400, detail="ID invalide")

    offer = await db["job_offers"].find_one({"_id": ObjectId(offer_id)})
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")

    offer["id"] = str(offer["_id"])
    del offer["_id"]

    if current_user:
        interaction = await db["user_offer_interactions"].find_one({
            "user_id": str(current_user.id),
            "offer_id": str(offer_id),
        })
        offer["user_interaction"] = interaction.get("status") if interaction else None

        evaluation = await db["offer_evaluations"].find_one({
            "user_id": str(current_user.id),
            "offer_id": str(offer_id),
        })
        if evaluation:
            offer["evaluation_score"] = evaluation.get("score")
    else:
        offer["user_interaction"] = None

    return offer


@job_offers_router.post("/{offer_id}/interaction", response_model=UserOfferInteractionResponse)
async def set_user_offer_interaction(
    offer_id: str,
    payload: UserOfferInteractionRequest,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Enregistre ou met à jour l'interaction personnelle d'un candidat sur une offre (saved, hidden, applied, none)."""
    if not ObjectId.is_valid(offer_id):
        raise HTTPException(status_code=400, detail="ID d'offre invalide")

    offer = await db["job_offers"].find_one({"_id": ObjectId(offer_id)})
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")

    now = datetime.now(timezone.utc)
    user_id_str = str(current_user.id)
    filter_query = {"user_id": user_id_str, "offer_id": str(offer_id)}

    if payload.status == "none":
        await db["user_offer_interactions"].delete_many(filter_query)
        return UserOfferInteractionResponse(
            user_id=user_id_str,
            offer_id=str(offer_id),
            status="none",
            notes=payload.notes,
            created_at=now,
            updated_at=now,
        )

    update_doc = {
        "$set": {
            "status": payload.status,
            "notes": payload.notes,
            "updated_at": now,
        },
        "$setOnInsert": {
            "created_at": now,
        },
    }
    await db["user_offer_interactions"].update_one(filter_query, update_doc, upsert=True)

    interaction_doc = await db["user_offer_interactions"].find_one(filter_query)
    if interaction_doc:
        interaction_doc["id"] = str(interaction_doc["_id"])
        del interaction_doc["_id"]
        return UserOfferInteractionResponse(**interaction_doc)

    return UserOfferInteractionResponse(
        user_id=user_id_str,
        offer_id=str(offer_id),
        status=payload.status,
        notes=payload.notes,
        created_at=now,
        updated_at=now,
    )


@job_offers_router.get("/{offer_id}/interaction", response_model=UserOfferInteractionResponse)
async def get_user_offer_interaction(
    offer_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Récupère l'état d'interaction de l'utilisateur connecté pour une offre donnée."""
    if not ObjectId.is_valid(offer_id):
        raise HTTPException(status_code=400, detail="ID d'offre invalide")

    interaction_doc = await db["user_offer_interactions"].find_one({
        "user_id": str(current_user.id),
        "offer_id": str(offer_id),
    })

    now = datetime.now(timezone.utc)
    if not interaction_doc:
        return UserOfferInteractionResponse(
            user_id=str(current_user.id),
            offer_id=str(offer_id),
            status="none",
            notes=None,
            created_at=now,
            updated_at=now,
        )

    interaction_doc["id"] = str(interaction_doc["_id"])
    del interaction_doc["_id"]
    return UserOfferInteractionResponse(**interaction_doc)


@job_offers_router.post("/{offer_id}/evaluate", response_model=OfferEvaluationResponse)
async def evaluate_job_offer_endpoint(
    offer_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Déclenche l'évaluation Two-Pass de l'offre pour le candidat connecté"""
    if not ObjectId.is_valid(offer_id):
        raise HTTPException(status_code=400, detail="ID d'offre invalide")

    evaluation = await evaluate_offer_two_pass(
        db=db,
        user_id=str(current_user.id),
        offer_id=str(offer_id),
    )
    result = evaluation.model_dump()
    if "_id" in result:
        result["id"] = str(result["_id"])
    elif not result.get("id"):
        result["id"] = f"{current_user.id}_{offer_id}"
    return result


@job_offers_router.get("/{offer_id}/evaluation", response_model=OfferEvaluationResponse)
async def get_job_offer_evaluation_endpoint(
    offer_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Récupère l'évaluation détaillée associée au couple (offer_id, user_id)"""
    if not ObjectId.is_valid(offer_id):
        raise HTTPException(status_code=400, detail="ID d'offre invalide")

    evaluation_doc = await db["offer_evaluations"].find_one({
        "user_id": str(current_user.id),
        "offer_id": str(offer_id),
    })
    if not evaluation_doc:
        raise HTTPException(
            status_code=404,
            detail="Aucune évaluation trouvée pour cette offre et cet utilisateur",
        )

    if "_id" in evaluation_doc:
        evaluation_doc["id"] = str(evaluation_doc["_id"])
    return evaluation_doc


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
    contract_type: Optional[str] = Query(None),
    work_mode: Optional[str] = Query(None),
    days_recent: Optional[int] = Query(None),
    interaction_status: Optional[str] = Query(None),
    only_saved: bool = Query(False),
    include_hidden: bool = Query(False),
    min_score: Optional[float] = Query(None),
    db=Depends(get_database),
    current_user: Optional[UserModel] = Depends(get_current_user_optional),
):
    """Compte les offres d'emploi dédupliquées en tenant compte des filtres multi-tenant."""
    try:
        collection = db["job_offers"]

        # ✅ MÊME LOGIQUE: Construire le filtre de base
        match_filter = {
            "$or": [{"is_deleted": {"$exists": False}}, {"is_deleted": False}]
        }

        # Multi-tenant user filters
        match_filter, _, should_return_empty = await apply_user_interaction_filters(
            match_filter=match_filter,
            db=db,
            current_user=current_user,
            only_saved=only_saved,
            include_hidden=include_hidden,
            min_score=min_score,
            interaction_status=interaction_status,
        )
        if should_return_empty:
            return {"total": 0}

        # Ajouter les filtres de recherche
        if keywords:
            kw_filter = _build_keywords_filter(keywords)
            if kw_filter:
                match_filter["$and"] = match_filter.get("$and", [])
                match_filter["$and"].append(kw_filter)

        if location:
            match_filter["localisation"] = {"$regex": location, "$options": "i"}

        if company:
            match_filter["entreprise"] = {"$regex": company, "$options": "i"}

        if contract_type:
            match_filter["type_contrat"] = {"$regex": contract_type, "$options": "i"}

        if work_mode:
            match_filter["mode_travail"] = {"$regex": work_mode, "$options": "i"}

        if days_recent and days_recent > 0:
            threshold_dt = datetime.now(timezone.utc) - timedelta(days=days_recent)
            iso_str = threshold_dt.isoformat()
            match_filter["$and"] = match_filter.get("$and", [])
            match_filter["$and"].append(
                {
                    "$or": [
                        {"created_at": {"$gte": threshold_dt}},
                        {"created_at": {"$gte": iso_str}},
                    ]
                }
            )

        # ✅ PIPELINE pour compter les offres dédupliquées (synchronisé avec get_job_offers)
        count_pipeline = [
            {"$match": match_filter},
            # Déduplication
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
