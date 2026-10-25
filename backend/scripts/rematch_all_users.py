# backend/scripts/rematch_all_users.py
"""Recalcule le rattachement (score hybride, Task 6) de tous les profils contre
le stock d'offres actif.

Sans `--apply` : aucune écriture (ni `job_offers`, ni `offer_relevance`, ni le
cache `offer_embeddings` — `rematch_user(..., apply=False)` propage
`cache=False` à `get_offer_vectors`). Affiche d'abord le nombre d'offres sans
vecteur en cache et le coût estimé de leur embarquement (même formule que
`scripts/matching_bench.py` `run_embed`), puis, par utilisateur (identifiant
tronqué, jamais de texte de profil) : `attached`, `detached`, `kept_by_guard`,
`levels`, et les offres conservées sous FLOOR par la garde d'interaction.

Usage:
    docker exec jobtracker-backend python scripts/rematch_all_users.py
    docker exec jobtracker-backend python scripts/rematch_all_users.py --apply
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import get_database
from app.services.offer_profile_matcher import rematch_user
from app.services.offer_scoring.constants import EMBEDDING_MODEL
from app.services.offer_scoring.embeddings import offer_embedding_text, text_hash

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def _estimate_embedding_cost(db, offers: list, *, apply: bool, profile_count: int) -> None:
    """Affiche le nombre d'offres sans vecteur en cache et le coût estimé de leur
    embarquement, avant tout rematch (même formule que `matching_bench.py run_embed`).

    En dry-run, `rematch_user(..., apply=False)` ne persiste jamais le cache
    `offer_embeddings` (cf. docstring module) : chaque profil réembarque donc
    les mêmes offres manquantes. Le coût affiché ici est celui d'UNE passe —
    le coût réel d'un dry-run complet est ce montant multiplié par le nombre
    de profils, affiché séparément pour ne pas sous-estimer la facture."""
    offer_texts = {}
    for offer in offers:
        text = offer_embedding_text(offer)
        if text is not None:
            offer_texts[str(offer["_id"])] = text

    if not offer_texts:
        logger.info("🧮 Aucune offre embarquable (ni intitulé ni description) dans le stock actif.")
        return

    offer_ids = list(offer_texts.keys())
    cached_hashes = {}
    async for doc in db["offer_embeddings"].find({"offer_id": {"$in": offer_ids}, "model": EMBEDDING_MODEL}):
        cached_hashes[doc["offer_id"]] = doc.get("text_hash")

    missing_chars = 0
    missing_count = 0
    for offer_id, text in offer_texts.items():
        if cached_hashes.get(offer_id) != text_hash(text):
            missing_chars += len(text)
            missing_count += 1

    cost_per_pass = (missing_chars / 4) / 1_000_000 * 0.1
    if apply:
        logger.info(
            f"🧮 Embeddings offres {EMBEDDING_MODEL} : {missing_count} offre(s) sans vecteur en cache sur "
            f"{len(offer_texts)}, coût estimé {cost_per_pass:.4f} $ (cache écrit après la 1ère passe)."
        )
    else:
        estimated_total = cost_per_pass * profile_count
        logger.info(
            f"🧮 Embeddings offres {EMBEDDING_MODEL} : {missing_count} offre(s) sans vecteur en cache sur "
            f"{len(offer_texts)}, coût par passe {cost_per_pass:.4f} $ — DRY-RUN n'écrit pas le cache "
            f"offer_embeddings, donc les {missing_count} offre(s) sont réembarquées à chaque profil : "
            f"{profile_count} profil(s) × {cost_per_pass:.4f} $ ≈ {estimated_total:.4f} $ au total estimé."
        )


async def rematch_all_users(apply: bool) -> None:
    db = await get_database()

    profiles = await db["candidate_profile"].find({}).to_list(length=None)
    offers = await db["job_offers"].find({"is_deleted": {"$ne": True}}).to_list(length=None)

    await _estimate_embedding_cost(db, offers, apply=apply, profile_count=len(profiles))

    mode = "RUN RÉEL (écriture)" if apply else "DRY-RUN (aucune écriture)"
    logger.info(f"🔍 {len(profiles)} profil(s) candidat(s), {len(offers)} offre(s) active(s) [{mode}]")

    for profile in profiles:
        user_id = str(profile["user_id"])
        summary = await rematch_user(user_id, db, apply=apply)
        truncated = user_id[:8]
        logger.info(
            f"  - user {truncated}… : attached={summary.attached} detached={summary.detached} "
            f"kept_by_guard={summary.kept_by_guard} levels={summary.levels}"
        )
        if summary.applied_below_floor:
            logger.info(
                f"    ⚠️ offres sous FLOOR conservées (garde interaction) pour {truncated}… : "
                f"{summary.applied_below_floor}"
            )

    logger.info(f"✅ Rematch terminé [{mode}].")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Écrit réellement les changements (job_offers, offer_relevance, cache offer_embeddings). "
        "Sans ce flag : dry-run, aucune écriture.",
    )
    args = parser.parse_args()
    asyncio.run(rematch_all_users(apply=args.apply))
