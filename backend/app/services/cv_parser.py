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


def _clean_parsed_cv(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return data
    projects = data.get("projects")
    if isinstance(projects, list):
        for p in projects:
            if isinstance(p, dict):
                ctx = str(p.get("context", "")).strip().lower()
                if ctx in ("client", "professionnel", "pro", "entreprise", "work", "job"):
                    p["context"] = "client"
                elif ctx in ("recherche", "research"):
                    p["context"] = "recherche"
                elif ctx in ("consortium",):
                    p["context"] = "consortium"
                else:
                    p["context"] = "perso"

    raw_interests = data.get("interests")
    if isinstance(raw_interests, list):
        data["interests"] = [str(i).strip() for i in raw_interests if str(i).strip()]
    elif isinstance(raw_interests, str) and raw_interests.strip():
        data["interests"] = [str(raw_interests).strip()]
    else:
        data["interests"] = []

    raw_languages = data.get("languages")
    if isinstance(raw_languages, list):
        data["languages"] = [str(l).strip() for l in raw_languages if str(l).strip()]
    elif isinstance(raw_languages, str) and raw_languages.strip():
        data["languages"] = [str(raw_languages).strip()]
    else:
        data["languages"] = []

    raw_skills = data.get("skills")
    if isinstance(raw_skills, dict):
        data["skills"] = {
            category: items
            for category, items in raw_skills.items()
            if isinstance(items, list) and any(str(i).strip() for i in items)
        }

    return data


DEFAULT_VLM_MODEL = os.getenv("MISTRAL_VLM_MODEL", "mistral/pixtral-12b-2409")
DEFAULT_CV_PARSER_MODEL = os.getenv("CV_PARSER_MODEL", "openai/gpt-4o-mini")


async def parse_cv_with_vlm(
    base64_images: List[str],
    model: str = DEFAULT_VLM_MODEL,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Extrait les informations structurées d'un CV via un Vision Language Model.

    Utilise Pixtral Large (ou le modèle VLM configuré) pour l'analyse visuelle
    multimodale du CV.
    """
    if not base64_images:
        raise ValueError("Aucune image de page PDF fournie pour l'analyse VLM")

    key = api_key or os.environ.get("MISTRAL_API_KEY")
    if not key and model.startswith("mistral/"):
        raise ValueError("MISTRAL_API_KEY manquante pour l'analyse VLM Mistral")

    instruction_text = """Voici les pages numérisées d'un CV de candidat.
Analyse attentivement la disposition visuelle, les colonnes multiples, les encarts latéraux et les sections.
Extrais fidèlement les informations réelles sans rien inventer sous format JSON strict avec les clés :
- "headline": Titre professionnel du candidat (ex: 'Développeur Fullstack', 'Directeur Marketing', 'Chef de Projet', etc.)
- "summary": Synthèse percutante du parcours et des compétences clés
- "experiences": [
    {
      "company": "Entreprise ou Organisation",
      "role": "Poste occupé",
      "location": "Lieu (ex: Paris, Remote)",
      "contract": "CDI / Freelance / Alternance / Stage / CDD",
      "start": "Date début (ex: 2021-09)",
      "end": "Date fin ou null si poste actuel",
      "missions": ["Réalisation concrète, responsabilité ou impact chiffré"],
      "stack": ["Outil, technologie, méthodologie ou logiciel utilisé"]
    }
  ]
- "projects": [
    {
      "name": "Nom du projet",
      "description": "Description succincte",
      "context": "perso",
      "stack": ["Techno ou outil"],
      "url": "Lien si présent"
    }
  ]
- "education": [{"school": "École / Université", "degree": "Diplôme / Formation", "years": "Période"}]
- "certifications": [{"name": "Nom", "issuer": "Organisme", "year": "Année"}]
- "languages": ["Langues parlées avec niveau si précisé (ex: 'Français (natif)', 'Anglais (professionnel)')"]
- "interests": ["Centres d'intérêt, passions, sports, engagements associatifs ou bénévolat"]
- "skills": {
    "nom_de_categorie_adaptee": ["Compétence 1", "Compétence 2"]
  }

Consignes importantes :
- Le champ "skills" doit comporter des catégories dynamiques et pertinentes par rapport au secteur du candidat (ex: développement, design, marketing, finance, RH, management, etc.). N'impose aucune catégorie fixe ou orientée Data/IA si le candidat exerce un autre métier.
- Extrais bien les langues ("languages") et centres d'intérêt ("interests") s'ils figurent sur le CV.
- Assure-toi de renvoyer un JSON valide sans aucun texte ni markdown avant ou après."""

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
    return _clean_parsed_cv(data)


async def parse_cv_with_llm(
    cv_text: str = "",
    pdf_path: Optional[str] = None,
    model: str = DEFAULT_CV_PARSER_MODEL,
    vlm_model: str = DEFAULT_VLM_MODEL,
) -> Dict[str, Any]:
    """Extrait les données structurées du CV.

    Tente en priorité l'analyse visuelle multimodale (VLM Mistral) si le fichier PDF
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
    if chosen_model.startswith("gemini/") or chosen_model in ("gemini/gemini-3.8-flash", "gemini/gemini-2.5-flash", "gemini/gemini-3.7-flash", "gemini/gemini-2.0-flash"):
        chosen_model = os.getenv("CV_PARSER_MODEL", "openai/gpt-4o-mini")

    prompt = f"""
Voici le texte brut d'un CV (curriculum vitae).
Ton rôle est d'extraire les informations sous format JSON strictement structuré sans inventer de données.

Texte du CV :
-----------------
{cv_text}
-----------------

Schéma JSON attendu :
- 'headline': titre professionnel principal (ex: Développeur Fullstack, Chef de Projet, Directeur Financier, etc.).
- 'summary': résumé court (3-4 phrases).
- 'experiences': liste d'objets avec company, role, location, contract, start, end, missions (liste de réalisations), stack (outils/logiciels/technologies).
- 'projects': liste d'objets avec name, description, context ("perso" ou "client"), stack, url.
- 'education': liste d'objets avec school, degree, years.
- 'certifications': liste d'objets avec name, issuer, year.
- 'languages': liste des langues parlées avec niveau si mentionné.
- 'interests': liste des centres d'intérêt, loisirs, activités associatives ou bénévolat.
- 'skills': dictionnaire de compétences regroupées par catégories dynamiques adaptées au domaine du candidat (ex: outils, compétences clés, logiciels, méthodologies). Ne force pas de catégorie Data/IA si le candidat est dans un autre métier.
- Si des données sont absentes, renvoie une liste vide [].
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
    return _clean_parsed_cv(data)
