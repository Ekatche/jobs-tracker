import json
import os
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from bson import ObjectId
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.database import get_database
from app.models import (
    ApiUsageAction,
    BlocA,
    BlocB,
    BlocG,
    MissingRequirement,
    OfferEvaluation,
    RequirementMatch,
    UserModel,
    UserTier,
)
from app.services.evaluation.evaluator import (
    _clean_json_output,
    calculate_evaluation_score,
    evaluate_offer_two_pass,
)
from main import app

TEST_USER_ID = "507f1f77bcf86cd799439011"
TEST_OFFER_ID = "507f1f77bcf86cd799439022"


# --- Unit Tests: Score Calculation & JSON Parsing ---

def test_clean_json_output_fences():
    raw = "```json\n{\"archetype\": \"Lead Dev\", \"requirements\": []}\n```"
    cleaned = _clean_json_output(raw)
    assert cleaned["archetype"] == "Lead Dev"


def test_clean_json_output_raw_text_wrapper():
    raw = "Here is the result:\n{\"summary\": \"Cool job\", \"is_ghost_job\": false}\nHope it helps!"
    cleaned = _clean_json_output(raw)
    assert cleaned["summary"] == "Cool job"
    assert cleaned["is_ghost_job"] is False


def test_calculate_evaluation_score_perfect():
    bloc_a = BlocA(archetype="Staff Engineer", geo_mismatch=False, visa_sponsoring_refused=False)
    bloc_b = BlocB(
        matched_requirements=[
            RequirementMatch(
                requirement="Python",
                weight="critical",
                candidate_evidence="10 years Python",
                verbatim_quote="10+ years Python required",
                status="full_match",
            ),
            RequirementMatch(
                requirement="FastAPI",
                weight="critical",
                candidate_evidence="Built 20 microservices",
                verbatim_quote="Strong FastAPI experience",
                status="full_match",
            ),
            RequirementMatch(
                requirement="MongoDB",
                weight="critical",
                candidate_evidence="Production MongoDB DBA",
                verbatim_quote="MongoDB skills",
                status="full_match",
            ),
        ],
        missing_requirements=[],
    )
    bloc_g = BlocG(is_ghost_job=False, is_scam_risk=False)

    score = calculate_evaluation_score(bloc_a, bloc_b, bloc_g)
    assert score == 5.0


def test_calculate_evaluation_score_red_flag_caps():
    bloc_a_geo = BlocA(archetype="Staff Engineer", geo_mismatch=True)
    bloc_b = BlocB(matched_requirements=[], missing_requirements=[])
    bloc_g = BlocG(is_ghost_job=False, is_scam_risk=False)
    assert calculate_evaluation_score(bloc_a_geo, bloc_b, bloc_g) == 1.5

    bloc_a_clean = BlocA(archetype="Staff Engineer", geo_mismatch=False)
    bloc_g_ghost = BlocG(is_ghost_job=True, is_scam_risk=False)
    assert calculate_evaluation_score(bloc_a_clean, bloc_b, bloc_g_ghost) == 1.5


def test_calculate_evaluation_score_domain_mismatch_caps():
    bloc_a = BlocA(archetype="Data Scientist", domain_mismatch=True)
    bloc_b = BlocB(matched_requirements=[], missing_requirements=[])
    bloc_g = BlocG(is_ghost_job=False, is_scam_risk=False)
    assert calculate_evaluation_score(bloc_a, bloc_b, bloc_g) == 1.5


def test_calculate_evaluation_score_deductions():
    bloc_a = BlocA(archetype="Backend Developer")
    bloc_b = BlocB(
        matched_requirements=[],
        missing_requirements=[
            MissingRequirement(requirement="Kubernetes", weight="critical", reason="No K8s on profile"),
            MissingRequirement(requirement="Go", weight="high", reason="Only Python"),
            MissingRequirement(requirement="GCP", weight="meaningful", reason="Only AWS"),
        ],
    )
    bloc_g = BlocG()

    # 5.0 - 1.0 (critical) - 0.5 (high) - 0.2 (meaningful) = 3.3
    score = calculate_evaluation_score(bloc_a, bloc_b, bloc_g)
    assert score == 3.3


