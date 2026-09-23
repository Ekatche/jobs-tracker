"""Supprime de la base réelle les documents laissés par test_interview_prep_api.

Rejouable : ne cible que les _id listés dans test_pollution_backup.json.
Usage : docker exec -i -w /app jobtracker-backend uv run python - < delete_test_pollution.py
(depuis ce dossier, le backup étant copié dans /app au préalable)
"""
from bson import json_util
from pymongo import MongoClient

from app.database import DATABASE_NAME, MONGO_URI

db = MongoClient(MONGO_URI)[DATABASE_NAME]
backup = json_util.loads(open("/app/test_pollution_backup.json").read())

offer_ids = [d["_id"] for d in backup["job_offers"]]
prep_ids = [d["_id"] for d in backup["interview_preps"]]
profile_ids = [d["_id"] for d in backup["candidate_profiles"]]

print("offers:", db.job_offers.delete_many({"_id": {"$in": offer_ids}, "poste": {"$exists": False}}).deleted_count)
print("interview_preps:", db.interview_preps.delete_many({"_id": {"$in": prep_ids}}).deleted_count)
print("candidate_profiles:", db.candidate_profiles.delete_many({"_id": {"$in": profile_ids}}).deleted_count)
