import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body, UploadFile, File
from pydantic import ValidationError

from app.database import get_database
from app.auth import get_current_user
from app.models import ApiUsageAction, CandidateProfile, UserModel
from app.utils import serialize_mongodb_doc
from app.routers.applications import _generate_cover_letter_bg
from app.services.cv_parser import extract_text_from_pdf, parse_cv_with_llm
from app.services.profile.collectors.github import collect_github
from app.services.profile.collectors.website import collect_website
from app.services.normalization import clean_job_title_syntax
from app.services.profile.merge import build_profile_from_sources
from app.services.profile.urls import validate_public_url_async
from app.services.role_normalizer import match_taxonomy_role, suggest_role_titles_from_profile
from app.services.usage_tracker import record_api_usage, require_user_quota
from app.services.offer_profile_matcher import rematch_user

MAX_SUGGESTED_ROLES = 8

logger = logging.getLogger(__name__)

cover_letters_router = APIRouter(tags=["cover_letters"])

UPLOAD_DIR = str(Path(__file__).resolve().parent.parent / "uploads")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
PDF_MAGIC = b"%PDF"

@cover_letters_router.get("/applications/{application_id}/cover-letter")
async def get_cover_letter(
    application_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    app_doc = await db["applications"].find_one({"_id": ObjectId(application_id)})
    if not app_doc:
        raise HTTPException(status_code=404, detail="Candidature non trouvée")
    if str(app_doc.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès non autorisé à cette candidature")

    letter = await db["cover_letters"].find_one({"application_id": ObjectId(application_id)})
    if not letter:
        return {"status": "none"}
    return serialize_mongodb_doc(letter)

@cover_letters_router.post("/applications/{application_id}/cover-letter/regenerate")
async def regenerate_cover_letter(
    application_id: str,
    background_tasks: BackgroundTasks,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    app_doc = await db["applications"].find_one({"_id": ObjectId(application_id)})
    if not app_doc:
        raise HTTPException(status_code=404, detail="Candidature non trouvée")
    if str(app_doc.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès non autorisé à cette candidature")

    # Remise en attente : l'historique et les versions éditées sont conservés.
    await db["cover_letters"].update_one(
        {"application_id": ObjectId(application_id)},
        {"$set": {"status": "pending", "error": None, "updated_at": datetime.now(timezone.utc)}},
    )
    background_tasks.add_task(
        _generate_cover_letter_bg,
        ObjectId(application_id),
        ObjectId(current_user.id),
        db
    )
    return {"status": "scheduled"}

@cover_letters_router.patch("/applications/{application_id}/cover-letter")
async def edit_cover_letter(
    application_id: str,
    body_data: dict = Body(...),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    letter = await db["cover_letters"].find_one({"application_id": ObjectId(application_id)})
    if not letter:
        raise HTTPException(status_code=404, detail="Lettre non trouvée")
    if str(letter.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès non autorisé")

    new_version_num = len(letter.get("versions", [])) + 1
    new_version = {
        "n": new_version_num,
        "body": body_data.get("body", ""),
        "origin": "edited",
        "models": {},
        "created_at": datetime.now(timezone.utc)
    }
    await db["cover_letters"].update_one(
        {"_id": letter["_id"]},
        {
            "$set": {"current_version": new_version_num, "updated_at": datetime.now(timezone.utc)},
            "$push": {"versions": new_version}
        }
    )
    updated = await db["cover_letters"].find_one({"_id": letter["_id"]})
    return serialize_mongodb_doc(updated)

@cover_letters_router.get("/profile/candidate")
async def get_candidate_profile(
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    prof = await db["candidate_profile"].find_one({"user_id": ObjectId(current_user.id)})
    if not prof:
        raise HTTPException(status_code=404, detail="Profil non initialisé")
    return serialize_mongodb_doc(prof)


def _suggested_roles_profile_hash(prof: dict) -> str:
    """Empreinte du sous-ensemble de profil qui influence les suggestions.

    Sert à invalider le cache de suggestions uniquement quand ces champs
    changent, plutôt qu'à chaque chargement de page.
    """
    payload = {
        "headline": prof.get("headline") or "",
        "summary": prof.get("summary") or "",
        "skills": prof.get("skills") or {},
        "experience_roles": [
            (exp.get("role") or "").strip() for exp in (prof.get("experiences") or [])
        ],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


async def _canonicalize_roles(raw_roles: list[str], db) -> list[str]:
    """Canonicalise `raw_roles` puis élargit avec les métiers liés.

    Les rôles liés sont les autres intitulés (issus d'autres CV) que
    role_aliases a déjà rattachés au même rôle canonique, pour élargir la
    recherche au-delà des seuls intitulés présents sur ce profil.
    """
    seen: set[str] = set()
    suggestions: list[str] = []
    canonicals: list[str] = []
    for raw in raw_roles:
        cleaned = clean_job_title_syntax(raw)
        if not cleaned or cleaned == "Non spécifié":
            cleaned = raw
        canonical = await match_taxonomy_role(cleaned, db=db)
        if not canonical:
            continue
        key = canonical.lower()
        if key not in seen:
            seen.add(key)
            suggestions.append(canonical)
            canonicals.append(canonical)
        if len(suggestions) >= MAX_SUGGESTED_ROLES:
            break

    if canonicals and len(suggestions) < MAX_SUGGESTED_ROLES:
        aliases = await db["role_aliases"].find(
            {"canonical": {"$in": canonicals}}
        ).to_list(length=len(canonicals))
        for alias in aliases:
            for variant in alias.get("variants") or []:
                related = variant.strip().title()
                key = related.lower()
                if related and key not in seen:
                    seen.add(key)
                    suggestions.append(related)
                if len(suggestions) >= MAX_SUGGESTED_ROLES:
                    break
            if len(suggestions) >= MAX_SUGGESTED_ROLES:
                break

    return suggestions


@cover_letters_router.get("/profile/candidate/suggested-roles")
async def get_suggested_roles(
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Suggère des intitulés de poste réels pour alimenter la recherche d'offres.

    Combine deux sources, toutes deux validées en lecture seule contre la
    taxonomie ROME/ESCO (role_aliases) via match_taxonomy_role: le headline et
    les rôles d'expérience bruts du profil, et des intitulés de métier proposés
    par un LLM à partir du profil complet (headline, résumé, expériences,
    compétences) pour capter des métiers cohérents mais non formulés tels
    quels dans le CV. Un titre sans correspondance suffisamment proche dans la
    taxonomie est simplement omis, jamais affiché brut ni enregistré comme
    nouveau canonical.

    Le résultat du LLM ET la canonicalisation contre la taxonomie (elle-même
    coûteuse : un appel d'embedding par intitulé non déjà connu) sont tous
    deux mis en cache sur le profil, recalculés seulement quand
    headline/summary/skills/experiences changent, pour éviter de refaire ces
    appels réseau à chaque clic ou chargement de page.
    """
    prof = await db["candidate_profile"].find_one({"user_id": ObjectId(current_user.id)})
    if not prof:
        return {"roles": []}

    profile_hash = _suggested_roles_profile_hash(prof)
    cache = prof.get("suggested_roles_cache") or {}
    cache_hit = cache.get("hash") == profile_hash

    if cache_hit and cache.get("suggestions") is not None:
        return {"roles": cache["suggestions"][:MAX_SUGGESTED_ROLES]}

    raw_roles: list[str] = []
    headline = (prof.get("headline") or "").strip()
    if headline:
        raw_roles.append(headline)
    for exp in prof.get("experiences") or []:
        role = (exp.get("role") or "").strip()
        if role:
            raw_roles.append(role)

    usage = None
    if cache_hit:
        llm_roles = cache.get("raw_roles") or []
    else:
        await require_user_quota(db, current_user.id, ApiUsageAction.ROLE_SUGGESTION)
        result = await suggest_role_titles_from_profile(prof)
        llm_roles = result.get("roles") or []
        usage = result.get("_usage")

        if usage:
            await record_api_usage(
                db,
                current_user.id,
                ApiUsageAction.ROLE_SUGGESTION,
                models_used=[usage["model"]],
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
            )

    suggestions = (await _canonicalize_roles(raw_roles + llm_roles, db))[:MAX_SUGGESTED_ROLES]

    await db["candidate_profile"].update_one(
        {"_id": prof["_id"]},
        {
            "$set": {
                "suggested_roles_cache": {
                    "hash": profile_hash,
                    "raw_roles": llm_roles,
                    "suggestions": suggestions,
                    "updated_at": datetime.now(timezone.utc),
                }
            }
        },
    )

    return {"roles": suggestions}


async def _read_upload(file: UploadFile, magic: bytes) -> bytes:
    """Lit un upload en plafonnant la taille et en vérifiant la signature."""
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(1024 * 1024):
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Fichier trop volumineux (10 Mo maximum)")
        chunks.append(chunk)
    content = b"".join(chunks)
    if not content.startswith(magic):
        raise HTTPException(status_code=400, detail="Le contenu du fichier n'est pas un PDF valide")
    return content


async def _store_source(db, user_id: str, name: str, payload: dict) -> dict:
    """Range une source, recalcule le profil dérivé, retourne le profil à jour."""
    existing = await db["candidate_profile"].find_one({"user_id": ObjectId(user_id)}) or {}
    sources = dict(existing.get("sources") or {})
    sources[name] = payload

    derived, conflicts = build_profile_from_sources(sources)
    document = {
        **derived,
        "sources": sources,
        "conflicts": conflicts,
        "user_id": ObjectId(user_id),
        "updated_at": datetime.now(timezone.utc),
    }
    # La validation refuse d'écrire une sortie de LLM malformée en base.
    try:
        CandidateProfile.model_validate({**document, "user_id": str(user_id)})
    except ValidationError:
        logger.exception(
            "Le profil dérivé après import de la source %s est invalide pour %s", name, user_id
        )
        raise HTTPException(status_code=502, detail="Le profil obtenu n'a pas pu être validé")

    await db["candidate_profile"].update_one(
        {"user_id": ObjectId(user_id)}, {"$set": document}, upsert=True
    )
    stored = await db["candidate_profile"].find_one({"user_id": ObjectId(user_id)})
    return serialize_mongodb_doc(stored)


@cover_letters_router.post("/profile/candidate/sources/cv")
async def import_cv_source(
    file: UploadFile = File(...),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    await require_user_quota(db, current_user.id, ApiUsageAction.CV_PARSING)

    content = await _read_upload(file, PDF_MAGIC)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, f"cv_{current_user.id}_{uuid4().hex}.pdf")

    try:
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        text = await asyncio.to_thread(extract_text_from_pdf, file_path)
        try:
            payload = await parse_cv_with_llm(text, pdf_path=file_path)
        except TypeError:
            payload = await parse_cv_with_llm(text)
        usage = payload.pop("_usage", None)
        if usage:
            await record_api_usage(
                db=db,
                user_id=current_user.id,
                action=ApiUsageAction.CV_PARSING,
                models_used=[usage["model"]],
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
            )
        return await _store_source(db, str(current_user.id), "cv", payload)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Échec du parsing de CV pour %s", current_user.id)
        raise HTTPException(status_code=502, detail="Le CV n'a pas pu être analysé")
    finally:
        # Donnée personnelle : le PDF ne survit pas à la requête.
        if os.path.exists(file_path):
            os.remove(file_path)


@cover_letters_router.post("/profile/candidate/sources/github")
async def import_github_source(
    payload_in: dict = Body(...),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    try:
        payload = await collect_github(payload_in.get("url", ""))
        return await _store_source(db, str(current_user.id), "github", payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception:
        logger.exception("Échec de l'import GitHub pour %s", current_user.id)
        raise HTTPException(status_code=502, detail="L'import GitHub a échoué")


@cover_letters_router.post("/profile/candidate/sources/website")
async def import_website_source(
    payload_in: dict = Body(...),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    try:
        url = await validate_public_url_async(payload_in.get("url", ""))
        payload = await collect_website(url)
        return await _store_source(db, str(current_user.id), "website", payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception:
        logger.exception("Échec de l'import du site pour %s", current_user.id)
        raise HTTPException(status_code=502, detail="L'import du site a échoué")


@cover_letters_router.put("/profile/candidate")
async def update_candidate_profile(
    profile_data: dict = Body(...),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    for key in ("_id", "id", "user_id", "sources", "conflicts", "updated_at"):
        profile_data.pop(key, None)
    try:
        existing = await db["candidate_profile"].find_one({"user_id": ObjectId(current_user.id)}) or {}
        manual = dict(existing.get("sources", {}).get("manual") or {})
        manual.update(profile_data)
        return await _store_source(db, str(current_user.id), "manual", manual)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Échec de la mise à jour manuelle du profil pour %s", current_user.id)
        raise HTTPException(status_code=502, detail="La mise à jour du profil a échoué")


async def _safe_rematch_user(user_id: str, db) -> None:
    """Enveloppe rematch_user pour tâche de fond : une erreur de matching ne doit
    jamais faire échouer ou logguer de traceback bruyant après que la réponse
    HTTP a déjà été envoyée."""
    try:
        await rematch_user(user_id, db)
    except Exception:
        logger.exception("Échec du rematch en tâche de fond pour %s", user_id)


@cover_letters_router.put("/profile/candidate/preferences")
async def update_candidate_preferences(
    background_tasks: BackgroundTasks,
    preferences_data: dict = Body(...),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Mise à jour ciblée des critères de recherche et préférences du candidat."""
    try:
        from app.models import CandidatePreferences
        validated_pref = CandidatePreferences.model_validate(preferences_data)
        existing = await db["candidate_profile"].find_one({"user_id": ObjectId(current_user.id)}) or {}
        sources = dict(existing.get("sources") or {})
        manual = dict(sources.get("manual") or {})
        old_preferences = dict(manual.get("preferences") or {})
        manual["preferences"] = validated_pref.model_dump()
        result = await _store_source(db, str(current_user.id), "manual", manual)

        if old_preferences:
            try:
                old_preferences = CandidatePreferences.model_validate(old_preferences).model_dump()
            except Exception:
                pass

        matching_fields_changed = any(
            old_preferences.get(field) != manual["preferences"].get(field)
            for field in ("target_roles", "locations", "remote_policy")
        )
        if matching_fields_changed:
            background_tasks.add_task(_safe_rematch_user, str(current_user.id), db)

        return result
    except HTTPException:
        raise
    except Exception:
        logger.exception("Échec de la mise à jour des préférences pour %s", current_user.id)
        raise HTTPException(status_code=502, detail="La mise à jour des préférences a échoué")


@cover_letters_router.get("/profile/api-status")
async def check_api_accounts_status(
    current_user: UserModel = Depends(get_current_user),
):
    """
    Retourne le statut de configuration des clés API (OpenAI, Gemini, Mistral)
    et les informations d'accès aux soldes/crédits sur les consoles fournisseurs.
    """
    import sys
    from pathlib import Path as _Path
    job_trackers_path = _Path(__file__).parent.parent.parent / "job_trackers" / "src" / "job_trackers"
    if str(job_trackers_path) not in sys.path:
        sys.path.insert(0, str(job_trackers_path))
    from letter_llm import get_api_status
    return get_api_status()
