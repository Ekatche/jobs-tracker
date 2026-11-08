"""Statut `needs_review` des lettres : garde bloquante persistante, sortie par édition, export."""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId

from app.routers.applications import _generate_cover_letter_bg
from tests.conftest import USER_ID

job_trackers_path = Path(__file__).parent.parent / "job_trackers" / "src" / "job_trackers"
if str(job_trackers_path) not in sys.path:
    sys.path.insert(0, str(job_trackers_path))

OFFER = "Offre Data Engineer chez Acme : pipelines Python."
ANALYST = {"missions": ["Pipelines"], "stacks": ["Python"], "companies": [], "projects": []}
BLOCKING = {"is_blocking": True, "violations": ["Point d'exclamation (!) interdit"], "warnings": [], "stats": {}}
_PARAGRAPH = (
    "Je construis des pipelines Python robustes pour des équipes qui exploitent "
    "des données volumineuses. Mon travail consiste à fiabiliser les chargements, "
    "à mesurer la qualité des sources et à documenter chaque décision technique. "
    "Cette approche rend les analyses reproductibles et facilite la reprise par d'autres."
)
CLEAN_BODY = "\n\n".join(["Madame, Monsieur,"] + [_PARAGRAPH] * 5)
DIRTY_BODY = CLEAN_BODY + " Merci !"
ACK_MESSAGE = "points à corriger"


def _pipeline_result(guard_report):
    return {
        "body": DIRTY_BODY,
        "revised": True,
        "critic_verdict": {"verdict": "pass", "flaws": []},
        "guard_report": guard_report,
        "guard_context": {"analyst_data": ANALYST},
        "models": {},
        "prompt_version": "test",
    }


async def _seed_application(db):
    app_id = ObjectId()
    await db["applications"].insert_one({
        "_id": app_id, "user_id": ObjectId(USER_ID), "company": "Acme",
        "position": "Data Engineer", "description": OFFER,
    })
    await db["candidate_profile"].insert_one({"user_id": ObjectId(USER_ID), "headline": "Data Engineer"})
    await db["users"].insert_one({"_id": ObjectId(USER_ID), "full_name": "Jane Doe"})
    return app_id


async def _seed_letter(db, app_id, status, guard_context=True, guard_report=None):
    version = {"n": 1, "body": DIRTY_BODY, "origin": "generated", "guard_report": guard_report or {}}
    letter = {
        "_id": ObjectId(), "user_id": ObjectId(USER_ID), "application_id": app_id,
        "status": status, "current_version": 1, "versions": [version],
    }
    if guard_context:
        letter["guard_context"] = {"analyst_data": ANALYST}
    await db["cover_letters"].insert_one(letter)


async def _generate(db, app_id, guard_report):
    with patch(
        "cover_letter_crew.run_letter_pipeline_async",
        new_callable=AsyncMock,
        return_value=_pipeline_result(guard_report),
    ) as pipeline:
        await _generate_cover_letter_bg(app_id, ObjectId(USER_ID), db)
    return pipeline


@pytest.mark.asyncio
async def test_blocking_guard_report_yields_needs_review_with_text_and_history(client, letter_db):
    app_id = await _seed_application(letter_db)
    await _generate(letter_db, app_id, BLOCKING)

    res = client.get(f"/applications/{app_id}/cover-letter")
    data = res.json()
    assert data["status"] == "needs_review"
    assert data["versions"][0]["body"] == DIRTY_BODY
    assert data["versions"][0]["guard_report"]["violations"] == BLOCKING["violations"]
    assert "guard_context" not in data
    stored = await letter_db["cover_letters"].find_one({"application_id": app_id})
    assert stored["guard_context"] == {"analyst_data": ANALYST}


@pytest.mark.asyncio
async def test_clean_guard_report_yields_ready(client, letter_db):
    app_id = await _seed_application(letter_db)
    await _generate(letter_db, app_id, {"is_blocking": False, "violations": []})
    assert client.get(f"/applications/{app_id}/cover-letter").json()["status"] == "ready"


@pytest.mark.parametrize("new_body, expected_status, expected_violations", [
    (CLEAN_BODY, "ready", []),
    (CLEAN_BODY + " Cordialement !", "needs_review", ["Point d'exclamation (!) interdit"]),
])
@pytest.mark.asyncio
async def test_edit_reevaluates_guards_without_llm(
    client, letter_db, new_body, expected_status, expected_violations
):
    app_id = await _seed_application(letter_db)
    await _seed_letter(letter_db, app_id, "needs_review", guard_report=BLOCKING)

    res = client.patch(f"/applications/{app_id}/cover-letter", json={"body": new_body})

    assert res.status_code == 200
    data = res.json()
    assert "guard_context" not in data
    assert data["status"] == expected_status
    latest = data["versions"][-1]
    assert latest["origin"] == "edited"
    assert latest["guard_report"]["is_blocking"] is (expected_status == "needs_review")
    assert latest["guard_report"]["violations"] == expected_violations
    assert len(data["versions"]) == 2


@pytest.mark.asyncio
async def test_edit_of_legacy_ready_letter_without_context_stays_ready(client, letter_db):
    app_id = await _seed_application(letter_db)
    await _seed_letter(letter_db, app_id, "ready", guard_context=False)

    res = client.patch(f"/applications/{app_id}/cover-letter", json={"body": DIRTY_BODY})

    data = res.json()
    assert data["status"] == "ready"
    assert "guard_report" not in data["versions"][-1]


@pytest.mark.parametrize("query, status, expected_code", [
    ("", "needs_review", 409),
    ("?acknowledge_review=true", "needs_review", 200),
    ("?acknowledge_review=true", "pending", 404),
])
@pytest.mark.asyncio
async def test_pdf_export_contract_and_status_untouched(client, letter_db, query, status, expected_code):
    app_id = await _seed_application(letter_db)
    await _seed_letter(letter_db, app_id, status, guard_report=BLOCKING)

    with patch("app.routers.cover_letters.generate_cv_pdf", new_callable=AsyncMock, return_value=b"%PDF-x"):
        res = client.get(f"/applications/{app_id}/cover-letter/pdf{query}")

    assert res.status_code == expected_code
    if expected_code == 409:
        assert ACK_MESSAGE in res.json()["detail"]
    letter = await letter_db["cover_letters"].find_one({"application_id": app_id})
    assert letter["status"] == status
