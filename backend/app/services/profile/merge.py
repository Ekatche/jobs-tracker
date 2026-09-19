"""Fusion des sources du profil candidat.

Fonction pure : aucun I/O, aucun LLM, aucune base. Un seul endroit décide quelle
source gagne sur quel champ, ce qui rend la règle lisible et testable.
"""

import re
from typing import Any, Dict, List, Tuple

from app.services.profile.periods import company_slug, is_open_ended, normalize_month

SOURCE_PRIORITY: Tuple[str, ...] = ("manual", "cv", "website", "github")

_SCALAR_FIELDS = ("role", "location", "contract", "sector")


def _ordered_sources(sources: Dict[str, Dict[str, Any]]) -> List[str]:
    known = [s for s in SOURCE_PRIORITY if sources.get(s)]
    extra = sorted(s for s in sources if s not in SOURCE_PRIORITY and sources.get(s))
    return known + extra


def _dedup_preserving_order(values: List[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        key = value.strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(value.strip())
    return result


def _normalize_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")



def _derive_headline(
    experiences: List[Dict[str, Any]],
    summary: str,
    skills: Dict[str, List[str]],
) -> str:
    """Dérive un titre professionnel cohérent à partir du résumé ou du rôle le plus récent."""
    if summary:
        first_sentence = summary.split(".")[0].strip()
        match = re.match(
            r"^([A-ZÀ-ÖØ-öø-ÿ][a-zA-ZÀ-ÖØ-öø-ÿ0-9\s&/,\-\+]+?)(?:\s+(?:expérimenté[e]?|senior|confirmé[e]?|avec|spécialisé[e]?|passionné[e]?|dans|ayant|\.|\,)|$)",
            first_sentence,
            re.IGNORECASE,
        )
        if match:
            candidate = match.group(1).strip()
            if 3 <= len(candidate) <= 60 and not candidate.lower().startswith(("je ", "mon ", "le ", "un ")):
                candidate = re.sub(r"\s+et\s+", " & ", candidate, flags=re.IGNORECASE)
                return candidate

    if experiences:
        top_role = (experiences[0].get("role") or "").strip()
        if top_role:
            return top_role

    return ""


def _first_non_empty(
    field: str, contributions: List[Tuple[str, Dict[str, Any]]]
) -> Tuple[str | None, Any]:
    """Retourne (source, valeur) du premier champ renseigné dans l'ordre de priorité.

    Utilisé pour tous les scalaires (rôle, lieu, contrat, secteur) : `manual` gagne
    s'il a renseigné la valeur, sinon `cv`, sinon `website`. Ne retombe PAS sur
    `contributions[0]` lorsque la source de plus forte priorité est muette sur ce champ.
    """
    for source, payload in contributions:
        value = payload.get(field)
        if value:
            return source, value
    return None, None


def _merge_one_experience(
    contributions: List[Tuple[str, Dict[str, Any]]],
    conflicts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    winner_source, winner = contributions[0]

    # Date de début : chercher la première source non nulle dans l'ordre de priorité
    starts = [
        normalize_month(
            payload.get("start") or payload.get("start_date"),
            fallback_year=payload.get("end") or payload.get("end_date"),
        )
        for _, payload in contributions
    ]
    start_date = next((s for s in starts if s), None)

    merged: Dict[str, Any] = {
        "company": winner.get("company", ""),
        "start": start_date,
        "sources": [source for source, _ in contributions],
    }

    for field in _SCALAR_FIELDS:
        kept_source, kept_value = _first_non_empty(field, contributions)
        merged[field] = kept_value
        for source, payload in contributions:
            if source == kept_source:
                continue
            other = payload.get(field)
            if other and kept_value and other != kept_value:
                conflicts.append(
                    {
                        "company": merged["company"],
                        "field": field,
                        "kept": kept_value,
                        "kept_source": kept_source,
                        "discarded": other,
                        "discarded_source": source,
                    }
                )

    # Fin de période : une date réelle bat une période ouverte.
    ends = [
        (source, normalize_month(payload.get("end") or payload.get("end_date")))
        for source, payload in contributions
        if not is_open_ended(payload.get("end") or payload.get("end_date"))
    ]
    merged["end"] = ends[0][1] if ends else None
    distinct_ends = {value for _source, value in ends if value}
    if len(distinct_ends) > 1:
        conflicts.append(
            {
                "company": merged["company"],
                "field": "end",
                "kept": merged["end"],
                "kept_source": ends[0][0],
                "discarded": sorted(distinct_ends - {merged["end"]}),
                "discarded_source": "autres sources",
            }
        )

    # Missions : le bloc le plus fourni, pas l'union — évite le doublon FR/EN.
    blocks = [
        (source, payload.get("missions") or [])
        for source, payload in contributions
    ]
    blocks_sorted = sorted(
        blocks,
        key=lambda item: (-len(item[1]), SOURCE_PRIORITY.index(item[0]) if item[0] in SOURCE_PRIORITY else 99),
    )
    merged["missions"] = _dedup_preserving_order(list(blocks_sorted[0][1]))
    merged["missions_source"] = blocks_sorted[0][0]
    alternates: List[str] = []
    for _source, block in blocks_sorted[1:]:
        alternates.extend(block)
    merged["missions_alt"] = _dedup_preserving_order(alternates)

    stack: List[str] = []
    for _source, payload in contributions:
        stack.extend(payload.get("stack") or [])
    merged["stack"] = _dedup_preserving_order(stack)

    achievements: List[Dict[str, Any]] = []
    for _source, payload in contributions:
        achievements.extend(payload.get("achievements") or [])
    merged["achievements"] = achievements

    return merged


def _merge_experiences(
    sources: Dict[str, Dict[str, Any]],
    order: List[str],
    conflicts: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[str, str | None], List[Tuple[str, Dict[str, Any]]]] = {}
    key_order: List[Tuple[str, str | None]] = []

    for source in order:
        for experience in sources[source].get("experiences") or []:
            c_slug = company_slug(experience.get("company", ""))
            s_date = normalize_month(
                experience.get("start") or experience.get("start_date"),
                fallback_year=experience.get("end") or experience.get("end_date"),
            )

            # Rapprochement avec un groupe existant de la même entreprise
            matched_key = None
            for key in key_order:
                existing_company, existing_start = key
                if existing_company == c_slug:
                    # Ne jamais fusionner deux expériences distinctes provenant de la même source
                    if any(s == source for s, _ in grouped[key]):
                        continue
                    if existing_start == s_date or (existing_start is None and s_date is None):
                        matched_key = key
                        break
                    if existing_start is None or s_date is None:
                        matched_key = key
                        break
                    # Même année (ex: 2022-09 vs 2022-10 pour une seule expérience Nodya par source)
                    if (
                        existing_start
                        and s_date
                        and len(existing_start) >= 4
                        and len(s_date) >= 4
                        and existing_start[:4] == s_date[:4]
                    ):
                        matched_key = key
                        break

            if matched_key is None:
                new_key = (c_slug, s_date)
                if new_key in grouped:
                    new_key = (f"{c_slug}-{len(key_order)}", s_date)
                grouped[new_key] = [(source, experience)]
                key_order.append(new_key)
            else:
                grouped[matched_key].append((source, experience))
                # Si le groupe existant n'avait pas de date de début et que la nouvelle en a une, mettre à jour la clé
                if matched_key[1] is None and s_date is not None:
                    idx = key_order.index(matched_key)
                    updated_key = (c_slug, s_date)
                    key_order[idx] = updated_key
                    grouped[updated_key] = grouped.pop(matched_key)

    merged = [_merge_one_experience(grouped[key], conflicts) for key in key_order]
    # Ordre stable et lisible : du poste le plus récent au plus ancien.
    return sorted(merged, key=lambda e: e["start"] or "", reverse=True)


IGNORED_PROJECT_NAMES = {"cv", "pytests", "test", "tests", "demo", "sandbox"}


def _is_prettier_name(new_name: str, current_name: str) -> bool:
    """Favorise un libellé formaté (avec espaces et majuscules) sur un slug technique tout en minuscules."""
    if " " in new_name and " " not in current_name:
        return True
    if any(c.isupper() for c in new_name) and not any(c.isupper() for c in current_name):
        return True
    return False


def _merge_projects(
    sources: Dict[str, Dict[str, Any]], order: List[str]
) -> List[Dict[str, Any]]:
    excluded_keys = set()
    for source in order:
        for exc in sources[source].get("excluded_projects") or []:
            if isinstance(exc, str):
                excluded_keys.add(_normalize_key(exc))

    grouped: Dict[str, Dict[str, Any]] = {}
    for source in order:
        for project in sources[source].get("projects") or []:
            name = (project.get("name") or "").strip()
            if not name:
                continue
            key = _normalize_key(name)
            if not key or key in excluded_keys:
                continue

            # Filtrage des dépôts triviaux ou utilitaires non pertinents
            if key in IGNORED_PROJECT_NAMES:
                continue

            desc = (project.get("description") or "").strip()
            stack = project.get("stack") or []
            # Filtrage des dépôts vides sans description ni technologies
            if not desc and not stack and not project.get("highlights"):
                continue

            if key not in grouped:
                grouped[key] = dict(project)
                grouped[key]["name"] = name
                grouped[key]["sources"] = [source]
                continue

            current = grouped[key]
            if source not in current.get("sources", []):
                current.setdefault("sources", []).append(source)

            # Privilégie un nom d'affichage plus lisible (ex: "Jobs Tracker" vs "jobs-tracker")
            if _is_prettier_name(name, current.get("name", "")):
                current["name"] = name

            if len(desc) > len(current.get("description") or ""):
                current["description"] = project["description"]

            current["url"] = current.get("url") or project.get("url")
            current["repo"] = current.get("repo") or project.get("repo")
            current["context"] = current.get("context") or project.get("context") or "perso"
            current["stack"] = _dedup_preserving_order(
                (current.get("stack") or []) + stack
            )
            current["highlights"] = _dedup_preserving_order(
                (current.get("highlights") or []) + (project.get("highlights") or [])
            )
    return list(grouped.values())


def _merge_skills(
    sources: Dict[str, Dict[str, Any]], order: List[str]
) -> Dict[str, List[str]]:
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
        if isinstance(item, str):
            clean = item.strip()
            if clean:
                normalized.append(clean)
        elif isinstance(item, dict):
            lang = item.get("language") or item.get("name") or ""
            prof = item.get("proficiency") or item.get("level") or ""
            if lang:
                normalized.append(f"{lang} ({prof})" if prof else lang)
    return normalized


def _merge_education(
    sources: Dict[str, Dict[str, Any]], order: List[str]
) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for source in order:
        for item in sources[source].get("education") or []:
            school = (item.get("school") or item.get("institution") or "").strip()
            degree = (item.get("degree") or "").strip()
            years = (item.get("years") or item.get("dates") or "").strip() or None

            raw_topics = item.get("topics") or []
            if isinstance(raw_topics, str):
                raw_topics = [t.strip() for t in raw_topics.split(",") if t.strip()]
            elif not isinstance(raw_topics, list):
                raw_topics = []

            raw_details = item.get("details")
            if raw_details and isinstance(raw_details, str):
                details_list = [d.strip() for d in re.split(r"[,;.]\s*", raw_details) if d.strip()]
                topics = _dedup_preserving_order(raw_topics + details_list)
            else:
                topics = _dedup_preserving_order(raw_topics)

            if not school and not degree:
                continue

            school_slug = _normalize_key(school)
            degree_slug = _normalize_key(degree)
            key = f"{school_slug}::{degree_slug}" if degree_slug else school_slug

            if key not in grouped:
                grouped[key] = {
                    "school": school,
                    "degree": degree,
                    "years": years,
                    "topics": topics,
                }
            else:
                current = grouped[key]
                if not current.get("school") and school:
                    current["school"] = school
                if not current.get("degree") and degree:
                    current["degree"] = degree
                if not current.get("years") and years:
                    current["years"] = years
                current["topics"] = _dedup_preserving_order(current.get("topics", []) + topics)

    return list(grouped.values())


def _merge_certifications(
    sources: Dict[str, Dict[str, Any]], order: List[str]
) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for source in order:
        for item in sources[source].get("certifications") or []:
            name = (item.get("name") or item.get("title") or "").strip()
            issuer = (item.get("issuer") or item.get("organization") or "").strip()
            year = (item.get("year") or item.get("date") or "").strip() or None

            topics = item.get("topics") or []
            if isinstance(topics, str):
                topics = [t.strip() for t in topics.split(",") if t.strip()]
            elif not isinstance(topics, list):
                topics = []

            if not name:
                continue

            key = _normalize_key(name)
            if key not in grouped:
                grouped[key] = {
                    "name": name,
                    "issuer": issuer,
                    "year": year,
                    "topics": _dedup_preserving_order(topics),
                }
            else:
                current = grouped[key]
                if not current.get("issuer") and issuer:
                    current["issuer"] = issuer
                if not current.get("year") and year:
                    current["year"] = year
                current["topics"] = _dedup_preserving_order(current.get("topics", []) + topics)

    return list(grouped.values())


def build_profile_from_sources(
    sources: Dict[str, Dict[str, Any]],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Construit le profil dérivé et la liste des conflits non résolus.

    `sources` est un dictionnaire {nom de source: payload}. Les sources vides ou
    absentes sont ignorées. Le résultat ne dépend que de l'entrée : réappeler la
    fonction avec les mêmes sources rend exactement le même profil.
    """
    order = _ordered_sources(sources)
    conflicts: List[Dict[str, Any]] = []

    contributions = [(source, sources[source]) for source in order]

    contact: Dict[str, Any] = {}
    for source in reversed(order):  # la priorité la plus forte écrit en dernier
        src_payload = sources[source]
        src_contact = src_payload.get("contact") or src_payload.get("personal_info") or {}
        contact.update({k: v for k, v in src_contact.items() if v and k != "languages"})

    languages: List[str] = []
    interests: List[str] = []
    for source in order:
        languages.extend(_extract_languages(sources[source]))
        raw_interests = sources[source].get("interests") or sources[source].get("personal_info", {}).get("interests") or []
        if isinstance(raw_interests, list):
            interests.extend([str(i).strip() for i in raw_interests if str(i).strip()])

    _, headline = _first_non_empty("headline", contributions)
    _, summary = _first_non_empty("summary", contributions)
    _, preferences = _first_non_empty("preferences", contributions)
    _, writing_style = _first_non_empty("writing_style", contributions)

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
        "experiences": experiences,
        "projects": _merge_projects(sources, order),
        "education": _merge_education(sources, order),
        "certifications": _merge_certifications(sources, order),
        "languages": _dedup_preserving_order(languages),
        "interests": _dedup_preserving_order(interests),
        "skills": skills,
        "excluded_projects": list(sources.get("manual", {}).get("excluded_projects", []) or []),
    }
    return profile, conflicts

