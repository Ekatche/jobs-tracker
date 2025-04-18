import motor.motor_asyncio
import os
from dotenv import load_dotenv
import pathlib

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

# Client MongoDB
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)


# Fonction pour obtenir une instance de la base de données
async def get_database():  # Changé de get_() à get_database
    """
    Retourne une instance de la base de données MongoDB.
    Cette fonction est utilisée comme dépendance dans FastAPI.
    """
    return client[DATABASE_NAME]
