"""Fusion des sources du profil candidat.

Fonction pure : aucun I/O, aucun LLM, aucune base. Un seul endroit décide quelle
source gagne sur quel champ, ce qui rend la règle lisible et testable.
"""

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


def _first_non_empty(
    field: str, contributions: List[Tuple[str, Dict[str, Any]]]
) -> Tuple[str | None, Any]:
    """Returns the (source, value) of the first contribution with a truthy value.

    Returning the source alongside the value lets callers attribute a conflict
    to the source that actually supplied the kept value — which is not always
    `contributions[0]` when the highest-priority source is silent on this field.
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
    merged: Dict[str, Any] = {
        "company": winner.get("company", ""),
        "start": normalize_month(winner.get("start")),
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
        (source, normalize_month(payload.get("end")))
        for source, payload in contributions
        if not is_open_ended(payload.get("end"))
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
            key = (
                company_slug(experience.get("company", "")),
                normalize_month(experience.get("start")),
            )
            if key not in grouped:
                grouped[key] = []
                key_order.append(key)
            grouped[key].append((source, experience))

    merged = [_merge_one_experience(grouped[key], conflicts) for key in key_order]
    # Ordre stable et lisible : du poste le plus récent au plus ancien.
    return sorted(merged, key=lambda e: e["start"] or "", reverse=True)


def _merge_projects(
    sources: Dict[str, Dict[str, Any]], order: List[str]
) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for source in order:
        for project in sources[source].get("projects") or []:
            name = (project.get("name") or "").strip()
            if not name:
                continue
            key = name.lower()
            if key not in grouped:
                grouped[key] = dict(project)
                grouped[key]["sources"] = [source]
                continue
            current = grouped[key]
            current["sources"].append(source)
            if len(project.get("description") or "") > len(current.get("description") or ""):
                current["description"] = project["description"]
            current["url"] = current.get("url") or project.get("url")
            current["stack"] = _dedup_preserving_order(
                (current.get("stack") or []) + (project.get("stack") or [])
            )
    return list(grouped.values())


def _merge_skills(
    sources: Dict[str, Dict[str, Any]], order: List[str]
) -> Dict[str, List[str]]:
    merged: Dict[str, List[str]] = {}
    for source in order:
        for category, skills in (sources[source].get("skills") or {}).items():
            merged.setdefault(category, []).extend(skills or [])
    return {cat: _dedup_preserving_order(values) for cat, values in merged.items()}


def _merge_simple_list(
    field: str, sources: Dict[str, Dict[str, Any]], order: List[str], key: str
) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for source in order:
        for item in sources[source].get(field) or []:
            identity = (item.get(key) or "").strip().lower()
            if identity and identity not in grouped:
                grouped[identity] = dict(item)
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
        contact.update({k: v for k, v in (sources[source].get("contact") or {}).items() if v})

    languages: List[str] = []
    for source in order:
        languages.extend(sources[source].get("languages") or [])

    _, headline = _first_non_empty("headline", contributions)
    _, summary = _first_non_empty("summary", contributions)

    profile = {
        "headline": headline or "",
        "summary": summary or "",
        "contact": contact,
        "experiences": _merge_experiences(sources, order, conflicts),
        "projects": _merge_projects(sources, order),
        "education": _merge_simple_list("education", sources, order, "school"),
        "certifications": _merge_simple_list("certifications", sources, order, "name"),
        "languages": _dedup_preserving_order(languages),
        "skills": _merge_skills(sources, order),
    }
    return profile, conflicts
