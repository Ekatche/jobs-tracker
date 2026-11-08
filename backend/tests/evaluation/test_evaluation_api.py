"""Tests des routes API d'évaluation (/job-offers/{id}/evaluate et /evaluation)."""

from unittest.mock import AsyncMock, patch
from bson import ObjectId
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.database import get_database
from app.models import UserModel, UserTier
from main import app
from tests.evaluation.conftest import (
    TEST_OFFER_ID,
    TEST_USER_ID,
    make_eval_db,
    make_llm_response,
)


def test_evaluate_endpoint_and_get_evaluation():
    mock_user = UserModel(
        id=TEST_USER_ID,
        username="evaluator_user",
        email="evaluator@test.com",
        hashed_password="fake_hashed_pw",
        tier=UserTier.FREE,
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user

    mock_db, cols = make_eval_db()
    eval_doc_stored = {
        "_id": ObjectId(),
        "user_id": TEST_USER_ID,
        "offer_id": TEST_OFFER_ID,
        "score": 4.8,
        "headline": "AI Engineer (4.8/5.0)",
        "pipeline_stage": "evaluated",
        "bloc_a": {"archetype": "AI Engineer", "summary": "Mission IA", "geo_mismatch": False, "visa_sponsoring_refused": False, "red_flags": []},
        "bloc_b": {
            "matched_requirements": [{"requirement": "PyTorch", "weight": "critical", "candidate_evidence": "Projets LLM", "verbatim_quote": "PyTorch et LLM", "status": "full_match"}],
            "missing_requirements": [],
            "score_justification": "Profil en phase",
        },
        "bloc_g": {"is_ghost_job": False, "is_scam_risk": False, "warnings": []},
        "created_at": "2026-09-16T10:00:00Z",
        "updated_at": "2026-09-16T10:00:00Z",
    }
    cols["offer_evaluations"].find_one.return_value = eval_doc_stored
    app.dependency_overrides[get_database] = lambda: mock_db
    client = TestClient(app)

    pass1 = make_llm_response({"archetype": "AI Engineer", "summary": "Mission IA", "requirements": [{"requirement": "PyTorch", "weight": "critical", "quote_from_offer": "PyTorch et LLM"}], "is_ghost_job": False, "is_scam_risk": False, "ghost_job_warnings": []})
    pass2 = make_llm_response({"geo_mismatch": False, "matched_requirements": [{"requirement": "PyTorch", "weight": "critical", "candidate_evidence": "Projets LLM", "verbatim_quote": "PyTorch et LLM", "status": "full_match"}], "missing_requirements": [], "score_justification": "Profil en phase"})

    try:
        with patch("app.services.evaluation.evaluator.compute_domain_relevance", AsyncMock(return_value=None)), \
             patch("app.services.evaluation.evaluator.acompletion", AsyncMock(side_effect=[pass1, pass2])):
            # 1. POST evaluate
            res_post = client.post(f"/job-offers/{TEST_OFFER_ID}/evaluate")
            assert res_post.status_code == 200, res_post.text
            eval_data = res_post.json()
            assert eval_data["score"] == 4.0
            assert eval_data["bloc_a"]["archetype"] == "AI Engineer"

            # 2. GET evaluation
            res_get = client.get(f"/job-offers/{TEST_OFFER_ID}/evaluation")
            assert res_get.status_code == 200, res_get.text
            assert res_get.json()["score"] == 4.8

            # 3. GET evaluation not found -> 404
            cols["offer_evaluations"].find_one.return_value = None
            res_404 = client.get(f"/job-offers/{TEST_OFFER_ID}/evaluation")
            assert res_404.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_database, None)


def test_evaluate_invalid_ids():
    mock_user = UserModel(
        id=TEST_USER_ID,
        username="evaluator_user",
        email="evaluator@test.com",
        hashed_password="fake_hashed_pw",
        tier=UserTier.FREE,
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user
    client = TestClient(app)

    try:
        assert client.post("/job-offers/invalid-id/evaluate").status_code == 400
        assert client.get("/job-offers/invalid-id/evaluation").status_code == 400
    finally:
        app.dependency_overrides.pop(get_current_user, None)
