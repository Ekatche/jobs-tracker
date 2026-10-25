"""Référentiel géographique du score hybride : résolution d'une localisation
en départements français.

Charge une fois `communes_departements.json` (généré par
`scripts/build_communes_index.py` depuis geo.api.gouv.fr), qui mappe
`normalize_text(nom)` (commune, département ou région) vers la liste de ses
codes département. Une localisation non reconnue résout vers un ensemble
vide — jamais une erreur, jamais une exclusion par défaut (cf. assess.py).
"""

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from app.services.normalization import normalize_city
from app.services.relevance import normalize_text

_INDEX_PATH = Path(__file__).parent / "communes_departements.json"

_POSTAL_CODE = re.compile(r"\b(\d{5})\b")
_PAREN_CODE = re.compile(r"\(([^)]+)\)")
_CORSE_CODE = re.compile(r"^2[AB]$", re.IGNORECASE)
_DEPT_CODE = re.compile(r"^\d{2,3}$")


@lru_cache(maxsize=1)
def _load_index() -> dict[str, list[str]]:
    with open(_INDEX_PATH, encoding="utf-8") as f:
        data = json.load(f)
    data.pop("_source", None)
    return data


def _department_from_postal_code(code: str) -> frozenset[str]:
    """2 premiers chiffres, 3 pour les DOM (97x), {"2A", "2B"} pour la Corse (20)."""
    if code.startswith("97"):
        return frozenset({code[:3]})
    prefix = code[:2]
    if prefix == "20":
        return frozenset({"2A", "2B"})
    return frozenset({prefix})


def _department_from_code_token(token: str) -> Optional[frozenset[str]]:
    """Un jeton entre parenthèses, s'il ressemble à un code département."""
    token = token.strip().upper()
    if _CORSE_CODE.match(token):
        return frozenset({token})
    if _DEPT_CODE.match(token):
        if token == "20":
            return frozenset({"2A", "2B"})
        return frozenset({token})
    return None


def departments_for_location(text: Optional[str]) -> frozenset[str]:
    """Départements résolus pour `text`, vide si inconnu.

    Ordre de résolution : code postal à 5 chiffres repéré n'importe où dans
    le texte, puis code entre parenthèses, puis nom (premier segment avant
    une virgule, passé par `normalize_city` puis `normalize_text`).
    """
    if not text:
        return frozenset()

    postal_match = _POSTAL_CODE.search(text)
    if postal_match:
        return _department_from_postal_code(postal_match.group(1))

    paren_match = _PAREN_CODE.search(text)
    if paren_match:
        from_code = _department_from_code_token(paren_match.group(1))
        if from_code is not None:
            return from_code

    first_segment = text.split(",", 1)[0]
    key = normalize_text(normalize_city(first_segment))
    return frozenset(_load_index().get(key, []))
