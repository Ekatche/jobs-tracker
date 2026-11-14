"""Deterministic score calibration and aggregated JD skill-gap analysis."""

import re
from typing import Any, Dict, List, Optional, Set, Tuple

_SCORE_BANDS: Tuple[str, ...] = ("<3.5", "3.5-3.9", "4.0-4.4", ">=4.5")
_IN_FLIGHT_STATUSES = frozenset({"To Apply", "Applied", "Follow-up"})
_INTERVIEW_STATUSES = frozenset({"Interview", "Offer", "Accepted"})
_OFFER_STATUSES = frozenset({"Offer", "Accepted"})
_RESUME_WORKAROUND_RE = re.compile(
    r"\b(?:déjà\s+(?:couvert|présent)|already\s+(?:on|in)\s+(?:the\s+)?(?:cv|resume)|supported\s+by\s+resume)\b",
    re.IGNORECASE,
)


def _score_band(score: float) -> str:
    if score < 3.5:
        return "<3.5"
    if score < 4.0:
        return "3.5-3.9"
    if score < 4.5:
        return "4.0-4.4"
    return ">=4.5"


def _seen_statuses(app: Dict[str, Any]) -> Tuple[str, Set[str]]:
    current = str(app.get("status") or "").strip()
    seen: Set[str] = {current} if current else set()
    for entry in app.get("status_history") or []:
        if isinstance(entry, str) and entry.strip():
            seen.add(entry.strip())
        elif isinstance(entry, dict):
            for key in ("status", "to", "new_status"):
                val = entry.get(key)
                if isinstance(val, str) and val.strip():
                    seen.add(val.strip())
    return current, seen


def _new_bucket(label: str) -> Dict[str, Any]:
    return {
        "label": label,
        "total_count": 0,
        "in_flight_count": 0,
        "resolved_count": 0,
        "interview_count": 0,
        "offer_count": 0,
    }


def _record_outcome(bucket: Dict[str, Any], in_flight: bool, reached_interview: bool, reached_offer: bool) -> None:
    bucket["total_count"] += 1
    if in_flight:
        bucket["in_flight_count"] += 1
        return
    bucket["resolved_count"] += 1
    if reached_interview:
        bucket["interview_count"] += 1
    if reached_offer:
        bucket["offer_count"] += 1


def _finalize_bucket(bucket: Dict[str, Any], min_band_n: int) -> Dict[str, Any]:
    resolved = bucket["resolved_count"]
    floor_met = resolved >= min_band_n and resolved > 0
    return {
        **bucket,
        "sample_floor_met": floor_met,
        "interview_rate": round(100.0 * bucket["interview_count"] / resolved, 1) if floor_met else None,
        "offer_rate": round(100.0 * bucket["offer_count"] / resolved, 1) if floor_met else None,
    }


