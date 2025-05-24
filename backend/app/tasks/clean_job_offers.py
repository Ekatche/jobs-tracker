import asyncio
from datetime import datetime, timedelta, timezone
from app.database import get_database


async def cleanup_old_offers(days: int = 7):
    """Supprime les offres anciennes"""
    db = await get_database()
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    # date doit etre un string
    cutoff_date_str = cutoff_date.strftime("%Y-%m-%d")

    result = await db["job_offers"].delete_many(
        {"created_at": {"$lt": cutoff_date_str}}
    )

    print(f"Supprimé {result.deleted_count} offres anciennes")


if __name__ == "__main__":
    asyncio.run(cleanup_old_offers(7))
