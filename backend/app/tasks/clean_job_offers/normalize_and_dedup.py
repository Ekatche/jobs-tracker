"""Data normalization, exact deduplication, and similarity deduplication helpers."""

from datetime import datetime, timezone
import sys
from typing import Any, Dict, List

_SURVIVOR_UPDATE_FIELDS = (
    "url",
    "alternative_urls",
    "salaire",
    "type_contrat",
    "localisation",
    "description",
    "competences_cles",
    "canonical_title",
    "seniority_level",
    "poste",
)


def _compute_offer_normalization_updates(offer: Dict[str, Any], pkg: Any) -> Dict[str, Any]:
    updates: Dict[str, Any] = {}
    if offer.get("localisation"):
        normalized_city = pkg.normalize_city(offer["localisation"])
        if normalized_city != offer.get("normalized_city"):
            updates["normalized_city"] = normalized_city

    if offer.get("entreprise"):
        normalized_company = pkg.normalize_company(offer["entreprise"])
        if normalized_company != offer.get("normalized_company"):
            updates["normalized_company"] = normalized_company

    if offer.get("url"):
        normalized_site = pkg.extract_domain(offer["url"])
        if normalized_site != offer.get("normalized_site"):
            updates["normalized_site"] = normalized_site

    if not offer.get("pipeline_stage"):
        if offer.get("is_deleted"):
            updates["pipeline_stage"] = "expired"
        elif offer.get("evaluation_score") is not None:
            updates["pipeline_stage"] = "evaluated"
        else:
            updates["pipeline_stage"] = "discovered"

    return updates


async def normalize_existing_data() -> Dict[str, int]:
    """Normalize normalized_city/company/site and missing pipeline_stage on stored offers."""
    pkg = sys.modules["app.tasks.clean_job_offers"]
    pkg.logger.info("🔄 Début de la normalisation des données existantes")

    db = await pkg.get_database()
    collection = db["job_offers"]
    offers = await collection.find({}).to_list(length=None)
    pkg.logger.info(f"📊 {len(offers)} offres à traiter")

    updated_count = 0
    error_count = 0
    for offer in offers:
        try:
            updates = _compute_offer_normalization_updates(offer, pkg)
            if updates:
                await collection.update_one({"_id": offer["_id"]}, {"$set": updates})
                updated_count += 1
        except Exception as e:
            error_count += 1
            pkg.logger.error(f"💥 Erreur normalisation offre {offer.get('_id', 'unknown')}: {e}")

    pkg.logger.info(
        f"✅ Normalisation terminée: {updated_count} offres mises à jour sur {len(offers)}"
    )
    if error_count > 0:
        pkg.logger.warning(f"⚠️ {error_count} erreurs lors de la normalisation")
    return {"normalized": updated_count, "total": len(offers), "errors": error_count}


def _safe_date_sort(doc: Dict[str, Any]) -> datetime:
    val = doc.get("created_at")
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        except Exception:
            pass
    return datetime.min.replace(tzinfo=timezone.utc)


async def remove_exact_duplicates() -> Dict[str, Any]:
    """Delete exact URL duplicates, retaining the most recently created document."""
    pkg = sys.modules["app.tasks.clean_job_offers"]
    pkg.logger.info("🔍 Début de la suppression des doublons exacts")

    db = await pkg.get_database()
    collection = db["job_offers"]
    pipeline = [
        {"$match": {"url": {"$nin": [None, ""]}}},
        {
            "$group": {
                "_id": "$url",
                "count": {"$sum": 1},
                "docs": {"$push": {"id": "$_id", "created_at": "$created_at"}},
            }
        },
        {"$match": {"count": {"$gt": 1}}},
    ]

    deleted_count = 0
    try:
        url_duplicates = await collection.aggregate(pipeline).to_list(length=None)
        for group in url_duplicates:
            docs = sorted(group["docs"], key=_safe_date_sort, reverse=True)
            for doc in docs[1:]:
                action = await pkg.safe_delete_or_expire_offer(doc["id"], collection, db)
                if action in ("deleted", "expired"):
                    deleted_count += 1
        pkg.logger.info(f"✅ Supprimé {deleted_count} doublons exacts")
        return {"deleted_exact_duplicates": deleted_count}
    except Exception as e:
        pkg.logger.error(f"💥 Erreur lors de la suppression des doublons exacts: {e}")
        return {"deleted_exact_duplicates": 0, "error": str(e)}