def test_calculate_evaluation_score_min_bound():
    bloc_a = BlocA()
    bloc_b = BlocB(
        missing_requirements=[
            MissingRequirement(requirement=f"Req {i}", weight="critical", reason="Missing")
            for i in range(10)
        ]
    )
    bloc_g = BlocG()
    # 5.0 - 10.0 = -5.0 -> clamped to 1.0
    score = calculate_evaluation_score(bloc_a, bloc_b, bloc_g)
    assert score == 1.0


# --- Service Test: evaluate_offer_two_pass with Mocks ---

@pytest.mark.asyncio
async def test_evaluate_offer_two_pass_success():
    db = MagicMock()

    # Mock collections
    job_offers_collection = AsyncMock()
    candidate_profile_collection = AsyncMock()
    offer_evaluations_collection = AsyncMock()

    # Offer doc
    job_offers_collection.find_one.return_value = {
        "_id": ObjectId(TEST_OFFER_ID),
        "poste": "Senior Fullstack Engineer",
        "entreprise": "Acme Corp",
        "localisation": "Paris, France",
        "type_contrat": "CDI",
        "mode_travail": "Hybrid",
        "description": "Nous recherchons un Senior Fullstack Engineer maîtrisant React, FastAPI et MongoDB.",
    }
    job_offers_collection.update_one.return_value = MagicMock(modified_count=1)

    # Profile doc
    candidate_profile_collection.find_one.return_value = {
        "user_id": TEST_USER_ID,
        "headline": "Fullstack Developer 6 YoE",
        "summary": "Passionné par FastAPI et React",
        "skills": {"languages": ["Python", "TypeScript"], "frameworks": ["FastAPI", "React"]},
        "experiences": [
            {
                "role": "Fullstack Dev",
                "company": "Tech Corp",
                "stack": ["Python", "FastAPI", "React"],
                "missions": ["Conception d'APIs", "Refonte UI"],
            }
        ],
        "preferences": {"remote": "hybrid", "locations": ["Paris"]},
    }

    offer_evaluations_collection.update_one.return_value = MagicMock(upserted_id="eval_123")

    # Mock aggregation for quota check
    async def mock_async_cursor(*args, **kwargs):
        if False:
            yield {}

    def get_cursor(*args, **kwargs):
        return mock_async_cursor(*args, **kwargs)

    def db_getitem(name):
        if name == "job_offers":
            return job_offers_collection
        elif name == "candidate_profile":
            return candidate_profile_collection
        elif name == "offer_evaluations":
            return offer_evaluations_collection
        elif name == "users":
            users_col = AsyncMock()
            users_col.find_one.return_value = {"_id": ObjectId(TEST_USER_ID), "tier": "free"}
            return users_col
        elif name == "api_usage":
            api_col = AsyncMock()
            api_col.aggregate = MagicMock(side_effect=get_cursor)
            api_col.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
            return api_col
        return AsyncMock()

    db.__getitem__.side_effect = db_getitem

    # Mock LiteLLM responses for Pass 1 and Pass 2
    pass1_response = MagicMock()
    pass1_response.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps(
                    {
                        "archetype": "Senior Fullstack Engineer",
                        "summary": "Mission d'architecture fullstack moderne chez Acme Corp.",
                        "requirements": [
                            {
                                "requirement": "FastAPI",
                                "weight": "critical",
                                "quote_from_offer": "maîtrisant React, FastAPI et MongoDB",
                            }
                        ],
                        "is_ghost_job": False,
                        "is_scam_risk": False,
                        "ghost_job_warnings": [],
                    }
                )
            )
        )
    ]
    pass1_response.usage = MagicMock(prompt_tokens=300, completion_tokens=150)

    pass2_response = MagicMock()
    pass2_response.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps(
                    {
                        "geo_mismatch": False,
                        "visa_sponsoring_refused": False,
                        "red_flags": [],
                        "matched_requirements": [
                            {
                                "requirement": "FastAPI",
                                "weight": "critical",
                                "candidate_evidence": "Expérience confirmée chez Tech Corp",
                                "verbatim_quote": "maîtrisant React, FastAPI et MongoDB",
                                "status": "full_match",
                            }
                        ],
                        "missing_requirements": [],
                        "score_justification": "Excellente adéquation technique et géographique.",
                    }
                )
            )
        )
    ]
    pass2_response.usage = MagicMock(prompt_tokens=400, completion_tokens=180)

    with patch("app.services.evaluation.evaluator.acompletion", AsyncMock(side_effect=[pass1_response, pass2_response])):
        evaluation = await evaluate_offer_two_pass(
            db=db,
            user_id=TEST_USER_ID,
            offer_id=TEST_OFFER_ID,
        )

        assert isinstance(evaluation, OfferEvaluation)
        assert evaluation.user_id == TEST_USER_ID
        assert evaluation.offer_id == TEST_OFFER_ID
        assert evaluation.score >= 4.5
        assert evaluation.bloc_a.archetype == "Senior Fullstack Engineer"
        assert len(evaluation.bloc_b.matched_requirements) == 1
        assert evaluation.bloc_b.matched_requirements[0].verbatim_quote == "maîtrisant React, FastAPI et MongoDB"
        assert evaluation.bloc_g.is_ghost_job is False

        # Check DB updates
        job_offers_collection.update_one.assert_called_once()
        offer_evaluations_collection.update_one.assert_called_once()


