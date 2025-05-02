import logging
import os
import pathlib
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient
from dotenv import load_dotenv

# Configuration du logging standard
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Chargement des variables d'environnement
dotenv_path = pathlib.Path(__file__).parent.parent.parent.parent / ".env"
load_dotenv(dotenv_path=dotenv_path)

# Configuration de la connexion MongoDB
MONGO_USER = os.getenv("MONGO_USER")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD")
DATABASE_NAME = os.getenv("DATABASE_NAME")
MONGO_HOST = os.getenv("MONGO_HOST")

# Nombre de jours après lesquels une candidature est considérée comme "vieille"
DAYS_THRESHOLD = 40  # au lieu de 45 jours


def log_message(message):
    """Log un message (anciennement envoyé à RabbitMQ)"""
    logger.info(f"MESSAGE: {message}")
    return True


def log_and_queue(level, message, **extra_data):
    """Journalise sans envoyer à RabbitMQ"""
    # Préparer le message enrichi
    full_message = f"{message} | {extra_data if extra_data else ''}"

    # Log standard
    if level == "INFO":
        logger.info(full_message)
    elif level == "WARNING":
        logger.warning(full_message)
    elif level == "ERROR":
        logger.error(full_message)


def archive_old_applications():
    """
    Recherche et archive les candidatures plus anciennes que 45 jours
    qui sont dans les états "refusé" ou "candidature envoyée"
    """
    client = None
    try:
        # Connexion à MongoDB
        if not all([MONGO_USER, MONGO_PASSWORD, MONGO_HOST]):
            MONGO_URI = f"mongodb://localhost:27017/{DATABASE_NAME}"
            log_and_queue(
                "WARNING", "Utilisation de la configuration locale pour MongoDB"
            )
        else:
            MONGO_URI = f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}@{MONGO_HOST}:27017/{DATABASE_NAME}?authSource=admin"
            log_and_queue("INFO", f"Connexion à MongoDB sur {MONGO_HOST}")

        client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=6000,
            connectTimeoutMS=5000,
            socketTimeoutMS=10000,
        )
        db = client[DATABASE_NAME]

        # Calculer l'âge des candidatures en jours
        today = datetime.now(timezone.utc)

        cutoff_date_naive = (today - timedelta(days=DAYS_THRESHOLD)).replace(
            tzinfo=None
        )
        log_and_queue("INFO", f"Date actuelle: {today.isoformat()}")
        # Convertir la date limite en chaîne de caractères pour comparer avec des strings
        cutoff_date_str = cutoff_date_naive.isoformat()
        log_and_queue(
            "INFO", f"Date limite d'archivage (format chaîne): {cutoff_date_str}"
        )

        # Requête adaptée pour les dates stockées en format string
        query = {
            "$and": [
                {
                    "$or": [
                        # Comparaison lexicographique pour les chaînes de caractères
                        {"application_date": {"$lt": cutoff_date_str}},
                        # Au cas où certaines dates sont stockées comme objets Date
                        {"application_date": {"$lt": cutoff_date_naive}},
                    ]
                },
                {"status": {"$in": ["Refusée", "Candidature envoyée"]}},
                {"archived": {"$ne": True}},
            ]
        }

        # Log de la requête pour debug
        log_and_queue("INFO", f"Requête MongoDB: {str(query)}")

        # Compter le nombre de candidatures à archiver
        count = db["applications"].count_documents(query)
        log_and_queue("INFO", f"Nombre de candidatures à archiver: {count}")

        # Si aucune candidature trouvée, faire l'échantillonnage
        if count == 0:
            # Examiner toutes les candidatures pour comprendre pourquoi
            non_archived = db["applications"].count_documents(
                {"archived": {"$ne": True}}
            )
            log_and_queue(
                "INFO", f"Total de candidatures non archivées: {non_archived}"
            )

            # Regarder les statuts disponibles
            status_pipeline = [
                {"$match": {"archived": {"$ne": True}}},
                {"$group": {"_id": "$status", "count": {"$sum": 1}}},
            ]
            statuses = list(db["applications"].aggregate(status_pipeline))
            log_and_queue("INFO", f"Distribution des statuts: {statuses}")

            log_and_queue("INFO", "Aucune candidature à archiver", count=0)
            return 0

        # Archivage normal
        # Récupérer les candidatures à archiver
        applications = list(db["applications"].find(query))

        # Liste pour stocker les IDs des candidatures archivées
        archived_ids = []

        # Archiver chaque candidature
        for app in applications:
            app_id = app["_id"]
            company = app.get("company", "Entreprise inconnue")
            position = app.get("position", "Poste inconnu")
            app_date = app.get("application_date", "Date inconnue")

            # Mettre à jour le statut "archived"
            result = db["applications"].update_one(
                {"_id": app_id},
                {"$set": {"archived": True, "updated_at": datetime.now(timezone.utc)}},
            )

            if result.modified_count > 0:
                log_and_queue(
                    "INFO", f"Candidature archivée: {company} - {position} ({app_date})"
                )
                archived_ids.append(str(app_id))
            else:
                log_and_queue(
                    "WARNING", f"Échec de l'archivage: {company} - {position}"
                )

        # Envoyer un message de résumé
        log_and_queue(
            "INFO",
            f"Archivage terminé: {len(archived_ids)} candidatures archivées sur {count}",
            count=len(archived_ids),
            archived_ids=archived_ids,
        )

        return len(archived_ids)

    except Exception as e:
        error_message = f"Erreur lors de l'archivage des candidatures: {str(e)}"
        log_and_queue("ERROR", error_message)
        return -1

    finally:
        if client:
            client.close()
            log_and_queue("INFO", "Connexion MongoDB fermée")


if __name__ == "__main__":
    # Pour les tests manuels
    result = archive_old_applications()
    log_and_queue("INFO", f"Résultat de l'archivage: {result} candidatures archivées")
