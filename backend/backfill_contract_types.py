"""Recalcule type_contrat des offres existantes avec detect_contract_type (stage, alternance, CDI…).

Rattrape les offres collectées avant que le contrat ne soit déduit de l'intitulé brut et de la description.
Simulation par défaut : liste les changements sans rien écrire. `--apply` les enregistre.
"""
import asyncio
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))

from app.database import get_database
from app.services.normalization import detect_contract_type


async def backfill_contract_types(apply: bool = False):
    db = await get_database()
    collection = db["job_offers"]
    offers = await collection.find(
        {"is_deleted": {"$ne": True}},
        {"type_contrat": 1, "raw_poste": 1, "poste": 1, "description": 1, "entreprise": 1},
    ).to_list(None)
    print(f"Total non-deleted offers: {len(offers)} | mode: {'APPLY' if apply else 'simulation (aucune écriture)'}")

    transitions = Counter()
    for offer in offers:
        current = offer.get("type_contrat") or "Non spécifié"
        title = offer.get("raw_poste") or offer.get("poste")
        detected = detect_contract_type(current, title, offer.get("description"))
        if detected == current:
            continue
        transitions[(current, detected)] += 1
        print(f"  {offer['_id']} | {offer.get('entreprise')!r} | {title!r} : {current!r} -> {detected!r}")
        if apply:
            await collection.update_one({"_id": offer["_id"]}, {"$set": {"type_contrat": detected}})

    print(f"\nOffres {'mises à jour' if apply else 'à mettre à jour avec --apply'} : {sum(transitions.values())}")
    for (before, after), count in transitions.most_common():
        print(f"  {before!r} -> {after!r} : {count}")


if __name__ == "__main__":
    asyncio.run(backfill_contract_types(apply="--apply" in sys.argv[1:]))
