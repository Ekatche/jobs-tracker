import asyncio
from fastapi import APIRouter, Body, Depends, status, HTTPException, BackgroundTasks
from typing import Dict, List, Optional
from bson import ObjectId
from datetime import datetime, timezone
import pymongo
import logging
from fastapi.encoders import jsonable_encoder

from ..models import (
    ApiUsageAction,
    ApplicationStatus,
    JobApplicationCreate,
    JobApplicationResponse,
    JobApplicationUpdate,
    OfferEvaluationResponse,
    PipelineSummaryResponse,
    UserModel,
)
from ..database import get_database
from ..utils import serialize_mongodb_doc, capitalize_words
from ..auth import get_current_user
from ..llm.utils import fetch_documents, split_documents, summarize_chunks
from ..services.evaluation.evaluator import evaluate_offer_two_pass
from ..services.usage_tracker import record_api_usage, require_user_quota

logger = logging.getLogger(__name__)

job_router = APIRouter(prefix="/applications", tags=["applications"])


async def _generate_description_bg(application_id: ObjectId, user_id: ObjectId, url: str, db):
    logger.info(f"[description_bg] Démarrage pour ID={application_id}, URL={url}")
    try:
        docs = await fetch_documents(url)
        if not docs:
            logger.warning(f"[description_bg] Aucun document récupéré pour {url}")
            return

        chunks = split_documents(docs)

        usage_acc: list = []
        description = await summarize_chunks(chunks, usage_acc=usage_acc)

        if usage_acc:
            await record_api_usage(
                db=db,
                user_id=user_id,
                action=ApiUsageAction.OFFER_SUMMARY,
                models_used=[u["model"] for u in usage_acc],
                input_tokens=sum(u["input_tokens"] for u in usage_acc),
                output_tokens=sum(u["output_tokens"] for u in usage_acc),
                metadata={"application_id": str(application_id)},
            )

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


async def _append_letter_version(db, letter_id, version: dict) -> None:
    """Ajoute une version numérotée sans jamais écraser les précédentes."""
    letter = await db["cover_letters"].find_one({"_id": letter_id})
    version["n"] = len(letter.get("versions", [])) + 1
    await db["cover_letters"].update_one(
        {"_id": letter_id},
        {
            "$set": {
                "status": "ready",
                "current_version": version["n"],
                "updated_at": datetime.now(timezone.utc),
            },
            "$push": {"versions": version},
        },
    )


