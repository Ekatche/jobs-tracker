"""Fixtures communes : jeu de référence et PDF générés une fois par session (hors réseau)."""
import pytest

from scripts.cv_reference_pdfs import generate_cases, load_cases
from scripts.reference_dataset import load_reference


@pytest.fixture(scope="session")
def reference():
    return load_reference()


@pytest.fixture(scope="session")
def cases():
    return load_cases()


@pytest.fixture(scope="session")
def generated(tmp_path_factory, cases, reference):
    out_dir = tmp_path_factory.mktemp("cv_reference")
    return {"out_dir": out_dir, "manifest": generate_cases(cases, reference, out_dir)}


@pytest.fixture
def entry(generated):
    """Entrée du manifeste par ``case_id``."""
    by_id = {e["case_id"]: e for e in generated["manifest"]}
    return by_id.__getitem__
