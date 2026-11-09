import copy
from pathlib import Path

import pytest

from scripts.reference_dataset import load_reference, validate_reference

MINI = Path(__file__).parent / "fixtures" / "reference_mini"


@pytest.fixture
def ref():
    return load_reference(MINI)


def _dup_profile(r):
    r["profiles"][1]["profile_id"] = "p01"


def _unknown_label(r):
    r["matching_labels"][0]["label"] = "moyen"


def _missing_offer(r):
    r["matching_labels"][0]["offer_id"] = "o999"


def _dup_pair(r):
    r["matching_labels"].append(copy.deepcopy(r["matching_labels"][0]))


def _empty_motif(r):
    r["matching_labels"][0]["motif"] = "  "


def _page_zero(r):
    r["cv_facts"][0]["page"] = 0


def _incomplete_subgroup(r):
    del r["profiles"][0]["subgroup"]["langue"]


def _no_source(r):
    r["profiles"][0]["sources"] = {"cv": {}}


def _bad_critique(r):
    r["cv_facts"][0]["critique"] = "oui"


def _bad_preference_violee(r):
    r["matching_labels"][2]["preference_violee"] = "oui"


def _unknown_letter_profile(r):
    r["letter_requirements"][0]["profile_id"] = "p99"


def _empty_description(r):
    r["offers"][0]["description"] = ""


def _unhashable_profile_id(r):
    r["profiles"][0]["profile_id"] = ["p01"]


def _non_string_fact(r):
    r["cv_facts"][0]["fait"] = 12


def _unknown_source(r):
    r["profiles"][0]["sources"] = {"linkedin": {"headline": "x"}}


def _non_dict_row(r):
    r["profiles"][0] = "pas un objet"


def _missing_offer_id(r):
    del r["matching_labels"][0]["offer_id"]


def _bad_piege(r):
    r["offers"][0]["piege_filtre_metier"] = "oui"


def _dup_offer(r):
    r["offers"][1]["offer_id"] = "o001"


@pytest.mark.parametrize(
    "mutate, fragment",
    [
        (_dup_profile, "p01"),
        (_dup_offer, "o001"),
        (_unknown_label, "moyen"),
        (_missing_offer, "o999"),
        (_dup_pair, "dupliqu"),
        (_empty_motif, "motif"),
        (_page_zero, "page"),
        (_incomplete_subgroup, "langue"),
        (_no_source, "source"),
        (_bad_critique, "critique"),
        (_bad_preference_violee, "preference_violee"),
        (_unknown_letter_profile, "p99"),
        (_empty_description, "description"),
        (_unhashable_profile_id, "profile_id"),
        (_non_string_fact, "fait"),
        (_unknown_source, "source inconnue"),
        (_non_dict_row, "objet attendu"),
        (_missing_offer_id, "offer_id manquant ou vide"),
        (_bad_piege, "piege_filtre_metier"),
    ],
)
def test_invalid_dataset_reports_error(ref, mutate, fragment):
    mutate(ref)
    errors = validate_reference(ref)
    assert errors
    assert any(fragment in e for e in errors)


def test_valid_mini_dataset_has_no_error_and_tolerates_optional_field(ref):
    assert validate_reference(ref) == []
    ref["offers"][0]["piege_filtre_metier"] = True
    assert validate_reference(ref) == []