async def _generate_cover_letter_bg(application_id: ObjectId, user_id: ObjectId, db):
    logger.info(f"[cover_letter_bg] Démarrage pour ID={application_id}, user_id={user_id}")
    letter_id = None
    try:
        # 1. Idempotence : un échec antérieur ne doit pas geler la candidature.
        existing = await db["cover_letters"].find_one(
            {"application_id": ObjectId(application_id)}
        )
        if existing and existing.get("status") == "ready":
            logger.info(f"[cover_letter_bg] Lettre déjà prête pour {application_id}, pas de relance.")
            return
        if existing and existing.get("status") == "failed":
            await db["cover_letters"].delete_many(
                {"application_id": ObjectId(application_id), "status": "failed"}
            )
            existing = None

        # 2. Un seul document résolu avant tout travail susceptible d'échouer :
        #    celui déjà en "pending" (relance/régénération), ou un nouveau.
        if existing:
            letter_id = existing["_id"]
        else:
            letter_id = (await db["cover_letters"].insert_one({
                "user_id": ObjectId(user_id),
                "application_id": ObjectId(application_id),
                "status": "pending",
                "versions": [],
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            })).inserted_id

        # 3. Vérification candidature et description
        app_doc = await db["applications"].find_one({"_id": ObjectId(application_id)})
        if not app_doc:
            return

        offer_desc = app_doc.get("description")
        if not offer_desc:
            if app_doc.get("url"):
                await _generate_description_bg(ObjectId(application_id), user_id, str(app_doc["url"]), db)
                app_doc = await db["applications"].find_one({"_id": ObjectId(application_id)})
                offer_desc = app_doc.get("description") if app_doc else None

        if not offer_desc:
            await db["cover_letters"].update_one(
                {"_id": letter_id},
                {"$set": {"status": "failed", "error": "description_missing", "updated_at": datetime.now(timezone.utc)}}
            )
            return

        # 4. Vérification profil candidat
        profile_doc = await db["candidate_profile"].find_one({"user_id": ObjectId(user_id)})
        if not profile_doc:
            await db["cover_letters"].update_one(
                {"_id": letter_id},
                {"$set": {"status": "failed", "error": "profile_missing", "updated_at": datetime.now(timezone.utc)}}
            )
            return

        # 5. Exécution asynchrone via asyncio.to_thread pour isoler Motor
        import sys
        from pathlib import Path
        job_trackers_path = Path(__file__).parent.parent.parent / "job_trackers" / "src" / "job_trackers"
        if str(job_trackers_path) not in sys.path:
            sys.path.insert(0, str(job_trackers_path))
        from cover_letter_crew import run_letter_pipeline_sync

        user_doc = await db["users"].find_one({"_id": ObjectId(user_id)})
        full_name = (user_doc or {}).get("full_name") or ""

        pipeline_res = await asyncio.to_thread(
            run_letter_pipeline_sync,
            offer_desc,
            profile_doc,
            app_doc.get("company", "l'entreprise"),
            full_name,
        )
        version_entry = {
            "body": pipeline_res["body"],
            "origin": "generated",
            "models": pipeline_res["models"],
            "prompt_version": pipeline_res["prompt_version"],
            "guard_report": pipeline_res["guard_report"],
            "critic_verdict": pipeline_res["critic_verdict"],
            "revised": pipeline_res["revised"],
            "created_at": datetime.now(timezone.utc),
        }
        await _append_letter_version(db, letter_id, version_entry)

        usage = pipeline_res.get("usage") or {}
        if usage.get("input_tokens") or usage.get("output_tokens"):
            await record_api_usage(
                db=db,
                user_id=user_id,
                action=ApiUsageAction.COVER_LETTER,
                models_used=usage.get("models_used", []),
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                metadata={"application_id": str(application_id)},
            )
    except Exception as e:
        logger.error(f"[cover_letter_bg] Erreur lors de la génération pour {application_id}: {e}")
        try:
            from letter_llm import format_llm_error
            err_message = format_llm_error(e)
        except Exception:
            err_message = str(e)

        if letter_id is not None:
            await db["cover_letters"].update_one(
                {"_id": letter_id},
                {"$set": {"status": "failed", "error": err_message, "updated_at": datetime.now(timezone.utc)}}
            )
        else:
            await db["cover_letters"].update_one(
                {"application_id": ObjectId(application_id)},
                {"$set": {"status": "failed", "error": err_message, "updated_at": datetime.now(timezone.utc)}}
            )


def enrich_application_with_cadences(app_dict: dict) -> dict:
    """Calculate days_since_application and automated follow-up cadences."""
    if not app_dict:
        return app_dict

    app_date = app_dict.get("application_date")
    app_status = app_dict.get("status")

    days = 0
    if app_date:
        if isinstance(app_date, str):
            try:
                dt = datetime.fromisoformat(app_date.replace("Z", "+00:00"))
            except Exception:
                dt = datetime.now(timezone.utc)
        elif isinstance(app_date, datetime):
            dt = app_date
        else:
            dt = datetime.now(timezone.utc)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        diff = now - dt
        days = max(0, diff.days)

    app_dict["days_since_application"] = days

    status_str = str(app_status) if app_status else ""
    # Automated follow-up cadences:
    # 1. "Candidature envoyée" (APPLIED) and >= 7 days -> follow_up_due (Relance J+7)
    # 2. "Entretien" (INTERVIEW) and >= 1 day -> remerciement_due (Remerciement J+1)
    if (status_str == ApplicationStatus.APPLIED.value or status_str == "Candidature envoyée") and days >= 7:
        app_dict["follow_up_alert"] = "relance_due"
    elif (status_str == ApplicationStatus.INTERVIEW.value or status_str == "Entretien") and days >= 1:
        app_dict["follow_up_alert"] = "remerciement_due"
    else:
        app_dict["follow_up_alert"] = None

    return app_dict


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
        await require_user_quota(db, current_user.id, ApiUsageAction.OFFER_SUMMARY)
        try:
            url = app_data.get("url")
            logger.info(f"[create_application] URL: {url!r}, ID: {result.inserted_id}")
            app_id = result.inserted_id
            background_tasks.add_task(_generate_description_bg, app_id, current_user.id, url.strip(), db)
            logger.info(f"[create_application] Tâche planifiée pour URL: {url}")
        except Exception as e:
            logger.error(f"[create_application] Erreur: {str(e)}")

    return enrich_application_with_cadences(serialize_mongodb_doc(created))


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
        serialized_applications.append(enrich_application_with_cadences(serialized_app))

    return serialized_applications


