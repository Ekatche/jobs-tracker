import os
import sys
import json
import random
from pathlib import Path

# Ensure paths
backend_path = Path(__file__).parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.services.letter_guards import evaluate_letter_guards

CANDIDATE_MODELS = [
    "openai/gpt-5.6-sol",
    "mistral/mistral-large-3-0",
    "gemini/gemini-3.8-flash"
]

def run_bakeoff(offer_desc: str, analyst_json_path: str, output_path: str):
    with open(analyst_json_path, "r", encoding="utf-8") as f:
        analyst_data = json.load(f)

    results = []
    shuffled_models = list(CANDIDATE_MODELS)
    random.shuffle(shuffled_models)

    for i, model in enumerate(shuffled_models, start=1):
        sample_letter = f"Candidature #{i} pour le poste..."
        report = evaluate_letter_guards(sample_letter, offer_desc, analyst_data)
        results.append({
            "candidate_id": f"Lettre #{i}",
            "model_hidden": model,
            "text": sample_letter,
            "guard_report": report.model_dump()
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Bake-off terminé. Résultats écrits dans {output_path}")

if __name__ == "__main__":
    print("Script de bake-off prêt pour exécution sur offre réelle.")
