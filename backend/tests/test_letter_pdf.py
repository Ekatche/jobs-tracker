import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
from fastapi.testclient import TestClient

from main import app
from app.auth import get_current_user
from app.database import get_database
from app.models import UserModel
from app.services.letter_pdf import (
    build_candidate_info,
    format_french_date,
    render_letter_html,
    slugify,
)


@pytest.fixture(autouse=True)
def _clean_dependency_overrides():
    """Ensure dependency overrides do not leak between test files."""
    snapshot = dict(app.dependency_overrides)
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(snapshot)


MOCK_USER_ID = "60c72b2f9b1d8b2bad7f9999"
mock_current_user = UserModel(
    id=MOCK_USER_ID,
    username="testengineer",
    full_name="Jean Dupont",
    email="jean.dupont@example.com",
    hashed_password="pw",
)


def test_format_french_date():
    d1 = date(2026, 10, 1)
    assert format_french_date(d1) == "1er octobre 2026"
    d2 = date(2026, 10, 22)
    assert format_french_date(d2) == "22 octobre 2026"
    d3 = date(2025, 1, 15)
    assert format_french_date(d3) == "15 janvier 2025"


def test_slugify():
    assert slugify("Jean Dupont") == "jean_dupont"
    assert slugify("L'Oréal & Co.") == "loréal_co"
    assert slugify("") == "document"


def test_build_candidate_info():
    prof = {
        "personal_info": {
            "full_name": "Jean Dupont",
            "phone": "0601020304",
            "location": "Paris, France",
        }
    }
    candidate = build_candidate_info(prof, mock_current_user)
    assert candidate["full_name"] == "Jean Dupont"
    assert candidate["phone"] == "0601020304"
    assert candidate["email"] == "jean.dupont@example.com"
    assert candidate["location"] == "Paris, France"


def test_render_letter_html_header():
    candidate = {
        "full_name": "Alice Martin",
        "location": "Lyon, France",
        "phone": "+33 6 12 34 56 78",
        "email": "alice.martin@example.com",
    }
    html = render_letter_html(
        body="Premier paragraphe.\n\nDeuxième paragraphe.",
        candidate=candidate,
        company="Tech Innovate",
        position="Senior Software Engineer",
        location="Paris",
        today=date(2026, 10, 22),
    )

    # Expéditeur
    assert "Alice Martin" in html
    assert "Lyon, France" in html
    assert "+33 6 12 34 56 78" in html
    assert "alice.martin@example.com" in html

    # Destinataire & Date & Objet
    assert "Tech Innovate" in html
    assert "Paris" in html
    assert "22 octobre 2026" in html
    assert "Objet :" in html
    assert "Candidature au poste de Senior Software Engineer" in html

    # Paragraphes
    assert "<p class=\"letter-paragraph\">Premier paragraphe.</p>" in html
    assert "<p class=\"letter-paragraph\">Deuxième paragraphe.</p>" in html

    # Style v2 : typographie sans-serif moderne et absence d'encadré gris
    assert "sans-serif" in html
    assert "recipient-box" not in html
    assert "recipient-company" in html


def test_render_letter_html_escapes_body():
    candidate = {"full_name": "Bob <script>alert(1)</script>"}
    html = render_letter_html(
        body="<img src=x onerror=alert(1)> & malicious",
        candidate=candidate,
        company="Dangerous <>& Co",
        position="Hacker <alert>",
    )
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<img" not in html
    assert "&lt;img src=x onerror=alert(1)&gt; &amp; malicious" in html
    assert "&lt;&gt;" in html or "&amp;" in html


def test_letter_pdf_forbidden(client):
    app_id = ObjectId()
    other_user_id = ObjectId()

    apps_coll = MagicMock()
    apps_coll.find_one = AsyncMock(return_value={"_id": app_id, "user_id": other_user_id})

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda k: {"applications": apps_coll}[k]

    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_database] = lambda: mock_db

    res = client.get(f"/applications/{app_id}/cover-letter/pdf")
    assert res.status_code == 403
    assert "Accès non autorisé" in res.json()["detail"]


