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
    PreferenceMismatch,
    RequirementMatch,
    UserModel,
    UserTier,
)
from app.services.evaluation.evaluator import (
    _clean_json_output,
    calculate_evaluation_score,
    evaluate_offer_two_pass,
    quote_in_offer,
    reconcile_with_pass1,
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


def _match(requirement, weight="critical", status="full_match", quote_verified=True):
    return RequirementMatch(
        requirement=requirement,
        weight=weight,
        candidate_evidence="preuve",
        verbatim_quote="citation",
        status=status,
        quote_verified=quote_verified,
    )


def _missing(requirement, weight="critical"):
    return MissingRequirement(requirement=requirement, weight=weight, reason="absent")


FOUR_FULL_MATCHES = [_match("Python"), _match("FastAPI"), _match("MongoDB", "high"), _match("Docker", "meaningful")]


def test_calculate_evaluation_score_perfect():
    bloc_b = BlocB(matched_requirements=FOUR_FULL_MATCHES)
    assert calculate_evaluation_score(BlocA(), bloc_b, BlocG(), description_length=1200) == 5.0


def test_calculate_evaluation_score_red_flag_caps():
    bloc_a_geo = BlocA(archetype="Staff Engineer", geo_mismatch=True)
    bloc_b = BlocB(matched_requirements=FOUR_FULL_MATCHES)
    bloc_g = BlocG(is_ghost_job=False, is_scam_risk=False)
    assert calculate_evaluation_score(bloc_a_geo, bloc_b, bloc_g) == 1.5

    bloc_a_clean = BlocA(archetype="Staff Engineer", geo_mismatch=False)
    bloc_g_scam = BlocG(is_ghost_job=False, is_scam_risk=True)
    assert calculate_evaluation_score(bloc_a_clean, bloc_b, bloc_g_scam) == 1.5


def test_ghost_job_caps_only_when_repost_detected():
    bloc_a = BlocA(archetype="Staff Engineer")
    bloc_b = BlocB(matched_requirements=FOUR_FULL_MATCHES)
    # Le jugement "ghost" du modèle seul ne suffit plus à plafonner.
    assert calculate_evaluation_score(bloc_a, bloc_b, BlocG(is_ghost_job=True)) == 5.0
    corroborated = BlocG(is_ghost_job=True, reposted_frequency="3 publications")
    assert calculate_evaluation_score(bloc_a, bloc_b, corroborated) == 1.5


def test_calculate_evaluation_score_domain_mismatch_caps():
    bloc_a = BlocA(archetype="Data Scientist", domain_mismatch=True)
    bloc_b = BlocB(matched_requirements=[], missing_requirements=[])
    bloc_g = BlocG(is_ghost_job=False, is_scam_risk=False)
    assert calculate_evaluation_score(bloc_a, bloc_b, bloc_g) == 1.5


def test_score_is_weighted_coverage():
    bloc_b = BlocB(
        matched_requirements=[_match("Python", "critical"), _match("Go", "high")],
        missing_requirements=[_missing("Kubernetes", "critical"), _missing("GCP", "meaningful")],
    )
    # poids 3 + 2 + 3 + 1 = 9, acquis 5 : 1 + 4 x 5/9 = 3.22
    assert calculate_evaluation_score(BlocA(), bloc_b, BlocG()) == 3.22


def test_partial_match_earns_half_credit():
    bloc_b = BlocB(
        matched_requirements=[
            _match("5 ans d'expérience", "critical", "partial_match"),
            _match("Kafka", "high", "partial_match"),
            _match("Python", "critical"),
            _match("Anglais", "meaningful"),
        ]
    )
    # poids 3 + 2 + 3 + 1 = 9, acquis 1.5 + 1 + 3 + 1 = 6.5 : 1 + 4 x 6.5/9 = 3.89
    assert calculate_evaluation_score(BlocA(), bloc_b, BlocG()) == 3.89


def test_calculate_evaluation_score_min_bound():
    bloc_b = BlocB(missing_requirements=[_missing(f"Req {i}") for i in range(10)])
    assert calculate_evaluation_score(BlocA(), bloc_b, BlocG()) == 1.0


def test_no_requirement_evaluated_is_neutral():
    assert calculate_evaluation_score(BlocA(), BlocB(), BlocG()) == 3.0


def test_thin_offer_is_capped():
    few = BlocB(matched_requirements=FOUR_FULL_MATCHES[:3])
    assert calculate_evaluation_score(BlocA(), few, BlocG(), description_length=1200) == 4.0

    enough = BlocB(matched_requirements=FOUR_FULL_MATCHES)
    assert calculate_evaluation_score(BlocA(), enough, BlocG(), description_length=290) == 4.0
    # Longueur inconnue : seul le nombre d'exigences compte.
    assert calculate_evaluation_score(BlocA(), enough, BlocG()) == 5.0


def test_preference_mismatches_and_partial_domain_are_penalized():
    bloc_a = BlocA(
        domain_coherence="partial",
        preference_mismatches=[
            PreferenceMismatch(criterion="contrat", offer_value="Stage", expected="CDI", weight="high"),
            PreferenceMismatch(criterion="séniorité", offer_value="senior", expected="mid", weight="meaningful"),
        ],
    )
    bloc_b = BlocB(matched_requirements=FOUR_FULL_MATCHES)
    # 5.0 - 0.5 (contrat) - 0.2 (séniorité) - 0.5 (domaine partiel) = 3.8
    assert calculate_evaluation_score(bloc_a, bloc_b, BlocG()) == 3.8


def test_unverified_quote_does_not_change_score():
    unverified = BlocB(matched_requirements=FOUR_FULL_MATCHES[:3] + [_match("Docker", "meaningful", quote_verified=False)])
    assert calculate_evaluation_score(BlocA(), unverified, BlocG()) == 5.0


# --- Unit Tests: réconciliation Pass 1 / Pass 2 & vérification des citations ---

PASS1_REQUIREMENTS = [
    {"id": "R1", "requirement": "BAFA", "weight": "critical"},
    {"id": "R2", "requirement": "Permis B", "weight": "high"},
    {"id": "R3", "requirement": "Anglais", "weight": "meaningful"},
]


def test_reconcile_imposes_pass1_weight_and_adds_untreated_requirements():
    matched = [{"req_id": "R1", "requirement": "BAFA", "weight": "meaningful", "status": "full_match"}]
    missing = [{"req_id": "R3", "requirement": "Anglais", "weight": "critical", "reason": "absent"}]

    matched_out, missing_out = reconcile_with_pass1(PASS1_REQUIREMENTS, matched, missing)

    assert matched_out[0]["weight"] == "critical"
    assert [m["weight"] for m in missing_out if m["req_id"] == "R3"] == ["meaningful"]
    untreated = [m for m in missing_out if m["req_id"] == "R2"]
    assert len(untreated) == 1
    assert untreated[0]["weight"] == "high"
    assert "non traitée" in untreated[0]["reason"]


def test_reconcile_without_req_ids_keeps_pass2_as_is():
    matched = [{"requirement": "BAFA", "weight": "high", "status": "full_match"}]

    matched_out, missing_out = reconcile_with_pass1(PASS1_REQUIREMENTS, matched, [])

    assert matched_out[0]["weight"] == "high"
    assert missing_out == []


def test_reconcile_ignores_unknown_req_id():
    matched = [
        {"req_id": "R1", "requirement": "BAFA", "weight": "critical"},
        {"req_id": "R9", "requirement": "Inventé", "weight": "high"},
    ]

    matched_out, missing_out = reconcile_with_pass1(PASS1_REQUIREMENTS, matched, [])

    assert matched_out[1]["weight"] == "high"
    assert {m["req_id"] for m in missing_out} == {"R2", "R3"}


@pytest.mark.parametrize(
    "quote,expected",
    [
        ("Titulaire du BAFA", True),
        ("titulaire   du  bafa", True),
        ("l’équipe d'animation", True),
        ("Titulaire du BAFA ... permis B apprécié", True),
        ("Titulaire du BAFA … permis B apprécié", True),
        ("BAFA obligatoire", False),
        ("Titulaire du BAFA ... permis C", False),
        ("", False),
    ],
)
def test_quote_in_offer(quote, expected):
    offer = "Poste d'animateur. Titulaire du BAFA, vous rejoignez l'équipe d'animation.\nPermis B apprécié."
    assert quote_in_offer(quote, offer) is expected


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

    with patch("app.services.evaluation.evaluator.compute_domain_relevance", AsyncMock(return_value=None)), \
         patch("app.services.evaluation.evaluator.acompletion", AsyncMock(side_effect=[pass1_response, pass2_response])):
        evaluation = await evaluate_offer_two_pass(
            db=db,
            user_id=TEST_USER_ID,
            offer_id=TEST_OFFER_ID,
        )

        assert isinstance(evaluation, OfferEvaluation)
        assert evaluation.user_id == TEST_USER_ID
        assert evaluation.offer_id == TEST_OFFER_ID
        # 1 exigence sur une description courte : plafond "offre pauvre"
        assert evaluation.score == 4.0
        assert evaluation.bloc_a.archetype == "Senior Fullstack Engineer"
        assert len(evaluation.bloc_b.matched_requirements) == 1
        assert evaluation.bloc_b.matched_requirements[0].verbatim_quote == "maîtrisant React, FastAPI et MongoDB"
        assert evaluation.bloc_g.is_ghost_job is False

        # Check DB updates
        job_offers_collection.update_one.assert_called_once()
        offer_evaluations_collection.update_one.assert_called_once()


def _llm_response(payload):
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=json.dumps(payload)))]
    response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)
    return response


