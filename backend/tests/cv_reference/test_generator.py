"""Générateur de PDF synthétiques annotés : catégories, pages cibles, scans, protection."""
import pymupdf
import pytest

from app.services.cv_parser import extract_page_texts, is_pdf_password_protected
from scripts.cv_reference_pdfs import CATEGORIES, PageInvariantError, check_page_invariant, generate_cases

REPRESENTATIVE = ["oc_p01", "tc_p12", "en_p06", "mt_cariste", "mt_aide_soignante", "lg_p04", "lg_p07", "lg_p21"]
ONE_PAGE_FACT = {"fait": "Acme", "champ": "experiences.company", "page": 1, "critique": True}


def test_cases_cover_every_category(cases):
    assert len(cases) >= 20
    assert {c["category"] for c in cases} == set(CATEGORIES)
    assert len({c["case_id"] for c in cases}) == len(cases)


def test_manual_trade_cases_carry_their_own_profile(cases):
    manual = [c for c in cases if c["category"] == "manual_trade"]
    assert len(manual) >= 2
    assert all(c["extra_profile"] and c["extra_facts"] for c in manual)
    emails = [c["extra_profile"]["contact"]["email"] for c in manual]
    assert all(e.endswith("@example.com") for e in emails)


@pytest.mark.parametrize("case_id", REPRESENTATIVE)
def test_each_fact_is_on_its_target_page(generated, entry, case_id):
    e = entry(case_id)
    texts = [" ".join(t.split()) for t in extract_page_texts(e["path"])]
    for fact in e["facts"]:
        assert " ".join(fact["fait"].split()) in texts[fact["page"] - 1], fact


def test_page_invariant_holds_for_every_unscanned_page(generated):
    for e in generated["manifest"]:
        if e["category"] in ("protected", "unreadable"):
            continue
        check_page_invariant(extract_page_texts(e["path"]), e["facts"], skip_pages=e["scanned_pages"])


def test_page_invariant_violation_is_raised():
    with pytest.raises(PageInvariantError):
        check_page_invariant(["autre chose", ""], [ONE_PAGE_FACT])
    with pytest.raises(PageInvariantError):
        check_page_invariant(["", "Acme"], [ONE_PAGE_FACT])


def test_generation_fails_when_a_fact_cannot_be_placed(tmp_path, reference):
    case = {"case_id": "x", "profile_id": None, "category": "one_column", "options": {},
            "extra_profile": reference["profiles"][0]["sources"]["cv"],
            "extra_facts": [{**ONE_PAGE_FACT, "fait": "Absente SARL"}]}
    with pytest.raises(PageInvariantError):
        generate_cases([case], reference, tmp_path)


@pytest.mark.parametrize("case_id", ["sc_p01", "sc_p04", "sc_p19"])
def test_scanned_pages_have_no_text_layer(entry, case_id):
    e = entry(case_id)
    assert e["scanned_pages"] == list(range(1, e["n_pages"] + 1))
    assert all(not t.strip() for t in extract_page_texts(e["path"]))
    with pymupdf.open(e["path"]) as doc:
        assert all(page.get_images() for page in doc)


def test_mixed_scanned_keeps_first_page_as_text(entry):
    e = entry("ms_p07")
    texts = extract_page_texts(e["path"])
    assert texts[0].strip() and not any(t.strip() for t in texts[1:])


def test_protected_pdf_is_detected(entry):
    assert is_pdf_password_protected(entry("pr_p02")["path"])
    assert not is_pdf_password_protected(entry("oc_p01")["path"])


def test_unreadable_pdf_does_not_open(entry):
    with pytest.raises(Exception):
        pymupdf.open(entry("un_corrupt")["path"])


def test_empty_pdf_is_one_blank_page(entry):
    assert extract_page_texts(entry("em_blank")["path"]) == [""]


@pytest.mark.parametrize("case_id", ["lg_p04", "lg_p07", "lg_p13", "lg_p21"])
def test_long_cases_have_at_least_four_pages(entry, case_id):
    e = entry(case_id)
    assert e["n_pages"] >= 4 and len(extract_page_texts(e["path"])) == e["n_pages"]


def test_generation_is_deterministic(tmp_path, cases, reference):
    subset = [c for c in cases if c["case_id"] in ("oc_p01", "sc_p01", "lg_p04")]
    first = generate_cases(subset, reference, tmp_path / "a")
    second = generate_cases(subset, reference, tmp_path / "b")
    for a, b in zip(first, second):
        assert open(a["path"], "rb").read() == open(b["path"], "rb").read()
