#!/usr/bin/env python3
"""
Purge des offres hors zone géographique.

Usage:
    python scripts/purge_out_of_zone_offers.py [--delete] [--radius KM]

Options:
    --delete    Supprime réellement les offres listées (sinon mode audit).
    --radius    Rayon maximal en km autour de la ville cible (défaut : 50).

Comportement :
- Récupère toutes les offres actives de la collection job_offers.
- Pour chaque offre, applique le filtre géo (même logique que le pipeline).
  La ville cible est extraite du champ `source_query` via parse_source_query.
  Si absent, on skip (on ne supprime pas sans ville de référence).
- Liste chaque offre hors zone avec sa raison.
- Sans --delete, mode audit : affiche seulement.
- Avec --delete : supprime les offres non liées à une candidature ;
  expire (deleted_at) celles qui ont une candidature associée.
- L'offre Workday 6ab1570d1ed0f89eb7fd7804 (Workday fr-CA) est incluse dans le scan.
"""

import argparse
import asyncio
import logging
import os
import sys

# --- path setup (run from backend/) ---
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from bson import ObjectId
from datetime import datetime, timezone

from app.database import get_database
from app.services.sources.geo import location_rejection_reason
from app.services.relevance import parse_source_query

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("purge_geo")


async def is_referenced(offer_id, db) -> bool:
    """Renvoie True si l'offre est liée à une candidature."""
    try:
        obj_id = ObjectId(offer_id) if ObjectId.is_valid(str(offer_id)) else None
        query: dict = {"$or": [{"offer_id": str(offer_id)}]}
        if obj_id:
            query["$or"].append({"offer_id": obj_id})
        return await db["applications"].find_one(query) is not None
    except Exception:
        return True  # fail-safe: ne pas supprimer si incertain


async def run(delete: bool, radius_km: int) -> None:
    db = await get_database()
    collection = db["job_offers"]

    # Offres non supprimées
    offers = await collection.find(
        {"$or": [{"deleted_at": {"$exists": False}}, {"deleted_at": None}]}
    ).to_list(length=None)

    logger.info(f"🔍 {len(offers)} offres actives à analyser (rayon {radius_km} km)")

    to_delete: list[dict] = []
    to_expire: list[dict] = []
    skipped_no_city = 0

    async with httpx.AsyncClient(timeout=10.0) as client:
        for offer in offers:
            source_query = offer.get("source_query") or ""
            _, target_city = parse_source_query(source_query) if source_query else (None, None)

            if not target_city:
                skipped_no_city += 1
                continue  # Pas de ville de référence : on ne peut pas décider

            reason = await location_rejection_reason(
                localisation=offer.get("localisation"),
                url=offer.get("url") or offer.get("source_url"),
                target_city=target_city,
                client=client,
                radius_km=radius_km,
            )

            if reason:
                entry = {
                    "_id": str(offer["_id"]),
                    "poste": offer.get("poste", "?"),
                    "entreprise": offer.get("entreprise", "?"),
                    "localisation": offer.get("localisation", "?"),
                    "url": offer.get("url") or offer.get("source_url"),
                    "source_query": source_query,
                    "reason": reason,
                }
                referenced = await is_referenced(offer["_id"], db)
                if referenced:
                    to_expire.append(entry)
                else:
                    to_delete.append(entry)

    total = len(to_delete) + len(to_expire)
    logger.info(
        f"📊 Résultat : {total} offres hors zone ({len(to_delete)} à supprimer, "
        f"{len(to_expire)} à expirer, {skipped_no_city} skippées sans ville)"
    )

    # ── Affichage ──────────────────────────────────────────────────────
    if to_delete:
        print("\n🗑️  À SUPPRIMER (pas de candidature liée) :")
        for o in to_delete:
            print(f"  [{o['_id']}] {o['poste']} @ {o['entreprise']} — {o['localisation']} | {o['reason']}")

    if to_expire:
        print("\n📦 À EXPIRER (candidature liée, soft-delete) :")
        for o in to_expire:
            print(f"  [{o['_id']}] {o['poste']} @ {o['entreprise']} — {o['localisation']} | {o['reason']}")

    if total == 0:
        print("✅ Aucune offre hors zone détectée.")
        return

    # ── Suppression (uniquement avec --delete) ─────────────────────────
    if not delete:
        print(f"\nℹ️  Mode audit. Relancez avec --delete pour appliquer ({total} offres).")
        return

    confirm = input(f"\n⚠️  Confirmer la suppression / expiration de {total} offres ? [oui/non] ").strip().lower()
    if confirm not in {"oui", "o", "yes", "y"}:
        print("Annulé.")
        return

    now = datetime.now(timezone.utc)
    deleted_count = 0
    expired_count = 0

    if to_delete:
        ids = [ObjectId(o["_id"]) for o in to_delete if ObjectId.is_valid(o["_id"])]
        if ids:
            res = await collection.delete_many({"_id": {"$in": ids}})
            deleted_count = res.deleted_count

    for o in to_expire:
        if ObjectId.is_valid(o["_id"]):
            await collection.update_one(
                {"_id": ObjectId(o["_id"])},
                {"$set": {"deleted_at": now, "out_of_zone": True}},
            )
            expired_count += 1

    logger.info(f"✅ Terminé : {deleted_count} supprimées, {expired_count} expirées.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Purge des offres hors zone géographique.")
    parser.add_argument("--delete", action="store_true", help="Applique la suppression (défaut : audit)")
    parser.add_argument("--radius", type=int, default=50, help="Rayon géo en km (défaut : 50)")
    args = parser.parse_args()
    asyncio.run(run(delete=args.delete, radius_km=args.radius))


if __name__ == "__main__":
    main()