# --- Endpoint Tests: POST /job-offers/{id}/evaluate & GET /job-offers/{id}/evaluation ---

def test_evaluate_endpoint_and_get_evaluation():
    mock_user = UserModel(
        id=TEST_USER_ID,
        username="evaluator_user",
        email="evaluator@test.com",
        hashed_password="fake_hashed_pw",
        tier=UserTier.FREE,
    )

    app.dependency_overrides[get_current_user] = lambda: mock_user

    mock_db = MagicMock()
    job_offers_col = AsyncMock()
    candidate_profile_col = AsyncMock()
    offer_evaluations_col = AsyncMock()
    users_col = AsyncMock()
    api_usage_col = AsyncMock()

    users_col.find_one.return_value = {"_id": ObjectId(TEST_USER_ID), "tier": "free"}
    async def mock_endpoint_cursor(*args, **kwargs):
        if False:
            yield {}

    def get_endpoint_cursor(*args, **kwargs):
        return mock_endpoint_cursor(*args, **kwargs)

    api_usage_col.aggregate = MagicMock(side_effect=get_endpoint_cursor)
    api_usage_col.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))

    job_offers_col.find_one.return_value = {
        "_id": ObjectId(TEST_OFFER_ID),
        "poste": "AI Engineer",
        "entreprise": "DeepTech",
        "description": "Poste IA avec PyTorch et LLM",
        "localisation": "Lyon",
    }
    job_offers_col.update_one.return_value = MagicMock(modified_count=1)

    candidate_profile_col.find_one.return_value = {
        "user_id": TEST_USER_ID,
        "headline": "AI Engineer",
        "summary": "Spécialiste LLM",
        "skills": {"languages": ["Python"]},
        "experiences": [],
        "preferences": {},
    }

    eval_doc_stored = {
        "_id": ObjectId(),
        "user_id": TEST_USER_ID,
        "offer_id": TEST_OFFER_ID,
        "score": 4.8,
        "headline": "AI Engineer (4.8/5.0)",
        "pipeline_stage": "evaluated",
        "bloc_a": {
            "archetype": "AI Engineer",
            "summary": "Mission IA",
            "geo_mismatch": False,
            "visa_sponsoring_refused": False,
            "red_flags": [],
        },
        "bloc_b": {
            "matched_requirements": [
                {
                    "requirement": "PyTorch",
                    "weight": "critical",
                    "candidate_evidence": "Projets LLM",
                    "verbatim_quote": "PyTorch et LLM",
                    "status": "full_match",
                }
            ],
            "missing_requirements": [],
            "score_justification": "Profil en phase",
        },
        "bloc_g": {
            "is_ghost_job": False,
            "is_scam_risk": False,
            "warnings": [],
        },
        "created_at": "2026-09-16T10:00:00Z",
        "updated_at": "2026-09-16T10:00:00Z",
    }

    offer_evaluations_col.update_one.return_value = MagicMock(upserted_id="eval_456")
    offer_evaluations_col.find_one.return_value = eval_doc_stored

    def db_lookup(name):
        if name == "job_offers":
            return job_offers_col
        elif name == "candidate_profile":
            return candidate_profile_col
        elif name == "offer_evaluations":
            return offer_evaluations_col
        elif name == "users":
            return users_col
        elif name == "api_usage":
            return api_usage_col
        return AsyncMock()

    mock_db.__getitem__.side_effect = db_lookup
    app.dependency_overrides[get_database] = lambda: mock_db

    client = TestClient(app)

    pass1_response = MagicMock()
    pass1_response.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps(
                    {
                        "archetype": "AI Engineer",
                        "summary": "Mission IA",
                        "requirements": [{"requirement": "PyTorch", "weight": "critical", "quote_from_offer": "PyTorch et LLM"}],
                        "is_ghost_job": False,
                        "is_scam_risk": False,
                        "ghost_job_warnings": [],
                    }
                )
            )
        )
    ]
    pass1_response.usage = MagicMock(prompt_tokens=200, completion_tokens=100)

    pass2_response = MagicMock()
    pass2_response.choices = [
        MagicMock(
            message=MagicMock(
                content=json.dumps(
                    {
                        "geo_mismatch": False,
                        "visa_sponsoring_refused": False,
                        "red_flags": [],
                        "matched_requirements": [
                            {
                                "requirement": "PyTorch",
                                "weight": "critical",
                                "candidate_evidence": "Projets LLM",
                                "verbatim_quote": "PyTorch et LLM",
                                "status": "full_match",
                            }
                        ],
                        "missing_requirements": [],
                        "score_justification": "Profil en phase",
                    }
                )
            )
        )
    ]
    pass2_response.usage = MagicMock(prompt_tokens=250, completion_tokens=120)

    try:
        with patch("app.services.evaluation.evaluator.acompletion", AsyncMock(side_effect=[pass1_response, pass2_response])):
            # 1. Trigger POST evaluate
            res_post = client.post(f"/job-offers/{TEST_OFFER_ID}/evaluate")
            assert res_post.status_code == 200, res_post.text
            eval_data = res_post.json()
            assert eval_data["score"] >= 4.5
            assert eval_data["bloc_a"]["archetype"] == "AI Engineer"
            assert eval_data["pipeline_stage"] == "evaluated"

            # 2. Trigger GET evaluation
            res_get = client.get(f"/job-offers/{TEST_OFFER_ID}/evaluation")
            assert res_get.status_code == 200, res_get.text
            eval_fetched = res_get.json()
            assert eval_fetched["score"] == 4.8
            assert eval_fetched["user_id"] == TEST_USER_ID

            # 3. Trigger GET evaluation for non-existing evaluation
            offer_evaluations_col.find_one.return_value = None
            res_404 = client.get(f"/job-offers/{TEST_OFFER_ID}/evaluation")
            assert res_404.status_code == 404

    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_database, None)


