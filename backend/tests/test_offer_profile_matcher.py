import pytest
from unittest.mock import AsyncMock, patch
from app.services.offer_profile_matcher import offer_matches_criteria, get_normalized_profile_criteria


def test_offer_matches_criteria_role_only():
    offer = {"canonical_title": "Data Engineer", "localisation": "Lyon", "mode_travail": "Hybride"}
    assert offer_matches_criteria(offer, {"data engineer"}, set(), "flexible") is True
    assert offer_matches_criteria(offer, {"data scientist"}, set(), "flexible") is False


def test_offer_matches_criteria_location_only():
    offer = {"canonical_title": "Data Engineer", "localisation": "Lyon", "mode_travail": "Hybride"}
    assert offer_matches_criteria(offer, set(), {"lyon"}, "flexible") is True
    assert offer_matches_criteria(offer, set(), {"paris"}, "flexible") is False


def test_offer_matches_criteria_role_and_location():
    offer = {"canonical_title": "Data Engineer", "localisation": "Lyon", "mode_travail": "Hybride"}
    assert offer_matches_criteria(offer, {"data engineer"}, {"lyon"}, "flexible") is True
    assert offer_matches_criteria(offer, {"data engineer"}, {"paris"}, "flexible") is False
    assert offer_matches_criteria(offer, {"data scientist"}, {"lyon"}, "flexible") is False


def test_offer_matches_criteria_empty_profile_never_matches():
    offer = {"canonical_title": "Data Engineer", "localisation": "Lyon", "mode_travail": "Hybride"}
    assert offer_matches_criteria(offer, set(), set(), "flexible") is False


def test_offer_matches_criteria_full_remote_with_teletravail_offer():
    offer = {"canonical_title": "Data Engineer", "localisation": "Paris", "mode_travail": "Télétravail total"}
    # Localisation ne matche pas ("lyon" attendu), mais l'offre est en télétravail total
    # et le profil est en full_remote -> doit matcher malgré tout.
    assert offer_matches_criteria(offer, {"data engineer"}, {"lyon"}, "full_remote") is True


def test_offer_matches_criteria_case_insensitive():
    offer = {"canonical_title": "DATA ENGINEER", "localisation": "LYON", "mode_travail": "Hybride"}
    assert offer_matches_criteria(offer, {"data engineer"}, {"lyon"}, "flexible") is True


@pytest.mark.asyncio
async def test_get_normalized_profile_criteria_normalizes_roles_and_locations():
    prefs = {
        "target_roles": ["Ingénieur Data", "  "],
        "locations": ["69000 Lyon", "Paris"],
        "remote_policy": "hybrid",
    }

    async def fake_normalize_role(role, db=None):
        return {"Ingénieur Data": "Data Engineer"}.get(role, role)

    with patch(
        "app.services.offer_profile_matcher.normalize_role",
        AsyncMock(side_effect=fake_normalize_role),
    ):
        roles, locations, remote_policy = await get_normalized_profile_criteria(prefs, db=None)

    assert roles == {"data engineer"}
    assert locations == {"lyon", "paris"}
    assert remote_policy == "hybrid"


@pytest.mark.asyncio
async def test_get_normalized_profile_criteria_empty_prefs():
    with patch("app.services.offer_profile_matcher.normalize_role", AsyncMock()) as mock_role:
        roles, locations, remote_policy = await get_normalized_profile_criteria({}, db=None)

    assert roles == set()
    assert locations == set()
    assert remote_policy == "flexible"
    mock_role.assert_not_called()
