import asyncio
import os
import logging
from datetime import datetime, timezone
from app.services.job_offers import (
    get_urls,
    get_job_offers_from_query,
    clean_job_offer_duplicates,
)
from app.database import get_database
from pymongo import UpdateOne
from pymongo.errors import BulkWriteError
from app.services.normalization import compute_unique_key, extract_company_from_url
from app.services.relevance import (
    RELEVANCE_FILTER_ENABLED,
    is_off_domain_url,
    is_relevant_position,
)

# Borne par requête pour collect_offers_sync : 6 requêtes × 7 min = 42 min,
# sous l'execution_timeout de 45 min de la tâche Airflow. Sans cette borne,
# une requête qui pend consomme tout le budget et tue les 5 autres.
COLLECT_QUERY_TIMEOUT = 420


def setup_logger():
    """Configure le logger selon l'environnement"""
    env = os.getenv("ENVIRONMENT", "development")

    if env == "production":
        level = logging.WARNING
    elif env == "airflow":
        level = logging.INFO
    else:
        level = logging.DEBUG

    logger = logging.getLogger(__name__)
    logger.setLevel(level)
    return logger


logger = setup_logger()


# ========================================
# ======== FONCTIONS SPÉCIALISÉES ========
# ========================================


async def get_urls_for_query(query: str) -> list:
    """Étape 1: Récupération des URLs"""
    logger.info(f"🔍 Recherche d'URLs pour: {query}")

    # Vérifications des variables d'environnement
    required_env_vars = ["OPENAI_API_KEY", "TAVILY_API_KEY"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]

    if missing_vars:
        raise ValueError(f"Variables manquantes: {', '.join(missing_vars)}")

    try:
        urls = await get_urls(query)
        logger.info(f"✅ {len(urls)} URLs trouvées")

        if RELEVANCE_FILTER_ENABLED:
            kept_urls = []
            rejected_count = 0
            for url in urls:
                if is_off_domain_url(url):
                    logger.warning(
                        f"🚫 URL hors-domaine écartée: {url} (requête: '{query}')"
                    )
                    rejected_count += 1
                else:
                    kept_urls.append(url)
            logger.info(
                f"🚫 {rejected_count} URLs hors-domaine écartées, {len(kept_urls)} conservées"
            )
            urls = kept_urls

        return urls
    except Exception as e:
        logger.error(f"💥 Erreur récupération URLs: {e}")
        raise


async def crawl_urls_for_offers(urls: list) -> list:
    """Étape 2: Crawling des URLs pour extraire les offres"""
    logger.info(f"🕷️ Crawling de {len(urls)} URLs")

    if not urls:
        logger.warning("⚠️ Aucune URL à crawler")
        return []

    try:
        offers = await get_job_offers_from_query(urls)

        if not isinstance(offers, list):
            raise TypeError(f"Format invalide: {type(offers)}, attendu: list")

        logger.info(f"📊 {len(offers)} offres brutes récupérées")
        return offers
    except Exception as e:
        logger.error(f"💥 Erreur crawling: {e}")
        raise


