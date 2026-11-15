import sys
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from ...auth import get_current_admin_user, get_current_user
from ...database import get_database
from ...models import OfferEvaluationResponse, UserModel

router = APIRouter()


def _pkg():
    return sys.modules[__package__]


def _validate_oid(offer_id: str, detail: str = "ID invalide") -> ObjectId:
    if not ObjectId.is_valid(offer_id):
        raise HTTPException(status_code=400, detail=detail)
    return ObjectId(offer_id)


@router.post("/{offer_id}/evaluate", response_model=OfferEvaluationResponse)
async def evaluate_job_offer_endpoint(
    offer_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Déclenche l'évaluation Two-Pass de l'offre pour le candidat connecté."""
    _validate_oid(offer_id, "ID d'offre invalide")
    evaluation = await _pkg().evaluate_offer_two_pass(
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


@router.get("/{offer_id}/evaluation", response_model=OfferEvaluationResponse)
async def get_job_offer_evaluation_endpoint(
    offer_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Récupère l'évaluation détaillée associée au couple (offer_id, user_id)."""
    _validate_oid(offer_id, "ID d'offre invalide")
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


@router.patch("/{offer_id}/soft-delete")
async def soft_delete_job_offer(
    offer_id: str,
    db=Depends(get_database),
    current_admin: UserModel = Depends(get_current_admin_user),
):
    """Effectue un soft delete d'une offre d'emploi (marque comme supprimée)."""
    oid = _validate_oid(offer_id)
    offer = await db["job_offers"].find_one({"_id": oid})
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")
    if offer.get("is_deleted", False):
        raise HTTPException(status_code=400, detail="Offre déjà supprimée")

    now = datetime.now(timezone.utc)
    result = await db["job_offers"].update_one(
        {"_id": oid},
        {"$set": {"is_deleted": True, "deleted_date": now, "updated_at": now}},
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=500, detail="Erreur lors de la suppression")

    updated_offer = await db["job_offers"].find_one({"_id": oid})
    updated_offer["id"] = str(updated_offer["_id"])
    del updated_offer["_id"]
    return {"message": "Offre marquée comme supprimée", "offer": updated_offer}


@router.delete("/{offer_id}")
async def delete_job_offer(
    offer_id: str,
    db=Depends(get_database),
    current_admin: UserModel = Depends(get_current_admin_user),
):
    """Supprime une offre d'emploi, sauf si une candidature y est liée : elle est alors expirée."""
    oid = _validate_oid(offer_id)
    if not await db["job_offers"].find_one({"_id": oid}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Offre non trouvée")

    outcome = await _pkg().safe_delete_or_expire_offer(offer_id, db["job_offers"], db)
    if outcome == "error":
        raise HTTPException(status_code=500, detail="Erreur lors de la suppression")
    if outcome == "expired":
        return {"message": "Offre liée à une candidature : conservée et marquée expirée"}
    return {"message": "Offre supprimée"}


@router.post("/{offer_id}/regenerate-description")
async def regenerate_offer_description_endpoint(offer_id: str, db=Depends(get_database)):
    """Régénère la description d'une offre d'emploi (et gère les liens morts/expirés)."""
    oid = _validate_oid(offer_id)
    offer = await db["job_offers"].find_one({"_id": oid})
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")

    from ...tasks.regenerate_descriptions import regenerate_single_offer

    res = await regenerate_single_offer(offer, db=db)
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error", "Erreur de régénération"))

    updated_offer = await db["job_offers"].find_one({"_id": oid})
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
