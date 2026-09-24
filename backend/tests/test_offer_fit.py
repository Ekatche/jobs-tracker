import pytest

from app.services.evaluation.offer_fit import (
    check_preference_fit,
    normalize_contract,
    offer_quality_warnings,
    parse_annual_salary_max,
)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("CDI", "cdi"),
        ("CDII", "cdi"),
        ("Contrat à durée indéterminée (permanent)", "cdi"),
        ("CDD 6 mois", "cdd"),
        ("Freelance / portage", "freelance"),
        ("Alternance", "alternance"),
        ("Stage", "stage"),
        ("Intérim", "interim"),
        ("Non spécifié", None),
        (None, None),
    ],
)
def test_normalize_contract(value, expected):
    assert normalize_contract(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("35 000 - 42 000 € / an", 42000),
        ("45k€", None),
        ("Mensuel de 2 100,00 Euros à 2 300,00 Euros sur 12 mois", 27600),
        ("Annuel de 38000.00 Euros", 38000),
        ("Selon profil", None),
        (None, None),
    ],
)
def test_parse_annual_salary_max(value, expected):
    assert parse_annual_salary_max(value) == expected


PREFS = {"contract_types": ["CDI", "Freelance"], "seniority_levels": ["junior", "mid"], "min_salary": 40000}


def test_preference_fit_no_mismatch():
    offer = {"type_contrat": "CDI", "seniority_level": "mid", "salaire": "40 000 - 48 000 €"}
    assert check_preference_fit(offer, PREFS) == []


def test_preference_fit_contract_mismatch_is_high():
    [mismatch] = check_preference_fit({"type_contrat": "CDD"}, PREFS)
    assert (mismatch.criterion, mismatch.weight) == ("contrat", "high")


@pytest.mark.parametrize("level,weight", [("senior", "meaningful"), ("lead", "high"), ("intern", "meaningful")])
def test_preference_fit_seniority_weight_by_distance(level, weight):
    [mismatch] = check_preference_fit({"seniority_level": level}, PREFS)
    assert (mismatch.criterion, mismatch.weight) == ("séniorité", weight)


def test_preference_fit_salary_below_minimum():
    [mismatch] = check_preference_fit({"salaire": "Mensuel de 2 500 Euros"}, PREFS)
    assert (mismatch.criterion, mismatch.weight) == ("salaire", "high")


def test_preference_fit_missing_field_is_not_a_mismatch():
    offer = {"type_contrat": "Non spécifié", "seniority_level": None, "salaire": None}
    assert check_preference_fit(offer, PREFS) == []
    assert check_preference_fit({"type_contrat": "CDD", "seniority_level": "lead"}, {}) == []


def test_offer_quality_warnings():
    long_offer = {"description": "x" * 600}
    assert offer_quality_warnings(long_offer, 1) == []

    warnings = offer_quality_warnings({"description": "Court."}, 2)
    assert len(warnings) == 2
    assert "publiée 2 fois" in warnings[0]
    assert "Description courte (6 caractères)" in warnings[1]
