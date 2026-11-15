"""LLM retry/fallback runner and Two-Pass pass execution helpers."""

import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from bson import ObjectId
from fastapi import HTTPException

from app.services.evaluation.prompts import (
    LLM_RETRY_DELAYS,
    TRANSIENT_LLM_ERRORS,
    _clean_json_output,
    build_pass1_prompt,
    build_pass2_prompt,
)
from app.services.evaluation.scoring_rules import cap_pass1_inferred_importance
from app.services.profile.context import build_candidate_context


def _evaluator_module() -> Any:
    """Resolve facade module dynamically so test patches on evaluator attributes apply."""
    return sys.modules["app.services.evaluation.evaluator"]


async def _acompletion_retry(**kwargs: Any) -> Any:
    """`acompletion` réessayé avec attente croissante sur les erreurs passagères."""
    mod = _evaluator_module()
    for attempt, delay in enumerate((*LLM_RETRY_DELAYS, None), start=1):
        try:
            return await mod.acompletion(**kwargs)
        except TRANSIENT_LLM_ERRORS as e:
            if delay is None:
                raise
            mod.logger.warning(
                f"⏳ {kwargs.get('model')} indisponible (tentative {attempt}), nouvel essai dans {delay}s : {type(e).__name__}"
            )
            await mod.asyncio.sleep(delay)


async def _acompletion_with_fallback(models_used: List[str], **kwargs: Any) -> Any:
    """`_acompletion_retry`, puis un essai sur le modèle de secours si le principal
    reste indisponible. Ajoute à `models_used` le modèle qui a réellement répondu."""
    mod = _evaluator_module()
    try:
        response = await mod._acompletion_retry(**kwargs)
    except TRANSIENT_LLM_ERRORS as e:
        fallback = mod.EVALUATION_FALLBACK_MODEL
        if not fallback or fallback == kwargs.get("model"):
            raise
        mod.logger.warning(f"↪️ {kwargs.get('model')} indisponible ({type(e).__name__}), bascule sur {fallback}")
        kwargs = {**kwargs, "model": fallback}
        response = await mod.acompletion(**kwargs)
    if kwargs["model"] not in models_used:
        models_used.append(kwargs["model"])
    return response


@dataclass
class OfferEvaluationRun:
    """Résultat du Two-Pass avant enregistrement : évaluation et consommation LLM."""

    evaluation: Dict[str, Any]
    input_tokens: int
    output_tokens: int
    latency_ms: int


async def load_evaluation_inputs(
    db: Any,
    user_str_id: str,
    offer_oid: ObjectId,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Fetch target job offer and candidate profile from MongoDB."""
    offer_doc = await db["job_offers"].find_one({"_id": offer_oid})
    if not offer_doc:
        raise HTTPException(status_code=404, detail="Offre d'emploi introuvable")

    description = offer_doc.get("description") or ""
    if not description.strip() and not offer_doc.get("competences_cles"):
        raise HTTPException(
            status_code=400,
            detail="L'offre d'emploi ne contient pas de description ou de compétences exploitables pour l'évaluation.",
        )

    profile_query: List[Any] = [{"user_id": user_str_id}]
    try:
        profile_query.append({"user_id": ObjectId(user_str_id)})
    except Exception:
        pass
    profile_doc = await db["candidate_profile"].find_one({"$or": profile_query})
    if not profile_doc:
        # Profil minimaliste par défaut si non encore initialisé
        profile_doc = {"headline": "", "experiences": [], "skills": {}, "preferences": {}}
    return offer_doc, profile_doc


async def run_pass1(
    offer_doc: Dict[str, Any],
    eval_model: str,
    models_used: List[str],
    domain_mismatch_prefilter: bool,
) -> Tuple[Dict[str, Any], int, int]:
    """Run Pass 1 (requirement extraction + viability analysis) or return prefilter stub."""
    job_title = offer_doc.get("poste", "Poste sans titre")
    if domain_mismatch_prefilter:
        return {
            "archetype": job_title,
            "summary": "",
            "is_ghost_job": False,
            "is_scam_risk": False,
            "ghost_job_warnings": [],
        }, 0, 0

    pass1_prompt = build_pass1_prompt(
        job_title=job_title,
        company=offer_doc.get("entreprise", "Entreprise inconnue"),
        location=offer_doc.get("localisation", ""),
        contract=offer_doc.get("type_contrat", ""),
        work_mode=offer_doc.get("mode_travail", ""),
        description=offer_doc.get("description") or "",
    )
    response = await _acompletion_with_fallback(
        models_used,
        model=eval_model,
        messages=[{"role": "user", "content": pass1_prompt}],
        response_format={"type": "json_object"},
        temperature=0.1,
        drop_params=True,
    )
    usage = getattr(response, "usage", None)
    in_tok = getattr(usage, "prompt_tokens", 0) if usage else 0
    out_tok = getattr(usage, "completion_tokens", 0) if usage else 0

    pass1_data = _clean_json_output(response.choices[0].message.content)
    reqs_pass1 = pass1_data.get("requirements") or []
    for idx, req in enumerate(reqs_pass1, start=1):
        if isinstance(req, dict):
            req["id"] = f"R{idx}"
    cap_pass1_inferred_importance(reqs_pass1)
    return pass1_data, in_tok, out_tok


async def run_pass2(
    offer_doc: Dict[str, Any],
    profile_doc: Dict[str, Any],
    pass1_data: Dict[str, Any],
    eval_model: str,
    models_used: List[str],
    domain_mismatch_prefilter: bool,
) -> Tuple[Dict[str, Any], int, int]:
    """Run Pass 2 (candidate matching) or return domain-mismatch stub."""
    if domain_mismatch_prefilter:
        return {
            "domain_coherence": "mismatch",
            "geo_mismatch": False,
            "visa_sponsoring_refused": False,
            "red_flags": [],
            "matched_requirements": [],
            "missing_requirements": [],
            "score_justification": (
                "Offre écartée par le pré-filtre de cohérence métier : le métier de "
                "l'offre ne correspond pas au profil du candidat."
            ),
        }, 0, 0

    pass2_prompt = build_pass2_prompt(
        pass1_data=pass1_data,
        location=offer_doc.get("localisation", ""),
        work_mode=offer_doc.get("mode_travail", ""),
        candidate_context=build_candidate_context(profile_doc),
    )
    response = await _acompletion_with_fallback(
        models_used,
        model=eval_model,
        messages=[{"role": "user", "content": pass2_prompt}],
        response_format={"type": "json_object"},
        temperature=0.1,
        drop_params=True,
    )
    usage = getattr(response, "usage", None)
    in_tok = getattr(usage, "prompt_tokens", 0) if usage else 0
    out_tok = getattr(usage, "completion_tokens", 0) if usage else 0
    return _clean_json_output(response.choices[0].message.content), in_tok, out_tok
