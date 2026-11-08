import copy
import shutil
from pathlib import Path

import pytest

from scripts.reference_dataset import coverage_report, load_reference, validate_reference

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


def _blank_fact(r):
    r["cv_facts"][0]["fait"] = 12


def _unknown_source(r):
    r["profiles"][0]["sources"] = {"linkedin": {"headline": "x"}}


def _dup_offer(r):
    r["offers"][1]["offer_id"] = "o001"


@pytest.mark.parametrize("name", ["profiles", "offers", "matching_labels", "cv_facts", "letter_requirements"])
def test_non_dict_row_reports_error(ref, name):
    ref[name][0] = "pas un objet"
    assert any(f"{name}[0]" in e and "objet attendu" in e for e in validate_reference(ref))


@pytest.mark.parametrize(
    "name, key, value",
    [
        ("profiles", "profile_id", ""),
        ("offers", "offer_id", None),
        ("matching_labels", "profile_id", ""),
        ("matching_labels", "offer_id", None),
        ("cv_facts", "profile_id", " "),
        ("letter_requirements", "profile_id", None),
        ("letter_requirements", "offer_id", ""),
    ],
)
def test_missing_or_empty_id_reports_error(ref, name, key, value):
    if value is None:
        del ref[name][0][key]
    else:
        ref[name][0][key] = value
    assert any(f"{name}[0] : {key} manquant ou vide" in e for e in validate_reference(ref))


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
        (_blank_fact, "fait"),
        (_unknown_source, "source inconnue"),
    ],
)
def test_invalid_dataset_reports_error(ref, mutate, fragment):
    mutate(ref)
    errors = validate_reference(ref)
    assert errors
    assert any(fragment in e for e in errors)


def test_valid_mini_dataset_has_no_error(ref):
    assert validate_reference(ref) == []


def test_unknown_optional_offer_field_is_tolerated(ref):
    ref["offers"][0]["piege_filtre_metier"] = True
    assert validate_reference(ref) == []


def test_non_boolean_piege_filtre_metier_rejected(ref):
    ref["offers"][0]["piege_filtre_metier"] = "oui"
    assert any("piege_filtre_metier" in e for e in validate_reference(ref))


def test_coverage_report_on_mini_dataset(ref):
    report = coverage_report(ref)
    assert report["profiles"] == 2
    assert report["offers"] == 2
    assert report["labels"] == 3
    assert report["labels_per_profile_min"] == 1
    assert report["labels_by_value"] == {"pertinent": 1, "partiel": 1, "hors_sujet": 1}
    assert report["profiles_with_fact_page_ge_4"] == 1
    assert report["letter_requirements"] == 1
    assert report["subgroups"]["niveau"] == {"junior": 1, "senior": 1}


def test_load_reference_missing_file_raises(tmp_path):
    shutil.copytree(MINI, tmp_path / "ref")
    (tmp_path / "ref" / "offers.json").unlink()
    with pytest.raises(FileNotFoundError):
        load_reference(tmp_path / "ref")
