"""Candidate profile, evaluation, and offer formatting helpers for interview prompts."""

import json
from typing import Any, Dict, Optional, Tuple

from app.services.profile.context import build_candidate_context


def format_candidate_profile_context(profile: Dict[str, Any]) -> str:
    """Format candidate profile into text context for prompts (same projection as the evaluator)."""
    full_name = (profile.get("contact") or {}).get("full_name") or "Candidat"
    headline = profile.get("headline") or ""
    header = f"Candidat : {full_name} - {headline}" if headline else f"Candidat : {full_name}"
    context = json.dumps(build_candidate_context(profile), ensure_ascii=False, indent=2)
    return f"{header}\n{context}"


def _format_bloc_b_lines(bloc_b: Dict[str, Any]) -> list[str]:
    """Format matched and missing requirements from evaluation Block B."""
    lines: list[str] = []
    matched = bloc_b.get("matched_requirements") or []
    if matched:
        lines.append("\nExigences validées (Points forts du candidat) :")
        for m in matched:
            tags = [m.get("weight", "")]
            if m.get("status") == "partial_match":
                tags.append("couverture partielle")
            if m.get("evidence_tier") == "inferred":
                tags.append("preuve déduite, non explicite dans le profil")
            tags_str = ", ".join(t for t in tags if t)
            lines.append(f"- {m.get('requirement', '')} [{tags_str}] (Preuve: {m.get('candidate_evidence', '')})")

    missing = bloc_b.get("missing_requirements") or []
    if missing:
        lines.append("\nExigences manquantes / à anticiper :")
        for mis in missing:
            lines.append(
                f"- {mis.get('requirement', '')} [Poids: {mis.get('weight', '')}] "
                f"(Écart: {mis.get('reason', '')})"
            )

    if bloc_b.get("score_justification"):
        lines.append(f"\nJustification du score : {bloc_b.get('score_justification')}")
    return lines


def format_evaluation_context(evaluation: Optional[Dict[str, Any]]) -> str:
    """Extract and format Bloc A, Bloc B, and Bloc G insights."""
    if not evaluation:
        return "Aucune évaluation préalable disponible."

    lines = []
    score = evaluation.get("score")
    if score is not None:
        lines.append(f"Score de matching global : {score}/5.0")

    bloc_a = evaluation.get("bloc_a") or {}
    if bloc_a.get("summary"):
        lines.append(f"Synthèse de l'offre : {bloc_a.get('summary')}")
    if bloc_a.get("archetype"):
        lines.append(f"Archétype de poste identifié : {bloc_a.get('archetype')}")
    if bloc_a.get("red_flags"):
        lines.append("Drapeaux rouges détectés : " + "; ".join(bloc_a.get("red_flags")))

    lines.extend(_format_bloc_b_lines(evaluation.get("bloc_b") or {}))

    bloc_g = evaluation.get("bloc_g") or {}
    if bloc_g.get("warnings"):
        lines.append("Alertes sur l'offre : " + "; ".join(bloc_g.get("warnings")))

    return "\n".join(lines)


def _offer_role_and_company(offer: Dict[str, Any]) -> Tuple[str, str]:
    """job_offers stocke poste/entreprise ; title/company gardés en repli."""
    role = offer.get("poste") or offer.get("title") or "Poste"
    company = offer.get("entreprise") or offer.get("company") or "Entreprise"
    return role, company
