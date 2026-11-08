"""Tests de résilience LLM de l'évaluateur (retries 503, repli multi-modèle, traçabilité)."""

from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
import litellm
import pytest

from app.services.evaluation import evaluator
from tests.evaluation.conftest import (
    TEST_OFFER_ID,
    TEST_USER_ID,
    make_eval_db,
    make_llm_response,
)

PRIMARY_MODEL = "gemini/gemini-3.8-flash"
FALLBACK_MODEL = "gemini/gemini-2.5-flash"


def _gemini_503():
    return litellm.ServiceUnavailableError(
        message="This model is currently experiencing high demand.",
        llm_provider="vertex_ai",
        model="gemini-3.8-flash",
    )


@pytest.mark.asyncio
async def test_scoring_llm_call_retries_transient_503():
    ok = MagicMock()
    with patch.object(evaluator, "acompletion", AsyncMock(side_effect=[_gemini_503(), _gemini_503(), ok])) as mock_llm, \
         patch.object(evaluator.asyncio, "sleep", AsyncMock()) as mock_sleep:
        result = await evaluator._acompletion_retry(model=PRIMARY_MODEL, messages=[])

    assert result is ok
    assert mock_llm.await_count == 3
    assert [c.args[0] for c in mock_sleep.await_args_list] == [2, 5]


@pytest.mark.asyncio
async def test_scoring_llm_call_gives_up_after_last_attempt():
    with patch.object(evaluator, "acompletion", AsyncMock(side_effect=_gemini_503())) as mock_llm, \
         patch.object(evaluator.asyncio, "sleep", AsyncMock()):
        with pytest.raises(litellm.ServiceUnavailableError):
            await evaluator._acompletion_retry(model=PRIMARY_MODEL, messages=[])

    assert mock_llm.await_count == len(evaluator.LLM_RETRY_DELAYS) + 1


@pytest.mark.asyncio
async def test_scoring_llm_call_does_not_retry_non_transient_error():
    with patch.object(evaluator, "acompletion", AsyncMock(side_effect=ValueError("bad request"))) as mock_llm, \
         patch.object(evaluator.asyncio, "sleep", AsyncMock()) as mock_sleep:
        with pytest.raises(ValueError):
            await evaluator._acompletion_retry(model=PRIMARY_MODEL, messages=[])

    assert mock_llm.await_count == 1
    mock_sleep.assert_not_awaited()


@pytest.mark.asyncio
async def test_scoring_switches_to_fallback_model_after_retries_exhausted():
    ok = MagicMock()
    primary_failures = [_gemini_503()] * (len(evaluator.LLM_RETRY_DELAYS) + 1)
    models_used = []
    with patch.object(evaluator, "EVALUATION_FALLBACK_MODEL", FALLBACK_MODEL), \
         patch.object(evaluator, "acompletion", AsyncMock(side_effect=[*primary_failures, ok])) as mock_llm, \
         patch.object(evaluator.asyncio, "sleep", AsyncMock()):
        result = await evaluator._acompletion_with_fallback(models_used, model=PRIMARY_MODEL, messages=[])

    assert result is ok
    assert mock_llm.await_args_list[-1].kwargs["model"] == FALLBACK_MODEL
    assert models_used == [FALLBACK_MODEL]


@pytest.mark.asyncio
async def test_scoring_keeps_primary_model_when_it_answers():
    ok = MagicMock()
    models_used = []
    with patch.object(evaluator, "EVALUATION_FALLBACK_MODEL", FALLBACK_MODEL), \
         patch.object(evaluator, "acompletion", AsyncMock(return_value=ok)) as mock_llm:
        result = await evaluator._acompletion_with_fallback(models_used, model=PRIMARY_MODEL, messages=[])

    assert result is ok
    assert mock_llm.await_count == 1
    assert models_used == [PRIMARY_MODEL]


@pytest.mark.asyncio
async def test_scoring_raises_when_fallback_also_fails():
    with patch.object(evaluator, "EVALUATION_FALLBACK_MODEL", FALLBACK_MODEL), \
         patch.object(evaluator, "acompletion", AsyncMock(side_effect=_gemini_503())) as mock_llm, \
         patch.object(evaluator.asyncio, "sleep", AsyncMock()):
        with pytest.raises(litellm.ServiceUnavailableError):
            await evaluator._acompletion_with_fallback([], model=PRIMARY_MODEL, messages=[])

    assert mock_llm.await_count == len(evaluator.LLM_RETRY_DELAYS) + 2


@pytest.mark.asyncio
async def test_scoring_does_not_fallback_to_same_model():
    with patch.object(evaluator, "EVALUATION_FALLBACK_MODEL", PRIMARY_MODEL), \
         patch.object(evaluator, "acompletion", AsyncMock(side_effect=_gemini_503())) as mock_llm, \
         patch.object(evaluator.asyncio, "sleep", AsyncMock()):
        with pytest.raises(litellm.ServiceUnavailableError):
            await evaluator._acompletion_with_fallback([], model=PRIMARY_MODEL, messages=[])

    assert mock_llm.await_count == len(evaluator.LLM_RETRY_DELAYS) + 1


@pytest.mark.asyncio
async def test_evaluation_records_models_actually_used():
    offer_doc = {
        "_id": ObjectId(TEST_OFFER_ID),
        "poste": "Préparateur de commandes",
        "entreprise": "Logistique SA",
        "description": "Préparation de commandes, CACES 1 exigé.",
    }
    profile_doc = {"user_id": TEST_USER_ID, "headline": "Préparateur"}
    db, cols = make_eval_db(offer_doc=offer_doc, profile_doc=profile_doc)

    pass1 = make_llm_response({
        "archetype": "Préparateur de commandes",
        "summary": "Préparation en entrepôt.",
        "requirements": [{"requirement": "CACES 1", "weight": "critical", "quote_from_offer": "CACES 1 exigé"}],
        "is_ghost_job": False,
        "ghost_job_warnings": [],
    })
    pass2 = make_llm_response({"matched_requirements": [], "missing_requirements": []})
    primary_failures = [_gemini_503()] * (len(evaluator.LLM_RETRY_DELAYS) + 1)

    with patch.object(evaluator, "EVALUATION_FALLBACK_MODEL", FALLBACK_MODEL), \
         patch.object(evaluator, "compute_domain_relevance", AsyncMock(return_value=None)), \
         patch.object(evaluator, "acompletion", AsyncMock(side_effect=[*primary_failures, pass1, pass2])), \
         patch.object(evaluator.asyncio, "sleep", AsyncMock()), \
         patch.object(evaluator, "record_api_usage", AsyncMock()) as mock_usage:
        await evaluator.evaluate_offer_two_pass(
            db=db, user_id=TEST_USER_ID, offer_id=TEST_OFFER_ID, model=PRIMARY_MODEL
        )

    stored = cols["offer_evaluations"].update_one.call_args.args[1]["$set"]
    assert stored["models_used"] == [FALLBACK_MODEL, PRIMARY_MODEL]
    assert mock_usage.await_args.kwargs["models_used"] == [FALLBACK_MODEL, PRIMARY_MODEL]
