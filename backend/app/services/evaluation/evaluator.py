"""Two-Pass Career-Ops offer evaluation orchestrator and compatibility facade."""

import asyncio
import logging
import os
import sys
import time
from typing import List, Optional, Union

from bson import ObjectId
from litellm import acompletion

from app.models import (
    ApiUsageAction,
    OfferEvaluation,
    PyObjectId,
    utcnow_with_timezone,
)
from app.services.evaluation.bloc_h import (
    _RESPONDED_APP_STATUSES,
    _SILENT_APP_STATUSES,
    build_bloc_h_draft,
    compute_company_history_note,
)
from app.services.evaluation.block_builder import assemble_evaluation_blocks
from app.services.evaluation.domain_relevance import (
    DOMAIN_RELEVANCE_THRESHOLD,
    build_candidate_identity,
    compute_domain_relevance,
)
from app.services.evaluation.llm_runner import (
    OfferEvaluationRun,
    _acompletion_retry,
    _acompletion_with_fallback,
    load_evaluation_inputs,
    run_pass1,
    run_pass2,
)
from app.services.evaluation.prompts import (
    LLM_RETRY_DELAYS,
    TRANSIENT_LLM_ERRORS,
    _clean_json_output,
)
from app.services.evaluation.scoring_rules import (
    BLOC_B_ROW_BUDGET,
    DOMAIN_PARTIAL_PENALTY,
    MATCH_CREDIT,
    MISSING_PENALTY,
    NO_REQUIREMENT_SCORE,
    REQUIREMENT_WEIGHT,
    THIN_OFFER_MAX_SCORE,
    THIN_OFFER_MIN_DESCRIPTION_CHARS,
    THIN_OFFER_MIN_REQUIREMENTS,
    _VALID_PASS1_TIERS,
    _WEIGHT_RANK,
    _normalize_for_quote,
    apply_bloc_b_row_budget,
    calculate_evaluation_score,
    cap_pass1_inferred_importance,
    quote_in_offer,
    reconcile_with_pass1,
)
from app.services.usage_tracker import record_api_usage, require_user_quota

__all__ = [
    "BLOC_B_ROW_BUDGET",
    "DEFAULT_EVALUATION_MODEL",
    "DOMAIN_PARTIAL_PENALTY",
    "EVALUATION_FALLBACK_MODEL",
    "LLM_RETRY_DELAYS",
    "MATCH_CREDIT",
    "MISSING_PENALTY",
    "NO_REQUIREMENT_SCORE",
    "OfferEvaluationRun",
    "REQUIREMENT_WEIGHT",
    "THIN_OFFER_MAX_SCORE",
    "THIN_OFFER_MIN_DESCRIPTION_CHARS",
    "THIN_OFFER_MIN_REQUIREMENTS",
    "TRANSIENT_LLM_ERRORS",
    "_RESPONDED_APP_STATUSES",
    "_SILENT_APP_STATUSES",
    "_VALID_PASS1_TIERS",
    "_WEIGHT_RANK",
    "_acompletion_retry",
    "_acompletion_with_fallback",
    "_clean_json_output",
    "_normalize_for_quote",
    "acompletion",
    "apply_bloc_b_row_budget",
    "asyncio",
    "build_bloc_h_draft",
    "calculate_evaluation_score",
    "cap_pass1_inferred_importance",
    "compute_company_history_note",
    "compute_domain_relevance",
    "compute_offer_evaluation",
    "evaluate_offer_two_pass",
    "quote_in_offer",
    "reconcile_with_pass1",
    "record_api_usage",
    "require_user_quota",
]

logger = logging.getLogger(__name__)

DEFAULT_EVALUATION_MODEL = os.getenv("EVALUATION_MODEL", "gemini/gemini-3.8-flash")
# Modèle de secours quand le principal reste indisponible après tous les essais
# (surcharge propre à un modèle) ; vide = pas de secours.
EVALUATION_FALLBACK_MODEL = os.getenv("EVALUATION_FALLBACK_MODEL", "gemini/gemini-3.8-flash")


