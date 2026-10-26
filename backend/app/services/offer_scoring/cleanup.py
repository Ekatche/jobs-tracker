"""Purge des documents de scoring orphelins (score de pertinence hybride, Task 6, M14).

`offer_relevance` (un doc par couple utilisateur/offre) et `offer_embeddings`
(un doc par couple offre/modèle) référencent une offre par son `offer_id`,
une chaîne (`str(offer["_id"])`, cf. `offer_profile_matcher.py` et
`offer_scoring/embeddings.py`) — jamais par une vraie clé étrangère Mongo. Une
offre physiquement supprimée de `job_offers` (ou dont l'`offer_id` stocké
n'est même pas un `ObjectId` valide) laisse donc ses documents de scoring
derrière elle indéfiniment, sans purge explicite. Une offre seulement
archivée (`is_deleted: True`) existe toujours physiquement : ses documents
sont conservés.

Bornée par les deux collections de scoring, jamais par `job_offers` : on ne
lit cette dernière que pour les `_id` déjà vus côté scoring (projection
`_id` seule, par lots de 1000 pour rester sous la limite BSON d'un `$in`).
`job_offers` n'est jamais modifiée ici.
"""

import asyncio
import logging

from app.database import get_database
from bson import ObjectId
from bson.errors import InvalidId

logger = logging.getLogger(__name__)

_LOOKUP_BATCH_SIZE = 1000


async def purge_orphan_scoring_docs(db) -> dict:
    """Supprime les docs `offer_relevance`/`offer_embeddings` orphelins.

    Un `offer_id` est orphelin quand il ne correspond à aucun `job_offers._id`
    existant (offre supprimée) ou quand il n'est même pas un `ObjectId`
    valide. Renvoie `{"offer_relevance": <supprimés>, "offer_embeddings":
    <supprimés>}`.
    """
    relevance_collection = db["offer_relevance"]
    embeddings_collection = db["offer_embeddings"]

    relevance_ids = set(await relevance_collection.distinct("offer_id"))
    embeddings_ids = set(await embeddings_collection.distinct("offer_id"))
    tracked_ids = relevance_ids | embeddings_ids
    if not tracked_ids:
        return {"offer_relevance": 0, "offer_embeddings": 0}

    # Un offer_id syntaxiquement invalide ne peut correspondre à aucune
    # offre réelle : orphelin d'office, jamais interrogé contre job_offers.
    object_id_by_offer_id: dict = {}
    orphan_ids: set = set()
    for offer_id in tracked_ids:
        try:
            object_id_by_offer_id[offer_id] = ObjectId(offer_id)
        except (InvalidId, TypeError):
            orphan_ids.add(offer_id)

    existing_object_ids: set = set()
    candidates = list(object_id_by_offer_id.items())
    for i in range(0, len(candidates), _LOOKUP_BATCH_SIZE):
        batch_object_ids = [
            object_id for _, object_id in candidates[i : i + _LOOKUP_BATCH_SIZE]
        ]
        async for doc in db["job_offers"].find(
            {"_id": {"$in": batch_object_ids}}, {"_id": 1}
        ):
            existing_object_ids.add(doc["_id"])

    for offer_id, object_id in candidates:
        if object_id not in existing_object_ids:
            orphan_ids.add(offer_id)

    orphan_list = list(orphan_ids)
    relevance_result = await relevance_collection.delete_many(
        {"offer_id": {"$in": orphan_list}}
    )
    embeddings_result = await embeddings_collection.delete_many(
        {"offer_id": {"$in": orphan_list}}
    )

    return {
        "offer_relevance": relevance_result.deleted_count,
        "offer_embeddings": embeddings_result.deleted_count,
    }


def purge_orphan_scoring_docs_sync() -> dict:
    """Variante synchrone, pour l'appel direct depuis un `PythonOperator` Airflow."""

    async def _run() -> dict:
        db = await get_database()
        return await purge_orphan_scoring_docs(db)

    result = asyncio.run(_run())
    logger.info(
        "Purge des docs de scoring orphelins : %d offer_relevance, %d offer_embeddings supprimés",
        result["offer_relevance"],
        result["offer_embeddings"],
    )
    return result
