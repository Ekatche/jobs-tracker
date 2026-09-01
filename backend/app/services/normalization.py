import re
import string
from typing import Optional


def normalize_city(city: Optional[str]) -> str:
    """Normalise les noms de villes pour éviter les doublons"""
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
    """Normalise les noms d'entreprises pour comparaison et déduplication"""
    if not company:
        return "Non spécifié"

    normalized = company.upper()

    # Supprimer les suffixes juridiques courants
    suffixes = [" SAS", " SA", " SARL", " EURL", " SNC", " SCOP", " SASU", " SCIC", " INC", " LLC", " LTD"]
    for suffix in suffixes:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
            break

    # Nettoyer les espaces multiples
    normalized = re.sub(r"\s+", " ", normalized.strip())

    return normalized if normalized else "Non spécifié"


def normalize_position(position: Optional[str]) -> str:
    """Normalise les intitulés de postes pour améliorer la détection de similarité"""
    if not position:
        return "Non spécifié"

    normalized = position.upper()

    # Supprimer les mentions H/F courantes avant de nettoyer la ponctuation
    mentions_hf = [r"\(H/F\)", r"\(F/H\)", r"\(H\s*F\)", r"\bH/F\b", r"\bF/H\b", r"\bHF\b", r"\bHOMME\s+FEMME\b", r"\bFEMME\s+HOMME\b"]
    for pattern in mentions_hf:
        normalized = re.sub(pattern, " ", normalized, flags=re.IGNORECASE)

    # Supprimer la ponctuation et caractères spéciaux
    normalized = normalized.translate(str.maketrans("", "", string.punctuation))

    # Nettoyer les espaces multiples
    normalized = re.sub(r"\s+", " ", normalized.strip())

    # Trier les mots significatifs pour rendre l'ordre non-bloquant
    words = [word for word in normalized.split() if len(word) > 1 and word.lower() not in {"de", "du", "des", "le", "la", "les", "un", "une", "en", "pour", "et", "ou"}]
    words.sort()

    return " ".join(words) if words else "Non spécifié"


def extract_domain(url: Optional[str]) -> str:
    """Extrait et normalise le domaine d'une URL"""
    if not url:
        return "Non spécifié"

    try:
        if "://" in url:
            domain = url.split("://")[1].split("/")[0]
        else:
            domain = url.split("/")[0]

        if domain.startswith("www."):
            domain = domain[4:]

        return domain.lower().strip()
    except Exception:
        return "Non spécifié"


def compute_unique_key(company: str, position: str, location: Optional[str] = None, url: Optional[str] = None) -> str:
    """
    Génère une clé d'upsert robuste pour une offre d'emploi.
    Si une URL spécifique est présente, elle fait partie de l'unicité.
    Sinon, elle se base sur le triplet normalisé Entreprise | Poste | Localisation.
    """
    norm_comp = normalize_company(company).lower()
    norm_pos = normalize_position(position).lower()
    norm_loc = normalize_city(location).lower() if location else "non-specifie"

    if url and len(url.strip()) > 10:
        clean_url = url.strip().rstrip("/")
        return f"{norm_comp}|{norm_pos}|{clean_url}"

    return f"{norm_comp}|{norm_pos}|{norm_loc}"