async def enrich_offers(offers: list, query: str) -> list:
    """Étape 3: Enrichissement des offres avec métadonnées selon le modèle MongoDB"""
    logger.info(f"🔧 Enrichissement de {len(offers)} offres selon le modèle de données")

    if not offers:
        logger.warning("⚠️ Aucune offre à enrichir")
        return []

    try:
        enriched_offers = []
        invalid_count = 0
        off_domain_count = 0
        current_time = datetime.now(timezone.utc)

        # Traitement par batch
        batch_size = 20
        for batch_start in range(0, len(offers), batch_size):
            batch = offers[batch_start : batch_start + batch_size]

            for index, offer in enumerate(batch, batch_start + 1):
                try:
                    # Validation des champs requis
                    if not all(key in offer for key in ["poste", "entreprise"]):
                        logger.warning(f"⚠️ Offre invalide (champs manquants): {offer}")
                        invalid_count += 1
                        continue

                    # Nettoyage des champs texte de base
                    poste = str(offer.get("poste", "")).strip()
                    entreprise = str(offer.get("entreprise", "")).strip()
                    description = str(offer.get("description", "")).strip() or "Non spécifié"
                    localisation = str(offer.get("localisation", "")).strip()
                    date = str(offer.get("date", "")).strip()
                    type_contrat = str(offer.get("type_contrat", "")).strip()
                    salaire = str(offer.get("salaire", "")).strip()
                    mode_travail = str(offer.get("mode_travail", "")).strip()
                    competences_cles = offer.get("competences_cles", [])
                    if isinstance(competences_cles, str):
                        competences_cles = [c.strip() for c in competences_cles.split(",") if c.strip()]
                    elif not isinstance(competences_cles, list):
                        competences_cles = []

                    url = str(offer.get("url", "")).strip() or None
                    source_url = str(offer.get("source_url", "")).strip() or None

                    # Fallback nom d'entreprise depuis l'URL si manquant ou non spécifié
                    invalid_placeholders = {"non spécifié", "non disponible", "inconnu", "none", "null", "undefined", ""}
                    if (not entreprise or entreprise.lower() in invalid_placeholders) and (url or source_url):
                        fallback_company = extract_company_from_url(url or source_url)
                        if fallback_company:
                            logger.info(
                                f"🏢 Entreprise enrichie via fallback URL: '{fallback_company}' (était '{entreprise}')"
                            )
                            entreprise = fallback_company

                    # Rejet strict des offres avec champs obligatoires vides ou factices ("Non spécifié", 404, etc.)
                    if (
                        not poste
                        or not entreprise
                        or poste.lower() in invalid_placeholders
                        or entreprise.lower() in invalid_placeholders
                    ):
                        logger.warning(
                            f"⚠️ Offre rejetée (poste ou entreprise invalide/non spécifié): poste='{poste}', entreprise='{entreprise}'"
                        )
                        invalid_count += 1
                        continue

                    if RELEVANCE_FILTER_ENABLED and not is_relevant_position(poste):
                        logger.warning(
                            f"🚫 Offre hors-domaine rejetée: poste='{poste}' (requête: '{query}')"
                        )
                        off_domain_count += 1
                        continue

                    # Clé d'unicité normalisée
                    unique_key = compute_unique_key(
                        company=entreprise,
                        position=poste,
                        location=localisation,
                        url=url,
                    )

                    # ✅ Enrichissement selon le modèle MongoDB complet
                    enriched_offer = {
                        # ===== CHAMPS PRINCIPAUX =====
                        "poste": poste,
                        "entreprise": entreprise,
                        "description": description,
                        "localisation": (
                            localisation if localisation else "Non spécifié"
                        ),
                        "date": date if date else "Non spécifié",
                        "type_contrat": type_contrat if type_contrat else "Non spécifié",
                        "salaire": salaire if salaire else "Non spécifié",
                        "mode_travail": mode_travail if mode_travail else "Non spécifié",
                        "competences_cles": competences_cles,
                        "url": url,
                        "source_url": source_url,
                        "unique_key": unique_key,
                        # ===== MÉTADONNÉES DE COLLECTE =====
                        "source_query": query,
                        "created_at": current_time,
                        "updated_at": current_time,
                        # ===== CHAMPS DE GESTION =====
                        "is_deleted": False,  # Nouveau champ pour soft delete
                        "deleted_date": None,  # Date de suppression (None par défaut)
                        # ===== RAW DATA (données originales) =====
                        "raw_data": offer,
                    }

                    enriched_offers.append(enriched_offer)

                    # Log détaillé pour les premières offres (debug)
                    if index <= 3:
                        logger.debug(
                            f"🔍 Offre {index} enrichie: {enriched_offer['poste']} chez {enriched_offer['entreprise']}"
                        )

                except Exception as e:
                    logger.warning(f"⚠️ Erreur enrichissement offre {index}: {e}")
                    logger.debug(f"Offre problématique: {offer}")
                    invalid_count += 1
                    continue

        logger.info(
            f"✅ {len(enriched_offers)} offres enrichies selon le modèle MongoDB "
            f"({invalid_count} invalides, {off_domain_count} hors-domaine)"
        )

        return enriched_offers

    except Exception as e:
        logger.error(f"💥 Erreur enrichissement: {e}")
        raise


async def clean_duplicate_offers(offers: list) -> list:
    """Étape 4: Nettoyage des doublons (processus long)"""
    logger.info(f"🧹 Nettoyage des doublons sur {len(offers)} offres")

    if not offers:
        logger.warning("⚠️ Aucune offre à nettoyer")
        return []

    try:
        # Cette fonction peut être longue, d'où la séparation
        cleaned_offers = clean_job_offer_duplicates(
            offers, company_similarity_threshold=0.75, position_similarity_threshold=0.8
        )

        removed_count = len(offers) - len(cleaned_offers)
        logger.info(
            f"✅ Nettoyage terminé: {removed_count} doublons supprimés, {len(cleaned_offers)} offres conservées"
        )
        return cleaned_offers

    except Exception as e:
        logger.error(f"💥 Erreur nettoyage doublons: {e}")
        raise


