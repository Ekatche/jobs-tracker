"""Backfill de `canonical_title` sur les offres déjà en base MongoDB.

Recalcule canonical_title via normalize_role() pour chaque offre existante,
en s'appuyant sur la taxonomie role_aliases enrichie (ROME + ESCO). N'effectue
aucun appel de collecte web/LLM : lecture + normalisation + écriture DB only.

Usage:
    docker exec jobtracker-backend python scripts/backfill_canonical_titles.py --dry-run
    docker exec jobtracker-backend python scripts/backfill_canonical_titles.py
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import get_database
from app.services.role_normalizer import (
    EMBEDDING_MODEL,
    ROLE_SIMILARITY_THRESHOLD,
    cosine_similarity,
    normalize_role,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def peek_normalize_role(role: str, collection) -> str:
    """Version lecture seule de normalize_role(): prédit le canonical_title
    sans écrire dans role_aliases (ni nouveau canonical, ni addToSet de variant).
    """
    role_clean = role.strip() if role else ""
    if not role_clean:
        return ""

    role_variant = role_clean.lower()

    existing = await collection.find_one({"variants": role_variant})
    if existing and existing.get("canonical"):
        return existing["canonical"]

    from litellm import aembedding

    resp = await aembedding(model=EMBEDDING_MODEL, input=[role_clean])
    item = resp.data[0] if hasattr(resp, "data") else resp["data"][0]
    embedding = (
        item.get("embedding")
        if isinstance(item, dict)
        else getattr(item, "embedding", item["embedding"])
    )

    aliases = await collection.find({}).to_list(length=200)
    best_alias = None
    best_score = -1.0
    for alias in aliases:
        cand_emb = alias.get("embedding")
        if not cand_emb:
            continue
        score = cosine_similarity(embedding, cand_emb)
        if score > best_score:
            best_score = score
            best_alias = alias

    if best_alias is not None and best_score >= ROLE_SIMILARITY_THRESHOLD:
        return best_alias.get("canonical", role_clean)

    return role_clean


async def backfill_canonical_titles(dry_run: bool) -> None:
    db = await get_database()
    collection = db["job_offers"]
    role_aliases_collection = db["role_aliases"]

    total_count = await collection.count_documents({"is_deleted": {"$ne": True}})
    logger.info(f"🔍 Analyse de {total_count} offres actives...")

    cursor = collection.find({"is_deleted": {"$ne": True}})
    changed_count = 0
    unchanged_count = 0
    empty_poste_count = 0

    async for doc in cursor:
        doc_id = doc.get("_id")
        poste = doc.get("poste", "")
        if not poste:
            empty_poste_count += 1
            continue

        old_canonical = doc.get("canonical_title")
        if dry_run:
            new_canonical = await peek_normalize_role(poste, role_aliases_collection)
        else:
            new_canonical = await normalize_role(poste, db=db)

        if new_canonical != old_canonical:
            changed_count += 1
            logger.info(
                f"🔁 [{doc_id}] '{poste}': canonical_title '{old_canonical}' -> '{new_canonical}'"
            )
            if not dry_run:
                await collection.update_one(
                    {"_id": doc_id}, {"$set": {"canonical_title": new_canonical}}
                )
        else:
            unchanged_count += 1

    mode = "DRY-RUN (aucune écriture)" if dry_run else "RUN RÉEL"
    logger.info(
        f"✅ Backfill terminé [{mode}] !\n"
        f"  - Total d'offres analysées : {total_count}\n"
        f"  - canonical_title modifié : {changed_count}\n"
        f"  - canonical_title inchangé : {unchanged_count}\n"
        f"  - Offres sans poste : {empty_poste_count}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche les changements sans écrire en base",
    )
    args = parser.parse_args()
    asyncio.run(backfill_canonical_titles(dry_run=args.dry_run))
