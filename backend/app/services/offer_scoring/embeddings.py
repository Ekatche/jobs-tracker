"""Texte embarqué des offres et cache `offer_embeddings` (score hybride, Task 2).

Le texte embarqué d'une offre est `expand_title_acronyms(poste) + ". " +`
les 1000 premiers caractères de la description, espaces compressés —
`competences_cles` n'y entre jamais (cf. global-constraints.md). Le cache
Mongo est clé par `{offer_id, model}` : un document d'un autre modèle
d'embedding n'est ni lu ni écrasé, et un `text_hash` différent du texte
courant force un réembarquement (texte d'offre modifié depuis le dernier
calcul).

Fail-open partout où un appel d'embedding réseau peut échouer : on ne
propage jamais l'erreur au-delà de ce module, sauf `embed_texts` elle-même
(le point d'entrée réseau), dont l'appelant (`get_offer_vectors` /
`get_profile_vector`) absorbe l'exception.
"""

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.services.evaluation.domain_relevance import _extract_embedding, expand_title_acronyms
from app.services.offer_scoring.constants import DESCRIPTION_CHARS, EMBED_BATCH, EMBEDDING_MODEL

logger = logging.getLogger(__name__)


def offer_embedding_text(offer: dict) -> Optional[str]:
    """Texte embarqué d'une offre, ou None si l'offre n'a ni intitulé ni description."""
    poste = (offer.get("poste") or "").strip()
    description = offer.get("description") or ""

    poste_is_blank = not poste or poste == "Non spécifié"
    if poste_is_blank and not description.strip():
        return None

    title = expand_title_acronyms(poste)
    # Collapse d'abord, tronque ensuite : COS_FLOOR/COS_CEIL ont été calibrées
    # sur les 1000 premiers caractères du texte déjà nettoyé, pas du texte brut.
    collapsed_description = " ".join(description.split())[:DESCRIPTION_CHARS]
    return f"{title}. {collapsed_description}".strip()


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embarque `texts` par lots de `EMBED_BATCH` via `litellm.aembedding`.

    Chaque lot est tenté au plus 3 fois (1 tentative + 2 retries), avec un
    backoff de 1 s puis 2 s entre les tentatives. Après le 3e échec,
    l'exception est relevée telle quelle : c'est aux appelants
    (`get_offer_vectors`, `get_profile_vector`) de décider du fail-open, pas
    à cette fonction.
    """
    from litellm import aembedding

    vectors: List[List[float]] = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch = texts[i : i + EMBED_BATCH]
        for attempt in range(3):
            try:
                resp = await aembedding(model=EMBEDDING_MODEL, input=batch)
                break
            except Exception:
                if attempt == 2:
                    raise
                await asyncio.sleep(1 if attempt == 0 else 2)
        data = resp.data if hasattr(resp, "data") else resp["data"]
        vectors.extend(_extract_embedding(item) for item in data)
    return vectors


async def get_offer_vectors(
    offers: List[dict],
    db,
    *,
    embed=embed_texts,
    cache: bool = True,
) -> Dict[str, List[float]]:
    """Vecteurs d'embedding des offres, servis par le cache `offer_embeddings` quand possible.

    Fail-open : si `embed` lève, retourne les vecteurs déjà en cache (jamais
    d'exception propagée, pas de texte d'offre journalisé).
    """
    offer_texts: Dict[str, str] = {}
    for offer in offers:
        text = offer_embedding_text(offer)
        if text is None:
            continue
        offer_texts[str(offer["_id"])] = text

    if not offer_texts:
        return {}

    collection = db["offer_embeddings"]
    offer_ids = list(offer_texts.keys())
    cached_docs: Dict[str, dict] = {}
    async for doc in collection.find({"offer_id": {"$in": offer_ids}, "model": EMBEDDING_MODEL}):
        cached_docs[doc["offer_id"]] = doc

    vectors: Dict[str, List[float]] = {}
    missing_ids: List[str] = []
    for offer_id, text in offer_texts.items():
        doc = cached_docs.get(offer_id)
        if doc is not None and doc.get("text_hash") == text_hash(text):
            vectors[offer_id] = doc["vector"]
        else:
            missing_ids.append(offer_id)

    if not missing_ids:
        return vectors

    missing_texts = [offer_texts[offer_id] for offer_id in missing_ids]
    try:
        embedded_vectors = await embed(missing_texts)
        # Un nombre de vecteurs différent du nombre de textes envoyés est une
        # erreur d'embedding comme une autre (réponse tronquée/désalignée) :
        # même traitement fail-open que l'exception ci-dessous, rien n'est
        # mis en cache pour ce lot.
        pairs = list(zip(missing_ids, embedded_vectors, strict=True))
    except Exception as e:
        logger.warning(
            "⚠️ Erreur d'embedding des offres (%d offre(s) manquante(s)), "
            "fail-open : renvoi des seuls vecteurs déjà en cache: %s",
            len(missing_ids),
            e,
        )
        return vectors

    now = datetime.now(timezone.utc)
    for offer_id, vector in pairs:
        vectors[offer_id] = vector
        if cache:
            await collection.update_one(
                {"offer_id": offer_id, "model": EMBEDDING_MODEL},
                {"$set": {"text_hash": text_hash(offer_texts[offer_id]), "vector": vector, "updated_at": now}},
                upsert=True,
            )

    return vectors


async def get_profile_vector(identity: str, *, embed=embed_texts) -> Optional[List[float]]:
    """Vecteur d'embedding de l'identité candidat, None si vide ou si `embed` échoue."""
    if not identity or not identity.strip():
        return None

    try:
        vectors = await embed([identity])
    except Exception as e:
        logger.warning("⚠️ Erreur d'embedding du profil candidat, fail-open (pas de vecteur): %s", e)
        return None

    return vectors[0]
