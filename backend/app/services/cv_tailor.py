import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

from litellm import acompletion

from app.models import TailoredCVSchema
from app.services.cv_guards import verify_cv_honesty

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "llm" / "prompts"
DEFAULT_CV_MODEL = os.getenv("CV_TAILOR_MODEL", os.getenv("EVALUATION_MODEL", "gemini/gemini-2.5-flash"))


def _clean_json_output(raw_text: str) -> Dict[str, Any]:
    """Strip markdown code block fences and parse JSON."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw_text.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"(\{.*\})", cleaned, flags=re.DOTALL)
        if match:
            return json.loads(match.group(1))
        raise


def load_tailor_prompt(
    profile: Dict[str, Any],
    offer: Dict[str, Any],
    evaluation: Optional[Dict[str, Any]] = None,
) -> str:
    """Format and load the CV tailor prompt template."""
    prompt_file = PROMPTS_DIR / "cv" / "tailor_prompt.md"
    template = prompt_file.read_text(encoding="utf-8")

    eval_context_lines = []
    if evaluation and "bloc_b" in evaluation:
        bloc_b = evaluation["bloc_b"]
        matched = bloc_b.get("requirements_matched", [])
        if matched:
            eval_context_lines.append("Compétences et exigences validées du candidat :")
            for m in matched:
                req = m.get("requirement", "")
                evidence = m.get("candidate_evidence", "")
                eval_context_lines.append(f"- {req} (Preuve: {evidence})")

        missing = bloc_b.get("missing_requirements", [])
        if missing:
            eval_context_lines.append("\nCompétences manquantes (ATTENTION : NE PAS INVENTER, NE PAS PRÉTENDRE LES AVOIR) :")
            for miss in missing:
                req = miss.get("requirement", "")
                importance = miss.get("importance", "")
                eval_context_lines.append(f"- {req} [{importance}]")

    eval_context_str = "\n".join(eval_context_lines) if eval_context_lines else "Aucune analyse Bloc B préalable disponible."

    # Serialize profile for prompt (excluding internal ids)
    profile_for_prompt = {
        k: v for k, v in profile.items()
        if k not in ["_id", "id", "user_id", "created_at", "updated_at"]
    }

    return template.format(
        candidate_profile=json.dumps(profile_for_prompt, ensure_ascii=False, indent=2),
        target_company=offer.get("company", "L'entreprise cible"),
        target_role=offer.get("title", "Poste visé"),
        job_location=offer.get("location", "Non spécifié"),
        offer_description=offer.get("description", offer.get("job_description", "")),
        evaluation_context=eval_context_str,
    )


async def generate_tailored_cv_content(
    profile: Dict[str, Any],
    offer: Dict[str, Any],
    evaluation: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
) -> TailoredCVSchema:
    """
    Generate tailored CV content aligned to job offer and Bloc B evaluation,
    validated by strict anti-hallucination guardrails.
    """
    prompt = load_tailor_prompt(profile, offer, evaluation)
    chosen_model = model or DEFAULT_CV_MODEL

    logger.info(f"Generating tailored CV for {offer.get('title')} at {offer.get('company')} with model {chosen_model}")

    try:
        response = await acompletion(
            model=chosen_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        content_text = response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error calling LLM for CV tailoring: {e}", exc_info=True)
        raise

    raw_json = _clean_json_output(content_text)
    tailored_cv = TailoredCVSchema(**raw_json)

    # Anti-hallucination guardrail validation
    is_valid, violations = verify_cv_honesty(tailored_cv, profile)
    if not is_valid:
        error_msg = f"CV honesty verification failed: {'; '.join(violations)}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    return tailored_cv
