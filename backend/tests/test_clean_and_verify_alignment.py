import pytest
from bson import ObjectId
from unittest.mock import AsyncMock, MagicMock, patch

from app.tasks.clean_job_offers import (
    cleanup_invalid_offers,
    cleanup_old_offers,
    is_offer_referenced_by_application,
    normalize_existing_data,
    safe_delete_or_expire_offer,
)
from app.tasks.verify_job_offers import (
    restore_falsely_deleted_offers,
    verify_job_offers_workflow,
)


@pytest.mark.asyncio
async def test_is_offer_referenced_by_application_found():
    db = MagicMock()
    offer_id = ObjectId()
    apps_collection = MagicMock()
    apps_collection.find_one = AsyncMock(return_value={"_id": ObjectId(), "offer_id": str(offer_id)})
    db.__getitem__.side_effect = lambda name: apps_collection if name == "applications" else MagicMock()

    is_ref = await is_offer_referenced_by_application(offer_id, db)
    assert is_ref is True


@pytest.mark.asyncio
async def test_is_offer_referenced_by_application_not_found():
    db = MagicMock()
    offer_id = ObjectId()
    apps_collection = MagicMock()
    apps_collection.find_one = AsyncMock(return_value=None)
    db.__getitem__.side_effect = lambda name: apps_collection if name == "applications" else MagicMock()

    is_ref = await is_offer_referenced_by_application(offer_id, db)
    assert is_ref is False


@pytest.mark.asyncio
async def test_safe_delete_or_expire_offer_when_linked():
    db = MagicMock()
    offer_id = ObjectId()
    apps_collection = MagicMock()
    apps_collection.find_one = AsyncMock(return_value={"_id": ObjectId(), "offer_id": str(offer_id)})
    offers_collection = MagicMock()
    offers_collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    offers_collection.delete_one = AsyncMock()

    db.__getitem__.side_effect = lambda name: apps_collection if name == "applications" else offers_collection

    action = await safe_delete_or_expire_offer(offer_id, offers_collection, db)
    assert action == "expired"
    offers_collection.delete_one.assert_not_called()
    offers_collection.update_one.assert_called_once()
    set_clause = offers_collection.update_one.call_args[0][1]["$set"]
    assert set_clause["is_deleted"] is True
    assert set_clause["pipeline_stage"] == "expired"


@pytest.mark.asyncio
async def test_safe_delete_or_expire_offer_when_unlinked():
    db = MagicMock()
    offer_id = ObjectId()
    apps_collection = MagicMock()
    apps_collection.find_one = AsyncMock(return_value=None)
    offers_collection = MagicMock()
    offers_collection.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))
    offers_collection.update_one = AsyncMock()

    db.__getitem__.side_effect = lambda name: apps_collection if name == "applications" else offers_collection

    action = await safe_delete_or_expire_offer(offer_id, offers_collection, db)
    assert action == "deleted"
    offers_collection.delete_one.assert_called_once_with({"_id": offer_id})
    offers_collection.update_one.assert_not_called()


@pytest.mark.asyncio
async def test_cleanup_old_offers_protects_linked_applications():
    db = MagicMock()
    linked_id = ObjectId()
    unlinked_id = ObjectId()

    # Applications has linked_id
    apps_cursor = MagicMock()
    apps_cursor.to_list = AsyncMock(return_value=[{"offer_id": str(linked_id)}])
    apps_coll = MagicMock()
    apps_coll.find.return_value = apps_cursor

    # Offers collection has both old offers
    offers_coll = MagicMock()
    offers_cursor = MagicMock()
    offers_cursor.to_list = AsyncMock(return_value=[{"_id": linked_id}, {"_id": unlinked_id}])
    offers_coll.find.return_value = offers_cursor
    offers_coll.delete_many = AsyncMock(return_value=MagicMock(deleted_count=1))
    offers_coll.update_many = AsyncMock(return_value=MagicMock(modified_count=1))

    colls = {"applications": apps_coll, "job_offers": offers_coll}
    db.__getitem__.side_effect = lambda name: colls[name]

    with patch("app.tasks.clean_job_offers.get_database", AsyncMock(return_value=db)):
        res = await cleanup_old_offers(days=30)

    assert res["deleted"] == 1
    assert res["soft_expired"] == 1
    # Check delete_many called only for unlinked_id
    delete_filter = offers_coll.delete_many.call_args[0][0]
    assert unlinked_id in delete_filter["_id"]["$in"]
    assert linked_id not in delete_filter["_id"]["$in"]

    # Check update_many called with pipeline_stage: expired for linked_id
    update_set = offers_coll.update_many.call_args[0][1]["$set"]
    assert update_set["pipeline_stage"] == "expired"
    assert update_set["is_deleted"] is True


