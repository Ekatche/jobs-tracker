import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from bson import ObjectId
from app.routers.applications import update_application, _generate_cover_letter_bg
from app.models import JobApplicationUpdate, ApplicationStatus

@pytest.mark.asyncio
async def test_trigger_cover_letter_on_etude_transition():
    mock_db = MagicMock()
    app_id = str(ObjectId())
    user_id = str(ObjectId())

    # Candidature existante avec statut APPLIED
    mock_db["applications"].find_one = AsyncMock(side_effect=[
        {"_id": ObjectId(app_id), "user_id": ObjectId(user_id), "status": ApplicationStatus.APPLIED, "description": "Desc"},
        {"_id": ObjectId(app_id), "user_id": ObjectId(user_id), "status": ApplicationStatus.ETUDE, "description": "Desc"}
    ])
    mock_db["applications"].update_one = AsyncMock()

    bg_tasks = MagicMock()
    current_user = MagicMock(id=user_id)

    with patch("app.routers.applications._generate_cover_letter_bg") as mock_bg_fn:
        await update_application(
            background_tasks=bg_tasks,
            application_id=app_id,
            application_data=JobApplicationUpdate(status=ApplicationStatus.ETUDE),
            db=mock_db,
            current_user=current_user
        )
        bg_tasks.add_task.assert_called()
        # Verify first arg passed to add_task is _generate_cover_letter_bg
        args, _ = bg_tasks.add_task.call_args
        assert args[0] == mock_bg_fn

@pytest.mark.asyncio
async def test_cover_letter_bg_idempotency():
    mock_db = MagicMock()
    app_id = ObjectId()
    user_id = ObjectId()

    mock_db["cover_letters"].find_one = AsyncMock(return_value={"_id": ObjectId()})
    mock_db["cover_letters"].insert_one = AsyncMock()

    await _generate_cover_letter_bg(app_id, user_id, mock_db)
    mock_db["cover_letters"].insert_one.assert_not_called()

@pytest.mark.asyncio
async def test_cover_letter_bg_missing_profile():
    app_id = ObjectId()
    user_id = ObjectId()

    cover_letters_coll = MagicMock()
    cover_letters_coll.find_one = AsyncMock(return_value=None)
    cover_letters_coll.insert_one = AsyncMock()

    apps_coll = MagicMock()
    apps_coll.find_one = AsyncMock(return_value={"_id": app_id, "description": "Valid desc"})

    profile_coll = MagicMock()
    profile_coll.find_one = AsyncMock(return_value=None)

    colls = {
        "cover_letters": cover_letters_coll,
        "applications": apps_coll,
        "candidate_profile": profile_coll,
    }
    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda k: colls[k]

    await _generate_cover_letter_bg(app_id, user_id, mock_db)
    cover_letters_coll.insert_one.assert_called_once()
    doc_inserted = cover_letters_coll.insert_one.call_args[0][0]
    assert doc_inserted["status"] == "failed"
    assert doc_inserted["error"] == "profile_missing"
