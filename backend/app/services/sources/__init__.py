"""Sources d'offres structurées (API / scraping ciblé), en complément de la recherche Tavily.

Produit des offres brutes au format du crawler (poste, entreprise, description,
localisation, url…) : déjà en base, hors métier ou hors zone sont écartées
avant tout appel LLM de résumé.
"""

import asyncio
import logging
import re
from typing import Optional

import httpx

from app.services.evaluation.domain_relevance import EMBEDDING_MODEL, expand_title_acronyms
from app.services.evaluation.offer_fit import normalize_contract
from app.services.relevance import parse_source_query
from app.services.role_normalizer import cosine_similarity
from app.services.sources.france_travail import fetch_france_travail_offers
from app.services.sources.geo import filter_offers_by_location
from app.services.sources.jobboards import fetch_jobboard_offers

logger = logging.getLogger(__name__)

# Similarité rôle recherché / intitulé, mesurée le 2026-09-25 sur des résultats réels :
# « Data Scientist » vs Data Analyst 0.52-0.59, Ingénieur Data & IA 0.51, Lead Tech Data 0.41,
# Développeur Java 0.30, Comptable 0.16 ; « Animatrice permanente » vs animation 0.69, reste < 0.32.
TITLE_RELEVANCE_THRESHOLD = 0.40

_LINKEDIN_JOB_ID = re.compile(r"linkedin\.com/jobs/view/(?:[^/?#]*-)?(\d{6,})")
_QUERY_CONTRACT = re.compile(r"\(([^)]*)\)\s*$")


def offer_identity(url: str) -> str:
    """Clé stable d'une offre : identifiant LinkedIn (l'URL varie selon le slug et le sous-domaine) ou URL."""
    match = _LINKEDIN_JOB_ID.search(url or "")
    return f"linkedin:{match.group(1)}" if match else (url or "").strip()


def parse_query_contract(query: str) -> Optional[str]:
    match = _QUERY_CONTRACT.search(query or "")
    return normalize_contract(match.group(1)) if match else None


async def drop_known_offers(
    offers: list[dict], db, extra_known: Optional[set[str]] = None
) -> list[dict]:
    """Retire les offres déjà en base, y compris supprimées (bruit déjà trié), ou dans extra_known."""
    urls = [o["url"] for o in offers if o.get("url")]
    if not urls:
        return []

    linkedin_ids = [key.split(":", 1)[1] for key in map(offer_identity, urls) if key.startswith("linkedin:")]
    conditions: list[dict] = [{"url": {"$in": urls}}, {"alternative_urls": {"$in": urls}}]
    if linkedin_ids:
        conditions.append({"url": {"$regex": rf"linkedin\.com/jobs/view/(?:[^/?#]*-)?(?:{'|'.join(linkedin_ids)})(?:[/?#]|$)"}})

    known: set[str] = set(extra_known) if extra_known else set()
    if db is not None:
        try:
            collection = db.get("job_offers") if isinstance(db, dict) else db["job_offers"]
            if collection is not None:
                async for doc in collection.find({"$or": conditions}, {"url": 1, "alternative_urls": 1}):
                    for url in [doc.get("url")] + list(doc.get("alternative_urls") or []):
                        if url:
                            known.add(offer_identity(url))
        except Exception as e:
            logger.warning(f"⚠️ Contrôle des offres déjà en base impossible: {e}")

    seen: set[str] = set()
    fresh = []
    for offer in offers:
        key = offer_identity(offer.get("url"))
        if key and key not in known and key not in seen:
            seen.add(key)
            fresh.append(offer)
    return fresh


async def drop_known_urls(
    urls: list[str], db, extra_known: Optional[set[str]] = None
) -> list[str]:
    """Retire les URLs déjà en base ou déjà couvertes par une identité connue."""
    stubs = [{"url": u} for u in urls if u]
    kept = await drop_known_offers(stubs, db, extra_known=extra_known)
    return [s["url"] for s in kept]


async def keep_relevant_titles(role: str, offers: list[dict]) -> list[dict]:
    """Garde les intitulés proches du rôle recherché. Fail-open si l'embedding échoue."""
    if not offers:
        return offers
    try:
        from litellm import aembedding

        resp = await aembedding(
            model=EMBEDDING_MODEL, input=[role] + [expand_title_acronyms(o["poste"]) or "?" for o in offers]
        )
        data = resp.data if hasattr(resp, "data") else resp["data"]
        vectors = [item["embedding"] if isinstance(item, dict) else item.embedding for item in data]
    except Exception as e:
        logger.warning(f"⚠️ Filtre de pertinence indisponible pour '{role}': {e}, offres conservées")
        return offers

    kept = []
    for offer, vector in zip(offers, vectors[1:]):
        score = cosine_similarity(vectors[0], vector)
        if score >= TITLE_RELEVANCE_THRESHOLD:
            kept.append(offer)
        else:
            logger.info(f"🚫 Hors métier ({score:.2f} < {TITLE_RELEVANCE_THRESHOLD}): {offer['poste']} — {offer['url']}")
    return kept


async def collect_structured_offers(query: str, db) -> list[dict]:
    """Offres France Travail, Indeed et LinkedIn pour une requête de collecte, filtrées.

    Ne lève jamais : une source en échec est journalisée et ignorée.
    """
    role, city = parse_source_query(query)
    if not role:
        logger.info(f"ℹ️ Requête hors format, sources structurées ignorées: '{query}'")
        return []
    contract = parse_query_contract(query)

    async with httpx.AsyncClient(timeout=20.0) as client:
        results = await asyncio.gather(
            fetch_france_travail_offers(role, city, contract, client),
            fetch_jobboard_offers(role, city, contract),
            return_exceptions=True,
        )
    offers: list[dict] = []
    for name, result in zip(("France Travail", "Indeed/LinkedIn"), results):
        if isinstance(result, Exception):
            logger.warning(f"⚠️ Source {name} en échec pour '{query}': {result}")
        else:
            offers.extend(o for o in result if o.get("poste") and o.get("url"))

    total = len(offers)
    try:
        offers = await drop_known_offers(offers, db)
    except Exception as e:
        logger.warning(f"⚠️ Contrôle des offres déjà connues impossible: {e}")
    known = total - len(offers)
    offers = await keep_relevant_titles(role, offers)
    offers = await filter_offers_by_location(offers, city)
    logger.info(
        f"📦 Sources structurées '{query}': {total} offres, {known} déjà connues, {len(offers)} retenues"
    )
    return offers
