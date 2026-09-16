import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from bson import ObjectId
from app.routers.applications import update_application, _generate_cover_letter_bg
from app.models import JobApplicationUpdate, ApplicationStatus

import sys
from pathlib import Path

job_trackers_path = Path(__file__).parent.parent / "job_trackers" / "src" / "job_trackers"
if str(job_trackers_path) not in sys.path:
    sys.path.insert(0, str(job_trackers_path))

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

    with patch("app.routers.applications._generate_cover_letter_bg") as mock_bg_fn, \
         patch("app.routers.applications.require_user_quota", new=AsyncMock()):
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

    mock_db["cover_letters"].find_one = AsyncMock(return_value={"_id": ObjectId(), "status": "ready"})
    mock_db["cover_letters"].insert_one = AsyncMock()

    await _generate_cover_letter_bg(app_id, user_id, mock_db)
    mock_db["cover_letters"].insert_one.assert_not_called()


@pytest.mark.asyncio
async def test_cover_letter_bg_missing_profile():
    app_id = ObjectId()
    user_id = ObjectId()
    letter_id = ObjectId()

    cover_letters_coll = MagicMock()
    cover_letters_coll.find_one = AsyncMock(return_value=None)
    inserted = MagicMock()
    inserted.inserted_id = letter_id
    cover_letters_coll.insert_one = AsyncMock(return_value=inserted)
    cover_letters_coll.update_one = AsyncMock()

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
    cover_letters_coll.update_one.assert_called_once()
    call_args = cover_letters_coll.update_one.call_args[0]
    assert call_args[0] == {"_id": letter_id}
    assert call_args[1]["$set"]["status"] == "failed"
    assert call_args[1]["$set"]["error"] == "profile_missing"


@pytest.mark.asyncio
async def test_failed_letter_does_not_block_a_later_run():
    """Profil complété après un échec : la génération doit repartir."""
    app_id = ObjectId()
    user_id = ObjectId()
    old_failed_id = ObjectId()
    new_letter_id = ObjectId()

    cover_letters_coll = MagicMock()
    cover_letters_coll.find_one = AsyncMock(
        return_value={"_id": old_failed_id, "status": "failed", "error": "profile_missing"}
    )
    cover_letters_coll.delete_many = AsyncMock()
    inserted = MagicMock()
    inserted.inserted_id = new_letter_id
    cover_letters_coll.insert_one = AsyncMock(return_value=inserted)
    cover_letters_coll.update_one = AsyncMock()

    apps_coll = MagicMock()
    apps_coll.find_one = AsyncMock(return_value={"_id": app_id, "description": "Desc", "company": "Acme"})

    profile_coll = MagicMock()
    profile_coll.find_one = AsyncMock(return_value={"headline": "Data Engineer"})

    users_coll = MagicMock()
    users_coll.find_one = AsyncMock(return_value={"full_name": "Jane Doe"})

    colls = {
        "cover_letters": cover_letters_coll,
        "applications": apps_coll,
        "candidate_profile": profile_coll,
        "users": users_coll,
    }
    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda k: colls[k]

    pipeline_called = False

    def fake_pipeline(*args, **kwargs):
        nonlocal pipeline_called
        pipeline_called = True
        return {
            "body": "Lettre générée",
            "revised": False,
            "critic_verdict": {"verdict": "pass", "flaws": []},
            "guard_report": {"violations": []},
            "models": {},
            "prompt_version": "02_style-v1",
        }

    with patch("cover_letter_crew.run_letter_pipeline_sync", side_effect=fake_pipeline):
        await _generate_cover_letter_bg(app_id, user_id, mock_db)

    cover_letters_coll.delete_many.assert_called_once_with(
        {"application_id": app_id, "status": "failed"}
    )
    assert pipeline_called is True


@pytest.mark.asyncio
async def test_append_letter_version_appends_without_overwriting_previous_versions():
    from app.routers.applications import _append_letter_version

    letter_id = ObjectId()
    cover_letters_coll = MagicMock()
    cover_letters_coll.find_one = AsyncMock(side_effect=[
        {"_id": letter_id, "versions": [{"n": 1, "body": "Version éditée", "origin": "edited"}]},
        {"_id": letter_id, "versions": [
            {"n": 1, "body": "Version éditée", "origin": "edited"},
            {"n": 2, "body": "Régénérée", "origin": "generated"},
        ]},
    ])
    cover_letters_coll.update_one = AsyncMock()

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda k: cover_letters_coll

    v1 = {"body": "Régénérée", "origin": "generated"}
    await _append_letter_version(mock_db, letter_id, v1)
    assert v1["n"] == 2

    v2 = {"body": "Encore régénérée", "origin": "generated"}
    await _append_letter_version(mock_db, letter_id, v2)
    assert v2["n"] == 3

    pushed_ns = [c.args[1]["$push"]["versions"]["n"] for c in cover_letters_coll.update_one.call_args_list]
    assert pushed_ns == [2, 3]
