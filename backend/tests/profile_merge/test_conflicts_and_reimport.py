import pytest

from app.services.profile.merge import build_profile_from_sources
from tests.profile_merge.fixtures import (
    CV_V1_ORION,
    MANUAL_ORION_CORRECTION,
    experience,
)


def _by_company(profile, needle):
    return [e for e in profile["experiences"] if needle in e["company"].lower()]


def test_conflicting_dates_for_same_role_keep_priority_source_dates():
    """Même poste, débuts à un mois d'écart à cheval sur deux années : une seule expérience, dates du CV."""
    cv_start, website_start = "2021-12", "2022-01"
    cv = {"experiences": [experience("Orion Data", "Data Engineer", cv_start, "2024-06")]}
    website = {"experiences": [experience("Orion Data", "Data Engineer", website_start, "2024-09")]}
    profile, conflicts = build_profile_from_sources({"cv": cv, "website": website})
    assert len(profile["experiences"]) == 1
    exp = profile["experiences"][0]
    assert (exp["start"], exp["end"]) == (cv_start, "2024-06")
    # Contrat existant : seule la fin divergente est signalée comme conflit.
    end_conflicts = [c for c in conflicts if c["field"] == "end"]
    assert [(c["kept"], c["kept_source"]) for c in end_conflicts] == [("2024-06", "cv")]


@pytest.mark.parametrize(
    "variant",
    ["Societe Orion Data", "ORION DATA SAS", "Orion Data (Lyon, France)", "Orion-Data", "Orion Data Systems"],
)
def test_employer_wording_variants_of_same_role_are_merged(variant):
    cv = {"experiences": [experience("Orion Data SAS", "Data Engineer", "2022-03", "2024-06")]}
    website = {"experiences": [experience(variant, "Data Engineer", "2022-03", "2024-06")]}
    profile, _ = build_profile_from_sources({"cv": cv, "website": website})
    assert len(_by_company(profile, "orion")) == 1


@pytest.mark.parametrize(
    "first, second",
    [
        # Même employeur, deux postes successifs d'années différentes.
        (
            experience("Orion Data", "Data Analyst", "2019-01", "2020-12"),
            experience("Orion Data", "Data Engineer", "2021-01", None),
        ),
        # Employeurs différents, même intitulé et mêmes dates.
        (
            experience("Orion Data", "Data Engineer", "2022-03", "2024-06"),
            experience("Helios Conseil", "Data Engineer", "2022-03", "2024-06"),
        ),
    ],
)
def test_distinct_positions_are_never_merged(first, second):
    profile, _ = build_profile_from_sources(
        {"cv": {"experiences": [first]}, "website": {"experiences": [second]}}
    )
    assert len(profile["experiences"]) == 2


@pytest.mark.parametrize(
    "label, manual_start, cv_start",
    [
        ("Orion Data SAS", "2022-03", "2022-03"),
        ("ORION DATA", "2022-03", "2022-03"),
        ("Orion Data (Paris)", "2022-03", "2022-03"),
        ("Orion-Data", "2022-03", "2022-03"),
        ("Orion Data Systems", "2022-03", "2022-03"),
        ("Société Orion Data", "2022-03", "2022-03"),
        # La correction manual décale le début de 4 mois, à cheval sur deux années.
        ("Orion Data SAS", "2022-04", "2021-12"),
    ],
)
def test_manual_correction_survives_reimport_with_different_employer_label(label, manual_start, cv_start):
    cv_v2 = {
        "experiences": [
            experience(label, "Data Engineer", cv_start, "2024-06"),
            experience("Helios Conseil", "Analyste", "2020-01", "2021-12"),
        ]
    }
    manual = {"experiences": [experience("Orion Data", "Lead Data Engineer", manual_start, "2024-06")]}
    profile, _ = build_profile_from_sources({"cv": cv_v2, "manual": manual})
    orion = _by_company(profile, "orion")
    assert len(orion) == 1
    assert orion[0]["role"] == "Lead Data Engineer"  # la correction reste visible
    assert set(orion[0]["sources"]) == {"manual", "cv"}
    assert len(_by_company(profile, "helios")) == 1  # l'autre poste du CV v2 est là
    assert len(profile["experiences"]) == 2


def test_manual_correction_still_applies_before_and_after_reimport():
    before, _ = build_profile_from_sources({"cv": CV_V1_ORION, "manual": MANUAL_ORION_CORRECTION})
    cv_v2 = {"experiences": [experience("ORION DATA", "Ingenieur Data", "2022-03", "2024-06")]}
    after, _ = build_profile_from_sources({"cv": cv_v2, "manual": MANUAL_ORION_CORRECTION})
    assert _by_company(before, "orion")[0]["role"] == "Lead Data Engineer"
    assert _by_company(after, "orion")[0]["role"] == "Lead Data Engineer"
    assert len(_by_company(after, "orion")) == 1


def test_reimport_with_another_real_employer_does_not_swallow_correction():
    """Le libellé change au point de désigner un autre employeur : deux postes, pas de fusion."""
    cv_v2 = {"experiences": [experience("Helios Conseil", "Data Engineer", "2022-03", "2024-06")]}
    profile, _ = build_profile_from_sources({"cv": cv_v2, "manual": MANUAL_ORION_CORRECTION})
    assert len(profile["experiences"]) == 2
    orion = _by_company(profile, "orion")[0]
    assert orion["sources"] == ["manual"]
    assert orion["role"] == "Lead Data Engineer"
