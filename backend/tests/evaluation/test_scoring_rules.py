"""Tests des règles de calcul du score, de réconciliation et de parsing JSON."""

import pytest

from app.models import (
    BlocA,
    BlocB,
    BlocG,
    MissingRequirement,
    PreferenceMismatch,
    RequirementMatch,
)
from app.services.evaluation.evaluator import (
    _clean_json_output,
    calculate_evaluation_score,
    quote_in_offer,
    reconcile_with_pass1,
)


def _match(requirement, weight="critical", status="full_match", quote_verified=True):
    return RequirementMatch(
        requirement=requirement,
        weight=weight,
        candidate_evidence="preuve",
        verbatim_quote="citation",
        status=status,
        quote_verified=quote_verified,
    )


def _missing(requirement, weight="critical"):
    return MissingRequirement(requirement=requirement, weight=weight, reason="absent")


FOUR_FULL_MATCHES = [
    _match("Python"),
    _match("FastAPI"),
    _match("MongoDB", "high"),
    _match("Docker", "meaningful"),
]

PASS1_REQUIREMENTS = [
    {"id": "R1", "requirement": "BAFA", "weight": "critical"},
    {"id": "R2", "requirement": "Permis B", "weight": "high"},
    {"id": "R3", "requirement": "Anglais", "weight": "meaningful"},
]


# --- Nettoyage JSON ---


def test_clean_json_output_fences():
    raw = '```json\n{"archetype": "Lead Dev", "requirements": []}\n```'
    cleaned = _clean_json_output(raw)
    assert cleaned["archetype"] == "Lead Dev"


def test_clean_json_output_raw_text_wrapper():
    raw = 'Here is the result:\n{"summary": "Cool job", "is_ghost_job": false}\nHope it helps!'
    cleaned = _clean_json_output(raw)
    assert cleaned["summary"] == "Cool job"
    assert cleaned["is_ghost_job"] is False


# --- Calcul du Score ---


def test_calculate_evaluation_score_perfect():
    bloc_b = BlocB(matched_requirements=FOUR_FULL_MATCHES)
    assert calculate_evaluation_score(BlocA(), bloc_b, BlocG(), description_length=1200) == 5.0


def test_calculate_evaluation_score_red_flag_caps():
    bloc_a_geo = BlocA(archetype="Staff Engineer", geo_mismatch=True)
    bloc_b = BlocB(matched_requirements=FOUR_FULL_MATCHES)
    bloc_g = BlocG(is_ghost_job=False, is_scam_risk=False)
    assert calculate_evaluation_score(bloc_a_geo, bloc_b, bloc_g) == 1.5

    bloc_a_clean = BlocA(archetype="Staff Engineer", geo_mismatch=False)
    bloc_g_scam = BlocG(is_ghost_job=False, is_scam_risk=True)
    assert calculate_evaluation_score(bloc_a_clean, bloc_b, bloc_g_scam) == 1.5


def test_ghost_job_caps_only_when_repost_detected():
    bloc_a = BlocA(archetype="Staff Engineer")
    bloc_b = BlocB(matched_requirements=FOUR_FULL_MATCHES)
    assert calculate_evaluation_score(bloc_a, bloc_b, BlocG(is_ghost_job=True)) == 5.0
    corroborated = BlocG(is_ghost_job=True, reposted_frequency="3 publications")
    assert calculate_evaluation_score(bloc_a, bloc_b, corroborated) == 1.5


def test_calculate_evaluation_score_domain_mismatch_caps():
    bloc_a = BlocA(archetype="Data Scientist", domain_mismatch=True)
    bloc_b = BlocB(matched_requirements=[], missing_requirements=[])
    bloc_g = BlocG(is_ghost_job=False, is_scam_risk=False)
    assert calculate_evaluation_score(bloc_a, bloc_b, bloc_g) == 1.5


def test_score_is_weighted_coverage():
    bloc_b = BlocB(
        matched_requirements=[_match("Python", "critical"), _match("Go", "high")],
        missing_requirements=[_missing("Kubernetes", "critical"), _missing("GCP", "meaningful")],
    )
    assert calculate_evaluation_score(BlocA(), bloc_b, BlocG()) == 3.22