@pytest.mark.asyncio
async def test_evaluate_offer_quota_exceeded():
    db = MagicMock()
    users_col = AsyncMock()
    users_col.find_one.return_value = {"_id": ObjectId(TEST_USER_ID), "tier": "free"}

    # Free tier limit for evaluation is 20
    async def cursor_quota_reached(*args, **kwargs):
        yield {"_id": "evaluation", "count": 20, "total_tokens": 50000, "total_cost": 0.20}

    api_usage_col = AsyncMock()
    api_usage_col.aggregate = MagicMock(side_effect=cursor_quota_reached)

    def db_getitem(name):
        if name == "users":
            return users_col
        elif name == "api_usage":
            return api_usage_col
        return AsyncMock()

    db.__getitem__.side_effect = db_getitem

    with patch.dict(os.environ, {"DISABLE_QUOTA_BLOCKING": "false"}):
        with pytest.raises(HTTPException) as exc_info:
            await evaluate_offer_two_pass(
                db=db,
                user_id=TEST_USER_ID,
                offer_id=TEST_OFFER_ID,
            )
    assert exc_info.value.status_code == 429
    assert "Monthly quota limit reached" in exc_info.value.detail


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
        # Invalid ObjectId
        res = client.post("/job-offers/invalid-id/evaluate")
        assert res.status_code == 400

        res_get = client.get("/job-offers/invalid-id/evaluation")
        assert res_get.status_code == 400
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_evaluate_offer_candidate_profile_lookup_supports_objectid_and_str():
    db = MagicMock()
    job_offers_col = AsyncMock()
    job_offers_col.find_one.return_value = {
        "_id": ObjectId(TEST_OFFER_ID),
        "poste": "AI Engineer",
        "entreprise": "Tech AI",
        "description": "Nous cherchons un ingénieur IA Python FastAPI",
        "localisation": "Lyon",
        "type_contrat": "CDI",
        "mode_travail": "remote",
    }
    candidate_profile_col = AsyncMock()

    async def mock_find_profile(query):
        or_list = query.get("$or", [])
        for cond in or_list:
            if cond.get("user_id") == ObjectId(TEST_USER_ID) or cond.get("user_id") == TEST_USER_ID:
                return {
                    "headline": "Lead AI Engineer",
                    "experiences": [{"role": "AI Dev", "company": "Co", "stack": ["Python"]}],
                    "skills": {"languages": ["Python"]},
                    "preferences": {"locations": ["Lyon"]},
                }
        return None

    candidate_profile_col.find_one = AsyncMock(side_effect=mock_find_profile)
    offer_eval_col = AsyncMock()
    offer_eval_col.update_one.return_value = MagicMock(upserted_id="eval_123")

    users_col = AsyncMock()
    users_col.find_one.return_value = {"_id": ObjectId(TEST_USER_ID), "tier": "free"}

    async def cursor_quota(*args, **kwargs):
        if False:
            yield {}

    api_usage_col = AsyncMock()
    api_usage_col.aggregate = MagicMock(side_effect=lambda *a, **k: cursor_quota(*a, **k))
    api_usage_col.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))

    def db_getitem(name):
        if name == "job_offers":
            return job_offers_col
        elif name == "candidate_profile":
            return candidate_profile_col
        elif name == "offer_evaluations":
            return offer_eval_col
        elif name == "users":
            return users_col
        elif name == "api_usage":
            return api_usage_col
        return AsyncMock()

    db.__getitem__.side_effect = db_getitem

    mock_p1 = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content='{"archetype": "AI Engineer", "summary": "Job", "requirements": [], "is_ghost_job": false, "is_scam_risk": false, "ghost_job_warnings": []}'
                )
            )
        ],
        usage=None,
    )
    mock_p2 = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content='{"geo_mismatch": false, "visa_sponsoring_refused": false, "red_flags": [], "matched_requirements": [], "missing_requirements": [], "score_justification": "Good"}'
                )
            )
        ],
        usage=None,
    )

    with patch("app.services.evaluation.evaluator.acompletion", side_effect=[mock_p1, mock_p2]) as mock_acompletion:
        res = await evaluate_offer_two_pass(
            db=db,
            user_id=TEST_USER_ID,
            offer_id=TEST_OFFER_ID,
        )
        assert res.score == 5.0
        candidate_profile_col.find_one.assert_called_once()
        call_query = candidate_profile_col.find_one.call_args[0][0]
        assert "$or" in call_query
        assert {"user_id": TEST_USER_ID} in call_query["$or"]
        assert {"user_id": ObjectId(TEST_USER_ID)} in call_query["$or"]
        pass2_prompt = mock_acompletion.call_args_list[1].kwargs["messages"][0]["content"]
        assert "Lead AI Engineer" in pass2_prompt
        assert "AI Dev" in pass2_prompt


