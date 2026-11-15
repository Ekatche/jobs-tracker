import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, BackgroundTasks, Body, Depends, File, HTTPException, UploadFile
from pydantic import ValidationError

from app.auth import get_current_user
from app.database import get_database
from app.llm.provider_errors import llm_http_exception
from app.models import ApiUsageAction, CandidatePreferences, CandidateProfile, UserModel
from app.utils import serialize_mongodb_doc

router = APIRouter()


def _pkg():
    return sys.modules[__package__]


def safe_remove(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as exc:
        _pkg().logger.warning(f"Impossible de supprimer le fichier temporaire {path}: {exc}")


async def _read_upload(file: UploadFile, magic: bytes) -> bytes:
    """Read an uploaded file enforcing the size cap and magic bytes check."""
    pkg = _pkg()
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(1024 * 1024):
        total += len(chunk)
        if total > pkg.MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Fichier trop volumineux (10 Mo maximum)")
        chunks.append(chunk)
    content = b"".join(chunks)
    if not content.startswith(magic):
        raise HTTPException(status_code=400, detail="Le contenu du fichier n'est pas un PDF valide")
    return content


async def store_source(db, user_id: str, name: str, payload: dict) -> dict:
    """Store one profile source, rebuild the merged profile, and return serialized doc."""
    pkg = _pkg()
    existing = await db["candidate_profile"].find_one({"user_id": ObjectId(user_id)}) or {}
    sources = dict(existing.get("sources") or {})
    sources[name] = payload

    derived, conflicts = pkg.build_profile_from_sources(sources)
    document = {
        **derived,
        "sources": sources,
        "conflicts": conflicts,
        "user_id": ObjectId(user_id),
        "updated_at": datetime.now(timezone.utc),
    }
    try:
        CandidateProfile.model_validate({**document, "user_id": str(user_id)})
    except ValidationError:
        pkg.logger.exception(
            "Le profil dérivé après import de la source %s est invalide pour %s", name, user_id
        )
        raise HTTPException(status_code=502, detail="Le profil obtenu n'a pas pu être validé")

    await db["candidate_profile"].update_one(
        {"user_id": ObjectId(user_id)}, {"$set": document}, upsert=True
    )
    stored = await db["candidate_profile"].find_one({"user_id": ObjectId(user_id)})
    return serialize_mongodb_doc(stored)


async def record_cv_parsing_usage(db, user_id, usage) -> None:
    """Record billable CV-parsing calls as a single quota ledger entry."""
    pkg = _pkg()
    calls = [usage] if isinstance(usage, dict) else list(usage or [])
    calls = [c for c in calls if isinstance(c, dict) and c.get("model")]
    if not calls:
        return
    await pkg.record_api_usage(
        db=db,
        user_id=user_id,
        action=ApiUsageAction.CV_PARSING,
        models_used=list(dict.fromkeys(c["model"] for c in calls)),
        input_tokens=sum(c.get("input_tokens", 0) for c in calls),
        output_tokens=sum(c.get("output_tokens", 0) for c in calls),
        estimated_cost_usd=sum(
            pkg.estimate_llm_cost(c["model"], c.get("input_tokens", 0), c.get("output_tokens", 0))
            for c in calls
        ),
    )


@router.get("/profile/candidate")
async def get_candidate_profile(
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    prof = await db["candidate_profile"].find_one({"user_id": ObjectId(current_user.id)})
    if not prof:
        raise HTTPException(status_code=404, detail="Profil non initialisé")
    return serialize_mongodb_doc(prof)


@router.post("/profile/candidate/sources/cv")
async def import_cv_source(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    pkg = _pkg()
    await pkg.require_user_quota(db, current_user.id, ApiUsageAction.CV_PARSING)

    content = await _read_upload(file, pkg.PDF_MAGIC)
    os.makedirs(pkg.UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(pkg.UPLOAD_DIR, f"cv_{current_user.id}_{uuid4().hex}.pdf")

    try:
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        if await asyncio.to_thread(pkg.is_pdf_password_protected, file_path):
            raise HTTPException(status_code=400, detail=pkg.PROTECTED_PDF_MESSAGE)
        if not await asyncio.to_thread(pkg.is_pdf_readable, file_path):
            raise HTTPException(status_code=400, detail=pkg.UNREADABLE_PDF_MESSAGE)
        text = await asyncio.to_thread(pkg.extract_text_from_pdf, file_path)
        try:
            payload = await pkg.parse_cv_with_llm(text, pdf_path=file_path)
        except TypeError:
            payload = await pkg.parse_cv_with_llm(text)
        if pkg.is_empty_extraction(payload):
            raise HTTPException(status_code=400, detail=pkg.EMPTY_CV_MESSAGE)
        await record_cv_parsing_usage(db, current_user.id, payload.pop("_usage", None))
        import_report = payload.pop("_import_report", None)
        stored = await pkg._store_source(db, str(current_user.id), "cv", payload)
        return {**stored, "import_report": import_report} if import_report else stored
    except HTTPException:
        raise
    except pkg.CVVisionUnavailable as exc:
        pkg.logger.warning(
            "Analyse visuelle du CV indisponible (%s)",
            type(exc.__cause__).__name__ if exc.__cause__ else "VLM non tenté",
        )
        raise HTTPException(status_code=503, detail=pkg.VISION_UNAVAILABLE_MESSAGE)
    except Exception as exc:
        pkg.logger.exception("Échec du parsing de CV pour %s", current_user.id)
        raise llm_http_exception(exc) or HTTPException(
            status_code=502, detail="Le CV n'a pas pu être analysé"
        )
    finally:
        background_tasks.add_task(safe_remove, file_path)


@router.post("/profile/candidate/sources/github")
async def import_github_source(
    payload_in: dict = Body(...),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    pkg = _pkg()
    try:
        payload = await pkg.collect_github(payload_in.get("url", ""))
        return await pkg._store_source(db, str(current_user.id), "github", payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception:
        pkg.logger.exception("Échec de l'import GitHub pour %s", current_user.id)
        raise HTTPException(status_code=502, detail="L'import GitHub a échoué")


@router.post("/profile/candidate/sources/website")
async def import_website_source(
    payload_in: dict = Body(...),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    pkg = _pkg()
    try:
        url = await pkg.validate_public_url_async(payload_in.get("url", ""))
        payload = await pkg.collect_website(url)
        return await pkg._store_source(db, str(current_user.id), "website", payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        pkg.logger.exception("Échec de l'import du site pour %s", current_user.id)
        raise llm_http_exception(exc) or HTTPException(
            status_code=502, detail="L'import du site a échoué"
        )


@router.put("/profile/candidate")
async def update_candidate_profile(
    profile_data: dict = Body(...),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    pkg = _pkg()
    for key in ("_id", "id", "user_id", "sources", "conflicts", "updated_at"):
        profile_data.pop(key, None)
    try:
        existing = await db["candidate_profile"].find_one({"user_id": ObjectId(current_user.id)}) or {}
        manual = dict(existing.get("sources", {}).get("manual") or {})
        manual.update(profile_data)
        return await pkg._store_source(db, str(current_user.id), "manual", manual)
    except HTTPException:
        raise
    except Exception:
        pkg.logger.exception("Échec de la mise à jour manuelle du profil pour %s", current_user.id)
        raise HTTPException(status_code=502, detail="La mise à jour du profil a échoué")


async def safe_rematch_user(user_id: str, db) -> None:
    """Coalesce concurrent background rematches for a single user."""
    pkg = _pkg()
    if user_id in pkg._rematch_running:
        pkg._rematch_rerun.add(user_id)
        return
    pkg._rematch_running.add(user_id)
    try:
        while True:
            pkg._rematch_rerun.discard(user_id)
            try:
                await pkg.rematch_user(user_id, db)
            except Exception:
                pkg.logger.exception("Échec du rematch en tâche de fond pour %s", user_id)
            if user_id not in pkg._rematch_rerun:
                break
    finally:
        pkg._rematch_running.discard(user_id)
        pkg._rematch_rerun.discard(user_id)


@router.put("/profile/candidate/preferences")
async def update_candidate_preferences(
    background_tasks: BackgroundTasks,
    preferences_data: dict = Body(...),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Targeted update of candidate search preferences with debounced offer rematch."""
    pkg = _pkg()
    try:
        validated_pref = CandidatePreferences.model_validate(preferences_data)
        existing = await db["candidate_profile"].find_one({"user_id": ObjectId(current_user.id)}) or {}
        sources = dict(existing.get("sources") or {})
        manual = dict(sources.get("manual") or {})
        old_preferences = dict(manual.get("preferences") or {})
        manual["preferences"] = validated_pref.model_dump()
        result = await pkg._store_source(db, str(current_user.id), "manual", manual)

        if old_preferences:
            try:
                old_preferences = CandidatePreferences.model_validate(old_preferences).model_dump()
            except Exception:
                pass

        matching_fields_changed = any(
            old_preferences.get(field) != manual["preferences"].get(field)
            for field in (
                "target_roles", "locations", "remote_policy", "excluded_keywords",
                "contract_types", "seniority_levels", "preferred_industries", "preferred_company_sizes",
            )
        )
        if matching_fields_changed:
            background_tasks.add_task(pkg._safe_rematch_user, str(current_user.id), db)
        return result
    except HTTPException:
        raise
    except Exception:
        pkg.logger.exception("Échec de la mise à jour des préférences pour %s", current_user.id)
        raise HTTPException(status_code=502, detail="La mise à jour des préférences a échoué")


@router.get("/profile/api-status")
async def check_api_accounts_status(current_user: UserModel = Depends(get_current_user)):
    """Return configured LLM provider key statuses."""
    job_trackers_path = (
        Path(__file__).resolve().parent.parent.parent.parent / "job_trackers" / "src" / "job_trackers"
    )
    if str(job_trackers_path) not in sys.path:
        sys.path.insert(0, str(job_trackers_path))
    from letter_llm import get_api_status

    return get_api_status()
