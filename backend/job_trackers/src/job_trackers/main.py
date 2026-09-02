#!/usr/bin/env python
import sys
import os
import warnings


current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from crew import JobTrackers
from models import FilteredJobOffersResult


warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")


def run_crew(user_query: str):
    """Exécute le Crew JobTrackers pour une requête utilisateur."""
    try:
        inputs = {"user_query": user_query}
        result = JobTrackers().crew().kickoff(inputs=inputs)
        return result
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
