"""Référentiel géographique du score hybride : résolution d'une localisation
en départements français.

Charge une fois `communes_departements.json` (généré par
`scripts/build_communes_index.py` depuis geo.api.gouv.fr), qui mappe
`normalize_text(nom)` (commune, département ou région) vers la liste de ses
codes département. Une localisation non reconnue résout vers un ensemble
vide — jamais une erreur, jamais une exclusion par défaut (cf. assess.py).
"""

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from app.services.normalization import normalize_city
from app.services.relevance import normalize_text

logger = logging.getLogger(__name__)

_INDEX_PATH = Path(__file__).parent / "communes_departements.json"

_POSTAL_CODE = re.compile(r"\b(\d{5})\b")
_PAREN_CODE = re.compile(r"\(([^)]+)\)")
_CORSE_CODE = re.compile(r"^2[AB]$", re.IGNORECASE)
# Codes département à 2 chiffres valides : 01-95 (le 20 corse est remappé à
# part vers {"2A", "2B"}). 00 et 96-99 n'existent pas.
_DEPT_CODE = re.compile(r"^(0[1-9]|[1-8][0-9]|9[0-5])$")
# DOM : 971 (Guadeloupe) à 976 (Mayotte). 977/978 (Saint-Barthélemy,
# Saint-Martin) ne sont pas des départements et sont donc rejetés ici.
_DOM_CODE = re.compile(r"^97[1-6]$")
# Libellés LinkedIn anglais (« Greater Lyon Area », « Greater Paris
# Metropolitan Region ») sur une clé déjà passée par `normalize_text`.
_LINKEDIN_AREA = re.compile(r"^(?:greater )?(.+?) (?:metropolitan (?:region|area)|area)$")
# La métropole parisienne de LinkedIn couvre toute l'Île-de-France, pas le
# seul département 75 (sens permissif, cf. build_communes_index.py).
_LINKEDIN_AREA_ALIASES = {"paris": "ile de france"}


@lru_cache(maxsize=1)
def _load_index() -> dict[str, list[str]]:
    """Charge l'index commune/département/région -> codes département.

    Fail-open : un fichier absent ou un JSON invalide logue une erreur et
    renvoie un index vide plutôt que de lever une exception. Cohérent avec
    le reste du module (cf. docstring en tête de fichier) : une localisation
    inconnue ne doit jamais faire planter le scoring.
    """
    try:
        with open(_INDEX_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        logger.error(
            "Index géographique illisible (%s), résolution par nom désactivée",
            _INDEX_PATH,
        )
        return {}
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
    """Un jeton entre parenthèses, s'il ressemble à un code département valide.

    Codes acceptés : 01-95 (le 20 corse se résout en {"2A", "2B"}), 2A/2B
    explicite, et les DOM 971-976. Tout le reste (ex: "100", "977", "00",
    "96"-"99") est rejeté : `departments_for_location` retombe alors sur la
    résolution par nom plutôt que de renvoyer un code inventé.
    """
    token = token.strip().upper()
    if _CORSE_CODE.match(token):
        return frozenset({token})
    if _DEPT_CODE.match(token):
        if token == "20":
            return frozenset({"2A", "2B"})
        return frozenset({token})
    if _DOM_CODE.match(token):
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
    index = _load_index()
    if key not in index:
        area_match = _LINKEDIN_AREA.match(key)
        if area_match:
            city = area_match.group(1)
            key = _LINKEDIN_AREA_ALIASES.get(city, city)
    return frozenset(index.get(key, []))
