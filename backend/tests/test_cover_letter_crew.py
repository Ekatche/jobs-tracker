import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

# Ensure job_trackers source is importable
job_trackers_path = Path(__file__).parent.parent / "job_trackers" / "src" / "job_trackers"
if str(job_trackers_path) not in sys.path:
    sys.path.insert(0, str(job_trackers_path))

import cover_letter_crew
from cover_letter_crew import run_letter_pipeline_async

@pytest.mark.asyncio
async def test_pipeline_executes_revision_when_critic_requests():
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

        result = await run_letter_pipeline_async(
            offer_description="Offre Biomérieux Lead Data",
            candidate_profile={"headline": "Data Engineer"},
            company_name="Biomérieux"
        )

        assert result["body"] == mock_revised_letter
        assert result["revised"] is True
        assert result["critic_verdict"]["verdict"] == "revise"

@pytest.mark.asyncio
async def test_completion_uses_max_completion_tokens():
    from cover_letter_crew import _call_analyst, _call_writer, _call_critic, _call_reviser

    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content='{"missions": ["M1"], "verdict": "pass", "flaws": []}'))]

    with patch("cover_letter_crew.acompletion", return_value=mock_resp) as mock_comp:
        await _call_analyst("Description", {"experiences": []})
        assert mock_comp.called
        assert "max_completion_tokens" in mock_comp.call_args.kwargs
        assert "max_tokens" not in mock_comp.call_args.kwargs
        assert mock_comp.call_args.kwargs["max_completion_tokens"] == 1500

    with patch("cover_letter_crew.acompletion", return_value=mock_resp) as mock_comp:
        await _call_writer({"missions": []}, "Company")
        assert mock_comp.called
        assert "max_completion_tokens" in mock_comp.call_args.kwargs
        assert "max_tokens" not in mock_comp.call_args.kwargs
        assert mock_comp.call_args.kwargs["max_completion_tokens"] == 2500

    with patch("cover_letter_crew.acompletion", return_value=mock_resp) as mock_comp:
        await _call_critic("Lettre...", ["M1"])
        assert mock_comp.called
        assert "max_completion_tokens" in mock_comp.call_args.kwargs
        assert "max_tokens" not in mock_comp.call_args.kwargs
        assert mock_comp.call_args.kwargs["max_completion_tokens"] == 1000


    with patch("cover_letter_crew.acompletion", return_value=mock_resp) as mock_comp:
        await _call_reviser("Lettre...", {"missions": []}, ["Flaw 1"], {"violations": ["V1"]})
        assert mock_comp.called
        assert "max_completion_tokens" in mock_comp.call_args.kwargs
        assert "max_tokens" not in mock_comp.call_args.kwargs
        assert mock_comp.call_args.kwargs["max_completion_tokens"] == 2500


@pytest.mark.asyncio
async def test_call_analyst_prefers_explicit_candidate_name_over_contact_email():
    from cover_letter_crew import _call_analyst

    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content='{"missions": ["M1"]}'))]

    with patch("cover_letter_crew.acompletion", return_value=mock_resp):
        result = await _call_analyst(
            "Description",
            {"experiences": [], "contact": {"email": "fallback@example.com"}},
            candidate_name="Jane Doe",
        )

    assert result["candidate_name"] == "Jane Doe"


@pytest.mark.asyncio
async def test_call_analyst_never_uses_email_as_candidate_name():
    from cover_letter_crew import _call_analyst

    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content='{"missions": ["M1"]}'))]

    with patch("cover_letter_crew.acompletion", return_value=mock_resp):
        result = await _call_analyst(
            "Description",
            {"experiences": [], "contact": {"email": "fallback@example.com"}},
        )

    assert result["candidate_name"] == ""


def _fake_response(text: str) -> MagicMock:
    mock = MagicMock()
    mock.choices = [MagicMock(message=MagicMock(content=text))]
    return mock


