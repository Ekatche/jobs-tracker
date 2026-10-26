"""Tests de `offer_scoring.cleanup` : purge des docs de scoring orphelins (Task 6, M14).

Contre la vraie base de test (127.0.0.1:27018, cf. conftest.py) : `distinct`,
`delete_many` multi-collections et la correspondance avec `job_offers._id`
(`ObjectId`) ne peuvent pas être vérifiés avec un faux client Mongo. Chaque
test nettoie les documents qu'il sème (le reste de la suite partage la même
base le temps d'une session pytest)."""

from app.services.offer_scoring.cleanup import purge_orphan_scoring_docs
from bson import ObjectId


def _scoring_docs(offer_id: str):
    """Un doc minimal par collection pour un `offer_id` donné."""
    return (
        {"user_id": str(ObjectId()), "offer_id": offer_id, "score": 50},
        {"offer_id": offer_id, "model": "mistral-embed", "vector": [0.1, 0.2]},
    )


async def test_purge_orphan_scoring_docs_removes_absent_and_invalid_ids_only(test_db):
    existing_offer_id = ObjectId()
    deleted_offer_id = ObjectId()
    absent_offer_id = ObjectId()  # jamais inséré dans job_offers
    invalid_offer_id = "not-an-object-id"

    await test_db["job_offers"].insert_many(
        [
            {"_id": existing_offer_id, "poste": "Existe", "is_deleted": False},
            {"_id": deleted_offer_id, "poste": "Archivée", "is_deleted": True},
        ]
    )

    tracked_ids = [
        str(existing_offer_id),
        str(deleted_offer_id),
        str(absent_offer_id),
        invalid_offer_id,
    ]
    relevance_docs = []
    embedding_docs = []
    for offer_id in tracked_ids:
        relevance_doc, embedding_doc = _scoring_docs(offer_id)
        relevance_docs.append(relevance_doc)
        embedding_docs.append(embedding_doc)

    await test_db["offer_relevance"].insert_many(relevance_docs)
    await test_db["offer_embeddings"].insert_many(embedding_docs)

    try:
        result = await purge_orphan_scoring_docs(test_db)

        assert result == {"offer_relevance": 2, "offer_embeddings": 2}

        remaining_relevance_ids = {
            doc["offer_id"]
            async for doc in test_db["offer_relevance"].find(
                {"offer_id": {"$in": tracked_ids}}
            )
        }
        remaining_embedding_ids = {
            doc["offer_id"]
            async for doc in test_db["offer_embeddings"].find(
                {"offer_id": {"$in": tracked_ids}}
            )
        }

        assert remaining_relevance_ids == {
            str(existing_offer_id),
            str(deleted_offer_id),
        }
        assert remaining_embedding_ids == {
            str(existing_offer_id),
            str(deleted_offer_id),
        }

        # Idempotent : plus rien à purger au second appel.
        second_result = await purge_orphan_scoring_docs(test_db)
        assert second_result == {"offer_relevance": 0, "offer_embeddings": 0}
    finally:
        await test_db["job_offers"].delete_many(
            {"_id": {"$in": [existing_offer_id, deleted_offer_id]}}
        )
        await test_db["offer_relevance"].delete_many({"offer_id": {"$in": tracked_ids}})
        await test_db["offer_embeddings"].delete_many(
            {"offer_id": {"$in": tracked_ids}}
        )