@pytest.mark.asyncio
async def test_cleanup_invalid_offers_protects_linked_applications():
    db = MagicMock()
    linked_id = ObjectId()
    unlinked_id = ObjectId()

    apps_cursor = MagicMock()
    apps_cursor.to_list = AsyncMock(return_value=[{"offer_id": str(linked_id)}])
    apps_coll = MagicMock()
    apps_coll.find.return_value = apps_cursor

    offers_coll = MagicMock()
    offers_cursor = MagicMock()
    offers_cursor.to_list = AsyncMock(return_value=[{"_id": linked_id}, {"_id": unlinked_id}])
    offers_coll.find.return_value = offers_cursor
    offers_coll.delete_many = AsyncMock(return_value=MagicMock(deleted_count=1))
    offers_coll.update_many = AsyncMock(return_value=MagicMock(modified_count=1))

    colls = {"applications": apps_coll, "job_offers": offers_coll}
    db.__getitem__.side_effect = lambda name: colls[name]

    with patch("app.tasks.clean_job_offers.get_database", AsyncMock(return_value=db)):
        res = await cleanup_invalid_offers()

    assert res["deleted_invalid"] == 1
    assert res["protected_linked"] == 1
    delete_filter = offers_coll.delete_many.call_args[0][0]
    assert unlinked_id in delete_filter["_id"]["$in"]
    assert linked_id not in delete_filter["_id"]["$in"]

    update_set = offers_coll.update_many.call_args[0][1]["$set"]
    assert update_set["pipeline_stage"] == "expired"
    assert update_set["is_deleted"] is True


@pytest.mark.asyncio
async def test_normalize_existing_data_synchronizes_pipeline_stage():
    db = MagicMock()
    doc1 = {"_id": ObjectId(), "is_deleted": True, "entreprise": "Acme"}
    doc2 = {"_id": ObjectId(), "evaluation_score": 4.5, "entreprise": "Beta"}
    doc3 = {"_id": ObjectId(), "is_deleted": False, "entreprise": "Gamma"}

    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=[doc1, doc2, doc3])
    collection = MagicMock()
    collection.find.return_value = cursor
    collection.update_one = AsyncMock()

    db.__getitem__.side_effect = lambda name: collection

    with patch("app.tasks.clean_job_offers.get_database", AsyncMock(return_value=db)):
        await normalize_existing_data()

    assert collection.update_one.call_count == 3
    calls = collection.update_one.call_args_list

    # doc1 is deleted -> pipeline_stage: expired
    assert calls[0][0][1]["$set"]["pipeline_stage"] == "expired"
    # doc2 has evaluation_score -> pipeline_stage: evaluated
    assert calls[1][0][1]["$set"]["pipeline_stage"] == "evaluated"
    # doc3 has neither -> pipeline_stage: discovered
    assert calls[2][0][1]["$set"]["pipeline_stage"] == "discovered"


@pytest.mark.asyncio
async def test_verify_job_offers_sets_pipeline_stage_expired():
    db = MagicMock()
    offer_id = ObjectId()
    offer_doc = {
        "_id": offer_id,
        "url": "https://example.com/job/123",
        "entreprise": "Acme",
        "poste": "Data Scientist",
    }

    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.limit.return_value = cursor
    cursor.to_list = AsyncMock(return_value=[offer_doc])

    collection = MagicMock()
    collection.find.return_value = cursor
    collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    db.__getitem__.side_effect = lambda name: collection

    # Mock verify_single_offer to return closed offer
    mock_verify = AsyncMock(
        return_value={
            "offer_id": str(offer_id),
            "is_valid": False,
            "status": "closed",
            "reason": "http_404",
            "url": "https://example.com/job/123",
        }
    )

    with (
        patch("app.tasks.verify_job_offers.get_database", AsyncMock(return_value=db)),
        patch("app.tasks.verify_job_offers.verify_single_offer", mock_verify),
    ):
        result = await verify_job_offers_workflow(dry_run=False, limit=1)

    assert result["closed_count"] == 1
    assert result["updated_db_count"] == 1
    collection.update_one.assert_called_once()
    update_set = collection.update_one.call_args[0][1]["$set"]
    assert update_set["is_deleted"] is True
    assert update_set["pipeline_stage"] == "expired"
    assert update_set["deletion_reason"] == "http_404"


@pytest.mark.asyncio
async def test_restore_falsely_deleted_offers_sets_pipeline_stage_discovered():
    db = MagicMock()
    collection = MagicMock()
    collection.count_documents = AsyncMock(return_value=2)
    collection.update_many = AsyncMock(return_value=MagicMock(modified_count=2))
    db.__getitem__.side_effect = lambda name: collection

    with patch("app.tasks.verify_job_offers.get_database", AsyncMock(return_value=db)):
        result = await restore_falsely_deleted_offers(dry_run=False)

    assert result["restored"] == 2
    collection.update_many.assert_called_once()
    update_set = collection.update_many.call_args[0][1]["$set"]
    assert update_set["is_deleted"] is False
    assert update_set["pipeline_stage"] == "discovered"
