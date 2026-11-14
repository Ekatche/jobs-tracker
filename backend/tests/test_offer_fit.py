import pytest

from app.models import BlocA, BlocG, PreferenceMismatch
from app.services.evaluation.offer_fit import (
    build_risk_summary,
    check_ai_buzzword_mismatch,
    check_employment_classification_risk,
    check_pay_range_width,
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


@pytest.mark.parametrize(
    "offer,expected_triggered",
    [
        ({"salaire": "$60,000 - $150,000", "description": ""}, True),
        ({"salaire": "45k - 80k€", "description": ""}, True),
        ({"salaire": None, "description": "Package prévu entre 60 000 € et 100 000 € selon profil."}, True),
        ({"salaire": "90 000 € - 110 000 €", "description": ""}, False),
        ({"salaire": None, "description": "Expérience souhaitée : 2 - 5 ans sur la période 2020 - 2024."}, False),
    ],
)
def test_check_pay_range_width(offer, expected_triggered):
    res = check_pay_range_width(offer)
    assert bool(res) is expected_triggered
    if res:
        assert "50 %" in res


@pytest.mark.parametrize(
    "offer,expected_triggered",
    [
        ({"type_contrat": "CDI", "description": "Statut indépendant / facturation mensuelle sur TJM."}, True),
        ({"type_contrat": "Non spécifié", "description": "Mission d'independent contractor (1099) sans congés."}, True),
        ({"type_contrat": "Freelance", "description": "Mission freelance avec congés payés et mutuelle."}, False),
        ({"type_contrat": "CDI", "description": "CDI classique avec RTT et mutuelle d'entreprise."}, False),
    ],
)
def test_check_employment_classification_risk(offer, expected_triggered):
    res = check_employment_classification_risk(offer)
    assert bool(res) is expected_triggered


@pytest.mark.parametrize(
    "offer,expected_triggered",
    [
        (
            {
                "poste": "Chargé de transformation IA junior",
                "description": "Piloter la transformation IA dans notre petite équipe de 3 personnes en logistique.",
            },
            True,
        ),
        (
            {
                "poste": "Lead MLOps Engineer",
                "description": "Industrialiser PyTorch, Kubernetes, MLflow et CI/CD pour les équipes data.",
            },
            False,
        ),
    ],
)
def test_check_ai_buzzword_mismatch(offer, expected_triggered):
    res = check_ai_buzzword_mismatch(offer)
    assert bool(res) is expected_triggered


def test_build_risk_summary_fixed_order_and_states():
    bloc_a = BlocA(preference_mismatches=[PreferenceMismatch(criterion="contrat", offer_value="CDD", expected="CDI")])
    bloc_g = BlocG(
        is_ghost_job=True,
        employment_classification_risk="mention « facturation »",
        pay_range_width_warning="écart > 50 %",
    )
    rows = build_risk_summary(bloc_a, bloc_g, {"salaire": "40k - 80k€"})
    assert [r.signal for r in rows] == [
        "Posting legitimacy",
        "Employment classification",
        "Pay range transparency",
        "AI claims vs. infrastructure",
        "Preference & domain fit",
    ]
    assert rows[0].status.startswith("⚠️")
    assert rows[1].status.startswith("⚠️")
    assert rows[2].status.startswith("⚠️")
    assert rows[3].status == "✅ consistent"
    assert rows[4].status.startswith("⚠️")
