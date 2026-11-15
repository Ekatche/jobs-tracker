from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.database import get_database
from app.models import (
    TailoredCVSchema,
    TailoredEducationItem,
    TailoredExperienceItem,
    TailoredSkillGroup,
    UserModel,
)
from app.routers.applications import _append_letter_version
from app.services.ats_score import (
    clean_invisible_markers,
    export_cv_ats_plain_text,
    scan_invisible_markers,
    score_cv_ats_friendliness,
)
from app.services.cv_guards import _extract_metrics, verify_cv_honesty
from main import app


def _make_profile(missions: list[str], skills: list[str] | None = None) -> dict:
    return {
        "experiences": [{"company": "Acme", "title": "Tech Lead", "missions": missions}],
        "education": [{"degree": "Master", "school": "IMT"}],
        "skills": skills or ["Python", "Kubernetes"],
    }


def _make_cv(bullets: list[str], summary: str = "Profil senior backend.") -> TailoredCVSchema:
    return TailoredCVSchema(
        target_role_title="Staff Backend Engineer",
        professional_summary=summary,
        prioritized_skills=[TailoredSkillGroup(category="Core", skills=["Python", "Kubernetes"])],
        experiences=[
            TailoredExperienceItem(
                title="Tech Lead",
                company="Acme",
                start_date="2021",
                end_date="Présent",
                bullet_points=bullets,
                relevant_technologies=["Python", "Kubernetes"],
            )
        ],
        education=[TailoredEducationItem(degree="Master", institution="IMT", year="2020")],
    )


@pytest.mark.parametrize(
    ("source_mission", "bullet", "expected_valid"),
    [
        (
            "Participé à la migration Kubernetes de la plateforme paiement.",
            "Architecturé la migration Kubernetes de la plateforme paiement.",
            False,
        ),
        (
            "En coordination avec le prestataire externe sur le déploiement SSO.",
            "Piloté le déploiement SSO multi-région en autonomie.",
            False,
        ),
        (
            "Assisted an external vendor delivering the billing pipeline.",
            "Led the billing pipeline architecture end-to-end.",
            False,
        ),
        (
            "Participé à la migration Kubernetes de la plateforme paiement.",
            "Participé à la migration Kubernetes de la plateforme paiement.",
            True,
        ),
        (
            "Architecturé la migration Kubernetes de la plateforme paiement.",
            "Architecturé la migration Kubernetes de la plateforme paiement.",
            True,
        ),
    ],
)
def test_delegated_authorship_escalation_guard(source_mission: str, bullet: str, expected_valid: bool):
    cv = _make_cv([bullet])
    profile = _make_profile([source_mission])
    is_valid, violations = verify_cv_honesty(cv, profile)
    assert is_valid is expected_valid, violations


@pytest.mark.parametrize(
    ("bullet", "expected_valid"),
    [
        ("Proposera un plan pour les 90 premiers jours d'intégration de l'équipe Python.", True),
        ("Built a 30-day onboarding roadmap for the next 60 days on Kubernetes.", True),
        ("Livré 90 modules Kubernetes critiques en production.", False),
    ],
)
def test_plan_horizon_exclusion_and_real_claims(bullet: str, expected_valid: bool):
    profile = _make_profile(["Développement Python et administration Kubernetes en production."])
    is_valid, violations = verify_cv_honesty(_make_cv([bullet]), profile)
    assert is_valid is expected_valid, violations


@pytest.mark.parametrize(
    ("source_mission", "bullet", "expected_valid"),
    [
        (
            "Pendant 15 ans, exploitation et maintien de 4 plateformes critiques Python.",
            "Maintenu 4 plateformes critiques Python en haute disponibilité.",
            True,
        ),
        (
            "Exploitation de 4 plateformes critiques Python en production.",
            "Maintenu 15 plateformes critiques Python en production.",
            False,
        ),
        (
            "Formé 16 étudiants sur Python pendant 46 heures de cours pratiques.",
            "Formé 16 étudiants et animé 46 heures d'atelier Python.",
            True,
        ),
    ],
)
def test_nearest_metric_noun_and_education_nouns(source_mission: str, bullet: str, expected_valid: bool):
    cv = _make_cv([bullet])
    profile = _make_profile([source_mission])
    is_valid, violations = verify_cv_honesty(cv, profile)
    assert is_valid is expected_valid, violations


