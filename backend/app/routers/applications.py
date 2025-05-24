from fastapi import APIRouter, Body, Depends, status, HTTPException, BackgroundTasks
from typing import List, Optional
from bson import ObjectId
from datetime import datetime, timezone
import pymongo
import logging
from fastapi.encoders import jsonable_encoder

from ..models import (
    JobApplicationCreate,
    JobApplicationResponse,
    JobApplicationUpdate,
    UserModel,
)
from ..database import get_database
from ..utils import serialize_mongodb_doc, capitalize_words
from ..auth import get_current_user
from ..llm.utils import fetch_documents, split_documents, summarize_chunks

logger = logging.getLogger(__name__)

job_router = APIRouter(prefix="/applications", tags=["applications"])


async def _generate_description_bg(application_id: ObjectId, url: str, db):
    logger.info(f"[description_bg] Démarrage pour ID={application_id}, URL={url}")
    try:
        docs = await fetch_documents(url)
        if not docs:
            logger.warning(f"[description_bg] Aucun document récupéré pour {url}")
            return

        chunks = split_documents(docs)
        description = await summarize_chunks(chunks)

        if description:
            logger.info(
                f"[description_bg] Description générée ({len(description)} chars)"
            )
            await db["applications"].update_one(
                {"_id": ObjectId(application_id)},
                {
                    "$set": {
                        "description": description,
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
        else:
            logger.warning("[description_bg] Échec de génération de description")
    except Exception as e:
        logger.error(f"[description_bg] Erreur: {str(e)}")


@job_router.post(
    "/", response_model=JobApplicationResponse, status_code=status.HTTP_201_CREATED
)
async def create_application(
    background_tasks: BackgroundTasks,
    application: JobApplicationCreate = Body(...),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    raw_data = jsonable_encoder(application)
    app_data = {
        k: v
        for k, v in raw_data.items()
        if v is not None and (not isinstance(v, str) or v.strip() != "")
    }

    if "company" in app_data and app_data["company"]:
        app_data["company"] = capitalize_words(app_data["company"])

    if "position" in app_data and app_data["position"]:
        app_data["position"] = capitalize_words(app_data["position"])

    app_data["user_id"] = current_user.id
    app_data["created_at"] = datetime.now(timezone.utc)
    if not app_data.get("application_date"):
        app_data["application_date"] = app_data["created_at"]

    result = await db["applications"].insert_one(app_data)
    created = await db["applications"].find_one({"_id": result.inserted_id})

    url_exists = "url" in app_data and app_data["url"] and app_data["url"].strip() != ""
    description_missing = "description" not in app_data or not app_data["description"]
    if url_exists and description_missing:
        try:
            url = app_data.get("url")
            logger.info(f"[create_application] URL: {url!r}, ID: {result.inserted_id}")
            app_id = result.inserted_id
            background_tasks.add_task(_generate_description_bg, app_id, url.strip(), db)
            logger.info(f"[create_application] Tâche planifiée pour URL: {url}")
        except Exception as e:
            logger.error(f"[create_application] Erreur: {str(e)}")

    return serialize_mongodb_doc(created)


@job_router.get("/", response_model=List[JobApplicationResponse])
async def get_applications(
    status: Optional[str] = None,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
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
        serialized_applications.append(serialized_app)

    return serialized_applications


@job_router.get("/{application_id}", response_model=JobApplicationResponse)
async def get_application(
    application_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    application = await db["applications"].find_one({"_id": ObjectId(application_id)})

    if not application:
        raise HTTPException(status_code=404, detail="Candidature non trouvée")

    if str(application["user_id"]) != str(current_user.id):
        raise HTTPException(
            status_code=403, detail="Accès non autorisé à cette candidature"
        )

    return serialize_mongodb_doc(application)


@job_router.put("/{application_id}", response_model=JobApplicationResponse)
async def update_application(
    background_tasks: BackgroundTasks,
    application_id: str,
    application_data: JobApplicationUpdate = Body(...),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    application = await db["applications"].find_one({"_id": ObjectId(application_id)})

    if not application:
        raise HTTPException(status_code=404, detail="Candidature non trouvée")

    if str(application["user_id"]) != str(current_user.id):
        raise HTTPException(
            status_code=403, detail="Accès non autorisé à cette candidature"
        )

    raw_data = jsonable_encoder(application_data)
    update_data = {
        k: v
        for k, v in raw_data.items()
        if v is not None and (not isinstance(v, str) or v.strip() != "")
    }

    if "company" in update_data and update_data["company"]:
        update_data["company"] = capitalize_words(update_data["company"])

    if "position" in update_data and update_data["position"]:
        update_data["position"] = capitalize_words(update_data["position"])

    url_provided = "url" in update_data and update_data["url"]
    url_changed = url_provided and update_data["url"] != application.get("url", "")
    description_provided = "description" in update_data and update_data["description"]

    update_data["updated_at"] = datetime.now(timezone.utc)
    await db["applications"].update_one(
        {"_id": ObjectId(application_id)}, {"$set": update_data}
    )

    if url_changed or (url_provided and not description_provided):
        try:
            background_tasks.add_task(
                _generate_description_bg,
                ObjectId(application_id),
                update_data["url"],
                db,
            )
        except Exception as e:
            logger.error(f"Failed to schedule description generation: {e}")

    updated_application = await db["applications"].find_one(
        {"_id": ObjectId(application_id)}
    )
    return serialize_mongodb_doc(updated_application)


@job_router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    application_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    application = await db["applications"].find_one({"_id": ObjectId(application_id)})

    if not application:
        raise HTTPException(status_code=404, detail="Candidature non trouvée")

    if str(application["user_id"]) != str(current_user.id):
        raise HTTPException(
            status_code=403, detail="Accès non autorisé à cette candidature"
        )

    await db["applications"].delete_one({"_id": ObjectId(application_id)})
    return None


@job_router.post("/{application_id}/notes", response_model=JobApplicationResponse)
async def add_note(
    application_id: str,
    note: str = Body(..., embed=True),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    application = await db["applications"].find_one({"_id": ObjectId(application_id)})

    if not application:
        raise HTTPException(status_code=404, detail="Candidature non trouvée")

    if str(application["user_id"]) != str(current_user.id):
        raise HTTPException(
            status_code=403, detail="Accès non autorisé à cette candidature"
        )

    await db["applications"].update_one(
        {"_id": ObjectId(application_id)},
        {"$push": {"notes": note}, "$set": {"updated_at": datetime.now(timezone.utc)}},
    )

    updated_application = await db["applications"].find_one(
        {"_id": ObjectId(application_id)}
    )

    return serialize_mongodb_doc(updated_application)
