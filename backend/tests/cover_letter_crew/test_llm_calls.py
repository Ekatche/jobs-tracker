from unittest.mock import patch, MagicMock
import pytest

from tests.cover_letter_crew.fixtures import fake_response
import cover_letter_crew

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
        assert mock_comp.call_args.kwargs["max_completion_tokens"] == 4000

    with patch("cover_letter_crew.acompletion", return_value=mock_resp) as mock_comp:
        await _call_writer({"missions": []}, "Company")
        assert mock_comp.called
        assert "max_completion_tokens" in mock_comp.call_args.kwargs
        assert "max_tokens" not in mock_comp.call_args.kwargs
        assert mock_comp.call_args.kwargs["max_completion_tokens"] == 6000

    with patch("cover_letter_crew.acompletion", return_value=mock_resp) as mock_comp:
        await _call_critic("Lettre...", ["M1"])
        assert mock_comp.called
        assert "max_completion_tokens" in mock_comp.call_args.kwargs
        assert "max_tokens" not in mock_comp.call_args.kwargs
        assert mock_comp.call_args.kwargs["max_completion_tokens"] == 4000


    with patch("cover_letter_crew.acompletion", return_value=mock_resp) as mock_comp:
        await _call_reviser("Lettre...", {"missions": []}, ["Flaw 1"], {"violations": ["V1"]})
        assert mock_comp.called
        assert "max_completion_tokens" in mock_comp.call_args.kwargs
        assert "max_tokens" not in mock_comp.call_args.kwargs
        assert mock_comp.call_args.kwargs["max_completion_tokens"] == 6000


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


@pytest.mark.asyncio
@pytest.mark.parametrize("content,finish_reason", [
    ("", "stop"),
    (None, "stop"),
    ("Madame, Monsieur, je travaille aujourd'hui comme", "length"),
])
async def test_reviser_keeps_draft_when_output_is_empty_or_truncated(monkeypatch, content, finish_reason):
    # Un modèle à réflexion peut épuiser max_completion_tokens avant d'écrire :
    # une révision vide ou coupée ne doit jamais remplacer un brouillon complet.
    resp = MagicMock()
    resp.choices = [MagicMock(message=MagicMock(content=content), finish_reason=finish_reason)]

    async def fake_completion(**kwargs):
        return resp

    monkeypatch.setattr(cover_letter_crew, "acompletion", fake_completion)
    draft = "Brouillon complet de la lettre."
    result = await cover_letter_crew._call_reviser(draft, {"missions": []}, ["Flaw"], {"violations": ["V1"]})
    assert result == draft


@pytest.mark.asyncio
async def test_role_temperature_reaches_the_completion_call_for_standard_models(monkeypatch):
    from letter_llm import ROLE_TEMPERATURES
    captured = {}

    async def fake_completion(**kwargs):
        captured.update(kwargs)
        return fake_response("texte")

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
        return fake_response("texte")

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


def _unavailable():
    import litellm
    return litellm.ServiceUnavailableError(
        message="This model is currently experiencing high demand.",
        llm_provider="vertex_ai",
        model="gemini/gemini-3.8-flash",
    )


@pytest.mark.asyncio
async def test_acompletion_retry_waits_through_transient_503(monkeypatch):
    sleeps = []

    async def fake_sleep(delay):
        sleeps.append(delay)

    ok = MagicMock()
    calls = {"n": 0}

    async def flaky(**kwargs):
        calls["n"] += 1
        if calls["n"] < 3:
            raise _unavailable()
        return ok

    monkeypatch.setattr(cover_letter_crew.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(cover_letter_crew, "acompletion", flaky)

    assert await cover_letter_crew._acompletion_retry(model="gemini/gemini-3.8-flash") is ok
    assert calls["n"] == 3
    assert sleeps == list(cover_letter_crew.LLM_RETRY_DELAYS[:2])


@pytest.mark.asyncio
async def test_acompletion_retry_gives_up_and_skips_non_transient(monkeypatch):
    import litellm

    async def fake_sleep(delay):
        pass

    async def always_down(**kwargs):
        raise _unavailable()

    monkeypatch.setattr(cover_letter_crew.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(cover_letter_crew, "acompletion", always_down)
    with pytest.raises(litellm.ServiceUnavailableError):
        await cover_letter_crew._acompletion_retry(model="gemini/gemini-3.8-flash")

    calls = {"n": 0}

    async def broken(**kwargs):
        calls["n"] += 1
        raise ValueError("réponse invalide")

    monkeypatch.setattr(cover_letter_crew, "acompletion", broken)
    with pytest.raises(ValueError):
        await cover_letter_crew._acompletion_retry(model="gemini/gemini-3.8-flash")
    assert calls["n"] == 1


@pytest.mark.parametrize("raw, expected", [
    ("eliel Katche", "Eliel Katche"),
    ("jean de la fontaine", "Jean de la Fontaine"),
    ("marie-claire dupont", "Marie-Claire Dupont"),
    ("Anne McDonald", "Anne McDonald"),
    ("", ""),
])
def test_format_person_name_capitalizes_lowercase_parts(raw, expected):
    assert cover_letter_crew._format_person_name(raw) == expected
