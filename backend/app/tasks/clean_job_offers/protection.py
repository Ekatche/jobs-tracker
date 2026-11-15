"""Application-reference checks and safe offer deletion / soft-expiration helpers."""

from datetime import datetime, timezone
import sys
from typing import Any, Dict, List, Set, Tuple


def _to_object_id(offer_id: Any) -> Any:
    from bson import ObjectId

    if not isinstance(offer_id, ObjectId) and ObjectId.is_valid(str(offer_id)):
        return ObjectId(offer_id)
    return offer_id


async def is_offer_referenced_by_application(offer_id: Any, db: Any) -> bool:
    """Return True if an offer is linked to at least one document in `db['applications']`."""
    pkg = sys.modules["app.tasks.clean_job_offers"]
    if not offer_id:
        return False
    try:
        obj_id = _to_object_id(offer_id)
        str_id = str(offer_id)
        linked = await db["applications"].find_one(
            {"$or": [{"offer_id": str_id}, {"offer_id": obj_id}]}
        )
        return linked is not None
    except Exception as e:
        pkg.logger.warning(f"Erreur vérification référence offre {offer_id}: {e}")
        return True  # Fail-safe: preserve offer when check fails


async def safe_delete_or_expire_offer(offer_id: Any, collection: Any, db: Any) -> str:
    """Hard-delete an unreferenced offer, or soft-expire it if referenced by an application."""
    pkg = sys.modules["app.tasks.clean_job_offers"]
    try:
        obj_id = _to_object_id(offer_id)
        if await pkg.is_offer_referenced_by_application(offer_id, db):
            now = datetime.now(timezone.utc)
            await collection.update_one(
                {"_id": obj_id},
                {
                    "$set": {
                        "is_deleted": True,
                        "pipeline_stage": "expired",
                        "deletion_reason": "application_referenced_retention",
                        "deleted_date": now,
                        "updated_at": now,
                    }
                },
            )
            return "expired"
        await collection.delete_one({"_id": obj_id})
        return "deleted"
    except Exception as e:
        pkg.logger.error(f"Erreur safe_delete_or_expire_offer pour {offer_id}: {e}")
        return "error"


async def fetch_referenced_offer_ids(db: Any) -> Set[str]:
    """Fetch all offer IDs referenced by existing applications."""
    cursor = db["applications"].find(
        {"offer_id": {"$exists": True, "$ne": None}},
        {"offer_id": 1},
    )
    apps = await cursor.to_list(length=None)
    return {str(app["offer_id"]) for app in apps if app.get("offer_id")}


async def purge_or_soft_expire_offers(
    collection: Any,
    offer_docs: List[Dict[str, Any]],
    referenced_raw: Set[str],
    deletion_reason: str,
) -> Tuple[int, int]:
    """Delete unlinked offers in bulk and soft-expire linked offers."""
    purge_ids: List[Any] = []
    soft_expire_ids: List[Any] = []
    for doc in offer_docs:
        if str(doc["_id"]) in referenced_raw:
            soft_expire_ids.append(doc["_id"])
        else:
            purge_ids.append(doc["_id"])

    purged_count = 0
    if purge_ids:
        res_del = await collection.delete_many({"_id": {"$in": purge_ids}})
        purged_count = res_del.deleted_count

    if soft_expire_ids:
        now = datetime.now(timezone.utc)
        await collection.update_many(
            {"_id": {"$in": soft_expire_ids}},
            {
                "$set": {
                    "is_deleted": True,
                    "pipeline_stage": "expired",
                    "deletion_reason": deletion_reason,
                    "deleted_date": now,
                    "updated_at": now,
                }
            },
        )

    return purged_count, len(soft_expire_ids)
