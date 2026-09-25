#!/usr/bin/env python
import sys
import os
import logging
import warnings


current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from crew import JobTrackers, tavily_search


warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

logger = logging.getLogger(__name__)


# Un agent qui répond sans appeler l'outil invente des URLs (pages de recherche,
# domaines périmés) : on relance une fois, puis on échoue plutôt que de les crawler.
MAX_CREW_ATTEMPTS = 2


def search_tool_was_called(crew) -> bool:
    """Vrai si un agent du crew a réellement exécuté l'outil de recherche Tavily."""
    return any(
        result.get("tool_name") == tavily_search.name
        for agent in crew.agents
        for result in (agent.tools_results or [])
    )


def run_crew(user_query: str):
    """Exécute le Crew JobTrackers pour une requête utilisateur."""
    try:
        inputs = {"user_query": user_query}
        for attempt in range(1, MAX_CREW_ATTEMPTS + 1):
            crew = JobTrackers().crew()
            result = crew.kickoff(inputs=inputs)
            if search_tool_was_called(crew):
                return result
            logger.warning(
                f"⚠️ Outil de recherche non appelé (essai {attempt}/{MAX_CREW_ATTEMPTS}) : URLs ignorées"
            )
        raise RuntimeError("l'agent de recherche n'a pas appelé l'outil Tavily")
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")


if __name__ == "__main__":
    # Example usage
    user_query = "Je recherche un poste de data scientist proche de Lyon"
    try:
        result = run_crew(user_query)
        print("Crew executed successfully:", result)
    except Exception as e:
        print("Error executing crew:", e)
