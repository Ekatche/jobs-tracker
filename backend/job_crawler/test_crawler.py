#!/usr/bin/env python3
import sys
import os
import asyncio
from pathlib import Path

# Ajouter le répertoire backend au path
backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))
from job_crawler.crawler1 import (
    crawl_and_extract_jobs_optimized,
    get_filtered_markdown,
)  # noqa: E402


async def test_crawl4ai():
    """Test simple du crawler"""
    print("🧪 Test du crawler...")

    # Vérifier la clé API
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY manquante")
        return

    # URLs de test
    urls = [
        "https://www.linkedin.com/jobs/search/?currentJobId=4231957565&keywords=data%20scientist&location=Lyon",
        "https://www.welcometothejungle.com/fr/pages/emploi-developpeur-python",
    ]

    try:
        result = await crawl_and_extract_jobs_optimized(urls, api_key=api_key)

        print("📊 Résultat:")
        print(f"  - resultat: {result.get('offers')} ")

        # Afficher les premières offres
        # offers = result.get("offers", [])
        # for i, offer in enumerate(offers[:3]):
        #     print(
        #         f"  {i + 1}. {offer.get('poste', 'N/A')} - {offer.get('entreprise', 'N/A')}"
        #     )

    except Exception as e:
        print(f"❌ Erreur: {e}")


async def test_get_filtered_markdown():
    """Test de la fonction get_filtered_markdown"""
    print("🧪 Test de get_filtered_markdown...")
    # Vérifier la clé API
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY manquante")
        return

    url = "https://galderma.wd3.myworkdayjobs.com/fr-FR/External/job/Alby/Data-Analyst_JR014026-1"

    # Appel de la fonction
    try:

        result = await get_filtered_markdown(url, api_key)

        print("📋 URLs filtrées:")
        print(result)

    except Exception as e:
        print(f"❌ Erreur: {e}")


if __name__ == "__main__":
    # asyncio.run(test_crawl4ai())
    asyncio.run(test_get_filtered_markdown())
