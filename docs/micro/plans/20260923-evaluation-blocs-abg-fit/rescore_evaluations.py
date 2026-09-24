"""Recalcule la note des évaluations stockées depuis leurs blocs (aucun appel LLM).

Sauvegarde score/headline d'origine dans /app/evaluations_before_rescore.json,
puis met à jour offer_evaluations (score, headline) et job_offers.evaluation_score.
Les évaluations dont l'offre a été supprimée sont ignorées.
Usage : docker exec -i -w /app jobtracker-backend uv run python - < rescore_evaluations.py
"""
import asyncio

from bson import ObjectId, json_util
from motor.motor_asyncio import AsyncIOMotorClient

from app.database import DATABASE_NAME, MONGO_URI
from app.models import BlocA, BlocB, BlocG
from app.services.evaluation.evaluator import calculate_evaluation_score


async def main():
    db = AsyncIOMotorClient(MONGO_URI)[DATABASE_NAME]
    evaluations = await db["offer_evaluations"].find({}, {"score": 1, "headline": 1, "offer_id": 1, "user_id": 1, "bloc_a": 1, "bloc_b": 1, "bloc_g": 1}).to_list(None)
    with open("/app/evaluations_before_rescore.json", "w") as f:
        f.write(json_util.dumps([{k: e.get(k) for k in ("_id", "user_id", "offer_id", "score", "headline")} for e in evaluations], indent=1))

    for ev in evaluations:
        offer = await db["job_offers"].find_one({"_id": ObjectId(ev["offer_id"])}, {"poste": 1, "description": 1})
        if not offer:
            print(f"ignorée (offre supprimée) : {ev['offer_id']}")
            continue
        bloc_a = BlocA(**ev["bloc_a"])
        score = calculate_evaluation_score(
            bloc_a, BlocB(**ev["bloc_b"]), BlocG(**ev["bloc_g"]), len((offer.get("description") or "").strip())
        )
        await db["offer_evaluations"].update_one(
            {"_id": ev["_id"]}, {"$set": {"score": score, "headline": f"{bloc_a.archetype} ({score}/5.0)"}}
        )
        await db["job_offers"].update_one({"_id": offer["_id"]}, {"$set": {"evaluation_score": score}})
        print(f"{ev['score']:>5} -> {score:>5} | {offer['poste'][:40]}")


asyncio.run(main())
