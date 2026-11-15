"""Age-based and malformed-offer cleanup rules with application protection."""

from datetime import datetime, timedelta, timezone
import sys
from typing import Any, Dict

from .protection import fetch_referenced_offer_ids, purge_or_soft_expire_offers


async def cleanup_old_offers(days: int = 40) -> Dict[str, Any]:
    """Delete or soft-expire offers older than `days` while protecting linked applications."""
    pkg = sys.modules["app.tasks.clean_job_offers"]
    pkg.logger.info(f"🗑️ Début du nettoyage des offres de plus de {days} jours")

    db = await pkg.get_database()
    collection = db["job_offers"]
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    try:
        query = {
            "$or": [
                {"created_at": {"$lt": cutoff_date}},
                {"created_at": {"$lt": cutoff_date.isoformat()}},
            ]
        }
        referenced_raw = await fetch_referenced_offer_ids(db)
        old_offers = await collection.find(query, {"_id": 1}).to_list(length=None)
        if not old_offers:
            pkg.logger.info("✅ Aucune offre ancienne à supprimer")
            return {"deleted": 0}

        purged_count, soft_expired = await purge_or_soft_expire_offers(
            collection,
            old_offers,
            referenced_raw,
            "old_offer_referenced_in_application",
        )
        pkg.logger.info(
            f"✅ {purged_count} offres anciennes purgées, "
            f"{soft_expired} offres liées archivées en soft-delete"
        )
        return {"deleted": purged_count, "soft_expired": soft_expired}
    except Exception as e:
        pkg.logger.error(f"💥 Erreur lors du nettoyage: {e}")
        return {"deleted": 0, "error": str(e)}


async def cleanup_invalid_offers() -> Dict[str, Any]:
    """Delete malformed offers (missing title/company or non-HTTP URL), protecting linked apps."""
    pkg = sys.modules["app.tasks.clean_job_offers"]
    pkg.logger.info("🧹 Début du nettoyage des offres invalides")

    db = await pkg.get_database()
    collection = db["job_offers"]

    try:
        referenced_raw = await fetch_referenced_offer_ids(db)
        invalid_query = {
            "$or": [
                {"poste": {"$in": [None, "", "Poste non spécifié"]}},
                {
                    "entreprise": {
                        "$in": [
                            None,
                            "",
                            "Entreprise non spécifiée",
                            "Non spécifié",
                        ]
                    }
                },
                {"url": {"$regex": "^(?!https?://).*"}},
            ]
        }
        invalid_docs = await collection.find(invalid_query, {"_id": 1}).to_list(length=None)
        deleted_count, protected_linked = await purge_or_soft_expire_offers(
            collection,
            invalid_docs,
            referenced_raw,
            "invalid_offer_referenced_in_application",
        )
        pkg.logger.info(
            f"✅ {deleted_count} offres invalides supprimées, "
            f"{protected_linked} offres liées protégées en soft-delete"
        )
        return {"deleted_invalid": deleted_count, "protected_linked": protected_linked}
    except Exception as e:
        pkg.logger.error(f"💥 Erreur lors du nettoyage des invalides: {e}")
        return {"deleted_invalid": 0, "error": str(e)}
