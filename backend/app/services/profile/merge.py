"""Fusion des sources du profil candidat (facade rétrocompatible).

Fonction pure : aucun I/O, aucun LLM, aucune base.
"""

from typing import Any, Dict, List, Tuple

from .merge_education import (
    _degrees_match,
    _education_items_match,
    _education_key,
    _extract_years,
    _merge_certifications,
    _merge_education,
    _schools_match,
    _years_compatible,
)
from .merge_experiences import (
    _end_of,
    _merge_experiences,
    _merge_one_experience,
    _month_index,
    _same_position_dates,
)
from .merge_helpers import (
    _MANUAL_CLEARABLE_CONTACT_KEYS,
    _SCALAR_FIELDS,
    SOURCE_PRIORITY,
    _dedup_preserving_order,
    _derive_headline,
    _excluded_keys_from,
    _first_non_empty,
    _keys_loosely_match,
    _normalize_key,
    _normalize_tokens,
    _ordered_sources,
)

IGNORED_PROJECT_NAMES = {"cv", "pytests", "test", "tests", "demo", "sandbox"}


def _is_prettier_name(new_name: str, current_name: str) -> bool:
    """Favorise un libellé formaté sur un slug technique tout en minuscules."""
    if " " in new_name and " " not in current_name:
        return True
    return any(c.isupper() for c in new_name) and not any(c.isupper() for c in current_name)


def _merge_projects(
    sources: Dict[str, Dict[str, Any]], order: List[str]
) -> List[Dict[str, Any]]:
    excluded_keys = _excluded_keys_from(sources, order, "excluded_projects")
    grouped: Dict[str, Dict[str, Any]] = {}
    for source in order:
        for project in sources[source].get("projects") or []:
            name = (project.get("name") or "").strip()
            if not name:
                continue
            key = _normalize_key(name)
            if not key or key in excluded_keys or key in IGNORED_PROJECT_NAMES:
                continue

            desc = (project.get("description") or "").strip()
            stack = project.get("stack") or []
            if not desc and not stack and not project.get("highlights"):
                continue

            matched_key = (
                key
                if key in grouped
                else next((ex for ex in grouped if _keys_loosely_match(key, ex)), None)
            )
            if matched_key is None:
                grouped[key] = {**project, "name": name, "sources": [source]}
                continue

            current = grouped[matched_key]
            if source not in current.get("sources", []):
                current.setdefault("sources", []).append(source)
            if _is_prettier_name(name, current.get("name", "")):
                current["name"] = name
            if len(desc) > len(current.get("description") or ""):
                current["description"] = project["description"]
            current["url"] = current.get("url") or project.get("url")
            current["repo"] = current.get("repo") or project.get("repo")
            current["context"] = current.get("context") or project.get("context")
            current["stack"] = _dedup_preserving_order((current.get("stack") or []) + stack)
            current["highlights"] = _dedup_preserving_order(
                (current.get("highlights") or []) + (project.get("highlights") or [])
            )
    return list(grouped.values())


def _merge_skills(
    sources: Dict[str, Dict[str, Any]], order: List[str]
) -> Dict[str, List[str]]:
    """Fusionne les compétences par catégorie (`manual` fait autorité seul s'il est rempli)."""
    manual_skills = sources.get("manual", {}).get("skills") or {}
    if manual_skills:
        return {
            cat: _dedup_preserving_order([str(v) for v in (values or [])])
            for cat, values in manual_skills.items()
            if any(str(v).strip() for v in (values or []))
        }
    merged: Dict[str, List[str]] = {}
    for source in order:
        for category, skills in (sources[source].get("skills") or {}).items():
            merged.setdefault(category, []).extend(skills or [])
    return {
        cat: _dedup_preserving_order(values)
        for cat, values in merged.items()
        if any(str(v).strip() for v in values)
    }


def _extract_languages(source_payload: Dict[str, Any]) -> List[str]:
    raw = source_payload.get("languages") or []
    if not raw and "personal_info" in source_payload:
        raw = source_payload["personal_info"].get("languages") or []
    normalized: List[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            normalized.append(item.strip())
        elif isinstance(item, dict):
            lang = item.get("language") or item.get("name") or ""
            prof = item.get("proficiency") or item.get("level") or ""
            if lang:
                normalized.append(f"{lang} ({prof})" if prof else lang)
    return normalized


def build_profile_from_sources(
    sources: Dict[str, Dict[str, Any]],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Construit le profil dérivé et la liste des conflits non résolus."""
    order = _ordered_sources(sources)
    conflicts: List[Dict[str, Any]] = []
    contributions = [(source, sources[source]) for source in order]

    contact: Dict[str, Any] = {}
    for source in reversed(order):
        src_payload = sources[source]
        src_contact = src_payload.get("contact") or src_payload.get("personal_info") or {}
        contact.update({k: v for k, v in src_contact.items() if v and k != "languages"})
        if source == "manual":
            for key in _MANUAL_CLEARABLE_CONTACT_KEYS:
                if key in src_contact and not str(src_contact[key] or "").strip():
                    contact.pop(key, None)

    languages: List[str] = []
    interests: List[str] = []
    for source in order:
        languages.extend(_extract_languages(sources[source]))
        raw_interests = (
            sources[source].get("interests")
            or sources[source].get("personal_info", {}).get("interests")
            or []
        )
        if isinstance(raw_interests, list):
            interests.extend([str(i).strip() for i in raw_interests if str(i).strip()])

    _, headline = _first_non_empty("headline", contributions)
    _, summary = _first_non_empty("summary", contributions)
    _, preferences = _first_non_empty("preferences", contributions)
    _, writing_style = _first_non_empty("writing_style", contributions)
    _, writing_samples = _first_non_empty("writing_samples", contributions)

    experiences = _merge_experiences(sources, order, conflicts)
    skills = _merge_skills(sources, order)
    if not headline:
        headline = _derive_headline(experiences, summary or "", skills)

    profile = {
        "headline": headline or "",
        "summary": summary or "",
        "contact": contact,
        "preferences": preferences or {},
        "writing_style": writing_style or "",
        "writing_samples": writing_samples or "",
        "experiences": experiences,
        "projects": _merge_projects(sources, order),
        "education": _merge_education(sources, order, conflicts),
        "certifications": _merge_certifications(sources, order),
        "languages": _dedup_preserving_order(languages),
        "interests": _dedup_preserving_order(interests),
        "skills": skills,
        "excluded_projects": list(sources.get("manual", {}).get("excluded_projects", []) or []),
        "excluded_education": list(sources.get("manual", {}).get("excluded_education", []) or []),
        "excluded_certifications": list(
            sources.get("manual", {}).get("excluded_certifications", []) or []
        ),
    }
    return profile, conflicts


__all__ = [
    "IGNORED_PROJECT_NAMES",
    "SOURCE_PRIORITY",
    "_MANUAL_CLEARABLE_CONTACT_KEYS",
    "_SCALAR_FIELDS",
    "_dedup_preserving_order",
    "_degrees_match",
    "_derive_headline",
    "_education_items_match",
    "_education_key",
    "_end_of",
    "_excluded_keys_from",
    "_extract_languages",
    "_extract_years",
    "_first_non_empty",
    "_is_prettier_name",
    "_keys_loosely_match",
    "_merge_certifications",
    "_merge_education",
    "_merge_experiences",
    "_merge_one_experience",
    "_merge_projects",
    "_merge_skills",
    "_month_index",
    "_normalize_key",
    "_normalize_tokens",
    "_ordered_sources",
    "_same_position_dates",
    "_schools_match",
    "_years_compatible",
    "build_profile_from_sources",
]
