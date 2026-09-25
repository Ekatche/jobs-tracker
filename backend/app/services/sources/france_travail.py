"""Source France Travail : API officielle Offres d'emploi v2 (francetravail.io).

Nécessite FRANCE_TRAVAIL_CLIENT_ID / FRANCE_TRAVAIL_CLIENT_SECRET (application
abonnée à l'API « Offres d'emploi v2 ») ; sans eux la source est ignorée.
"""

import logging
import os
import re
from typing import Optional

import httpx

from app.services.sources.geo import ARRONDISSEMENT_CODES, GEO_RADIUS_KM, clean_city_label, resolve_commune

logger = logging.getLogger(__name__)

FT_TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
FT_SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
FT_OFFER_URL = "https://candidat.francetravail.fr/offres/recherche/detail/{id}"
FT_SCOPE = "api_offresdemploiv2 o2dsoffre"
FT_PUBLISHED_SINCE_DAYS = 14
FT_MAX_RESULTS = 50

# Contrat normalisé (offer_fit.normalize_contract) -> code typeContrat de l'API.
FT_CONTRACT_CODES = {"cdi": "CDI", "cdd": "CDD", "interim": "MIS", "freelance": "LIB"}

# motsCles n'accepte que lettres, chiffres, espace et @#$%^&+./- (400 sinon).
_FORBIDDEN_KEYWORD_CHARS = re.compile(r"[^\w\s@#$%^&+./-]")


def france_travail_configured() -> bool:
    return bool(os.getenv("FRANCE_TRAVAIL_CLIENT_ID") and os.getenv("FRANCE_TRAVAIL_CLIENT_SECRET"))


async def _get_token(client: httpx.AsyncClient) -> str:
    resp = await client.post(
        FT_TOKEN_URL,
        params={"realm": "/partenaire"},
        data={
            "grant_type": "client_credentials",
            "client_id": os.environ["FRANCE_TRAVAIL_CLIENT_ID"],
            "client_secret": os.environ["FRANCE_TRAVAIL_CLIENT_SECRET"],
            "scope": FT_SCOPE,
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def map_france_travail_offer(item: dict) -> dict:
    lieu = item.get("lieuTravail") or {}
    salaire = (item.get("salaire") or {}).get("libelle")
    offer_url = FT_OFFER_URL.format(id=item["id"])
    return {
        "poste": item.get("intitule") or "",
        "entreprise": (item.get("entreprise") or {}).get("nom") or "Entreprise anonyme (France Travail)",
        "description": item.get("description") or "",
        "localisation": clean_city_label(lieu.get("libelle") or ""),
        "date": (item.get("dateCreation") or "")[:10],
        "type_contrat": item.get("typeContratLibelle") or item.get("typeContrat") or "",
        "salaire": salaire or "",
        "mode_travail": "",
        "competences_cles": [c["libelle"] for c in item.get("competences") or [] if c.get("libelle")],
        "url": offer_url,
        "source_url": offer_url,
        "ats_platform": "france_travail",
    }


async def fetch_france_travail_offers(
    role: str, city: Optional[str], contract: Optional[str], client: httpx.AsyncClient
) -> list[dict]:
    if not france_travail_configured():
        logger.info("ℹ️ France Travail non configuré (FRANCE_TRAVAIL_CLIENT_ID/SECRET absents), source ignorée")
        return []

    params = {
        "motsCles": _FORBIDDEN_KEYWORD_CHARS.sub(" ", role).strip(),
        "publieeDepuis": FT_PUBLISHED_SINCE_DAYS,
        "sort": 1,
        "range": f"0-{FT_MAX_RESULTS - 1}",
    }
    if city:
        commune = await resolve_commune(clean_city_label(city), client)
        if commune:
            params["commune"] = ARRONDISSEMENT_CODES.get(commune["code"], commune["code"])
            params["distance"] = GEO_RADIUS_KM
        else:
            logger.warning(f"⚠️ France Travail : commune '{city}' non résolue, recherche nationale")
    if contract in FT_CONTRACT_CODES:
        params["typeContrat"] = FT_CONTRACT_CODES[contract]

    token = await _get_token(client)
    resp = await client.get(FT_SEARCH_URL, params=params, headers={"Authorization": f"Bearer {token}"})
    if resp.status_code == 204:
        return []
    resp.raise_for_status()
    return [map_france_travail_offer(item) for item in resp.json().get("resultats", [])]