@pytest.mark.asyncio
async def test_role_temperature_reaches_the_completion_call_for_standard_models(monkeypatch):
    from letter_llm import ROLE_TEMPERATURES
    captured = {}

    async def fake_completion(**kwargs):
        captured.update(kwargs)
        return _fake_response("texte")

    monkeypatch.setenv("LETTER_MODEL_WRITER", "mistral/mistral-large-2407")
    monkeypatch.setattr(cover_letter_crew, "acompletion", fake_completion)
    await cover_letter_crew._call_writer({"missions": []}, "Acme")
    assert captured["temperature"] == ROLE_TEMPERATURES["writer"]
    assert captured["drop_params"] is True


@pytest.mark.asyncio
async def test_role_temperature_omitted_for_reasoning_models(monkeypatch):
    captured = {}

    async def fake_completion(**kwargs):
        captured.update(kwargs)
        return _fake_response("texte")

    monkeypatch.setenv("LETTER_MODEL_WRITER", "openai/gpt-5.6-terra")
    monkeypatch.setattr(cover_letter_crew, "acompletion", fake_completion)
    await cover_letter_crew._call_writer({"missions": []}, "Acme")
    assert "temperature" not in captured
    assert captured["drop_params"] is True


def test_module_does_not_mutate_litellm_globally():
    source = open(cover_letter_crew.__file__, encoding="utf-8").read()
    assert "litellm.drop_params = True" not in source


@pytest.mark.asyncio
async def test_call_analyst_propagates_exception_instead_of_silent_fallback():
    # Une panne de l'analyste ne doit jamais retomber sur des missions
    # génériques factices : l'exception doit se propager telle quelle.
    with patch("cover_letter_crew.acompletion", side_effect=RuntimeError("panne fournisseur")):
        with pytest.raises(RuntimeError):
            await cover_letter_crew._call_analyst("Description", {"experiences": []})


@pytest.mark.asyncio
async def test_call_critic_returns_explicit_error_object_on_failure():
    from cover_letter_crew import _call_critic

    with patch("cover_letter_crew.acompletion", side_effect=RuntimeError("panne critique")):
        result = await _call_critic("Lettre...", ["M1"])

    assert result["verdict"] == "error"
    assert result["flaws"] == []
    assert result["role"] == "critic"
    assert result["detail"] == "panne critique"
    assert "provider" in result


