"""Tests du service d'évaluation à deux passes (pipeline, garde-fous, profil et quota)."""

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
import pytest
from fastapi import HTTPException

from app.services.evaluation.evaluator import (
    compute_offer_evaluation,
    evaluate_offer_two_pass,
)
from tests.evaluation.conftest import (
    TEST_OFFER_ID,
    TEST_USER_ID,
    make_eval_db,
    make_llm_response,
)


@pytest.mark.asyncio
async def test_evaluate_offer_two_pass_success():
    db, cols = make_eval_db()

    pass1 = make_llm_response({
        "archetype": "Senior Fullstack Engineer",
        "summary": "Opportunité pour un ingénieur expérimenté.",
        "requirements": [
            {"requirement": "FastAPI", "weight": "critical", "quote_from_offer": "maîtrisant React, FastAPI et MongoDB"},
            {"requirement": "Non mentionné", "weight": "high", "quote_from_offer": "absent"},
        ],
        "is_ghost_job": False,
        "is_scam_risk": False,
        "ghost_job_warnings": [],
    })
    pass2 = make_llm_response({
        "matched_requirements": [
            {
                "requirement": "FastAPI",
                "weight": "critical",
                "candidate_evidence": "Expérience chez Tech Corp avec FastAPI",
                "verbatim_quote": "maîtrisant React, FastAPI et MongoDB",
                "status": "full_match",
                "evidence_tier": "stated",
            }
        ],
        "missing_requirements": [
            {"requirement": "Non mentionné", "weight": "high", "reason": "absent"}
        ],
    })

    with patch("app.services.evaluation.evaluator.compute_domain_relevance", AsyncMock(return_value=None)), \
         patch("app.services.evaluation.evaluator.acompletion", AsyncMock(side_effect=[pass1, pass2])):
        evaluation = await evaluate_offer_two_pass(db=db, user_id=TEST_USER_ID, offer_id=TEST_OFFER_ID)

    assert evaluation.score > 1.0
    assert evaluation.bloc_a.archetype == "Senior Fullstack Engineer"
    assert len(evaluation.bloc_b.matched_requirements) == 1
    assert evaluation.bloc_b.matched_requirements[0].verbatim_quote == "maîtrisant React, FastAPI et MongoDB"
    assert evaluation.bloc_g.is_ghost_job is False

    cols["job_offers"].update_one.assert_called_once()
    cols["offer_evaluations"].update_one.assert_called_once()


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
    profile_doc = {
        "user_id": TEST_USER_ID,
        "headline": "Animateur",
        "preferences": {"contract_types": ["CDI"], "seniority_levels": ["junior"]},
    }
    db, cols = make_eval_db(offer_doc=offer_doc, profile_doc=profile_doc)
    cols["job_offers"].count_documents = AsyncMock(return_value=3)

    pass1 = make_llm_response({
        "archetype": "Animateur périscolaire",
        "summary": "Encadrement périscolaire.",
        "requirements": [
            {"requirement": "BAFA", "weight": "critical", "quote_from_offer": "Titulaire du BAFA"},
            {"requirement": "Encadrement d'enfants", "weight": "critical", "quote_from_offer": "vous encadrez"},
            {"requirement": "Permis B", "weight": "meaningful", "quote_from_offer": "Permis B apprécié"},
        ],
        "is_ghost_job": True,
        "ghost_job_warnings": [],
    })
    pass2 = make_llm_response({
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
    })

    with patch("app.services.evaluation.evaluator.compute_domain_relevance", AsyncMock(return_value=None)), \
         patch("app.services.evaluation.evaluator.acompletion", AsyncMock(side_effect=[pass1, pass2])):
        evaluation = await evaluate_offer_two_pass(db=db, user_id=TEST_USER_ID, offer_id=TEST_OFFER_ID)

    assert cols["job_offers"].count_documents.call_args.args[0]["canonical_title"] == "animateur periscolaire"
    assert evaluation.bloc_a.domain_coherence == "partial"
    assert {(m.criterion, m.weight) for m in evaluation.bloc_a.preference_mismatches} == {
        ("contrat", "high"),
        ("séniorité", "high"),
    }
    bafa = evaluation.bloc_b.matched_requirements[0]
    assert bafa.weight == "critical"
    assert bafa.quote_verified is False
    assert {m.requirement for m in evaluation.bloc_b.missing_requirements} == {"Permis B", "Encadrement d'enfants"}
    assert evaluation.bloc_g.reposted_frequency == "3 publications"
    assert evaluation.score == 1.5


