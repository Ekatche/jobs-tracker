import asyncio
import sys
sys.path.insert(0, "/Users/elielkatche/job-tracker/backend")

from app.database import get_database


async def main():
    db = await get_database()
    cursor = db["job_offers"].find(
        {"url": {"$type": "string", "$ne": ""}, "is_deleted": {"$ne": True}},
        {"url": 1, "poste": 1, "entreprise": 1, "created_at": 1},
    ).sort("created_at", -1).limit(15)
    async for doc in cursor:
        print(doc.get("url"), "|", doc.get("poste"), "|", doc.get("entreprise"), "|", doc.get("created_at"))


asyncio.run(main())
