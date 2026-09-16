from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.database import get_database
from app.models import (
    ApplicationStatus,
    BlocA,
    BlocB,
    BlocG,
    JobApplication,
    JobApplicationCreate,
    JobApplicationResponse,
    OfferEvaluationResponse,
    PipelineSummaryResponse,
    UserModel,
    UserTier,
)
from app.routers.applications import enrich_application_with_cadences
from main import app

TEST_USER_ID = "507f1f77bcf86cd799439011"
TEST_OFFER_ID = "507f1f77bcf86cd799439022"


# --- Unit Tests: Models & Status ---

def test_application_status_enum_values():
    assert ApplicationStatus.OFFER_RECEIVED.value == "Offre reçue"
    assert ApplicationStatus.OFFER.value == "Offre reçue"
    assert ApplicationStatus.APPLIED.value == "Candidature envoyée"
    assert ApplicationStatus.INTERVIEW.value == "Entretien"


def test_job_application_model_with_offer_id():
    app_doc = JobApplication(
        user_id=TEST_USER_ID,
        offer_id=TEST_OFFER_ID,
        company="FinTech Corp",
        position="Backend Engineer",
        status=ApplicationStatus.APPLIED,
    )
    assert app_doc.offer_id == TEST_OFFER_ID
    assert app_doc.status == ApplicationStatus.APPLIED


# --- Unit Tests: Follow-up Cadences (J+7 / J+1) ---

def test_cadences_applied_follow_up_due():
    eight_days_ago = datetime.now(timezone.utc) - timedelta(days=8)
    app_dict = {
        "status": ApplicationStatus.APPLIED.value,
        "application_date": eight_days_ago.isoformat(),
    }
    enriched = enrich_application_with_cadences(app_dict)
    assert enriched["days_since_application"] >= 8
    assert enriched["follow_up_alert"] == "relance_due"


def test_cadences_applied_recent_no_alert():
    two_days_ago = datetime.now(timezone.utc) - timedelta(days=2)
    app_dict = {
        "status": ApplicationStatus.APPLIED.value,
        "application_date": two_days_ago.isoformat(),
    }
    enriched = enrich_application_with_cadences(app_dict)
    assert enriched["days_since_application"] == 2
    assert enriched["follow_up_alert"] is None


def test_cadences_interview_thank_you_due():
    yesterday = datetime.now(timezone.utc) - timedelta(days=2)
    app_dict = {
        "status": ApplicationStatus.INTERVIEW.value,
        "application_date": yesterday.isoformat(),
    }
    enriched = enrich_application_with_cadences(app_dict)
    assert enriched["days_since_application"] >= 1
    assert enriched["follow_up_alert"] == "remerciement_due"


# --- Endpoint Tests: GET /applications/pipeline/summary ---

def test_get_pipeline_summary_endpoint():
    mock_user = UserModel(
        id=TEST_USER_ID,
        username="kanban_user",
        email="kanban@test.com",
        hashed_password="secret_password",
        tier=UserTier.FREE,
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user

    mock_db = MagicMock()
    app_col = AsyncMock()
    eval_col = AsyncMock()

    now = datetime.now(timezone.utc)
    eight_days_ago = now - timedelta(days=8)
    two_days_ago = now - timedelta(days=2)

    sample_apps = [
        # 1. Candidature envoyée depuis 8 jours -> relance due
        {
            "_id": ObjectId(),
            "user_id": ObjectId(TEST_USER_ID),
            "company": "Company A",
            "position": "Dev Python",
            "offer_id": TEST_OFFER_ID,
            "status": ApplicationStatus.APPLIED.value,
            "application_date": eight_days_ago,
            "archived": False,
            "created_at": eight_days_ago,
        },
        # 2. Entretien depuis 2 jours -> remerciement due
        {
            "_id": ObjectId(),
            "user_id": ObjectId(TEST_USER_ID),
            "company": "Company B",
            "position": "Lead Tech",
            "status": ApplicationStatus.INTERVIEW.value,
            "application_date": two_days_ago,
            "archived": False,
            "created_at": two_days_ago,
        },
        # 3. Offre reçue
        {
            "_id": ObjectId(),
            "user_id": ObjectId(TEST_USER_ID),
            "company": "Company C",
            "position": "Staff Eng",
            "status": ApplicationStatus.OFFER_RECEIVED.value,
            "application_date": two_days_ago,
            "archived": False,
            "created_at": two_days_ago,
        },
        # 4. Candidature archivée
        {
            "_id": ObjectId(),
            "user_id": ObjectId(TEST_USER_ID),
            "company": "Company D",
            "position": "Analyst",
            "status": ApplicationStatus.REJECTED.value,
            "application_date": eight_days_ago,
            "archived": True,
            "created_at": eight_days_ago,
        },
    ]

    cursor_mock = MagicMock()
    cursor_mock.to_list = AsyncMock(return_value=sample_apps)
    app_col.find = MagicMock(return_value=cursor_mock)
    eval_col.count_documents = AsyncMock(return_value=5)

    def db_lookup(name):
        if name == "applications":
            return app_col
        elif name == "offer_evaluations":
            return eval_col
        return AsyncMock()

    mock_db.__getitem__.side_effect = db_lookup
    app.dependency_overrides[get_database] = lambda: mock_db

    client = TestClient(app)

    try:
        response = client.get("/applications/pipeline/summary")
        assert response.status_code == 200, response.text
        data = response.json()

        assert data["total_active"] == 3
        assert data["total_archived"] == 1
        assert data["follow_ups_due_count"] == 1
        assert data["thank_yous_due_count"] == 1
        assert data["evaluated_offers_ready_count"] == 5
        # Total started = 4 (Company A, B, C, D)
        # Interview stages = 2 (Company B entretien + Company C offre reçue) -> 2/4 = 50.0%
        # Offer stages = 1 (Company C offre reçue) -> 1/4 = 25.0%
        assert data["interview_conversion_rate"] == 50.0
        assert data["offer_conversion_rate"] == 25.0

    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_database, None)


