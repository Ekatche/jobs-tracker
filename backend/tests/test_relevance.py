"""Tests unitaires du module de pertinence, sans DB ni fixture async.

Le module `app.services.relevance` est pur (aucun import de app.database,
motor, crewai ou openai) : ces tests s'exécutent sans conteneur Mongo.
"""

import pytest

from app.services.relevance import (
    contains_keyword,
    is_off_domain_url,
    is_relevant_position,
    normalize_text,
    RELEVANCE_KEYWORDS,
)


class TestNormalizeText:
    def test_accents_and_parentheses(self):
        assert normalize_text("Ingénieur(e) structure") == "ingenieur e structure"

    def test_hyphen(self):
        assert normalize_text("structures-metalliques") == "structures metalliques"


@pytest.mark.parametrize(
    "title,expected",
    [
        # Cas réels de production — postes hors-domaine rejetés à tort avant ce plan.
        ("Référent Bureau d'Études Acier (H/F)", False),
        ("Ingénieur Calcul de Structure (H/F)", False),
        ("Ingénieur(e) structure", False),
        ("Responsable Calculs Mécaniques Défense - Nucléaire (H/F)", False),
        ("Ingénieur calcul de structures métalliques et charpentes (H/F)", False),
        # Postes pertinents (data / IA / ML), doivent passer.
        ("Data analyste - CDD", True),
        ("Tech lead IA", True),
        ("Machine Learning Engineer", True),
        ("Ingénieur MLOps", True),
        ("Data Scientist Senior", True),
        # Titre vide.
        ("", False),
    ],
)
def test_is_relevant_position(title, expected):
    assert is_relevant_position(title) is expected


def test_word_boundary_no_false_positive_on_specialiste():
    """Régression la plus probable : "ia" ne doit pas matcher dans "spécialiste"."""
    assert is_relevant_position("Spécialiste sécurité") is False


@pytest.mark.parametrize(
    "url,expected",
    [
        (
            "https://candidat.francetravail.fr/offres/emploi/ingenieur-structures/lyon/s2m4v3",
            True,
        ),
        ("https://candidat.francetravail.fr/offres/recherche/detail/1234abc", False),
        ("https://fr.linkedin.com/jobs/view/data-scientist-at-acme-123", False),
        # L'allowlist gagne sur la blocklist : "data-scientist" l'emporte sur "mecanique".
        (
            "https://example.com/jobs/view/data-scientist-mecanique-des-fluides",
            False,
        ),
    ],
)
def test_is_off_domain_url(url, expected):
    assert is_off_domain_url(url) is expected


def test_host_does_not_influence_verdict():
    """data.gouv.fr ne doit pas être jugé pertinent uniquement via son host."""
    assert is_off_domain_url("https://data.gouv.fr/fr/datasets/genie-civil") is True


def test_contains_keyword_requires_word_boundary():
    # "ml" ne doit pas matcher à l'intérieur d'un autre mot.
    assert contains_keyword("hectomlitre", RELEVANCE_KEYWORDS) is False
    assert contains_keyword("Stage ML", RELEVANCE_KEYWORDS) is True
