# backend/scripts/backfill_matched_user_ids.py
"""Backfill de `matched_user_ids` sur les offres déjà en base MongoDB.

Recalcule le matching persistant (canonical_title / localisation normalisés)
pour chaque profil candidat existant, contre tout le stock d'offres actif.
N'effectue aucun appel de collecte web ; peut néanmoins déclencher un appel
d'embedding via normalize_role() pour des rôles pas encore connus de
role_aliases (mode réel uniquement, pas en --dry-run).

Usage:
    docker exec jobtracker-backend python scripts/backfill_matched_user_ids.py --dry-run
    docker exec jobtracker-backend python scripts/backfill_matched_user_ids.py
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import get_database
from app.services.offer_profile_matcher import get_normalized_profile_criteria, offer_matches_criteria

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def backfill_matched_user_ids(dry_run: bool) -> None:
    db = await get_database()

    profiles = await db["candidate_profile"].find({}).to_list(length=None)
    logger.info(f"🔍 {len(profiles)} profils candidats à traiter...")

    offers = await db["job_offers"].find({"is_deleted": {"$ne": True}}).to_list(length=None)
    logger.info(f"🔍 {len(offers)} offres actives en base...")

    total_tagged = 0

    for profile in profiles:
        user_id = str(profile["user_id"])
        prefs = profile.get("preferences") or {}
        normalized_roles, normalized_locations, remote_policy = await get_normalized_profile_criteria(prefs, db)

        matching_ids = [
            offer["_id"]
            for offer in offers
            if offer_matches_criteria(offer, normalized_roles, normalized_locations, remote_policy)
        ]

        logger.info(f"  - user {user_id} : {len(matching_ids)} offres matchées")
        total_tagged += len(matching_ids)

        if not dry_run and matching_ids:
            await db["job_offers"].update_many(
                {"_id": {"$in": matching_ids}},
                {"$addToSet": {"matched_user_ids": user_id}},
            )

    mode = "DRY-RUN (aucune écriture)" if dry_run else "RUN RÉEL"
    logger.info(
        f"✅ Backfill terminé [{mode}] !\n"
        f"  - Profils traités : {len(profiles)}\n"
        f"  - Offres actives analysées : {len(offers)}\n"
        f"  - Associations profil<->offre trouvées : {total_tagged}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche les changements sans écrire en base",
    )
    args = parser.parse_args()
    asyncio.run(backfill_matched_user_ids(dry_run=args.dry_run))
