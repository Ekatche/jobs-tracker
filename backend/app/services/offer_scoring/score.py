"""Score de pertinence hybride : fonctions pures, aucune I/O ni appel réseau.

Combine une composante sémantique (similarité cosinus, Task 2) et des
composantes déterministes (compétences, séniorité, secteur, taille
d'entreprise) en un score 0-100. Règle d'inconnu (spec §4.3) : une
composante applicable dont la donnée de l'offre manque reçoit la moitié de
ses points (`known=False`) ; une composante pour laquelle le candidat n'a
exprimé aucune préférence renvoie `None` et sort du dénominateur.
"""

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, NamedTuple, Optional, Sequence

from app.services.evaluation.domain_relevance import build_candidate_identity, expand_title_acronyms
from app.services.evaluation.offer_fit import SENIORITY_ORDER
from app.services.offer_scoring.constants import (
    CAP_SCORE,
    COS_CEIL,
    COS_FLOOR,
    MEDIUM_THRESHOLD,
    STRONG_THRESHOLD,
    W_SEMANTIC,
    W_SENIORITY,
    W_SKILLS,
)
from app.services.relevance import contains_keyword, normalize_text


class ComponentPoints(NamedTuple):
    points: float
    max_points: float
    known: bool


@dataclass(frozen=True)
class ScoreResult:
    score: float
    raw_score: float
    level: str
    breakdown: Dict[str, float]
    unknown_components: List[str]
    failed_conditions: List[str]


@dataclass(frozen=True)
class ProfileFeatures:
    identity: str
    skills: frozenset[str]
    seniority_levels: tuple[str, ...]
    preferred_industries: tuple[str, ...]
    preferred_company_sizes: tuple[str, ...]
    preferences: dict


class SkillIdf:
    """Pondère chaque compétence par son IDF sur un corpus d'offres : plus
    une compétence est rare, plus un match pèse dans le score."""

    def __init__(self, doc_frequencies: Dict[str, int], n_docs: int):
        self._doc_frequencies = doc_frequencies
        self._n_docs = n_docs

    def weight(self, skill: str) -> float:
        normalized = normalize_text(skill)
        df = self._doc_frequencies.get(normalized, 0)
        return math.log((1 + self._n_docs) / (1 + df)) + 1


def build_skill_idf(skill_lists: Iterable[Sequence[str]]) -> "SkillIdf":
    skill_lists = list(skill_lists)
    doc_frequencies: Dict[str, int] = {}
    for skills in skill_lists:
        normalized_unique = {normalize_text(s) for s in skills if s and normalize_text(s)}
        for skill in normalized_unique:
            doc_frequencies[skill] = doc_frequencies.get(skill, 0) + 1
    return SkillIdf(doc_frequencies, len(skill_lists))


def semantic_points(cos: Optional[float]) -> ComponentPoints:
    if cos is None:
        return ComponentPoints(W_SEMANTIC / 2, W_SEMANTIC, False)
    if cos <= COS_FLOOR:
        fraction = 0.0
    elif cos >= COS_CEIL:
        fraction = 1.0
    else:
        fraction = (cos - COS_FLOOR) / (COS_CEIL - COS_FLOOR)
    return ComponentPoints(fraction * W_SEMANTIC, W_SEMANTIC, True)


def skill_points(
    offer_skills: Sequence[str], candidate_skills: frozenset[str], idf: SkillIdf
) -> Optional[ComponentPoints]:
    """Composante compétences, en bonus seul.

    Le profil écrit ses compétences en expressions de plusieurs mots
    ("python scikit learn") quand l'offre liste des mots isolés ("python") :
    une correspondance exacte échouerait presque toujours. Une compétence de
    l'offre compte si elle apparaît, avec des frontières de mot, dans une
    compétence du profil (sens unique : l'inverse ne compte pas). La
    composante ne descend jamais sous la moitié de ses points quand l'offre
    liste des compétences, pour qu'un profil incomplet ne pénalise pas
    l'offre.
    """
    if not candidate_skills:
        return None

    normalized_offer_skills = {normalize_text(s) for s in offer_skills if s and normalize_text(s)}
    if not normalized_offer_skills:
        return ComponentPoints(W_SKILLS / 2, W_SKILLS, False)

    total = sum(idf.weight(skill) for skill in normalized_offer_skills)
    if total == 0:
        return ComponentPoints(W_SKILLS / 2, W_SKILLS, False)

    def matches(skill: str) -> bool:
        if skill in candidate_skills:
            return True
        return any(contains_keyword(phrase, frozenset({skill})) for phrase in candidate_skills)

    matched = sum(idf.weight(skill) for skill in normalized_offer_skills if matches(skill))
    return ComponentPoints(max(W_SKILLS / 2, W_SKILLS * matched / total), W_SKILLS, True)


