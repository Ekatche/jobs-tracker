import sys
from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId

from ...models import ApiUsageAction, ApplicationStatus


def _pkg():
    return sys.modules[__package__]


async def sync_applied_interaction(db, user_id: str, offer_id: str) -> None:
    """Upsert user_offer_interactions to record an applied, seen status."""
    now_utc = datetime.now(timezone.utc)
    await db["user_offer_interactions"].update_one(
        {"user_id": str(user_id), "offer_id": str(offer_id)},
        {
            "$set": {"status": "applied", "seen": True, "updated_at": now_utc},
            "$setOnInsert": {"created_at": now_utc, "notes": None},
        },
        upsert=True,
    )


async def _generate_description_bg(application_id: ObjectId, user_id: ObjectId, url: str, db):
    pkg = _pkg()
    pkg.logger.info(f"[description_bg] Démarrage pour ID={application_id}, URL={url}")
    try:
        docs = await pkg.fetch_documents(url)
        if not docs:
            pkg.logger.warning(f"[description_bg] Aucun document récupéré pour {url}")
            return

        chunks = pkg.split_documents(docs)
        usage_acc: list = []
        description = await pkg.summarize_chunks(chunks, usage_acc=usage_acc)

        if usage_acc:
            await pkg.record_api_usage(
                db=db,
                user_id=user_id,
                action=ApiUsageAction.OFFER_SUMMARY,
                models_used=[u["model"] for u in usage_acc],
                input_tokens=sum(u["input_tokens"] for u in usage_acc),
                output_tokens=sum(u["output_tokens"] for u in usage_acc),
                metadata={"application_id": str(application_id)},
            )

        if description:
            pkg.logger.info(f"[description_bg] Description générée ({len(description)} chars)")
            await db["applications"].update_one(
                {"_id": ObjectId(application_id)},
                {"$set": {"description": description, "updated_at": datetime.now(timezone.utc)}},
            )
            # Auto-lier l'offre pour débloquer le CV adapté et l'évaluation
            app_doc = await db["applications"].find_one({"_id": ObjectId(application_id)})
            if app_doc:
                linked_oid = await pkg._ensure_offer_for_application(str(application_id), app_doc, db)
                if linked_oid:
                    await sync_applied_interaction(db, str(user_id), str(linked_oid))
        else:
            pkg.logger.warning("[description_bg] Échec de génération de description")
    except Exception as e:
        pkg.logger.error(f"[description_bg] Erreur: {str(e)}")


async def _append_letter_version(
    db, letter_id, version: dict, guard_context: dict | None = None
) -> None:
    """Ajoute une version numérotée sans jamais écraser les précédentes."""
    pkg = _pkg()
    letter = await db["cover_letters"].find_one({"_id": letter_id})
    version["n"] = len(letter.get("versions", [])) + 1
    if isinstance(version.get("body"), str):
        version["body"] = pkg.clean_invisible_markers(version["body"])
    # Un rapport de garde encore bloquant (après révisions) ne rend pas la lettre prête.
    blocking = (version.get("guard_report") or {}).get("is_blocking")
    update_set = {
        "status": "needs_review" if blocking else "ready",
        "current_version": version["n"],
        "updated_at": datetime.now(timezone.utc),
    }
    if guard_context:
        update_set["guard_context"] = guard_context
    await db["cover_letters"].update_one(
        {"_id": letter_id},
        {"$set": update_set, "$push": {"versions": version}},
    )


async def _resolve_pending_letter_id(db, application_id: ObjectId, user_id: ObjectId):
    """Ensure idempotency and return the letter_id to populate, or None if already done."""
    pkg = _pkg()
    existing = await db["cover_letters"].find_one({"application_id": ObjectId(application_id)})
    if existing and existing.get("status") in ("ready", "needs_review"):
        pkg.logger.info(
            f"[cover_letter_bg] Lettre déjà générée pour {application_id}, pas de relance."
        )
        return None
    if existing and existing.get("status") == "failed":
        await db["cover_letters"].delete_many(
            {"application_id": ObjectId(application_id), "status": "failed"}
        )
        existing = None
    if existing:
        return existing["_id"]
    res = await db["cover_letters"].insert_one({
        "user_id": ObjectId(user_id),
        "application_id": ObjectId(application_id),
        "status": "pending",
        "versions": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })
    return res.inserted_id


