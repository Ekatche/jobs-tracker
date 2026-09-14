import pytest

from app.services.profile.periods import company_slug, is_open_ended, normalize_month


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Août 2025", "2025-08"),
        ("aout 2025", "2025-08"),
        ("Aug. 2025", "2025-08"),
        ("August 2025", "2025-08"),
        ("Sept 2021", "2021-09"),
        ("Fev 2023", "2023-02"),
        ("February 2023", "2023-02"),
        ("2022", "2022"),
        ("03/2021", "2021-03"),
        ("2021-03", "2021-03"),
        ("PRESENT", None),
        ("Present", None),
        ("en cours", None),
        ("", None),
        (None, None),
    ],
)
def test_normalize_month(raw, expected):
    assert normalize_month(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Agence Nile", "agence nile"),
        ("Agence Nile(Mauritius — International Assignment (VIE))", "agence nile"),
        ("AGENCE NILE, VIE - Ile Maurice", "agence nile"),
        ("Centre Léon Bérard", "centre leon berard"),
        ("CENTRE LEON BERARD, LYON", "centre leon berard"),
        ("Bimedoc  SAS", "bimedoc"),
        ("bioMérieux", "biomerieux"),
        ("Nodya Group(Lyon, France)", "nodya group"),
    ],
)
def test_company_slug(raw, expected):
    assert company_slug(raw) == expected


def test_is_open_ended():
    assert is_open_ended("PRESENT") is True
    assert is_open_ended("aujourd'hui") is True
    assert is_open_ended(None) is True
    assert is_open_ended("Aug. 2026") is False
