"""Assembly of evaluation blocks A, B, G, H and final score calculation."""

import re
from typing import Any, Dict, List, Tuple

from app.models import (
    BlocA,
    BlocB,
    BlocG,
    BlocH,
    MissingRequirement,
    RequirementMatch,
)
from app.services.evaluation.bloc_h import (
    build_bloc_h_draft,
    compute_company_history_note,
)
from app.services.evaluation.offer_fit import (
    build_risk_summary,
    check_ai_buzzword_mismatch,
    check_employment_classification_risk,
    check_pay_range_width,
    check_preference_fit,
    offer_quality_warnings,
)
from app.services.evaluation.scoring_rules import (
    apply_bloc_b_row_budget,
    calculate_evaluation_score,
    quote_in_offer,
    reconcile_with_pass1,
)


def _build_bloc_a(
    offer_doc: Dict[str, Any],
    candidate_preferences: Any,
    job_title: str,
    pass1_data: Dict[str, Any],
    pass2_data: Dict[str, Any],
    domain_mismatch_prefilter: bool,
) -> BlocA:
    """Build Block A (identity, red flags, preference mismatches, domain coherence)."""
    domain_coherence = "mismatch" if domain_mismatch_prefilter else pass2_data.get("domain_coherence")
    domain_mismatch = domain_coherence == "mismatch"
    if domain_coherence not in ("match", "partial", "mismatch"):
        domain_coherence = ""

    return BlocA(
        summary=pass1_data.get("summary", ""),
        archetype=pass1_data.get("archetype", job_title),
        red_flags=pass2_data.get("red_flags", []),
        geo_mismatch=bool(pass2_data.get("geo_mismatch", False)),
        visa_sponsoring_refused=bool(pass2_data.get("visa_sponsoring_refused", False)),
        domain_mismatch=domain_mismatch,
        domain_coherence=domain_coherence,
        preference_mismatches=check_preference_fit(
            offer_doc, candidate_preferences if isinstance(candidate_preferences, dict) else {}
        ),
    )


def _build_bloc_b_pair(
    offer_doc: Dict[str, Any],
    job_title: str,
    description: str,
    pass1_data: Dict[str, Any],
    pass2_data: Dict[str, Any],
) -> Tuple[BlocB, BlocB]:
    """Reconcile Pass 1 & 2 requirements and return (full_bloc_b, budgeted_bloc_b)."""
    matched_raw, missing_raw = reconcile_with_pass1(
        pass1_data.get("requirements") or [],
        pass2_data.get("matched_requirements", []),
        pass2_data.get("missing_requirements", []),
    )
    offer_text = "\n".join([job_title, description, " ".join(offer_doc.get("competences_cles") or [])])

    matched_reqs: List[RequirementMatch] = []
    for m in matched_raw:
        weight = m.get("weight", "high")
        status = m.get("status", "full_match")
        evidence_tier = m.get("evidence_tier", "stated")
        # Gate déterministe : une preuve "inferred" ne peut jamais à elle seule
        # valider un full_match sur une exigence critical/high, même si le
        # modèle l'a affirmé. Ne pas se fier au seul respect de la consigne
        # dans le prompt (cf. career-ops : evidence tier → importance gate).
        if evidence_tier == "inferred" and weight in ("critical", "high") and status == "full_match":
            status = "partial_match"
        matched_reqs.append(
            RequirementMatch(
                requirement=m.get("requirement", ""),
                weight=weight,
                importance_evidence_tier=m.get("importance_evidence_tier", "stated"),
                candidate_evidence=m.get("candidate_evidence", ""),
                verbatim_quote=m.get("verbatim_quote", ""),
                status=status,
                evidence_tier=evidence_tier,
                quote_verified=quote_in_offer(m.get("verbatim_quote", ""), offer_text),
            )
        )

    missing_reqs = [
        MissingRequirement(
            requirement=m.get("requirement", ""),
            weight=m.get("weight", "high"),
            importance_evidence_tier=m.get("importance_evidence_tier", "stated"),
            reason=m.get("reason", ""),
            impact_on_role=m.get("impact_on_role"),
        )
        for m in missing_raw
    ]

    justification = pass2_data.get("score_justification", "")
    full_bloc_b = BlocB(
        matched_requirements=matched_reqs,
        missing_requirements=missing_reqs,
        score_justification=justification,
    )
    trimmed_matched, trimmed_missing, dropped_count = apply_bloc_b_row_budget(matched_reqs, missing_reqs)
    budgeted_bloc_b = BlocB(
        matched_requirements=trimmed_matched,
        missing_requirements=trimmed_missing,
        score_justification=justification,
        dropped_requirements_count=dropped_count,
    )
    return full_bloc_b, budgeted_bloc_b


async def _build_bloc_g(
    db: Any,
    user_str_id: str,
    offer_doc: Dict[str, Any],
    bloc_a: BlocA,
    pass1_data: Dict[str, Any],
) -> BlocG:
    """Build Block G with ghost/scam/repost signals and prior company application history."""
    publication_count = 1
    offer_company = (offer_doc.get("entreprise") or "").strip()
    if offer_company and offer_doc.get("canonical_title"):
        publication_count = await db["job_offers"].count_documents(
            {
                "entreprise": {"$regex": f"^{re.escape(offer_company)}$", "$options": "i"},
                "canonical_title": offer_doc["canonical_title"],
            }
        )
    company_history_note = await compute_company_history_note(
        db,
        user_str_id,
        offer_company,
        current_offer_id=offer_doc.get("_id"),
    )
    bloc_g = BlocG(
        is_ghost_job=bool(pass1_data.get("is_ghost_job", False)),
        is_scam_risk=bool(pass1_data.get("is_scam_risk", False)),
        reposted_frequency=f"{publication_count} publications" if publication_count >= 2 else None,
        warnings=list(pass1_data.get("ghost_job_warnings", [])) + offer_quality_warnings(offer_doc, publication_count),
        employment_classification_risk=check_employment_classification_risk(offer_doc),
        pay_range_width_warning=check_pay_range_width(offer_doc),
        ai_buzzword_mismatch=check_ai_buzzword_mismatch(offer_doc),
        company_history_note=company_history_note,
    )
    bloc_g.risk_summary = build_risk_summary(bloc_a, bloc_g, offer_doc)
    return bloc_g


async def assemble_evaluation_blocks(
    db: Any,
    user_str_id: str,
    offer_doc: Dict[str, Any],
    profile_doc: Dict[str, Any],
    job_title: str,
    description: str,
    candidate_preferences: Any,
    pass1_data: Dict[str, Any],
    pass2_data: Dict[str, Any],
    domain_mismatch_prefilter: bool,
) -> Tuple[BlocA, BlocB, BlocG, BlocH, float]:
    """Assemble blocks A/B/G/H and compute score from full unbudgeted requirements."""
    bloc_a = _build_bloc_a(
        offer_doc, candidate_preferences, job_title, pass1_data, pass2_data, domain_mismatch_prefilter
    )
    full_bloc_b, bloc_b = _build_bloc_b_pair(offer_doc, job_title, description, pass1_data, pass2_data)
    bloc_g = await _build_bloc_g(db, user_str_id, offer_doc, bloc_a, pass1_data)
    # Compute final score on the full unbudgeted requirement set so row trimming stays score-neutral
    final_score = calculate_evaluation_score(bloc_a, full_bloc_b, bloc_g, len(description.strip()))
    bloc_h = build_bloc_h_draft(offer_doc, profile_doc, bloc_a, full_bloc_b, final_score)
    return bloc_a, bloc_b, bloc_g, bloc_h, final_score