def test_pipeline_summary_with_en_etude():
    mock_user = UserModel(
        id=TEST_USER_ID,
        username="etude_user",
        email="etude@test.com",
        hashed_password="secret_password",
        tier=UserTier.FREE,
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user

    mock_db = MagicMock()
    app_col = AsyncMock()
    eval_col = AsyncMock()

    sample_apps = [
        {
            "_id": ObjectId(),
            "user_id": ObjectId(TEST_USER_ID),
            "company": "Company In Study",
            "position": "Research Eng",
            "status": ApplicationStatus.ETUDE.value,
            "application_date": datetime.now(timezone.utc),
            "archived": False,
            "created_at": datetime.now(timezone.utc),
        }
    ]

    cursor_mock = MagicMock()
    cursor_mock.to_list = AsyncMock(return_value=sample_apps)
    app_col.find = MagicMock(return_value=cursor_mock)
    eval_col.count_documents = AsyncMock(return_value=0)

    def db_lookup(name):
        if name == "applications":
            return app_col
        elif name == "offer_evaluations":
            return eval_col
        return AsyncMock()

    mock_db.__getitem__.side_effect = db_lookup
    app.dependency_overrides[get_database] = lambda: mock_db

    client = TestClient(app)
    try:
        response = client.get("/applications/pipeline/summary")
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["total_active"] == 1
        assert data["status_counts"]["En étude"] == 1
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_database, None)


def test_evaluate_application_endpoint():
    mock_user = UserModel(
        id=TEST_USER_ID,
        username="eval_app_user",
        email="eval_app@test.com",
        hashed_password="secret_password",
        tier=UserTier.FREE,
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user

    mock_db = MagicMock()
    app_col = AsyncMock()
    job_offers_col = AsyncMock()
    eval_col = AsyncMock()

    app_id = str(ObjectId())
    app_doc = {
        "_id": ObjectId(app_id),
        "user_id": ObjectId(TEST_USER_ID),
        "company": "Deloitte",
        "position": "AI Engineer",
        "description": "Poste IA / Python / FastAPI",
        "status": "En étude",
        "offer_id": None,
    }

    app_col.find_one = AsyncMock(return_value=app_doc)
    app_col.update_one = AsyncMock()
    job_offers_col.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId(TEST_OFFER_ID)))
    job_offers_col.find_one = AsyncMock(return_value=None)

    def db_lookup(name):
        if name == "applications":
            return app_col
        elif name == "job_offers":
            return job_offers_col
        elif name == "offer_evaluations":
            return eval_col
        return AsyncMock()

    mock_db.__getitem__.side_effect = db_lookup
    app.dependency_overrides[get_database] = lambda: mock_db

    fake_eval = OfferEvaluationResponse(
        id=str(ObjectId()),
        user_id=TEST_USER_ID,
        offer_id=TEST_OFFER_ID,
        score=4.2,
        headline="Très forte adéquation",
        pipeline_stage="evaluated",
        bloc_a=BlocA(archetype="AI Engineer", geo_mismatch=False, visa_sponsorship_refused=False),
        bloc_b=BlocB(matched_requirements=[], missing_requirements=[]),
        bloc_g=BlocG(is_ghost_job=False, is_scam_risk=False),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    client = TestClient(app)
    try:
        with patch("app.routers.applications.evaluate_offer_two_pass", AsyncMock(return_value=fake_eval)):
            response = client.post(f"/applications/{app_id}/evaluate")
            assert response.status_code == 200, response.text
            data = response.json()
            assert data["score"] == 4.2
            assert data["bloc_a"]["archetype"] == "AI Engineer"
            # Verify offer_id was generated and linked
            app_col.update_one.assert_called_once()
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_database, None)


def test_get_application_evaluation_endpoint():
    mock_user = UserModel(
        id=TEST_USER_ID,
        username="eval_app_user",
        email="eval_app@test.com",
        hashed_password="secret_password",
        tier=UserTier.FREE,
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user

    mock_db = MagicMock()
    app_col = AsyncMock()
    eval_col = AsyncMock()

    app_id = str(ObjectId())
    app_doc = {
        "_id": ObjectId(app_id),
        "user_id": ObjectId(TEST_USER_ID),
        "company": "Deloitte",
        "position": "AI Engineer",
        "offer_id": TEST_OFFER_ID,
    }

    eval_doc = {
        "_id": ObjectId(),
        "user_id": TEST_USER_ID,
        "offer_id": TEST_OFFER_ID,
        "score": 4.5,
        "headline": "Excellente opportunité",
        "pipeline_stage": "evaluated",
        "bloc_a": {"archetype": "AI Engineer", "geo_mismatch": False, "visa_sponsorship_refused": False},
        "bloc_b": {"matched_requirements": [], "missing_requirements": []},
        "bloc_g": {"is_ghost_job": False, "is_scam_risk": False},
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    app_col.find_one = AsyncMock(return_value=app_doc)
    eval_col.find_one = AsyncMock(return_value=eval_doc)

    def db_lookup(name):
        if name == "applications":
            return app_col
        elif name == "offer_evaluations":
            return eval_col
        return AsyncMock()

    mock_db.__getitem__.side_effect = db_lookup
    app.dependency_overrides[get_database] = lambda: mock_db

    client = TestClient(app)
    try:
        response = client.get(f"/applications/{app_id}/evaluation")
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["score"] == 4.5
        assert data["bloc_a"]["archetype"] == "AI Engineer"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_database, None)