@job_router.get("/pipeline/summary", response_model=PipelineSummaryResponse)
async def get_pipeline_summary(
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Calcule le résumé du pipeline, les taux de conversion et les cadences de relance."""
    user_apps = (
        await db["applications"]
        .find({"user_id": current_user.id})
        .to_list(length=1000)
    )

    total_active = 0
    total_archived = 0
    status_counts: Dict[str, int] = {s.value: 0 for s in ApplicationStatus}
    follow_ups_due = 0
    thank_yous_due = 0

    interview_stages = {
        ApplicationStatus.SCREENING.value,
        ApplicationStatus.INTERVIEW.value,
        ApplicationStatus.TECHNICAL_TEST.value,
        ApplicationStatus.NEGOTIATION.value,
        ApplicationStatus.OFFER.value,
        ApplicationStatus.OFFER_RECEIVED.value,
        ApplicationStatus.ACCEPTED.value,
    }
    offer_stages = {
        ApplicationStatus.OFFER.value,
        ApplicationStatus.OFFER_RECEIVED.value,
        ApplicationStatus.ACCEPTED.value,
    }

    interview_count = 0
    offer_count = 0
    total_started = 0

    for doc in user_apps:
        enriched = enrich_application_with_cadences(serialize_mongodb_doc(doc))
        is_archived = bool(enriched.get("archived", False))
        status_val = enriched.get("status")

        if is_archived:
            total_archived += 1
        else:
            total_active += 1

        if status_val:
            status_counts[status_val] = status_counts.get(status_val, 0) + 1

        # Alertes de cadences
        if enriched.get("follow_up_alert") == "relance_due":
            follow_ups_due += 1
        elif enriched.get("follow_up_alert") == "remerciement_due":
            thank_yous_due += 1

        # Statistiques de conversion
        if status_val:
            total_started += 1
            if status_val in interview_stages:
                interview_count += 1
            if status_val in offer_stages:
                offer_count += 1

    interview_rate = (
        round((interview_count / total_started * 100), 1) if total_started > 0 else 0.0
    )
    offer_rate = (
        round((offer_count / total_started * 100), 1) if total_started > 0 else 0.0
    )

    # Décompte des offres évaluées avec score >= 3.5 prêtes à postuler
    eval_count = await db["offer_evaluations"].count_documents({
        "user_id": str(current_user.id),
        "score": {"$gte": 3.5},
    })

    return PipelineSummaryResponse(
        total_active=total_active,
        total_archived=total_archived,
        status_counts=status_counts,
        interview_conversion_rate=interview_rate,
        offer_conversion_rate=offer_rate,
        follow_ups_due_count=follow_ups_due,
        thank_yous_due_count=thank_yous_due,
        evaluated_offers_ready_count=eval_count,
    )


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

    return enrich_application_with_cadences(serialize_mongodb_doc(application))


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
        await require_user_quota(db, application["user_id"], ApiUsageAction.OFFER_SUMMARY)
        try:
            background_tasks.add_task(
                _generate_description_bg,
                ObjectId(application_id),
                application["user_id"],
                update_data["url"],
                db,
            )
        except Exception as e:
            logger.error(f"Failed to schedule description generation: {e}")

    status_changed = "status" in update_data and update_data["status"] != application.get("status")
    if status_changed and update_data["status"] == ApplicationStatus.ETUDE:
        await require_user_quota(db, application["user_id"], ApiUsageAction.COVER_LETTER)
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
    return enrich_application_with_cadences(serialize_mongodb_doc(updated_application))


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

    return enrich_application_with_cadences(serialize_mongodb_doc(updated_application))


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

    await require_user_quota(db, current_user.id, ApiUsageAction.OFFER_SUMMARY)

    try:
        docs = await fetch_documents(str(url).strip())
        if not docs:
            raise HTTPException(
                status_code=400,
                detail="Impossible d'extraire le contenu depuis l'URL de l'offre",
            )

        chunks = split_documents(docs)
        usage_acc: list = []
        description = await summarize_chunks(chunks, usage_acc=usage_acc)
        if usage_acc:
            await record_api_usage(
                db=db,
                user_id=current_user.id,
                action=ApiUsageAction.OFFER_SUMMARY,
                models_used=[u["model"] for u in usage_acc],
                input_tokens=sum(u["input_tokens"] for u in usage_acc),
                output_tokens=sum(u["output_tokens"] for u in usage_acc),
                metadata={"application_id": str(application_id)},
            )
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
        return enrich_application_with_cadences(serialize_mongodb_doc(updated))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[regenerate_description] Erreur: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de la régénération : {str(e)}")


@job_router.post("/{application_id}/evaluate", response_model=OfferEvaluationResponse)
async def evaluate_application_offer(
    application_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Évalue l'offre liée à une candidature via le pipeline Two-Pass (Gemini 3.7 Flash).
    Si la candidature n'est pas encore liée à une offre scrapée, une entrée job_offers est initialisée automatiquement.
    """
    if not ObjectId.is_valid(application_id):
        raise HTTPException(status_code=400, detail="ID de candidature invalide")

    app_doc = await db["applications"].find_one({"_id": ObjectId(application_id)})
    if not app_doc:
        raise HTTPException(status_code=404, detail="Candidature non trouvée")

    if str(app_doc.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    offer_id = app_doc.get("offer_id")

    # Si pas d'offer_id ou si l'offre n'existe pas en base, créer une entrée job_offers
    existing_offer = None
    if offer_id and ObjectId.is_valid(offer_id):
        existing_offer = await db["job_offers"].find_one({"_id": ObjectId(offer_id)})

    if not existing_offer:
        now = datetime.now(timezone.utc)
        new_offer_doc = {
            "poste": app_doc.get("position") or "Poste non spécifié",
            "entreprise": app_doc.get("company") or "Entreprise",
            "localisation": app_doc.get("location") or "France",
            "description": app_doc.get("description") or "Description non disponible",
            "url": str(app_doc.get("url")) if app_doc.get("url") else "https://placeholder.local",
            "pipeline_stage": "discovered",
            "created_at": now,
            "updated_at": now,
            "is_deleted": False,
        }
        res = await db["job_offers"].insert_one(new_offer_doc)
        offer_id = str(res.inserted_id)

        # Lier l'offer_id à l'application
        await db["applications"].update_one(
            {"_id": ObjectId(application_id)},
            {"$set": {"offer_id": offer_id, "updated_at": now}}
        )

    # Exécuter l'évaluation Two-Pass
    evaluation = await evaluate_offer_two_pass(
        offer_id=offer_id,
        user_id=str(current_user.id),
        db=db,
    )

    return evaluation


@job_router.get("/{application_id}/evaluation", response_model=Optional[OfferEvaluationResponse])
async def get_application_evaluation(
    application_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Récupère l'évaluation Two-Pass existante pour l'offre liée à cette candidature."""
    if not ObjectId.is_valid(application_id):
        raise HTTPException(status_code=400, detail="ID de candidature invalide")

    app_doc = await db["applications"].find_one({"_id": ObjectId(application_id)})
    if not app_doc:
        raise HTTPException(status_code=404, detail="Candidature non trouvée")

    if str(app_doc.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    offer_id = app_doc.get("offer_id")
    if not offer_id:
        return None

    evaluation = await db["offer_evaluations"].find_one({
        "offer_id": str(offer_id),
        "user_id": str(current_user.id),
    })

    if not evaluation:
        return None

    evaluation["id"] = str(evaluation["_id"])
    return OfferEvaluationResponse(**evaluation)