@pytest.mark.asyncio
async def test_evaluate_offer_pass2_receives_education_and_projects():
    """Vérifie que la Pass 2 de matching transmet bien l'éducation, les projets et certifications au LLM."""
    db = MagicMock()
    job_offers_col = AsyncMock()
    job_offers_col.find_one.return_value = {
        "_id": ObjectId(TEST_OFFER_ID),
        "poste": "Lead Data Scientist",
        "entreprise": "BigCorp",
        "description": "Nous cherchons un profil Bac+5 en Data/IA.",
        "localisation": "Lyon",
        "type_contrat": "CDI",
        "mode_travail": "hybride",
    }
    candidate_profile_col = AsyncMock()
    candidate_profile_col.find_one.return_value = {
        "_id": ObjectId(),
        "user_id": TEST_USER_ID,
        "headline": "AI Engineer",
        "summary": "Expert IA",
        "education": [
            {
                "school": "CNAM Lyon",
                "degree": "Spécialisation en Intelligence Artificielle",
                "years": "2024 - 2025",
                "topics": ["Optimisation", "IA Avancée"],
            }
        ],
        "projects": [
            {
                "name": "WideDocs",
                "description": "OCR et IA pour juristes",
                "stack": ["Python", "FastAPI", "Mistral"],
                "repo": "https://github.com/Ekatche/widedocs",
            }
        ],
        "certifications": [
            {"name": "Azure AI Engineer", "issuer": "Microsoft", "year": "2023"}
        ],
        "languages": ["English (Fluent)", "Français (Natif)"],
        "experiences": [],
        "skills": {"data": ["Python", "PyTorch"]},
        "preferences": {},
    }
    offer_evaluations_col = AsyncMock()
    offer_evaluations_col.update_one.return_value = MagicMock(upserted_id="eval_999")
    users_col = AsyncMock()
    users_col.find_one.return_value = {"_id": ObjectId(TEST_USER_ID), "tier": "free"}
    api_usage_col = AsyncMock()

    async def mock_cursor(*args, **kwargs):
        if False:
            yield {}

    api_usage_col.aggregate = MagicMock(side_effect=lambda *args, **kwargs: mock_cursor())
    api_usage_col.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))

    def db_getitem(name):
        mapping = {
            "job_offers": job_offers_col,
            "candidate_profile": candidate_profile_col,
            "offer_evaluations": offer_evaluations_col,
            "users": users_col,
            "api_usage": api_usage_col,
        }
        return mapping.get(name, AsyncMock())

    db.__getitem__.side_effect = db_getitem

    mock_p1 = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content='{"archetype": "Data Scientist", "summary": "Poste", "requirements": [{"requirement": "Bac+5 Data", "weight": "critical", "quote_from_offer": "Bac+5 en Data/IA"}], "is_ghost_job": false, "is_scam_risk": false, "ghost_job_warnings": []}'
                )
            )
        ],
        usage=None,
    )
    mock_p2 = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content='{"geo_mismatch": false, "visa_sponsoring_refused": false, "red_flags": [], "matched_requirements": [{"requirement": "Bac+5 Data", "weight": "critical", "candidate_evidence": "Spécialisation IA au CNAM Lyon", "verbatim_quote": "Bac+5 en Data/IA", "status": "full_match", "evidence_tier": "stated"}], "missing_requirements": [], "score_justification": "Parfait match académique."}'
                )
            )
        ],
        usage=None,
    )

    with patch("app.services.evaluation.evaluator.acompletion", side_effect=[mock_p1, mock_p2]) as mock_acompletion:
        res = await evaluate_offer_two_pass(
            db=db,
            user_id=TEST_USER_ID,
            offer_id=TEST_OFFER_ID,
        )
        assert res.score == 5.0
        pass2_prompt = mock_acompletion.call_args_list[1].kwargs["messages"][0]["content"]
        assert "CNAM Lyon" in pass2_prompt
        assert "Spécialisation en Intelligence Artificielle" in pass2_prompt
        assert "WideDocs" in pass2_prompt
        assert "Azure AI Engineer" in pass2_prompt
        assert "English (Fluent)" in pass2_prompt


