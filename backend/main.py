from contextlib import asynccontextmanager

import pymongo
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles


from app.database import get_database
from app.routers import auth_router, job_router, user_router, task_router


@asynccontextmanager
async def lifespan(app):
    # Code de démarrage (remplace on_event("startup"))
    try:
        # Test réel de la connexion avec une commande ping
        db = await get_database()
        await db.command("ping")
        print("Connexion à la base de données établie avec succès")

        # Créer les index nécessaires
        await db["users"].create_index([("username", pymongo.ASCENDING)], unique=True)
        await db["users"].create_index([("email", pymongo.ASCENDING)], unique=True)
    except Exception as e:
        print(f"Erreur de connexion à la base de données: {e}")

    yield  # L'application s'exécute pendant cette période

    # Code d'arrêt (remplace on_event("shutdown"))
    print("Connexion à la base de données fermée")


# Création de l'application FastAPI
app = FastAPI(
    title="Job Tracker API",
    description="API pour suivre vos candidatures d'emploi",
    version="1.0.0",
    lifespan=lifespan,  # Ajoutez le gestionnaire de cycle de vie ici
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restreindre en production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusion des routeurs
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(job_router)
app.include_router(task_router)

app.mount("/uploads", StaticFiles(directory="app/uploads"), name="uploads")


@app.get("/")
async def root():
    return {"message": "Bienvenue sur l'API Job Tracker"}


# Point d'entrée pour exécuter l'application directement
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Activer le rechargement automatique en développement
    )
