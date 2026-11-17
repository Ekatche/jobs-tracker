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


_SEGMENT_SPLIT_RE = re.compile(r"\s+[–—-]\s+|\s*\|\s*|[()\[\]]+")
_WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ]+")
_MIN_UPPER_PROSE_WORD_LEN = 4


def _segment_bounds(title: str, start: int, end: int) -> tuple[int, int]:
    seg_start, seg_end = 0, len(title)
    for sep in _SEGMENT_SPLIT_RE.finditer(title):
        if sep.end() <= start:
            seg_start = sep.end()
        elif sep.start() >= end:
            seg_end = sep.start()
            break
    return seg_start, seg_end


def _should_expand_case_sensitive(title: str, match: "re.Match[str]") -> bool:
    """Reject case-sensitive acronym expansion inside uppercase French prose segments."""
    seg_start, seg_end = _segment_bounds(title, match.start(), match.end())
    segment = title[seg_start:seg_end]
    tokens = list(_WORD_RE.finditer(segment))
    words = [tok.group(0) for tok in tokens if len(tok.group(0)) >= 2]
    if (
        len(words) >= 2
        and all(w.isupper() for w in words)
        and any(len(w) >= _MIN_UPPER_PROSE_WORD_LEN for w in words)
    ):
        return False

    rel_start = match.start() - seg_start
    rel_end = match.end() - seg_start
    match_idx = next(
        (i for i, tok in enumerate(tokens) if tok.start() == rel_start and tok.end() == rel_end),
        None,
    )
    if match_idx is None:
        return True

    prev_word = next(
        (tokens[i].group(0) for i in range(match_idx - 1, -1, -1) if len(tokens[i].group(0)) >= 2),
        "",
    )
    next_word = next(
        (tokens[i].group(0) for i in range(match_idx + 1, len(tokens)) if len(tokens[i].group(0)) >= 2),
        "",
    )
    return not (
        (len(prev_word) >= _MIN_UPPER_PROSE_WORD_LEN and prev_word.isupper())
        or (len(next_word) >= _MIN_UPPER_PROSE_WORD_LEN and next_word.isupper())
    )


def expand_title_acronyms(title: str) -> str:
    # Un intitulé tout en majuscules ("CHEF DE PROJET DA") ou un segment
    # patronymique/géographique en capitales ("CONSEIL DEPARTEMENTAL DE L'ISERE")
    # ne permet pas de distinguer un sigle (« DE ») d'une préposition : on ne
    # garde alors que l'expansion insensible à la casse (« IA »).
    title_is_upper = title.isupper()
    for pattern, expansion in ACRONYM_EXPANSIONS:
        title = pattern.sub(expansion, title)
    if not title_is_upper:
        for pattern, expansion in CASE_SENSITIVE_ACRONYMS:
            current = title
            title = pattern.sub(
                lambda m, exp=expansion, src=current: (
                    exp if _should_expand_case_sensitive(src, m) else m.group(0)
                ),
                current,
            )
    return title


def build_candidate_identity(headline: str, target_roles: List[str]) -> str:
    """Construit le texte identitaire du candidat pour comparaison d'embedding.

    Concatène le headline et les rôles ciblés ; les entrées vides sont ignorées.
    """
    parts = [headline] + list(target_roles or [])
    return " ".join(p.strip() for p in parts if p and p.strip())


async def compute_domain_relevance(
    candidate_identity: str,
    offer_title: str,
    candidate_roles: Optional[List[str]] = None,
) -> Optional[float]:
    """Max cosine similarity between candidate identity/roles and offer title.

    Fail-open: returns None if no non-empty candidate text or offer title is
    provided, or if the embedding call fails (timeout, quota, network error).
    Callers must treat None as "do not short-circuit evaluation", never mismatch.
    """
    candidates = list(
        dict.fromkeys(
            c.strip()
            for c in [candidate_identity, *(candidate_roles or [])]
            if c and c.strip()
        )
    )
    if not candidates or not offer_title.strip():
        return None

    try:
        from litellm import aembedding

        resp = await aembedding(
            model=EMBEDDING_MODEL,
            input=[*candidates, expand_title_acronyms(offer_title)],
        )
        data = resp.data if hasattr(resp, "data") else resp["data"]

        emb_offer = _extract_embedding(data[-1])
        return max(
            cosine_similarity(_extract_embedding(item), emb_offer)
            for item in data[:-1]
        )
    except Exception as e:
        logger.warning(
            f"⚠️ Erreur pré-filtre de cohérence métier (candidat='{candidate_identity}', "
            f"offre='{offer_title}'): {e}, fail-open (pas de court-circuit)"
        )
        return None
