import re
from typing import Tuple, List, Dict, Any, Set
from difflib import SequenceMatcher
from app.models import TailoredCVSchema


def _clean_str(s: str) -> str:
    """Normalizes string for comparison by lowercasing and removing extra spaces/punctuation."""
    if not s:
        return ""
    cleaned = re.sub(r"[^\w\s]", " ", s.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def _is_fuzzy_match(val: str, known_set: Set[str], threshold: float = 0.85) -> bool:
    """Checks if val is present in or closely matches any item in known_set."""
    clean_val = _clean_str(val)
    if not clean_val:
        return True

    for item in known_set:
        clean_item = _clean_str(item)
        if not clean_item:
            continue
        if clean_val == clean_item or clean_val in clean_item or clean_item in clean_val:
            return True
        if SequenceMatcher(None, clean_val, clean_item).ratio() >= threshold:
            return True
    return False


def verify_cv_honesty(
    tailored: TailoredCVSchema,
    source_profile: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """
    Guardrail anti-hallucination pur.
    Vérifie qu'aucune entreprise, diplôme ou compétence inventée
    n'a été injectée par le LLM dans le CV sur-mesure.
    """
    violations: List[str] = []

    # 1. Extraction des entreprises connues dans le profil source
    known_companies: Set[str] = set()
    for exp in source_profile.get("experiences", []):
        comp = exp.get("company") or exp.get("entreprise")
        if comp:
            known_companies.add(str(comp).strip())

    for exp in tailored.experiences:
        if not _is_fuzzy_match(exp.company, known_companies):
            violations.append(
                f"Entreprise '{exp.company}' non trouvée dans les expériences du profil candidat."
            )

    # 2. Extraction des compétences connues
    known_skills: Set[str] = set()

    def _extract_skills_recursive(data: Any) -> None:
        if isinstance(data, list):
            for item in data:
                _extract_skills_recursive(item)
        elif isinstance(data, dict):
            for k, v in data.items():
                if isinstance(k, str) and not k.lower().endswith(("_skills", "skills", "langages")):
                    known_skills.add(k.strip())
                _extract_skills_recursive(v)
        elif isinstance(data, str) and data.strip():
            known_skills.add(data.strip())
            # Split compound strings such as "Python (Pandas, NumPy, PyTorch)"
            tokens = re.findall(r"[\w\.\+#\-]+", data)
            for token in tokens:
                if len(token) > 1:
                    known_skills.add(token.strip())

    _extract_skills_recursive(source_profile.get("skills"))

    for exp in source_profile.get("experiences", []):
        for t in exp.get("technologies", []) or []:
            if t:
                known_skills.add(str(t).strip())

    for proj in source_profile.get("projects", []):
        for t in proj.get("technologies", []) or []:
            if t:
                known_skills.add(str(t).strip())

    for group in tailored.prioritized_skills:
        for skill in group.skills:
            if not _is_fuzzy_match(skill, known_skills, threshold=0.88):
                violations.append(
                    f"Compétence '{skill}' (catégorie '{group.category}') absente du profil candidat vérifié."
                )

    # 3. Extraction des formations et diplômes connus
    known_schools: Set[str] = set()
    known_degrees: Set[str] = set()
    for edu in source_profile.get("education", []) or []:
        school = edu.get("school") or edu.get("institution") or edu.get("ecole")
        if school:
            known_schools.add(str(school).strip())
        degree = edu.get("degree") or edu.get("diplome")
        if degree:
            known_degrees.add(str(degree).strip())

    for edu in tailored.education:
        school_match = _is_fuzzy_match(edu.institution, known_schools)
        degree_match = _is_fuzzy_match(edu.degree, known_degrees)
        if not (school_match or degree_match):
            violations.append(
                f"Formation '{edu.degree}' à '{edu.institution}' absente du cursus du profil candidat."
            )

    is_valid = len(violations) == 0
    return is_valid, violations
