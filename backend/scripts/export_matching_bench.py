# backend/scripts/export_matching_bench.py
"""Export en lecture seule des données du banc de mesure du matching.

Spec matching hybride, §6 (étape 1b). Lit les profils actifs (au moins une
interaction `applied` ou `hidden` et un profil candidat), leurs interactions,
un échantillon d'offres commun à tous les profils et les comptages de
republication que lit le Two-Pass. N'écrit rien en base.

Le fichier produit contient des données personnelles : il reste dans
`scripts/data/`, ignoré par git.

Usage:
    docker exec jobtracker-backend python scripts/export_matching_bench.py
    docker exec jobtracker-backend python scripts/export_matching_bench.py --out scripts/data/matching_bench/export_local.json
    # Prod, sans déployer le script (lu sur stdin) :
    ssh sentinel-vps 'docker exec -i jobtracker-backend python - --out /tmp/matching_bench_export.json' < backend/scripts/export_matching_bench.py
"""

import argparse
import asyncio
import logging
import random
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bson import ObjectId, json_util

from app.database import get_database

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

INTERACTION_STATUSES = ("applied", "hidden")
SEED = 20261024
DEFAULT_OUT = "scripts/data/matching_bench/export.json"


def select_sample(
    candidates: Iterable[Dict[str, Any]],
    user_ids: List[str],
    excluded_ids: Iterable[str],
    seed: int,
    per_profile: int = 30,
    unmatched: int = 40,
) -> List[str]:
    """Échantillon d'offres commun à tous les profils (§6.1).

    `per_profile` offres rattachées à chaque profil (`matched_user_ids`), dans
    l'ordre de `user_ids`, puis `unmatched` offres rattachées à aucun d'eux. Le
    tirage dépend de la graine, pas de l'ordre de lecture en base. Une réserve
    trop petite est prise en entier.
    """
    excluded = {str(oid) for oid in excluded_ids}
    pool = sorted(
        (str(c["_id"]), set(c.get("matched_user_ids") or []))
        for c in candidates
        if str(c["_id"]) not in excluded
    )
    active = set(user_ids)
    rng = random.Random(seed)
    sample: List[str] = []
    for uid in user_ids:
        taken = set(sample)
        reserve = [oid for oid, matched in pool if uid in matched and oid not in taken]
        sample.extend(rng.sample(reserve, min(per_profile, len(reserve))))
    reserve = [oid for oid, matched in pool if not matched & active]
    sample.extend(rng.sample(reserve, min(unmatched, len(reserve))))
    return sample


def assign_aliases(interaction_counts: Dict[str, int]) -> Dict[str, str]:
    """Alias A, B, … par nombre d'interactions décroissant, puis par user_id."""
    ordered = sorted(interaction_counts, key=lambda uid: (-interaction_counts[uid], uid))
    return {uid: chr(ord("A") + rank) for rank, uid in enumerate(ordered)}


async def build_export(db, user_ids: Optional[List[str]] = None, seed: int = SEED) -> Dict[str, Any]:
    """Construit l'export du banc. Lecture seule."""
    interactions = await db["user_offer_interactions"].find(
        {"status": {"$in": list(INTERACTION_STATUSES)}},
        {"_id": 0, "user_id": 1, "offer_id": 1, "status": 1},
    ).to_list(length=None)
    counts = Counter(str(i["user_id"]) for i in interactions)
    if user_ids:
        counts = Counter({uid: counts.get(uid, 0) for uid in user_ids})

    id_values: List[Any] = list(counts) + [ObjectId(uid) for uid in counts if ObjectId.is_valid(uid)]
    profile_docs = await db["candidate_profile"].find({"user_id": {"$in": id_values}}).to_list(length=None)
    profiles = {str(p["user_id"]): p for p in profile_docs}
    for uid in counts:
        if uid not in profiles:
            logger.warning(f"⚠️ {counts[uid]} interactions sans profil candidat : utilisateur ignoré")

    aliases = assign_aliases({uid: counts[uid] for uid in profiles})
    ordered_uids = sorted(aliases, key=aliases.get)
    kept = sorted(
        (
            {"alias": aliases[str(i["user_id"])], "offer_id": str(i["offer_id"]), "status": i["status"]}
            for i in interactions
            if str(i["user_id"]) in aliases
        ),
        key=lambda i: (i["alias"], i["offer_id"]),
    )

    candidates = await db["job_offers"].find(
        {
            "is_deleted": {"$ne": True},
            "pipeline_stage": {"$ne": "expired"},
            "$or": [{"description": {"$regex": r"\S"}}, {"competences_cles.0": {"$exists": True}}],
        },
        {"matched_user_ids": 1},
    ).to_list(length=None)
    sample_ids = select_sample(candidates, ordered_uids, {i["offer_id"] for i in kept}, seed)

    wanted = list(dict.fromkeys(sample_ids + [i["offer_id"] for i in kept]))
    offers = await db["job_offers"].find(
        {"_id": {"$in": [ObjectId(oid) for oid in wanted if ObjectId.is_valid(oid)]}}
    ).to_list(length=None)
    found = {str(o["_id"]) for o in offers}
    missing = sorted({i["offer_id"] for i in kept} - found)

    # Même filtre que `compute_offer_evaluation` (bloc G, republications).
    publication_counts: Dict[str, int] = {}
    for offer in offers:
        company = (offer.get("entreprise") or "").strip()
        if company and offer.get("canonical_title"):
            publication_counts[str(offer["_id"])] = await db["job_offers"].count_documents(
                {
                    "entreprise": {"$regex": f"^{re.escape(company)}$", "$options": "i"},
                    "canonical_title": offer["canonical_title"],
                }
            )

    sample_set = set(sample_ids)
    for uid in ordered_uids:
        alias = aliases[uid]
        statuses = Counter(i["status"] for i in kept if i["alias"] == alias)
        matched = sum(1 for o in offers if str(o["_id"]) in sample_set and uid in (o.get("matched_user_ids") or []))
        logger.info(
            f"👤 Profil {alias} : {statuses.get('applied', 0)} applied, {statuses.get('hidden', 0)} hidden, "
            f"{matched} offres rattachées dans l'échantillon"
        )
    logger.info(
        f"📦 {len(candidates)} offres candidates, échantillon de {len(sample_ids)}, "
        f"{len(kept)} interactions dont {len(missing)} sur une offre introuvable"
    )

    return {
        "exported_at": datetime.now(timezone.utc),
        "seed": seed,
        "profiles": [{"alias": aliases[uid], "user_id": uid, "profile": profiles[uid]} for uid in ordered_uids],
        "sample_offer_ids": sample_ids,
        "interactions": kept,
        "offers": offers,
        "publication_counts": publication_counts,
        "missing_interaction_offer_ids": missing,
    }


async def export_matching_bench(out: Path, user_ids: Optional[List[str]], seed: int) -> None:
    db = await get_database()
    export = await build_export(db, user_ids, seed)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json_util.dumps(export, ensure_ascii=False), encoding="utf-8")
    logger.info(f"✅ Export écrit dans {out} ({len(export['profiles'])} profils)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path(DEFAULT_OUT), help="Fichier JSON produit")
    parser.add_argument(
        "--user-id",
        action="append",
        dest="user_ids",
        help="Profil à inclure (répétable) ; par défaut, tous les profils ayant une interaction applied ou hidden",
    )
    parser.add_argument("--seed", type=int, default=SEED, help="Graine du tirage de l'échantillon")
    args = parser.parse_args()
    asyncio.run(export_matching_bench(args.out, args.user_ids, args.seed))
