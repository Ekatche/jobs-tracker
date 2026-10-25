import asyncio
import hashlib
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body, UploadFile, File, Response
from pydantic import BaseModel, Field, ValidationError

from app.database import get_database
from app.auth import get_current_user
from app.llm.provider_errors import llm_http_exception
from app.models import ApiUsageAction, CandidateProfile, UserModel
from app.utils import serialize_mongodb_doc
from app.routers.applications import _generate_cover_letter_bg
from app.services.cv_parser import extract_text_from_pdf, parse_cv_with_llm
from app.services.cv_pdf_renderer import generate_cv_pdf
from app.services.letter_pdf import render_letter_html, build_candidate_info, slugify
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
    
def _safe_remove(path: str):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        logger.warning(f"Impossible de supprimer le fichier temporaire {path}: {e}")

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


@cover_letters_router.get("/applications/{application_id}/cover-letter/pdf")
async def get_cover_letter_pdf(
    application_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Génère et télécharge la lettre de motivation mise en page en PDF vectoriel A4."""
    if not ObjectId.is_valid(application_id):
        raise HTTPException(status_code=400, detail="ID de candidature invalide")

    app_doc = await db["applications"].find_one({"_id": ObjectId(application_id)})
    if not app_doc:
        raise HTTPException(status_code=404, detail="Candidature non trouvée")
    if str(app_doc.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès non autorisé à cette candidature")

    letter = await db["cover_letters"].find_one({"application_id": ObjectId(application_id)})
    if not letter or letter.get("status") != "ready":
        raise HTTPException(status_code=404, detail="Lettre de motivation non disponible ou non prête")

    # Résolution de la version courante
    versions = letter.get("versions") or []
    current_v = letter.get("current_version", 1)
    version_doc = next((v for v in versions if v.get("n") == current_v), None)
    if not version_doc and versions:
        version_doc = versions[-1]
    if not version_doc or not version_doc.get("body"):
        raise HTTPException(status_code=404, detail="Contenu de la lettre introuvable")

    # Résolution des coordonnées candidat
    profile_query = [{"user_id": str(current_user.id)}]
    if ObjectId.is_valid(str(current_user.id)):
        profile_query.append({"user_id": ObjectId(current_user.id)})
    profile_doc = await db["candidate_profile"].find_one({"$or": profile_query}) or {}

    candidate = build_candidate_info(profile_doc, current_user)

    html_content = render_letter_html(
        body=version_doc["body"],
        candidate=candidate,
        company=app_doc.get("company", "Entreprise"),
        position=app_doc.get("position", ""),
        location=app_doc.get("location"),
    )

    try:
        pdf_bytes = await generate_cv_pdf(html_content)
    except Exception as e:
        logger.error(f"Erreur rendu PDF lettre pour application {application_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Échec du rendu PDF de la lettre de motivation.")

    name_slug = slugify(candidate.get("full_name") or "candidat")
    company_slug = slugify(app_doc.get("company") or "entreprise")
    raw_pos = (app_doc.get("position") or "").strip()
    if raw_pos:
        position_slug = slugify(raw_pos)
        filename = f"Lettre_{name_slug}_{position_slug}_{company_slug}.pdf"
    else:
        filename = f"Lettre_{name_slug}_{company_slug}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "application/pdf"
        }
    )


class RewritePassageRequest(BaseModel):
    letter: str = Field(..., min_length=1, max_length=8000)
    passage: str = Field(..., min_length=1, max_length=2000)
    instruction: str = Field(default="", max_length=500)


@cover_letters_router.post("/applications/{application_id}/cover-letter/rewrite")
async def rewrite_cover_letter_passage(
    application_id: str,
    payload: RewritePassageRequest,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Réécrit un passage spécifique d'une lettre de motivation avec consigne utilisateur."""
    if not ObjectId.is_valid(application_id):
        raise HTTPException(status_code=400, detail="ID de candidature invalide")

    app_doc = await db["applications"].find_one({"_id": ObjectId(application_id)})
    if not app_doc:
        raise HTTPException(status_code=404, detail="Candidature non trouvée")
    if str(app_doc.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès non autorisé à cette candidature")

    if not payload.passage.strip() or payload.passage not in payload.letter:
        raise HTTPException(
            status_code=422,
            detail="Le passage sélectionné est vide ou absent de la lettre",
        )

    await require_user_quota(db, current_user.id, ApiUsageAction.LETTER_REWRITE)

    job_trackers_path = Path(__file__).resolve().parent.parent.parent / "job_trackers" / "src" / "job_trackers"
    if str(job_trackers_path) not in sys.path:
        sys.path.insert(0, str(job_trackers_path))
    from cover_letter_crew import rewrite_letter_passage_async, RewriteFailedError

    try:
        result = await rewrite_letter_passage_async(
            letter=payload.letter,
            passage=payload.passage,
            instruction=payload.instruction,
        )
    except RewriteFailedError:
        raise HTTPException(status_code=502, detail="La réécriture n'a pas abouti, réessayez.")
    except HTTPException:
        raise
    except Exception as e:
        mapped_err = llm_http_exception(e)
        if mapped_err:
            raise mapped_err
        logger.exception("Échec inattendu de la réécriture de passage pour %s", application_id)
        raise HTTPException(status_code=502, detail="La réécriture n'a pas abouti, réessayez.")

    await record_api_usage(
        db,
        current_user.id,
        ApiUsageAction.LETTER_REWRITE,
        model=result.get("model"),
        input_tokens=result.get("input_tokens", 0),
        output_tokens=result.get("output_tokens", 0),
        metadata={"application_id": application_id},
    )

    return {
        "rewritten": result["text"],
        "warnings": result["warnings"],
    }



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


# Sigles d'intitulés de poste que str.title() abîme (« Drh », « Daf ») :
# role_aliases stocke ses variantes en minuscules, la casse d'origine est perdue.
TITLE_ACRONYMS = {
    "rh", "drh", "rrh", "daf", "dsi", "dg", "rssi", "dpo", "pmo", "rse", "qse", "hse", "qhse",
    "adv", "kam", "moa", "moe", "amoa", "esn", "btp", "pme", "eti",
    "ceo", "cfo", "cto", "coo", "cmo", "cio", "cpo", "vp", "hr",
    "it", "si", "ia", "ai", "ml", "nlp", "llm", "bi", "crm", "erp", "sap", "sql", "api",
    "aws", "gcp", "qa", "ux", "ui", "seo", "sea", "b2b", "b2c",
}


def _restore_title_acronyms(title: str) -> str:
    """Remet en majuscules les sigles d'un intitulé (« Fp&A » -> « FP&A »).

    Un mot contenant « & » (FP&A, R&D, M&A) ou présent dans TITLE_ACRONYMS
    passe en majuscules ; les autres mots gardent leur casse.
    """
    def _fix(match: re.Match) -> str:
        word = match.group(0)
        if "&" in word or word.lower() in TITLE_ACRONYMS:
            return word.upper()
        return word

    return re.sub(r"\w+(?:&\w+)*", _fix, title)


async def _canonicalize_roles(raw_roles: list[str], db) -> list[str]:
    """Canonicalise `raw_roles` puis élargit avec les métiers liés.

    Les rôles liés sont les autres intitulés (issus d'autres CV) que
    role_aliases a déjà rattachés au même rôle canonique, pour élargir la
    recherche au-delà des seuls intitulés présents sur ce profil.
    """
    seen: set[str] = set()
    suggestions: list[str] = []
    canonicals: list[str] = []
    fallback_titles: list[str] = []
    for raw in raw_roles:
        cleaned = clean_job_title_syntax(raw)
        if not cleaned or cleaned == "Non spécifié":
            cleaned = raw
        fallback_key = cleaned.lower()
        if cleaned and fallback_key not in {t.lower() for t in fallback_titles}:
            fallback_titles.append(cleaned)
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

    # Taxonomie trop pauvre pour le domaine (ex: aucun rôle data/IA connu) :
    # mieux vaut montrer les intitulés bruts nettoyés que rien du tout.
    if not suggestions:
        return fallback_titles[:MAX_SUGGESTED_ROLES]

    if canonicals and len(suggestions) < MAX_SUGGESTED_ROLES:
        aliases = await db["role_aliases"].find(
            {"canonical": {"$in": canonicals}}
        ).to_list(length=len(canonicals))
        for alias in aliases:
            for variant in alias.get("variants") or []:
                related = _restore_title_acronyms(variant.strip().title())
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
        # Les caches calculés avant _restore_title_acronyms contiennent encore
        # « Fp&A » : on les répare ici plutôt que de les invalider (un appel LLM
        # et du quota par profil pour une correction typographique).
        return {
            "roles": [
                _restore_title_acronyms(role)
                for role in cache["suggestions"][:MAX_SUGGESTED_ROLES]
            ]
        }

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
    background_tasks: BackgroundTasks,
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
    except Exception as exc:
        logger.exception("Échec du parsing de CV pour %s", current_user.id)
        raise llm_http_exception(exc) or HTTPException(status_code=502, detail="Le CV n'a pas pu être analysé")
    finally:
        # Donnée personnelle : le PDF ne survit pas à la requête.
        # Suppression asynchrone en tâche de fond pour économiser les I/O de la requête.
        background_tasks.add_task(_safe_remove, file_path)


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
    except Exception as exc:
        logger.exception("Échec de l'import du site pour %s", current_user.id)
        raise llm_http_exception(exc) or HTTPException(status_code=502, detail="L'import du site a échoué")


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
            for field in (
                "target_roles",
                "locations",
                "remote_policy",
                "excluded_keywords",
                "contract_types",
                "seniority_levels",
                "preferred_industries",
                "preferred_company_sizes",
            )
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