def test_extract_metrics_does_not_lazily_bind_time_duration_to_later_noun():
    extracted = _extract_metrics("Pendant 15 ans, exploitation de 4 plateformes critiques Python.")
    assert [m.mantissa for m in extracted] == [4.0]
    assert extracted[0].noun.startswith("plateforme")


def test_invisible_markers_scan_and_clean_preserves_style_script():
    raw_html = (
        "<html><style>.x::after{content:'\u200b'}</style>"
        "<script>const z='\u202e';</script>"
        "<body>Ingé\u200bnieur\u00ad \u202ePython\U000e0061 — ‘test’</body></html>"
    )
    found = scan_invisible_markers(raw_html)
    assert found == {"ZERO-WIDTH SPACE": 1, "SOFT HYPHEN": 1, "RLO": 1, "TAG U+E0061": 1}

    cleaned = clean_invisible_markers(raw_html, ascii_punctuation=True)
    assert scan_invisible_markers(cleaned) == {}
    assert ".x::after{content:'\u200b'}" in cleaned
    assert "const z='\u202e'" in cleaned
    assert "Ingénieur Python - 'test'" in cleaned


def test_score_cv_ats_and_export_plain_text():
    cv_dict = _make_cv(["Réduit la latence API de 35% sur Python et Kubernetes."]).model_dump()
    candidate = {"full_name": "Alice Martin", "email": "alice@example.com", "linkedin_url": "https://linkedin.com/in/alice"}
    html_ok = "<html><head><meta charset='utf-8'></head><body>" + ("x " * 160) + "</body></html>"

    report = score_cv_ats_friendliness(
        cv_dict, candidate, target_keywords=["Python", "Rust"], html_content=html_ok
    )
    assert report["score"] == 80
    assert report["grade"] == "B"
    assert report["breakdown"]["offer_alignment"] == 20
    assert report["keyword_coverage"] == {
        "matched": ["Python"], "missing": ["Rust"], "coverage_pct": 50.0
    }

    full_report = score_cv_ats_friendliness(
        cv_dict,
        candidate,
        target_keywords=["Python", "Kubernetes"],
        html_content=html_ok,
    )
    assert full_report["score"] == 100
    assert full_report["grade"] == "A"
    assert full_report["breakdown"]["offer_alignment"] == 40

    md = export_cv_ats_plain_text(cv_dict, candidate, fmt="markdown")
    txt = export_cv_ats_plain_text(cv_dict, candidate, fmt="txt")
    assert md.startswith("# Alice Martin — Staff Backend Engineer")
    assert "## Compétences" in md
    assert "ALICE MARTIN — STAFF BACKEND ENGINEER" in txt


def test_resume_ats_score_uses_eval_bloc_b_and_description_fallback():
    user_id = ObjectId()
    offer_id = ObjectId()
    resume_id = ObjectId()
    user = UserModel(
        id=str(user_id), username="alice", email="alice@example.com", hashed_password="pw"
    )
    cv_data = _make_cv(["Modèles PyTorch et API Python en production."]).model_dump()
    resume_doc = {
        "_id": resume_id,
        "user_id": user_id,
        "offer_id": offer_id,
        "template": "sidebar_elegance",
        "accent": "indigo",
        "content": cv_data,
    }
    offer_doc = {
        "_id": offer_id,
        "poste": "Data Scientist",
        "competences_cles": None,
        "description": "Stack : Docker et PostgreSQL pour les données cliniques.",
    }
    eval_doc = {
        "offer_id": offer_id,
        "bloc_b": {
            "matched_requirements": [{"requirement": "Maîtrise de Python et PyTorch"}],
            "missing_requirements": [{"requirement": "Orchestration Airflow"}],
        },
    }
    colls = {
        "tailored_resumes": MagicMock(
            find_one=AsyncMock(return_value=resume_doc), update_one=AsyncMock()
        ),
        "candidate_profile": MagicMock(
            find_one=AsyncMock(return_value={"personal_info": {"full_name": "Alice"}})
        ),
        "job_offers": MagicMock(find_one=AsyncMock(return_value=offer_doc)),
        "offer_evaluations": MagicMock(find_one=AsyncMock(return_value=eval_doc)),
    }
    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda name: colls[name]

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_database] = lambda: mock_db
    try:
        client = TestClient(app)
        with patch(
            "app.routers.resumes.render_cv_html",
            return_value="<html><meta charset='utf-8'><body>" + ("ok " * 60) + "</body></html>",
        ):
            resp = client.get(f"/resumes/{resume_id}/ats-score")
        assert resp.status_code == 200
        body = resp.json()
        assert "Python" in body["keyword_coverage"]["matched"]
        assert "PyTorch" in body["keyword_coverage"]["matched"]
        assert "Docker" in body["keyword_coverage"]["missing"]
        assert "Airflow" in body["keyword_coverage"]["missing"]
        assert 0 < body["breakdown"]["offer_alignment"] < 40
    finally:
        app.dependency_overrides.clear()


