"""Pure scoring, quote verification, and Block B row-budget rules for Two-Pass evaluation."""

import re
from typing import Any, Dict, List, Optional, Tuple

from app.models import (
    BlocA,
    BlocB,
    BlocG,
    MissingRequirement,
    RequirementMatch,
)

MISSING_PENALTY = {"critical": 1.0, "high": 0.5, "meaningful": 0.2}
REQUIREMENT_WEIGHT = {"critical": 3.0, "high": 2.0, "meaningful": 1.0}
MATCH_CREDIT = {"full_match": 1.0, "partial_match": 0.5}
DOMAIN_PARTIAL_PENALTY = 0.5
NO_REQUIREMENT_SCORE = 3.0
THIN_OFFER_MAX_SCORE = 4.0
THIN_OFFER_MIN_REQUIREMENTS = 4
THIN_OFFER_MIN_DESCRIPTION_CHARS = 500

_WEIGHT_RANK = {"critical": 0, "high": 1, "meaningful": 2}
_VALID_PASS1_TIERS = ("stated", "structural", "inferred")
BLOC_B_ROW_BUDGET = 12


def calculate_evaluation_score(
    bloc_a: BlocA,
    bloc_b: BlocB,
    bloc_g: BlocG,
    description_length: Optional[int] = None,
) -> float:
    """
    Calculate final match score between 1.0 and 5.0:
    - Cap at 1.5: geo-mismatch, visa refused, domain mismatch, scam risk, or ghost job
      corroborated by a detected republication (bloc_g.reposted_frequency)
    - Base: 1 + 4 x weighted coverage of the offer requirements
      (weight critical 3 / high 2 / meaningful 1 ; credit full 1 / partial 0.5 / missing 0) ;
      3.0 when no requirement was evaluated
    - Preference mismatch (contract, seniority, salary): -1.0 critical / -0.5 high / -0.2 meaningful
    - Partial domain coherence: -0.5
    - Cap at 4.0 when the offer is too thin to justify more: fewer than 4 requirements
      evaluated, or description shorter than 500 characters (when known)
    - Bound between 1.0 and 5.0
    """
    if (
        bloc_a.geo_mismatch
        or bloc_a.visa_sponsoring_refused
        or bloc_a.domain_mismatch
        or bloc_g.is_scam_risk
        or (bloc_g.is_ghost_job and bloc_g.reposted_frequency)
    ):
        return 1.5

    total_weight = 0.0
    earned = 0.0
    for match in bloc_b.matched_requirements:
        weight = REQUIREMENT_WEIGHT.get(match.weight, 1.0)
        total_weight += weight
        earned += weight * MATCH_CREDIT.get(match.status, 0.0)
    for missing in bloc_b.missing_requirements:
        total_weight += REQUIREMENT_WEIGHT.get(missing.weight, 1.0)

    score = 1.0 + 4.0 * earned / total_weight if total_weight else NO_REQUIREMENT_SCORE
    for mismatch in bloc_a.preference_mismatches:
        score -= MISSING_PENALTY.get(mismatch.weight, 0.0)
    if bloc_a.domain_coherence == "partial":
        score -= DOMAIN_PARTIAL_PENALTY

    requirement_count = len(bloc_b.matched_requirements) + len(bloc_b.missing_requirements)
    thin_offer = requirement_count < THIN_OFFER_MIN_REQUIREMENTS or (
        description_length is not None and description_length < THIN_OFFER_MIN_DESCRIPTION_CHARS
    )
    if thin_offer:
        score = min(score, THIN_OFFER_MAX_SCORE)

    return max(1.0, min(5.0, round(score, 2)))