@pytest.mark.asyncio
async def test_evaluate_offer_two_pass_wires_blocs_a_b_g():
    offer_doc = {
        "_id": ObjectId(TEST_OFFER_ID),
        "poste": "Animateur périscolaire",
        "entreprise": "Mairie de Lyon",
        "canonical_title": "animateur periscolaire",
        "type_contrat": "CDD",
        "seniority_level": "senior",
        "description": "Titulaire du BAFA, vous encadrez des groupes d'enfants. Permis B apprécié.",
    }
    job_offers = AsyncMock()
    job_offers.find_one.return_value = offer_doc
    job_offers.count_documents.return_value = 3
    profiles = AsyncMock()
    profiles.find_one.return_value = {
        "user_id": TEST_USER_ID,
        "headline": "Animateur",
        "preferences": {"contract_types": ["CDI"], "seniority_levels": ["junior"]},
    }

    async def empty_cursor(*args, **kwargs):
        if False:
            yield {}

    def db_getitem(name):
        if name == "job_offers":
            return job_offers
        if name == "candidate_profile":
            return profiles
        if name == "users":
            users = AsyncMock()
            users.find_one.return_value = {"_id": ObjectId(TEST_USER_ID), "tier": "free"}
            return users
        if name == "api_usage":
            api = AsyncMock()
            api.aggregate = MagicMock(side_effect=lambda *a, **k: empty_cursor())
            api.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
            return api
        return AsyncMock()

    db = MagicMock()
    db.__getitem__.side_effect = db_getitem

    pass1 = _llm_response(
        {
            "archetype": "Animateur périscolaire",
            "summary": "Encadrement périscolaire.",
            "requirements": [
                {"requirement": "BAFA", "weight": "critical", "quote_from_offer": "Titulaire du BAFA"},
                {"requirement": "Encadrement d'enfants", "weight": "critical", "quote_from_offer": "vous encadrez"},
                {"requirement": "Permis B", "weight": "meaningful", "quote_from_offer": "Permis B apprécié"},
            ],
            "is_ghost_job": True,
            "ghost_job_warnings": [],
        }
    )
    pass2 = _llm_response(
        {
            "domain_coherence": "partial",
            "matched_requirements": [
                {
                    "req_id": "R1",
                    "requirement": "BAFA",
                    "weight": "high",
                    "candidate_evidence": "BAFA obtenu",
                    "verbatim_quote": "BAFA exigé",
                    "status": "full_match",
                    "evidence_tier": "stated",
                }
            ],
            "missing_requirements": [
                {"req_id": "R3", "requirement": "Permis B", "weight": "meaningful", "reason": "absent"}
            ],
        }
    )

    with patch("app.services.evaluation.evaluator.compute_domain_relevance", AsyncMock(return_value=None)), \
         patch("app.services.evaluation.evaluator.acompletion", AsyncMock(side_effect=[pass1, pass2])):
        evaluation = await evaluate_offer_two_pass(db=db, user_id=TEST_USER_ID, offer_id=TEST_OFFER_ID)

    count_filter = job_offers.count_documents.call_args.args[0]
    assert count_filter["canonical_title"] == "animateur periscolaire"
    assert count_filter["entreprise"]["$options"] == "i"

    # Bloc A : cohérence partielle + écarts de préférences (contrat, séniorité distance 2)
    assert evaluation.bloc_a.domain_coherence == "partial"
    assert {(m.criterion, m.weight) for m in evaluation.bloc_a.preference_mismatches} == {
        ("contrat", "high"),
        ("séniorité", "high"),
    }
    # Bloc B : poids Pass 1 imposé, R2 non traitée devenue manquante, citation reformulée détectée
    bafa = evaluation.bloc_b.matched_requirements[0]
    assert bafa.weight == "critical"
    assert bafa.quote_verified is False
    assert {m.requirement for m in evaluation.bloc_b.missing_requirements} == {"Permis B", "Encadrement d'enfants"}
    # Bloc G : republication détectée + description courte ; ghost corroboré => plafond
    assert evaluation.bloc_g.reposted_frequency == "3 publications"
    assert any("publiée 3 fois" in w for w in evaluation.bloc_g.warnings)
    assert any("Description courte" in w for w in evaluation.bloc_g.warnings)
    assert evaluation.score == 1.5


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
        with patch("app.services.evaluation.evaluator.compute_domain_relevance", AsyncMock(return_value=None)), \
             patch("app.services.evaluation.evaluator.acompletion", AsyncMock(side_effect=[pass1_response, pass2_response])):
            # 1. Trigger POST evaluate
            res_post = client.post(f"/job-offers/{TEST_OFFER_ID}/evaluate")
            assert res_post.status_code == 200, res_post.text
            eval_data = res_post.json()
            assert eval_data["score"] == 4.0  # 1 exigence : plafond "offre pauvre"
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

    with patch("app.services.evaluation.evaluator.compute_domain_relevance", AsyncMock(return_value=None)), \
         patch("app.services.evaluation.evaluator.acompletion", side_effect=[mock_p1, mock_p2]) as mock_acompletion:
        res = await evaluate_offer_two_pass(
            db=db,
            user_id=TEST_USER_ID,
            offer_id=TEST_OFFER_ID,
        )
        assert res.score == 3.0  # aucune exigence évaluée : note neutre
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

    with patch("app.services.evaluation.evaluator.compute_domain_relevance", AsyncMock(return_value=None)), \
         patch("app.services.evaluation.evaluator.acompletion", side_effect=[mock_p1, mock_p2]) as mock_acompletion:
        res = await evaluate_offer_two_pass(
            db=db,
            user_id=TEST_USER_ID,
            offer_id=TEST_OFFER_ID,
        )
        assert res.score == 4.0  # 1 exigence : plafond "offre pauvre"
        pass2_prompt = mock_acompletion.call_args_list[1].kwargs["messages"][0]["content"]
        assert "CNAM Lyon" in pass2_prompt
        assert "Spécialisation en Intelligence Artificielle" in pass2_prompt
        assert "WideDocs" in pass2_prompt
        assert "Azure AI Engineer" in pass2_prompt
        assert "English (Fluent)" in pass2_prompt


