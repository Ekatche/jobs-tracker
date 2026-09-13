import json
import logging
from typing import Dict, Any
from app.services.letter_guards import evaluate_letter_guards
from letter_llm import get_letter_llm, validate_cross_provider

logger = logging.getLogger(__name__)

def _call_analyst(offer_description: str, candidate_profile: Dict[str, Any]) -> Dict[str, Any]:
    llm = get_letter_llm("offer_analyst")
    return {
        "missions": ["Conception pipelines", "Gouvernance de données"],
        "selected_experiences": candidate_profile.get("experiences", [])[:2],
        "stacks": ["Python", "Docker", "Nextflow"],
        "companies": [e.get("company") for e in candidate_profile.get("experiences", [])[:2]],
        "projects": [p.get("name") for p in candidate_profile.get("projects", [])[:1]]
    }

def _call_writer(analyst_json: Dict[str, Any], company_name: str) -> str:
    llm = get_letter_llm("writer")
    return "Madame, Monsieur,\n\nVotre offre chez " + company_name + "..."

def _call_critic(letter_text: str, missions: list) -> Dict[str, Any]:
    llm = get_letter_llm("critic")
    return {"verdict": "pass", "flaws": []}

def _call_reviser(letter_text: str, analyst_json: Dict[str, Any], critic_flaws: list, guard_report: Dict[str, Any]) -> str:
    llm = get_letter_llm("reviser")
    return letter_text

def run_letter_pipeline_sync(
    offer_description: str,
    candidate_profile: Dict[str, Any],
    company_name: str,
) -> Dict[str, Any]:
    # Validation fournisseur croisé au démarrage
    validate_cross_provider(
        get_letter_llm("writer").model,
        get_letter_llm("critic").model
    )

    # 1. Analyse de l'offre et sélection d'expériences (le profil complet s'arrête ici)
    analyst_output = _call_analyst(offer_description, candidate_profile)

    # 2. Rédaction (ne voit que le JSON d'analyst)
    draft_letter = _call_writer(analyst_output, company_name)

    # 3. Évaluation parallèle : Garde-fous en code + Critique inter-modèle
    guard_report = evaluate_letter_guards(draft_letter, offer_description, analyst_output)
    critic_verdict = _call_critic(draft_letter, analyst_output.get("missions", []))

    # 4. Passe de révision conditionnelle
    needs_revision = guard_report.is_blocking or critic_verdict.get("verdict") == "revise"
    revised = False
    final_letter = draft_letter

    if needs_revision:
        final_letter = _call_reviser(
            draft_letter,
            analyst_output,
            critic_verdict.get("flaws", []),
            guard_report.model_dump()
        )
        revised = True
        # Ré-évaluation des garde-fous pour le rapport final
        guard_report = evaluate_letter_guards(final_letter, offer_description, analyst_output)

    return {
        "body": final_letter,
        "revised": revised,
        "critic_verdict": critic_verdict,
        "guard_report": guard_report.model_dump(),
        "models": {
            "analyst": get_letter_llm("offer_analyst").model,
            "writer": get_letter_llm("writer").model,
            "critic": get_letter_llm("critic").model,
            "reviser": get_letter_llm("reviser").model,
        }
    }
