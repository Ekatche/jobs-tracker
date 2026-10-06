# backend/app/routers/admin.py
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..auth import get_current_admin_user
from ..database import get_database
from ..models import (
    ActionCostItem,
    AdminCostSummaryResponse,
    AdminUserSummaryResponse,
    AdminUserToggleStatusRequest,
    AdminUserUpdateTierRequest,
    ModelCostItem,
    UserModel,
    UserRole,
    UserTier,
    utcnow_with_timezone,
)

logger = logging.getLogger(__name__)

admin_router = APIRouter(prefix="/admin", tags=["admin"])

ACTION_LABELS = {
    "interview_prep": "Préparation d'Entretien (STAR+R)",
    "cv_tailoring": "CVs Sur-Mesure (ATS)",
    "cover_letter": "Lettres de Motivation IA",
    "evaluation": "Évaluations d'Adéquation IA",
    "cv_parsing": "Parsing de CV (Mistral VLM)",
    "offer_summary": "Résumés d'Offres & Découverte",
    "role_suggestion": "Suggestions de Rôles",
}


def pseudonymize_email(email: str) -> str:
    """Masque l'email conformément au RGPD (ex: a***e@gmail.com)."""
    if not email or "@" not in email:
        return "anonymized@local"
    parts = email.split("@")
    user_part, domain_part = parts[0], parts[1]
    if len(user_part) <= 2:
        masked_user = user_part[0] + "***"
    else:
        masked_user = user_part[0] + "***" + user_part[-1]
    return f"{masked_user}@{domain_part}"


def pseudonymize_name(name: Optional[str]) -> str:
    """Réduit le nom complet à des initiales pour minimiser les données personnelles."""
    if not name or not name.strip():
        return "Utilisateur"
    parts = name.strip().split()
    if len(parts) == 1:
        return f"{parts[0][0].upper()}."
    return f"{parts[0][0].upper()}. {parts[-1][0].upper()}."


@admin_router.get("/stats/costs", response_model=AdminCostSummaryResponse)
async def get_admin_cost_summary(
    period: str = Query("30d", pattern="^(24h|7d|30d|all)$"),
    db=Depends(get_database),
    current_admin: UserModel = Depends(get_current_admin_user),
):
    """Agrège l'usage et les coûts API en USD sur la période spécifiée."""
    now = datetime.now(timezone.utc)
    start_date: Optional[datetime] = None

    if period == "24h":
        start_date = now - timedelta(hours=24)
    elif period == "7d":
        start_date = now - timedelta(days=7)
    elif period == "30d":
        start_date = now - timedelta(days=30)

    match_query = {}
    if start_date:
        match_query["created_at"] = {"$gte": start_date}

    # 1. Totaux globaux
    global_pipeline = [
        {"$match": match_query},
        {
            "$group": {
                "_id": None,
                "total_cost": {"$sum": "$estimated_cost_usd"},
                "total_tokens": {"$sum": "$total_tokens"},
                "total_requests": {"$sum": 1},
                "unique_users": {"$addToSet": "$user_id"},
            }
        },
    ]

    global_res = await db["api_usage"].aggregate(global_pipeline).to_list(length=1)
    total_cost = 0.0
    total_tokens = 0
    total_requests = 0
    active_users_count = 0

    if global_res:
        g = global_res[0]
        total_cost = float(g.get("total_cost", 0.0))
        total_tokens = int(g.get("total_tokens", 0))
        total_requests = int(g.get("total_requests", 0))
        unique_users = [u for u in g.get("unique_users", []) if u != "anonymized_deleted"]
        active_users_count = len(unique_users)

    avg_cost = round(total_cost / max(active_users_count, 1), 4)

    # 2. Répartition par Modèle
    model_pipeline = [
        {"$match": match_query},
        {"$unwind": "$models_used"},
        {
            "$group": {
                "_id": "$models_used",
                "input_tokens": {"$sum": "$input_tokens"},
                "output_tokens": {"$sum": "$output_tokens"},
                "total_tokens": {"$sum": "$total_tokens"},
                "cost_usd": {"$sum": "$estimated_cost_usd"},
                "requests_count": {"$sum": 1},
            }
        },
        {"$sort": {"cost_usd": -1}},
    ]
    model_res = await db["api_usage"].aggregate(model_pipeline).to_list(length=50)
    model_breakdown = [
        ModelCostItem(
            model=m["_id"],
            input_tokens=m.get("input_tokens", 0),
            output_tokens=m.get("output_tokens", 0),
            total_tokens=m.get("total_tokens", 0),
            cost_usd=round(float(m.get("cost_usd", 0.0)), 4),
            requests_count=m.get("requests_count", 0),
        )
        for m in model_res
    ]

    # 3. Répartition par Action
    action_pipeline = [
        {"$match": match_query},
        {
            "$group": {
                "_id": "$action",
                "total_tokens": {"$sum": "$total_tokens"},
                "cost_usd": {"$sum": "$estimated_cost_usd"},
                "requests_count": {"$sum": 1},
            }
        },
        {"$sort": {"cost_usd": -1}},
    ]
    action_res = await db["api_usage"].aggregate(action_pipeline).to_list(length=50)
    action_breakdown = [
        ActionCostItem(
            action=a["_id"],
            label=ACTION_LABELS.get(a["_id"], a["_id"]),
            total_tokens=a.get("total_tokens", 0),
            cost_usd=round(float(a.get("cost_usd", 0.0)), 4),
            requests_count=a.get("requests_count", 0),
        )
        for a in action_res
    ]

    return AdminCostSummaryResponse(
        period=period,
        total_cost_usd=round(total_cost, 4),
        total_tokens=total_tokens,
        total_requests=total_requests,
        avg_cost_per_user=avg_cost,
        active_users_count=active_users_count,
        model_breakdown=model_breakdown,
        action_breakdown=action_breakdown,
    )


