import asyncio
import os
import sys
import re
from datetime import datetime, timezone
from bson import ObjectId

sys.path.insert(0, os.path.dirname(__file__))

from app.database import get_database
from app.services.normalization import (
    compute_unique_key,
    normalize_company,
    are_offers_duplicates,
    merge_multidiffusion_offers,
)


async def deduplicate_collection():
    db = await get_database()
    collection = db["job_offers"]
    offers = await collection.find({"is_deleted": {"$ne": True}}).to_list(1000)
    print(f"Total non-deleted offers: {len(offers)}")

    # 1. Calculer la clé canonique en mémoire pour chaque offre
    for offer in offers:
        canonical_key = compute_unique_key(
            company=offer.get("entreprise", ""),
            position=offer.get("poste", ""),
            location=offer.get("localisation"),
        )
        offer["canonical_key"] = canonical_key

    # 2. Regrouper par entreprise normalisée pour détecter les doublons exacts et sémantiques
    company_groups = {}
    for offer in offers:
        comp_norm = normalize_company(offer.get("entreprise", "")).lower()
        if not comp_norm or comp_norm == "non spécifié":
            comp_norm = f"unknown_{offer['_id']}"
        company_groups.setdefault(comp_norm, []).append(offer)

    duplicates_merged = 0
    deleted_ids = set()

    for comp, group in company_groups.items():
        if len(group) < 2:
            continue

        for i in range(len(group)):
            doc1 = group[i]
            if doc1["_id"] in deleted_ids:
                continue

            for j in range(i + 1, len(group)):
                doc2 = group[j]
                if doc2["_id"] in deleted_ids:
                    continue

                is_dup = (doc1["canonical_key"] == doc2["canonical_key"]) or are_offers_duplicates(doc1, doc2)
                if is_dup:
                    print(f"\n🔍 Duplicate detected in company '{comp}':")
                    print(f"  - Doc 1 ({doc1['_id']}): '{doc1.get('poste')}' | URL: {doc1.get('url')}")
                    print(f"  - Doc 2 ({doc2['_id']}): '{doc2.get('poste')}' | URL: {doc2.get('url')}")

                    # Fusionner avec merge_multidiffusion_offers
                    merged = merge_multidiffusion_offers(doc1, doc2)

                    # Supprimer le document doublon d'abord pour libérer l'index d'unicité
                    await collection.delete_one({"_id": doc2["_id"]})
                    deleted_ids.add(doc2["_id"])

                    # Préparer les champs mis à jour pour le document survivant
                    update_fields = {
                        k: v for k, v in merged.items()
                        if k not in {"_id", "created_at", "date_creation"}
                    }
                    update_fields["unique_key"] = doc1["canonical_key"]
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

                    await collection.update_one({"_id": doc1["_id"]}, {"$set": update_fields})

                    # Mettre à jour l'objet doc1 en mémoire
                    doc1.update(update_fields)

                    # Si doc2 avait des interactions utilisateur, les réassigner à doc1
                    try:
                        await db["user_interactions"].update_many(
                            {"offer_id": str(doc2["_id"])},
                            {"$set": {"offer_id": str(doc1["_id"])}},
                        )
                        await db["user_interactions"].update_many(
                            {"offer_id": doc2["_id"]},
                            {"$set": {"offer_id": doc1["_id"]}},
                        )
                    except Exception:
                        pass

                    duplicates_merged += 1
                    print(f"  ✅ Merged into Doc 1 ({doc1['_id']}) with primary URL {merged['url']}, alternative_urls={merged.get('alternative_urls')}, Doc 2 deleted.")

    # 3. Maintenant que les doublons sont purgés, assigner unique_key canonique aux offres restantes
    for offer in offers:
        if offer["_id"] in deleted_ids:
            continue
        canonical_key = offer["canonical_key"]
        if offer.get("unique_key") != canonical_key:
            try:
                await collection.update_one(
                    {"_id": offer["_id"]},
                    {"$set": {"unique_key": canonical_key}},
                )
            except Exception as e:
                print(f"⚠️ Erreur mise à jour unique_key pour {offer['_id']}: {e}")


if __name__ == "__main__":
    asyncio.run(deduplicate_collection())
