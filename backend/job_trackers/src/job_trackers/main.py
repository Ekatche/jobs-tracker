#!/usr/bin/env python
import sys
import os
import logging
import warnings


current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from crew import JobTrackers, tavily_search
from models import FilteredJobOffersResult


warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

logger = logging.getLogger(__name__)


def run_crew(user_query: str) -> FilteredJobOffersResult:
    """Exécute la recherche et le filtrage d'offres d'emploi de façon déterministe.

    Pipeline en 3 étapes :
    1. Optimisation de la requête (query_converter LLM) -> OptimizedQueries
    2. Recherche Tavily déterministe en Python (0 hallucination d'agent, 100% fiable)
    3. Qualification et filtrage des URLs (url_filter LLM) -> FilteredJobOffersResult
    """
    try:
        tracker = JobTrackers()
        logger.info(f"🚀 Début de la recherche déterministe pour: '{user_query}'")

        # Étape 1 : Optimisation de la requête
        optimized = tracker.optimize_query(user_query)
        primary = optimized.primary_query if (optimized and optimized.primary_query) else user_query
        logger.info(f"🎯 Requête optimisée: '{primary}'")

        # Étape 2 : Appel Tavily direct et déterministe en Python
        raw_urls = tavily_search._run(query=primary)

        # Si la requête principale ne ramène rien mais qu'on a des variantes, repli
        if not raw_urls and optimized and optimized.alternative_queries:
            for alt in optimized.alternative_queries[:2]:
                logger.info(f"🔄 Repli sur requête alternative: '{alt}'")
                raw_urls = tavily_search._run(query=alt)
                if raw_urls:
                    break

        if not raw_urls:
            logger.warning(f"⚠️ Aucune URL trouvée par Tavily pour '{user_query}'")
            return FilteredJobOffersResult(urls=[], items=[])

        logger.info(f"🔎 {len(raw_urls)} URLs brutes trouvées par Tavily, filtrage en cours...")

        # Étape 3 : Filtrage et scoring LLM
        filtered = tracker.filter_urls(original_query=user_query, urls=raw_urls)
        logger.info(f"✅ {len(filtered.urls)} URLs retenues après filtrage")
        return filtered

    except Exception as e:
        logger.error(f"Erreur lors de l'exécution de la recherche: {e}")
        raise Exception(f"An error occurred while running the crew: {e}")


if __name__ == "__main__":
    # Example usage
    user_query = "Je recherche un poste de data scientist proche de Lyon"
    try:
        result = run_crew(user_query)
        print("Crew executed successfully:", result)
    except Exception as e:
        print("Error executing crew:", e)
