from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.database import get_database
from app.models import UserModel
from app.services.analytics.calibration import compute_jd_skill_gaps, compute_score_calibration
from main import app


def _app_doc(offer_id: str, status: str, history: list | None = None, interview_date: str | None = None) -> dict:
    return {
        "_id": ObjectId(),
        "offer_id": offer_id,
        "status": status,
        "status_history": history or [],
        "interview_date": interview_date,
    }


def _eval_doc(
    offer_id: str,
    score: float,
    archetype: str = "backend_platform",
    missing: list[dict] | None = None,
    matches: list[dict] | None = None,
) -> dict:
    return {
        "offer_id": offer_id,
        "overall_score_1_to_5": score,
        "bloc_a": {"archetype": archetype},
        "bloc_b": {"missing_requirements": missing or [], "matches": matches or []},
    }


def test_calibration_excludes_in_flight_and_detects_history_or_interview_date():
    evals = [
        _eval_doc("o1", 4.6, "backend"),
        _eval_doc("o2", 4.7, "backend"),
        _eval_doc("o3", 4.8, "backend"),
        _eval_doc("o4", 4.9, "backend"),
        _eval_doc("o5", 4.5, "backend"),
    ]
    apps = [
        _app_doc("o1", "Offer"),
        _app_doc("o2", "Rejected", history=[{"status": "Interview"}]),
        _app_doc("o3", "Rejected", interview_date="2026-10-12"),
        _app_doc("o4", "Applied"),
        _app_doc("o5", "To Apply"),
    ]
    report = compute_score_calibration(apps, evals, min_band_n=3)
    band = report["bands"][">=4.5"]
    assert report["total_in_flight"] == 2
    assert report["total_resolved"] == 3
    assert band["total_count"] == 5
    assert band["in_flight_count"] == 2
    assert band["resolved_count"] == 3
    assert band["interview_count"] == 3
    assert band["offer_count"] == 1
    assert band["sample_floor_met"] is True
    assert band["interview_rate"] == 100.0
    assert band["offer_rate"] == 33.3


def test_calibration_sample_floor_and_monotonicity_warning():
    apps = [
        _app_doc("l1", "Interview"),
        _app_doc("l2", "Interview"),
        _app_doc("l3", "Rejected"),
        _app_doc("h1", "Rejected"),
        _app_doc("h2", "Rejected"),
        _app_doc("h3", "Rejected"),
        _app_doc("m1", "Rejected"),
    ]
    evals = [
        _eval_doc("l1", 3.2),
        _eval_doc("l2", 3.3),
        _eval_doc("l3", 3.1),
        _eval_doc("h1", 4.7),
        _eval_doc("h2", 4.8),
        _eval_doc("h3", 4.6),
        _eval_doc("m1", 3.7),
    ]
    report = compute_score_calibration(apps, evals, min_band_n=3)
    assert report["bands"]["3.5-3.9"]["sample_floor_met"] is False
    assert report["bands"]["3.5-3.9"]["interview_rate"] is None
    assert report["bands"]["<3.5"]["interview_rate"] == 66.7
    assert report["bands"][">=4.5"]["interview_rate"] == 0.0
    assert any("Calibration inversée" in w for w in report["warnings"])


def test_jd_skill_gaps_aggregation_classification_and_min_score():
    evals = [
        _eval_doc(
            "e1",
            4.2,
            archetype="backend",
            missing=[
                {"requirement": "Rust", "importance": "critical", "workaround": "À monter en compétence"},
                {"requirement": "Terraform", "importance": "high", "workaround": "Déjà couvert sur projet infra"},
            ],
            matches=[{"requirement": "Kafka", "strength": "strong"}],
        ),
        _eval_doc(
            "e2",
            4.4,
            archetype="platform",
            missing=[
                {"requirement": "Rust", "importance": "high", "workaround": "Formation interne"},
                {"requirement": "Kafka", "importance": "medium", "workaround": "Préciser la version"},
            ],
        ),
        _eval_doc(
            "e3",
            2.5,
            archetype="frontend",
            missing=[{"requirement": "Angular", "importance": "critical"}],
        ),
    ]
    report = compute_jd_skill_gaps(evals, min_score=4.0)
    assert report["total_evaluations_analyzed"] == 2
    items = report["items"]
    assert [i["skill"] for i in items] == ["Rust", "Terraform", "Kafka"]
    assert items[0]["count"] == 2 and items[0]["critical_or_high_count"] == 2
    assert items[0]["classification"] == "gap"
    assert items[0]["archetypes"] == ["backend", "platform"]
    assert items[1]["classification"] == "supported_by_resume"
    assert items[2]["classification"] == "supported_by_resume"


def test_calibration_and_skill_gaps_fastapi_endpoints():
    user_id = ObjectId()
    user = UserModel(id=str(user_id), username="alice", email="alice@example.com", hashed_password="pw")
    apps = [_app_doc("o1", "Offer")]
    evals = [_eval_doc("o1", 4.6, missing=[{"requirement": "Rust", "importance": "critical"}])]

    def _find_coll(docs):
        cursor = MagicMock(to_list=AsyncMock(return_value=docs))
        return MagicMock(find=MagicMock(return_value=cursor))

    colls = {"applications": _find_coll(apps), "offer_evaluations": _find_coll(evals)}
    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda k: colls[k]

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_database] = lambda: mock_db
    try:
        client = TestClient(app)
        cal_resp = client.get("/applications/pipeline/calibrate?min_band_n=1")
        assert cal_resp.status_code == 200
        cal_data = cal_resp.json()
        assert cal_data["bands"][">=4.5"]["offer_rate"] == 100.0

        gap_resp = client.get("/job-offers/analytics/skill-gaps?min_score=4.0")
        assert gap_resp.status_code == 200
        gap_data = gap_resp.json()
        assert gap_data["total_evaluations_analyzed"] == 1
        assert gap_data["items"][0]["skill"] == "Rust"
    finally:
        app.dependency_overrides.clear()
