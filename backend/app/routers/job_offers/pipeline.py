import inspect
import sys
from typing import List, Optional

from bson import ObjectId

from ...models import UserModel

DEDUP_KEY_STAGE = {
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
}


def _pkg():
    return sys.modules[__package__]


def relevance_lookup_stages(user_id: str) -> list[dict]:
    """Étapes d'agrégation qui rattachent à chaque offre le score de pertinence hybride
    de l'utilisateur courant (collection `offer_relevance`).
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
                    {
                        "$project": {
                            "_id": 0,
                            "score": 1,
                            "level": 1,
                            "failed_conditions": 1,
                            "unknown_components": 1,
                        }
                    },
                ],
                "as": "_relevance",
            }
        },
        {"$addFields": {"_relevance": {"$arrayElemAt": ["$_relevance", 0]}}},
        {"$addFields": {"_score_sort": {"$ifNull": ["$_relevance.score", -1]}}},
    ]


def _relevance_level_match(relevance_level: List[str]) -> dict:
    """Filtre par niveau(x) de pertinence, à placer après `relevance_lookup_stages`."""
    return {"$match": {"_relevance.level": {"$in": relevance_level}}}


def _build_list_pipeline(
    match_filter: dict,
    *,
    sort: str,
    current_user: Optional[UserModel],
    skip: int,
    limit: int,
    relevance_level: Optional[List[str]] = None,
) -> list[dict]:
    """Construit le pipeline d'agrégation de la liste : déduplication, lookup, tri, pagination."""
    pipeline = [
        {"$match": match_filter},
        {"$sort": {"created_at": -1, "_id": -1}},
        DEDUP_KEY_STAGE,
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

    relevance_sort = bool(current_user) and sort == "relevance"
    level_filter = bool(current_user) and bool(relevance_level)
    early_lookup = relevance_sort or level_filter
    if early_lookup:
        pipeline.extend(relevance_lookup_stages(str(current_user.id)))
    if level_filter:
        pipeline.append(_relevance_level_match(relevance_level))

    final_sort = (
        {"_score_sort": -1, "created_at": -1, "_id": -1}
        if relevance_sort
        else {"created_at": -1, "_id": -1}
    )
    pipeline.extend([{"$sort": final_sort}, {"$skip": skip}, {"$limit": limit}])

    if current_user and not early_lookup:
        pipeline.extend(relevance_lookup_stages(str(current_user.id)))

    if current_user:
        pipeline.append(
            {
                "$addFields": {
                    "failed_conditions": {"$ifNull": ["$_relevance.failed_conditions", []]},
                    "unknown_components": {"$ifNull": ["$_relevance.unknown_components", []]},
                    "relevance_level": "$_relevance.level",
                }
            }
        )
        pipeline.append({"$unset": ["_relevance", "_oid_str", "_score_sort"]})

    return pipeline


async def _merge_applied_applications(
    db, user_id_str: str, interaction_map: dict, seen_map: dict
) -> None:
    """Include offers linked via user applications when filtering on applied status."""
    user_match: list = [user_id_str]
    if ObjectId.is_valid(user_id_str):
        user_match.append(ObjectId(user_id_str))
    try:
        apps_cursor = db["applications"].find(
            {"user_id": {"$in": user_match}, "offer_id": {"$exists": True, "$ne": None}},
            {"offer_id": 1},
        )
        if hasattr(apps_cursor, "to_list"):
            maybe_coro = apps_cursor.to_list(length=None)
            applied_apps = (
                await maybe_coro if inspect.isawaitable(maybe_coro) else (maybe_coro or [])
            )
        else:
            applied_apps = []

        for app in applied_apps:
            if not isinstance(app, dict):
                continue
            app_oid = str(app.get("offer_id", ""))
            if app_oid and ObjectId.is_valid(app_oid) and interaction_map.get(app_oid) != "hidden":
                interaction_map[app_oid] = "applied"
                seen_map[app_oid] = True
    except Exception as e_app:
        _pkg().logger.warning(f"Error retrieving applied applications: {e_app}")


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
    """Applique les filtres multi-tenant au filtre MongoDB.
    Renvoie (match_filter_mis_à_jour, interaction_map, seen_map, should_return_empty).
    """
    target_status = "saved" if only_saved else interaction_status
    interaction_map: dict = {}
    seen_map: dict = {}

    if not current_user:
        return match_filter, interaction_map, seen_map, bool(target_status or min_score is not None)

    user_id_str = str(current_user.id)
    user_interactions = await db["user_offer_interactions"].find(
        {"user_id": user_id_str}
    ).to_list(length=None)
    interaction_map = {doc["offer_id"]: doc.get("status") for doc in user_interactions}
    seen_map = {doc["offer_id"]: doc.get("seen", False) for doc in user_interactions}

    if target_status == "applied":
        await _merge_applied_applications(db, user_id_str, interaction_map, seen_map)

    allowed_oids: Optional[set] = None

    if target_status:
        matching_oids = [
            ObjectId(oid)
            for oid, st in interaction_map.items()
            if st == target_status and ObjectId.is_valid(oid)
        ]
        if not matching_oids:
            return match_filter, interaction_map, seen_map, True
        allowed_oids = set(matching_oids)

    if min_score is not None:
        evals = await db["offer_evaluations"].find(
            {"user_id": user_id_str, "score": {"$gte": min_score}},
            {"offer_id": 1},
        ).to_list(length=None)
        score_oids = {
            ObjectId(doc["offer_id"])
            for doc in evals
            if doc.get("offer_id") and ObjectId.is_valid(doc["offer_id"])
        }
        if not score_oids:
            return match_filter, interaction_map, seen_map, True
        allowed_oids = score_oids if allowed_oids is None else allowed_oids & score_oids
        if not allowed_oids:
            return match_filter, interaction_map, seen_map, True

    excluded_oids = set()
    if not include_hidden and target_status != "hidden":
        excluded_oids.update(
            ObjectId(oid)
            for oid, st in interaction_map.items()
            if st == "hidden" and ObjectId.is_valid(oid)
        )
    if unseen_only:
        excluded_oids.update(
            ObjectId(oid)
            for oid, seen_val in seen_map.items()
            if seen_val and ObjectId.is_valid(oid)
        )

    if allowed_oids is not None:
        allowed_oids -= excluded_oids
        if not allowed_oids:
            return match_filter, interaction_map, seen_map, True
        match_filter["_id"] = {"$in": list(allowed_oids)}
    elif excluded_oids:
        match_filter["_id"] = {"$nin": list(excluded_oids)}

    return match_filter, interaction_map, seen_map, False