async def save_offers_to_database(offers: list) -> dict:
    """Étape 6: Sauvegarde en base de données avec upsert non destructif"""
    logger.info(f"💾 Sauvegarde de {len(offers)} offres")

    if not offers:
        logger.warning("⚠️ Aucune offre à sauvegarder")
        return {"saved": 0, "updated": 0}

    try:
        db = await get_database()
        collection = db["job_offers"]

        saved_count = 0
        updated_count = 0
        error_count = 0

        # Traitement par batch pour la base de données
        db_batch_size = 10

        for batch_start in range(0, len(offers), db_batch_size):
            batch = offers[batch_start : batch_start + db_batch_size]
            operations = []

            for offer in batch:
                try:
                    unique_key = offer.get("unique_key") or compute_unique_key(
                        company=offer.get("entreprise", ""),
                        position=offer.get("poste", ""),
                        location=offer.get("localisation"),
                        url=offer.get("url"),
                    )

                    filter_clause = {"unique_key": unique_key}
                    if offer.get("url"):
                        filter_clause = {
                            "$or": [
                                {"url": offer["url"]},
                                {"unique_key": unique_key},
                            ]
                        }

                    # Isoler created_at pour ne jamais écraser la date de création d'une offre existante
                    offer_set_fields = {k: v for k, v in offer.items() if k not in {"created_at", "date_creation"}}
                    offer_set_fields["unique_key"] = unique_key
                    offer_set_fields["updated_at"] = datetime.now(timezone.utc)

                    operation = UpdateOne(
                        filter_clause,
                        {
                            "$set": offer_set_fields,
                            "$setOnInsert": {
                                "created_at": offer.get("created_at") or datetime.now(timezone.utc),
                            },
                        },
                        upsert=True,
                    )
                    operations.append(operation)

                except Exception as e:
                    logger.warning(f"⚠️ Erreur préparation offre: {e}")
                    error_count += 1
                    continue

            # Exécution du batch avec capture fine des erreurs
            if operations:
                try:
                    result = await collection.bulk_write(operations, ordered=False)
                    saved_count += result.upserted_count
                    updated_count += result.modified_count
                except BulkWriteError as bwe:
                    details = bwe.details or {}
                    saved_count += details.get("nUpserted", 0)
                    updated_count += details.get("nModified", 0)
                    write_errors = details.get("writeErrors", [])
                    error_count += len(write_errors)
                    logger.warning(f"⚠️ BulkWriteError partiel: {len(write_errors)} erreurs sur {len(operations)} opérations")
                except Exception as e:
                    logger.error(f"💥 Erreur sauvegarde batch: {e}")
                    error_count += len(operations)

        logger.info(
            f"✅ Sauvegarde terminée: {saved_count} créées, {updated_count} mises à jour"
        )

        if error_count > 0:
            logger.warning(f"⚠️ {error_count} erreurs lors de la sauvegarde")
            if saved_count == 0 and updated_count == 0:
                raise RuntimeError(
                    f"Sauvegarde totalement échouée: {error_count}/{len(offers)} offres perdues"
                )

        return {"saved": saved_count, "updated": updated_count}

    except Exception as e:
        logger.error(f"💥 Erreur sauvegarde: {e}")
        raise


async def cleanup_resources():
    """Étape 7: Nettoyage des ressources"""
    logger.info("🧹 Nettoyage des ressources")

    try:
        from app.services.job_offers import cleanup_shared_configs

        await cleanup_shared_configs()
        logger.info("✅ Ressources nettoyées")
    except Exception as e:
        logger.warning(f"⚠️ Erreur nettoyage: {e}")


# ========================================
# ======== FONCTIONS SYNC POUR AIRFLOW ===
# ========================================




def enrich_offers_sync(offers: list, query: str) -> list:
    """Version sync pour Airflow - Étape 3"""
    os.environ.setdefault("ENVIRONMENT", "airflow")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        return loop.run_until_complete(
            asyncio.wait_for(enrich_offers(offers, query), timeout=300)
        )
    finally:
        loop.close()




async def collect_and_save_offers(query: str) -> dict:
    """Version asynchrone complète pour collecter, nettoyer et enregistrer les offres"""
    logger.info(f"🚀 Collecte async démarrée: {query}")
    try:
        urls = await get_urls_for_query(query)
        offers = await crawl_urls_for_offers(urls)
        enriched = await enrich_offers(offers, query)
        cleaned = await clean_duplicate_offers(enriched)
        return await save_offers_to_database(cleaned)
    finally:
        await cleanup_resources()


def collect_offers_sync(query: str) -> dict:
    """Version sync pour Airflow — une seule boucle d'événements par requête."""
    os.environ.setdefault("ENVIRONMENT", "airflow")
    try:
        logger.info(f"🚀 Collecte complète démarrée: {query}")
        # 6 requêtes × 7 min = 42 min, sous l'execution_timeout de 45 min du DAG.
        # Sans cette borne, une requête qui pend consomme tout le budget de la tâche.
        result = asyncio.run(
            asyncio.wait_for(collect_and_save_offers(query), timeout=COLLECT_QUERY_TIMEOUT)
        )
        logger.info(f"🎯 Collecte terminée: {result}")
        return result
    except Exception as e:
        logger.error(f"💥 Erreur collecte complète: {e}")
        raise
