import sys
from datetime import datetime, timezone
from typing import Optional

import pymongo
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from ...auth import get_current_user
from ...database import get_database
from ...models import ApiUsageAction, JobApplicationResponse, OfferEvaluationResponse, UserModel
from ...utils import serialize_mongodb_doc
from .background import sync_applied_interaction

router = APIRouter()


def _pkg():
    return sys.modules[__package__]


async def _find_owned_app(
    db, application_id: str, current_user: UserModel, *, validate_oid: bool = True
) -> dict:
    if validate_oid and not ObjectId.is_valid(application_id):
        raise HTTPException(status_code=400, detail="ID de candidature invalide")
    app_doc = await db["applications"].find_one({"_id": ObjectId(application_id)})
    if not app_doc:
        raise HTTPException(status_code=404, detail="Candidature non trouvée")
    if str(app_doc.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès non autorisé")
    return app_doc


async def _migrate_user_offer_data(user_id, old_offer_id, new_offer_id: str, db) -> None:
    """Rattache l'évaluation et le kit d'entretien de l'utilisateur au nouvel offer_id,
    sans écraser un document qu'il aurait déjà pour ce nouvel id.
    """
    def id_variants(value) -> list:
        return (
            [str(value), ObjectId(str(value))] if ObjectId.is_valid(str(value)) else [str(value)]
        )

    user_ids = id_variants(user_id)
    for collection in ("offer_evaluations", "interview_preps"):
        if await db[collection].find_one(
            {"user_id": {"$in": user_ids}, "offer_id": {"$in": id_variants(new_offer_id)}},
            {"_id": 1},
        ):
            continue
        await db[collection].update_many(
            {"user_id": {"$in": user_ids}, "offer_id": {"$in": id_variants(old_offer_id)}},
            {"$set": {"offer_id": str(new_offer_id)}},
        )


async def _ensure_offer_for_application(application_id: str, app_doc: dict, db) -> str:
    """Retrouve ou crée l'entrée job_offers correspondant à l'URL/poste de cette candidature,
    et lie son offer_id à l'application. Ne déclenche aucun scoring IA.
    """
    pkg = _pkg()
    offer_id = app_doc.get("offer_id")
    original_offer_id = offer_id
    now = datetime.now(timezone.utc)
    existing_offer = None

    # 1. Chercher par offer_id si déjà renseigné
    if offer_id and ObjectId.is_valid(offer_id):
        existing_offer = await db["job_offers"].find_one({"_id": ObjectId(offer_id)})

    app_url = app_doc.get("url")
    position = app_doc.get("position")
    poste = pkg.clean_job_title_syntax(position) if position else "Poste non spécifié"
    company = (app_doc.get("company") or "").strip()
    entreprise = company or "Non spécifié"
    localisation = app_doc.get("location") or None
    # Sans entreprise, pas de clé (l'index unique_key est sparse) : une telle candidature ne fusionne jamais
    computed_key = (
        pkg.compute_unique_key(company=company, position=poste, location=localisation)
        if company
        else None
    )
    probe = {
        "entreprise": entreprise,
        "poste": poste,
        "localisation": localisation,
        "url": str(app_url) if app_url else None,
        "description": app_doc.get("description"),
    }
    if computed_key:
        probe["unique_key"] = computed_key

    # 2-3. Chercher par clé/URL puis variante d'entreprise compatible
    if not existing_offer:
        existing_offer = await pkg.find_offer_by_identity(db["job_offers"], probe)
        if not existing_offer and company:
            existing_offer = await pkg.find_company_variant_duplicate(
                db["job_offers"], probe, await db["job_offers"].distinct("entreprise")
            )
        if existing_offer:
            offer_id = str(existing_offer["_id"])
            await db["applications"].update_one(
                {"_id": ObjectId(application_id)},
                {"$set": {"offer_id": offer_id, "updated_at": now}},
            )

    if existing_offer:
        current_desc = existing_offer.get("description") or ""
        app_desc = app_doc.get("description") or ""
        if app_desc and (not current_desc or current_desc in ("Description non disponible", "Non spécifié")):
            await db["job_offers"].update_one(
                {"_id": existing_offer["_id"]},
                {"$set": {"description": app_desc, "updated_at": now}},
            )

    # 4. Insérer une nouvelle offre avec gestion des collisions d'index
    if not existing_offer:
        new_offer_doc = {
            "poste": poste,
            "entreprise": entreprise,
            "localisation": localisation,
            "description": app_doc.get("description") or "Description non disponible",
            "url": str(app_url) if app_url else f"https://placeholder.local/{application_id}",
            "pipeline_stage": "discovered",
            "created_at": now,
            "updated_at": now,
            "is_deleted": False,
        }
        if computed_key:
            new_offer_doc["unique_key"] = computed_key
        try:
            res = await db["job_offers"].insert_one(new_offer_doc)
            offer_id = str(res.inserted_id)
        except pymongo.errors.DuplicateKeyError:
            fallback = await pkg.find_offer_by_identity(db["job_offers"], new_offer_doc)
            if fallback:
                offer_id = str(fallback["_id"])
            else:
                pkg.logger.error(
                    f"[_ensure_offer_for_application] DuplicateKeyError sans document correspondant pour app {application_id}"
                )
                raise HTTPException(
                    status_code=500, detail="Conflit de clé d'offre dans la base de données"
                )

        await db["applications"].update_one(
            {"_id": ObjectId(application_id)},
            {"$set": {"offer_id": offer_id, "updated_at": now}},
        )

    # L'offre d'origine a disparu : l'évaluation et le kit d'entretien suivent le nouvel id.
    if original_offer_id and app_doc.get("user_id") and str(original_offer_id) != str(offer_id):
        await pkg._migrate_user_offer_data(app_doc["user_id"], original_offer_id, offer_id, db)

    return offer_id


@router.post("/{application_id}/regenerate-description", response_model=JobApplicationResponse)
async def regenerate_application_description(
    application_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Régénère la synthèse/description de l'offre d'emploi à partir de son URL."""
    pkg = _pkg()
    application = await _find_owned_app(db, application_id, current_user, validate_oid=False)

    url = application.get("url")
    if not url or not str(url).strip():
        raise HTTPException(
            status_code=400,
            detail="Aucune URL d'offre associée à cette candidature pour régénérer la description",
        )

    await pkg.require_user_quota(db, current_user.id, ApiUsageAction.OFFER_SUMMARY)

    try:
        docs = await pkg.fetch_documents(str(url).strip())
        if not docs:
            raise HTTPException(
                status_code=400,
                detail="Impossible d'extraire le contenu depuis l'URL de l'offre",
            )

        chunks = pkg.split_documents(docs)
        usage_acc: list = []
        description = await pkg.summarize_chunks(chunks, usage_acc=usage_acc)
        if usage_acc:
            await pkg.record_api_usage(
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
            {"$set": {"description": description, "updated_at": datetime.now(timezone.utc)}},
        )
        updated = await db["applications"].find_one({"_id": ObjectId(application_id)})
        if updated:
            await pkg._ensure_offer_for_application(str(application_id), updated, db)
            updated = await db["applications"].find_one({"_id": ObjectId(application_id)})
        return pkg.enrich_application_with_cadences(serialize_mongodb_doc(updated))
    except HTTPException:
        raise
    except Exception as e:
        pkg.logger.error(f"[regenerate_description] Erreur: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur lors de la régénération : {str(e)}")


@router.post("/{application_id}/link-offer", response_model=JobApplicationResponse)
async def link_application_offer(
    application_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Crée ou retrouve l'offre associée à cette candidature (par URL, poste ou clé d'unicité),
    sans lancer le scoring IA — permet de consulter l'offre avant de payer une évaluation.
    """
    pkg = _pkg()
    app_doc = await _find_owned_app(db, application_id, current_user)
    await pkg._ensure_offer_for_application(application_id, app_doc, db)

    updated = await db["applications"].find_one({"_id": ObjectId(application_id)})
    if updated and updated.get("offer_id"):
        try:
            await sync_applied_interaction(db, str(current_user.id), str(updated["offer_id"]))
        except Exception as e_interact:
            pkg.logger.warning(
                f"[link_application_offer] Erreur mise à jour interaction 'applied': {e_interact}"
            )

    return pkg.enrich_application_with_cadences(serialize_mongodb_doc(updated))


@router.post("/{application_id}/evaluate", response_model=OfferEvaluationResponse)
async def evaluate_application_offer(
    application_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Évalue l'offre liée à une candidature via le pipeline Two-Pass (Gemini 3.7 Flash).
    Si la candidature n'est pas encore liée à une offre scrapée, une entrée job_offers est initialisée automatiquement.
    """
    pkg = _pkg()
    app_doc = await _find_owned_app(db, application_id, current_user)
    offer_id = await pkg._ensure_offer_for_application(application_id, app_doc, db)

    try:
        return await pkg.evaluate_offer_two_pass(
            offer_id=offer_id,
            user_id=str(current_user.id),
            db=db,
        )
    except HTTPException:
        raise
    except Exception as e:
        pkg.logger.error(
            f"[evaluate_application_offer] Erreur Two-Pass pour app {application_id}: {e}",
            exc_info=True,
        )
        raise pkg.llm_http_exception(e) or HTTPException(
            status_code=500, detail=f"Erreur lors du scoring IA : {str(e)}"
        )


@router.get("/{application_id}/evaluation", response_model=Optional[OfferEvaluationResponse])
async def get_application_evaluation(
    application_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Récupère l'évaluation Two-Pass existante pour l'offre liée à cette candidature."""
    app_doc = await _find_owned_app(db, application_id, current_user)
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
