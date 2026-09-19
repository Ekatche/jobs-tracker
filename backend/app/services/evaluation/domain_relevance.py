"""Pré-filtre de cohérence métier entre le profil candidat et une offre.

Réutilise l'infrastructure d'embeddings de app.services.role_normalizer
(text-embedding-3-small + cosine_similarity) pour écarter, avant le coût
du Two-Pass LLM complet, une offre manifestement hors du domaine du
candidat (ex: profil animatrice face à une offre Data Scientist).
"""

import logging
from typing import List, Optional

from app.services.role_normalizer import cosine_similarity

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"

# Seuil de départ conservateur (biaisé vers laisser passer plutôt que
# rejeter) — cf. section Risques du spec
# docs/superpowers/specs/2026-09-19-generalisation-multi-metiers-design.md.
DOMAIN_RELEVANCE_THRESHOLD = 0.30


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

        resp = await aembedding(model=EMBEDDING_MODEL, input=[candidate_identity, offer_title])
        data = resp.data if hasattr(resp, "data") else resp["data"]

        def _extract(item):
            return item.get("embedding") if isinstance(item, dict) else getattr(item, "embedding", item["embedding"])

        emb_candidate = _extract(data[0])
        emb_offer = _extract(data[1])
        return cosine_similarity(emb_candidate, emb_offer)
    except Exception as e:
        logger.warning(
            f"⚠️ Erreur pré-filtre de cohérence métier (candidat='{candidate_identity}', "
            f"offre='{offer_title}'): {e}, fail-open (pas de court-circuit)"
        )
        return None
