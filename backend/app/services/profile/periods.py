"""Normalisation des périodes et des employeurs.

Les sources n'écrivent pas les dates de la même façon : le CV dit « Août 2025 »,
le site dit « Aug. 2025 ». Comparer les chaînes brutes crée un doublon par
variante d'écriture ; tout passe donc par ces fonctions avant comparaison.
"""

import re
import unicodedata

_MONTHS = {
    "janvier": 1, "january": 1, "jan": 1,
    "fevrier": 2, "february": 2, "feb": 2, "fev": 2,
    "mars": 3, "march": 3, "mar": 3,
    "avril": 4, "april": 4, "apr": 4, "avr": 4,
    "mai": 5, "may": 5,
    "juin": 6, "june": 6, "jun": 6,
    "juillet": 7, "july": 7, "jul": 7, "juil": 7,
    "aout": 8, "august": 8, "aug": 8,
    "septembre": 9, "september": 9, "sep": 9, "sept": 9,
    "octobre": 10, "october": 10, "oct": 10,
    "novembre": 11, "november": 11, "nov": 11,
    "decembre": 12, "december": 12, "dec": 12,
}

_OPEN_ENDED = {
    "present", "presente", "aujourd'hui", "aujourdhui", "en cours",
    "current", "now", "actuel", "actuellement", "today", "",
}

_LEGAL_SUFFIXES = {"sas", "sa", "sarl", "sasu", "inc", "llc", "ltd", "gmbh"}


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def is_open_ended(raw: str | None) -> bool:
    """Vrai quand la période n'a pas de fin connue (poste en cours)."""
    if raw is None:
        return True
    return _strip_accents(raw).strip().lower() in _OPEN_ENDED


def normalize_month(raw: str | None, fallback_year: str | None = None) -> str | None:
    """Retourne 'YYYY-MM', ou 'YYYY' si le mois est absent, ou None si sans fin.

    None signifie « pas de date exploitable » : période ouverte, chaîne vide,
    ou format non reconnu. L'appelant traite None comme une information absente,
    jamais comme une erreur.
    Si le mois est présent mais que l'année est omise (ex: "Mars" pour "Mars — Sept. 2021"),
    fallback_year permet de déduire l'année depuis la date de fin.
    """
    if is_open_ended(raw):
        return None

    text = _strip_accents(str(raw)).strip().lower()

    # 2021-03 ou 2021/03
    iso = re.match(r"^(\d{4})[-/](\d{1,2})$", text)
    if iso:
        month = int(iso.group(2))
        if 1 <= month <= 12:
            return f"{iso.group(1)}-{month:02d}"
        else:
            return None

    # 03/2021 ou 03-2021
    reverse = re.match(r"^(\d{1,2})[-/](\d{4})$", text)
    if reverse:
        month = int(reverse.group(1))
        if 1 <= month <= 12:
            return f"{reverse.group(2)}-{month:02d}"
        else:
            return None

    year_match = re.search(r"(19|20)\d{2}", text)
    if not year_match and fallback_year:
        year_match = re.search(r"(19|20)\d{2}", str(fallback_year))
    if not year_match:
        return None
    year = year_match.group(0)

    for name, number in _MONTHS.items():
        if re.search(rf"\b{name}\b", text):
            return f"{year}-{number:02d}"

    return year


def company_slug(raw: str) -> str:
    """Clé stable pour un employeur, insensible à la casse, aux accents et au lieu.

    Les sources accolent le lieu ou le type de contrat au nom : on coupe à la
    première parenthèse et à la première virgule, puis on retire les suffixes
    juridiques.
    """
    if not raw:
        return ""
    text = _strip_accents(raw).lower()
    text = re.split(r"[(,|]", text)[0]
    text = re.sub(r"[^a-z0-9&\s-]", " ", text)
    tokens = [t for t in text.split() if t]
    # Strip legal suffixes only from the end
    while tokens and tokens[-1] in _LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens).strip()
