import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

# Ensure job_trackers is in sys.path
job_trackers_path = Path(__file__).resolve().parent.parent / "job_trackers" / "src" / "job_trackers"
if str(job_trackers_path) not in sys.path:
    sys.path.insert(0, str(job_trackers_path))

import cover_letter_crew
from cover_letter_crew import (
    RewriteFailedError,
    _preserve_outer_whitespace,
    _strip_wrapping_quotes,
    _is_wrapped_in_quotes,
    detect_new_numbers,
    rewrite_letter_passage_async,
    load_prompt,
)

from main import app
from app.auth import get_current_user
from app.database import get_database
from app.models import ApiUsageAction, UserModel


@pytest.fixture(autouse=True)
def _clean_dependency_overrides():
    """Ensure dependency overrides do not leak between test files."""
    snapshot = dict(app.dependency_overrides)
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(snapshot)


MOCK_USER_ID = "60c72b2f9b1d8b2bad7f9999"
mock_current_user = UserModel(
    id=MOCK_USER_ID,
    username="testengineer",
    full_name="Jean Dupont",
    email="jean.dupont@example.com",
    hashed_password="pw",
)


# ==============================================================================
# Unit tests: helpers and algorithms
# ==============================================================================


def test_detect_new_numbers():
    letter = (
        "Durant mes 2,5 années chez Biomérieux, j'ai piloté 1 000 pipelines "
        "et généré +30 % de gain de performance avec une équipe de 10 personnes."
    )

    # All these numbers exist in the letter (accounting for normalized formatting):
    # 1 000 == 1000, 30 % == 30%, 2,5 == 2.5
    rewritten_clean = (
        "Chez Biomérieux pendant 2.5 ans, j'ai optimisé 1000 pipelines pour un gain de 30%."
    )
    assert detect_new_numbers(letter, rewritten_clean) == []

    # 40 % is NOT in the letter:
    rewritten_hallucinated = "J'ai amélioré le rendement de 40 % sur les pipelines."
    warnings = detect_new_numbers(letter, rewritten_hallucinated)
    assert len(warnings) == 1
    assert "40 %" in warnings[0] or "40%" in warnings[0]


def test_rewrite_preserves_outer_whitespace():
    # DoD: passage "Phrase.\n\n" -> texte réécrit terminé par "\n\n"
    assert _preserve_outer_whitespace("Phrase.\n\n", "Phrase réécrite.") == "Phrase réécrite.\n\n"
    assert _preserve_outer_whitespace("  Phrase.  ", "Phrase réécrite.") == "  Phrase réécrite.  "
    assert _preserve_outer_whitespace("\n\tPhrase.", "Phrase réécrite.") == "\n\tPhrase réécrite."
    assert _preserve_outer_whitespace("Phrase.", "Phrase réécrite.") == "Phrase réécrite."


def test_rewrite_strips_wrapping_quotes_only_if_passage_unquoted():
    # 1. Unquoted original passage: LLM wrapping quotes should be stripped
    unquoted_passage = "Je souhaite vivement rejoindre votre équipe."
    llm_output_double = '"Je souhaite vivement intégrer vos équipes."'
    llm_output_guillemets = "« Je souhaite vivement intégrer vos équipes. »"
    llm_output_curly = "“Je souhaite vivement intégrer vos équipes.”"

    assert not _is_wrapped_in_quotes(unquoted_passage)
    assert _strip_wrapping_quotes(llm_output_double) == "Je souhaite vivement intégrer vos équipes."
    assert _strip_wrapping_quotes(llm_output_guillemets) == "Je souhaite vivement intégrer vos équipes."
    assert _strip_wrapping_quotes(llm_output_curly) == "Je souhaite vivement intégrer vos équipes."

    # 2. Quoted original passage: quotes should be kept
    quoted_passage = '« Citation inspirante »'
    assert _is_wrapped_in_quotes(quoted_passage)


def test_rewrite_prompt_renders_inputs():
    rendered = load_prompt(
        "05_rewrite_passage",
        letter_text="Lettre de motivation complète ici.",
        passage="Passage sélectionné.",
        instruction="Rendre plus concis.",
    )
    assert "Lettre de motivation complète ici." in rendered
    assert "Passage sélectionné." in rendered
    assert "Rendre plus concis." in rendered
    # No orphan template braces left unrendered
    assert "{" not in rendered
    assert "}" not in rendered


# ==============================================================================
# API tests: POST /applications/{id}/cover-letter/rewrite
# ==============================================================================


def test_rewrite_invalid_id(client):
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    res = client.post(
        "/applications/not-a-valid-object-id/cover-letter/rewrite",
        json={"letter": "Texte", "passage": "Texte", "instruction": ""},
    )
    assert res.status_code == 400
    assert "invalide" in res.json()["detail"].lower()


def test_rewrite_forbidden(client):
    app_id = ObjectId()
    other_user_id = ObjectId()

    apps_coll = MagicMock()
    apps_coll.find_one = AsyncMock(return_value={"_id": app_id, "user_id": other_user_id})

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda k: apps_coll if k == "applications" else MagicMock()

    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_database] = lambda: mock_db

    res = client.post(
        f"/applications/{app_id}/cover-letter/rewrite",
        json={"letter": "Texte", "passage": "Texte", "instruction": ""},
    )
    assert res.status_code == 403
    assert "non autorisé" in res.json()["detail"].lower()


