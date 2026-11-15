import hashlib
import json
import re
import sys
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.database import get_database
from app.models import ApiUsageAction, UserModel

MAX_SUGGESTED_ROLES = 8

TITLE_ACRONYMS = {
    "rh", "drh", "rrh", "daf", "dsi", "dg", "rssi", "dpo", "pmo", "rse", "qse", "hse", "qhse",
    "adv", "kam", "moa", "moe", "amoa", "esn", "btp", "pme", "eti",
    "ceo", "cfo", "cto", "coo", "cmo", "cio", "cpo", "vp", "hr",
    "it", "si", "ia", "ai", "ml", "nlp", "llm", "bi", "crm", "erp", "sap", "sql", "api",
    "aws", "gcp", "qa", "ux", "ui", "seo", "sea", "b2b", "b2c",
}

router = APIRouter()


def _pkg():
    return sys.modules[__package__]


def suggested_roles_profile_hash(prof: dict) -> str:
    """Hash of the profile subset affecting suggested role caching."""
    payload = {
        "headline": prof.get("headline") or "",
        "summary": prof.get("summary") or "",
        "skills": prof.get("skills") or {},
        "experience_roles": [
            (exp.get("role") or "").strip() for exp in (prof.get("experiences") or [])
        ],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def restore_title_acronyms(title: str) -> str:
    """Restore uppercase acronyms after title casing (`Fp&A` -> `FP&A`)."""

    def _fix(match: re.Match) -> str:
        word = match.group(0)
        return word.upper() if "&" in word or word.lower() in TITLE_ACRONYMS else word

    return re.sub(r"\w+(?:&\w+)*", _fix, title)


async def canonicalize_roles(raw_roles: list[str], db) -> list[str]:
    """Canonicalize raw titles against ROME/ESCO aliases and expand related roles."""
    pkg = _pkg()
    seen: set[str] = set()
    suggestions: list[str] = []
    canonicals: list[str] = []
    fallback_titles: list[str] = []
    for raw in raw_roles:
        cleaned = pkg.clean_job_title_syntax(raw)
        if not cleaned or cleaned == "Non spécifié":
            cleaned = raw
        fallback_key = cleaned.lower()
        if cleaned and fallback_key not in {t.lower() for t in fallback_titles}:
            fallback_titles.append(cleaned)
        canonical = await pkg.match_taxonomy_role(cleaned, db=db)
        if not canonical:
            continue
        key = canonical.lower()
        if key not in seen:
            seen.add(key)
            suggestions.append(canonical)
            canonicals.append(canonical)
        if len(suggestions) >= MAX_SUGGESTED_ROLES:
            break

    if not suggestions:
        return fallback_titles[:MAX_SUGGESTED_ROLES]

    if canonicals and len(suggestions) < MAX_SUGGESTED_ROLES:
        aliases = await db["role_aliases"].find(
            {"canonical": {"$in": canonicals}}
        ).to_list(length=len(canonicals))
        for alias in aliases:
            for variant in alias.get("variants") or []:
                related = restore_title_acronyms(variant.strip().title())
                key = related.lower()
                if related and key not in seen:
                    seen.add(key)
                    suggestions.append(related)
                if len(suggestions) >= MAX_SUGGESTED_ROLES:
                    break
            if len(suggestions) >= MAX_SUGGESTED_ROLES:
                break

    return suggestions


@router.get("/profile/candidate/suggested-roles")
async def get_suggested_roles(
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    """Suggest taxonomy-validated role titles derived from candidate profile + LLM."""
    pkg = _pkg()
    prof = await db["candidate_profile"].find_one({"user_id": ObjectId(current_user.id)})
    if not prof:
        return {"roles": []}

    profile_hash = suggested_roles_profile_hash(prof)
    cache = prof.get("suggested_roles_cache") or {}
    cache_hit = cache.get("hash") == profile_hash

    if cache_hit and cache.get("suggestions") is not None:
        return {
            "roles": [
                restore_title_acronyms(role)
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

    if cache_hit:
        llm_roles = cache.get("raw_roles") or []
    else:
        await pkg.require_user_quota(db, current_user.id, ApiUsageAction.ROLE_SUGGESTION)
        result = await pkg.suggest_role_titles_from_profile(prof)
        llm_roles = result.get("roles") or []
        usage = result.get("_usage")
        if usage:
            await pkg.record_api_usage(
                db,
                current_user.id,
                ApiUsageAction.ROLE_SUGGESTION,
                models_used=[usage["model"]],
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
            )

    suggestions = (await pkg._canonicalize_roles(raw_roles + llm_roles, db))[:MAX_SUGGESTED_ROLES]
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
