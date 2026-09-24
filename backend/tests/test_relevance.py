"""Tests unitaires du module de pertinence, sans DB ni fixture async.

Le module `app.services.relevance` est pur (aucun import de app.database,
motor, crewai ou openai) : ces tests s'exécutent sans conteneur Mongo.
"""

import pytest

from app.services.relevance import (
    contains_keyword,
    is_off_domain_url,
    normalize_text,
    RELEVANCE_KEYWORDS,
)


class TestNormalizeText:
    def test_accents_and_parentheses(self):
        assert normalize_text("Ingénieur(e) structure") == "ingenieur e structure"

    def test_hyphen(self):
        assert normalize_text("structures-metalliques") == "structures metalliques"


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


from app.services.relevance import parse_source_query


@pytest.mark.parametrize(
    "query,expected",
    [
        (
            "Je recherche un poste de Animatrice permanente proche de bourgoin-jallieu (CDI)",
            ("Animatrice permanente", "bourgoin-jallieu"),
        ),
        ("Je recherche un poste d'ingénieur MLOps proche de Lyon", ("ingénieur MLOps", "Lyon")),
        ("Je recherche un poste de Data Engineer en télétravail (CDI)", ("Data Engineer", None)),
        ("Je recherche un poste de Data Engineer", ("Data Engineer", None)),
        ("Je recherche un poste proche de Lyon (CDI)", (None, None)),
        ("", (None, None)),
    ],
)
def test_parse_source_query(query, expected):
    assert parse_source_query(query) == expected