@pytest.mark.asyncio
async def test_compute_offer_evaluation_has_no_side_effects():
    write_methods = ("update_one", "update_many", "insert_one", "replace_one", "delete_one", "delete_many")
    collections = {}

    def collection(name):
        if name not in collections:
            col = AsyncMock()
            for method in write_methods:
                setattr(col, method, AsyncMock(side_effect=AssertionError(f"{name}.{method} interdit")))
            collections[name] = col
        return collections[name]

    collection("job_offers").find_one.return_value = {
        "_id": ObjectId(TEST_OFFER_ID),
        "poste": "Senior Fullstack Engineer",
        "entreprise": "Acme Corp",
        "description": "Nous recherchons un Senior Fullstack Engineer maîtrisant React, FastAPI et MongoDB.",
    }
    collection("candidate_profile").find_one.return_value = {
        "user_id": TEST_USER_ID,
        "headline": "Fullstack Developer 6 YoE",
        "skills": {"frameworks": ["FastAPI", "React"]},
    }
    db = MagicMock()
    db.__getitem__.side_effect = collection

    pass1 = make_llm_response({
        "archetype": "Senior Fullstack Engineer",
        "summary": "Mission fullstack.",
        "requirements": [{"requirement": "FastAPI", "weight": "critical", "quote_from_offer": "maîtrisant React, FastAPI et MongoDB"}],
    })
    pass2 = make_llm_response({
        "matched_requirements": [{"requirement": "FastAPI", "weight": "critical", "candidate_evidence": "ok", "verbatim_quote": "maîtrisant React, FastAPI et MongoDB", "status": "full_match"}],
        "missing_requirements": [],
    })

    with patch("app.services.evaluation.evaluator.compute_domain_relevance", AsyncMock(return_value=None)), \
         patch("app.services.evaluation.evaluator.acompletion", AsyncMock(side_effect=[pass1, pass2])):
        run = await compute_offer_evaluation(db=db, user_id=TEST_USER_ID, offer_id=TEST_OFFER_ID)

    assert run.evaluation["score"] == 4.0
    assert run.evaluation["offer_id"] == TEST_OFFER_ID


@pytest.mark.asyncio
async def test_evaluate_offer_quota_exceeded():
    db = MagicMock()
    users_col = AsyncMock()
    users_col.find_one.return_value = {"_id": ObjectId(TEST_USER_ID), "tier": "free"}

    async def cursor_quota_reached(*args, **kwargs):
        yield {"_id": "evaluation", "count": 20, "total_tokens": 50000, "total_cost": 0.20}

    api_usage_col = AsyncMock()
    api_usage_col.aggregate = MagicMock(side_effect=cursor_quota_reached)

    def db_getitem(name):
        return users_col if name == "users" else api_usage_col

    db.__getitem__.side_effect = db_getitem

    with patch.dict(os.environ, {"DISABLE_QUOTA_BLOCKING": "false"}):
        with pytest.raises(HTTPException) as exc_info:
            await evaluate_offer_two_pass(db=db, user_id=TEST_USER_ID, offer_id=TEST_OFFER_ID)
    assert exc_info.value.status_code == 429
    assert "Monthly quota limit reached" in exc_info.value.detail


