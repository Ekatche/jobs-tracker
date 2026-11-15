import re
from typing import Any, Dict, List, Optional, Tuple

from .merge_helpers import (
    _dedup_preserving_order,
    _excluded_keys_from,
    _keys_loosely_match,
    _normalize_key,
    _normalize_tokens,
)

_GENERIC_SCHOOL_WORDS = {
    "universite", "university", "ecole", "school", "institut", "institute", "faculte", "faculty",
}
_DEGREE_LEVEL_WORDS = {
    "master", "m2", "m1", "ingenieur", "engineer", "licence", "bachelor",
    "doctorat", "phd", "dut", "bts",
}


def _education_key(school: str, degree: str) -> str:
    school_slug = _normalize_key(school)
    degree_slug = _normalize_key(degree)
    return f"{school_slug}::{degree_slug}" if degree_slug else school_slug


def _schools_match(s1: str, s2: str) -> bool:
    slug1, slug2 = _normalize_key(s1), _normalize_key(s2)
    if not slug1 or not slug2:
        return False
    if slug1 == slug2 or _keys_loosely_match(slug1, slug2):
        return True
    tok1, tok2 = _normalize_tokens(s1), _normalize_tokens(s2)
    if not tok1 or not tok2:
        return False
    distinctive = (tok1 & tok2) - _GENERIC_SCHOOL_WORDS
    if distinctive:
        shorter = (tok1 if len(tok1) <= len(tok2) else tok2) - _GENERIC_SCHOOL_WORDS
        if (shorter and shorter.issubset(distinctive)) or len(distinctive) >= 2:
            return True
    return False


def _degrees_match(d1: str, d2: str) -> bool:
    slug1, slug2 = _normalize_key(d1), _normalize_key(d2)
    if not slug1 or not slug2 or slug1 == slug2 or _keys_loosely_match(slug1, slug2):
        return True
    tok1, tok2 = _normalize_tokens(d1), _normalize_tokens(d2)
    if not tok1 or not tok2:
        return True
    level1, level2 = tok1 & _DEGREE_LEVEL_WORDS, tok2 & _DEGREE_LEVEL_WORDS
    if level1 and level2 and not (level1 & level2):
        return False
    return bool(tok1 & tok2) or tok1.issubset(tok2) or tok2.issubset(tok1)


def _extract_years(years_str: str | None) -> set[str]:
    return set(re.findall(r"\b(19\d\d|20\d\d)\b", years_str)) if years_str else set()


def _years_compatible(y1: str | None, y2: str | None) -> bool:
    years1, years2 = _extract_years(y1), _extract_years(y2)
    return True if (not years1 or not years2) else bool(years1 & years2)


def _education_items_match(item1: Dict[str, Any], item2: Dict[str, Any]) -> bool:
    s1 = item1.get("school") or item1.get("institution") or ""
    s2 = item2.get("school") or item2.get("institution") or ""
    if not _schools_match(s1, s2):
        return False
    if not _degrees_match(item1.get("degree") or "", item2.get("degree") or ""):
        return False
    return _years_compatible(
        item1.get("years") or item1.get("dates"),
        item2.get("years") or item2.get("dates"),
    )


def _collect_topics(group: List[Tuple[str, Dict[str, Any]]]) -> List[str]:
    all_topics: List[str] = []
    for _, item in group:
        raw_topics = item.get("topics") or []
        if isinstance(raw_topics, str):
            raw_topics = [t.strip() for t in raw_topics.split(",") if t.strip()]
        elif not isinstance(raw_topics, list):
            raw_topics = []
        raw_details = item.get("details")
        if raw_details and isinstance(raw_details, str):
            details = [d.strip() for d in re.split(r"[,;.]\s*", raw_details) if d.strip()]
            all_topics.extend(raw_topics + details)
        else:
            all_topics.extend(raw_topics)
    return _dedup_preserving_order(all_topics)


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
        return any(
            _schools_match(s, exc["school"]) and (not exc["degree"] or _degrees_match(d, exc["degree"]))
            for exc in excluded_raw
        )

    groups: List[List[Tuple[str, Dict[str, Any]]]] = []
    for source in order:
        for item in sources[source].get("education") or []:
            school = (item.get("school") or item.get("institution") or "").strip()
            degree = (item.get("degree") or "").strip()
            if (not school and not degree) or is_excluded(item):
                continue
            matched = next(
                (
                    group
                    for group in groups
                    if not any(s == source for s, _ in group)
                    and _education_items_match(item, group[0][1])
                ),
                None,
            )
            if matched is not None:
                matched.append((source, item))
            else:
                groups.append([(source, item)])

    merged_list: List[Dict[str, Any]] = []
    for group in groups:
        winner_source, _ = group[0]
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

        degrees = [
            (s, (it.get("degree") or "").strip()) for s, it in group if (it.get("degree") or "").strip()
        ]
        kept_degree = degrees[0][1] if degrees else ""
        if winner_source != "manual" and len(degrees) > 1:
            longest_degree = max((dg for _, dg in degrees), key=len)
            if len(longest_degree) > len(kept_degree) and _degrees_match(kept_degree, longest_degree):
                kept_degree = longest_degree

        years_list = [
            (s, (it.get("years") or it.get("dates") or "").strip())
            for s, it in group
            if (it.get("years") or it.get("dates") or "").strip()
        ]
        kept_years = (
            sorted(years_list, key=lambda x: ("-" in x[1], len(x[1])), reverse=True)[0][1]
            if years_list
            else None
        )

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
                        "company": kept_school, "field": "degree", "kept": kept_degree,
                        "kept_source": winner_source, "discarded": other_degree,
                        "discarded_source": other_source,
                    })
                other_years = (other_item.get("years") or other_item.get("dates") or "").strip()
                if other_years and kept_years and other_years != kept_years:
                    y_kept, y_other = _extract_years(kept_years), _extract_years(other_years)
                    if y_kept and y_other and not (y_kept & y_other):
                        conflicts.append({
                            "company": kept_school, "field": "years", "kept": kept_years,
                            "kept_source": winner_source, "discarded": other_years,
                            "discarded_source": other_source,
                        })

        merged_list.append({
            "school": kept_school,
            "degree": kept_degree,
            "years": kept_years,
            "topics": _collect_topics(group),
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
            if not name:
                continue
            key = _normalize_key(name)
            if key in excluded_keys:
                continue
            issuer = (item.get("issuer") or item.get("organization") or "").strip()
            year = (item.get("year") or item.get("date") or "").strip() or None
            topics = item.get("topics") or []
            if isinstance(topics, str):
                topics = [t.strip() for t in topics.split(",") if t.strip()]
            elif not isinstance(topics, list):
                topics = []

            if key not in grouped:
                grouped[key] = {
                    "name": name, "issuer": issuer, "year": year,
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