def test_letter_pdf_not_ready(client):
    app_id = ObjectId()

    apps_coll = MagicMock()
    apps_coll.find_one = AsyncMock(return_value={
        "_id": app_id,
        "user_id": ObjectId(MOCK_USER_ID),
        "company": "Acme",
        "position": "Dev",
    })

    letters_coll = MagicMock()
    letters_coll.find_one = AsyncMock(return_value={
        "_id": ObjectId(),
        "application_id": app_id,
        "status": "pending",
        "versions": [],
    })

    colls = {"applications": apps_coll, "cover_letters": letters_coll}
    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda k: colls[k]

    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_database] = lambda: mock_db

    res = client.get(f"/applications/{app_id}/cover-letter/pdf")
    assert res.status_code == 404
    assert "non disponible ou non prête" in res.json()["detail"]


def test_letter_pdf_ok(client):
    app_id = ObjectId()

    apps_coll = MagicMock()
    apps_coll.find_one = AsyncMock(return_value={
        "_id": app_id,
        "user_id": ObjectId(MOCK_USER_ID),
        "company": "Tech Corp",
        "position": "Data Scientist",
        "location": "Nantes",
    })

    letters_coll = MagicMock()
    letters_coll.find_one = AsyncMock(return_value={
        "_id": ObjectId(),
        "application_id": app_id,
        "status": "ready",
        "current_version": 1,
        "versions": [{"n": 1, "body": "Madame, Monsieur,\n\nJe vous soumets ma candidature."}],
    })

    profiles_coll = MagicMock()
    profiles_coll.find_one = AsyncMock(return_value={
        "user_id": ObjectId(MOCK_USER_ID),
        "personal_info": {
            "full_name": "Jean Dupont",
            "email": "jean.dupont@example.com",
            "phone": "0601020304",
            "location": "Paris",
        }
    })

    colls = {
        "applications": apps_coll,
        "cover_letters": letters_coll,
        "candidate_profile": profiles_coll,
    }
    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda k: colls[k]

    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_database] = lambda: mock_db

    with patch("app.routers.cover_letters.generate_cv_pdf", new_callable=AsyncMock) as mock_pdf:
        mock_pdf.return_value = b"%PDF-1.4 mock pdf data"
        res = client.get(f"/applications/{app_id}/cover-letter/pdf")

    assert res.status_code == 200
    assert res.headers["Content-Type"] == "application/pdf"
    assert "attachment;" in res.headers["Content-Disposition"]
    assert "Lettre_jean_dupont_data_scientist_tech_corp.pdf" in res.headers["Content-Disposition"]
    assert res.content == b"%PDF-1.4 mock pdf data"
    assert mock_pdf.called


def test_letter_pdf_without_position(client):
    app_id = ObjectId()

    apps_coll = MagicMock()
    apps_coll.find_one = AsyncMock(return_value={
        "_id": app_id,
        "user_id": ObjectId(MOCK_USER_ID),
        "company": "Tech Corp",
        "position": "",
    })

    letters_coll = MagicMock()
    letters_coll.find_one = AsyncMock(return_value={
        "_id": ObjectId(),
        "application_id": app_id,
        "status": "ready",
        "current_version": 1,
        "versions": [{"n": 1, "body": "Contenu de la lettre"}],
    })

    profiles_coll = MagicMock()
    profiles_coll.find_one = AsyncMock(return_value={
        "user_id": ObjectId(MOCK_USER_ID),
        "personal_info": {"full_name": "Jean Dupont"},
    })

    colls = {
        "applications": apps_coll,
        "cover_letters": letters_coll,
        "candidate_profile": profiles_coll,
    }
    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda k: colls[k]

    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_database] = lambda: mock_db

    with patch("app.routers.cover_letters.generate_cv_pdf", new_callable=AsyncMock) as mock_pdf:
        mock_pdf.return_value = b"%PDF-1.4 mock pdf data"
        res = client.get(f"/applications/{app_id}/cover-letter/pdf")

    assert res.status_code == 200
    assert "Lettre_jean_dupont_tech_corp.pdf" in res.headers["Content-Disposition"]

