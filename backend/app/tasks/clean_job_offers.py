import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.database import get_database
from app.services.job_offers import clean_job_offer_duplicates_optimized
from app.services.normalization import (
    extract_domain,
    normalize_city,
    normalize_company,
)
from app.services.offer_dedup import merge_duplicate_offers

logger = logging.getLogger(__name__)


# ======================================================================
# FONCTIONS DE VÉRIFICATION & PROTECTION MULTI-TENANT
# ======================================================================


async def is_offer_referenced_by_application(offer_id, db) -> bool:
    """Vérifie si une offre est liée à au moins une candidature dans db['applications']."""
    if not offer_id:
        return False
    try:
        from bson import ObjectId

        obj_id = (
            ObjectId(offer_id)
            if not isinstance(offer_id, ObjectId) and ObjectId.is_valid(str(offer_id))
            else offer_id
        )
        str_id = str(offer_id)
        linked = await db["applications"].find_one(
            {"$or": [{"offer_id": str_id}, {"offer_id": obj_id}]}
        )
        return linked is not None
    except Exception as e:
        logger.warning(f"Erreur vérification référence offre {offer_id}: {e}")
        return True  # Principe de précaution : préserver si erreur


async def safe_delete_or_expire_offer(offer_id, collection, db) -> str:
    """Supprime physiquement une offre non référencée, ou la passe en soft-delete ('expired') si liée."""
    try:
        from bson import ObjectId

        obj_id = (
            ObjectId(offer_id)
            if not isinstance(offer_id, ObjectId) and ObjectId.is_valid(str(offer_id))
            else offer_id
        )

        if await is_offer_referenced_by_application(offer_id, db):
            await collection.update_one(
                {"_id": obj_id},
                {
                    "$set": {
                        "is_deleted": True,
                        "pipeline_stage": "expired",
                        "deletion_reason": "application_referenced_retention",
                        "deleted_date": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )
            return "expired"
        else:
            await collection.delete_one({"_id": obj_id})
            return "deleted"
    except Exception as e:
        logger.error(f"Erreur safe_delete_or_expire_offer pour {offer_id}: {e}")
        return "error"


# ======================================================================
# FONCTIONS DE NETTOYAGE
# ======================================================================


async def normalize_existing_data():
    """Normalise les données existantes en base"""
    logger.info("🔄 Début de la normalisation des données existantes")

    db = await get_database()
    collection = db["job_offers"]

    # Récupérer toutes les offres
    offers = await collection.find({}).to_list(length=None)
    logger.info(f"📊 {len(offers)} offres à traiter")

    updated_count = 0
    error_count = 0

    for offer in offers:
        try:
            updates = {}

            # Normaliser la ville
            if offer.get("localisation"):
                normalized_city = normalize_city(offer["localisation"])
                if normalized_city != offer.get("normalized_city"):
                    updates["normalized_city"] = normalized_city

            # Normaliser l'entreprise
            if offer.get("entreprise"):
                normalized_company = normalize_company(offer["entreprise"])
                if normalized_company != offer.get("normalized_company"):
                    updates["normalized_company"] = normalized_company

            # Normaliser le site web
            if offer.get("url"):
                normalized_site = extract_domain(offer["url"])
                if normalized_site != offer.get("normalized_site"):
                    updates["normalized_site"] = normalized_site

            # Synchroniser pipeline_stage si manquant
            if not offer.get("pipeline_stage"):
                if offer.get("is_deleted"):
                    updates["pipeline_stage"] = "expired"
                elif offer.get("evaluation_score") is not None:
                    updates["pipeline_stage"] = "evaluated"
                else:
                    updates["pipeline_stage"] = "discovered"

            # Mettre à jour si nécessaire
            if updates:
                await collection.update_one({"_id": offer["_id"]}, {"$set": updates})
                updated_count += 1

        except Exception as e:
            error_count += 1
            logger.error(
                f"💥 Erreur normalisation offre {offer.get('_id', 'unknown')}: {e}"
            )

    logger.info(
        f"✅ Normalisation terminée: {updated_count} offres mises à jour sur {len(offers)}"
    )
    if error_count > 0:
        logger.warning(f"⚠️ {error_count} erreurs lors de la normalisation")

    return {"normalized": updated_count, "total": len(offers), "errors": error_count}


async def remove_exact_duplicates():
    """Supprime les doublons exacts basés sur URL ou combinaison poste+entreprise+localisation"""
    logger.info("🔍 Début de la suppression des doublons exacts")

    db = await get_database()
    collection = db["job_offers"]

    # Pipeline pour identifier les doublons par URL
    url_duplicates_pipeline = [
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
        # Traiter les doublons par URL
        url_duplicates = await collection.aggregate(url_duplicates_pipeline).to_list(
            length=None
        )

        for duplicate_group in url_duplicates:
            # Garder le plus récent, supprimer les autres avec tri défensif
            def safe_date_sort(d):
                val = d.get("created_at")
                if isinstance(val, datetime):
                    return val
                if isinstance(val, str):
                    try:
                        return datetime.fromisoformat(val.replace("Z", "+00:00"))
                    except Exception:
                        pass
                return datetime.min.replace(tzinfo=timezone.utc)

            docs = sorted(duplicate_group["docs"], key=safe_date_sort, reverse=True)
            docs_to_delete = docs[1:]  # Tous sauf le premier (plus récent)

            for doc in docs_to_delete:
                action = await safe_delete_or_expire_offer(doc["id"], collection, db)
                if action in ("deleted", "expired"):
                    deleted_count += 1

        logger.info(f"✅ Supprimé {deleted_count} doublons exacts")
        return {"deleted_exact_duplicates": deleted_count}

    except Exception as e:
        logger.error(f"💥 Erreur lors de la suppression des doublons exacts: {e}")
        return {"deleted_exact_duplicates": 0, "error": str(e)}


async def remove_similarity_duplicates(
    company_similarity_threshold: float = 0.75,
    position_similarity_threshold: float = 0.80,
    batch_size: int = 1000,
):
    """✨ NOUVEAU: Utilise la fonction optimisée pour supprimer les doublons par similarité"""
    logger.info(
        f"🎯 Début de la suppression des doublons par similarité (seuils: entreprise={company_similarity_threshold}, poste={position_similarity_threshold})"
    )

    db = await get_database()
    collection = db["job_offers"]

    # Récupérer toutes les offres actives (non supprimées)
    query = {"$or": [{"is_deleted": {"$exists": False}}, {"is_deleted": False}]}

    offers = await collection.find(query).to_list(length=None)
    logger.info(f"📊 {len(offers)} offres actives à analyser")

    if len(offers) <= 1:
        logger.info("✅ Pas assez d'offres pour détecter des similarités")
        return {"deleted_similarity_duplicates": 0}

    try:
        # ✅ UTILISATION de la fonction optimisée existante
        logger.info("🔧 Utilisation de clean_job_offer_duplicates_optimized")

        # Nettoyer les doublons avec la fonction optimisée
        cleaned_offers = clean_job_offer_duplicates_optimized(
            offers,
            company_similarity_threshold=company_similarity_threshold,
            position_similarity_threshold=position_similarity_threshold,
        )

        # Calculer le nombre de doublons supprimés
        deleted_count = len(offers) - len(cleaned_offers)

        if deleted_count > 0:
            # 1. Mettre à jour les offres survivantes avec leurs métadonnées consolidées (multi-sources, salaire, etc.)
            for survivor in cleaned_offers:
                survivor_id = survivor.get("_id")
                if survivor_id:
                    update_fields = {}
                    for field in [
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
                    ]:
                        if field in survivor:
                            update_fields[field] = survivor[field]
                    if update_fields:
                        update_fields["updated_at"] = datetime.now(timezone.utc)
                        await collection.update_one(
                            {"_id": survivor_id},
                            {"$set": update_fields},
                        )

            # 2. Identifier et supprimer/expirer les doublons de manière sécurisée
            cleaned_ids = {offer.get("_id") for offer in cleaned_offers}
            offers_to_delete = [
                offer for offer in offers if offer.get("_id") not in cleaned_ids
            ]

            for offer_to_delete in offers_to_delete:
                action = await safe_delete_or_expire_offer(
                    offer_to_delete["_id"], collection, db
                )
                if action not in ("deleted", "expired"):
                    logger.warning(f"⚠️ Échec traitement doublon: {offer_to_delete['_id']}")

            logger.info(
                f"✅ Nettoyage par similarité terminé: {deleted_count} doublons traités et métadonnées fusionnées sur {len(offers)} offres analysées"
            )
        else:
            logger.info("✅ Aucun doublon par similarité détecté")

        return {"deleted_similarity_duplicates": deleted_count}

    except Exception as e:
        logger.error(f"💥 Erreur lors du nettoyage par similarité: {e}")
        return {"deleted_similarity_duplicates": 0, "error": str(e)}


async def cleanup_old_offers(days: int = 40):
    """Supprime ou expire les offres anciennes en protégeant les candidatures actives"""
    logger.info(f"🗑️ Début du nettoyage des offres de plus de {days} jours")

    db = await get_database()
    collection = db["job_offers"]

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    try:
        # Requête robuste gérant BSON Date et ISO String
        query = {
            "$or": [
                {"created_at": {"$lt": cutoff_date}},
                {"created_at": {"$lt": cutoff_date.isoformat()}},
            ]
        }

        # Identifier les offres référencées par des candidatures pour éviter de les purger
        app_cursor = db["applications"].find(
            {"offer_id": {"$exists": True, "$ne": None}}, {"offer_id": 1}
        )
        apps = await app_cursor.to_list(length=None)
        referenced_raw = {str(a["offer_id"]) for a in apps if a.get("offer_id")}

        # Compter d'abord les offres candidates
        old_offers = await collection.find(query, {"_id": 1}).to_list(length=None)
        if not old_offers:
            logger.info("✅ Aucune offre ancienne à supprimer")
            return {"deleted": 0}

        purge_ids = []
        soft_expire_ids = []
        for o in old_offers:
            if str(o["_id"]) in referenced_raw:
                soft_expire_ids.append(o["_id"])
            else:
                purge_ids.append(o["_id"])

        purged_count = 0
        if purge_ids:
            res_del = await collection.delete_many({"_id": {"$in": purge_ids}})
            purged_count = res_del.deleted_count

        if soft_expire_ids:
            await collection.update_many(
                {"_id": {"$in": soft_expire_ids}},
                {
                    "$set": {
                        "is_deleted": True,
                        "pipeline_stage": "expired",
                        "deletion_reason": "old_offer_referenced_in_application",
                        "deleted_date": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )

        logger.info(
            f"✅ {purged_count} offres anciennes purgées, {len(soft_expire_ids)} offres liées archivées en soft-delete"
        )
        return {"deleted": purged_count, "soft_expired": len(soft_expire_ids)}

    except Exception as e:
        logger.error(f"💥 Erreur lors du nettoyage: {e}")
        return {"deleted": 0, "error": str(e)}


async def cleanup_invalid_offers():
    """Supprime les offres avec des données invalides en protégeant les candidatures liées"""
    logger.info("🧹 Début du nettoyage des offres invalides")

    db = await get_database()
    collection = db["job_offers"]

    try:
        # Identifier les offres référencées par des candidatures pour éviter de les purger
        app_cursor = db["applications"].find(
            {"offer_id": {"$exists": True, "$ne": None}}, {"offer_id": 1}
        )
        apps = await app_cursor.to_list(length=None)
        referenced_raw = {str(a["offer_id"]) for a in apps if a.get("offer_id")}

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

        purge_ids = []
        soft_expire_ids = []
        for inv in invalid_docs:
            if str(inv["_id"]) in referenced_raw:
                soft_expire_ids.append(inv["_id"])
            else:
                purge_ids.append(inv["_id"])

        deleted_count = 0
        if purge_ids:
            res = await collection.delete_many({"_id": {"$in": purge_ids}})
            deleted_count = res.deleted_count

        if soft_expire_ids:
            await collection.update_many(
                {"_id": {"$in": soft_expire_ids}},
                {
                    "$set": {
                        "is_deleted": True,
                        "pipeline_stage": "expired",
                        "deletion_reason": "invalid_offer_referenced_in_application",
                        "deleted_date": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    }
                },
            )

        logger.info(
            f"✅ {deleted_count} offres invalides supprimées, {len(soft_expire_ids)} offres liées protégées en soft-delete"
        )
        return {"deleted_invalid": deleted_count, "protected_linked": len(soft_expire_ids)}

    except Exception as e:
        logger.error(f"💥 Erreur lors du nettoyage des invalides: {e}")
        return {"deleted_invalid": 0, "error": str(e)}


# ======================================================================
# FONCTION PRINCIPALE POUR AIRFLOW
# ======================================================================


async def cleanup_workflow(
    days: Optional[int] = None,
    enable_similarity_cleanup: bool = True,
    enable_global_similarity: bool = True,  # ✅ NOUVEAU: Priorité au global
    company_similarity_threshold: float = 0.75,
    position_similarity_threshold: float = 0.80,
    enable_old_offers_cleanup: bool = False,  # ✅ Désactivé par défaut au profit de l'inspection réelle verify_job_offers
):
    """✨ MODIFIÉ: Workflow avec nettoyage global renforcé (sans purge aveugle par date)"""
    logger.info("🚀 Début du workflow de nettoyage Airflow (mode global renforcé)")

    results = {"start_time": datetime.now(timezone.utc), "steps": {}}

    try:
        # Étape 1: Normalisation des données
        logger.info("📝 Étape 1: Normalisation des données")
        results["steps"]["normalize"] = await normalize_existing_data()

        # Étape 2: Suppression des doublons exacts
        logger.info("🔍 Étape 2: Suppression des doublons exacts")
        results["steps"]["exact_duplicates"] = await remove_exact_duplicates()

        # ✨ Étape 3: fusion des doublons avec la règle de l'insertion (même ville, URL du doublon conservée)
        if enable_global_similarity:
            logger.info("🌍 Étape 3: Fusion des doublons (règle de l'insertion)")
            results["steps"]["global_similarity"] = await merge_duplicate_offers(
                await get_database(), apply=True
            )
        elif enable_similarity_cleanup:
            logger.info("🎯 Étape 3: Nettoyage par similarité (mode standard)")
            results["steps"]["similarity_duplicates"] = (
                await remove_similarity_duplicates(
                    company_similarity_threshold=company_similarity_threshold,
                    position_similarity_threshold=position_similarity_threshold,
                )
            )
        else:
            logger.info("⏭️ Étape 3: Nettoyage par similarité désactivé")
            results["steps"]["similarity_duplicates"] = {
                "deleted_similarity_duplicates": 0
            }

        # Étape 4: Suppression des offres invalides
        logger.info("🧹 Étape 4: Suppression des offres invalides")
        results["steps"]["invalid"] = await cleanup_invalid_offers()

        # Étape 5: Suppression des anciennes offres (uniquement si explicitement activé)
        if enable_old_offers_cleanup and days and days > 0:
            logger.info(f"🗑️ Étape 5: Suppression des offres > {days} jours")
            results["steps"]["old_offers"] = await cleanup_old_offers(days)
        else:
            logger.info(
                "⏭️ Étape 5: Purge aveugle par âge désactivée (la validité réelle est assurée par verify_job_offers)"
            )
            results["steps"]["old_offers"] = {
                "deleted": 0,
                "status": "disabled_in_favor_of_live_verification",
            }

        # Calcul des résultats
        results["end_time"] = datetime.now(timezone.utc)
        results["duration"] = (
            results["end_time"] - results["start_time"]
        ).total_seconds()

        # ✅ Adaptation aux nouvelles métriques
        if enable_global_similarity:
            similarity_deleted = results["steps"].get("global_similarity", {}).get("merged", 0)
            skipped_referenced = (
                results["steps"].get("global_similarity", {}).get("skipped_referenced", 0)
            )
        else:
            similarity_deleted = (
                results["steps"]
                .get("similarity_duplicates", {})
                .get("deleted_similarity_duplicates", 0)
            )
            skipped_referenced = 0

        total_deleted = sum(
            [
                results["steps"]
                .get("exact_duplicates", {})
                .get("deleted_exact_duplicates", 0),
                similarity_deleted,
                results["steps"].get("invalid", {}).get("deleted_invalid", 0),
                results["steps"].get("old_offers", {}).get("deleted", 0),
            ]
        )

        total_normalized = results["steps"].get("normalize", {}).get("normalized", 0)

        logger.info("🎯 Workflow de nettoyage terminé:")
        logger.info(f"  📊 Données normalisées: {total_normalized}")
        logger.info(
            f"  🔗 Doublons exacts supprimés: {results['steps'].get('exact_duplicates', {}).get('deleted_exact_duplicates', 0)}"
        )

        if enable_global_similarity:
            logger.info(
                f"  🌍 Doublons similaires fusionnés (global): {similarity_deleted}"
            )
            logger.info(
                f"  ⏭️ Paires sautées (deux offres référencées): {skipped_referenced}"
            )
        elif enable_similarity_cleanup:
            logger.info(
                f"  🎯 Doublons similaires supprimés (standard): {similarity_deleted}"
            )

        logger.info(
            f"  🧹 Offres invalides supprimées: {results['steps'].get('invalid', {}).get('deleted_invalid', 0)}"
        )
        logger.info(
            f"  🗑️ Offres anciennes supprimées: {results['steps'].get('old_offers', {}).get('deleted', 0)}"
        )
        logger.info(f"  📊 Total supprimé: {total_deleted}")
        logger.info(f"  ⏱️ Durée: {results['duration']:.2f}s")

        results["summary"] = {
            "total_normalized": total_normalized,
            "total_deleted": total_deleted,
            "exact_duplicates_deleted": results["steps"]
            .get("exact_duplicates", {})
            .get("deleted_exact_duplicates", 0),
            "similarity_duplicates_deleted": similarity_deleted,
            "skipped_referenced": skipped_referenced,
            "invalid_deleted": results["steps"]
            .get("invalid", {})
            .get("deleted_invalid", 0),
            "old_offers_deleted": results["steps"]
            .get("old_offers", {})
            .get("deleted", 0),
            "success": True,
        }

        return results

    except Exception as e:
        logger.error(f"💥 Erreur dans le workflow de nettoyage: {e}")
        results["error"] = str(e)
        results["summary"] = {"success": False}
        return results


def cleanup_workflow_sync(
    days: Optional[int] = None,
    enable_similarity_cleanup: bool = False,  # ✅ Désactivé par défaut
    enable_global_similarity: bool = True,  # ✅ Activé par défaut
    company_similarity_threshold: float = 0.75,
    position_similarity_threshold: float = 0.80,
    enable_old_offers_cleanup: bool = False,  # ✅ Purge aveugle par âge désactivée par défaut
):
    """✨ MODIFIÉ: Version synchrone avec mode global par défaut et sans purge aveugle par date"""
    return asyncio.run(
        cleanup_workflow(
            days=days,
            enable_similarity_cleanup=enable_similarity_cleanup,
            enable_global_similarity=enable_global_similarity,
            company_similarity_threshold=company_similarity_threshold,
            position_similarity_threshold=position_similarity_threshold,
            enable_old_offers_cleanup=enable_old_offers_cleanup,
        )
    )


# ✅ NOUVELLE FONCTION: Nettoyage préventif avant insertion (pour le crawler)
async def prevent_duplicate_insertion(new_offers: list) -> list:
    """Évite l'insertion de doublons en vérifiant contre toute la base"""
    if not new_offers:
        return []

    logger.info(f"🛡️ Vérification anti-doublon pour {len(new_offers)} nouvelles offres")

    db = await get_database()
    collection = db["job_offers"]

    # Récupérer toutes les offres existantes
    existing_offers = await collection.find({}).to_list(length=None)
    logger.info(f"📊 Comparaison contre {len(existing_offers)} offres existantes")

    if not existing_offers:
        return new_offers

    # Combiner nouvelles et existantes pour la détection
    all_offers = existing_offers + new_offers

    # Utiliser la fonction optimisée pour détecter les doublons
    cleaned_offers = clean_job_offer_duplicates_optimized(all_offers)

    # Identifier les nouvelles offres qui ont survécu au nettoyage
    existing_ids = {str(offer.get("_id", "")) for offer in existing_offers}
    surviving_new_offers = []

    for offer in cleaned_offers:
        offer_id = str(offer.get("_id", ""))
        if offer_id not in existing_ids:
            # C'est une nouvelle offre qui a survécu
            surviving_new_offers.append(offer)

    filtered_count = len(new_offers) - len(surviving_new_offers)
    logger.info(
        f"🛡️ Prévention doublons: {filtered_count} nouvelles offres filtrées, {len(surviving_new_offers)} à insérer"
    )

    return surviving_new_offers
