import inspect
import logging
import re
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Literal, Optional
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from ..models import (
    JobOfferResponse,
    OfferEvaluationResponse,
    UserModel,
    UserOfferInteractionRequest,
    UserOfferInteractionResponse,
    SeenStatusRequest,
)
from ..database import get_database
from ..auth import get_current_admin_user, get_current_user
from ..services.company_profiles import COMPANY_SIZES, SECTORS
from ..services.normalization import normalize_city, normalize_company
from ..services.evaluation.evaluator import evaluate_offer_two_pass
from ..tasks.clean_job_offers import safe_delete_or_expire_offer

logger = logging.getLogger(__name__)

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
        # Une alternance de plusieurs métiers (ex: filtre "selon mon profil" avec
        # plusieurs rôles) doit bénéficier du même tolérant matching (stemming,
        # mots de domaine) que chaque rôle pris seul, pas d'un match de phrase
        # exacte qui échoue dès que l'intitulé réel diffère légèrement.
        sub_filters = [
            _build_keywords_filter(term.strip())
            for term in clean_kw.split("|")
            if term.strip()
        ]
        sub_filters = [f for f in sub_filters if f]
        if not sub_filters:
            return {}
        if len(sub_filters) == 1:
            return sub_filters[0]
        return {"$or": sub_filters}

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


def _build_contract_type_filter(contract_type: str) -> dict:
    """Construit le filtre de contrat.

    Pour les recherches de contrats standards (CDI, CDD, Freelance, profile_targeted) :
    inclut le contrat recherché ET les offres à contrat 'Non spécifié' (ou absent),
    tout en excluant les stages et alternances.
    Pour une recherche ciblant explicitement 'Stage' ou 'Alternance' :
    filtre uniquement sur ces contrats.
    """
    c_lower = contract_type.lower()
    if ("stage" in c_lower or "alternance" in c_lower) and "cdi" not in c_lower and "cdd" not in c_lower:
        return {"type_contrat": {"$regex": contract_type, "$options": "i"}}

    return {
        "$and": [
            {
                "$or": [
                    {"type_contrat": {"$regex": contract_type, "$options": "i"}},
                    {"type_contrat": "Non spécifié"},
                    {"type_contrat": None},
                    {"type_contrat": {"$exists": False}},
                ]
            },
            {"type_contrat": {"$not": {"$regex": "stage|alternance", "$options": "i"}}},
        ]
    }


def _build_sector_filter(sector: List[str]) -> dict:
    """Filtre par secteur(s) (taxonomie `SECTORS`) : plusieurs valeurs se combinent en $in."""
    return {"sector": {"$in": sector}}


def _build_company_size_filter(company_size: List[str]) -> dict:
    """Filtre par taille(s) d'entreprise (taxonomie `COMPANY_SIZES`) : plusieurs valeurs se combinent en $in."""
    return {"company_size": {"$in": company_size}}


def relevance_lookup_stages(user_id: str) -> list[dict]:
    """Étapes d'agrégation qui rattachent à chaque offre le score de pertinence hybride
    de l'utilisateur courant (Task 6, collection `offer_relevance`, un document par
    (user_id, offer_id)).

    Une offre attachée sans document `offer_relevance` — gardée par le garde-fou
    d'interaction après un filtre dur, attachée avant le premier rematch, ou passée
    pendant une panne d'embedding — n'est jamais masquée : elle obtient `_score_sort`
    à -1 (reléguée en fin de tri par pertinence) et `failed_conditions` vide.
    """
    return [
        {"$addFields": {"_oid_str": {"$toString": "$_id"}}},
        {
            "$lookup": {
                "from": "offer_relevance",
                "localField": "_oid_str",
                "foreignField": "offer_id",
                "pipeline": [
                    {"$match": {"user_id": user_id}},
                    {"$project": {"_id": 0, "score": 1, "failed_conditions": 1}},
                ],
                "as": "_relevance",
            }
        },
        {"$addFields": {"_relevance": {"$arrayElemAt": ["$_relevance", 0]}}},
        {"$addFields": {"_score_sort": {"$ifNull": ["$_relevance.score", -1]}}},
    ]


