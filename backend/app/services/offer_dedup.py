"""Doublons d'offres : recherche à l'insertion et fusion de ceux déjà en base, avec une seule règle
(are_offers_duplicates).

La recherche sert à la collecte et à l'offre créée depuis une candidature ; la fusion sert au script
rétroactif et à l'étape 3 du nettoyage nocturne.
"""
import logging
import re
from datetime import datetime, timezone
from itertools import combinations, product
from typing import Optional

from bson import ObjectId

from app.services.normalization import (
    compute_unique_key,
    company_match_strength,
    are_offers_duplicates,
    merge_multidiffusion_offers,
)

logger = logging.getLogger(__name__)

# Collections dont un document lié rend une offre non supprimable par la fusion
REFERENCING_COLLECTIONS = ("applications", "offer_evaluations", "interview_preps")


def id_variants(value) -> list:
    # Selon la collection, les ids sont stockés en str ou en ObjectId.
    return [str(value), ObjectId(str(value))] if ObjectId.is_valid(str(value)) else [str(value)]


def pick_survivor(doc1: dict, doc2: dict, referenced_ids: set):
    """Renvoie (survivant, doublon supprimé), ou None si les deux offres sont référencées.

    L'offre liée à une candidature, une évaluation ou un kit d'entretien survit, pour ne jamais
    rompre ce lien. Si les deux le sont, la paire est laissée à un arbitrage manuel.
    """
    ref1 = str(doc1["_id"]) in referenced_ids
    ref2 = str(doc2["_id"]) in referenced_ids
    if ref1 and ref2:
        return None
    return (doc2, doc1) if ref2 else (doc1, doc2)


def is_same_offer(doc1: dict, doc2: dict) -> bool:
    return doc1["canonical_key"] == doc2["canonical_key"] or are_offers_duplicates(doc1, doc2)


def find_duplicate_pairs(offers: list) -> list:
    """Paires d'offres en doublon, comparées seulement entre noms d'entreprise compatibles."""
    by_name = {}
    for offer in offers:
        by_name.setdefault(offer.get("entreprise") or "", []).append(offer)

    names = list(by_name)
    pairs = []
    for i, name1 in enumerate(names):
        for name2 in names[i:]:
            if not company_match_strength(name1, name2):
                continue
            if name1 == name2:
                candidates = combinations(by_name[name1], 2)
            else:
                candidates = product(by_name[name1], by_name[name2])
            pairs.extend((a, b) for a, b in candidates if is_same_offer(a, b))
    return pairs


async def load_referenced_offer_ids(db) -> set:
    referenced = set()
    for collection in REFERENCING_COLLECTIONS:
        for offer_id in await db[collection].distinct("offer_id"):
            if offer_id:
                referenced.add(str(offer_id))
    return referenced


async def move_interactions(db, loser_id, survivor_id, apply: bool) -> tuple:
    """Rattache les interactions du doublon au survivant, sans écraser celle qu'un utilisateur y a déjà."""
    interactions = db["user_offer_interactions"]
    moved, kept = 0, 0
    for interaction in await interactions.find({"offer_id": {"$in": id_variants(loser_id)}}).to_list(None):
        already = await interactions.find_one(
            {"user_id": interaction["user_id"], "offer_id": {"$in": id_variants(survivor_id)}}, {"_id": 1}
        )
        if already:
            kept += 1
            continue
        if apply:
            await interactions.update_one({"_id": interaction["_id"]}, {"$set": {"offer_id": str(survivor_id)}})
        moved += 1
    return moved, kept


def describe(doc: dict) -> str:
    return f"{doc['_id']} | {doc.get('entreprise')!r} | {doc.get('poste')!r} @ {doc.get('localisation')!r} | {doc.get('url')}"


async def find_offer_by_identity(collection, offer: dict) -> Optional[dict]:
    """Offre en base de même clé unique ou de même URL (principale ou alternative)."""
    offer_url = (offer.get("url") or "").strip()
    query_conditions = []
    if offer.get("unique_key"):
        query_conditions.append({"unique_key": offer["unique_key"]})
    if offer_url:
        query_conditions.append({"url": offer_url})
        query_conditions.append({"alternative_urls": offer_url})
    if offer.get("alternative_urls"):
        query_conditions.append({"url": {"$in": offer["alternative_urls"]}})
    if not query_conditions:
        return None
    return await collection.find_one({"$or": query_conditions})


async def find_company_variant_duplicate(collection, offer: dict, known_companies: list) -> Optional[dict]:
    """Doublon publié sous un nom d'entreprise compatible : un même poste peut être publié sous
    « BackMarket » et « Back Market »."""
    company = offer.get("entreprise", "")
    matching_names = [
        name for name in known_companies
        if isinstance(name, str) and company_match_strength(name, company)
    ]
    if not matching_names:
        return None
    for candidate in await collection.find({"entreprise": {"$in": matching_names}}).to_list(None):
        if are_offers_duplicates(candidate, offer):
            return candidate
    return None


