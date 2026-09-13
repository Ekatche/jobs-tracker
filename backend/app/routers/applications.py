import asyncio
from fastapi import APIRouter, Body, Depends, status, HTTPException, BackgroundTasks
from typing import List, Optional
from bson import ObjectId
from datetime import datetime, timezone
import pymongo
import logging
from fastapi.encoders import jsonable_encoder

from ..models import (
    ApplicationStatus,
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


async def _generate_cover_letter_bg(application_id: ObjectId, user_id: ObjectId, db):
    logger.info(f"[cover_letter_bg] Démarrage pour ID={application_id}, user_id={user_id}")
    try:
        # 1. Vérification idempotence
        existing = await db["cover_letters"].find_one({"application_id": ObjectId(application_id)})
        if existing:
            logger.info(f"[cover_letter_bg] Lettre déjà existante pour {application_id}, pas de relance.")
            return

        # 2. Vérification candidature et description
        app_doc = await db["applications"].find_one({"_id": ObjectId(application_id)})
        if not app_doc:
            return

        offer_desc = app_doc.get("description")
        if not offer_desc:
            if app_doc.get("url"):
                await _generate_description_bg(ObjectId(application_id), str(app_doc["url"]), db)
                app_doc = await db["applications"].find_one({"_id": ObjectId(application_id)})
                offer_desc = app_doc.get("description") if app_doc else None

        if not offer_desc:
            await db["cover_letters"].insert_one({
                "user_id": ObjectId(user_id),
                "application_id": ObjectId(application_id),
                "status": "failed",
                "error": "description_missing",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            })
            return

        # 3. Vérification profil candidat
        profile_doc = await db["candidate_profile"].find_one({"user_id": ObjectId(user_id)})
        if not profile_doc:
            await db["cover_letters"].insert_one({
                "user_id": ObjectId(user_id),
                "application_id": ObjectId(application_id),
                "status": "failed",
                "error": "profile_missing",
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            })
            return

        # Initialisation statut pending
        letter_id = (await db["cover_letters"].insert_one({
            "user_id": ObjectId(user_id),
            "application_id": ObjectId(application_id),
            "status": "pending",
            "versions": [],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        })).inserted_id

        # 4. Exécution asynchrone via asyncio.to_thread pour isoler Motor
        import sys
        from pathlib import Path
        job_trackers_path = Path(__file__).parent.parent.parent / "job_trackers" / "src" / "job_trackers"
        if str(job_trackers_path) not in sys.path:
            sys.path.insert(0, str(job_trackers_path))
        from cover_letter_crew import run_letter_pipeline_sync

        pipeline_res = await asyncio.to_thread(
            run_letter_pipeline_sync,
            offer_desc,
            profile_doc,
            app_doc.get("company", "l'entreprise")
        )
        version_entry = {
            "n": 1,
            "body": pipeline_res["body"],
            "origin": "generated",
            "models": pipeline_res["models"],
            "guard_report": pipeline_res["guard_report"],
            "critic_verdict": pipeline_res["critic_verdict"],
            "revised": pipeline_res["revised"],
            "created_at": datetime.now(timezone.utc),
        }
        await db["cover_letters"].update_one(
            {"_id": letter_id},
            {
                "$set": {
                    "status": "ready",
                    "current_version": 1,
                    "updated_at": datetime.now(timezone.utc)
                },
                "$push": {"versions": version_entry}
            }
        )
    except Exception as e:
        logger.error(f"[cover_letter_bg] Erreur lors de la génération pour {application_id}: {e}")
        try:
            from letter_llm import format_llm_error
            err_message = format_llm_error(e)
        except Exception:
            err_message = str(e)

        await db["cover_letters"].update_one(
            {"application_id": ObjectId(application_id)},
            {"$set": {"status": "failed", "error": err_message, "updated_at": datetime.now(timezone.utc)}}
        )


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

    status_changed = "status" in update_data and update_data["status"] != application.get("status")
    if status_changed and update_data["status"] == ApplicationStatus.ETUDE:
        try:
            background_tasks.add_task(
                _generate_cover_letter_bg,
                ObjectId(application_id),
                ObjectId(application["user_id"]),
                db,
            )
        except Exception as e:
            logger.error(f"Failed to schedule cover letter generation: {e}")

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


@job_router.post(
    "/{application_id}/regenerate-description",
    response_model=JobApplicationResponse,
)
async def regenerate_application_description(
    application_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """
    Régénère la synthèse/description de l'offre d'emploi à partir de son URL.
    """
    application = await db["applications"].find_one({"_id": ObjectId(application_id)})
    if not application:
        raise HTTPException(status_code=404, detail="Candidature non trouvée")

    if str(application["user_id"]) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    url = application.get("url")
    if not url or not str(url).strip():
        raise HTTPException(
            status_code=400,
            detail="Aucune URL d'offre associée à cette candidature pour régénérer la description",
        )

    try:
        docs = await fetch_documents(str(url).strip())
        if not docs:
            raise HTTPException(
                status_code=400,
                detail="Impossible d'extraire le contenu depuis l'URL de l'offre",
            )

        chunks = split_documents(docs)
        description = await summarize_chunks(chunks)
        if not description:
            raise HTTPException(
                status_code=422,
                detail="Impossible d'extraire une description exploitable depuis cette offre (contenu protégé ou non identifiable)",
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
        updated = await db["applications"].find_one({"_id": ObjectId(application_id)})
        return serialize_mongodb_doc(updated)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[regenerate_description] Erreur: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de la régénération : {str(e)}")