def restrict_to_profile_offers(
    match_filter: dict,
    current_user: Optional[UserModel],
    only_saved: bool = False,
    interaction_status: Optional[str] = None,
) -> dict:
    """Un utilisateur connecté ne voit que les offres rattachées à son profil.

    Exception : les vues Favoris / par statut listent déjà les seules offres
    de l'utilisateur, y compris celles sauvegardées hors de son profil.
    """
    if current_user and not only_saved and not interaction_status:
        match_filter["matched_user_ids"] = str(current_user.id)
    return match_filter


async def apply_user_interaction_filters(
    match_filter: dict,
    db,
    current_user: Optional[UserModel],
    only_saved: bool = False,
    include_hidden: bool = False,
    min_score: Optional[float] = None,
    interaction_status: Optional[str] = None,
    unseen_only: bool = False,
) -> tuple[dict, dict, dict, bool]:
    """
    Applique les filtres multi-tenant (masquées, sauvegardées, statut d'interaction, score IA minimum, non vues) au filtre MongoDB.
    Renvoie (match_filter_mis_à_jour, interaction_map, seen_map, should_return_empty).
    """
    target_status = "saved" if only_saved else interaction_status

    interaction_map = {}
    seen_map = {}
    if not current_user:
        if target_status or min_score is not None:
            return match_filter, interaction_map, seen_map, True
        return match_filter, interaction_map, seen_map, False

    user_id_str = str(current_user.id)
    user_interactions = await db["user_offer_interactions"].find({"user_id": user_id_str}).to_list(length=None)
    interaction_map = {doc["offer_id"]: doc.get("status") for doc in user_interactions}
    seen_map = {doc["offer_id"]: doc.get("seen", False) for doc in user_interactions}

    # Si filtrage par statut "applied", inclure également les offres issues de la collection applications
    if target_status == "applied":
        user_match = [user_id_str]
        if ObjectId.is_valid(user_id_str):
            user_match.append(ObjectId(user_id_str))

        try:
            apps_cursor = db["applications"].find(
                {"user_id": {"$in": user_match}, "offer_id": {"$exists": True, "$ne": None}},
                {"offer_id": 1}
            )
            if hasattr(apps_cursor, "to_list"):
                maybe_coro = apps_cursor.to_list(length=None)
                applied_apps = await maybe_coro if inspect.isawaitable(maybe_coro) else (maybe_coro or [])
            else:
                applied_apps = []

            for app in applied_apps:
                if isinstance(app, dict):
                    app_oid = str(app.get("offer_id", ""))
                    if app_oid and ObjectId.is_valid(app_oid):
                        if interaction_map.get(app_oid) != "hidden":
                            interaction_map[app_oid] = "applied"
                            seen_map[app_oid] = True
        except Exception as e_app:
            logger.warning(f"Error retrieving applied applications: {e_app}")

    allowed_oids = None

    # 1. Filtre par statut d'interaction (saved, applied, etc.)
    if target_status:
        matching_oids = [
            ObjectId(oid)
            for oid, st in interaction_map.items()
            if st == target_status and ObjectId.is_valid(oid)
        ]
        if not matching_oids:
            return match_filter, interaction_map, seen_map, True
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
            return match_filter, interaction_map, seen_map, True
        if allowed_oids is None:
            allowed_oids = set(score_oids)
        else:
            allowed_oids = allowed_oids.intersection(set(score_oids))
            if not allowed_oids:
                return match_filter, interaction_map, seen_map, True

    # 3. Exclusion des offres masquées par l'utilisateur
    excluded_oids = set()
    if not include_hidden and target_status != "hidden":
        for oid, st in interaction_map.items():
            if st == "hidden" and ObjectId.is_valid(oid):
                excluded_oids.add(ObjectId(oid))

    # 4. Exclusion des offres déjà vues (filtre "non vues")
    if unseen_only:
        for oid, seen_val in seen_map.items():
            if seen_val and ObjectId.is_valid(oid):
                excluded_oids.add(ObjectId(oid))

    if allowed_oids is not None:
        allowed_oids = allowed_oids - excluded_oids
        if not allowed_oids:
            return match_filter, interaction_map, seen_map, True
        match_filter["_id"] = {"$in": list(allowed_oids)}
    elif excluded_oids:
        match_filter["_id"] = {"$nin": list(excluded_oids)}

    return match_filter, interaction_map, seen_map, False


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
    unseen_only: bool = Query(False),
    min_score: Optional[float] = Query(None),
    sort: Literal["relevance", "recent"] = Query("recent"),
    sector: Optional[List[Literal[*SECTORS]]] = Query(None),
    company_size: Optional[List[Literal[*COMPANY_SIZES]]] = Query(None),
    limit: int = Query(16, ge=1, le=100),
    skip: int = Query(0, ge=0),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Récupère les offres d'emploi avec pagination, déduplication et statut d'interaction multi-tenant.

    `sort="relevance"` trie par score de pertinence hybride (Task 6) décroissant, puis
    par date ; par défaut (`"recent"`), l'ordre reste chronologique. Dans les deux cas,
    aucune offre n'est masquée ni repliée selon son score — le tri est le seul effet."""
    try:
        collection = db["job_offers"]

        # ✅ ÉTAPE 1: Construire le filtre de base (exclure les supprimées globales)
        match_filter = {
            "$or": [{"is_deleted": {"$exists": False}}, {"is_deleted": False}]
        }

        # Multi-tenant user filters
        match_filter, interaction_map, seen_map, should_return_empty = await apply_user_interaction_filters(
            match_filter=match_filter,
            db=db,
            current_user=current_user,
            only_saved=only_saved,
            include_hidden=include_hidden,
            min_score=min_score,
            interaction_status=interaction_status,
            unseen_only=unseen_only,
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
            cf = _build_contract_type_filter(contract_type)
            match_filter["$and"] = match_filter.get("$and", [])
            match_filter["$and"].append(cf)

        if work_mode:
            match_filter["mode_travail"] = {"$regex": work_mode, "$options": "i"}

        if sector:
            match_filter["$and"] = match_filter.get("$and", [])
            match_filter["$and"].append(_build_sector_filter(sector))

        if company_size:
            match_filter["$and"] = match_filter.get("$and", [])
            match_filter["$and"].append(_build_company_size_filter(company_size))

        restrict_to_profile_offers(match_filter, current_user, only_saved, interaction_status)

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
        ]

        # Le lookup de pertinence s'applique pour tout utilisateur connecté, quel que
        # soit le tri demandé (il alimente aussi `failed_conditions`, exposé même en
        # tri "recent"). Il se place après la déduplication, avant le tri final.
        if current_user:
            pipeline.extend(relevance_lookup_stages(str(current_user.id)))

        if sort == "relevance" and current_user:
            final_sort = {"_score_sort": -1, "created_at": -1, "_id": -1}
        else:
            final_sort = {"created_at": -1, "_id": -1}

        pipeline.append({"$sort": final_sort})
        pipeline.append({"$skip": skip})
        pipeline.append({"$limit": limit})

        if current_user:
            # `failed_conditions` remonte au premier niveau pour JobOfferResponse ;
            # les champs internes du lookup ne doivent jamais fuiter dans la réponse.
            pipeline.append(
                {"$addFields": {"failed_conditions": {"$ifNull": ["$_relevance.failed_conditions", []]}}}
            )
            pipeline.append({"$unset": ["_relevance", "_oid_str", "_score_sort"]})

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
            # evaluation_score sur le doc job_offers brut est écrit globalement par
            # le dernier utilisateur à avoir évalué l'offre (evaluator.py) : ne
            # jamais le laisser fuiter tel quel, ne renvoyer que le score propre
            # à l'utilisateur courant.
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
    current_user: UserModel = Depends(get_current_user),
):
    """Récupère une offre d'emploi par son ID avec état d'interaction personnalisé"""
    if not ObjectId.is_valid(offer_id):
        raise HTTPException(status_code=400, detail="ID invalide")

    offer = await db["job_offers"].find_one({"_id": ObjectId(offer_id)})
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")

    offer["id"] = str(offer["_id"])
    del offer["_id"]
    # Même précaution que sur la liste : evaluation_score brut est global à
    # l'offre (dernier utilisateur à l'avoir évaluée), jamais scopé par tenant.
    offer.pop("evaluation_score", None)

    if current_user:
        interaction = await db["user_offer_interactions"].find_one({
            "user_id": str(current_user.id),
            "offer_id": str(offer_id),
        })
        offer["user_interaction"] = interaction.get("status") if interaction else None
        offer["seen"] = interaction.get("seen", False) if interaction else False

        evaluation = await db["offer_evaluations"].find_one({
            "user_id": str(current_user.id),
            "offer_id": str(offer_id),
        })
        if evaluation:
            offer["evaluation_score"] = evaluation.get("score")
    else:
        offer["user_interaction"] = None
        offer["seen"] = False

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
        # Le tag "seen" est orthogonal à status : le préserver si présent plutôt
        # que de supprimer tout le document d'interaction.
        existing = await db["user_offer_interactions"].find_one(filter_query)
        if existing and existing.get("seen"):
            await db["user_offer_interactions"].update_one(
                filter_query,
                {"$set": {"status": "none", "notes": payload.notes, "updated_at": now}},
            )
            updated_doc = await db["user_offer_interactions"].find_one(filter_query)
            updated_doc["id"] = str(updated_doc["_id"])
            del updated_doc["_id"]
            return UserOfferInteractionResponse(**updated_doc)

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


