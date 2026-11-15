from typing import Any, Dict, List, Tuple

from app.services.profile.periods import company_slug, is_open_ended, normalize_month

from .merge_helpers import (
    _SCALAR_FIELDS,
    SOURCE_PRIORITY,
    _dedup_preserving_order,
    _first_non_empty,
    _keys_loosely_match,
)

_MAX_START_GAP_MONTHS = 2
_MIN_OVERLAP_MONTHS = 2


def _end_of(experience: Dict[str, Any]) -> str | None:
    return normalize_month(experience.get("end") or experience.get("end_date"))


def _month_index(value: str, *, end: bool = False) -> int:
    """'YYYY-MM' en nombre de mois ; 'YYYY' seul vaut janvier (début) ou décembre (fin)."""
    year = int(value[:4])
    month = int(value[5:7]) if len(value) >= 7 else (12 if end else 1)
    return year * 12 + month


def _same_position_dates(
    start_a: str, end_a: str | None, start_b: str, end_b: str | None
) -> bool:
    """Deux périodes d'un même employeur désignent-elles le même poste ?"""
    if len(start_a) < 7 or len(start_b) < 7:
        return start_a[:4] == start_b[:4]
    a0, b0 = _month_index(start_a), _month_index(start_b)
    if abs(a0 - b0) <= _MAX_START_GAP_MONTHS:
        return True
    if not end_a or not end_b:
        return start_a[:4] == start_b[:4]
    a1, b1 = _month_index(end_a, end=True), _month_index(end_b, end=True)
    if abs(a1 - b1) > _MAX_START_GAP_MONTHS:
        return False
    return min(a1, b1) - max(a0, b0) + 1 >= _MIN_OVERLAP_MONTHS


def _merge_one_experience(
    contributions: List[Tuple[str, Dict[str, Any]]],
    conflicts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    _winner_source, winner = contributions[0]
    starts = [
        normalize_month(
            payload.get("start") or payload.get("start_date"),
            fallback_year=payload.get("end") or payload.get("end_date"),
        )
        for _, payload in contributions
    ]
    merged: Dict[str, Any] = {
        "company": winner.get("company", ""),
        "start": next((s for s in starts if s), None),
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
                conflicts.append({
                    "company": merged["company"],
                    "field": field,
                    "kept": kept_value,
                    "kept_source": kept_source,
                    "discarded": other,
                    "discarded_source": source,
                })

    # Fin de période : une date réelle bat une période ouverte.
    ends = [
        (source, normalize_month(payload.get("end") or payload.get("end_date")))
        for source, payload in contributions
        if not is_open_ended(payload.get("end") or payload.get("end_date"))
    ]
    merged["end"] = ends[0][1] if ends else None
    distinct_ends = {value for _source, value in ends if value}
    if len(distinct_ends) > 1:
        conflicts.append({
            "company": merged["company"],
            "field": "end",
            "kept": merged["end"],
            "kept_source": ends[0][0],
            "discarded": sorted(distinct_ends - {merged["end"]}),
            "discarded_source": "autres sources",
        })

    # Missions : le bloc le plus fourni, pas l'union — évite le doublon FR/EN.
    blocks = [(source, payload.get("missions") or []) for source, payload in contributions]
    blocks_sorted = sorted(
        blocks,
        key=lambda item: (
            -len(item[1]),
            SOURCE_PRIORITY.index(item[0]) if item[0] in SOURCE_PRIORITY else 99,
        ),
    )
    merged["missions"] = _dedup_preserving_order(list(blocks_sorted[0][1]))
    merged["missions_source"] = blocks_sorted[0][0]
    alternates = [m for _source, block in blocks_sorted[1:] for m in block]
    merged["missions_alt"] = _dedup_preserving_order(alternates)

    merged["stack"] = _dedup_preserving_order(
        [item for _source, payload in contributions for item in (payload.get("stack") or [])]
    )
    merged["achievements"] = [
        item for _source, payload in contributions for item in (payload.get("achievements") or [])
    ]
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

            matched_key = None
            for key in key_order:
                existing_company, existing_start = key
                if existing_company == c_slug or _keys_loosely_match(existing_company, c_slug):
                    if any(s == source for s, _ in grouped[key]):
                        continue
                    if existing_start == s_date or existing_start is None or s_date is None:
                        matched_key = key
                        break
                    if any(
                        _same_position_dates(
                            normalize_month(
                                payload.get("start") or payload.get("start_date"),
                                fallback_year=_end_of(payload),
                            )
                            or existing_start,
                            _end_of(payload),
                            s_date,
                            _end_of(experience),
                        )
                        for _s, payload in grouped[key]
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
                if matched_key[1] is None and s_date is not None:
                    idx = key_order.index(matched_key)
                    updated_key = (c_slug, s_date)
                    key_order[idx] = updated_key
                    grouped[updated_key] = grouped.pop(matched_key)

    merged = [_merge_one_experience(grouped[key], conflicts) for key in key_order]
    return sorted(merged, key=lambda e: e["start"] or "", reverse=True)
