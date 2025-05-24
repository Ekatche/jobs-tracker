#!/usr/bin/env python3
import sys
import os
import asyncio
from pathlib import Path

# Ajouter le répertoire backend au path
backend_root = Path(__file__).parent.parent
sys.path.insert(0, str(backend_root))
from job_crawler.crawler1 import crawl_and_extract_jobs  # noqa: E402


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
        "https://www.hellowork.com/fr-fr/emploi/metier_developpeur-python.html",
        "https://www.welcometothejungle.com/fr/pages/emploi-developpeur-python",
    ]

    try:
        result = await crawl_and_extract_jobs(urls, api_key=api_key)

        print("📊 Résultat:")
        print(f"  - Type: {type(result)}")
        print(f"  - Offres trouvées: {len(result.get('offers', []))}")
        print(f"  - Echantillon: {result.get('offers', [])[:3]}")

        # Afficher les premières offres
        offers = result.get("offers", [])
        for i, offer in enumerate(offers[:3]):
            print(
                f"  {i + 1}. {offer.get('poste', 'N/A')} - {offer.get('entreprise', 'N/A')}"
            )

    except Exception as e:
        print(f"❌ Erreur: {e}")


if __name__ == "__main__":
    asyncio.run(test_crawl4ai())
