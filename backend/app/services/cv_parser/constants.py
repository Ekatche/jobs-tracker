import os
from typing import Any, Dict, List, Optional

PROFILE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string", "description": "Titre professionnel (ex: Senior Data & ML Engineer)"},
        "summary": {
            "type": "string",
            "description": "Accroche factuelle (3-4 phrases) centrée sur la personne, sans compétences génériques du métier ni superlatifs",
        },
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
                    "missions": {"type": "array", "items": {"type": "string"}},
                    "stack": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["company", "role"],
            },
        },
        "projects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "context": {
                        "type": "string",
                        "description": "cadre du projet en texte libre, libellé court fidèle au CV (ex : Perso, Client, Stage, Associatif)",
                    },
                    "stack": {"type": "array", "items": {"type": "string"}},
                    "url": {"type": "string"},
                },
            },
        },
        "education": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "school": {"type": "string"},
                    "degree": {"type": "string"},
                    "years": {"type": "string"},
                },
            },
        },
        "certifications": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "issuer": {"type": "string"},
                    "year": {"type": "string"},
                },
            },
        },
        "contact": {
            "type": "object",
            "properties": {
                "mobility": {
                    "type": "string",
                    "description": "Permis, véhicule ou zone de mobilité (ex: Permis B, véhiculé)",
                },
                "availability": {
                    "type": "string",
                    "description": "Disponibilité et horaires acceptés (ex: Disponible immédiatement · 2x8, nuit)",
                },
            },
        },
        "skills": {
            "type": "object",
            "description": "Dictionnaire des compétences classées par catégories (ex: languages, frameworks, devops, data_ai, tools)",
            "additionalProperties": {"type": "array", "items": {"type": "string"}},
        },
    },
    "required": ["headline", "summary", "experiences", "skills"],
}

VLM_MAX_PAGES = 3

PROTECTED_PDF_MESSAGE = (
    "Ce PDF est protégé par un mot de passe : exportez une version non protégée puis réessayez"
)
UNREADABLE_PDF_MESSAGE = (
    "Ce PDF est illisible ou endommagé : exportez-le de nouveau puis réessayez"
)
EMPTY_CV_MESSAGE = (
    "Aucun contenu exploitable n'a été trouvé dans ce PDF : "
    "vérifiez qu'il contient du texte ou une image lisible"
)
VISION_UNAVAILABLE_MESSAGE = (
    "L'analyse visuelle de ce PDF est momentanément indisponible. Réessayez dans quelques minutes."
)

CV_OUTPUT_KEYS = frozenset(PROFILE_JSON_SCHEMA["properties"]) | {"languages", "interests"}

DEFAULT_VLM_MODEL = os.getenv("MISTRAL_VLM_MODEL", "mistral/ministral-14b-2512")
DEFAULT_CV_PARSER_MODEL = os.getenv("CV_PARSER_MODEL", "openai/gpt-4o-mini")


class CVVisionUnavailable(Exception):
    """PDF sans texte exploitable dont l'analyse visuelle n'a pas abouti."""

    def __init__(
        self,
        message: str = VISION_UNAVAILABLE_MESSAGE,
        usage: Optional[List[Dict[str, Any]]] = None,
    ):
        super().__init__(message)
        self.usage = usage or []


class CVResponseError(ValueError):
    """Réponse de modèle inexploitable ; porte l'usage déjà facturé pour le suivi."""

    def __init__(self, message: str, usage: Optional[List[Dict[str, Any]]] = None):
        super().__init__(message)
        self.usage = usage or []