def test_partial_match_earns_half_credit():
    bloc_b = BlocB(
        matched_requirements=[
            _match("5 ans d'expérience", "critical", "partial_match"),
            _match("Kafka", "high", "partial_match"),
            _match("Python", "critical"),
            _match("Anglais", "meaningful"),
        ]
    )
    assert calculate_evaluation_score(BlocA(), bloc_b, BlocG()) == 3.89


def test_calculate_evaluation_score_min_bound():
    bloc_b = BlocB(missing_requirements=[_missing(f"Req {i}") for i in range(10)])
    assert calculate_evaluation_score(BlocA(), bloc_b, BlocG()) == 1.0


def test_no_requirement_evaluated_is_neutral():
    assert calculate_evaluation_score(BlocA(), BlocB(), BlocG()) == 3.0


def test_thin_offer_is_capped():
    few = BlocB(matched_requirements=FOUR_FULL_MATCHES[:3])
    assert calculate_evaluation_score(BlocA(), few, BlocG(), description_length=1200) == 4.0

    enough = BlocB(matched_requirements=FOUR_FULL_MATCHES)
    assert calculate_evaluation_score(BlocA(), enough, BlocG(), description_length=290) == 4.0
    assert calculate_evaluation_score(BlocA(), enough, BlocG()) == 5.0


def test_preference_mismatches_and_partial_domain_are_penalized():
    bloc_a = BlocA(
        domain_coherence="partial",
        preference_mismatches=[
            PreferenceMismatch(criterion="contrat", offer_value="Stage", expected="CDI", weight="high"),
            PreferenceMismatch(criterion="séniorité", offer_value="senior", expected="mid", weight="meaningful"),
        ],
    )
    bloc_b = BlocB(matched_requirements=FOUR_FULL_MATCHES)
    assert calculate_evaluation_score(bloc_a, bloc_b, BlocG()) == 3.8


def test_unverified_quote_does_not_change_score():
    unverified = BlocB(matched_requirements=FOUR_FULL_MATCHES[:3] + [_match("Docker", "meaningful", quote_verified=False)])
    assert calculate_evaluation_score(BlocA(), unverified, BlocG()) == 5.0


# --- Réconciliation Pass 1 / Pass 2 ---


def test_reconcile_imposes_pass1_weight_and_adds_untreated_requirements():
    matched = [{"req_id": "R1", "requirement": "BAFA", "weight": "meaningful", "status": "full_match"}]
    missing = [{"req_id": "R3", "requirement": "Anglais", "weight": "critical", "reason": "absent"}]

    matched_out, missing_out = reconcile_with_pass1(PASS1_REQUIREMENTS, matched, missing)
    assert matched_out[0]["weight"] == "critical"
    assert [m["weight"] for m in missing_out if m["req_id"] == "R3"] == ["meaningful"]
    untreated = [m for m in missing_out if m["req_id"] == "R2"]
    assert len(untreated) == 1
    assert untreated[0]["weight"] == "high"
    assert "non traitée" in untreated[0]["reason"]


def test_reconcile_without_req_ids_keeps_pass2_as_is():
    matched = [{"requirement": "BAFA", "weight": "high", "status": "full_match"}]
    matched_out, missing_out = reconcile_with_pass1(PASS1_REQUIREMENTS, matched, [])
    assert matched_out[0]["weight"] == "high"
    assert missing_out == []


def test_reconcile_ignores_unknown_req_id():
    matched = [
        {"req_id": "R1", "requirement": "BAFA", "weight": "critical"},
        {"req_id": "R9", "requirement": "Inventé", "weight": "high"},
    ]
    matched_out, missing_out = reconcile_with_pass1(PASS1_REQUIREMENTS, matched, [])
    assert matched_out[1]["weight"] == "high"
    assert {m["req_id"] for m in missing_out} == {"R2", "R3"}


# --- Vérification des citations ---


@pytest.mark.parametrize(
    "quote,expected",
    [
        ("Titulaire du BAFA", True),
        ("titulaire   du  bafa", True),
        ("l’équipe d'animation", True),
        ("Titulaire du BAFA ... permis B apprécié", True),
        ("Titulaire du BAFA … permis B apprécié", True),
        ("BAFA obligatoire", False),
        ("Titulaire du BAFA ... permis C", False),
        ("", False),
    ],
)
def test_quote_in_offer(quote, expected):
    offer = "Poste d'animateur. Titulaire du BAFA, vous rejoignez l'équipe d'animation.\nPermis B apprécié."
    assert quote_in_offer(quote, offer) is expected
