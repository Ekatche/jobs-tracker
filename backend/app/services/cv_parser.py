import fitz  # PyMuPDF
import json
from litellm import completion
from typing import Dict, Any

# Définition du schéma attendu
PROFILE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string", "description": "Titre professionnel (ex: Ingénieur Data & IA)"},
        "summary": {"type": "string", "description": "Résumé court (3-4 phrases) des compétences et expériences clés"},
        "experiences": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company": {"type": "string"},
                    "role": {"type": "string"},
                    "start": {"type": "string", "description": "Année de début"},
                    "end": {"type": "string", "description": "Année de fin ou null si en cours"},
                    "missions": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "stack": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["company", "role"]
            }
        },
        "projects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "stack": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                }
            }
        },
        "education": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "school": {"type": "string"},
                    "degree": {"type": "string"},
                    "years": {"type": "string"}
                }
            }
        },
        "skills": {
            "type": "object",
            "description": "Dictionnaire des compétences classées par catégories (ex: langages, cloud, bases, mlops)",
            "additionalProperties": {
                "type": "array",
                "items": {"type": "string"}
            }
        }
    },
    "required": ["headline", "summary", "experiences", "skills"]
}

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extrait le texte d'un PDF en conservant la structure."""
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text() + "\n\n"
    return text

def parse_cv_with_llm(cv_text: str, model: str = "gemini/gemini-3.8-flash") -> Dict[str, Any]:
    """Parse le texte du CV avec le LLM pour extraire les données structurées."""
    prompt = f"""
Voici le texte brut d'un CV (curriculum vitae).
Ton rôle est d'extraire les informations sous format JSON strictement structuré.

Texte du CV :
-----------------
{cv_text}
-----------------

Instructions :
- Remplis tous les champs du schéma JSON demandé.
- Sois synthétique pour le 'summary'.
- Pour les 'experiences', regroupe bien les missions et la 'stack' (technologies utilisées).
- Si des données sont absentes (ex: projets), renvoie une liste vide [].
"""

    try:
        response = completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        content = response.choices[0].message.content.strip()
        # Fallback pour supprimer les balises markdown si le modèle les inclut malgré le json_object
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        return json.loads(content)
    except Exception as e:
        print(f"Erreur LLM Parsing CV: {e}")
        raise e