def compute_score_calibration(
    applications: List[Dict[str, Any]],
    evaluations: List[Dict[str, Any]],
    min_band_n: int = 5,
) -> Dict[str, Any]:
    """Compare offer evaluation scores against actual pipeline outcomes while excluding in-flight apps."""
    eval_by_app: Dict[str, Dict[str, Any]] = {}
    eval_by_offer: Dict[str, Dict[str, Any]] = {}
    for ev in evaluations:
        if not isinstance(ev, dict):
            continue
        app_id = ev.get("application_id")
        if app_id is not None and str(app_id).strip():
            eval_by_app[str(app_id)] = ev
        offer_id = ev.get("offer_id")
        if offer_id is not None and str(offer_id).strip():
            eval_by_offer[str(offer_id)] = ev

    bands = {band: _new_bucket(band) for band in _SCORE_BANDS}
    archetypes: Dict[str, Dict[str, Any]] = {}
    matched_count = 0
    unscored_count = 0
    total_resolved = 0
    total_in_flight = 0

    for app in applications:
        if not isinstance(app, dict):
            continue
        ev: Optional[Dict[str, Any]] = None
        if app.get("_id") is not None:
            ev = eval_by_app.get(str(app.get("_id")))
        if ev is None and app.get("offer_id") is not None:
            ev = eval_by_offer.get(str(app.get("offer_id")))
        if ev is None:
            unscored_count += 1
            continue

        raw_score = ev.get("overall_score_1_to_5")
        if raw_score is None:
            unscored_count += 1
            continue

        matched_count += 1
        score = float(raw_score)
        band = _score_band(score)
        archetype = str(((ev.get("bloc_a") or {}).get("archetype")) or "unknown").strip() or "unknown"
        arch_bucket = archetypes.setdefault(archetype, _new_bucket(archetype))

        current_status, seen = _seen_statuses(app)
        reached_offer = bool(seen & _OFFER_STATUSES)
        reached_interview = reached_offer or bool(seen & _INTERVIEW_STATUSES) or bool(app.get("interview_date"))
        in_flight = (current_status in _IN_FLIGHT_STATUSES) and not reached_interview

        if in_flight:
            total_in_flight += 1
        else:
            total_resolved += 1

        _record_outcome(bands[band], in_flight, reached_interview, reached_offer)
        _record_outcome(arch_bucket, in_flight, reached_interview, reached_offer)

    bands_out = {band: _finalize_bucket(bands[band], min_band_n) for band in _SCORE_BANDS}
    archetypes_out = {
        k: _finalize_bucket(v, min_band_n)
        for k, v in sorted(archetypes.items(), key=lambda kv: (-kv[1]["resolved_count"], kv[0]))
    }

    warnings: List[str] = []
    if total_resolved < min_band_n:
        warnings.append(
            f"Échantillon résolu insuffisant ({total_resolved} < {min_band_n}) : calibration statistiquement fragile."
        )

    qualified = [bands_out[b] for b in _SCORE_BANDS if bands_out[b]["sample_floor_met"]]
    for idx, lower in enumerate(qualified):
        for higher in qualified[idx + 1:]:
            if (
                higher["interview_rate"] is not None
                and lower["interview_rate"] is not None
                and higher["interview_rate"] < lower["interview_rate"]
            ):
                warnings.append(
                    f"Calibration inversée : la tranche {higher['label']} ({higher['interview_rate']}%) "
                    f"convertit moins en entretien que {lower['label']} ({lower['interview_rate']}%)."
                )

    return {
        "min_band_n": min_band_n,
        "total_applications": len(applications),
        "matched_evaluations": matched_count,
        "unscored_count": unscored_count,
        "total_resolved": total_resolved,
        "total_in_flight": total_in_flight,
        "bands": bands_out,
        "by_archetype": archetypes_out,
        "warnings": warnings,
    }


def _norm_skill(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w.+/#-]+", " ", (text or "").lower())).strip()


def compute_jd_skill_gaps(
    evaluations: List[Dict[str, Any]],
    min_score: float = 0.0,
) -> Dict[str, Any]:
    """Aggregate missing JD requirements across evaluations and distinguish resume-supported skills from real gaps."""
    matched_skills: Set[str] = set()
    for ev in evaluations:
        if not isinstance(ev, dict):
            continue
        bloc_b = ev.get("bloc_b") or {}
        for match in bloc_b.get("matches") or []:
            if not isinstance(match, dict):
                continue
            if str(match.get("strength") or "").lower() in ("strong", "partial"):
                norm = _norm_skill(str(match.get("requirement") or ""))
                if norm:
                    matched_skills.add(norm)

    filtered = [
        ev for ev in evaluations
        if isinstance(ev, dict) and float(ev.get("overall_score_1_to_5") or 0.0) >= min_score
    ]

    agg: Dict[str, Dict[str, Any]] = {}
    for ev in filtered:
        archetype = str(((ev.get("bloc_a") or {}).get("archetype")) or "unknown").strip() or "unknown"
        bloc_b = ev.get("bloc_b") or {}
        seen_in_eval: Set[str] = set()
        for req in bloc_b.get("missing_requirements") or []:
            if not isinstance(req, dict):
                continue
            raw_name = str(req.get("requirement") or "").strip()
            norm = _norm_skill(raw_name)
            if not norm or norm in seen_in_eval:
                continue
            seen_in_eval.add(norm)

            entry = agg.setdefault(
                norm,
                {
                    "skill": raw_name,
                    "count": 0,
                    "critical_or_high_count": 0,
                    "archetypes": set(),
                    "supported": False,
                },
            )
            entry["count"] += 1
            if str(req.get("importance") or "").lower() in ("critical", "high"):
                entry["critical_or_high_count"] += 1
            entry["archetypes"].add(archetype)

            workaround = str(req.get("workaround") or "")
            if (
                norm in matched_skills
                or req.get("supported_by_resume") is True
                or bool(_RESUME_WORKAROUND_RE.search(workaround))
            ):
                entry["supported"] = True

    items = [
        {
            "skill": v["skill"],
            "count": v["count"],
            "critical_or_high_count": v["critical_or_high_count"],
            "archetypes": sorted(v["archetypes"]),
            "classification": "supported_by_resume" if v["supported"] else "gap",
        }
        for v in agg.values()
    ]
    items.sort(key=lambda item: (-item["critical_or_high_count"], -item["count"], item["skill"].lower()))

    return {
        "total_evaluations_analyzed": len(filtered),
        "min_score": min_score,
        "items": items,
    }
