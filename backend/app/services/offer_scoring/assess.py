"""Filtre dur, conditions bloquantes et assemblage du score hybride.

Trois couches, dans l'ordre où `assess_offer` les applique :
1. `hard_filter_reason` : l'offre est écartée entièrement (mot-clé exclu,
   stage/alternance non souhaité) — aucun score ne lui est jamais rattaché.
2. `failed_conditions` : l'offre est conservée mais plafonnée (`CAP_SCORE`)
   si une condition bloquante (géographie, type de contrat) échoue.
3. `combine` (Task 1) assemble les composantes en un `ScoreResult`.
"""

from typing import Optional

from app.services.evaluation.offer_fit import normalize_contract
from app.services.normalization import detect_contract_type
from app.services.offer_scoring.constants import W_SECTOR, W_SIZE
from app.services.offer_scoring.geo import departments_for_location
from app.services.offer_scoring.score import (
    ProfileFeatures,
    ScoreResult,
    SkillIdf,
    combine,
    preference_points,
    semantic_points,
    seniority_points,
    skill_points,
)
from app.services.relevance import contains_keyword, normalize_text

# Modes de travail reconnus d'une offre. Tout le reste (None, "", "Non
# spécifié", valeur inattendue) est traité comme inconnu.
FULL_REMOTE_MODE = "Télétravail total"
KNOWN_WORK_MODES = {FULL_REMOTE_MODE, "Hybride", "Présentiel"}

# Types de contrat exclus entièrement (et non simplement plafonnés) quand le
# candidat a exprimé des contract_types qui ne les incluent pas — §
# « Interprétation retenue » de global-constraints.md.
_HARD_FILTERED_CONTRACTS = {"stage", "alternance"}


def _offer_contract(offer: dict) -> Optional[str]:
    detected = detect_contract_type(offer.get("type_contrat"), offer.get("poste"), offer.get("description"))
    return normalize_contract(detected)


def hard_filter_reason(offer: dict, features: ProfileFeatures) -> Optional[str]:
    """Raison d'exclusion totale de l'offre, ou None si elle passe le filtre dur."""
    excluded_keywords = [kw for kw in (features.preferences.get("excluded_keywords") or []) if kw]
    if excluded_keywords:
        vocabulary = frozenset(normalize_text(kw) for kw in excluded_keywords if normalize_text(kw))
        text = f"{offer.get('poste') or ''} {offer.get('description') or ''}"
        if vocabulary and contains_keyword(text, vocabulary):
            return "excluded_keyword"

    contract_types = features.preferences.get("contract_types") or []
    if contract_types:
        offer_contract = _offer_contract(offer)
        if offer_contract in _HARD_FILTERED_CONTRACTS:
            wanted = {normalize_contract(c) for c in contract_types} - {None}
            if offer_contract not in wanted:
                return "contract"

    return None


def _geo_condition_ok(offer: dict, features: ProfileFeatures) -> bool:
    locations = features.preferences.get("locations") or []
    if not locations:
        return True

    remote_policy = features.preferences.get("remote_policy")
    mode = offer.get("mode_travail")

    if mode == FULL_REMOTE_MODE and remote_policy != "on_site":
        return True

    if remote_policy == "full_remote":
        return mode not in KNOWN_WORK_MODES

    offer_departments = departments_for_location(offer.get("localisation"))
    candidate_departments: frozenset[str] = frozenset()
    for location in locations:
        candidate_departments |= departments_for_location(location)

    if not offer_departments or not candidate_departments:
        return True

    return bool(offer_departments & candidate_departments)


def _contract_condition_ok(offer: dict, features: ProfileFeatures) -> bool:
    contract_types = features.preferences.get("contract_types") or []
    if not contract_types:
        return True

    offer_contract = _offer_contract(offer)
    if offer_contract is None:
        return True

    wanted = {normalize_contract(c) for c in contract_types} - {None}
    return offer_contract in wanted


def failed_conditions(offer: dict, features: ProfileFeatures) -> list[str]:
    """Conditions bloquantes échouées, sous-ensemble ordonné de ["geo", "contract"]."""
    conditions: list[str] = []
    if not _geo_condition_ok(offer, features):
        conditions.append("geo")
    if not _contract_condition_ok(offer, features):
        conditions.append("contract")
    return conditions


def assess_offer(
    offer: dict, features: ProfileFeatures, cos: Optional[float], idf: SkillIdf
) -> tuple[Optional[str], Optional[ScoreResult]]:
    """Évalue une offre pour un profil : (raison du filtre, None) si écartée,
    sinon (None, résultat du score), qui peut être `None` si aucune composante
    n'est applicable (ruling R1 : pas de donnée candidat exploitable)."""
    reason = hard_filter_reason(offer, features)
    if reason is not None:
        return reason, None

    conditions = failed_conditions(offer, features)

    # Ruling R1 : `semantic` sort du dénominateur si le candidat n'a aucune
    # identité exploitable, comme les autres composantes sans préférence
    # exprimée (§4.3) — sinon `semantic_points` gère `cos=None` (inconnu).
    semantic = semantic_points(cos) if features.identity else None
    skills = skill_points(offer.get("competences_cles") or [], features.skills, idf)
    seniority = seniority_points(offer.get("seniority_level"), features.seniority_levels)
    sector = preference_points(offer.get("sector"), features.preferred_industries, W_SECTOR)
    size = preference_points(offer.get("company_size"), features.preferred_company_sizes, W_SIZE)

    result = combine(
        {"semantic": semantic, "skills": skills, "seniority": seniority, "sector": sector, "size": size},
        conditions,
    )
    return None, result
