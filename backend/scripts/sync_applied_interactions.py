# backend/scripts/sync_applied_interactions.py
"""Synchronise le statut d'interaction 'applied' et 'seen' dans user_offer_interactions
pour toutes les candidatures existantes qui disposent d'un offer_id.

Usage:
    docker exec jobtracker-backend python scripts/sync_applied_interactions.py --dry-run
    docker exec jobtracker-backend python scripts/sync_applied_interactions.py
"""

import argparse
import asyncio
from datetime import datetime, timezone
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import get_database

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def sync_applied_interactions(dry_run: bool) -> None:
    db = await get_database()

    query = {"offer_id": {"$exists": True, "$ne": None}}
    apps = await db["applications"].find(query).to_list(length=None)
    logger.info(f"Trouvé {len(apps)} candidatures avec un offer_id.")

    now = datetime.now(timezone.utc)
    updated_count = 0

    for app in apps:
        user_id = str(app.get("user_id"))
        offer_id = str(app.get("offer_id"))
        company = app.get("company", "Entreprise")
        position = app.get("position", "Poste")

        if not user_id or not offer_id:
            continue

        logger.info(f"  - App {app.get('_id')}: {company} | {position} -> offer_id={offer_id}, user_id={user_id}")

        if not dry_run:
            await db["user_offer_interactions"].update_one(
                {
                    "user_id": user_id,
                    "offer_id": offer_id,
                },
                {
                    "$set": {
                        "status": "applied",
                        "seen": True,
                        "updated_at": now,
                    },
                    "$setOnInsert": {
                        "created_at": now,
                        "notes": None,
                    },
                },
                upsert=True,
            )
        updated_count += 1

    mode_str = "[DRY-RUN] " if dry_run else ""
    logger.info(f"✅ {mode_str}Synchronisation terminée : {updated_count} interactions 'applied' traitées.")


def main():
    parser = argparse.ArgumentParser(description="Synchronise les interactions 'applied' depuis les candidatures.")
    parser.add_argument("--dry-run", action="store_true", help="Simule l'exécution sans écrire en base")
    args = parser.parse_args()

    asyncio.run(sync_applied_interactions(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
