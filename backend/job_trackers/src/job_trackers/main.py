#!/usr/bin/env python
import warnings

from crew import JobTrackers

warnings.filterwarnings("ignore", category=SyntaxWarning, module="pysbd")

# This main file is intended to be a way for you to run your
# crew locally, so refrain from adding unnecessary logic into this file.
# Replace with inputs you want to test with, it will automatically
# interpolate any tasks and agents information


def run():
    """
    Run the crew.
    """
    inputs = {
        "user_query": "Je cherche un poste de data scientist à Lyon",
    }

    print(f"🚀 Démarrage du crew avec la requête: {inputs['user_query']}")

    try:
        # Récupérer et afficher explicitement le résultat
        result = JobTrackers().crew().kickoff(inputs=inputs)
        print("\n✅ Résultat final de l'exécution du crew:")
        print(result)
        return result
    except Exception as e:
        print(f"\n❌ ERREUR lors de l'exécution du crew: {e}")
        raise Exception(f"An error occurred while running the crew: {e}")


if __name__ == "__main__":
    run()
