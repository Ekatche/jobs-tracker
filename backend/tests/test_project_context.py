import pytest

from app.models import CandidateProject


@pytest.mark.parametrize("raw,expected", [
    ("Stage", "Stage"),
    ("  Freelance ", "Freelance"),
    ("Projet de fin d'études", "Projet de fin d'études"),
    ("client", "client"),
])
def test_candidate_project_keeps_free_text_context(raw, expected):
    assert CandidateProject(name="Projet", context=raw).context == expected


@pytest.mark.parametrize("raw", ["", "   ", None, 42, ["perso"]])
def test_candidate_project_empty_or_non_string_context_becomes_none(raw):
    assert CandidateProject(name="Projet", context=raw).context is None


def test_candidate_project_context_defaults_to_none():
    assert CandidateProject(name="Projet").context is None
