import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Ensure job_trackers source is importable
job_trackers_path = Path(__file__).parent.parent / "job_trackers" / "src" / "job_trackers"
if str(job_trackers_path) not in sys.path:
    sys.path.insert(0, str(job_trackers_path))

import cover_letter_crew
from cover_letter_crew import run_letter_pipeline_sync

def test_pipeline_executes_revision_when_critic_requests():
    mock_analyst = {
        "missions": ["Lead data pipelines"],
        "selected_experiences": [{"company": "Sanofi", "missions": ["Nextflow"]}],
        "stacks": ["Nextflow", "Kafka"],
        "companies": ["Sanofi", "Biomérieux"],
        "projects": []
    }
    mock_writer_letter = "Première version de la lettre Madame, Monsieur..."
    mock_critic_verdict = {"verdict": "revise", "flaws": ["Ton trop convenu"]}
    mock_revised_letter = "Version révisée et corrigée..."

    with patch("cover_letter_crew._call_analyst", return_value=mock_analyst), \
         patch("cover_letter_crew._call_writer", return_value=mock_writer_letter), \
         patch("cover_letter_crew._call_critic", return_value=mock_critic_verdict), \
         patch("cover_letter_crew._call_reviser", return_value=mock_revised_letter), \
         patch("cover_letter_crew.validate_cross_provider"):

        result = run_letter_pipeline_sync(
            offer_description="Offre Biomérieux Lead Data",
            candidate_profile={"headline": "Data Engineer"},
            company_name="Biomérieux"
        )

        assert result["body"] == mock_revised_letter
        assert result["revised"] is True
        assert result["critic_verdict"]["verdict"] == "revise"

def test_completion_uses_max_completion_tokens():
    from cover_letter_crew import _call_analyst, _call_writer, _call_critic, _call_reviser

    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content='{"missions": ["M1"], "verdict": "pass", "flaws": []}'))]

    with patch("cover_letter_crew.completion", return_value=mock_resp) as mock_comp:
        _call_analyst("Description", {"experiences": []})
        assert mock_comp.called
        assert "max_completion_tokens" in mock_comp.call_args.kwargs
        assert "max_tokens" not in mock_comp.call_args.kwargs
        assert mock_comp.call_args.kwargs["max_completion_tokens"] == 600

    with patch("cover_letter_crew.completion", return_value=mock_resp) as mock_comp:
        _call_writer({"missions": []}, "Company")
        assert mock_comp.called
        assert "max_completion_tokens" in mock_comp.call_args.kwargs
        assert "max_tokens" not in mock_comp.call_args.kwargs
        assert mock_comp.call_args.kwargs["max_completion_tokens"] == 2500

    with patch("cover_letter_crew.completion", return_value=mock_resp) as mock_comp:
        _call_critic("Lettre...", ["M1"])
        assert mock_comp.called
        assert "max_completion_tokens" in mock_comp.call_args.kwargs
        assert "max_tokens" not in mock_comp.call_args.kwargs
        assert mock_comp.call_args.kwargs["max_completion_tokens"] == 400

    with patch("cover_letter_crew.completion", return_value=mock_resp) as mock_comp:
        _call_reviser("Lettre...", {"missions": []}, ["Flaw 1"], {"violations": ["V1"]})
        assert mock_comp.called
        assert "max_completion_tokens" in mock_comp.call_args.kwargs
        assert "max_tokens" not in mock_comp.call_args.kwargs
        assert mock_comp.call_args.kwargs["max_completion_tokens"] == 2500


def test_call_analyst_prefers_explicit_candidate_name_over_contact_email():
    from cover_letter_crew import _call_analyst

    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content='{"missions": ["M1"]}'))]

    with patch("cover_letter_crew.completion", return_value=mock_resp):
        result = _call_analyst(
            "Description",
            {"experiences": [], "contact": {"email": "fallback@example.com"}},
            candidate_name="Jane Doe",
        )

    assert result["candidate_name"] == "Jane Doe"


def _fake_response(text: str) -> MagicMock:
    mock = MagicMock()
    mock.choices = [MagicMock(message=MagicMock(content=text))]
    return mock


def test_role_temperature_reaches_the_completion_call_for_standard_models(monkeypatch):
    from letter_llm import ROLE_TEMPERATURES
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return _fake_response("texte")

    monkeypatch.setenv("LETTER_MODEL_WRITER", "mistral/mistral-large-2407")
    monkeypatch.setattr(cover_letter_crew, "completion", fake_completion)
    cover_letter_crew._call_writer({"missions": []}, "Acme")
    assert captured["temperature"] == ROLE_TEMPERATURES["writer"]
    assert captured["drop_params"] is True


def test_role_temperature_omitted_for_reasoning_models(monkeypatch):
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return _fake_response("texte")

    monkeypatch.setenv("LETTER_MODEL_WRITER", "openai/gpt-5.6-terra")
    monkeypatch.setattr(cover_letter_crew, "completion", fake_completion)
    cover_letter_crew._call_writer({"missions": []}, "Acme")
    assert "temperature" not in captured
    assert captured["drop_params"] is True


def test_module_does_not_mutate_litellm_globally():
    source = open(cover_letter_crew.__file__, encoding="utf-8").read()
    assert "litellm.drop_params = True" not in source


def test_call_analyst_propagates_exception_instead_of_silent_fallback():
    # Une panne de l'analyste ne doit jamais retomber sur des missions
    # génériques factices : l'exception doit se propager telle quelle.
    with patch("cover_letter_crew.completion", side_effect=RuntimeError("panne fournisseur")):
        with pytest.raises(RuntimeError):
            cover_letter_crew._call_analyst("Description", {"experiences": []})


def test_call_critic_returns_explicit_error_object_on_failure():
    from cover_letter_crew import _call_critic

    with patch("cover_letter_crew.completion", side_effect=RuntimeError("panne critique")):
        result = _call_critic("Lettre...", ["M1"])

    assert result["verdict"] == "error"
    assert result["flaws"] == []
    assert result["role"] == "critic"
    assert result["detail"] == "panne critique"
    assert "provider" in result


def test_pipeline_triggers_revision_and_reports_provider_failure_on_critic_error():
    mock_analyst = {
        "missions": ["Lead data pipelines"],
        "selected_experiences": [],
        "stacks": [],
        "companies": [],
        "projects": [],
    }
    mock_writer_letter = "Lettre rédigée normalement..."
    mock_critic_error = {
        "verdict": "error",
        "flaws": [],
        "provider": "google",
        "role": "critic",
        "detail": "quota dépassé",
    }
    mock_revised_letter = "Lettre révisée après panne du critique..."

    with patch("cover_letter_crew._call_analyst", return_value=mock_analyst), \
         patch("cover_letter_crew._call_writer", return_value=mock_writer_letter), \
         patch("cover_letter_crew._call_critic", return_value=mock_critic_error), \
         patch("cover_letter_crew._call_reviser", return_value=mock_revised_letter) as mock_reviser, \
         patch("cover_letter_crew.validate_cross_provider"):

        result = run_letter_pipeline_sync(
            offer_description="Offre Acme",
            candidate_profile={"headline": "Data Engineer"},
            company_name="Acme",
        )

    assert mock_reviser.called
    assert result["revised"] is True
    assert result["body"] == mock_revised_letter
    assert result["provider_failures"] == [
        {"provider": "google", "role": "critic", "detail": "quota dépassé"}
    ]

