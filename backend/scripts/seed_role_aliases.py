"""Script one-shot pour initialiser et pré-remplir la collection MongoDB `role_aliases`.

Ce script configure les index (`variants` et `canonical`) et insère une taxonomie
de rôles tech avec leurs variantes courantes (français / anglais) et leurs embeddings.

Usage manuel :
    uv run python scripts/seed_role_aliases.py
    ou
    docker exec jobtracker-backend python scripts/seed_role_aliases.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Assure que le dossier parent (backend) est dans le PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import get_database
from app.services.role_normalizer import (
    EMBEDDING_MODEL,
    ensure_role_aliases_indexes,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Taxonomie initiale de rôles tech courants et leurs variantes courantes FR + EN
INITIAL_TECH_ROLES = [
    {
        "canonical": "Data Engineer",
        "variants": [
            "data engineer",
            "ingénieur data",
            "ingénieur de données",
            "ingenieur data",
            "data engineering",
        ],
    },
    {
        "canonical": "Data Scientist",
        "variants": [
            "data scientist",
            "scientifique des données",
            "chercheur data",
            "data science",
        ],
    },
    {
        "canonical": "Data Analyst",
        "variants": [
            "data analyst",
            "analyste de données",
            "analyste data",
            "data analytics",
        ],
    },
    {
        "canonical": "Machine Learning Engineer",
        "variants": [
            "machine learning engineer",
            "ml engineer",
            "ingénieur machine learning",
            "ingénieur ml",
            "machine learning",
        ],
    },
    {
        "canonical": "AI Engineer",
        "variants": [
            "ai engineer",
            "ingénieur ia",
            "ingenieur ia",
            "artificial intelligence engineer",
            "ingénieur en intelligence artificielle",
        ],
    },
    {
        "canonical": "LLM Engineer",
        "variants": [
            "llm engineer",
            "ingénieur llm",
            "ia générative",
            "generative ai engineer",
            "genai engineer",
            "ingénieur ia générative",
        ],
    },
    {
        "canonical": "MLOps Engineer",
        "variants": [
            "mlops engineer",
            "ingénieur mlops",
            "mlops",
            "machine learning ops",
        ],
    },
    {
        "canonical": "DevOps Engineer",
        "variants": [
            "devops engineer",
            "ingénieur devops",
            "devops",
            "cloud devops",
        ],
    },
    {
        "canonical": "Cloud Architect",
        "variants": [
            "cloud architect",
            "architecte cloud",
            "cloud engineer",
            "ingénieur cloud",
        ],
    },
    {
        "canonical": "Software Engineer",
        "variants": [
            "software engineer",
            "ingénieur logiciel",
            "développeur logiciel",
            "ingenieur logiciel",
        ],
    },
    {
        "canonical": "Backend Developer",
        "variants": [
            "backend developer",
            "développeur backend",
            "dev backend",
            "developpeur back-end",
            "back-end developer",
        ],
    },
    {
        "canonical": "Frontend Developer",
        "variants": [
            "frontend developer",
            "développeur frontend",
            "dev frontend",
            "developpeur front-end",
            "front-end developer",
        ],
    },
    {
        "canonical": "Fullstack Developer",
        "variants": [
            "fullstack developer",
            "développeur fullstack",
            "dev fullstack",
            "developpeur full-stack",
            "full-stack developer",
        ],
    },
    {
        "canonical": "Python Developer",
        "variants": [
            "python developer",
            "développeur python",
            "dev python",
            "python engineer",
        ],
    },
    {
        "canonical": "Cybersecurity Engineer",
        "variants": [
            "cybersecurity engineer",
            "ingénieur cybersécurité",
            "sécurité informatique",
            "cyber security",
            "expert cybersécurité",
        ],
    },
    {
        "canonical": "Product Manager",
        "variants": [
            "product manager",
            "chef de produit",
            "pm",
            "product management",
        ],
    },
    {
        "canonical": "Product Owner",
        "variants": [
            "product owner",
            "po",
        ],
    },
    {
        "canonical": "Scrum Master",
        "variants": [
            "scrum master",
            "coach agile",
            "agile coach",
        ],
    },
    {
        "canonical": "QA Engineer",
        "variants": [
            "qa engineer",
            "ingénieur qa",
            "testeur qa",
            "quality assurance",
            "ingénieur test et validation",
        ],
    },
    {
        "canonical": "Data Architect",
        "variants": [
            "data architect",
            "architecte de données",
            "architecte data",
        ],
    },
    {
        "canonical": "Site Reliability Engineer",
        "variants": [
            "site reliability engineer",
            "sre",
            "ingénieur sre",
        ],
    },
    {
        "canonical": "Business Intelligence Developer",
        "variants": [
            "bi developer",
            "développeur bi",
            "consultant bi",
            "business intelligence",
        ],
    },
    {
        "canonical": "Computer Vision Engineer",
        "variants": [
            "computer vision engineer",
            "ingénieur vision par ordinateur",
            "vision par ordinateur",
        ],
    },
    {
        "canonical": "NLP Engineer",
        "variants": [
            "nlp engineer",
            "ingénieur nlp",
            "traitement automatique du langage",
        ],
    },
]


async def seed_role_aliases():
    """Pré-remplit les rôles et leurs variantes dans MongoDB de manière idempotente."""
    from litellm import aembedding

    db = await get_database()
    collection = db["role_aliases"]

    logger.info("🔧 Vérification et création des index...")
    await ensure_role_aliases_indexes(db)

    inserted_count = 0
    updated_count = 0

    for item in INITIAL_TECH_ROLES:
        canonical = item["canonical"]
        variants = list(
            set([canonical.lower().strip()] + [v.lower().strip() for v in item["variants"]])
        )

        existing = await collection.find_one({"canonical": canonical})

        if existing:
            # Met à jour les variantes connues
            await collection.update_one(
                {"_id": existing["_id"]},
                {"$addToSet": {"variants": {"$each": variants}}},
            )
            updated_count += 1
            logger.info(f"🔄 Rôle '{canonical}' déjà présent, variantes synchronisées.")
        else:
            # Calcule l'embedding et insère le nouveau rôle canonique
            logger.info(f"✨ Calcul embedding pour '{canonical}'...")
            resp = await aembedding(model=EMBEDDING_MODEL, input=[canonical])
            item_data = resp.data[0] if hasattr(resp, "data") else resp["data"][0]
            embedding = (
                item_data.get("embedding")
                if isinstance(item_data, dict)
                else getattr(item_data, "embedding", item_data["embedding"])
            )

            await collection.insert_one(
                {
                    "canonical": canonical,
                    "embedding": embedding,
                    "variants": variants,
                }
            )
            inserted_count += 1
            logger.info(f"✅ Rôle '{canonical}' inséré avec {len(variants)} variantes.")

    total = await collection.count_documents({})
    logger.info(
        f"🎉 Seeding terminé: {inserted_count} insérés, {updated_count} mis à jour. Total documents: {total}"
    )


if __name__ == "__main__":
    asyncio.run(seed_role_aliases())