def _build_survivor_update_fields(survivor: Dict[str, Any]) -> Dict[str, Any]:
    update_fields = {field: survivor[field] for field in _SURVIVOR_UPDATE_FIELDS if field in survivor}
    if update_fields:
        update_fields["updated_at"] = datetime.now(timezone.utc)
    return update_fields


async def remove_similarity_duplicates(
    company_similarity_threshold: float = 0.75,
    position_similarity_threshold: float = 0.80,
    batch_size: int = 1000,
) -> Dict[str, Any]:
    """Deduplicate active offers using `clean_job_offer_duplicates_optimized`."""
    pkg = sys.modules["app.tasks.clean_job_offers"]
    pkg.logger.info(
        "🎯 Début de la suppression des doublons par similarité "
        f"(seuils: entreprise={company_similarity_threshold}, poste={position_similarity_threshold})"
    )

    db = await pkg.get_database()
    collection = db["job_offers"]
    query = {"$or": [{"is_deleted": {"$exists": False}}, {"is_deleted": False}]}
    offers = await collection.find(query).to_list(length=None)
    pkg.logger.info(f"📊 {len(offers)} offres actives à analyser")

    if len(offers) <= 1:
        pkg.logger.info("✅ Pas assez d'offres pour détecter des similarités")
        return {"deleted_similarity_duplicates": 0}

    try:
        cleaned_offers = pkg.clean_job_offer_duplicates_optimized(
            offers,
            company_similarity_threshold=company_similarity_threshold,
            position_similarity_threshold=position_similarity_threshold,
        )
        deleted_count = len(offers) - len(cleaned_offers)
        if deleted_count <= 0:
            pkg.logger.info("✅ Aucun doublon par similarité détecté")
            return {"deleted_similarity_duplicates": 0}

        for survivor in cleaned_offers:
            survivor_id = survivor.get("_id")
            if survivor_id:
                update_fields = _build_survivor_update_fields(survivor)
                if update_fields:
                    await collection.update_one({"_id": survivor_id}, {"$set": update_fields})

        cleaned_ids = {offer.get("_id") for offer in cleaned_offers}
        for offer_to_delete in (o for o in offers if o.get("_id") not in cleaned_ids):
            action = await pkg.safe_delete_or_expire_offer(offer_to_delete["_id"], collection, db)
            if action not in ("deleted", "expired"):
                pkg.logger.warning(f"⚠️ Échec traitement doublon: {offer_to_delete['_id']}")

        pkg.logger.info(
            f"✅ Nettoyage par similarité terminé: {deleted_count} doublons traités et métadonnées "
            f"fusionnées sur {len(offers)} offres analysées"
        )
        return {"deleted_similarity_duplicates": deleted_count}
    except Exception as e:
        pkg.logger.error(f"💥 Erreur lors du nettoyage par similarité: {e}")
        return {"deleted_similarity_duplicates": 0, "error": str(e)}


async def prevent_duplicate_insertion(new_offers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter candidate offers against existing DB offers before bulk insertion."""
    pkg = sys.modules["app.tasks.clean_job_offers"]
    if not new_offers:
        return []

    pkg.logger.info(f"🛡️ Vérification anti-doublon pour {len(new_offers)} nouvelles offres")
    db = await pkg.get_database()
    collection = db["job_offers"]
    existing_offers = await collection.find({}).to_list(length=None)
    pkg.logger.info(f"📊 Comparaison contre {len(existing_offers)} offres existantes")

    if not existing_offers:
        return new_offers

    cleaned_offers = pkg.clean_job_offer_duplicates_optimized(existing_offers + new_offers)
    existing_ids = {str(offer.get("_id", "")) for offer in existing_offers}
    surviving = [o for o in cleaned_offers if str(o.get("_id", "")) not in existing_ids]

    filtered_count = len(new_offers) - len(surviving)
    pkg.logger.info(
        f"🛡️ Prévention doublons: {filtered_count} nouvelles offres filtrées, {len(surviving)} à insérer"
    )
    return surviving
