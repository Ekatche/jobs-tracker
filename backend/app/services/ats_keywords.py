"""Deterministic keyword extraction from job offers & evaluations, plus CV keyword matching."""

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

_CANONICAL_KEYWORDS: Tuple[str, ...] = (
    "Python", "SQL", "PostgreSQL", "Trino", "Spark", "PySpark", "SAS", "R",
    "Git", "GitLab", "GitHub", "CI/CD", "Docker", "Kubernetes", "FastAPI",
    "Django", "Flask", "React", "TypeScript", "JavaScript", "Java", "Rust",
    "Scala", "C++", "PyTorch", "TensorFlow", "Keras", "Scikit-learn", "Pandas",
    "NumPy", "MLflow", "Airflow", "dbt", "Snowflake", "BigQuery", "Databricks",
    "Microsoft Fabric", "Power BI", "Tableau", "AWS", "Azure", "GCP", "NoSQL",
    "MongoDB", "Qdrant", "ChromaDB", "Redis", "Kafka", "Linux", "Excel",
    "SNDS", "RGPD", "CNIL", "NLP", "LLM", "RAG", "MLOps", "ETL", "ELT",
    "API", "REST", "Machine Learning", "Deep Learning", "Computer Vision",
    "Data Science", "Data Engineering", "Data Management", "Modélisation statistique",
    "Optimisation", "Algorithmes", "Segmentation", "Feature Engineering",
    "Bases de données", "Données de santé", "Essais cliniques", "Biostatistiques",
    "Supply Chain", "Agile",
)

_CASE_SENSITIVE_SINGLE_LETTER = {"R"}

_SYNONYM_MAP: Dict[str, Tuple[str, ...]] = {
    "deep learning": ("apprentissage profond", "deep learning"),
    "machine learning": ("apprentissage automatique", "machine learning"),
    "computer vision": ("vision par ordinateur", "computer vision"),
    "spark": ("pyspark", "spark"),
    "sql": ("postgresql", "azure sql", "mysql", "tsql", "pl/sql", "sql"),
    "ci/cd": ("integration continue", "github actions", "gitlab ci", "ci/cd"),
    "git": ("github", "gitlab", "git"),
    "data engineering": ("data engineer", "ingenierie des donnees", "data engineering"),
    "data science": ("data scientist", "science des donnees", "data science"),
    "data management": ("data manager", "gestion de donnees", "data management"),
    "rest": ("api rest", "restful", "fastapi", "rest"),
    "api": ("apis", "fastapi", "rest api", "api"),
    "llm": ("llms", "ia generative", "genai", "mistral", "llm"),
    "algorithmes": ("algorithme", "algorithmique", "algorithmes"),
    "bases de donnees": ("base de donnees", "sql", "nosql", "postgresql", "mongodb", "bases de donnees"),
    "donnees de sante": ("donnees patients", "donnees cliniques", "donnees medicales", "snds", "donnees de sante"),
}


def _strip_accents_lower(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def _keyword_pattern(term: str, *, case_sensitive: bool = False) -> re.Pattern[str]:
    norm = term if case_sensitive else _strip_accents_lower(term)
    parts = [re.escape(part) for part in norm.strip().split()]
    body = r"\s+".join(parts)
    if len(norm.strip()) >= 4 and norm.strip()[-1].isalnum():
        body = f"{body}s?"
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile(rf"(?<![A-Za-z0-9_]){body}(?![A-Za-z0-9_])", flags)


def _find_canonical_matches(text: str) -> List[str]:
    """Scan a single text block and return canonical keywords ordered by first match position."""
    if not text or not text.strip():
        return []
    norm_text = _strip_accents_lower(text)
    hits: List[Tuple[int, str]] = []
    for kw in _CANONICAL_KEYWORDS:
        if kw in _CASE_SENSITIVE_SINGLE_LETTER:
            match = _keyword_pattern(kw, case_sensitive=True).search(text)
        else:
            match = _keyword_pattern(kw).search(norm_text)
        if match:
            hits.append((match.start(), kw))
    hits.sort(key=lambda pair: pair[0])
    return [kw for _, kw in hits]


def _extract_clean_role_parts(raw_title: str) -> List[str]:
    cleaned = re.sub(r"\(\s*(?:f/h|h/f|m/f|f/m|e)\s*\)", "", raw_title or "", flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:cdi|cdd|stage|alternance|freelance)\b", "", cleaned, flags=re.IGNORECASE)
    head = re.split(r"\s+[–—-]\s+", cleaned.strip())[0]
    parts = []
    for chunk in re.split(r"\s*/\s*", head):
        item = re.sub(r"\s+", " ", chunk).strip(" -–—,")
        if len(item) >= 4:
            parts.append(item)
    return parts


def extract_offer_keywords(
    offer_doc: Optional[Dict[str, Any]],
    evaluation_doc: Optional[Dict[str, Any]] = None,
    max_keywords: int = 18,
) -> List[str]:
    """Extract prioritized offer keywords from competences_cles, evaluation bloc_b, title, and description."""
    ordered: List[str] = []
    seen: set[str] = set()

    def _add(kw: str) -> None:
        key = _strip_accents_lower(kw).strip()
        if key and key not in seen and len(ordered) < max_keywords:
            seen.add(key)
            ordered.append(kw.strip())

    if isinstance(offer_doc, dict):
        raw_kws = offer_doc.get("competences_cles")
        if isinstance(raw_kws, list):
            for kw in raw_kws:
                if str(kw).strip():
                    _add(str(kw).strip())
        elif isinstance(raw_kws, str) and raw_kws.strip():
            for kw in raw_kws.split(","):
                if kw.strip():
                    _add(kw.strip())

    if isinstance(evaluation_doc, dict):
        bloc_b = evaluation_doc.get("bloc_b") or {}
        req_lines = [
            str(item.get("requirement") or "").strip()
            for bucket in ("matched_requirements", "missing_requirements")
            for item in (bloc_b.get(bucket) or [])
            if isinstance(item, dict) and item.get("requirement")
        ]
        for kw in _find_canonical_matches("\n".join(req_lines)):
            _add(kw)

    if isinstance(offer_doc, dict):
        raw_poste = str(offer_doc.get("poste") or offer_doc.get("title") or "").strip()
        for kw in _find_canonical_matches(raw_poste):
            _add(kw)
        for role_part in _extract_clean_role_parts(raw_poste):
            _add(role_part)
        desc = str(offer_doc.get("description") or offer_doc.get("job_description") or "")
        for kw in _find_canonical_matches(desc):
            _add(kw)

    return ordered


def keyword_matches_cv(keyword: str, cv_text: str) -> bool:
    """Return True if keyword or a recognized FR/EN synonym appears cleanly in CV text."""
    norm_kw = _strip_accents_lower(keyword).strip()
    if not norm_kw or not cv_text:
        return False
    norm_cv = _strip_accents_lower(cv_text)
    if keyword.strip() in _CASE_SENSITIVE_SINGLE_LETTER:
        return bool(_keyword_pattern(keyword.strip(), case_sensitive=True).search(cv_text))
    if _keyword_pattern(norm_kw).search(norm_cv):
        return True
    for synonym in _SYNONYM_MAP.get(norm_kw, ()):
        if _keyword_pattern(synonym).search(norm_cv):
            return True
    return False
