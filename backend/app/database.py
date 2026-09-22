import asyncio
import os
import pathlib

import motor.motor_asyncio
from dotenv import load_dotenv

# Chargement des variables d'environnement (cherche dans le dossier parent aussi)
dotenv_path = pathlib.Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=dotenv_path)

# Récupération des variables d'environnement pour MongoDB
MONGO_USER = os.getenv("MONGO_USER")
MONGO_PASSWORD = os.getenv("MONGO_PASSWORD")
DATABASE_NAME = os.getenv("DATABASE_NAME")
MONGO_HOST = os.getenv("MONGO_HOST")

# Vérifier que les variables nécessaires sont définies
if not all([MONGO_USER, MONGO_PASSWORD, DATABASE_NAME, MONGO_HOST]):
    print("ATTENTION: Variables d'environnement manquantes pour MongoDB")
    print(f"MONGO_USER: {'défini' if MONGO_USER else 'manquant'}")
    print(f"MONGO_PASSWORD: {'défini' if MONGO_PASSWORD else 'manquant'}")
    print(f"DATABASE_NAME: {'défini' if DATABASE_NAME else 'manquant'}")
    print(f"MONGO_HOST: {'défini' if MONGO_HOST else 'manquant'}")
    # Valeurs par défaut pour le développement
    MONGO_URI = "mongodb://localhost:27017/job_tracker"
else:
    MONGO_URI = f"mongodb://{MONGO_USER}:{MONGO_PASSWORD}@{MONGO_HOST}:27017/{DATABASE_NAME}?authSource=admin"

print(f"Connexion à: {MONGO_URI.replace(MONGO_PASSWORD or '', '****')}")

_client = None
_client_loop = None


def _get_client() -> motor.motor_asyncio.AsyncIOMotorClient:
    """Client Motor lié à la boucle d'événements courante.

    Motor capture la boucle active à sa première I/O. Airflow ouvre puis
    ferme une boucle neuve par étape : un client mis en cache au niveau
    module lève "Event loop is closed" dès la deuxième requête. On le
    reconstruit quand la boucle change, et on ferme l'ancien pour ne pas
    laisser fuir ses sockets et ses threads de fond.
    """
    global _client, _client_loop
    loop = asyncio.get_running_loop()
    if _client is None or _client_loop is not loop or _client_loop.is_closed():
        if _client is not None:
            _client.close()
        _client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
        _client_loop = loop
    return _client


# Fonction pour obtenir une instance de la base de données
async def get_database():  # Changé de get_() à get_database
    """
    Retourne une instance de la base de données MongoDB.
    Cette fonction est utilisée comme dépendance dans FastAPI.
    """
    return _get_client()[DATABASE_NAME]


async def create_job_offers_indexes(db):
    """Crée les index pour optimiser les requêtes sur les offres d'emploi"""
    collection = db["job_offers"]

    # Index sur l'URL unique partiel (évite les conflits sur les offres sans URL)
    await collection.create_index(
        "url",
        unique=True,
        partialFilterExpression={"url": {"$type": "string"}},
    )

    # Index unique sur la clé de déduplication calculée
    await collection.create_index(
        "unique_key",
        unique=True,
        sparse=True,
    )

    # Index de recherche textuelle
    await collection.create_index(
        [("poste", "text"), ("entreprise", "text"), ("localisation", "text")]
    )

    # Index sur les dates
    await collection.create_index("created_at")
    await collection.create_index("updated_at")

    # Index composé pour les filtres fréquents et soft-delete
    await collection.create_index([("is_deleted", 1), ("created_at", -1)])
    await collection.create_index([("localisation", 1), ("created_at", -1)])

    # Index sur le matching persistant profil <-> offre (filtre "Selon mon profil")
    await collection.create_index("matched_user_ids")
