from bson import ObjectId


def serialize_mongodb_doc(doc):
    """
    Convertit un document MongoDB en un document sérialisable pour JSON
    """
    if not doc:
        return None

    # Créer une copie du document pour éviter de modifier l'original
    serialized = dict(doc)

    # Convertir les ObjectId en str
    for key, value in serialized.items():
        if isinstance(value, ObjectId):
            serialized[key] = str(value)

    # S'assurer que location est bien inclus (même si None)
    if "location" not in serialized and isinstance(doc, dict):
        serialized["location"] = None

    return serialized


def capitalize_words(text):
    """
    Capitalise la première lettre de chaque mot dans une chaîne de caractères
    et met le reste en minuscule.

    Exemples:
        "MACHINE LEARNING ENGINEER" -> "Machine Learning Engineer"
        "data analyst" -> "Data Analyst"
    """
    if not text:
        return text

    # Sépare les mots et capitalise chacun d'eux
    return " ".join(word.capitalize() for word in text.split())

from typing import Dict, Any, List, Tuple

def merge_profile_sources(cv_data: Dict[str, Any], site_data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Fusionne les données du CV (cv_data) avec les données du web enrichi (site_data)."""
    conflicts: List[Dict[str, Any]] = []
    merged_experiences: List[Dict[str, Any]] = []
    provenance: List[Dict[str, str]] = []

    cv_exps = cv_data.get("experiences") or []
    site_exps = site_data.get("experiences") or []

    site_exp_map = {
        (e.get("company", "").lower().strip(), str(e.get("start", "")), str(e.get("end", ""))): e
        for e in site_exps
    }

    for cv_e in cv_exps:
        company = cv_e.get("company", "")
        key = (company.lower().strip(), str(cv_e.get("start", "")), str(cv_e.get("end", "")))
        if key in site_exp_map:
            site_e = site_exp_map.pop(key)
            cv_stack = set(cv_e.get("stack") or [])
            site_stack = set(site_e.get("stack") or [])
            if cv_stack != site_stack:
                conflicts.append({
                    "company": company,
                    "field": "stack",
                    "cv_stack": list(cv_stack),
                    "site_stack": list(site_stack),
                })
            unified_exp = dict(cv_e)
            unified_exp["stack"] = list(cv_stack.union(site_stack))
            unified_exp["missions"] = list(set((cv_e.get("missions") or []) + (site_e.get("missions") or [])))
            merged_experiences.append(unified_exp)
            provenance.append({"field_path": f"experiences.{company}", "source": "cv+site"})
        else:
            merged_experiences.append(cv_e)
            provenance.append({"field_path": f"experiences.{company}", "source": "cv"})

    for site_e in site_exp_map.values():
        company = site_e.get("company", "")
        merged_experiences.append(site_e)
        provenance.append({"field_path": f"experiences.{company}", "source": "site"})

    # Merge skills
    cv_skills = cv_data.get("skills") or {}
    site_skills = site_data.get("skills") or {}
    merged_skills = dict(cv_skills)
    for cat, skills in site_skills.items():
        if cat not in merged_skills:
            merged_skills[cat] = []
        merged_skills[cat] = list(set(merged_skills[cat] + skills))

    merged_profile = {
        "headline": cv_data.get("headline") or site_data.get("headline", ""),
        "summary": cv_data.get("summary") or site_data.get("summary", ""),
        "experiences": merged_experiences,
        "projects": site_data.get("projects") or cv_data.get("projects") or [],
        "education": cv_data.get("education") or site_data.get("education") or [],
        "certifications": site_data.get("certifications") or cv_data.get("certifications") or [],
        "languages": cv_data.get("languages") or site_data.get("languages") or [],
        "skills": merged_skills,
        "provenance": provenance,
    }

    return merged_profile, conflicts

