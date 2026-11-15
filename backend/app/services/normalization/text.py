"""Text, entity, city, company, position, and canonical unique key normalization."""

import html
import re
import string
import unicodedata
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Optional, Set


def clean_html_entities_and_tags(text: Optional[str]) -> str:
    """Nettoie les entités HTML (ex: &amp; -> &) et supprime les balises HTML résiduelles."""
    if not text:
        return ""
    val = str(text)
    # 1. Supprimer les balises HTML réelles d'abord (ex: <b>, <h3>, <p>, <br/>, <div ...>)
    # pour ne pas détruire les brackets légitimes issus de &lt;...&gt;
    val = re.sub(r"<(?:/[a-zA-Z][a-zA-Z0-9]*|[a-zA-Z][a-zA-Z0-9]*(?:\s+[^>]*)?)>", " ", val)
    # 2. Remplacer les espaces insécables et caractères invisibles
    val = val.replace("\u00a0", " ").replace("\u200b", "").replace("\ufeff", "")
    # 3. Décoder les entités HTML (jusqu'à 2 passes pour le double encodage ex: &amp;amp;)
    for _ in range(2):
        unescaped = html.unescape(val)
        if unescaped == val:
            break
        val = unescaped
    val = re.sub(r"\s+", " ", val)
    return val.strip()


def normalize_city(city: Optional[str]) -> str:
    """Normalise les noms de villes pour éviter les doublons."""
    if not city:
        return "Non spécifié"

    # Supprimer les codes postaux complets (ex: "44000 Nantes" -> "Nantes")
    city = re.sub(r"^\d{5}\s+", "", city)
    # Supprimer les codes postaux avec tiret (ex: "Nantes - 44" -> "Nantes")
    city = re.sub(r"\s*-\s*\d+.*$", "", city)
    # Supprimer les arrondissements avec tiret (ex: "Lyon - 01" -> "Lyon")
    city = re.sub(r"\s*-\s*\d{2}$", "", city)
    # Supprimer les arrondissements avec espace (ex: "LYON 01" -> "LYON")
    city = re.sub(r"\s+\d{2}$", "", city)
    # Supprimer les arrondissements avec "er", "ème", etc. (ex: "Lyon 1er" -> "Lyon")
    city = re.sub(r"\s+\d{1,2}(er|ème|e)?$", "", city, flags=re.IGNORECASE)
    # Supprimer les parenthèses et leur contenu (ex: "Lyon (Rhône)" -> "Lyon")
    city = re.sub(r"\s*\([^)]*\)", "", city)
    # Nettoyer les espaces multiples
    city = re.sub(r"\s+", " ", city.strip())

    return city.title() if city else "Non spécifié"


def normalize_company(company: Optional[str]) -> str:
    """Normalise les noms d'entreprises pour comparaison et déduplication."""
    if not company:
        return "Non spécifié"

    normalized = company.upper()

    # Supprimer les suffixes juridiques courants
    suffixes = [" SAS", " SA", " SARL", " EURL", " SNC", " SCOP", " SASU", " SCIC", " INC", " LLC", " LTD"]
    for suffix in suffixes:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
            break

    normalized = re.sub(r"\s+", " ", normalized.strip())
    return normalized if normalized else "Non spécifié"


def _fold_ascii(text: str) -> str:
    """Minuscules sans accents ni caractères non ASCII (ex: « D’Or » -> « dor »)."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


@lru_cache(maxsize=4096)
def _company_tokens(company: Optional[str]) -> tuple:
    """Jetons alphanumériques sans accents du nom normalisé ; vide pour une entreprise inconnue."""
    normalized = normalize_company(company)
    if normalized.lower() == "non spécifié":
        return ()
    return tuple(re.findall(r"[a-z0-9]+", _fold_ascii(normalized)))


def company_match_strength(company1: Optional[str], company2: Optional[str]) -> Optional[str]:
    """Compare deux noms d'entreprise, éventuellement écrits différemment selon le job board.

    "strong" : mêmes jetons une fois espaces, ponctuation et accents retirés (« BackMarket » / « Back Market »)
    ou noms très proches (ratio >= 0.85).
    "weak" : les jetons d'un nom sont le début de l'autre (« JEMS » / « Jems Group ») ; l'appelant doit
    alors exiger des descriptions proches.
    None : entreprises différentes ou inconnues.
    """
    t1, t2 = _company_tokens(company1), _company_tokens(company2)
    if not t1 or not t2:
        return None

    k1, k2 = "".join(t1), "".join(t2)
    if k1 == k2:
        return "strong"
    if 2 * min(len(k1), len(k2)) >= 0.85 * (len(k1) + len(k2)):
        matcher = SequenceMatcher(None, k1, k2)
        if matcher.quick_ratio() >= 0.85 and matcher.ratio() >= 0.85:
            return "strong"

    short, long_ = (t1, t2) if len(t1) < len(t2) else (t2, t1)
    if long_[: len(short)] == short:
        return "weak"
    return None


GENERIC_CITY_KEYS: Set[str] = {"", "nonspecifie", "france", "teletravail", "remote"}


def _city_key(location: Optional[str]) -> str:
    """Ville repliée, limitée au segment avant la première virgule (« Lyon, Auvergne-Rhône-Alpes, France » -> « lyon »)."""
    city = normalize_city(location).split(",")[0]
    return "".join(re.findall(r"[a-z0-9]+", _fold_ascii(city)))


def normalize_position(position: Optional[str]) -> str:
    """Normalise les intitulés de postes pour améliorer la détection de similarité."""
    if not position:
        return "Non spécifié"

    normalized = position.upper()

    # Supprimer les mentions H/F courantes avant de nettoyer la ponctuation
    mentions_hf = [
        r"\(H/F\)",
        r"\(F/H\)",
        r"\(H\s*F\)",
        r"\bH/F\b",
        r"\bF/H\b",
        r"\bHF\b",
        r"\bHOMME\s+FEMME\b",
        r"\bFEMME\s+HOMME\b",
    ]
    for pattern in mentions_hf:
        normalized = re.sub(pattern, " ", normalized, flags=re.IGNORECASE)

    normalized = normalized.translate(str.maketrans("", "", string.punctuation))
    normalized = re.sub(r"\s+", " ", normalized.strip())

    stopwords = {"de", "du", "des", "le", "la", "les", "un", "une", "en", "pour", "et", "ou"}
    words = [word for word in normalized.split() if len(word) > 1 and word.lower() not in stopwords]
    words.sort()

    return " ".join(words) if words else "Non spécifié"


def compute_unique_key(
    company: str,
    position: str,
    location: Optional[str] = None,
    url: Optional[str] = None,
) -> str:
    """
    Génère une clé d'unicité canonique et sémantique pour une offre d'emploi.
    La clé est basée sur le triplet normalisé Entreprise | Poste | Localisation,
    permettant la réconciliation cross-plateformes (ex: Welcome to the Jungle vs LinkedIn).
    """
    norm_comp = normalize_company(company).lower()
    norm_pos = normalize_position(position).lower()
    norm_loc = normalize_city(location).lower() if location else "non-specifie"

    return f"{norm_comp}|{norm_pos}|{norm_loc}"
