"""Contrôle géographique des offres collectées.

Fail-open : une offre n'est écartée que sur preuve (pays étranger cité,
commune française hors rayon, localisation inconnue avec une URL publiée
pour un autre pays). Une localisation non résolue est conservée.
"""

import logging
import math
import re
from typing import Optional
from urllib.parse import urlparse

import httpx

from app.services.relevance import normalize_text

logger = logging.getLogger(__name__)

GEO_RADIUS_KM = 50
GEO_API_URL = "https://geo.api.gouv.fr/communes"

UNKNOWN_LOCATIONS = {"", "non specifie", "inconnu", "none", "null", "n a"}
REMOTE_MARKERS = ("teletravail", "remote", "france entiere")

# Pays et grandes villes étrangères, comparés sur texte normalisé (sans accents).
# Pas de ville homonyme d'une commune française (ex. Montréal, dans l'Aude).
FOREIGN_MARKERS = (
    "usa", "united states", "etats unis", "canada", "united kingdom", "royaume uni", "england",
    "germany", "allemagne", "deutschland", "spain", "espagne", "espana", "italy", "italie",
    "belgium", "belgique", "switzerland", "suisse", "schweiz", "netherlands", "pays bas",
    "luxembourg", "portugal", "ireland", "irlande", "poland", "pologne", "india", "inde",
    "singapore", "singapour", "australia", "australie", "japan", "japon", "china", "chine",
    "brazil", "bresil", "mexico", "mexique", "maroc", "morocco", "tunisie", "tunisia",
    "romania", "roumanie", "israel", "london", "londres", "new york", "san francisco",
    "berlin", "munich", "madrid", "barcelona", "amsterdam", "dublin", "zurich", "geneve",
    "geneva", "bruxelles", "brussels", "toronto", "vancouver", "bangalore", "bengaluru",
    "warsaw", "varsovie", "lisbon", "lisbonne", "prague",
)
_FOREIGN_PATTERN = re.compile(r"\b(?:" + "|".join(re.escape(m) for m in FOREIGN_MARKERS) + r")\b")

# Segment de locale dans le chemin (Workday : /fr-CA/, /en-US/).
_URL_LOCALE = re.compile(r"/([a-z]{2})-([A-Z]{2})(?:/|$)")

# Grandes villes : l'API France Travail n'accepte que le code d'arrondissement.
ARRONDISSEMENT_CODES = {"75056": "75101", "69123": "69381", "13055": "13201"}

_commune_cache: dict[str, Optional[dict]] = {}


def clean_city_label(localisation: str) -> str:
    """'69 - Lyon 3e Arrondissement' / 'Lyon, ARA, FR' / 'Toulouse Area' -> ville seule."""
    city = re.split(r"[,/(]", localisation, maxsplit=1)[0]
    city = re.sub(r"^\s*\d{2,3}\s*-\s*", "", city)
    city = re.sub(r"\s+\d{1,2}\s*(?:er|e|ème)?\s+arrondissement\b.*$", "", city, flags=re.I)
    city = re.sub(r"\s+(?:area|metropolitan area|métropole|metropole)\s*$", "", city, flags=re.I)
    return city.strip()


def mentions_foreign_country(localisation: str) -> bool:
    text = normalize_text(localisation)
    return "france" not in text.split() and bool(_FOREIGN_PATTERN.search(text))


def foreign_url_locale(url: Optional[str]) -> Optional[str]:
    """Locale d'URL indiquant un autre pays. 'en-US' n'est pas une preuve :
    c'est la locale par défaut de Workday, y compris pour des postes en France."""
    match = _URL_LOCALE.search(urlparse(url or "").path)
    if not match:
        return None
    lang, country = match.groups()
    if country == "FR" or lang == "en":
        return None
    return f"{lang}-{country}"


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lon1, lat1, lon2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


async def resolve_commune(name: str, client: httpx.AsyncClient) -> Optional[dict]:
    """Commune française dont le nom correspond exactement (sans accents) :
    {"code", "lon", "lat"}. None si inconnue ; les erreurs réseau ne sont pas mises en cache."""
    key = normalize_text(name)
    if not key:
        return None
    if key in _commune_cache:
        return _commune_cache[key]
    try:
        resp = await client.get(
            GEO_API_URL,
            params={"nom": name, "fields": "code,centre", "boost": "population", "limit": 1},
        )
        resp.raise_for_status()
        communes = resp.json()
    except Exception as e:
        logger.warning(f"⚠️ Géocodage indisponible pour '{name}': {e}")
        return None
    commune = None
    if communes and normalize_text(communes[0]["nom"]) == key:
        lon, lat = communes[0]["centre"]["coordinates"]
        commune = {"code": communes[0]["code"], "lon": lon, "lat": lat}
    _commune_cache[key] = commune
    return commune


async def location_rejection_reason(
    localisation: Optional[str],
    url: Optional[str],
    target_city: Optional[str],
    client: httpx.AsyncClient,
    radius_km: int = GEO_RADIUS_KM,
) -> Optional[str]:
    """Raison du rejet, ou None si l'offre est conservée."""
    text = normalize_text(localisation or "")
    if text in UNKNOWN_LOCATIONS:
        locale = foreign_url_locale(url)
        return f"localisation inconnue, URL publiée en {locale}" if locale else None
    if mentions_foreign_country(localisation):
        return f"localisation à l'étranger ({localisation})"
    if any(marker in text for marker in REMOTE_MARKERS) or not target_city:
        return None

    city = clean_city_label(localisation)
    target = clean_city_label(target_city)
    if normalize_text(city) == normalize_text(target):
        return None
    # Offre multi-sites ('Saint-Étienne / Lyon, France') : la ville cible citée suffit.
    if re.search(rf"\b{re.escape(normalize_text(target))}\b", text):
        return None
    offer_commune = await resolve_commune(city, client)
    target_commune = await resolve_commune(target, client)
    if not offer_commune or not target_commune:
        return None
    distance = haversine_km(
        (offer_commune["lon"], offer_commune["lat"]), (target_commune["lon"], target_commune["lat"])
    )
    if distance > radius_km:
        return f"{city} à {distance:.0f} km de {target} (rayon {radius_km} km)"
    return None


async def filter_offers_by_location(offers: list[dict], target_city: Optional[str]) -> list[dict]:
    """Écarte les offres hors zone ; chaque rejet est journalisé avec sa raison."""
    kept = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for offer in offers:
            reason = await location_rejection_reason(
                offer.get("localisation"), offer.get("url") or offer.get("source_url"), target_city, client
            )
            if reason:
                logger.warning(f"🌍 Offre hors zone écartée: {offer.get('poste')} ({offer.get('url')}) — {reason}")
            else:
                kept.append(offer)
    return kept
