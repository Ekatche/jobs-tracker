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


# Départements français limitrophes (métropole + Corse ; les DOM sont insulaires).
# Utilisé par `expand_with_neighboring_departments` pour qu'une recherche centrée
# sur une ville (ex: Paris 75, Lyon 69, Bourgoin-Jallieu 38) accepte les communes
# limitrophes du bassin d'emploi situées juste de l'autre côté de la frontière
# départementale (ex: petite couronne 92/93/94 autour de Paris, Ain 01 / Isère 38
# autour de Lyon, Savoie 73 / Ain 01 autour de Bourgoin-Jallieu).
NEIGHBORING_DEPARTMENTS: dict[str, frozenset[str]] = {
    "01": frozenset({"38", "39", "69", "71", "73", "74"}),
    "02": frozenset({"08", "51", "59", "60", "77", "80"}),
    "03": frozenset({"18", "23", "42", "58", "63", "71"}),
    "04": frozenset({"05", "06", "26", "83", "84"}),
    "05": frozenset({"04", "26", "38", "73"}),
    "06": frozenset({"04", "83"}),
    "07": frozenset({"26", "30", "38", "42", "43", "48", "84"}),
    "08": frozenset({"02", "51", "55"}),
    "09": frozenset({"11", "31", "66"}),
    "10": frozenset({"21", "51", "52", "77", "89"}),
    "11": frozenset({"09", "31", "34", "66", "81"}),
    "12": frozenset({"15", "30", "34", "46", "48", "81", "82"}),
    "13": frozenset({"30", "83", "84"}),
    "14": frozenset({"27", "50", "61", "76"}),
    "15": frozenset({"12", "19", "43", "46", "48", "63"}),
    "16": frozenset({"17", "24", "79", "86", "87"}),
    "17": frozenset({"16", "24", "33", "79", "85"}),
    "18": frozenset({"03", "23", "36", "41", "45", "58"}),
    "19": frozenset({"15", "23", "24", "46", "63", "87"}),
    "2A": frozenset({"2B"}),
    "2B": frozenset({"2A"}),
    "21": frozenset({"10", "39", "52", "58", "70", "71", "89"}),
    "22": frozenset({"29", "35", "56"}),
    "23": frozenset({"03", "18", "19", "36", "63", "87"}),
    "24": frozenset({"16", "17", "19", "33", "46", "47", "87"}),
    "25": frozenset({"39", "70", "90"}),
    "26": frozenset({"04", "05", "07", "38", "84"}),
    "27": frozenset({"14", "28", "60", "61", "76", "78", "95"}),
    "28": frozenset({"27", "41", "45", "61", "72", "78", "91"}),
    "29": frozenset({"22", "56"}),
    "30": frozenset({"07", "12", "13", "34", "48", "84"}),
    "31": frozenset({"09", "11", "32", "65", "81", "82"}),
    "32": frozenset({"31", "40", "47", "64", "65", "82"}),
    "33": frozenset({"17", "24", "40", "47"}),
    "34": frozenset({"11", "12", "30", "81"}),
    "35": frozenset({"22", "44", "49", "50", "53", "56"}),
    "36": frozenset({"18", "23", "37", "41", "86", "87"}),
    "37": frozenset({"36", "41", "49", "72", "86"}),
    "38": frozenset({"01", "05", "07", "26", "42", "69", "73"}),
    "39": frozenset({"01", "21", "25", "70", "71"}),
    "40": frozenset({"32", "33", "47", "64"}),
    "41": frozenset({"18", "28", "36", "37", "45", "72"}),
    "42": frozenset({"03", "07", "38", "43", "63", "69", "71"}),
    "43": frozenset({"07", "15", "42", "48", "63"}),
    "44": frozenset({"35", "49", "56", "85"}),
    "45": frozenset({"18", "28", "41", "58", "77", "89", "91"}),
    "46": frozenset({"12", "15", "19", "24", "47", "82"}),
    "47": frozenset({"24", "32", "33", "40", "46", "82"}),
    "48": frozenset({"07", "12", "15", "30", "43"}),
    "49": frozenset({"35", "37", "44", "53", "72", "79", "85", "86"}),
    "50": frozenset({"14", "35", "53", "61"}),
    "51": frozenset({"02", "08", "10", "52", "55", "77"}),
    "52": frozenset({"10", "21", "51", "55", "70", "88"}),
    "53": frozenset({"35", "49", "50", "61", "72"}),
    "54": frozenset({"55", "57", "67", "88"}),
    "55": frozenset({"08", "51", "52", "54", "88"}),
    "56": frozenset({"22", "29", "35", "44"}),
    "57": frozenset({"54", "67"}),
    "58": frozenset({"03", "18", "21", "45", "71", "89"}),
    "59": frozenset({"02", "62", "80"}),
    "60": frozenset({"02", "27", "76", "77", "80", "95"}),
    "61": frozenset({"14", "27", "28", "50", "53", "72"}),
    "62": frozenset({"59", "80"}),
    "63": frozenset({"03", "15", "19", "23", "42", "43"}),
    "64": frozenset({"32", "40", "65"}),
    "65": frozenset({"31", "32", "64"}),
    "66": frozenset({"09", "11"}),
    "67": frozenset({"54", "57", "68", "88"}),
    "68": frozenset({"67", "70", "88", "90"}),
    "69": frozenset({"01", "38", "42", "71"}),
    "70": frozenset({"21", "25", "39", "52", "68", "88", "90"}),
    "71": frozenset({"01", "03", "21", "39", "42", "58", "69"}),
    "72": frozenset({"28", "37", "41", "49", "53", "61"}),
    "73": frozenset({"01", "05", "38", "74"}),
    "74": frozenset({"01", "73"}),
    "75": frozenset({"92", "93", "94"}),
    "76": frozenset({"14", "27", "60", "80"}),
    "77": frozenset({"02", "10", "45", "51", "60", "89", "91", "93", "94", "95"}),
    "78": frozenset({"27", "28", "91", "92", "95"}),
    "79": frozenset({"16", "17", "49", "85", "86"}),
    "80": frozenset({"02", "59", "60", "62", "76"}),
    "81": frozenset({"11", "12", "31", "34", "82"}),
    "82": frozenset({"12", "31", "32", "46", "47", "81"}),
    "83": frozenset({"04", "06", "13", "84"}),
    "84": frozenset({"04", "07", "13", "26", "30", "83"}),
    "85": frozenset({"17", "44", "49", "79"}),
    "86": frozenset({"16", "36", "37", "49", "79", "87"}),
    "87": frozenset({"16", "19", "23", "24", "36", "86"}),
    "88": frozenset({"52", "54", "55", "67", "68", "70"}),
    "89": frozenset({"10", "21", "45", "58", "77"}),
    "90": frozenset({"25", "68", "70"}),
    "91": frozenset({"28", "45", "77", "78", "92", "94"}),
    "92": frozenset({"75", "78", "91", "93", "94", "95"}),
    "93": frozenset({"75", "77", "92", "94", "95"}),
    "94": frozenset({"75", "77", "91", "92", "93"}),
    "95": frozenset({"27", "60", "77", "78", "92", "93"}),
}


def expand_with_neighboring_departments(departments: frozenset[str]) -> frozenset[str]:
    """Élargit un ensemble de départements à leurs départements limitrophes directs."""
    expanded = set(departments)
    for dept in departments:
        expanded |= NEIGHBORING_DEPARTMENTS.get(dept, frozenset())
    return frozenset(expanded)


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
