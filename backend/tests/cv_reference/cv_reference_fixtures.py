"""Fixtures communes du banc : jeu de référence et PDF générés hors réseau.

Module au nom unique (un `conftest` ici masquerait celui de tests/). Importées explicitement :
chaque module qui les importe les construit une fois (scope session par module, pas global).
"""
import socket

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


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Preuve qu'aucun appel réseau ne part pendant les tests du banc."""

    def refuse(self, *args, **kwargs):
        raise AssertionError("connexion réseau interdite dans les tests du banc")

    monkeypatch.setattr(socket.socket, "connect", refuse)
