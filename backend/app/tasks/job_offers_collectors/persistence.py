"""Step 6 & 7 of collection: cross-source DB deduplication, persistence, and resource cleanup."""

from datetime import datetime, timezone
import sys
from typing import Any

from app.services.normalization import (
    compute_unique_key,
    deduplicate_and_merge_offers,
    merge_multidiffusion_offers,
)
from app.services.offer_dedup import find_company_variant_duplicate, find_offer_by_identity


def _pkg() -> Any:
    return sys.modules["app.tasks.job_offers_collectors"]


async def _resolve_company_attributes(resolver: Any, offer: dict) -> None:
    """Secteur et taille de l'entreprise : un échec d'enrichissement ne bloque jamais la sauvegarde."""
    pkg = _pkg()
    try:
        await resolver.resolve(offer)
    except Exception as e:
        pkg.logger.warning(f"⚠️ Secteur/taille non résolus pour '{offer.get('entreprise')}': {e}")


async def _upsert_or_insert_offer(
    collection: Any,
    company_resolver: Any,
    offer: dict,
    known_companies: list | None,
) -> tuple[bool, Any, list | None]:
    """Persist one consolidated offer; returns (was_inserted_new, offer_id, known_companies)."""
    pkg = _pkg()
    offer_url = (offer.get("url") or "").strip()
    company = offer.get("entreprise", "")
    unique_key = offer.get("unique_key") or compute_unique_key(
        company=company,
        position=offer.get("poste", ""),
        location=offer.get("localisation"),
        url=offer_url,
    )
    offer["unique_key"] = unique_key

    existing_doc = await find_offer_by_identity(collection, offer)
    if not existing_doc and company:
        if known_companies is None:
            known_companies = await collection.distinct("entreprise")
        existing_doc = await find_company_variant_duplicate(collection, offer, known_companies)

    if existing_doc:
        merged = merge_multidiffusion_offers(existing_doc, offer)
        await _resolve_company_attributes(company_resolver, merged)
        update_fields = {k: v for k, v in merged.items() if k not in {"_id", "created_at", "date_creation"}}
        update_fields["unique_key"] = unique_key
        update_fields["updated_at"] = datetime.now(timezone.utc)
        await collection.update_one({"_id": existing_doc["_id"]}, {"$set": update_fields})
        return False, existing_doc["_id"], known_companies

    new_doc = dict(offer)
    new_doc["unique_key"] = unique_key
    new_doc["created_at"] = offer.get("created_at") or datetime.now(timezone.utc)
    new_doc["updated_at"] = datetime.now(timezone.utc)
    await _resolve_company_attributes(company_resolver, new_doc)
    try:
        await collection.insert_one(new_doc)
        return True, new_doc["_id"], known_companies
    except Exception as ins_err:
        pkg.logger.warning(f"⚠️ Conflit d'insertion pour {unique_key}, repli sur update: {ins_err}")
        fallback_filter: dict[str, Any] = {"unique_key": unique_key}
        if offer_url:
            fallback_filter = {"$or": [{"url": offer_url}, {"unique_key": unique_key}]}
        fallback_result = await collection.update_one(
            fallback_filter,
            {"$set": {k: v for k, v in new_doc.items() if k != "_id"}},
            upsert=True,
        )
        if fallback_result.upserted_id:
            return False, fallback_result.upserted_id, known_companies
        fallback_doc = await collection.find_one(fallback_filter, {"_id": 1})
        return False, (fallback_doc["_id"] if fallback_doc else None), known_companies


async def save_offers_to_database(offers: list) -> dict:
    """Étape 6: Sauvegarde en base de données avec réconciliation cross-sources et fusion intelligente."""
    pkg = _pkg()
    pkg.logger.info(f"💾 Sauvegarde de {len(offers)} offres")
    if not offers:
        pkg.logger.warning("⚠️ Aucune offre à sauvegarder")
        return {"saved": 0, "updated": 0, "offer_ids": []}

    try:
        db = await pkg.get_database()
        collection = db["job_offers"]
        company_resolver = pkg.CompanyResolver(db)
        consolidated_offers = deduplicate_and_merge_offers(offers)

        saved_count = 0
        updated_count = 0
        error_count = 0
        offer_ids: list = []
        known_companies = None

        for offer in consolidated_offers:
            try:
                is_new, oid, known_companies = await _upsert_or_insert_offer(
                    collection, company_resolver, offer, known_companies
                )
                if oid is not None:
                    offer_ids.append(oid)
                if is_new:
                    saved_count += 1
                else:
                    updated_count += 1
            except Exception as e:
                pkg.logger.warning(f"⚠️ Erreur traitement offre {offer.get('poste')}: {e}")
                error_count += 1

        pkg.logger.info(f"✅ Sauvegarde terminée: {saved_count} créées, {updated_count} mises à jour")
        if error_count > 0:
            pkg.logger.warning(f"⚠️ {error_count} erreurs lors de la sauvegarde")
            if saved_count == 0 and updated_count == 0:
                raise RuntimeError(f"Sauvegarde totalement échouée: {error_count}/{len(offers)} offres perdues")

        return {"saved": saved_count, "updated": updated_count, "offer_ids": offer_ids}
    except Exception as e:
        pkg.logger.error(f"💥 Erreur sauvegarde: {e}")
        raise


async def cleanup_resources() -> None:
    """Étape 7: Nettoyage des ressources."""
    pkg = _pkg()
    pkg.logger.info("🧹 Nettoyage des ressources")
    try:
        from app.services.job_offers import cleanup_shared_configs

        await cleanup_shared_configs()
        pkg.logger.info("✅ Ressources nettoyées")
    except Exception as e:
        pkg.logger.warning(f"⚠️ Erreur nettoyage: {e}")