@pytest.mark.asyncio
async def test_pipeline_triggers_revision_and_reports_provider_failure_on_critic_error():
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

        result = await run_letter_pipeline_async(
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


@pytest.mark.asyncio
async def test_company_research_failure_does_not_break_pipeline():
    mock_analyst = {
        "missions": ["Lead data pipelines"],
        "selected_experiences": [],
        "stacks": [],
        "companies": [],
        "projects": [],
    }
    mock_writer_letter = "Lettre générée malgré l'erreur..."

    with patch("cover_letter_crew._call_analyst", return_value=mock_analyst), \
         patch("cover_letter_crew._search_company_web", side_effect=Exception("Tavily unreachable")), \
         patch("cover_letter_crew._call_writer", return_value=mock_writer_letter), \
         patch("cover_letter_crew._call_critic", return_value={"verdict": "pass", "flaws": []}), \
         patch("cover_letter_crew.evaluate_letter_guards") as mock_guards, \
         patch("cover_letter_crew.validate_cross_provider"):

        mock_guard_report = MagicMock()
        mock_guard_report.is_blocking = False
        mock_guards.return_value = mock_guard_report

        result = await run_letter_pipeline_async(
            offer_description="Offre Acme",
            candidate_profile={"headline": "Data Engineer"},
            company_name="Acme",
        )

    assert result.get("body") == mock_writer_letter


@pytest.mark.asyncio
async def test_writer_prompt_includes_voice_style_when_present():
    mock_choice = MagicMock()
    mock_choice.message.content = "Lettre générée"
    mock_resp = MagicMock(choices=[mock_choice], usage=None)

    with patch("cover_letter_crew.acompletion", return_value=mock_resp) as mock_comp, \
         patch("cover_letter_crew.get_letter_llm") as mock_llm:
        mock_llm.return_value.model = "openai/gpt-5.6-terra"
        mock_llm.return_value.api_key = "fake_key"

        analyst_json = {
            "candidate_name": "Alice",
            "candidate_headline": "ML Engineer",
            "missions": ["Mission 1"],
            "selected_experiences": [],
            "stacks": ["Python"],
            "projects": [],
        }

        await cover_letter_crew._call_writer(
            analyst_json=analyst_json,
            company_name="Acme",
            voice_style="Direct, phrases courtes, pas de jargon marketing.",
        )

        assert mock_comp.called
        sent_messages = mock_comp.call_args[1]["messages"]
        sent_prompt = sent_messages[0]["content"]
        assert "Direct, phrases courtes, pas de jargon marketing." in sent_prompt


@pytest.mark.asyncio
async def test_writer_prompt_includes_writing_samples_when_present():
    mock_choice = MagicMock()
    mock_choice.message.content = "Lettre générée"
    mock_resp = MagicMock(choices=[mock_choice], usage=None)

    with patch("cover_letter_crew.acompletion", return_value=mock_resp) as mock_comp, \
         patch("cover_letter_crew.get_letter_llm") as mock_llm:
        mock_llm.return_value.model = "openai/gpt-5.6-terra"
        mock_llm.return_value.api_key = "fake_key"

        await cover_letter_crew._call_writer(
            analyst_json={"candidate_name": "Alice", "missions": [], "stacks": [], "projects": []},
            company_name="Acme",
            writing_samples="Je travaille depuis deux ans sur des outils internes.",
        )

        sent_prompt = mock_comp.call_args[1]["messages"][0]["content"]
        assert "<exemples_du_candidat>" in sent_prompt
        assert "Je travaille depuis deux ans sur des outils internes." in sent_prompt


def test_voice_style_block_truncates_long_samples():
    block = cover_letter_crew._build_voice_style_block("", "a" * 10000)
    assert "a" * cover_letter_crew.WRITING_SAMPLES_MAX_CHARS in block
    assert "a" * (cover_letter_crew.WRITING_SAMPLES_MAX_CHARS + 1) not in block


def test_voice_style_block_empty_when_nothing_provided():
    assert cover_letter_crew._build_voice_style_block("", "") == ""


@pytest.mark.asyncio
async def test_reviser_prompt_includes_letter_and_analysis_data():
    mock_choice = MagicMock()
    mock_choice.message.content = "Lettre révisée"
    mock_resp = MagicMock(choices=[mock_choice], usage=None)

    with patch("cover_letter_crew.acompletion", return_value=mock_resp) as mock_comp, \
         patch("cover_letter_crew.get_letter_llm") as mock_llm:
        mock_llm.return_value.model = "openai/gpt-5.6-terra"
        mock_llm.return_value.api_key = "fake_key"

        letter_text = "Madame, Monsieur, voici ma candidature chez Acme..."
        analyst_json = {
            "missions": ["Optimiser les pipelines BigQuery"],
            "selected_experiences": [{"company": "DataCorp"}],
        }
        critic_flaws = ["Accroche trop générique"]
        guard_report = {"violations": ["Point d'exclamation interdit"]}

        revised = await cover_letter_crew._call_reviser(
            letter_text=letter_text,
            analyst_json=analyst_json,
            critic_flaws=critic_flaws,
            guard_report=guard_report,
        )

        assert revised == "Lettre révisée"
        assert mock_comp.called
        sent_prompt = mock_comp.call_args[1]["messages"][0]["content"]
        assert "Madame, Monsieur, voici ma candidature chez Acme..." in sent_prompt
        assert "Optimiser les pipelines BigQuery" in sent_prompt
        assert "Accroche trop générique" in sent_prompt
        assert "Point d'exclamation interdit" in sent_prompt


