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
        "summary": {"type": "string", "description": "Accroche factuelle (3-4 phrases) centrée sur la personne, sans compétences génériques du métier ni superlatifs"},
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
                    "context": {"type": "string", "description": "cadre du projet en texte libre, libellé court fidèle au CV (ex : Perso, Client, Stage, Associatif)"},
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
        "contact": {
            "type": "object",
            "properties": {
                "mobility": {"type": "string", "description": "Permis, véhicule ou zone de mobilité (ex: Permis B, véhiculé)"},
                "availability": {"type": "string", "description": "Disponibilité et horaires acceptés (ex: Disponible immédiatement · 2x8, nuit)"}
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


# Nombre de pages envoyées au VLM (coût) ; les suivantes passent par le repli texte.
VLM_MAX_PAGES = 3


def extract_page_texts(pdf_path: str) -> List[str]:
    """Texte brut de chaque page d'un PDF (chaîne vide pour une page sans couche texte)."""
    import fitz  # PyMuPDF

    doc = fitz.open(pdf_path)
    try:
        return [page.get_text() for page in doc]
    finally:
        doc.close()


def extract_text_from_pdf(pdf_path: str, start_page: int = 0) -> str:
    """Extrait le texte brut d'un PDF (à partir de la page d'index start_page)."""
    return "\n\n".join(extract_page_texts(pdf_path)[start_page:])


def is_pdf_password_protected(pdf_path: str) -> bool:
    """Vrai si le PDF exige un mot de passe d'ouverture (un mot de passe propriétaire seul ne compte pas)."""
    import fitz  # PyMuPDF

    try:
        doc = fitz.open(pdf_path)
    except Exception:
        return False  # fichier illisible : l'erreur sera remontée par l'extraction
    try:
        return bool(doc.needs_pass)
    finally:
        doc.close()


def render_pdf_pages_to_base64_images(
    pdf_path: str, max_pages: int = VLM_MAX_PAGES, dpi: int = 150
) -> List[str]:
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


def _flatten_contact_value(v: Any) -> Optional[str]:
    """Flattens nested dict or list into a clean ' · '-separated string."""
    if v is None:
        return None
    if isinstance(v, str):
        cleaned = v.strip()
        return cleaned if cleaned else None
    if isinstance(v, (list, tuple, set)):
        parts = [_flatten_contact_value(item) for item in v]
        valid = [p for p in parts if p]
        return " · ".join(valid) if valid else None
    if isinstance(v, dict):
        parts = []
        for key, val in v.items():
            flattened = _flatten_contact_value(val)
            if not flattened:
                continue
            # {'permis': ['B']} : la clé porte le sens, « B » seul ne dit rien au recruteur.
            key_text = str(key).casefold()
            if ("permis" in key_text or "licen" in key_text) and "permis" not in flattened.casefold():
                flattened = f"Permis {flattened}"
            parts.append(flattened)
        return " · ".join(parts) if parts else None
    s = str(v).strip()
    return s if s else None


def _clean_parsed_cv(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return data

    raw_contact = data.get("contact")
    if isinstance(raw_contact, dict):
        cleaned_contact: Dict[str, str] = {}
        for k, v in raw_contact.items():
            flattened = _flatten_contact_value(v)
            if flattened:
                cleaned_contact[k] = flattened
        data["contact"] = cleaned_contact
    elif "contact" in data:
        data.pop("contact")

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


class CVResponseError(ValueError):
    """Réponse de modèle inexploitable ; porte l'usage déjà facturé pour le suivi."""

    def __init__(self, message: str, usage: Optional[List[Dict[str, Any]]] = None):
        super().__init__(message)
        self.usage = usage or []


def _read_json_response(response: Any, model: str) -> tuple:
    """Décode la réponse JSON d'un modèle et renvoie (données, usage facturé).

    L'usage est capturé avant le décodage : une réponse invalide reste facturée.
    """
    usage_obj = getattr(response, "usage", None)
    usage = {
        "model": model,
        "input_tokens": getattr(usage_obj, "prompt_tokens", 0) or 0,
        "output_tokens": getattr(usage_obj, "completion_tokens", 0) or 0,
    }
    try:
        raw_content = response.choices[0].message.content.strip()
        clean_json = re.sub(r"^```(?:json)?|```$", "", raw_content, flags=re.MULTILINE).strip()
        data = json.loads(clean_json)
    except (ValueError, AttributeError, IndexError, TypeError) as exc:
        raise CVResponseError(f"Réponse du modèle {model} non exploitable : {exc}", [usage]) from exc
    if not isinstance(data, dict):
        raise CVResponseError(f"Réponse du modèle {model} : objet JSON attendu", [usage])
    return data, usage


def _has_usable_content(data: Any) -> bool:
    """Une extraction sans expérience, compétence ni intitulé n'est pas exploitable."""
    if not isinstance(data, dict):
        return False
    has_experience = any(isinstance(e, dict) and any(e.values()) for e in data.get("experiences") or [])
    skills = data.get("skills")
    has_skills = isinstance(skills, dict) and any(
        isinstance(items, list) and any(str(i).strip() for i in items) for items in skills.values()
    )
    has_headline = bool(str(data.get("headline") or "").strip())
    return has_experience or has_skills or has_headline


_LIST_SECTIONS = ("experiences", "projects", "education", "certifications", "languages", "interests")
# Champs d'identité par section : deux éléments de même identité sont le même élément.
_IDENTITY_FIELDS = {
    "experiences": ("company", "role", "start"),
    "projects": ("name",),
    "education": ("school", "degree"),
    "certifications": ("name",),
}


def _item_key(section: str, item: Any) -> str:
    if isinstance(item, dict):
        fields = _IDENTITY_FIELDS.get(section) or tuple(sorted(item))
        return "|".join(str(item.get(f) or "").strip().casefold() for f in fields)
    return str(item).strip().casefold()


def _merge_cv_complement(base: Dict[str, Any], extra: Dict[str, Any]) -> Dict[str, Any]:
    """Complète `base` avec `extra` sans jamais écraser une valeur déjà présente."""
    for section in _LIST_SECTIONS:
        current = list(base.get(section) or [])
        seen = {_item_key(section, item) for item in current}
        for item in extra.get(section) or []:
            key = _item_key(section, item)
            if key not in seen:
                seen.add(key)
                current.append(item)
        if current:
            base[section] = current

    skills = {cat: list(items) for cat, items in (base.get("skills") or {}).items()}
    for category, items in (extra.get("skills") or {}).items():
        merged = skills.setdefault(category, [])
        known = {str(i).strip().casefold() for i in merged}
        for item in items:
            if str(item).strip().casefold() not in known:
                known.add(str(item).strip().casefold())
                merged.append(item)
    if skills:
        base["skills"] = skills

    contact = dict(base.get("contact") or {})
    for key, value in (extra.get("contact") or {}).items():
        if not contact.get(key):
            contact[key] = value
    if contact:
        base["contact"] = contact

    for key, value in extra.items():
        if key in _LIST_SECTIONS or key in ("skills", "contact", "_usage"):
            continue
        if not base.get(key) and value:
            base[key] = value
    return base


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
- "summary": Accroche factuelle et sobre de 3-4 phrases, dans le vocabulaire du métier réel du candidat (déduit du CV). Pas de superlatifs génériques ('passionné', 'dynamique', 'expert'). Ne cite pas comme atout distinctif une compétence qui fait partie du socle normal du métier (ex: 'sécurité des enfants' pour une animatrice, 'rigueur' pour un comptable) — ne retiens que ce qui différencie réellement ce candidat : spécialisations, résultats concrets, trajectoire. Mets en valeur la personne et son parcours propre, pas une fiche de poste générique.
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
      "context": "Cadre du projet en texte libre, libellé court (ex : Perso, Client, Stage, Associatif)",
      "stack": ["Techno ou outil"],
      "url": "Lien si présent"
    }
  ]
- "education": [{"school": "École / Université", "degree": "Diplôme / Formation", "years": "Période"}]
- "certifications": [{"name": "Nom", "issuer": "Organisme", "year": "Année"}]
- "languages": ["Langues parlées avec niveau si précisé (ex: 'Français (natif)', 'Anglais (professionnel)')"]
- "interests": ["Centres d'intérêt, passions, sports, engagements associatifs ou bénévolat"]
- "contact": {"mobility": "Permis, véhicule ou zone de mobilité, seulement si mentionnés", "availability": "Disponibilité et horaires acceptés (ex: 2x8, nuit, week-end), seulement si mentionnés"}
- "skills": {
    "nom_de_categorie_adaptee": ["Compétence 1", "Compétence 2"]
  }

Consignes importantes :
- Les titres réglementaires et habilitations — CACES (avec les catégories, ex: 'CACES R489 cat. 1, 3, 5'), permis de conduire (B, C, CE…), SST, habilitations électriques, FIMO/FCO — vont dans "certifications", jamais dans "skills".
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
    data, usage = _read_json_response(response, model)
    data["_usage"] = [usage]
    return _clean_parsed_cv(data)


async def _parse_cv_text(cv_text: str, model: str) -> Dict[str, Any]:
    """Extrait les données structurées d'un texte de CV via le LLM texte."""
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
- 'summary': accroche factuelle et sobre de 3-4 phrases, dans le vocabulaire du métier réel du candidat (déduit du CV). Pas de superlatifs génériques ('passionné', 'dynamique', 'expert'). Ne cite pas comme atout distinctif une compétence qui fait partie du socle normal du métier (ex: 'sécurité des enfants' pour une animatrice, 'rigueur' pour un comptable) — ne retiens que ce qui différencie réellement ce candidat : spécialisations, résultats concrets, trajectoire. Mets en valeur la personne et son parcours propre, pas une fiche de poste générique.
- 'experiences': liste d'objets avec company, role, location, contract, start, end, missions (liste de réalisations), stack (outils/logiciels/technologies).
- 'projects': liste d'objets avec name, description, context (cadre du projet en texte libre : libellé court fidèle au CV, ex : Perso, Client, Stage, Associatif), stack, url.
- 'education': liste d'objets avec school, degree, years.
- 'certifications': liste d'objets avec name, issuer, year. Les titres réglementaires et habilitations — CACES (avec les catégories, ex: 'CACES R489 cat. 1, 3, 5'), permis de conduire (B, C, CE…), SST, habilitations électriques, FIMO/FCO — vont ici, jamais dans 'skills'.
- 'languages': liste des langues parlées avec niveau si mentionné.
- 'interests': liste des centres d'intérêt, loisirs, activités associatives ou bénévolat.
- 'contact': objet avec 'mobility' (permis, véhicule, zone de mobilité) et 'availability' (disponibilité, horaires acceptés comme 2x8, nuit, week-end), renseignés seulement si le CV les mentionne.
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
    data, usage = _read_json_response(response, chosen_model)
    data["_usage"] = [usage]
    return _clean_parsed_cv(data)


def _build_import_report(
    total_pages: int,
    vlm_pages: List[int],
    text_pages: List[int],
    fallback_used: bool,
    errors: List[str],
) -> Dict[str, Any]:
    """Rapport de couverture d'un import (pages numérotées à partir de 1)."""
    covered = set(vlm_pages) | set(text_pages)
    return {
        "total_pages": total_pages,
        "pages_by_method": {"vlm": sorted(vlm_pages), "text": sorted(text_pages)},
        "skipped_pages": [n for n in range(1, total_pages + 1) if n not in covered],
        "fallback_used": fallback_used,
        "errors": errors,
    }


def _pages_with_text(page_texts: List[str], first_page: int = 1) -> List[int]:
    """Numéros (base 1) des pages dont le texte extrait est non vide, à partir de first_page."""
    return [n for n, text in enumerate(page_texts, start=1) if n >= first_page and text.strip()]


async def parse_cv_with_llm(
    cv_text: str = "",
    pdf_path: Optional[str] = None,
    model: str = DEFAULT_CV_PARSER_MODEL,
    vlm_model: str = DEFAULT_VLM_MODEL,
) -> Dict[str, Any]:
    """Extrait les données structurées du CV.

    Tente en priorité l'analyse visuelle multimodale (VLM Mistral) si le fichier PDF
    est accessible et qu'une clé Mistral est active. Les pages au-delà de la limite
    VLM sont complétées par le LLM texte. Bascule sur l'extraction textuelle LLM en
    cas d'indisponibilité, d'erreur ou de réponse VLM vide.

    La clé `_usage` du résultat liste l'usage de chaque appel facturable ; la clé
    `_import_report` (si un PDF est fourni) décrit la couverture par page.
    """
    usages: List[Dict[str, Any]] = []
    errors: List[str] = []
    has_pdf = bool(pdf_path and os.path.exists(pdf_path))
    page_texts: Optional[List[str]] = None
    if has_pdf:
        try:
            page_texts = await asyncio.to_thread(extract_page_texts, pdf_path)
        except Exception as exc:
            logger.warning("Lecture page par page du PDF impossible, rapport de couverture omis : %s", exc)

    def report(vlm_pages: List[int], text_pages: List[int], fallback: bool) -> Optional[Dict[str, Any]]:
        if page_texts is None:
            return None
        return _build_import_report(len(page_texts), vlm_pages, text_pages, fallback, errors)

    # 1. Tentative VLM si PDF présent
    if has_pdf:
        try:
            images = await asyncio.to_thread(render_pdf_pages_to_base64_images, pdf_path)
            if images and os.environ.get("MISTRAL_API_KEY"):
                logger.info("Extraction du CV via VLM (%s) sur %d page(s)", vlm_model, len(images))
                vlm_payload = await parse_cv_with_vlm(images, model=vlm_model)
                if isinstance(vlm_payload, dict):
                    usages.extend(vlm_payload.pop("_usage", None) or [])
                if _has_usable_content(vlm_payload):
                    logger.info("Succès de l'extraction VLM pour le CV")
                    text_pages = await _complete_with_remaining_pages(
                        vlm_payload, page_texts, model, usages, errors
                    )
                    vlm_payload["_usage"] = usages
                    built = report(list(range(1, len(images) + 1)), text_pages, False)
                    if built is not None:
                        vlm_payload["_import_report"] = built
                    return vlm_payload
                logger.warning("Réponse VLM vide pour le CV, bascule vers le LLM texte")
                errors.append("L'analyse visuelle n'a rien renvoyé : le texte extrait du PDF a été utilisé à la place.")
        except Exception as exc:
            usages.extend(getattr(exc, "usage", None) or [])
            logger.warning("Échec de l'extraction VLM du CV, bascule vers le LLM texte : %s", exc)
            errors.append("L'analyse visuelle a échoué : le texte extrait du PDF a été utilisé à la place.")

    # 2. Fallback textuel classique
    if not cv_text and has_pdf:
        cv_text = await asyncio.to_thread(extract_text_from_pdf, pdf_path)

    # Si cv_text est vide, renvoyer un profil minimal par défaut
    if not cv_text.strip():
        empty = {
            "headline": "",
            "summary": "",
            "experiences": [],
            "projects": [],
            "education": [],
            "certifications": [],
            "skills": {}
        }
        if usages:
            empty["_usage"] = usages
        built = report([], [], has_pdf)
        if built is not None:
            empty["_import_report"] = built
        return empty

    try:
        data = await _parse_cv_text(cv_text, model)
    except CVResponseError as exc:
        exc.usage = usages + exc.usage
        raise
    data["_usage"] = usages + data.get("_usage", [])
    built = report([], _pages_with_text(page_texts or []), has_pdf)
    if built is not None:
        data["_import_report"] = built
    return data


async def _complete_with_remaining_pages(
    vlm_payload: Dict[str, Any],
    page_texts: Optional[List[str]],
    model: str,
    usages: List[Dict[str, Any]],
    errors: List[str],
) -> List[int]:
    """Complète le résultat VLM avec le texte des pages que le VLM n'a pas vues.

    Best effort : un échec ici ne fait jamais perdre le résultat VLM. Renvoie les
    pages (base 1) effectivement complétées par le texte.
    """
    if page_texts is None:
        return []
    text_pages = _pages_with_text(page_texts, VLM_MAX_PAGES + 1)
    if not text_pages:
        return []
    try:
        logger.info("Complément texte du CV pour les pages au-delà de %d", VLM_MAX_PAGES)
        extra = await _parse_cv_text("\n\n".join(page_texts[VLM_MAX_PAGES:]), model)
        usages.extend(extra.pop("_usage", None) or [])
        _merge_cv_complement(vlm_payload, extra)
        return text_pages
    except Exception as exc:
        usages.extend(getattr(exc, "usage", None) or [])
        logger.warning("Échec du complément texte des pages restantes du CV : %s", exc)
        errors.append(
            f"Les pages au-delà de la page {VLM_MAX_PAGES} n'ont pas pu être analysées : "
            "leur contenu n'est pas dans le profil importé."
        )
        return []