async def compute_offer_evaluation(
    db,
    user_id: Union[str, ObjectId, PyObjectId],
    offer_id: Union[str, ObjectId, PyObjectId],
    model: Optional[str] = None,
    skip_domain_prefilter: bool = False,
) -> OfferEvaluationRun:
    """
    Calcul pur du Two-Pass (Pass 1, Pass 2, blocs A/B/G, score), sans effet de bord.

    Lit l'offre et le profil en base, mais n'écrit rien, ne vérifie aucun quota et
    n'enregistre aucune consommation. Utilisé par le banc de mesure et par
    `evaluate_offer_two_pass`, qui se charge de l'enregistrement.
    """
    mod = sys.modules[__name__]
    eval_model = model or mod.DEFAULT_EVALUATION_MODEL
    models_used: List[str] = []
    user_str_id = str(user_id)
    offer_oid = ObjectId(str(offer_id))

    offer_doc, profile_doc = await load_evaluation_inputs(db, user_str_id, offer_oid)
    job_title = offer_doc.get("poste", "Poste sans titre")
    description = offer_doc.get("description") or ""
    candidate_headline = profile_doc.get("headline", "")
    candidate_preferences = profile_doc.get("preferences", {})
    candidate_target_roles = (
        candidate_preferences.get("target_roles", [])
        if isinstance(candidate_preferences, dict)
        else []
    )

    domain_mismatch_prefilter = False
    if not skip_domain_prefilter:
        candidate_identity = build_candidate_identity(candidate_headline, candidate_target_roles)
        candidate_roles = [
            r for r in [candidate_headline, *(candidate_target_roles or [])] if r and r.strip()
        ]
        domain_similarity = await mod.compute_domain_relevance(
            candidate_identity,
            job_title,
            candidate_roles=candidate_roles,
        )
        domain_mismatch_prefilter = (
            domain_similarity is not None and domain_similarity < DOMAIN_RELEVANCE_THRESHOLD
        )
        if domain_mismatch_prefilter:
            mod.logger.info(
                f"🚫 Offre '{job_title}' écartée par le pré-filtre de cohérence métier "
                f"(similarité={domain_similarity:.3f} < seuil={DOMAIN_RELEVANCE_THRESHOLD})"
            )

    start_time = time.time()
    pass1_data, in1, out1 = await run_pass1(offer_doc, eval_model, models_used, domain_mismatch_prefilter)
    pass2_data, in2, out2 = await run_pass2(
        offer_doc, profile_doc, pass1_data, eval_model, models_used, domain_mismatch_prefilter
    )
    latency_ms = int((time.time() - start_time) * 1000)

    bloc_a, bloc_b, bloc_g, bloc_h, final_score = await assemble_evaluation_blocks(
        db=db,
        user_str_id=user_str_id,
        offer_doc=offer_doc,
        profile_doc=profile_doc,
        job_title=job_title,
        description=description,
        candidate_preferences=candidate_preferences,
        pass1_data=pass1_data,
        pass2_data=pass2_data,
        domain_mismatch_prefilter=domain_mismatch_prefilter,
    )

    return OfferEvaluationRun(
        evaluation={
            "user_id": user_str_id,
            "offer_id": str(offer_oid),
            "score": final_score,
            "headline": f"{bloc_a.archetype} ({final_score}/5.0)",
            "pipeline_stage": "evaluated",
            "bloc_a": bloc_a.model_dump(),
            "bloc_b": bloc_b.model_dump(),
            "bloc_g": bloc_g.model_dump(),
            "bloc_h": bloc_h.model_dump(),
            "models_used": models_used or [eval_model],
        },
        input_tokens=in1 + in2,
        output_tokens=out1 + out2,
        latency_ms=latency_ms,
    )


async def evaluate_offer_two_pass(
    db,
    user_id: Union[str, ObjectId, PyObjectId],
    offer_id: Union[str, ObjectId, PyObjectId],
    model: Optional[str] = None,
    skip_domain_prefilter: bool = False,
) -> OfferEvaluation:
    """
    Execute the Two-Pass Career-Ops Evaluation Protocol:
    1. Pass 1: Parse job offer requirements, archetype, and ghost job signals (without CV bias).
    2. Pass 2: Match against CandidateProfile & Preferences with mandatory verbatim citations.
    3. Deduct quota, store the evaluation (computed by `compute_offer_evaluation`), and record API consumption.
    """
    mod = sys.modules[__name__]
    user_str_id = str(user_id)

    await mod.require_user_quota(db, user_str_id, ApiUsageAction.EVALUATION)

    run = await mod.compute_offer_evaluation(
        db,
        user_id,
        offer_id,
        model,
        skip_domain_prefilter=skip_domain_prefilter,
    )
    offer_oid = ObjectId(run.evaluation["offer_id"])
    final_score = run.evaluation["score"]

    now = utcnow_with_timezone()
    evaluation_doc = {**run.evaluation, "created_at": now, "updated_at": now}

    await db["offer_evaluations"].update_one(
        {"user_id": user_str_id, "offer_id": str(offer_oid)},
        {"$set": evaluation_doc},
        upsert=True,
    )

    await db["job_offers"].update_one(
        {"_id": offer_oid},
        {
            "$set": {
                "pipeline_stage": "evaluated",
                "evaluation_score": final_score,
                "updated_at": now,
            }
        },
    )

    await mod.record_api_usage(
        db=db,
        user_id=user_str_id,
        action=ApiUsageAction.EVALUATION,
        models_used=evaluation_doc["models_used"],
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        latency_ms=run.latency_ms,
        metadata={"offer_id": str(offer_oid), "score": final_score},
    )

    return OfferEvaluation(**evaluation_doc)
