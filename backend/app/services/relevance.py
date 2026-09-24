"""Filtrage de pertinence métier pour le pipeline de collecte d'offres.

Module PUR : aucun import de `app.database`, `motor`, `crewai` ni `openai`.
Uniquement des modules de la bibliothèque standard (`re`, `unicodedata`, `os`,
`logging`), pour rester testable sans base de données ni dépendances lourdes.

Origine : 7 offres de génie civil / calcul de structures collectées à tort
via une page listing France Travail pour le métier "ingénieur structures",
un LLM ayant retenu "ingénieur" + "Lyon" et perdu "MLOps" de la requête
d'origine. Voir docs/micro/20260913-filter-irrelevant-job-offers/PLAN.md.
"""

import logging
import os
import re
import unicodedata

logger = logging.getLogger(__name__)


def normalize_text(text: str) -> str:
    """Normalise une chaîne pour comparaison de vocabulaire.

    Minuscules, dépliage Unicode NFKD avec suppression des diacritiques
    (`é` -> `e`), tout caractère non-alphanumérique remplacé par une espace,
    espaces compressés.

    >>> normalize_text("Ingénieur(e) structure")
    'ingenieur e structure'
    >>> normalize_text("structures-metalliques")
    'structures metalliques'
    """
    text = text.lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# Allowlist du domaine cible (data / IA / ML). Liste exacte du plan,
# ne pas improviser d'ajouts.
RELEVANCE_KEYWORDS: frozenset[str] = frozenset(
    {
        "data",
        "donnees",
        "dataops",
        "datawarehouse",
        "data science",
        "data scientist",
        "data engineer",
        "data analyst",
        "data analyste",
        "ia",
        "ai",
        "intelligence artificielle",
        "artificial intelligence",
        "ml",
        "machine learning",
        "deep learning",
        "apprentissage automatique",
        "mlops",
        "llm",
        "genai",
        "nlp",
        "generative ai",
        "ia generative",
        "computer vision",
        "analytics",
        "analyste",
        "analyst",
        "scientist",
        "science des donnees",
        "bi",
        "business intelligence",
        "big data",
        "etl",
        "elt",
        "spark",
        "databricks",
        "snowflake",
        "dbt",
        "airflow",
        "kafka",
        "python",
    }
)

# Blocklist de métiers hors-domaine, destinée au filtrage d'URL uniquement.
# Liste exacte du plan, ne pas improviser d'ajouts.
OFF_DOMAIN_URL_SLUGS: frozenset[str] = frozenset(
    {
        "structure",
        "structures",
        "charpente",
        "charpentes",
        "acier",
        "metallique",
        "metalliques",
        "genie civil",
        "batiment",
        "beton",
        "mecanique",
        "mecaniques",
        "thermique",
        "hydraulique",
        "chaudronnerie",
        "soudure",
        "btp",
        "chantier",
        "automatisme",
        "electricite",
        "electrique",
    }
)


def contains_keyword(text: str, vocabulary: frozenset[str]) -> bool:
    """Teste si `text` (une fois normalisé) contient un terme de `vocabulary`.

    Les frontières de mot sont obligatoires : sans elles "ia" matcherait
    "spécialiste" (via son "ia" normalisé), et "ml" matcherait n'importe quoi.
    Retourne True au premier match.
    """
    norm = normalize_text(text)
    for kw in vocabulary:
        if re.search(rf"\b{re.escape(kw)}\b", norm):
            return True
    return False


def _url_path(url: str) -> str:
    """Extrait le chemin d'une URL sans son schéma ni son host.

    Implémentation volontairement sans `urllib.parse` pour respecter la
    contrainte de pureté du module (imports limités à re/unicodedata/os/
    logging). Le host est délibérément exclu : `data.gouv.fr` ne doit pas
    influer sur le verdict via le mot "data" contenu dans le nom de domaine.
    """
    without_scheme = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", "", url)
    slash_index = without_scheme.find("/")
    path = without_scheme[slash_index:] if slash_index != -1 else ""
    return path.split("?", 1)[0].split("#", 1)[0]


def is_off_domain_url(url: str) -> bool:
    """True si le chemin de l'URL relève d'un métier hors-domaine.

    Règle de priorité : l'allowlist gagne sur la blocklist. Retourne True
    seulement si le chemin contient un slug de OFF_DOMAIN_URL_SLUGS et aucun
    terme de RELEVANCE_KEYWORDS.
    """
    path = _url_path(url)
    if contains_keyword(path, RELEVANCE_KEYWORDS):
        return False
    return contains_keyword(path, OFF_DOMAIN_URL_SLUGS)


# Interrupteur d'urgence : permet de court-circuiter le filtre sans
# redéployer si la collecte s'effondre.
RELEVANCE_FILTER_ENABLED = os.getenv("RELEVANCE_FILTER_ENABLED", "true").lower() not in (
    "false",
    "0",
)


# ========================================
# Pertinence par rapport à la requête d'origine (tous métiers)
# ========================================

# Format produit par `build_search_queries` :
# "Je recherche un poste de {role} proche de {loc} (CDI)".
_SOURCE_QUERY_PATTERN = re.compile(
    r"poste (?:de |d['’])(?P<role>.+?)"
    r"(?: proche de (?P<loc>.+?))?"
    r"(?: en télétravail)?"
    r"(?: \([^)]*\))?\s*$",
    re.IGNORECASE,
)


def parse_source_query(query: str) -> tuple[str | None, str | None]:
    """Extrait (rôle, localisation) d'une requête de collecte.

    Retourne (None, None) pour une requête hors format (anciennes requêtes
    libres, requête par localisation seule).
    """
    match = _SOURCE_QUERY_PATTERN.search(query or "")
    if not match:
        return None, None
    role = match.group("role").strip()
    loc = (match.group("loc") or "").strip() or None
    return role or None, loc

