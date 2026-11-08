"""Générateur de PDF synthétiques annotés : données, pages cibles, scans, déterminisme."""
# ruff: noqa: F811  (les fixtures importées sont redéclarées en paramètres des tests)
import pymupdf
import pytest

from app.services.cv_parser import extract_page_texts
from tests.cv_reference.cv_reference_fixtures import (  # noqa: F401  (fixtures pytest)
    _no_network, cases, entry, generated, reference,
)
from scripts.cv_reference_pdfs import CATEGORIES, PageInvariantError, check_page_invariant, generate_cases

ABSENT_FACT = {"fait": "Absente SARL", "champ": "experiences.company", "page": 1, "critique": True}


def test_cases_data_cover_categories_manual_profiles_and_long_pages(cases, entry):
    assert len(cases) >= 20 and len({c["case_id"] for c in cases}) == len(cases)
    assert {c["category"] for c in cases} == set(CATEGORIES)
    manual = [c for c in cases if c["category"] == "manual_trade"]
    assert len(manual) >= 2 and all(c["extra_profile"] and c["extra_facts"] for c in manual)
    assert all(c["extra_profile"]["contact"]["email"].endswith("@example.com") for c in manual)
    assert all(entry(c["case_id"])["n_pages"] >= 4 for c in cases if c["category"] == "long")


def test_every_fact_is_on_its_target_page_and_misplacement_fails(generated, reference, tmp_path):
    for e in generated["manifest"]:
        if e["category"] not in ("protected", "unreadable"):
            check_page_invariant(extract_page_texts(e["path"]), e["facts"], skip_pages=e["scanned_pages"])
    with pytest.raises(PageInvariantError):
        check_page_invariant(["autre chose", "Absente SARL"], [ABSENT_FACT])
    case = {"case_id": "x", "profile_id": None, "category": "one_column", "options": {},
            "extra_profile": reference["profiles"][0]["sources"]["cv"], "extra_facts": [ABSENT_FACT]}
    with pytest.raises(PageInvariantError):
        generate_cases([case], reference, tmp_path)


@pytest.mark.parametrize("case_id", ["sc_p04", "ms_p07"])
def test_scanned_pages_have_no_text_layer(entry, case_id):
    e = entry(case_id)
    texts = extract_page_texts(e["path"])
    assert len(texts) == e["n_pages"]
    with pymupdf.open(e["path"]) as doc:
        for number, text in enumerate(texts, start=1):
            scanned = number in e["scanned_pages"]
            assert (not text.strip()) == scanned and bool(doc[number - 1].get_images()) == scanned
    assert (1 in e["scanned_pages"]) == (case_id == "sc_p04")  # le mixte garde la page 1 en texte


def test_generation_is_deterministic(tmp_path, cases, reference):
    subset = [c for c in cases if c["case_id"] in ("oc_p01", "sc_p01", "lg_p04")]
    first = generate_cases(subset, reference, tmp_path / "a")
    second = generate_cases(subset, reference, tmp_path / "b")
    for a, b in zip(first, second):
        assert open(a["path"], "rb").read() == open(b["path"], "rb").read()
