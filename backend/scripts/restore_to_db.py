import json
import os
from datetime import datetime, timezone
from bson import ObjectId
import motor.motor_asyncio
import asyncio
import sys

def parse_dt(val):
    if not val:
        return datetime.now(timezone.utc)
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if isinstance(val, str):
        try:
            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            return datetime.now(timezone.utc)
    return datetime.now(timezone.utc)

async def restore(mongo_uri: str, db_name: str, target_email: str, json_file: str):
    print(f"Connecting to {mongo_uri} (db: {db_name})...")
    client = motor.motor_asyncio.AsyncIOMotorClient(mongo_uri)
    db = client[db_name]

    user = await db.users.find_one({"email": target_email})
    if not user:
        print(f"ERROR: User with email '{target_email}' not found in database {db_name}!")
        return False

    user_oid = user["_id"]
    user_str = str(user_oid)
    print(f"Target User found: {user.get('full_name')} ({target_email}) -> ID: {user_oid}")

    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    apps = data.get("applications", [])
    cover_letters = data.get("cover_letters", {})
    evaluations = data.get("evaluations", {})
    resumes = data.get("resumes", [])

    print(f"\n--- 1. Restoring {len(apps)} Applications ---")
    app_count = 0
    for app in apps:
        aid = ObjectId(app["_id"])
        doc = dict(app)
        doc["_id"] = aid
        doc["user_id"] = user_str  # applications router stores user_id as string
        doc["application_date"] = parse_dt(doc.get("application_date"))
        doc["created_at"] = parse_dt(doc.get("created_at"))
        if "updated_at" in doc and doc["updated_at"]:
            doc["updated_at"] = parse_dt(doc["updated_at"])

        await db.applications.update_one(
            {"_id": aid},
            {"$set": doc},
            upsert=True
        )
        app_count += 1
    print(f"-> {app_count} applications restored/updated.")

    print(f"\n--- 2. Restoring {len(cover_letters)} Cover Letters ---")
    cl_count = 0
    for aid_str, cl in cover_letters.items():
        aid = ObjectId(aid_str)
        doc = dict(cl)
        if "_id" in doc:
            doc["_id"] = ObjectId(doc["_id"])
        doc["application_id"] = aid
        doc["user_id"] = user_str

        # parse dates in versions
        if "versions" in doc and isinstance(doc["versions"], list):
            for v in doc["versions"]:
                if "created_at" in v:
                    v["created_at"] = parse_dt(v["created_at"])
        if "created_at" in doc:
            doc["created_at"] = parse_dt(doc["created_at"])
        if "updated_at" in doc:
            doc["updated_at"] = parse_dt(doc["updated_at"])

        await db.cover_letters.update_one(
            {"application_id": aid},
            {"$set": doc},
            upsert=True
        )
        cl_count += 1
    print(f"-> {cl_count} cover letters restored/updated.")

    print(f"\n--- 3. Restoring {len(evaluations)} Evaluations ---")
    ev_count = 0
    for aid_str, ev in evaluations.items():
        aid = ObjectId(aid_str)
        doc = dict(ev)
        ev_id = doc.get("id") or doc.get("_id")
        if ev_id:
            doc["_id"] = ObjectId(ev_id)
        doc["application_id"] = aid
        doc["user_id"] = user_str

        await db.offer_evaluations.update_one(
            {"application_id": aid},
            {"$set": doc},
            upsert=True
        )
        ev_count += 1
    print(f"-> {ev_count} evaluations restored/updated.")

    print(f"\n--- 4. Restoring {len(resumes)} Resumes ---")
    res_count = 0
    for res in resumes:
        doc = dict(res)
        rid = ObjectId(doc["_id"])
        doc["_id"] = rid
        doc["user_id"] = user_oid  # tailored_resumes stores user_id as ObjectId
        if doc.get("offer_id") and ObjectId.is_valid(doc["offer_id"]):
            doc["offer_id"] = ObjectId(doc["offer_id"])
        if doc.get("application_id") and ObjectId.is_valid(doc["application_id"]):
            doc["application_id"] = ObjectId(doc["application_id"])
        doc["created_at"] = parse_dt(doc.get("created_at"))
        doc["updated_at"] = parse_dt(doc.get("updated_at"))

        await db.tailored_resumes.update_one(
            {"_id": rid},
            {"$set": doc},
            upsert=True
        )
        res_count += 1
    print(f"-> {res_count} tailored resumes restored/updated.")

    # Verification counts
    print(f"\n=== Database Verification for {target_email} ===")
    total_apps = await db.applications.count_documents({"user_id": user_str})
    total_cls = await db.cover_letters.count_documents({"user_id": user_str})
    total_evs = await db.offer_evaluations.count_documents({"user_id": user_str})
    total_res = await db.tailored_resumes.count_documents({"user_id": user_oid})
    print(f"Total Applications: {total_apps}")
    print(f"Total Cover Letters: {total_cls}")
    print(f"Total Evaluations: {total_evs}")
    print(f"Total Resumes: {total_res}")
    return True

if __name__ == "__main__":
    uri = sys.argv[1] if len(sys.argv) > 1 else os.getenv("MONGO_URI", "mongodb://mongodb:27017")
    db_name = sys.argv[2] if len(sys.argv) > 2 else os.getenv("DATABASE_NAME", "job_tracker")
    target_email = sys.argv[3] if len(sys.argv) > 3 else os.getenv("TARGET_EMAIL", "")
    if not target_email:
        print("Usage: python restore_to_db.py <mongo_uri> <db_name> <target_email> [json_file]")
        sys.exit(1)
    default_json = os.path.join(os.path.dirname(__file__), "../../data/recovered/consolidated_data.json")
    json_file = sys.argv[4] if len(sys.argv) > 4 else default_json

    asyncio.run(restore(uri, db_name, target_email, json_file))