async def _mark_letter_failed(db, letter_id, application_id: ObjectId, err_message: str) -> None:
    query = {"_id": letter_id} if letter_id is not None else {"application_id": ObjectId(application_id)}
    await db["cover_letters"].update_one(
        query,
        {"$set": {"status": "failed", "error": err_message, "updated_at": datetime.now(timezone.utc)}},
    )


async def _generate_cover_letter_bg(application_id: ObjectId, user_id: ObjectId, db):
    pkg = _pkg()
    pkg.logger.info(f"[cover_letter_bg] Démarrage pour ID={application_id}, user_id={user_id}")
    letter_id = None
    try:
        # 1-2. Idempotence et résolution du document lettre
        letter_id = await _resolve_pending_letter_id(db, application_id, user_id)
        if letter_id is None:
            return

        # 3. Vérification candidature et description
        app_doc = await db["applications"].find_one({"_id": ObjectId(application_id)})
        if not app_doc:
            return

        offer_desc = app_doc.get("description")
        if not offer_desc and app_doc.get("url"):
            await pkg._generate_description_bg(
                ObjectId(application_id), user_id, str(app_doc["url"]), db
            )
            app_doc = await db["applications"].find_one({"_id": ObjectId(application_id)})
            offer_desc = app_doc.get("description") if app_doc else None

        if not offer_desc:
            await _mark_letter_failed(db, letter_id, application_id, "description_missing")
            return

        # 4. Vérification profil candidat
        profile_doc = await db["candidate_profile"].find_one({"user_id": ObjectId(user_id)})
        if not profile_doc:
            await _mark_letter_failed(db, letter_id, application_id, "profile_missing")
            return

        # 5. Exécution asynchrone native
        job_trackers_path = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "job_trackers"
            / "src"
            / "job_trackers"
        )
        if str(job_trackers_path) not in sys.path:
            sys.path.insert(0, str(job_trackers_path))
        from cover_letter_crew import run_letter_pipeline_async

        user_doc = await db["users"].find_one({"_id": ObjectId(user_id)})
        full_name = (user_doc or {}).get("full_name") or ""

        pipeline_res = await run_letter_pipeline_async(
            offer_desc,
            profile_doc,
            app_doc.get("company", "l'entreprise"),
            full_name,
            job_title=app_doc.get("position") or "",
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
        await pkg._append_letter_version(
            db, letter_id, version_entry, pipeline_res.get("guard_context")
        )

        usage = pipeline_res.get("usage") or {}
        if usage.get("input_tokens") or usage.get("output_tokens"):
            await pkg.record_api_usage(
                db=db,
                user_id=user_id,
                action=ApiUsageAction.COVER_LETTER,
                models_used=usage.get("models_used", []),
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                metadata={"application_id": str(application_id)},
            )
    except Exception as e:
        pkg.logger.error(f"[cover_letter_bg] Erreur lors de la génération pour {application_id}: {e}")
        provider_error = pkg.classify_llm_error(e)
        if provider_error is not None:
            err_message = provider_error.message
        else:
            try:
                from letter_llm import format_llm_error

                err_message = format_llm_error(e)
            except Exception:
                err_message = str(e)
        await _mark_letter_failed(db, letter_id, application_id, err_message)


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

        diff = datetime.now(timezone.utc) - dt
        days = max(0, diff.days)

    app_dict["days_since_application"] = days

    status_str = str(app_status) if app_status else ""
    # Automated follow-up cadences:
    # 1. "Candidature envoyée" (APPLIED) and >= 7 days -> follow_up_due (Relance J+7)
    # 2. "Entretien" (INTERVIEW) and >= 1 day -> remerciement_due (Remerciement J+1)
    if (
        status_str == ApplicationStatus.APPLIED.value or status_str == "Candidature envoyée"
    ) and days >= 7:
        app_dict["follow_up_alert"] = "relance_due"
    elif (
        status_str == ApplicationStatus.INTERVIEW.value or status_str == "Entretien"
    ) and days >= 1:
        app_dict["follow_up_alert"] = "remerciement_due"
    else:
        app_dict["follow_up_alert"] = None

    return app_dict