def seniority_points(offer_level: Optional[str], wanted: Sequence[str]) -> Optional[ComponentPoints]:
    valid_wanted = [level for level in wanted if level in SENIORITY_ORDER]
    if not valid_wanted:
        return None

    if not offer_level or offer_level not in SENIORITY_ORDER:
        return ComponentPoints(W_SENIORITY / 2, W_SENIORITY, False)

    offer_index = SENIORITY_ORDER.index(offer_level)
    distance = min(abs(offer_index - SENIORITY_ORDER.index(level)) for level in valid_wanted)

    if distance == 0:
        points = W_SENIORITY
    elif distance == 1:
        points = W_SENIORITY * 0.6
    else:
        points = 0.0

    return ComponentPoints(points, W_SENIORITY, True)


def preference_points(value: Optional[str], preferred: Sequence[str], weight: float) -> Optional[ComponentPoints]:
    if not preferred:
        return None
    if value is None:
        return ComponentPoints(weight / 2, weight, False)
    if value in preferred:
        return ComponentPoints(weight, weight, True)
    return ComponentPoints(0.0, weight, True)


def level_for(score: float) -> str:
    if score >= STRONG_THRESHOLD:
        return "strong"
    if score >= MEDIUM_THRESHOLD:
        return "medium"
    return "weak"


def combine(
    components: Dict[str, Optional[ComponentPoints]], failed_conditions: Sequence[str]
) -> Optional[ScoreResult]:
    applicable = {name: cp for name, cp in components.items() if cp is not None}
    if not applicable:
        return None

    total_points = sum(cp.points for cp in applicable.values())
    total_max = sum(cp.max_points for cp in applicable.values())
    raw_score = max(0.0, min(100.0, 100 * total_points / total_max))

    failed_conditions = list(failed_conditions)
    score = min(raw_score, CAP_SCORE) if failed_conditions else raw_score

    breakdown: Dict[str, float] = {"raw_score": raw_score}
    for name, cp in applicable.items():
        breakdown[name] = cp.points
        breakdown[f"{name}_max"] = cp.max_points

    unknown_components = [name for name, cp in components.items() if cp is not None and not cp.known]

    return ScoreResult(
        score=score,
        raw_score=raw_score,
        level=level_for(score),
        breakdown=breakdown,
        unknown_components=unknown_components,
        failed_conditions=failed_conditions,
    )


def profile_features(profile: dict) -> ProfileFeatures:
    """Extrait les features pures du profil nécessaires au score hybride.

    `skills` attendu sous forme de dict de catégories -> liste de compétences
    (aplati) ou directement une liste ; `preferences` lu pour les rôles
    ciblés, niveaux de séniorité voulus, secteurs et tailles d'entreprise.
    """
    headline = profile.get("headline") or ""
    preferences = profile.get("preferences") or {}
    target_roles = preferences.get("target_roles") or []
    identity = expand_title_acronyms(build_candidate_identity(headline, target_roles))

    raw_skills = profile.get("skills") or {}
    if isinstance(raw_skills, dict):
        flattened = [skill for values in raw_skills.values() for skill in (values or [])]
    else:
        flattened = list(raw_skills)
    skills = frozenset(normalize_text(s) for s in flattened if s and normalize_text(s))

    seniority_levels = tuple(
        level for level in (preferences.get("seniority_levels") or []) if level in SENIORITY_ORDER
    )
    preferred_industries = tuple(preferences.get("preferred_industries") or [])
    preferred_company_sizes = tuple(preferences.get("preferred_company_sizes") or [])

    return ProfileFeatures(
        identity=identity,
        skills=skills,
        seniority_levels=seniority_levels,
        preferred_industries=preferred_industries,
        preferred_company_sizes=preferred_company_sizes,
        preferences=preferences,
    )