async def merge_duplicate_offers(db, apply: bool = False) -> dict:
    """Fusionne les offres non supprimées en doublon ; simulation sans écriture si apply est faux."""
    collection = db["job_offers"]
    offers = await collection.find({"is_deleted": {"$ne": True}}).to_list(None)
    logger.info(f"Total non-deleted offers: {len(offers)} | mode: {'APPLY' if apply else 'simulation (aucune écriture)'}")

    # 1. Calculer la clé canonique en mémoire pour chaque offre
    for offer in offers:
        offer["canonical_key"] = compute_unique_key(
            company=offer.get("entreprise", ""),
            position=offer.get("poste", ""),
            location=offer.get("localisation"),
        )

    referenced_ids = await load_referenced_offer_ids(db)
    pairs = find_duplicate_pairs(offers)

    # Une offre déjà fusionnée est remplacée par son survivant pour les paires suivantes
    merged_into = {}

    def resolve(doc):
        while doc["_id"] in merged_into:
            doc = merged_into[doc["_id"]]
        return doc

    duplicates_merged = 0
    skipped = 0

    for doc_a, doc_b in pairs:
        doc1, doc2 = resolve(doc_a), resolve(doc_b)
        if doc1["_id"] == doc2["_id"] or not is_same_offer(doc1, doc2):
            continue

        cross_company = (doc1.get("entreprise") or "") != (doc2.get("entreprise") or "")
        logger.info(f"\n🔍 Doublon{' (noms différents)' if cross_company else ''} :")
        logger.info(f"  - {describe(doc1)}")
        logger.info(f"  - {describe(doc2)}")

        choice = pick_survivor(doc1, doc2, referenced_ids)
        if choice is None:
            skipped += 1
            logger.info("  ⏭️ Les deux offres sont référencées (candidature, évaluation ou kit) : paire laissée à un arbitrage manuel.")
            continue
        survivor, loser = choice

        # Fusionner avec merge_multidiffusion_offers
        merged = merge_multidiffusion_offers(survivor, loser)
        update_fields = {
            k: v for k, v in merged.items()
            if k not in {"_id", "created_at", "date_creation", "canonical_key"}
        }
        update_fields["unique_key"] = survivor["canonical_key"]
        update_fields["updated_at"] = datetime.now(timezone.utc)

        # Nettoyer également le HTML brut dans la description si présent
        if update_fields.get("description"):
            desc = update_fields["description"]
            if "<" in desc and ">" in desc:
                desc = re.sub(r"<(?:br\s*/?|/p|/div)>", "\n", desc, flags=re.IGNORECASE)
                desc = re.sub(r"<[^>]+>", " ", desc)
                desc = re.sub(r"[ \t]+", " ", desc)
                desc = re.sub(r"\n\s*\n+", "\n\n", desc).strip()
                update_fields["description"] = desc

        if apply:
            # Supprimer le doublon d'abord pour libérer les index d'unicité (url, unique_key)
            await collection.delete_one({"_id": loser["_id"]})
            try:
                await collection.update_one({"_id": survivor["_id"]}, {"$set": update_fields})
            except Exception as e:
                restored = {k: v for k, v in loser.items() if k != "canonical_key"}
                await collection.insert_one(restored)
                logger.warning(f"  ⚠️ Fusion annulée, doublon restauré ({loser['_id']}) : {e}")
                continue

        moved, kept = await move_interactions(db, loser["_id"], survivor["_id"], apply)

        survivor.update(update_fields)
        merged_into[loser["_id"]] = survivor
        duplicates_merged += 1
        verb = "Fusionné" if apply else "À fusionner"
        logger.info(
            f"  ✅ {verb} dans {survivor['_id']} (URL principale {merged['url']}), {loser['_id']} supprimé ; "
            f"interactions rattachées : {moved}, conservées sur le survivant : {kept}"
        )

    logger.info(f"\nPaires {'fusionnées' if apply else 'à fusionner'} : {duplicates_merged} | sautées (deux offres référencées) : {skipped}")

    # 3. Maintenant que les doublons sont purgés, assigner unique_key canonique aux offres restantes
    stale_keys = [
        offer for offer in offers
        if offer["_id"] not in merged_into and offer.get("unique_key") != offer["canonical_key"]
    ]
    result = {"merged": duplicates_merged, "skipped_referenced": skipped, "stale_keys": len(stale_keys)}
    if not apply:
        logger.info(f"unique_key à recalculer avec --apply : {len(stale_keys)}")
        return result
    for offer in stale_keys:
        try:
            await collection.update_one(
                {"_id": offer["_id"]},
                {"$set": {"unique_key": offer["canonical_key"]}},
            )
        except Exception as e:
            logger.warning(f"⚠️ Erreur mise à jour unique_key pour {offer['_id']}: {e}")
    return result