@job_offers_router.post("/{offer_id}/seen", response_model=UserOfferInteractionResponse)
async def set_offer_seen(
    offer_id: str,
    payload: SeenStatusRequest,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Marque une offre comme vue/non vue. Orthogonal à status (saved/hidden/applied/dismissed)."""
    if not ObjectId.is_valid(offer_id):
        raise HTTPException(status_code=400, detail="ID d'offre invalide")

    offer = await db["job_offers"].find_one({"_id": ObjectId(offer_id)})
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")

    now = datetime.now(timezone.utc)
    user_id_str = str(current_user.id)
    filter_query = {"user_id": user_id_str, "offer_id": str(offer_id)}

    update_doc = {
        "$set": {
            "seen": payload.seen,
            "updated_at": now,
        },
        "$setOnInsert": {
            "status": "none",
            "created_at": now,
        },
    }
    await db["user_offer_interactions"].update_one(filter_query, update_doc, upsert=True)

    interaction_doc = await db["user_offer_interactions"].find_one(filter_query)
    interaction_doc["id"] = str(interaction_doc["_id"])
    del interaction_doc["_id"]
    return UserOfferInteractionResponse(**interaction_doc)


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
async def soft_delete_job_offer(
    offer_id: str,
    db=Depends(get_database),
    current_admin: UserModel = Depends(get_current_admin_user),
):
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
async def delete_job_offer(
    offer_id: str,
    db=Depends(get_database),
    current_admin: UserModel = Depends(get_current_admin_user),
):
    """Supprime une offre d'emploi, sauf si une candidature y est liée : elle est alors expirée."""
    if not ObjectId.is_valid(offer_id):
        raise HTTPException(status_code=400, detail="ID invalide")

    if not await db["job_offers"].find_one({"_id": ObjectId(offer_id)}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Offre non trouvée")

    outcome = await safe_delete_or_expire_offer(offer_id, db["job_offers"], db)
    if outcome == "error":
        raise HTTPException(status_code=500, detail="Erreur lors de la suppression")
    if outcome == "expired":
        return {"message": "Offre liée à une candidature : conservée et marquée expirée"}

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
    unseen_only: bool = Query(False),
    min_score: Optional[float] = Query(None),
    sort: Literal["relevance", "recent"] = Query("recent"),
    sector: Optional[List[Literal[*SECTORS]]] = Query(None),
    company_size: Optional[List[Literal[*COMPANY_SIZES]]] = Query(None),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Compte les offres d'emploi dédupliquées en tenant compte des filtres multi-tenant.

    `sort` n'a aucun effet sur un total : accepté ici uniquement pour que le front
    puisse envoyer les mêmes paramètres qu'à la liste sans déclencher de 422."""
    try:
        collection = db["job_offers"]

        # ✅ MÊME LOGIQUE: Construire le filtre de base
        match_filter = {
            "$or": [{"is_deleted": {"$exists": False}}, {"is_deleted": False}]
        }

        # Multi-tenant user filters
        match_filter, _, _, should_return_empty = await apply_user_interaction_filters(
            match_filter=match_filter,
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
            cf = _build_contract_type_filter(contract_type)
            match_filter["$and"] = match_filter.get("$and", [])
            match_filter["$and"].append(cf)

        if work_mode:
            match_filter["mode_travail"] = {"$regex": work_mode, "$options": "i"}

        if sector:
            match_filter["$and"] = match_filter.get("$and", [])
            match_filter["$and"].append(_build_sector_filter(sector))

        if company_size:
            match_filter["$and"] = match_filter.get("$and", [])
            match_filter["$and"].append(_build_company_size_filter(company_size))

        restrict_to_profile_offers(match_filter, current_user, only_saved, interaction_status)

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
