"""Contexte candidat injecté dans les prompts LLM (évaluation, préparation d'entretien).

Source unique : les champs lus ici sont ceux de CandidateProfile (app/models.py).
Toute nouvelle consommation du profil dans un prompt doit passer par cette fonction
pour éviter les divergences de nommage (headline, start/end, missions, ...).
"""

from typing import Any, Dict


def build_candidate_context(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Projette un document candidate_profile vers le dict sérialisé dans les prompts."""
    return {
        "headline": profile.get("headline", ""),
        "summary": profile.get("summary", ""),
        "preferences": profile.get("preferences", {}),
        "skills": profile.get("skills", {}),
        "experiences": [
            {
                "role": exp.get("role"),
                "company": exp.get("company"),
                "sector": exp.get("sector"),
                "start": exp.get("start"),
                "end": exp.get("end"),
                "stack": exp.get("stack", []),
                "missions": exp.get("missions", []),
                "achievements": [
                    {"text": ach.get("text"), "metric": ach.get("metric")}
                    for ach in exp.get("achievements", [])
                ],
            }
            for exp in profile.get("experiences", [])
        ],
        "education": [
            {
                "school": edu.get("school"),
                "degree": edu.get("degree"),
                "years": edu.get("years"),
                "topics": edu.get("topics", []),
            }
            for edu in profile.get("education", [])
        ],
        "projects": [
            {
                "name": proj.get("name"),
                "description": proj.get("description"),
                "stack": proj.get("stack", []),
                "context": proj.get("context"),
                "url": proj.get("url"),
                "repo": proj.get("repo"),
                "highlights": proj.get("highlights", []),
            }
            for proj in profile.get("projects", [])
        ],
        "certifications": [
            {
                "name": cert.get("name"),
                "issuer": cert.get("issuer"),
                "year": cert.get("year"),
                "topics": cert.get("topics", []),
            }
            for cert in profile.get("certifications", [])
        ],
        "languages": profile.get("languages", []),
    }
