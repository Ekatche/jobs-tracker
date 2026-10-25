"""Rattrapage de `sector` et `company_size` sur les offres déjà en base.

Sans `--apply` : estimation seule, à partir de `raw_data` et du cache `company_profiles`.
Aucun appel externe (API Recherche d'entreprises, LLM), aucune écriture.
Avec `--apply` : CompanyResolver sur chaque offre ciblée, sans plafond d'appels LLM ni échéance
(`--limit N` borne le nombre d'offres traitées).

Usage:
    docker exec jobtracker-backend python scripts/backfill_company_attributes.py
    docker exec jobtracker-backend python scripts/backfill_company_attributes.py --apply --limit 200
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import get_database
from app.services.company_profiles import CompanyResolver, extract_native_attributes, is_placeholder_company
from app.services.normalization import normalize_company

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Coût observé d'un appel gpt-5-nano de déduction secteur/taille
LLM_COST_PER_COMPANY_USD = 0.0006
# (champ de l'offre et du profil, champ de source du profil)
_ATTRIBUTES = (("sector", "sector_source"), ("company_size", "size_source"))


def estimate_backfill(offers: list[dict], profiles_by_name: dict[str, dict]) -> dict:
    """Compteurs du rattrapage, sans appel externe.

    `max_llm_calls` est une borne haute : l'API Recherche d'entreprises peut encore fournir la taille.
    """
    resolved_natively = 0
    resolved_from_cache = 0
    # Par entreprise : champs encore à trouver, et valeurs natives mises en commun sur toutes ses offres
    needed: dict[str, set] = {}
    pooled_native: dict[str, set] = {}

    for offer in offers:
        native = extract_native_attributes(offer.get("raw_data"))
        missing = [field for field, _ in _ATTRIBUTES if not offer.get(field)]
        remaining = [field for field in missing if not native[field]]
        if not remaining:
            resolved_natively += 1
            continue
        company = offer.get("entreprise")
        if is_placeholder_company(company):
            continue
        name = normalize_company(company)
        profile = profiles_by_name.get(name) or {}
        if all(profile.get(field) for field in remaining):
            resolved_from_cache += 1
        needed.setdefault(name, set()).update(remaining)

    for offer in offers:
        company = offer.get("entreprise")
        if is_placeholder_company(company):
            continue
        native = extract_native_attributes(offer.get("raw_data"))
        name = normalize_company(company)
        pooled_native.setdefault(name, set()).update(field for field, _ in _ATTRIBUTES if native[field])

    max_llm_calls = 0
    sources = dict(_ATTRIBUTES)
    for name, fields in needed.items():
        profile = profiles_by_name.get(name) or {}
        if any(
            field not in pooled_native[name] and not profile.get(field) and not profile.get(sources[field])
            for field in fields
        ):
            max_llm_calls += 1

    return {
        "offers": len(offers),
        "companies": len(pooled_native),
        "resolved_natively": resolved_natively,
        "resolved_from_cache": resolved_from_cache,
        "max_llm_calls": max_llm_calls,
        "estimated_cost_usd": round(max_llm_calls * LLM_COST_PER_COMPANY_USD, 4),
    }


async def backfill(apply: bool, limit: Optional[int] = None) -> dict:
    db = await get_database()
    collection = db["job_offers"]
    query = {"is_deleted": {"$ne": True}, "$or": [{"sector": None}, {"company_size": None}]}
    projection = {"entreprise": 1, "poste": 1, "description": 1, "raw_data": 1, "sector": 1, "company_size": 1}
    cursor = collection.find(query, projection)
    if limit:
        cursor = cursor.limit(limit)
    offers = await cursor.to_list(None)

    if not apply:
        names = {normalize_company(o.get("entreprise")) for o in offers if not is_placeholder_company(o.get("entreprise"))}
        profiles = await db["company_profiles"].find({"company_name_normalized": {"$in": list(names)}}).to_list(None)
        stats = estimate_backfill(offers, {p["company_name_normalized"]: p for p in profiles})
        logger.info(
            "Estimation (aucune écriture, aucun appel externe) :\n"
            + "\n".join(f"  - {key} : {value}" for key, value in stats.items())
        )
        return stats

    resolver = CompanyResolver(db, max_llm_calls=None, time_budget_seconds=None)
    updated = 0
    for offer in offers:
        before = {field: offer.get(field) for field, _ in _ATTRIBUTES}
        try:
            await resolver.resolve(offer)
        except Exception as e:
            logger.warning(f"⚠️ Offre {offer.get('_id')} ('{offer.get('entreprise')}') non résolue : {e}")
            continue
        changes = {field: offer[field] for field, _ in _ATTRIBUTES if not before[field] and offer.get(field)}
        if changes:
            await collection.update_one({"_id": offer["_id"]}, {"$set": changes})
            updated += 1

    stats = {"offers": len(offers), "updated": updated, "llm_calls": resolver.llm_calls}
    logger.info(
        f"✅ Rattrapage terminé : {updated} offres mises à jour sur {len(offers)}, {resolver.llm_calls} appels LLM"
    )
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Résout et écrit en base (appels API et LLM)")
    parser.add_argument("--limit", type=int, default=None, help="Nombre maximal d'offres traitées")
    args = parser.parse_args()
    asyncio.run(backfill(apply=args.apply, limit=args.limit))
