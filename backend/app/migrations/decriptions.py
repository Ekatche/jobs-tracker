import asyncio
import logging
import os
import pathlib
import sys
from pymongo import MongoClient
from dotenv import load_dotenv
from ..llm.utils import fetch_documents, split_documents, summarize_chunks

# Configuration du logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Chargement des variables d'environnement
dotenv_path = pathlib.Path(__file__).parent.parent.parent.parent / ".env"
load_dotenv(dotenv_path=dotenv_path)

# Vérification de la présence de la clé API OpenAI
if not os.getenv("OPENAI_API_KEY"):
    logger.error("OPENAI_API_KEY n'est pas définie dans les variables d'environnement")
    sys.exit(1)  # Arrêt du script avec code d'erreur

# Configuration de la connexion MongoDB
MONGO_USER = os.getenv("MONGO_USER")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD")
DATABASE_NAME = os.getenv("DATABASE_NAME")
MONGO_HOST = os.getenv("MONGO_HOST")

# Construction de l'URI de connexion
if not all([MONGO_USER, MONGO_PASSWORD, MONGO_HOST]):
    MONGO_URI = f"mongodb://localhost:27017/{DATABASE_NAME}"
    logger.warning("Utilisation de la configuration locale pour MongoDB")
else:
    MONGO_URI = f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}@{MONGO_HOST}:27017/{DATABASE_NAME}?authSource=admin"
    logger.info(f"Connexion à MongoDB sur {MONGO_HOST}")


async def generate_description_for_application(application):
    """Génère une description pour une candidature en utilisant son URL."""
    application_id = application["_id"]
    url = application.get("url")

    if not url:
        logger.warning(f"Pas d'URL fournie pour l'application {application_id}")
        return None

    company = application.get("company", "Entreprise")
    position = application.get("position", "Poste")

    logger.info(
        f"Génération de description pour {company} - {position} (ID: {application_id})"
    )

    # Récupération du contenu de la page
    docs = await fetch_documents(url)

    if not docs or len(docs) == 0:
        logger.warning(f"Aucun contenu récupéré depuis {url}")
        return None

    # Division du contenu en chunks pour traitement
    chunks = split_documents(docs)

    # Génération du résumé
    description = await summarize_chunks(chunks)

    # Vérifier si la description contient un message d'erreur
    if description and description.startswith("Erreur lors de la génération"):
        raise Exception(description)

    return description


async def process_applications_without_description():
    """
    Traite toutes les candidatures qui ont une URL mais pas de description,
    génère des descriptions et les enregistre dans la base de données.
    """
    client = None
    try:
        # Connexion à MongoDB
        client = MongoClient(MONGO_URI)
        db = client[DATABASE_NAME]
        collection = db["applications"]

        # Test de connexion
        db.command("ping")
        logger.info("Connexion à MongoDB établie avec succès")

        # Requête pour trouver les candidatures avec URL mais sans description
        query = {
            "url": {"$exists": True, "$nin": [None, ""]},
            "$or": [
                {"description": {"$exists": False}},
                {"description": None},
                {"description": ""},
            ],
        }

        # Récupération des candidatures correspondantes
        applications = list(collection.find(query))
        logger.info(
            f"Trouvé {len(applications)} candidatures sans description mais avec URL"
        )

        if not applications:
            logger.info("Aucune candidature à traiter. Fin du script.")
            return

        count_success = 0
        count_failed = 0

        # Traitement de chaque candidature
        for application in applications:
            application_id = application["_id"]

            try:
                description = await generate_description_for_application(application)

                if description:
                    # Mise à jour de la candidature avec la description générée
                    result = collection.update_one(
                        {"_id": application_id}, {"$set": {"description": description}}
                    )

                    if result.modified_count > 0:
                        logger.info(
                            f"Description mise à jour pour l'application {application_id}"
                        )
                        count_success += 1
                    else:
                        logger.warning(
                            f"Aucune modification pour l'application {application_id}"
                        )
                        count_failed += 1
                else:
                    logger.warning(f"Pas de description générée pour {application_id}")
                    count_failed += 1

            except Exception as e:
                logger.error(
                    f"Erreur critique lors du traitement de l'application {application_id}: {str(e)}"
                )
                # Arrêter complètement le script en cas d'erreur importante
                sys.exit(1)

        logger.info(
            f"Traitement terminé. Succès: {count_success}, Échecs: {count_failed}"
        )

    except Exception as e:
        logger.error(f"Erreur critique lors du traitement des candidatures: {str(e)}")
        sys.exit(1)  # Arrêt du script avec code d'erreur

    finally:
        if client:
            client.close()
            logger.info("Connexion MongoDB fermée")


async def main():
    """Fonction principale"""
    try:
        logger.info("Démarrage du processus de génération de descriptions")
        await process_applications_without_description()
        logger.info("Processus terminé avec succès")
    except Exception as e:
        logger.error(f"Erreur critique non gérée: {str(e)}")
        sys.exit(1)  # Arrêt du script avec code d'erreur


if __name__ == "__main__":
    asyncio.run(main())