def _normalize_for_quote(text: str) -> str:
    text = text.lower().replace("\u2019", "'").replace("\u00a0", " ")
    text = re.sub(r"[\"«»“”]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def quote_in_offer(quote: str, offer_text: str) -> bool:
    """True si chaque fragment de la citation (séparés par des ellipses) figure dans l'offre."""
    fragments = [f.strip(" .,;:") for f in re.split(r"\.\.\.|…", _normalize_for_quote(quote or ""))]
    fragments = [f for f in fragments if f]
    if not fragments:
        return False
    normalized_offer = _normalize_for_quote(offer_text)
    return all(f in normalized_offer for f in fragments)


def cap_pass1_inferred_importance(requirements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Enforce Pass 1 gate: an inferred requirement can never carry critical or high weight."""
    for req in requirements:
        if not isinstance(req, dict):
            continue
        tier = req.get("evidence_tier")
        if tier not in _VALID_PASS1_TIERS:
            tier = "stated"
        req["evidence_tier"] = tier
        if tier == "inferred" and req.get("weight") in ("critical", "high"):
            req["weight"] = "meaningful"
    return requirements


def apply_bloc_b_row_budget(
    matched: List[RequirementMatch],
    missing: List[MissingRequirement],
    max_rows: int = BLOC_B_ROW_BUDGET,
) -> Tuple[List[RequirementMatch], List[MissingRequirement], int]:
    """Sort Block B rows (importance desc, unmet before met) and enforce row budget.

    Retaining every critical and high requirement always outranks the budget:
    only meaningful rows are trimmed when total rows exceed ``max_rows``.
    """
    sorted_missing = sorted(missing, key=lambda m: _WEIGHT_RANK.get(m.weight, 1))
    sorted_matched = sorted(
        matched,
        key=lambda m: (_WEIGHT_RANK.get(m.weight, 1), 0 if m.status != "full_match" else 1),
    )

    total = len(sorted_matched) + len(sorted_missing)
    if total <= max_rows:
        return sorted_matched, sorted_missing, 0

    priority_missing = [m for m in sorted_missing if m.weight in ("critical", "high")]
    priority_matched = [m for m in sorted_matched if m.weight in ("critical", "high")]
    meaningful_missing = [m for m in sorted_missing if m.weight == "meaningful"]
    meaningful_partial = [
        m for m in sorted_matched if m.weight == "meaningful" and m.status != "full_match"
    ]
    meaningful_full = [
        m for m in sorted_matched if m.weight == "meaningful" and m.status == "full_match"
    ]

    remaining_budget = max(0, max_rows - (len(priority_missing) + len(priority_matched)))
    kept_missing_m: List[MissingRequirement] = []
    kept_matched_m: List[RequirementMatch] = []

    for item in meaningful_missing:
        if remaining_budget <= 0:
            break
        kept_missing_m.append(item)
        remaining_budget -= 1
    for item in meaningful_partial + meaningful_full:
        if remaining_budget <= 0:
            break
        kept_matched_m.append(item)
        remaining_budget -= 1

    total_meaningful = len(meaningful_missing) + len(meaningful_partial) + len(meaningful_full)
    kept_meaningful = len(kept_missing_m) + len(kept_matched_m)
    dropped = max(0, total_meaningful - kept_meaningful)

    final_matched = sorted(
        priority_matched + kept_matched_m,
        key=lambda m: (_WEIGHT_RANK.get(m.weight, 1), 0 if m.status != "full_match" else 1),
    )
    final_missing = sorted(
        priority_missing + kept_missing_m,
        key=lambda m: _WEIGHT_RANK.get(m.weight, 1),
    )
    return final_matched, final_missing, dropped


def reconcile_with_pass1(
    pass1_requirements: List[Dict[str, Any]],
    matched_raw: List[Dict[str, Any]],
    missing_raw: List[Dict[str, Any]],
) -> tuple:
    """Impose le poids Pass 1 via req_id et compte manquante toute exigence Pass 1 non traitée.

    Les éléments Pass 2 sans req_id connu gardent leur propre poids (compatibilité).
    """
    cap_pass1_inferred_importance(pass1_requirements)
    by_id = {r["id"]: r for r in pass1_requirements if isinstance(r, dict) and r.get("id")}
    seen = set()
    for item in matched_raw + missing_raw:
        req = by_id.get(item.get("req_id"))
        if req:
            seen.add(req["id"])
            if req.get("weight") in ("critical", "high", "meaningful"):
                item["weight"] = req["weight"]
            item["importance_evidence_tier"] = req.get("evidence_tier", "stated")
    missing = list(missing_raw)
    if not seen:
        # Pass 2 n'a renvoyé aucun req_id exploitable : impossible de savoir quoi a été traité.
        return matched_raw, missing
    for req_id, req in by_id.items():
        if req_id not in seen:
            missing.append(
                {
                    "req_id": req_id,
                    "requirement": req.get("requirement", ""),
                    "weight": req.get("weight", "high"),
                    "importance_evidence_tier": req.get("evidence_tier", "stated"),
                    "reason": "Exigence de l'offre non traitée par l'évaluation : aucune preuve dans le profil.",
                }
            )
    return matched_raw, missing
