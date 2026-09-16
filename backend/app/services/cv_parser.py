import asyncio
import base64
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from litellm import acompletion

logger = logging.getLogger(__name__)

# Définition du schéma attendu pour la validation et l'extraction
PROFILE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string", "description": "Titre professionnel (ex: Senior Data & ML Engineer)"},
        "summary": {"type": "string", "description": "Résumé factuel (3-4 phrases) des compétences clés et de la trajectoire"},
        "experiences": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "company": {"type": "string"},
                    "role": {"type": "string"},
                    "location": {"type": "string"},
                    "contract": {"type": "string"},
                    "start": {"type": "string", "description": "Date de début (ex: 2022, 09/2021)"},
                    "end": {"type": "string", "description": "Date de fin ou null si en cours"},
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
                    "context": {"type": "string", "description": "perso, client, recherche ou consortium"},
                    "stack": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "url": {"type": "string"}
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
        "certifications": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "issuer": {"type": "string"},
                    "year": {"type": "string"}
                }
            }
        },
        "skills": {
            "type": "object",
            "description": "Dictionnaire des compétences classées par catégories (ex: languages, frameworks, devops, data_ai, tools)",
            "additionalProperties": {
                "type": "array",
                "items": {"type": "string"}
            }
        }
    },
    "required": ["headline", "summary", "experiences", "skills"]
}


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extrait le texte brut d'un PDF en conservant la structure basique."""
    import fitz  # PyMuPDF

    doc = fitz.open(pdf_path)
    try:
        return "\n\n".join(page.get_text() for page in doc)
    finally:
        doc.close()


def render_pdf_pages_to_base64_images(pdf_path: str, max_pages: int = 3, dpi: int = 150) -> List[str]:
    """Rend les pages du PDF sous forme d'images PNG encodées en base64 pour analyse VLM.
    
    Permet au modèle visuel de capturer fidèlement la mise en page (colonnes,
    badges graphiques, timelines, blocs de compétences) que l'extraction texte
    brute a tendance à désordonner.
    """
    import fitz  # PyMuPDF

    doc = fitz.open(pdf_path)
    images: List[str] = []
    try:
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            pix = page.get_pixmap(dpi=dpi)
            png_bytes = pix.tobytes("png")
            images.append(base64.b64encode(png_bytes).decode("utf-8"))
        return images
    finally:
        doc.close()


