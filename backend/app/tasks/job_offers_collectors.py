import asyncio
import os
from datetime import datetime, timezone
from app.services.job_offers import get_job_offers_from_query
from app.database import get_database
import logging


# ✅ Configuration intelligente des logs
def setup_logger():
    """Configure le logger selon l'environnement"""
    env = os.getenv("ENVIRONMENT", "development")

    if env == "production":
        level = logging.WARNING  # ✅ Seulement WARNING et ERROR en prod
    elif env == "airflow":
        level = logging.INFO  # ✅ INFO pour Airflow (monitoring)
    else:
        level = logging.DEBUG  # ✅ DEBUG pour développement local

    logger = logging.getLogger(__name__)
    logger.setLevel(level)
    return logger


logger = setup_logger()


async def collect_and_save_offers(query: str):
    """Collecte et sauvegarde les offres d'emploi - Version optimisée logs"""
    try:
        logger.info(f"🚀 Collecte démarée: {query}")  # ✅ Log essentiel uniquement

        # Vérifications
        required_env_vars = ["OPENAI_API_KEY", "TAVILY_API_KEY"]
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]

        if missing_vars:
            raise ValueError(f"Variables manquantes: {', '.join(missing_vars)}")

        # ✅ Timeout interne pour éviter les blocages
        try:
            offers = await asyncio.wait_for(
                get_job_offers_from_query(query), timeout=900  # 15 minutes max
            )
        except asyncio.TimeoutError:
            logger.error("⏰ Timeout lors de la collecte des offres")
            raise Exception("Timeout de collecte dépassé")

        if not isinstance(offers, list):
            raise TypeError(f"Format invalide: {type(offers)}")

        logger.info(f"📊 {len(offers)} offres récupérées")  # ✅ Métrique importante

        if not offers:
            logger.warning("⚠️ Aucune offre trouvée")
            return {"saved": 0, "updated": 0}

        # ✅ Traitement avec logs réduits
        enriched_offers = []
        invalid_count = 0

        for i, offer in enumerate(offers):
            try:
                if not isinstance(offer, dict):
                    invalid_count += 1
                    continue

                url = offer.get("url") or offer.get("source_url") or ""

                # ✅ Accepter même sans URL valide (ne pas skip systématiquement)
                if url and not url.startswith("http"):
                    url = None  # Standardiser plutôt que rejeter

                enriched_offer = {
                    "poste": str(offer.get("poste") or "Poste non spécifié"),
                    "entreprise": str(
                        offer.get("entreprise") or "Entreprise non spécifiée"
                    ),
                    "localisation": offer.get("localisation"),
                    "date": offer.get("date"),
                    "url": url,
                    "source_url": offer.get("source_url"),
                    "updated_at": datetime.now(timezone.utc),
                    "source_query": query,
                    "offer_id": str(offer.get("id", "")),
                    "raw_data": offer,
                }
                enriched_offers.append(enriched_offer)

            except Exception as e:
                invalid_count += 1
                logger.error(f"💥 Erreur Enrichissement: {e}")
                # ✅ Log groupé plutôt qu'individuel
                continue

        # ✅ Log de résumé plutôt que détaillé
        if invalid_count > 0:
            logger.warning(f"⚠️ {invalid_count} offres invalides ignorées")

        if not enriched_offers:
            logger.warning("⚠️ Aucune offre valide après enrichissement")
            return {"saved": 0, "updated": 0}

        # logger.info(f"✅ {len(enriched_offers)} offres enrichies")

        # ✅ Sauvegarde optimisée
        db = await get_database()
        collection = db["job_offers"]

        saved_count = 0
        updated_count = 0
        error_count = 0

        for offer in enriched_offers:
            try:
                # ✅ Filtre intelligent pour éviter doublons
                if offer.get("url"):
                    query_filter = {"url": offer["url"]}
                else:
                    query_filter = {
                        "poste": offer["poste"],
                        "entreprise": offer["entreprise"],
                        "localisation": offer["localisation"],
                    }

                # ✅ Correction du conflit created_at
                current_time = datetime.now(timezone.utc)

                result = await collection.update_one(
                    query_filter,
                    {
                        "$set": {
                            "poste": offer["poste"],
                            "entreprise": offer["entreprise"],
                            "localisation": offer["localisation"],
                            "date": offer["date"],
                            "url": offer["url"],
                            "source_url": offer["source_url"],
                            "updated_at": current_time,
                            "source_query": offer["source_query"],
                            "offer_id": offer["offer_id"],
                            "raw_data": offer["raw_data"],
                        },
                        "$setOnInsert": {"created_at": current_time},
                    },
                    upsert=True,
                )

                if result.upserted_id:
                    saved_count += 1
                else:
                    updated_count += 1

            except Exception as e:
                error_count += 1
                logger.error(f"💥 Erreur Enrichissement : {e}")
                continue

        # ✅ Log final de résumé uniquement
        logger.info(f"🎯 Terminé: {saved_count} créées, {updated_count} mises à jour")

        if error_count > 0:
            logger.warning(f"⚠️ {error_count} erreurs de sauvegarde")

        return {"saved": saved_count, "updated": updated_count}

    except Exception as e:
        logger.error(f"💥 Erreur collecte: {e}")
        raise


def collect_offers_sync(query: str):
    """Version synchrone pour Airflow"""
    try:
        # ✅ Définir l'environnement pour Airflow
        os.environ.setdefault("ENVIRONMENT", "airflow")
        # ✅ Utiliser un event loop avec timeout
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            return loop.run_until_complete(
                asyncio.wait_for(
                    collect_and_save_offers(query), timeout=900  # 10 minutes max
                )
            )
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"💥 Erreur sync: {e}")
        raise
