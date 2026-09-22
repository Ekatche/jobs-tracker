from app.services.offer_profile_matcher import offer_matches_criteria


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
