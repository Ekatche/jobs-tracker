import litellm
import pytest
from fastapi import HTTPException

from app.llm.provider_errors import classify_llm_error, llm_http_exception


def _rate_limit(provider, model, message):
    return litellm.RateLimitError(message=message, llm_provider=provider, model=model)


def test_openai_insufficient_quota_is_credits_not_rate_limit():
    # OpenAI signale l'épuisement des crédits par un 429, comme une limite de débit.
    err = _rate_limit(
        "openai", "gpt-5.6-terra",
        "You exceeded your current quota, please check your plan and billing details. "
        "{'code': 'insufficient_quota'}",
    )
    info = classify_llm_error(err)
    assert info.kind == "credits"
    assert info.status_code == 402
    assert "OpenAI" in info.message
    assert "gpt-5.6-terra" in info.message
    assert "platform.openai.com" in info.message


def test_gemini_per_minute_quota_is_rate_limit():
    # Le message Gemini par minute parle aussi de « billing details » : ce n'est pas un épuisement de crédits.
    err = _rate_limit(
        "gemini", "gemini-3.8-flash",
        "RESOURCE_EXHAUSTED: You exceeded your current quota, please check your plan and billing details. "
        "Quota exceeded for metric: GenerateRequestsPerMinutePerProjectPerModel. Please retry in 18s.",
    )
    info = classify_llm_error(err)
    assert info.kind == "rate_limit"
    assert info.status_code == 429
    assert "Google Gemini" in info.message


def test_mistral_402_is_credits():
    err = litellm.APIError(
        status_code=402, message="Payment Required", llm_provider="mistral", model="mistral-large-2512"
    )
    info = classify_llm_error(err)
    assert info.kind == "credits"
    assert "Mistral" in info.message


def test_anthropic_credit_balance_is_credits():
    err = litellm.BadRequestError(
        message="Your credit balance is too low to access the Anthropic API.",
        model="claude-opus-5-5", llm_provider="anthropic",
    )
    info = classify_llm_error(err)
    assert info.kind == "credits"
    assert "Anthropic" in info.message


def test_authentication_error():
    err = litellm.AuthenticationError(message="Incorrect API key provided", llm_provider="openai", model="gpt-5.6-terra")
    info = classify_llm_error(err)
    assert info.kind == "auth"
    assert info.status_code == 502
    assert "OpenAI" in info.message


def test_overloaded_error():
    err = litellm.ServiceUnavailableError(
        message="The model is overloaded", llm_provider="gemini", model="gemini-3.8-flash"
    )
    info = classify_llm_error(err)
    assert info.kind == "overloaded"
    assert info.status_code == 503
    assert "Google Gemini" in info.message


def test_error_wrapped_by_a_service_is_found_in_the_chain():
    cause = _rate_limit("openai", "gpt-5.6-terra", "insufficient_quota")
    try:
        try:
            raise cause
        except Exception as e:
            raise ValueError("échec de génération") from e
    except ValueError as wrapped:
        info = classify_llm_error(wrapped)
    assert info is not None and info.kind == "credits"


def test_provider_deduced_from_model_prefix_when_missing():
    err = litellm.RateLimitError(message="insufficient_quota", llm_provider="", model="openai/gpt-5.6-terra")
    assert "OpenAI" in classify_llm_error(err).message


def test_non_llm_error_is_not_classified():
    assert classify_llm_error(ValueError("JSON invalide")) is None
    assert llm_http_exception(ValueError("JSON invalide")) is None


def test_llm_http_exception_carries_status_and_message():
    err = _rate_limit("openai", "gpt-5.6-terra", "insufficient_quota")
    exc = llm_http_exception(err)
    assert isinstance(exc, HTTPException)
    assert exc.status_code == 402
    assert "OpenAI" in exc.detail
