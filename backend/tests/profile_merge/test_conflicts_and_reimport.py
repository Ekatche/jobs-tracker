import pytest

from app.services.profile.merge import build_profile_from_sources
from tests.profile_merge.fixtures import (
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
    "cv_exp, other_source, other_exp",
    [
        # Même employeur, deux postes successifs d'années différentes.
        (
            experience("Orion Data", "Data Analyst", "2019-01", "2020-12"),
            "website",
            experience("Orion Data", "Data Engineer", "2021-01", None),
        ),
        # Employeurs différents, même intitulé et mêmes dates.
        (
            experience("Orion Data", "Data Engineer", "2022-03", "2024-06"),
            "website",
            experience("Helios Conseil", "Data Engineer", "2022-03", "2024-06"),
        ),
        # Fin absente côté CV : « en cours » ne doit pas faire chevaucher une promotion.
        (
            experience("Orion Data", "Data Analyst", "2019-01", None),
            "website",
            experience("Orion Data", "Senior Data Engineer", "2021-03", None),
        ),
        # Le réimport CV désigne un autre employeur réel : la correction manual n'est pas avalée.
        (
            experience("Helios Conseil", "Data Engineer", "2022-03", "2024-06"),
            "manual",
            MANUAL_ORION_CORRECTION["experiences"][0],
        ),
    ],
)
def test_distinct_positions_are_never_merged(cv_exp, other_source, other_exp):
    profile, _ = build_profile_from_sources(
        {"cv": {"experiences": [cv_exp]}, other_source: {"experiences": [other_exp]}}
    )
    assert len(profile["experiences"]) == 2
    assert {tuple(e["sources"]) for e in profile["experiences"]} == {("cv",), (other_source,)}


@pytest.mark.parametrize(
    "label, manual_start, cv_start, manual_has_helios",
    [
        ("Orion Data SAS", "2022-03", "2022-03", False),
        ("ORION DATA", "2022-03", "2022-03", False),
        ("Orion Data (Paris)", "2022-03", "2022-03", False),
        ("Orion-Data", "2022-03", "2022-03", False),
        ("Orion Data Systems", "2022-03", "2022-03", False),
        ("Société Orion Data", "2022-03", "2022-03", False),
        # La correction manual décale le début de 4 mois, à cheval sur deux années.
        ("Orion Data SAS", "2022-04", "2021-12", False),
        # Instantané manual complet : il contient aussi Helios, qui ne doit pas être dupliqué.
        ("Orion Data SAS", "2022-03", "2022-03", True),
    ],
)
def test_manual_correction_survives_reimport_with_different_employer_label(
    label, manual_start, cv_start, manual_has_helios
):
    cv_v2 = {
        "experiences": [
            experience(label, "Data Engineer", cv_start, "2024-06"),
            experience("Helios Conseil", "Analyste", "2020-01", "2021-12"),
        ]
    }
    manual_exps = [experience("Orion Data", "Lead Data Engineer", manual_start, "2024-06")]
    if manual_has_helios:
        manual_exps.append(experience("Helios Conseil", "Analyste", "2020-01", "2021-12"))
    manual = {"experiences": manual_exps}
    profile, _ = build_profile_from_sources({"cv": cv_v2, "manual": manual})
    orion = _by_company(profile, "orion")
    assert len(orion) == 1
    assert orion[0]["role"] == "Lead Data Engineer"  # la correction reste visible
    assert set(orion[0]["sources"]) == {"manual", "cv"}
    assert len(_by_company(profile, "helios")) == 1  # l'autre poste du CV v2 est là, une seule fois
    assert len(profile["experiences"]) == 2