def test_rewrite_passage_not_in_letter(client):
    app_id = ObjectId()

    apps_coll = MagicMock()
    apps_coll.find_one = AsyncMock(return_value={"_id": app_id, "user_id": ObjectId(MOCK_USER_ID)})

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda k: apps_coll if k == "applications" else MagicMock()

    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_database] = lambda: mock_db

    res = client.post(
        f"/applications/{app_id}/cover-letter/rewrite",
        json={"letter": "Voici toute la lettre.", "passage": "Passage imaginaire absent", "instruction": ""},
    )
    assert res.status_code == 422
    assert "absent" in res.json()["detail"].lower()


def test_rewrite_validation(client):
    app_id = ObjectId()

    apps_coll = MagicMock()
    apps_coll.find_one = AsyncMock(return_value={"_id": app_id, "user_id": ObjectId(MOCK_USER_ID)})

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda k: apps_coll if k == "applications" else MagicMock()

    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_database] = lambda: mock_db

    # 1. Whitespace only passage
    res = client.post(
        f"/applications/{app_id}/cover-letter/rewrite",
        json={"letter": "Voici la lettre.", "passage": "   ", "instruction": ""},
    )
    assert res.status_code == 422

    # 2. Passage too long (> 2000 chars)
    res = client.post(
        f"/applications/{app_id}/cover-letter/rewrite",
        json={"letter": "A" * 3000, "passage": "A" * 2005, "instruction": ""},
    )
    assert res.status_code == 422

    # 3. Letter too long (> 8000 chars)
    res = client.post(
        f"/applications/{app_id}/cover-letter/rewrite",
        json={"letter": "A" * 8005, "passage": "A", "instruction": ""},
    )
    assert res.status_code == 422


def test_rewrite_records_usage(client):
    app_id = ObjectId()

    apps_coll = MagicMock()
    apps_coll.find_one = AsyncMock(return_value={"_id": app_id, "user_id": ObjectId(MOCK_USER_ID)})

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda k: apps_coll if k == "applications" else MagicMock()

    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_database] = lambda: mock_db

    letter = "Madame, Monsieur,\n\nJe postule avec grand intérêt.\n\nCordialement."
    passage = "Je postule avec grand intérêt.\n\n"

    mock_resp = MagicMock()
    mock_resp.choices = [
        MagicMock(message=MagicMock(content="Je vous propose ma candidature avec enthousiasme."), finish_reason="stop")
    ]
    mock_resp.usage = MagicMock(prompt_tokens=150, completion_tokens=30)

    with patch.object(cover_letter_crew, "_acompletion_retry", new=AsyncMock(return_value=mock_resp)), \
         patch("app.routers.cover_letters.record_api_usage", new=AsyncMock()) as mock_record_usage:

        res = client.post(
            f"/applications/{app_id}/cover-letter/rewrite",
            json={"letter": letter, "passage": passage, "instruction": "Plus dynamique"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["rewritten"] == "Je vous propose ma candidature avec enthousiasme.\n\n"
        assert data["warnings"] == []

        # Check usage recording was called with LETTER_REWRITE
        mock_record_usage.assert_awaited_once()
        call_kwargs = mock_record_usage.await_args.kwargs
        call_args = mock_record_usage.await_args.args
        action = call_kwargs.get("action") or (call_args[2] if len(call_args) > 2 else None)
        assert action == ApiUsageAction.LETTER_REWRITE
        assert call_kwargs.get("input_tokens") == 150
        assert call_kwargs.get("output_tokens") == 30


def test_rewrite_empty_output_returns_502(client):
    app_id = ObjectId()

    apps_coll = MagicMock()
    apps_coll.find_one = AsyncMock(return_value={"_id": app_id, "user_id": ObjectId(MOCK_USER_ID)})

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda k: apps_coll if k == "applications" else MagicMock()

    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_database] = lambda: mock_db

    letter = "Madame, Monsieur,\n\nJe postule avec grand intérêt.\n\nCordialement."
    passage = "Je postule avec grand intérêt."

    # 1. Empty content -> 502, no usage recorded
    mock_resp_empty = MagicMock()
    mock_resp_empty.choices = [MagicMock(message=MagicMock(content=""), finish_reason="stop")]
    mock_resp_empty.usage = MagicMock(prompt_tokens=100, completion_tokens=0)

    with patch.object(cover_letter_crew, "_acompletion_retry", new=AsyncMock(return_value=mock_resp_empty)), \
         patch("app.routers.cover_letters.record_api_usage", new=AsyncMock()) as mock_record_usage:

        res = client.post(
            f"/applications/{app_id}/cover-letter/rewrite",
            json={"letter": letter, "passage": passage, "instruction": ""},
        )
        assert res.status_code == 502
        assert "La réécriture n'a pas abouti" in res.json()["detail"]
        mock_record_usage.assert_not_called()

    # 2. Truncated output (finish_reason == "length") -> 502, no usage recorded
    mock_resp_length = MagicMock()
    mock_resp_length.choices = [MagicMock(message=MagicMock(content="Tronqué"), finish_reason="length")]
    mock_resp_length.usage = MagicMock(prompt_tokens=100, completion_tokens=50)

    with patch.object(cover_letter_crew, "_acompletion_retry", new=AsyncMock(return_value=mock_resp_length)), \
         patch("app.routers.cover_letters.record_api_usage", new=AsyncMock()) as mock_record_usage:

        res = client.post(
            f"/applications/{app_id}/cover-letter/rewrite",
            json={"letter": letter, "passage": passage, "instruction": ""},
        )
        assert res.status_code == 502
        assert "La réécriture n'a pas abouti" in res.json()["detail"]
        mock_record_usage.assert_not_called()
