"""Pré-filtre de cohérence métier entre le profil candidat et une offre.

Réutilise l'infrastructure d'embeddings de app.services.role_normalizer
(text-embedding-3-small + cosine_similarity) pour écarter, avant le coût
du Two-Pass LLM complet, une offre manifestement hors du domaine du
candidat (ex: profil animatrice face à une offre Data Scientist).
"""

import logging
import re
from typing import List, Optional

from app.services.role_normalizer import cosine_similarity

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"

# Seuil de départ conservateur (biaisé vers laisser passer plutôt que
# rejeter) — cf. section Risques du spec
# docs/superpowers/specs/2026-09-19-generalisation-multi-metiers-design.md.
DOMAIN_RELEVANCE_THRESHOLD = 0.30

# L'embedding comprend mal le sigle "IA" (surtout écrit "Ia") : "Développeur Confirmé Ia"
# tombait à 0.28 face à un profil "AI Engineer", contre 0.43 une fois développé.
ACRONYM_EXPANSIONS = [
    (re.compile(r"\bia\b", re.I), "intelligence artificielle"),
    (re.compile(r"\bfp\s*&\s*a\b", re.I), "financial planning analysis"),
    (re.compile(r"\bfpa\b", re.I), "financial planning analysis"),
]

# Acronymes métiers fréquents, développés uniquement si trouvés tels quels
# (casse exacte, sans re.I) : insensibles à la casse, "PM", "DE", "DS"...
# collisionneraient avec des mots français courants ("de", "ds" familier).
# "DA" (directeur artistique en français) est volontairement exclu.
CASE_SENSITIVE_ACRONYMS = [
    (re.compile(r"\bPM\b"), "Product Manager"),
    (re.compile(r"\bPO\b"), "Product Owner"),
    (re.compile(r"\bML\b"), "Machine Learning"),
    (re.compile(r"\bQA\b"), "Quality Assurance"),
    (re.compile(r"\bSRE\b"), "Site Reliability Engineer"),
    (re.compile(r"\bBI\b"), "Business Intelligence"),
    (re.compile(r"\bDE\b"), "Data Engineer"),
    (re.compile(r"\bDS\b"), "Data Scientist"),
]


def _extract_embedding(item):
    """Extrait le vecteur d'un item de réponse `aembedding` (dict ou objet litellm).

    Pas d'évaluation anticipée du défaut : `item["embedding"]` ne doit être
    tenté que si `item` n'a pas l'attribut `embedding`, sinon un objet sans
    `__getitem__` (cas réel des réponses litellm) lèverait un `TypeError`
    même quand l'attribut existe.
    """
    if isinstance(item, dict):
        return item.get("embedding")
    if hasattr(item, "embedding"):
        return item.embedding
    return item["embedding"]


def expand_title_acronyms(title: str) -> str:
    # Un intitulé tout en majuscules ("CHEF DE PROJET DA") ne permet pas de
    # distinguer un acronyme d'un mot ordinaire en capitales : on ne tente
    # alors que l'expansion insensible à la casse ("IA").
    title_is_upper = title.isupper()
    for pattern, expansion in ACRONYM_EXPANSIONS:
        title = pattern.sub(expansion, title)
    if not title_is_upper:
        for pattern, expansion in CASE_SENSITIVE_ACRONYMS:
            title = pattern.sub(expansion, title)
    return title


def build_candidate_identity(headline: str, target_roles: List[str]) -> str:
    """Construit le texte identitaire du candidat pour comparaison d'embedding.

    Concatène le headline et les rôles ciblés ; les entrées vides sont ignorées.
    """
    parts = [headline] + list(target_roles or [])
    return " ".join(p.strip() for p in parts if p and p.strip())


async def compute_domain_relevance(candidate_identity: str, offer_title: str) -> Optional[float]:
    """Similarité cosinus entre l'identité candidat et l'intitulé de l'offre.

    Fail-open : retourne None si l'un des deux textes est vide, ou si l'appel
    d'embedding échoue (timeout, quota, erreur réseau). L'appelant doit alors
    traiter l'absence de score comme "ne pas court-circuiter l'évaluation",
    jamais comme un mismatch.
    """
    if not candidate_identity.strip() or not offer_title.strip():
        return None

    try:
        from litellm import aembedding

        resp = await aembedding(
            model=EMBEDDING_MODEL, input=[candidate_identity, expand_title_acronyms(offer_title)]
        )
        data = resp.data if hasattr(resp, "data") else resp["data"]

        emb_candidate = _extract_embedding(data[0])
        emb_offer = _extract_embedding(data[1])
        return cosine_similarity(emb_candidate, emb_offer)
    except Exception as e:
        logger.warning(
            f"⚠️ Erreur pré-filtre de cohérence métier (candidat='{candidate_identity}', "
            f"offre='{offer_title}'): {e}, fail-open (pas de court-circuit)"
        )
        return None
