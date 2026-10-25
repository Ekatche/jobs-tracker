"""Migration de `preferred_industries` (texte libre) vers les clés de la taxonomie secteurs.

Traite `preferences.preferred_industries` et chaque `sources.<clé>.preferences.preferred_industries`
de `candidate_profile`. Valeur déjà dans la taxonomie : gardée. Libellé reconnu (hors `other`) :
remplacé par sa clé. Sinon : gardé tel quel et listé.

Sans `--apply` : imprime avant -> après par profil, aucune écriture.

Usage:
    docker exec jobtracker-backend python scripts/migrate_preferred_industries.py
    docker exec jobtracker-backend python scripts/migrate_preferred_industries.py --apply
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import get_database
from app.services.company_profiles import PREFERENCE_SECTORS, map_sector_label

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def migrate_industry_values(values: list[str]) -> tuple[list[str], list[str]]:
    """(nouvelles valeurs dédoublonnées dans l'ordre, valeurs sans correspondance gardées telles quelles)."""
    migrated: list[str] = []
    unmatched: list[str] = []
    for value in values:
        new_value = value
        if value not in PREFERENCE_SECTORS:
            sector = map_sector_label(value)
            if sector and sector != "other":
                new_value = sector
            elif value not in unmatched:
                unmatched.append(value)
        if new_value not in migrated:
            migrated.append(new_value)
    return migrated, unmatched


def _preference_paths(profile: dict) -> list[tuple[str, dict]]:
    """Chemins Mongo des blocs `preferences` du profil fusionné et de chaque source."""
    paths = [("preferences", profile.get("preferences"))]
    for key, source in (profile.get("sources") or {}).items():
        if isinstance(source, dict):
            paths.append((f"sources.{key}.preferences", source.get("preferences")))
    return [(path, prefs) for path, prefs in paths if isinstance(prefs, dict)]


async def migrate(apply: bool) -> dict:
    db = await get_database()
    collection = db["candidate_profile"]
    profiles = await collection.find({}, {"preferences": 1, "sources": 1}).to_list(None)

    changed = 0
    all_unmatched: set[str] = set()
    for profile in profiles:
        updates = {}
        for path, prefs in _preference_paths(profile):
            values = prefs.get("preferred_industries") or []
            migrated, unmatched = migrate_industry_values(values)
            all_unmatched.update(unmatched)
            if migrated != values:
                updates[f"{path}.preferred_industries"] = migrated
                logger.info(f"Profil {profile['_id']} {path} : {values} -> {migrated}")
            if unmatched:
                logger.info(f"Profil {profile['_id']} {path} : sans correspondance {unmatched}")
        if updates:
            changed += 1
            if apply:
                await collection.update_one({"_id": profile["_id"]}, {"$set": updates})

    stats = {"profiles": len(profiles), "profiles_changed": changed, "unmatched_values": sorted(all_unmatched)}
    mode = "écrits" if apply else "à modifier (aucune écriture)"
    logger.info(f"{'✅' if apply else 'ℹ️'} {changed} profils {mode} sur {len(profiles)} ; sans correspondance : {stats['unmatched_values']}")
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Écrit les valeurs migrées en base")
    args = parser.parse_args()
    asyncio.run(migrate(apply=args.apply))