def test_resume_ats_score_and_export_endpoints_and_clean_markers():
    user_id = ObjectId()
    offer_id = ObjectId()
    resume_id = ObjectId()
    user = UserModel(id=str(user_id), username="alice", email="alice@example.com", hashed_password="pw")
    cv_data = _make_cv(["Optimisé 4 services Python (+30%)."]).model_dump()
    resume_doc = {
        "_id": resume_id,
        "user_id": user_id,
        "offer_id": offer_id,
        "target_company": "Acme",
        "template": "sidebar_elegance",
        "accent": "indigo",
        "content": cv_data,
    }
    colls = {
        "tailored_resumes": MagicMock(
            find_one=AsyncMock(return_value=resume_doc),
            update_one=AsyncMock(),
        ),
        "candidate_profile": MagicMock(find_one=AsyncMock(return_value={"personal_info": {"full_name": "Alice"}})),
        "job_offers": MagicMock(find_one=AsyncMock(return_value={"_id": offer_id, "competences_cles": ["Python", "Docker"]})),
        "offer_evaluations": MagicMock(find_one=AsyncMock(return_value=None)),
    }
    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda name: colls[name]

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_database] = lambda: mock_db
    try:
        client = TestClient(app)
        with patch("app.routers.resumes.render_cv_html", return_value="<html><meta charset='utf-8'><body>" + ("Python " * 60) + "</body></html>"):
            score_resp = client.get(f"/resumes/{resume_id}/ats-score")
        assert score_resp.status_code == 200
        body = score_resp.json()
        assert body["resume_id"] == str(resume_id)
        assert body["breakdown"]["offer_alignment"] == 20
        assert body["keyword_coverage"]["matched"] == ["Python"]
        assert body["keyword_coverage"]["missing"] == ["Docker"]

        export_resp = client.get(f"/resumes/{resume_id}/export-text?format=txt")
        assert export_resp.status_code == 200
        assert export_resp.json()["format"] == "txt"
        assert "Python" in export_resp.json()["content"]

        dirty_cv = _make_cv(["Built\u200b scalable Python\u202e API."]).model_dump()
        put_resp = client.put(f"/resumes/{resume_id}", json={"content": dirty_cv})
        assert put_resp.status_code == 200
        saved_content = colls["tailored_resumes"].update_one.call_args.args[1]["$set"]["content"]
        assert saved_content["experiences"][0]["bullet_points"][0] == "Built scalable Python API."
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_append_letter_version_strips_invisible_markers():
    cover_letters = MagicMock(
        find_one=AsyncMock(return_value={"_id": ObjectId(), "versions": []}),
        update_one=AsyncMock(),
    )
    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda name: cover_letters
    version = {"body": "Bonjour\u200b équipe\u00ad Acme\u202e."}
    await _append_letter_version(mock_db, ObjectId(), version)
    pushed = cover_letters.update_one.call_args.args[1]["$push"]["versions"]
    assert pushed["body"] == "Bonjour équipe Acme."