@admin_router.get("/users", response_model=List[AdminUserSummaryResponse])
async def list_admin_users(
    db=Depends(get_database),
    current_admin: UserModel = Depends(get_current_admin_user),
):
    """Liste tous les comptes avec pseudonymisation stricte et statistiques d'usage."""
    # Récupérer les métriques agrégées par utilisateur
    usage_by_user = await db["api_usage"].aggregate([
        {
            "$group": {
                "_id": "$user_id",
                "total_cost": {"$sum": "$estimated_cost_usd"},
                "total_tokens": {"$sum": "$total_tokens"},
                "total_requests": {"$sum": 1},
                "last_active": {"$max": "$created_at"},
            }
        }
    ]).to_list(length=None)
    usage_map = {doc["_id"]: doc for doc in usage_by_user}

    users_cursor = db["users"].find({}).sort("created_at", -1)
    users = await users_cursor.to_list(length=None)

    result = []
    for u in users:
        uid_str = str(u["_id"])
        usage_data = usage_map.get(uid_str, {})

        created = u.get("created_at") or utcnow_with_timezone()
        if isinstance(created, str):
            try:
                created = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except Exception:
                created = utcnow_with_timezone()

        raw_last = usage_data.get("last_active")
        if isinstance(raw_last, str):
            try:
                raw_last = datetime.fromisoformat(raw_last.replace("Z", "+00:00"))
            except Exception:
                raw_last = None

        result.append(
            AdminUserSummaryResponse(
                id=uid_str,
                pseudonym_email=pseudonymize_email(u.get("email", "")),
                pseudonym_name=pseudonymize_name(u.get("full_name") or u.get("username")),
                tier=UserTier(u.get("tier", "free")),
                role=UserRole(u.get("role", "user")),
                disabled=bool(u.get("disabled", False)),
                created_at=created,
                last_active_at=raw_last,
                total_cost_usd=round(float(usage_data.get("total_cost", 0.0)), 4),
                total_tokens=int(usage_data.get("total_tokens", 0)),
                total_requests=int(usage_data.get("total_requests", 0)),
            )
        )

    return result


@admin_router.put("/users/{user_id}/tier", response_model=AdminUserSummaryResponse)
async def update_user_tier_admin(
    user_id: str,
    payload: AdminUserUpdateTierRequest,
    db=Depends(get_database),
    current_admin: UserModel = Depends(get_current_admin_user),
):
    """Modifie le tier d'un utilisateur (free, advanced, pro)."""
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Identifiant utilisateur invalide")

    user = await db["users"].find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    now = utcnow_with_timezone()
    await db["users"].update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"tier": payload.tier.value, "updated_at": now}},
    )

    updated_user = await db["users"].find_one({"_id": ObjectId(user_id)})
    uid_str = str(updated_user["_id"])

    # Récupérer usage
    usage_data = await db["api_usage"].aggregate([
        {"$match": {"user_id": uid_str}},
        {
            "$group": {
                "_id": "$user_id",
                "total_cost": {"$sum": "$estimated_cost_usd"},
                "total_tokens": {"$sum": "$total_tokens"},
                "total_requests": {"$sum": 1},
                "last_active": {"$max": "$created_at"},
            }
        },
    ]).to_list(length=1)

    u_dict = usage_data[0] if usage_data else {}
    return AdminUserSummaryResponse(
        id=uid_str,
        pseudonym_email=pseudonymize_email(updated_user.get("email", "")),
        pseudonym_name=pseudonymize_name(updated_user.get("full_name") or updated_user.get("username")),
        tier=UserTier(updated_user.get("tier", "free")),
        role=UserRole(updated_user.get("role", "user")),
        disabled=bool(updated_user.get("disabled", False)),
        created_at=updated_user.get("created_at") or now,
        last_active_at=u_dict.get("last_active"),
        total_cost_usd=round(float(u_dict.get("total_cost", 0.0)), 4),
        total_tokens=int(u_dict.get("total_tokens", 0)),
        total_requests=int(u_dict.get("total_requests", 0)),
    )


