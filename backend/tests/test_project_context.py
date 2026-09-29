import pytest

from app.models import PROJECT_CONTEXTS, CandidateProject, normalize_project_context


def test_project_contexts_lists_the_six_values():
    assert set(PROJECT_CONTEXTS) == {
        "perso", "client", "recherche", "consortium", "associatif", "evenement",
    }


@pytest.mark.parametrize("raw,expected", [
    ("associatif", "associatif"),
    ("Association", "associatif"),
    ("asso", "associatif"),
    ("Bénévolat", "associatif"),
    ("benevolat", "associatif"),
    ("volunteer", "associatif"),
    ("evenement", "evenement"),
    ("Événement", "evenement"),
    ("event", "evenement"),
    ("salon", "evenement"),
    ("  Client ", "client"),
    ("research", "recherche"),
    ("consortium", "consortium"),
    ("personal", "perso"),
])
def test_normalize_project_context_maps_synonyms(raw, expected):
    assert normalize_project_context(raw) == expected


@pytest.mark.parametrize("raw", ["stage", "freelance", "", None, 42])
def test_normalize_project_context_falls_back_to_perso(raw):
    assert normalize_project_context(raw) == "perso"


def test_candidate_project_accepts_new_contexts():
    assert CandidateProject(name="Forum emploi", context="Événement").context == "evenement"
    assert CandidateProject(name="Restos du cœur", context="bénévolat").context == "associatif"
