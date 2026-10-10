"""Fusion des sources du profil candidat.

Fonction pure : aucun I/O, aucun LLM, aucune base. Un seul endroit décide quelle
source gagne sur quel champ, ce qui rend la règle lisible et testable.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from app.services.profile.periods import company_slug, is_open_ended, normalize_month

SOURCE_PRIORITY: Tuple[str, ...] = ("manual", "cv", "website", "github")

_SCALAR_FIELDS = ("role", "location", "contract", "sector")

_MANUAL_CLEARABLE_CONTACT_KEYS = ("mobility", "availability")


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


def _keys_loosely_match(a: str, b: str) -> bool:
    """Return True if `a` and `b` likely represent the same entity despite slight naming differences.

    Two sources (e.g. parsed CV vs scraped site) rarely extract the exact same
    name word-for-word ("Sentinel" vs "Sentinel - Trading Platform", or "Nile"
    vs "Agency Nile Consulting"). Once exact key equality is ruled out, we allow
    shorter key tokens to form a contiguous sub-sequence of the longer key, with a
    minimum length threshold to prevent short generic words from matching falsely.
    """
    if not a or not b or a == b:
        return False
    if len(a) < 4 or len(b) < 4:
        return False
    tokens_a = [t for t in re.split(r"[-\s]+", a) if t]
    tokens_b = [t for t in re.split(r"[-\s]+", b) if t]
    shorter, longer = (tokens_a, tokens_b) if len(tokens_a) <= len(tokens_b) else (tokens_b, tokens_a)
    if not shorter:
        return False
    window = len(shorter)
    return any(
        longer[i : i + window] == shorter for i in range(len(longer) - window + 1)
    )



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
                if existing_company == c_slug or _keys_loosely_match(existing_company, c_slug):
                    # Never merge two distinct experiences coming from the same source
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

            matched_key = key if key in grouped else next(
                (existing for existing in grouped if _keys_loosely_match(key, existing)),
                None,
            )

            if matched_key is None:
                grouped[key] = dict(project)
                grouped[key]["name"] = name
                grouped[key]["sources"] = [source]
                continue

            current = grouped[matched_key]
            if source not in current.get("sources", []):
                current.setdefault("sources", []).append(source)

            # Privilégie un nom d'affichage plus lisible (ex: "Jobs Tracker" vs "jobs-tracker")
            if _is_prettier_name(name, current.get("name", "")):
                current["name"] = name

            if len(desc) > len(current.get("description") or ""):
                current["description"] = project["description"]

            current["url"] = current.get("url") or project.get("url")
            current["repo"] = current.get("repo") or project.get("repo")
            current["context"] = current.get("context") or project.get("context")
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
    """Fusionne les compétences par catégorie.

    Contrairement aux expériences/projets (édition par élément, avec liste
    d'exclusion), l'UI édite les compétences via un unique textarea qui
    renvoie à chaque sauvegarde l'état complet voulu par l'utilisateur. Union
    additive avec cv/website/github ferait donc réapparaître une compétence
    supprimée: dès que manual contient des compétences, il fait autorité seul
    (même logique que headline/summary via _first_non_empty), sinon on retombe
    sur l'union des autres sources.
    """
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


def _excluded_keys_from(
    sources: Dict[str, Dict[str, Any]], order: List[str], field: str
) -> set[str]:
    """Clés normalisées exclues (`_normalize_key`), pour les champs à un seul critère."""
    excluded: set[str] = set()
    for source in order:
        for exc in sources[source].get(field) or []:
            if isinstance(exc, str) and exc:
                excluded.add(_normalize_key(exc))
    return excluded


def _education_key(school: str, degree: str) -> str:
    school_slug = _normalize_key(school)
    degree_slug = _normalize_key(degree)
    return f"{school_slug}::{degree_slug}" if degree_slug else school_slug


def _normalize_tokens(text: str) -> set[str]:
    stopwords = {
        "de", "des", "du", "et", "en", "d", "l", "la", "le", "les", "a", "au", "aux",
        "pour", "and", "of", "the", "in", "at", "sur", "sous", "par", "with"
    }
    tokens = set(re.split(r"[^a-z0-9]+", (text or "").lower()))
    return {t for t in tokens if len(t) > 1 and t not in stopwords}


def _schools_match(s1: str, s2: str) -> bool:
    slug1 = _normalize_key(s1)
    slug2 = _normalize_key(s2)
    if not slug1 or not slug2:
        return False
    if slug1 == slug2 or _keys_loosely_match(slug1, slug2):
        return True
    tok1 = _normalize_tokens(s1)
    tok2 = _normalize_tokens(s2)
    if not tok1 or not tok2:
        return False
    generic = {"universite", "university", "ecole", "school", "institut", "institute", "faculte", "faculty"}
    distinctive_intersection = (tok1 & tok2) - generic
    if distinctive_intersection:
        shorter_distinctive = (tok1 if len(tok1) <= len(tok2) else tok2) - generic
        if shorter_distinctive and shorter_distinctive.issubset(distinctive_intersection):
            return True
        if len(distinctive_intersection) >= 2:
            return True
    return False


def _degrees_match(d1: str, d2: str) -> bool:
    slug1 = _normalize_key(d1)
    slug2 = _normalize_key(d2)
    if not slug1 or not slug2:
        return True
    if slug1 == slug2 or _keys_loosely_match(slug1, slug2):
        return True
    tok1 = _normalize_tokens(d1)
    tok2 = _normalize_tokens(d2)
    if not tok1 or not tok2:
        return True
    levels = {"master", "m2", "m1", "ingenieur", "engineer", "licence", "bachelor", "doctorat", "phd", "dut", "bts"}
    level1 = tok1 & levels
    level2 = tok2 & levels
    if level1 and level2 and not (level1 & level2):
        return False
    intersection = tok1 & tok2
    return len(intersection) >= 1 or tok1.issubset(tok2) or tok2.issubset(tok1)


def _extract_years(years_str: str | None) -> set[str]:
    if not years_str:
        return set()
    return set(re.findall(r"\b(19\d\d|20\d\d)\b", years_str))


def _years_compatible(y1: str | None, y2: str | None) -> bool:
    years1 = _extract_years(y1)
    years2 = _extract_years(y2)
    if not years1 or not years2:
        return True
    return bool(years1 & years2)


def _education_items_match(item1: Dict[str, Any], item2: Dict[str, Any]) -> bool:
    s1 = item1.get("school") or item1.get("institution") or ""
    s2 = item2.get("school") or item2.get("institution") or ""
    if not _schools_match(s1, s2):
        return False
    d1 = item1.get("degree") or ""
    d2 = item2.get("degree") or ""
    if not _degrees_match(d1, d2):
        return False
    y1 = item1.get("years") or item1.get("dates")
    y2 = item2.get("years") or item2.get("dates")
    return _years_compatible(y1, y2)


def _merge_education(
    sources: Dict[str, Dict[str, Any]],
    order: List[str],
    conflicts: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    excluded_raw: List[Dict[str, str]] = []
    for source in order:
        for exc in sources[source].get("excluded_education") or []:
            if isinstance(exc, str) and exc:
                school, _, degree = exc.partition("::")
                excluded_raw.append({"school": school.strip(), "degree": degree.strip()})

    def is_excluded(item: Dict[str, Any]) -> bool:
        s = (item.get("school") or item.get("institution") or "").strip()
        d = (item.get("degree") or "").strip()
        for exc in excluded_raw:
            if _schools_match(s, exc["school"]) and (not exc["degree"] or _degrees_match(d, exc["degree"])):
                return True
        return False

    groups: List[List[Tuple[str, Dict[str, Any]]]] = []

    for source in order:
        for item in sources[source].get("education") or []:
            school = (item.get("school") or item.get("institution") or "").strip()
            degree = (item.get("degree") or "").strip()
            if not school and not degree:
                continue
            if is_excluded(item):
                continue

            matched_group = None
            for group in groups:
                # Ne jamais fusionner deux diplômes distincts de la même source
                if any(s == source for s, _ in group):
                    continue
                _, primary_item = group[0]
                if _education_items_match(item, primary_item):
                    matched_group = group
                    break

            if matched_group is not None:
                matched_group.append((source, item))
            else:
                groups.append([(source, item)])

    merged_list: List[Dict[str, Any]] = []
    for group in groups:
        winner_source, winner_item = group[0]

        all_topics: List[str] = []
        for _, item in group:
            raw_topics = item.get("topics") or []
            if isinstance(raw_topics, str):
                raw_topics = [t.strip() for t in raw_topics.split(",") if t.strip()]
            elif not isinstance(raw_topics, list):
                raw_topics = []

            raw_details = item.get("details")
            if raw_details and isinstance(raw_details, str):
                details_list = [d.strip() for d in re.split(r"[,;.]\s*", raw_details) if d.strip()]
                all_topics.extend(raw_topics + details_list)
            else:
                all_topics.extend(raw_topics)

        # École : priorité gagnante, enrichie par le libellé le plus exhaustif si non-manuel
        schools = [
            (s, (it.get("school") or it.get("institution") or "").strip())
            for s, it in group
            if (it.get("school") or it.get("institution") or "").strip()
        ]
        kept_school = schools[0][1] if schools else ""
        if winner_source != "manual" and len(schools) > 1:
            longest_school = max((sc for _, sc in schools), key=len)
            if len(longest_school) > len(kept_school) and _schools_match(kept_school, longest_school):
                kept_school = longest_school

        # Diplôme : priorité gagnante, enrichie par le libellé le plus informatif si non-manuel
        degrees = [(s, (it.get("degree") or "").strip()) for s, it in group if (it.get("degree") or "").strip()]
        kept_degree = degrees[0][1] if degrees else ""
        if winner_source != "manual" and len(degrees) > 1:
            longest_degree = max((dg for _, dg in degrees), key=len)
            if len(longest_degree) > len(kept_degree) and _degrees_match(kept_degree, longest_degree):
                kept_degree = longest_degree

        # Années : privilégier le format le plus complet (intervalle)
        years_list = [
            (s, (it.get("years") or it.get("dates") or "").strip())
            for s, it in group
            if (it.get("years") or it.get("dates") or "").strip()
        ]
        kept_years = None
        if years_list:
            years_sorted = sorted(years_list, key=lambda x: ("-" in x[1], len(x[1])), reverse=True)
            kept_years = years_sorted[0][1]

        # Traçabilité des divergences sur les diplômes
        if conflicts is not None and len(group) > 1:
            for other_source, other_item in group[1:]:
                other_degree = (other_item.get("degree") or "").strip()
                if (
                    other_degree
                    and kept_degree
                    and other_degree.lower() != kept_degree.lower()
                    and not _keys_loosely_match(_normalize_key(other_degree), _normalize_key(kept_degree))
                ):
                    conflicts.append({
                        "company": kept_school,
                        "field": "degree",
                        "kept": kept_degree,
                        "kept_source": winner_source,
                        "discarded": other_degree,
                        "discarded_source": other_source,
                    })
                other_years = (other_item.get("years") or other_item.get("dates") or "").strip()
                if other_years and kept_years and other_years != kept_years:
                    y_kept = _extract_years(kept_years)
                    y_other = _extract_years(other_years)
                    if y_kept and y_other and not (y_kept & y_other):
                        conflicts.append({
                            "company": kept_school,
                            "field": "years",
                            "kept": kept_years,
                            "kept_source": winner_source,
                            "discarded": other_years,
                            "discarded_source": other_source,
                        })

        merged_list.append({
            "school": kept_school,
            "degree": kept_degree,
            "years": kept_years,
            "topics": _dedup_preserving_order(all_topics),
        })

    return merged_list


def _merge_certifications(
    sources: Dict[str, Dict[str, Any]], order: List[str]
) -> List[Dict[str, Any]]:
    excluded_keys = _excluded_keys_from(sources, order, "excluded_certifications")
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
            if key in excluded_keys:
                continue
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
        if source == "manual":
            # Un champ vidé dans l'UI arrive en "" : il efface la valeur du CV
            # au lieu de la laisser revenir à chaque sauvegarde.
            for key in _MANUAL_CLEARABLE_CONTACT_KEYS:
                if key in src_contact and not str(src_contact[key] or "").strip():
                    contact.pop(key, None)

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

