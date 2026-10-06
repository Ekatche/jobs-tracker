import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from litellm import acompletion

from app.models import TailoredCVSchema
from app.services.cv_guards import verify_cv_honesty

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "llm" / "prompts"
DEFAULT_CV_MODEL = os.getenv("CV_TAILOR_MODEL", os.getenv("EVALUATION_MODEL", "gemini/gemini-3.8-flash"))


class CVHonestyError(ValueError):
    """Raised when the generated CV still contains unsupported claims after the retry."""

    def __init__(self, violations: List[str]) -> None:
        self.violations = violations
        super().__init__(f"CV honesty verification failed: {'; '.join(violations)}")



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
        matched = bloc_b.get("matched_requirements") or []
        if matched:
            eval_context_lines.append("Compétences et exigences validées du candidat [poids de l'exigence dans l'offre] :")
            for m in matched:
                req = m.get("requirement", "")
                evidence = m.get("candidate_evidence", "")
                tags = [m.get("weight", "")]
                if m.get("status") == "partial_match":
                    tags.append("couverture partielle")
                tags_str = ", ".join(t for t in tags if t)
                eval_context_lines.append(f"- {req} [{tags_str}] (Preuve: {evidence})")

        missing = bloc_b.get("missing_requirements") or []
        if missing:
            eval_context_lines.append("\nCompétences manquantes (ATTENTION : NE PAS INVENTER, NE PAS PRÉTENDRE LES AVOIR) :")
            for miss in missing:
                req = miss.get("requirement", "")
                weight = miss.get("weight", "")
                reason = miss.get("reason", "")
                eval_context_lines.append(f"- {req} [{weight}] (Écart: {reason})")

    eval_context_str = "\n".join(eval_context_lines) if eval_context_lines else "Aucune analyse Bloc B préalable disponible."

    # Serialize profile for prompt (excluding internal ids and cache state)
    profile_for_prompt = {
        k: v for k, v in profile.items()
        if k not in ["_id", "id", "user_id", "created_at", "updated_at", "suggested_roles_cache"]
    }

    target_company = offer.get("entreprise") or offer.get("company") or "L'entreprise cible"
    target_role = offer.get("poste") or offer.get("title") or "Poste visé"
    job_location = offer.get("localisation") or offer.get("location") or "Non spécifié"
    offer_desc = offer.get("description") or offer.get("job_description") or ""

    return template.format(
        candidate_profile=json.dumps(profile_for_prompt, ensure_ascii=False, indent=2, default=str),
        target_company=target_company,
        target_role=target_role,
        job_location=job_location,
        offer_description=offer_desc,
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

    log_role = offer.get("poste") or offer.get("title") or "Poste"
    log_company = offer.get("entreprise") or offer.get("company") or "Entreprise"
    logger.info(f"Generating tailored CV for {log_role} at {log_company} with model {chosen_model}")

    max_attempts = 2
    violations: List[str] = []
    for attempt in range(max_attempts):
        attempt_prompt = prompt
        if violations:
            attempt_prompt += (
                "\n\n## CORRECTION REQUISE\n"
                "Ta réponse précédente a été rejetée car elle contenait des éléments absents du profil candidat :\n"
                + "\n".join(f"- {v}" for v in violations)
                + "\nRetire ces éléments (ou remplace-les par des compétences présentes mot pour mot dans le profil) "
                "et renvoie le JSON complet corrigé."
            )

        try:
            response = await acompletion(
                model=chosen_model,
                messages=[{"role": "user", "content": attempt_prompt}],
                temperature=0.2,
                response_format={"type": "json_object"},
                drop_params=True,
            )

            content_text = response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error calling LLM for CV tailoring: {e}", exc_info=True)
            raise

        raw_json = _clean_json_output(content_text)
        tailored_cv = TailoredCVSchema(**raw_json)

        # Anti-hallucination guardrail validation
        is_valid, violations = verify_cv_honesty(tailored_cv, profile)
        if is_valid:
            return tailored_cv

        logger.warning(f"CV honesty verification failed (attempt {attempt + 1}/{max_attempts}): {'; '.join(violations)}")

    raise CVHonestyError(violations)
