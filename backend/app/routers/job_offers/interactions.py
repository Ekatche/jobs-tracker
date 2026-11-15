from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from ...auth import get_current_user
from ...database import get_database
from ...models import (
    SeenStatusRequest,
    UserModel,
    UserOfferInteractionRequest,
    UserOfferInteractionResponse,
)

router = APIRouter()


async def _ensure_offer_exists(db, offer_id: str) -> dict:
    if not ObjectId.is_valid(offer_id):
        raise HTTPException(status_code=400, detail="ID d'offre invalide")
    offer = await db["job_offers"].find_one({"_id": ObjectId(offer_id)})
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")
    return offer


def _format_interaction(doc: dict) -> UserOfferInteractionResponse:
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return UserOfferInteractionResponse(**doc)


@router.post("/{offer_id}/interaction", response_model=UserOfferInteractionResponse)
async def set_user_offer_interaction(
    offer_id: str,
    payload: UserOfferInteractionRequest,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Enregistre ou met à jour l'interaction personnelle d'un candidat sur une offre."""
    await _ensure_offer_exists(db, offer_id)

    now = datetime.now(timezone.utc)
    user_id_str = str(current_user.id)
    filter_query = {"user_id": user_id_str, "offer_id": str(offer_id)}

    if payload.status == "none":
        # Le tag "seen" est orthogonal à status : le préserver si présent
        existing = await db["user_offer_interactions"].find_one(filter_query)
        if existing and existing.get("seen"):
            await db["user_offer_interactions"].update_one(
                filter_query,
                {"$set": {"status": "none", "notes": payload.notes, "updated_at": now}},
            )
            return _format_interaction(await db["user_offer_interactions"].find_one(filter_query))

        await db["user_offer_interactions"].delete_many(filter_query)
        return UserOfferInteractionResponse(
            user_id=user_id_str,
            offer_id=str(offer_id),
            status="none",
            notes=payload.notes,
            created_at=now,
            updated_at=now,
        )

    await db["user_offer_interactions"].update_one(
        filter_query,
        {
            "$set": {"status": payload.status, "notes": payload.notes, "updated_at": now},
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    interaction_doc = await db["user_offer_interactions"].find_one(filter_query)
    if interaction_doc:
        return _format_interaction(interaction_doc)

    return UserOfferInteractionResponse(
        user_id=user_id_str,
        offer_id=str(offer_id),
        status=payload.status,
        notes=payload.notes,
        created_at=now,
        updated_at=now,
    )


@router.post("/{offer_id}/seen", response_model=UserOfferInteractionResponse)
async def set_offer_seen(
    offer_id: str,
    payload: SeenStatusRequest,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Marque une offre comme vue/non vue. Orthogonal à status (saved/hidden/applied/dismissed)."""
    await _ensure_offer_exists(db, offer_id)

    now = datetime.now(timezone.utc)
    filter_query = {"user_id": str(current_user.id), "offer_id": str(offer_id)}
    await db["user_offer_interactions"].update_one(
        filter_query,
        {
            "$set": {"seen": payload.seen, "updated_at": now},
            "$setOnInsert": {"status": "none", "created_at": now},
        },
        upsert=True,
    )
    return _format_interaction(await db["user_offer_interactions"].find_one(filter_query))


@router.get("/{offer_id}/interaction", response_model=UserOfferInteractionResponse)
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
    return _format_interaction(interaction_doc)
