"""Contrôles déterministes de l'évaluation : préférences candidat (Bloc A) et signaux d'offre (Bloc G).

Aucun appel LLM ici : ces comparaisons reposent sur des champs structurés de l'offre
(type_contrat, seniority_level, salaire, description) et du profil (preferences).
"""

import re
from typing import Any, Dict, List, Optional

from app.models import PreferenceMismatch

SHORT_DESCRIPTION_CHARS = 500

# Ordre de séniorité : la distance entre niveaux fixe le poids de l'écart.
SENIORITY_ORDER = ["intern", "junior", "mid", "senior", "lead", "director"]

# Première règle qui matche gagne ; valeurs non reconnues ("Non spécifié", "Temps partiel") ignorées.
CONTRACT_PATTERNS = [
    ("cdi", re.compile(r"\bcdii?\b|permanent", re.I)),
    ("cdd", re.compile(r"\bcdd\b", re.I)),
    ("freelance", re.compile(r"freelance|prestation|ind[ée]pendant|portage", re.I)),
    ("alternance", re.compile(r"alternance|apprentissage|contrat pro", re.I)),
    ("stage", re.compile(r"\bstage\b|intern", re.I)),
    ("interim", re.compile(r"int[ée]rim", re.I)),
]


def normalize_contract(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    for label, pattern in CONTRACT_PATTERNS:
        if pattern.search(value):
            return label
    return None


def parse_annual_salary_max(value: Optional[str]) -> Optional[int]:
    """Borne haute annuelle d'un salaire texte ; montants < 10 000 considérés mensuels."""
    if not value:
        return None
    amounts = []
    for raw in re.findall(r"\d[\d\s .,]*", value):
        digits = re.sub(r"[\s ]", "", raw)
        digits = re.sub(r"[.,]\d{1,2}$", "", digits)  # centimes
        digits = re.sub(r"[.,]", "", digits)
        if digits.isdigit() and int(digits) >= 1000:
            amounts.append(int(digits))
    if not amounts:
        return None
    top = max(amounts)
    return top * 12 if top < 10000 else top


def check_preference_fit(offer: Dict[str, Any], preferences: Dict[str, Any]) -> List[PreferenceMismatch]:
    """Écarts entre l'offre et les préférences déclarées ; champ absent d'un côté = pas d'écart."""
    mismatches: List[PreferenceMismatch] = []

    offer_contract = normalize_contract(offer.get("type_contrat"))
    wanted_contracts = {normalize_contract(c) for c in preferences.get("contract_types") or []} - {None}
    if offer_contract and wanted_contracts and offer_contract not in wanted_contracts:
        mismatches.append(
            PreferenceMismatch(
                criterion="contrat",
                offer_value=str(offer.get("type_contrat")),
                expected=", ".join(preferences.get("contract_types") or []),
                weight="high",
            )
        )

    offer_level = (offer.get("seniority_level") or "").lower()
    wanted_levels = [lvl.lower() for lvl in preferences.get("seniority_levels") or [] if lvl]
    if offer_level in SENIORITY_ORDER:
        known = [SENIORITY_ORDER.index(lvl) for lvl in wanted_levels if lvl in SENIORITY_ORDER]
        if known:
            distance = min(abs(SENIORITY_ORDER.index(offer_level) - k) for k in known)
            if distance:
                mismatches.append(
                    PreferenceMismatch(
                        criterion="séniorité",
                        offer_value=offer_level,
                        expected=", ".join(wanted_levels),
                        weight="meaningful" if distance == 1 else "high",
                    )
                )

    min_salary = preferences.get("min_salary")
    offer_salary_max = parse_annual_salary_max(offer.get("salaire"))
    if min_salary and offer_salary_max and offer_salary_max < min_salary:
        mismatches.append(
            PreferenceMismatch(
                criterion="salaire",
                offer_value=str(offer.get("salaire")),
                expected=f">= {min_salary} {preferences.get('currency') or 'EUR'} / an",
                weight="high",
            )
        )

    return mismatches


def offer_quality_warnings(offer: Dict[str, Any], publication_count: int) -> List[str]:
    """Alertes Bloc G factuelles, issues de la base et non du jugement du modèle."""
    warnings: List[str] = []
    if publication_count >= 2:
        warnings.append(
            f"Offre publiée {publication_count} fois (même entreprise et même intitulé) : possible republication."
        )
    description_len = len((offer.get("description") or "").strip())
    if description_len < SHORT_DESCRIPTION_CHARS:
        warnings.append(
            f"Description courte ({description_len} caractères) : exigences probablement incomplètes, évaluation peu fiable."
        )
    return warnings