@pytest.mark.asyncio
async def test_evaluate_offer_two_pass_short_circuits_on_domain_mismatch():
    """Une offre manifestement hors du domaine du candidat est écartée sans appel LLM Two-Pass."""
    db = MagicMock()
    job_offers_col = AsyncMock()
    job_offers_col.find_one.return_value = {
        "_id": ObjectId(TEST_OFFER_ID),
        "poste": "Data Scientist / Machine Learning Engineer",
        "entreprise": "Excelleria",
        "description": "Poste data science avec Python, TensorFlow et Spark.",
        "localisation": "Lyon",
        "type_contrat": "CDI",
        "mode_travail": "hybride",
    }
    job_offers_col.update_one.return_value = MagicMock(modified_count=1)

    candidate_profile_col = AsyncMock()
    candidate_profile_col.find_one.return_value = {
        "user_id": TEST_USER_ID,
        "headline": "Animatrice 2D",
        "summary": "Animatrice 2D spécialisée en motion design.",
        "skills": {"outils": ["Toon Boom Harmony", "After Effects"]},
        "experiences": [{"role": "Animatrice 2D", "company": "Studio Anim", "stack": []}],
        "preferences": {"target_roles": ["Animatrice 2D"]},
    }

    offer_evaluations_col = AsyncMock()
    offer_evaluations_col.update_one.return_value = MagicMock(upserted_id="eval_anim")

    users_col = AsyncMock()
    users_col.find_one.return_value = {"_id": ObjectId(TEST_USER_ID), "tier": "free"}

    async def mock_cursor(*args, **kwargs):
        if False:
            yield {}

    api_usage_col = AsyncMock()
    api_usage_col.aggregate = MagicMock(side_effect=lambda *a, **k: mock_cursor())
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

    with patch(
        "app.services.evaluation.evaluator.compute_domain_relevance",
        AsyncMock(return_value=0.05),
    ), patch("app.services.evaluation.evaluator.acompletion") as mock_acompletion:
        evaluation = await evaluate_offer_two_pass(
            db=db,
            user_id=TEST_USER_ID,
            offer_id=TEST_OFFER_ID,
        )

    mock_acompletion.assert_not_called()
    assert evaluation.score == 1.5
    assert evaluation.bloc_a.domain_mismatch is True
    job_offers_col.update_one.assert_called_once()
    offer_evaluations_col.update_one.assert_called_once()


