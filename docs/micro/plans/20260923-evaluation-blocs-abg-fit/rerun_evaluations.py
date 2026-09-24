"""Relance les évaluations existantes avec le nouveau calcul (blocs A/B/G) et compare avant/après.

Sauvegarde les évaluations d'origine dans /app/evaluations_before.json avant toute relance.
Consomme 2 appels LLM par évaluation (quota utilisateur + api_usage).
Usage : docker exec -i -w /app jobtracker-backend uv run python - < rerun_evaluations.py
"""
import asyncio
import json

from bson import json_util
from motor.motor_asyncio import AsyncIOMotorClient

from app.database import DATABASE_NAME, MONGO_URI
from app.services.evaluation.evaluator import evaluate_offer_two_pass


def summarize(ev):
    a, b, g = ev.get("bloc_a", {}), ev.get("bloc_b", {}), ev.get("bloc_g", {})
    matched = b.get("matched_requirements", [])
    return {
        "score": ev.get("score"),
        "full": sum(m.get("status") == "full_match" for m in matched),
        "partial": sum(m.get("status") == "partial_match" for m in matched),
        "missing": len(b.get("missing_requirements", [])),
        "critical": sum(r.get("weight") == "critical" for r in matched + b.get("missing_requirements", [])),
        "quotes_ko": sum(m.get("quote_verified") is False for m in matched),
        "domain": a.get("domain_coherence", "-"),
        "prefs": [f"{p['criterion']}:{p['weight']}" for p in a.get("preference_mismatches", [])],
        "reposted": g.get("reposted_frequency"),
        "ghost": g.get("is_ghost_job"),
        "warnings": len(g.get("warnings", [])),
    }


async def main():
    db = AsyncIOMotorClient(MONGO_URI)[DATABASE_NAME]
    before = await db["offer_evaluations"].find({}).to_list(None)
    with open("/app/evaluations_before.json", "w") as f:
        f.write(json_util.dumps(before, ensure_ascii=False, indent=1))
    print(f"sauvegardé : {len(before)} évaluations")

    rows = []
    for ev in before:
        offer = await db["job_offers"].find_one({"_id": __import__("bson").ObjectId(ev["offer_id"])}) or {}
        label = f"{offer.get('poste', '?')[:45]} | {offer.get('entreprise', '?')[:25]}"
        try:
            new = await evaluate_offer_two_pass(db, ev["user_id"], ev["offer_id"])
            after = summarize(new.model_dump())
        except Exception as exc:  # une offre supprimée ou un quota atteint ne bloque pas les autres
            after = {"error": repr(exc)[:200]}
        rows.append({"user_id": ev["user_id"], "offer": label, "before": summarize(ev), "after": after})
        print(json.dumps(rows[-1], ensure_ascii=False))

    with open("/app/evaluations_rerun_report.json", "w") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)


asyncio.run(main())
