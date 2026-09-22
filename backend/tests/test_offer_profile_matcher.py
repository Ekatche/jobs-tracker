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


@pytest.mark.asyncio
async def test_rematch_user_addstoset_and_pull():
    from unittest.mock import AsyncMock, MagicMock
    from bson import ObjectId
    from app.services.offer_profile_matcher import rematch_user

    user_id = "650000000000000000000001"

    matching_offer = {"_id": ObjectId("650000000000000000000010"), "canonical_title": "Data Engineer", "localisation": "Lyon", "mode_travail": "Hybride"}
    non_matching_offer = {"_id": ObjectId("650000000000000000000020"), "canonical_title": "Comptable", "localisation": "Nantes", "mode_travail": "Présentiel"}

    mock_profile_collection = MagicMock()
    mock_profile_collection.find_one = AsyncMock(
        return_value={"user_id": ObjectId(user_id), "preferences": {"target_roles": ["Data Engineer"], "locations": ["Lyon"], "remote_policy": "flexible"}}
    )

    mock_offers_cursor = MagicMock()
    mock_offers_cursor.to_list = AsyncMock(return_value=[matching_offer, non_matching_offer])

    mock_offers_collection = MagicMock()
    mock_offers_collection.find = MagicMock(return_value=mock_offers_cursor)
    mock_offers_collection.update_many = AsyncMock()

    mock_db = {"candidate_profile": mock_profile_collection, "job_offers": mock_offers_collection}

    with patch("app.services.offer_profile_matcher.normalize_role", AsyncMock(return_value="Data Engineer")):
        await rematch_user(user_id, mock_db)

    add_call = mock_offers_collection.update_many.call_args_list[0]
    assert add_call.args[0] == {"_id": {"$in": [matching_offer["_id"]]}}
    assert add_call.args[1] == {"$addToSet": {"matched_user_ids": user_id}}

    pull_call = mock_offers_collection.update_many.call_args_list[1]
    assert pull_call.args[0] == {"_id": {"$in": [non_matching_offer["_id"]]}}
    assert pull_call.args[1] == {"$pull": {"matched_user_ids": user_id}}


@pytest.mark.asyncio
async def test_rematch_user_no_profile_does_nothing():
    from unittest.mock import AsyncMock, MagicMock
    from app.services.offer_profile_matcher import rematch_user

    mock_profile_collection = MagicMock()
    mock_profile_collection.find_one = AsyncMock(return_value=None)

    mock_offers_cursor = MagicMock()
    mock_offers_cursor.to_list = AsyncMock(return_value=[])

    mock_offers_collection = MagicMock()
    mock_offers_collection.find = MagicMock(return_value=mock_offers_cursor)
    mock_offers_collection.update_many = AsyncMock()

    mock_db = {"candidate_profile": mock_profile_collection, "job_offers": mock_offers_collection}

    await rematch_user("650000000000000000000099", mock_db)

    mock_offers_collection.update_many.assert_not_called()