async def parse_cv_with_vlm(
    base64_images: List[str],
    model: str = "mistral/mistral-medium-3-5-26-04",
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Extrait les informations structurées d'un CV via un Vision Language Model.

    pixtral-12b-2409 est déprécié depuis le 2/12/2025. Son remplacement direct
    (Ministral 3 14B) n'a pas de preuve chiffrée de parité vision/OCR publiée.
    On utilise donc Mistral Medium 3.5, le modèle multimodal frontier-class actif
    de Mistral — remplacement officiel de Pixtral Large (lui-même déprécié le
    27/2/2026), plus cher mais avec une qualité vision nettement établie.
    """
    if not base64_images:
        raise ValueError("Aucune image de page PDF fournie pour l'analyse VLM")

    key = api_key or os.environ.get("MISTRAL_API_KEY")
    if not key and model.startswith("mistral/"):
        raise ValueError("MISTRAL_API_KEY manquante pour l'analyse VLM Mistral")

    instruction_text = """Voici les pages numérisées d'un CV de candidat.
Analyse attentivement la disposition visuelle, les colonnes multiples, les encarts latéraux et les badges techniques.
Extrais les faits réels sans rien inventer sous format JSON strict avec les clés :
- "headline": Titre professionnel du candidat (ex: 'Senior Data Engineer & AI Specialist')
- "summary": Synthèse percutante du parcours et des compétences clés
- "experiences": [
    {
      "company": "Entreprise",
      "role": "Poste occupé",
      "location": "Lieu (ex: Paris, Remote)",
      "contract": "CDI / Freelance / Alternance / Stage",
      "start": "Date début",
      "end": "Date fin ou null si poste actuel",
      "missions": ["Réalisation concrète ou responsabilité chiffrée"],
      "stack": ["Techno ou outil utilisé"]
    }
  ]
- "projects": [
    {
      "name": "Nom du projet",
      "description": "Description succincte",
      "context": "perso",
      "stack": ["Techno"],
      "url": "Lien si présent"
    }
  ]
- "education": [{"school": "École/Université", "degree": "Diplôme", "years": "Période"}]
- "certifications": [{"name": "Nom", "issuer": "Organisme", "year": "Année"}]
- "skills": {
    "languages": ["Python", "SQL", ...],
    "frameworks": ["FastAPI", "React", ...],
    "data_ai": ["PyTorch", "Airflow", "Spark", ...],
    "cloud_devops": ["Docker", "GCP", "Kubernetes", ...],
    "tools": ["Git", "Linux", ...]
  }

Consignes :
- Assure-toi de renvoyer un JSON valide.
- Ne rajoute aucun commentaire Markdown avant ou après le JSON."""

    content_parts: List[Dict[str, Any]] = [
        {"type": "text", "text": instruction_text}
    ]
    for b64 in base64_images:
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}"}
        })

    response = await acompletion(
        model=model,
        messages=[{"role": "user", "content": content_parts}],
        response_format={"type": "json_object"},
        temperature=0.1,
        api_key=key,
        drop_params=True,
    )
    raw_content = response.choices[0].message.content.strip()
    clean_json = re.sub(r"^```(?:json)?|```$", "", raw_content, flags=re.MULTILINE).strip()
    data = json.loads(clean_json)
    usage = getattr(response, "usage", None)
    data["_usage"] = {
        "model": model,
        "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
        "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
    }
    return data


async def parse_cv_with_llm(
    cv_text: str = "",
    pdf_path: Optional[str] = None,
    model: str = "gemini/gemini-2.5-flash",
    vlm_model: str = "mistral/mistral-medium-3-5-26-04",
) -> Dict[str, Any]:
    """Extrait les données structurées du CV.

    Tente en priorité l'analyse visuelle multimodale (VLM Mistral Medium 3.5) si le fichier PDF
    est accessible et qu'une clé Mistral est active. Bascule sur l'extraction
    textuelle LLM en cas d'indisponibilité ou d'erreur.
    """
    # 1. Tentative VLM si PDF présent
    if pdf_path and os.path.exists(pdf_path):
        try:
            images = await asyncio.to_thread(render_pdf_pages_to_base64_images, pdf_path)
            if images and os.environ.get("MISTRAL_API_KEY"):
                logger.info("Extraction du CV via VLM (%s) sur %d page(s)", vlm_model, len(images))
                vlm_payload = await parse_cv_with_vlm(images, model=vlm_model)
                if vlm_payload and isinstance(vlm_payload, dict):
                    if "experiences" in vlm_payload or "skills" in vlm_payload or "headline" in vlm_payload:
                        logger.info("Succès de l'extraction VLM pour le CV")
                        return vlm_payload
        except Exception as exc:
            logger.warning("Échec de l'extraction VLM du CV, bascule vers le LLM texte : %s", exc)

    # 2. Fallback textuel classique
    if not cv_text and pdf_path and os.path.exists(pdf_path):
        cv_text = await asyncio.to_thread(extract_text_from_pdf, pdf_path)

    # Si cv_text est vide, renvoyer un profil minimal par défaut
    if not cv_text.strip():
        return {
            "headline": "",
            "summary": "",
            "experiences": [],
            "projects": [],
            "education": [],
            "certifications": [],
            "skills": {}
        }

    chosen_model = model
    if chosen_model == "gemini/gemini-3.8-flash":
        chosen_model = "gemini/gemini-2.5-flash"

    prompt = f"""
Voici le texte brut d'un CV (curriculum vitae).
Ton rôle est d'extraire les informations sous format JSON strictement structuré.

Texte du CV :
-----------------
{cv_text}
-----------------

Instructions :
- Remplis tous les champs du schéma JSON demandé.
- 'headline': titre professionnel principal.
- 'summary': résumé court (3-4 phrases).
- 'experiences': regroupe bien les missions et la 'stack' (technologies utilisées).
- 'skills': regroupe par catégories (ex: languages, frameworks, devops, tools).
- Si des données sont absentes (ex: projets), renvoie une liste vide [].
"""

    response = await acompletion(
        model=chosen_model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.1,
        drop_params=True,
    )
    content = response.choices[0].message.content.strip()
    content = re.sub(r"^```(?:json)?|```$", "", content, flags=re.MULTILINE).strip()
    data = json.loads(content)
    usage = getattr(response, "usage", None)
    data["_usage"] = {
        "model": chosen_model,
        "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
        "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
    }
    return data
