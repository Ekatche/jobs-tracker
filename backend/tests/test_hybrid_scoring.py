import pytest

from app.services.offer_scoring.constants import CAP_SCORE, W_SENIORITY, W_SIZE
from app.services.offer_scoring.score import (
    ComponentPoints,
    build_skill_idf,
    combine,
    level_for,
    preference_points,
    profile_features,
    semantic_points,
    seniority_points,
    skill_points,
)


def test_semantic_points_clamped():
    assert semantic_points(0.70).points == 0
    assert semantic_points(0.78).points == pytest.approx(22.5)
    assert semantic_points(0.90).points == 45
    assert semantic_points(None) == ComponentPoints(22.5, 45, False)


def test_skill_points_idf_weighted():
    idf = build_skill_idf([["Python", "SQL"], ["python"], ["Python"]])
    result = skill_points(["Python", "SQL"], frozenset({"sql"}), idf)
    assert result.points == pytest.approx(30 * 1.6931 / 2.6931, rel=1e-3)


def test_skill_points_unknown_and_not_applicable():
    idf = build_skill_idf([["Python"]])
    assert skill_points([], frozenset({"python"}), idf) == ComponentPoints(15, 30, False)
    assert skill_points(["Python"], frozenset(), idf) is None


@pytest.mark.parametrize(
    "offer_level,wanted,expected",
    [
        ("senior", ["senior"], 10),
        ("lead", ["senior"], 6),
        ("junior", ["senior"], 0),
    ],
)
def test_seniority_points(offer_level, wanted, expected):
    result = seniority_points(offer_level, wanted)
    assert result.points == pytest.approx(expected)
    assert result.known is True


def test_seniority_points_unknown_offer_level():
    assert seniority_points(None, ["senior"]) == ComponentPoints(5, 10, False)


def test_seniority_points_no_preference_not_applicable():
    assert seniority_points("senior", []) is None


def test_preference_points():
    assert preference_points("tech", ["tech", "finance"], 10) == ComponentPoints(10, 10, True)
    assert preference_points("retail", ["tech", "finance"], 10) == ComponentPoints(0, 10, True)
    assert preference_points(None, ["tech", "finance"], 10) == ComponentPoints(5, 10, False)
    assert preference_points("tech", [], 10) is None

    assert preference_points("pme", ["pme", "startup"], 5) == ComponentPoints(5, 5, True)
    assert preference_points("eti", ["pme", "startup"], 5) == ComponentPoints(0, 5, True)
    assert preference_points(None, ["pme", "startup"], 5) == ComponentPoints(2.5, 5, False)


def test_score_normalizes_by_applicable_points():
    result = combine(
        {
            "semantic": ComponentPoints(45, 45, True),
            "skills": ComponentPoints(30, 30, True),
            "seniority": None,
            "sector": None,
            "size": None,
        },
        [],
    )
    assert result.score == 100
    assert result.level == "strong"


def test_unknown_components_give_half_score():
    result = combine(
        {
            "semantic": ComponentPoints(22.5, 45, False),
            "skills": ComponentPoints(15, 30, False),
            "seniority": ComponentPoints(5, 10, False),
            "sector": ComponentPoints(5, 10, False),
            "size": ComponentPoints(2.5, 5, False),
        },
        [],
    )
    assert result.score == pytest.approx(50)
    assert result.unknown_components == ["semantic", "skills", "seniority", "sector", "size"]


def test_failed_condition_caps_score():
    result = combine(
        {
            "semantic": ComponentPoints(40.5, 45, True),
            "skills": ComponentPoints(27, 30, True),
            "seniority": ComponentPoints(9, 10, True),
            "sector": ComponentPoints(9, 10, True),
            "size": ComponentPoints(4.5, 5, True),
        },
        ["geo"],
    )
    assert result.score == CAP_SCORE
    assert result.level == "weak"
    assert result.breakdown["raw_score"] == pytest.approx(90)
    assert result.failed_conditions == ["geo"]

    low = combine(
        {
            "semantic": ComponentPoints(18, 45, True),
            "skills": ComponentPoints(12, 30, True),
            "seniority": ComponentPoints(4, 10, True),
            "sector": ComponentPoints(4, 10, True),
            "size": ComponentPoints(2, 5, True),
        },
        ["contract"],
    )
    assert low.breakdown["raw_score"] == pytest.approx(40)
    assert low.score == pytest.approx(40)


@pytest.mark.parametrize(
    "score,expected",
    [
        (75, "strong"),
        (74.99, "medium"),
        (60, "medium"),
        (59.99, "weak"),
        (0, "weak"),
    ],
)
def test_level_thresholds(score, expected):
    assert level_for(score) == expected


def test_no_applicable_component_returns_none():
    result = combine(
        {"semantic": None, "skills": None, "seniority": None, "sector": None, "size": None},
        [],
    )
    assert result is None


def test_profile_features_flattens_skills():
    profile = {
        "headline": "AI Engineer",
        "skills": {"langages": ["Python"], "outils": ["Docker"]},
        "preferences": {"target_roles": ["ML Engineer"], "seniority_levels": ["senior", "inconnu"]},
    }
    features = profile_features(profile)

    assert features.skills == frozenset({"python", "docker"})
    assert features.seniority_levels == ("senior",)
    assert features.identity != ""
