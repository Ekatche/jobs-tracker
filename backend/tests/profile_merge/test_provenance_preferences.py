"""Provenance, préférences explicites et lisibilité des anciens profils."""

import copy

import pytest
from bson import ObjectId

from app.models import CandidateProfile
from app.services.offer_scoring.score import profile_features
from app.services.profile.context import build_candidate_context
from app.services.profile.merge import build_profile_from_sources
from tests.profile_merge.fixtures import (
    CV,
    CV_TWO_JOBS_NO_RUST,
    FERRIS_PROJECT,
    LEGACY_PROFILE_V0,
    LEGACY_PROFILE_V1,
    PREFS_MANUAL,
    PREFS_WEBSITE,
)


@pytest.mark.parametrize("project_source", ["github", "website", "cv"])
def test_project_skill_never_becomes_an_experience(project_source):
    sources = {"cv": copy.deepcopy(CV_TWO_JOBS_NO_RUST)}
    if project_source == "cv":
        sources["cv"]["projects"] = [FERRIS_PROJECT]
    else:
        sources[project_source] = {"projects": [FERRIS_PROJECT]}

    profile, _ = build_profile_from_sources(sources)
    context = build_candidate_context(profile)

    for view in (profile, context):
        assert len(view["experiences"]) == 2
        assert all(e["company"] != "ferris-cli" and e["role"] != "ferris-cli" for e in view["experiences"])
        assert all("Rust" not in (e.get("stack") or []) for e in view["experiences"])
    project = next(p for p in profile["projects"] if p["name"] == "ferris-cli")
    assert project["sources"] == [project_source]
    assert [p["name"] for p in context["projects"]] == ["ferris-cli"]


def test_explicit_preferences_survive_conflicts_reimport_and_refusion():
    """manual contre website contradictoires, réimport d'un cv autre, refusion idempotente."""
    sources = {"manual": {"preferences": PREFS_MANUAL}, "website": {"preferences": PREFS_WEBSITE}}
    profile, _ = build_profile_from_sources(sources)
    assert profile["preferences"] == PREFS_MANUAL  # manual gagne entièrement

    reimported, _ = build_profile_from_sources({**sources, "cv": CV})
    assert reimported["preferences"] == PREFS_MANUAL

    refused, _ = build_profile_from_sources(
        {"manual": {"preferences": profile["preferences"]}, "website": {"preferences": PREFS_WEBSITE}}
    )
    assert refused["preferences"] == profile["preferences"]

    features = profile_features(reimported)
    assert features.preferences == PREFS_MANUAL
    assert features.seniority_levels == ("senior",)


def test_website_preferences_are_used_when_manual_has_none():
    profile, _ = build_profile_from_sources(
        {"manual": {"headline": "Data Engineer"}, "website": {"preferences": PREFS_WEBSITE}}
    )
    assert profile["preferences"] == PREFS_WEBSITE


def test_manual_preferences_replace_other_sources_wholesale():
    """Documente la règle : l'objet `manual` entier fait autorité, comme `_merge_skills`.

    Le formulaire de préférences envoie l'état complet voulu par l'utilisateur ;
    une fusion clé par clé ferait réapparaître une valeur effacée. Les `locations`
    du site sont donc perdues quand manual ne porte que `target_roles`.
    """
    profile, _ = build_profile_from_sources(
        {
            "manual": {"preferences": {"target_roles": ["Data Engineer"]}},
            "website": {"preferences": {"locations": ["Paris"]}},
        }
    )
    assert profile["preferences"] == {"target_roles": ["Data Engineer"]}
    assert "locations" not in profile["preferences"]


@pytest.mark.parametrize("legacy", [LEGACY_PROFILE_V1, LEGACY_PROFILE_V0], ids=["v1", "v0"])
def test_legacy_profile_documents_stay_readable(legacy):
    document = copy.deepcopy(legacy)

    context = build_candidate_context(document)
    assert context["experiences"][0]["achievements"] == []
    assert context["experiences"][0]["company"] == legacy["experiences"][0]["company"]

    features = profile_features(document)
    assert features.preferences == (legacy.get("preferences") or {})
    assert features.preferred_industries == () and features.preferred_company_sizes == ()

    validated = CandidateProfile.model_validate({**document, "user_id": ObjectId()})
    assert validated.experiences[0].sources == []
    assert validated.preferences.excluded_keywords == []

    merged, _ = build_profile_from_sources({"cv": document})
    assert merged["experiences"][0]["sources"] == ["cv"]
    assert merged["headline"] == legacy["headline"]
