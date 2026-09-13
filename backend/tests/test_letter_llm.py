import os
import sys
import pytest
from pathlib import Path

# Ensure job_trackers source is importable
job_trackers_path = Path(__file__).parent.parent / "job_trackers" / "src" / "job_trackers"
if str(job_trackers_path) not in sys.path:
    sys.path.insert(0, str(job_trackers_path))

from letter_llm import get_letter_llm, get_model_provider, validate_cross_provider

def test_model_provider_detection():
    assert get_model_provider("gemini/gemini-3.8-flash") == "google"
    assert get_model_provider("openai/gpt-5.6-sol") == "openai"
    assert get_model_provider("mistral/mistral-large-3-0") == "mistral"

def test_disallow_latest_or_preview_aliases():
    with pytest.raises(ValueError, match="floating alias"):
        get_letter_llm("offer_analyst", model_override="gemini/gemini-flash-latest")
    with pytest.raises(ValueError, match="floating alias"):
        get_letter_llm("writer", model_override="openai/gpt-4o-preview")

def test_cross_provider_conflict_raises_error():
    # Writer and Critic on same provider must fail at startup
    with pytest.raises(ValueError, match="same provider"):
        validate_cross_provider("openai/gpt-5.6-sol", "openai/gpt-4o-mini")

def test_valid_cross_provider_resolution():
    critic_model = validate_cross_provider("openai/gpt-5.6-sol", None)
    assert get_model_provider(critic_model) == "google"

    critic_model_mistral = validate_cross_provider("mistral/mistral-large-3-0", None)
    assert get_model_provider(critic_model_mistral) == "openai"

def test_format_llm_error_quota_and_key():
    from letter_llm import format_llm_error
    quota_err = Exception("Error code: 429 - {'error': {'message': 'You exceeded your current quota, please check your plan and billing details.'}}")
    msg = format_llm_error(quota_err, "openai")
    assert "Crédits épuisés ou quota" in msg
    assert "OPENAI" in msg

    auth_err = Exception("Error code: 401 - Incorrect API key provided")
    msg_auth = format_llm_error(auth_err, "mistral")
    assert "Clé API MISTRAL invalide" in msg_auth

def test_get_api_status_structure():
    from letter_llm import get_api_status
    status = get_api_status()
    assert "google" in status
    assert "openai" in status
    assert "mistral" in status
    assert "billing_url" in status["openai"]