@admin_router.put("/users/{user_id}/status", response_model=AdminUserSummaryResponse)
async def toggle_user_status_admin(
    user_id: str,
    payload: AdminUserToggleStatusRequest,
    db=Depends(get_database),
    current_admin: UserModel = Depends(get_current_admin_user),
):
    """Active ou désactive un compte utilisateur."""
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Identifiant utilisateur invalide")

    if user_id == str(current_admin.id):
        raise HTTPException(
            status_code=400,
            detail="Impossible de désactiver votre propre compte administrateur",
        )

    user = await db["users"].find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    now = utcnow_with_timezone()
    await db["users"].update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"disabled": payload.disabled, "updated_at": now}},
    )

    updated_user = await db["users"].find_one({"_id": ObjectId(user_id)})
    uid_str = str(updated_user["_id"])

    usage_data = await db["api_usage"].aggregate([
        {"$match": {"user_id": uid_str}},
        {
            "$group": {
                "_id": "$user_id",
                "total_cost": {"$sum": "$estimated_cost_usd"},
                "total_tokens": {"$sum": "$total_tokens"},
                "total_requests": {"$sum": 1},
                "last_active": {"$max": "$created_at"},
            }
        },
    ]).to_list(length=1)

    u_dict = usage_data[0] if usage_data else {}
    return AdminUserSummaryResponse(
        id=uid_str,
        pseudonym_email=pseudonymize_email(updated_user.get("email", "")),
        pseudonym_name=pseudonymize_name(updated_user.get("full_name") or updated_user.get("username")),
        tier=UserTier(updated_user.get("tier", "free")),
        role=UserRole(updated_user.get("role", "user")),
        disabled=bool(updated_user.get("disabled", False)),
        created_at=updated_user.get("created_at") or now,
        last_active_at=u_dict.get("last_active"),
        total_cost_usd=round(float(u_dict.get("total_cost", 0.0)), 4),
        total_tokens=int(u_dict.get("total_tokens", 0)),
        total_requests=int(u_dict.get("total_requests", 0)),
    )


@admin_router.delete("/users/{user_id}/gdpr")
async def delete_user_gdpr_erasure(
    user_id: str,
    db=Depends(get_database),
    current_admin: UserModel = Depends(get_current_admin_user),
):
    """Droit à l'oubli RGPD : supprime définitivement les données personnelles de l'utilisateur

    et anonymise ses métriques de consommation d'API sans altérer les totaux comptables.
    """
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Identifiant utilisateur invalide")

    if user_id == str(current_admin.id):
        raise HTTPException(
            status_code=400,
            detail="Impossible de supprimer votre propre compte administrateur",
        )

    user = await db["users"].find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    user_obj = ObjectId(user_id)
    match_user = {"$in": [user_id, user_obj]}

    # Suppression en cascade des données privées
    await db["applications"].delete_many({"user_id": match_user})
    await db["candidate_profile"].delete_many({"user_id": match_user})
    await db["cover_letters"].delete_many({"user_id": match_user})
    await db["cv_tailored"].delete_many({"user_id": match_user})
    await db["user_offer_interactions"].delete_many({"user_id": user_id})
    await db["offer_evaluations"].delete_many({"user_id": user_id})

    # Anonymisation de l'historique d'usage (conservation des totaux sans identification)
    await db["api_usage"].update_many(
        {"user_id": user_id},
        {"$set": {"user_id": "anonymized_deleted", "metadata": {}}},
    )

    # Suppression du compte
    await db["users"].delete_one({"_id": user_obj})

    logger.info(f"Compte {user_id} effacé conformément au droit à l'oubli RGPD par admin {current_admin.id}")
    return {"message": "Données utilisateur supprimées et anonymisées conformément au RGPD"}
