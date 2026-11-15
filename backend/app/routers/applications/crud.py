import sys
from datetime import datetime, timezone
from typing import List, Optional

import pymongo
from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder

from ...auth import get_current_user
from ...database import get_database
from ...models import (
    ApiUsageAction,
    ApplicationStatus,
    JobApplicationCreate,
    JobApplicationResponse,
    JobApplicationUpdate,
    UserModel,
)
from ...utils import serialize_mongodb_doc
from .background import sync_applied_interaction

router = APIRouter()


def _pkg():
    return sys.modules[__package__]


def _clean_payload(model) -> dict:
    raw_data = jsonable_encoder(model)
    cleaned = {
        k: v
        for k, v in raw_data.items()
        if v is not None and (not isinstance(v, str) or v.strip() != "")
    }
    pkg = _pkg()
    for field in ("company", "position"):
        if cleaned.get(field):
            cleaned[field] = pkg.capitalize_words(cleaned[field])
    return cleaned


async def _find_owned_application(db, application_id: str, current_user: UserModel) -> dict:
    application = await db["applications"].find_one({"_id": ObjectId(application_id)})
    if not application:
        raise HTTPException(status_code=404, detail="Candidature non trouvée")
    if str(application["user_id"]) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès non autorisé à cette candidature")
    return application


@router.post("/", response_model=JobApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    background_tasks: BackgroundTasks,
    application: JobApplicationCreate = Body(...),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    pkg = _pkg()
    app_data = _clean_payload(application)
    app_data["user_id"] = current_user.id
    app_data["created_at"] = datetime.now(timezone.utc)
    if not app_data.get("application_date"):
        app_data["application_date"] = app_data["created_at"]

    result = await db["applications"].insert_one(app_data)
    created = await db["applications"].find_one({"_id": result.inserted_id})

    # Auto-lier une offre seulement si l'appelant n'en a pas fourni : un offer_id donné est conservé tel quel
    if not created.get("offer_id"):
        try:
            await pkg._ensure_offer_for_application(str(result.inserted_id), created, db)
            created = await db["applications"].find_one({"_id": result.inserted_id})
        except Exception as e_link:
            pkg.logger.warning(f"[create_application] Erreur auto-liaison offre: {e_link}")

    # Synchroniser l'interaction de l'utilisateur avec l'offre (status: "applied", seen: True)
    if created.get("offer_id"):
        try:
            await sync_applied_interaction(db, str(current_user.id), str(created["offer_id"]))
        except Exception as e_interact:
            pkg.logger.warning(
                f"[create_application] Erreur mise à jour interaction 'applied': {e_interact}"
            )

    url_exists = "url" in app_data and app_data["url"] and app_data["url"].strip() != ""
    description_missing = "description" not in app_data or not app_data["description"]
    if url_exists and description_missing:
        await pkg.require_user_quota(db, current_user.id, ApiUsageAction.OFFER_SUMMARY)
        try:
            url = app_data.get("url")
            pkg.logger.info(f"[create_application] URL: {url!r}, ID: {result.inserted_id}")
            background_tasks.add_task(
                pkg._generate_description_bg, result.inserted_id, current_user.id, url.strip(), db
            )
            pkg.logger.info(f"[create_application] Tâche planifiée pour URL: {url}")
        except Exception as e:
            pkg.logger.error(f"[create_application] Erreur: {str(e)}")

    return pkg.enrich_application_with_cadences(serialize_mongodb_doc(created))


@router.get("/", response_model=List[JobApplicationResponse])
async def get_applications(
    status: Optional[str] = None,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    pkg = _pkg()
    query = {"user_id": current_user.id}
    if status:
        query["status"] = status

    applications = (
        await db["applications"]
        .find(query)
        .sort("application_date", pymongo.DESCENDING)
        .to_list(length=100)
    )

    serialized_applications = []
    for app in applications:
        serialized_app = serialize_mongodb_doc(app)
        if "location" not in serialized_app:
            serialized_app["location"] = None
        serialized_applications.append(pkg.enrich_application_with_cadences(serialized_app))

    return serialized_applications


@router.get("/{application_id}", response_model=JobApplicationResponse)
async def get_application(
    application_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    application = await _find_owned_application(db, application_id, current_user)
    return _pkg().enrich_application_with_cadences(serialize_mongodb_doc(application))


@router.put("/{application_id}", response_model=JobApplicationResponse)
async def update_application(
    background_tasks: BackgroundTasks,
    application_id: str,
    application_data: JobApplicationUpdate = Body(...),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    pkg = _pkg()
    application = await _find_owned_application(db, application_id, current_user)

    update_data = _clean_payload(application_data)
    url_provided = "url" in update_data and update_data["url"]
    url_changed = url_provided and update_data["url"] != application.get("url", "")
    description_provided = "description" in update_data and update_data["description"]

    update_data["updated_at"] = datetime.now(timezone.utc)
    await db["applications"].update_one({"_id": ObjectId(application_id)}, {"$set": update_data})

    # Auto-lier l'offre. job_offers est partagée entre utilisateurs : la description de la
    # candidature ne fait que remplir une offre vide (_ensure_offer_for_application), jamais l'écraser.
    updated_doc = await db["applications"].find_one({"_id": ObjectId(application_id)})
    if updated_doc and (updated_doc.get("url") or updated_doc.get("description")):
        if not updated_doc.get("offer_id") or "description" in update_data:
            try:
                await pkg._ensure_offer_for_application(str(application_id), updated_doc, db)
            except Exception as e_link:
                pkg.logger.warning(f"[update_application] Erreur auto-liaison offre: {e_link}")

    if url_changed or (url_provided and not description_provided):
        await pkg.require_user_quota(db, application["user_id"], ApiUsageAction.OFFER_SUMMARY)
        try:
            background_tasks.add_task(
                pkg._generate_description_bg,
                ObjectId(application_id),
                application["user_id"],
                update_data["url"],
                db,
            )
        except Exception as e:
            pkg.logger.error(f"Failed to schedule description generation: {e}")

    status_changed = "status" in update_data and update_data["status"] != application.get("status")
    if status_changed and update_data["status"] == ApplicationStatus.ETUDE:
        await pkg.require_user_quota(db, application["user_id"], ApiUsageAction.COVER_LETTER)
        try:
            background_tasks.add_task(
                pkg._generate_cover_letter_bg,
                ObjectId(application_id),
                ObjectId(application["user_id"]),
                db,
            )
        except Exception as e:
            pkg.logger.error(f"Failed to schedule cover letter generation: {e}")

    updated_application = await db["applications"].find_one({"_id": ObjectId(application_id)})
    return pkg.enrich_application_with_cadences(serialize_mongodb_doc(updated_application))


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    application_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    await _find_owned_application(db, application_id, current_user)
    await db["applications"].delete_one({"_id": ObjectId(application_id)})
    return None


@router.post("/{application_id}/notes", response_model=JobApplicationResponse)
async def add_note(
    application_id: str,
    note: str = Body(..., embed=True),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    await _find_owned_application(db, application_id, current_user)
    await db["applications"].update_one(
        {"_id": ObjectId(application_id)},
        {"$push": {"notes": note}, "$set": {"updated_at": datetime.now(timezone.utc)}},
    )
    updated_application = await db["applications"].find_one({"_id": ObjectId(application_id)})
    return _pkg().enrich_application_with_cadences(serialize_mongodb_doc(updated_application))
