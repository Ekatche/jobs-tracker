#!/usr/bin/env python3
import asyncio
import sys
import logging
from pathlib import Path

# ✅ Configuration du chemin vers la racine du backend
script_dir = Path(__file__).parent.absolute()
# Remonter jusqu'à la racine du backend : tests -> tasks -> app -> backend
backend_root = script_dir.parent.parent.parent
sys.path.insert(0, str(backend_root))

print(f"📁 Script directory: {script_dir}")
print(f"📁 Backend root: {backend_root}")
print(f"📁 Sys.path[0]: {sys.path[0]}")

# Configuration des logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            str(backend_root / "test_workflow.log")
        ),  # ✅ Log dans backend root
    ],
)

logger = logging.getLogger(__name__)


async def test_complete_workflow():
    """Test du workflow complet"""
    try:
        logger.info("🚀 Test du workflow complet...")

        # Importer la fonction
        from app.tasks.job_offers_collectors import collect_and_save_offers

        # Test avec une requête simple d'abord
        test_queries = [
            "je suis a la recherche d'un poste de développeur Python proche de toulouse"
        ]  # Commencer par une seule requête

        results = {}

        for query in test_queries:
            logger.info(f"📝 Test avec requête: {query}")

            try:
                result = await collect_and_save_offers(query)
                results[query] = result
                logger.info(f"✅ Résultat pour '{query}': {result}")

            except Exception as e:
                logger.error(f"❌ Erreur pour '{query}': {e}")
                import traceback

                traceback.print_exc()
                results[query] = {"error": str(e)}

        return results

    except Exception as e:
        logger.error(f"❌ Test workflow échoué: {e}")
        import traceback

        traceback.print_exc()
        raise


async def main():
    """Fonction principale de test"""
    try:
        logger.info("=" * 60)
        logger.info("🧪 TESTS DU WORKFLOW JOB TRACKER")
        logger.info("=" * 60)

        # ✅ Vérifier que le répertoire app existe
        app_dir = Path(sys.path[0]) / "app"
        if not app_dir.exists():
            logger.error(f"❌ Répertoire app introuvable: {app_dir}")
            logger.warning(
                f"📁 Contenu du backend root: {list(Path(sys.path[0]).iterdir())}"
            )
            return
        else:
            logger.info(f"✅ Répertoire app trouvé: {app_dir}")

    except Exception as e:
        logger.error(f"❌ Erreur critique: {e}")
        import traceback

        traceback.print_exc()


async def get_offer_fitmarkdown():
    """Récupérer la mardown d'une offre"""
    try:
        from job_crawler import get_filtered_markdown

        url = "https://mon-vie-via.businessfrance.fr/offres/226007"
        result = await get_filtered_markdown(url)
        logger.info(f"Markdown récupéré: {result.get('fit_markdown')[:100]}")

    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la description: {e}")
        return "Erreur lors de la récupération de la description"


if __name__ == "__main__":
    # asyncio.run(main())
    asyncio.run(get_offer_fitmarkdown())
