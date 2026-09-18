import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
from fastapi.testclient import TestClient

from main import app
from app.auth import get_current_user
from app.database import get_database
from app.models import (
    UserModel,
    TailoredCVSchema,
    TailoredExperienceItem,
    TailoredSkillGroup,
    TailoredLanguage,
    TailoredEducationItem,
)


@pytest.fixture(autouse=True)
def _clean_dependency_overrides():
    snapshot = dict(app.dependency_overrides)
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(snapshot)


MOCK_USER_ID = "60c72b2f9b1d8b2bad7f9999"
mock_current_user = UserModel(
    id=MOCK_USER_ID,
    username="testengineer",
    email="test@example.com",
    hashed_password="pw"
)

SAMPLE_CV_SCHEMA = TailoredCVSchema(
    target_role_title="Senior Python Engineer",
    professional_summary="Architecte backend expérimenté.",
    prioritized_skills=[
        TailoredSkillGroup(category="Backend", skills=["Python", "FastAPI"])
    ],
    experiences=[
        TailoredExperienceItem(
            title="Senior Dev",
            company="Acme Corp",
            start_date="2021",
            bullet_points=["Built microservices."]
        )
    ],
    featured_projects=[],
    education=[
        TailoredEducationItem(degree="Master", institution="Tech School", year="2020")
    ],
    languages=[
        TailoredLanguage(language="Français", level="Natif")
    ],
    certifications=[]
)


def create_mock_db(colls):
    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda k: colls[k]
    return mock_db


def test_get_resumes_unauthorized(client):
    app.dependency_overrides.pop(get_current_user, None)
    res = client.get("/resumes")
    assert res.status_code == 401


def test_generate_resume_missing_profile(client):
    colls = {
        "candidate_profile": MagicMock(find_one=AsyncMock(return_value=None)),
    }
    mock_db = create_mock_db(colls)

    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_database] = lambda: mock_db

    with patch("app.routers.resumes.require_user_quota", new_callable=AsyncMock):
        res = client.post("/resumes/generate", json={"offer_id": str(ObjectId())})
        assert res.status_code == 400
        assert "Profil candidat introuvable" in res.json()["detail"]


def test_generate_resume_success(client):
    offer_id = ObjectId()
    mock_offer = {
        "_id": offer_id,
        "title": "Senior Python Engineer",
        "company": "Fintech France",
        "location": "Paris",
        "description": "Poste Python/FastAPI",
    }
    mock_profile = {
        "_id": ObjectId(),
        "user_id": ObjectId(MOCK_USER_ID),
        "full_name": "Jean Dupont",
        "skills": ["Python", "FastAPI"],
        "experiences": [{"title": "Dev", "company": "Acme Corp"}],
    }

    colls = {
        "candidate_profile": MagicMock(find_one=AsyncMock(return_value=mock_profile)),
        "job_offers": MagicMock(find_one=AsyncMock(return_value=mock_offer)),
        "offer_evaluations": MagicMock(find_one=AsyncMock(return_value=None)),
        "tailored_resumes": MagicMock(insert_one=AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))),
    }
    mock_db = create_mock_db(colls)

    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_database] = lambda: mock_db

    with patch("app.routers.resumes.generate_tailored_cv_content", new_callable=AsyncMock) as mock_generate, \
         patch("app.routers.resumes.require_user_quota", new_callable=AsyncMock) as mock_quota, \
         patch("app.routers.resumes.record_api_usage", new_callable=AsyncMock) as mock_record:

        mock_generate.return_value = SAMPLE_CV_SCHEMA

        res = client.post(
            "/resumes/generate",
            json={"offer_id": str(offer_id), "template": "sidebar_elegance"}
        )

        assert res.status_code == 200
        data = res.json()
        assert data["target_role"] == "Senior Python Engineer"
        assert data["target_company"] == "Fintech France"
        assert data["content"]["target_role_title"] == "Senior Python Engineer"
        mock_quota.assert_called_once()
        mock_record.assert_called_once()


def test_list_resumes(client):
    resume_doc = {
        "_id": ObjectId(),
        "user_id": ObjectId(MOCK_USER_ID),
        "offer_id": ObjectId(),
        "target_role": "Backend Lead",
        "target_company": "Cloud SA",
        "template": "executive_minimalist",
        "with_photo": False,
        "content": SAMPLE_CV_SCHEMA.model_dump(),
        "created_at": "2026-09-18T10:00:00Z",
        "updated_at": "2026-09-18T10:00:00Z",
    }

    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=[resume_doc])
    cursor.sort = MagicMock(return_value=cursor)

    colls = {
        "tailored_resumes": MagicMock(find=MagicMock(return_value=cursor)),
    }
    mock_db = create_mock_db(colls)

    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_database] = lambda: mock_db

    res = client.get("/resumes")
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["target_role"] == "Backend Lead"


def test_get_and_delete_resume(client):
    resume_id = ObjectId()
    resume_doc = {
        "_id": resume_id,
        "user_id": ObjectId(MOCK_USER_ID),
        "target_role": "Backend Lead",
        "target_company": "Cloud SA",
        "template": "sidebar_elegance",
        "content": SAMPLE_CV_SCHEMA.model_dump(),
    }

    colls = {
        "tailored_resumes": MagicMock(
            find_one=AsyncMock(return_value=resume_doc),
            delete_one=AsyncMock(return_value=MagicMock(deleted_count=1))
        )
    }
    mock_db = create_mock_db(colls)

    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_database] = lambda: mock_db

    # Get
    res = client.get(f"/resumes/{resume_id}")
    assert res.status_code == 200
    assert res.json()["target_role"] == "Backend Lead"

    # Delete
    del_res = client.delete(f"/resumes/{resume_id}")
    assert del_res.status_code == 200
    assert del_res.json() == {"status": "deleted"}


def test_get_resume_pdf_stream(client):
    resume_id = ObjectId()
    resume_doc = {
        "_id": resume_id,
        "user_id": ObjectId(MOCK_USER_ID),
        "target_role": "Lead Architect",
        "target_company": "Cloud SA",
        "template": "sidebar_elegance",
        "with_photo": False,
        "content": SAMPLE_CV_SCHEMA.model_dump(),
    }
    candidate_doc = {
        "user_id": ObjectId(MOCK_USER_ID),
        "full_name": "Jean Dupont",
        "email": "jean@test.com",
    }

    colls = {
        "tailored_resumes": MagicMock(find_one=AsyncMock(return_value=resume_doc)),
        "candidate_profile": MagicMock(find_one=AsyncMock(return_value=candidate_doc)),
    }
    mock_db = create_mock_db(colls)

    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_database] = lambda: mock_db

    with patch("app.routers.resumes.render_cv_html", return_value="<html>CV</html>") as mock_render, \
         patch("app.routers.resumes.generate_cv_pdf", new_callable=AsyncMock) as mock_pdf:

        mock_pdf.return_value = b"%PDF-1.4 Fake PDF Content"

        res = client.get(f"/resumes/{resume_id}/pdf")
        assert res.status_code == 200
        assert res.headers["content-type"] == "application/pdf"
        assert res.content.startswith(b"%PDF-")