@pytest.mark.asyncio
async def test_evaluate_offer_candidate_profile_lookup_supports_objectid_and_str():
    db, cols = make_eval_db()

    async def mock_find_profile(query):
        for cond in query.get("$or", []):
            if cond.get("user_id") in (ObjectId(TEST_USER_ID), TEST_USER_ID):
                return {
                    "headline": "Lead AI Engineer",
                    "experiences": [{"role": "AI Dev", "company": "Co", "stack": ["Python"]}],
                    "skills": {"languages": ["Python"]},
                    "preferences": {"locations": ["Lyon"]},
                }
        return None

    cols["candidate_profile"].find_one = AsyncMock(side_effect=mock_find_profile)
    pass1 = make_llm_response({"archetype": "AI Engineer", "summary": "Job", "requirements": [], "is_ghost_job": False, "is_scam_risk": False, "ghost_job_warnings": []})
    pass2 = make_llm_response({"matched_requirements": [], "missing_requirements": []})

    with patch("app.services.evaluation.evaluator.compute_domain_relevance", AsyncMock(return_value=None)), \
         patch("app.services.evaluation.evaluator.acompletion", AsyncMock(side_effect=[pass1, pass2])):
        res = await evaluate_offer_two_pass(db=db, user_id=TEST_USER_ID, offer_id=TEST_OFFER_ID)

    assert res.score == 3.0
    called_query = cols["candidate_profile"].find_one.call_args[0][0]
    assert "$or" in called_query
    assert {"user_id": ObjectId(TEST_USER_ID)} in called_query["$or"]
    assert {"user_id": TEST_USER_ID} in called_query["$or"]


@pytest.mark.asyncio
async def test_evaluate_offer_pass2_receives_education_and_projects():
    profile_doc = {
        "user_id": TEST_USER_ID,
        "headline": "Junior Dev",
        "education": [{"school": "CNAM Lyon", "degree": "Spécialisation en Intelligence Artificielle"}],
        "projects": [{"name": "WideDocs", "description": "Plateforme FastAPI"}],
        "certifications": [{"name": "Azure AI Engineer"}],
        "languages": ["English (Fluent)"],
    }
    db, _ = make_eval_db(profile_doc=profile_doc)

    pass1 = make_llm_response({"archetype": "Dev", "summary": "Job", "requirements": [{"requirement": "Master", "weight": "critical", "quote_from_offer": "Bac+5"}]})
    pass2 = make_llm_response({"matched_requirements": [], "missing_requirements": []})
    mock_llm = AsyncMock(side_effect=[pass1, pass2])

    with patch("app.services.evaluation.evaluator.compute_domain_relevance", AsyncMock(return_value=None)), \
         patch("app.services.evaluation.evaluator.acompletion", mock_llm):
        await evaluate_offer_two_pass(db=db, user_id=TEST_USER_ID, offer_id=TEST_OFFER_ID)

    pass2_prompt = mock_llm.call_args_list[1].kwargs["messages"][0]["content"]
    assert "CNAM Lyon" in pass2_prompt
    assert "WideDocs" in pass2_prompt
    assert "Azure AI Engineer" in pass2_prompt
    assert "English (Fluent)" in pass2_prompt


@pytest.mark.asyncio
async def test_evaluate_offer_two_pass_short_circuits_on_domain_mismatch():
    db, cols = make_eval_db()
    with patch("app.services.evaluation.evaluator.compute_domain_relevance", AsyncMock(return_value=0.05)), \
         patch("app.services.evaluation.evaluator.acompletion") as mock_acompletion:
        evaluation = await evaluate_offer_two_pass(db=db, user_id=TEST_USER_ID, offer_id=TEST_OFFER_ID)

    mock_acompletion.assert_not_called()
    assert evaluation.bloc_a.domain_mismatch is True
    assert evaluation.score == 1.5
    cols["job_offers"].update_one.assert_called_once()
    cols["offer_evaluations"].update_one.assert_called_once()
