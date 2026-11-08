"""Générateur de PDF de CV synthétiques annotés (référence du plan parseur).

Les cas sont décrits dans ``scripts/reference/cv_pdf_cases.json`` ; chaque cas
s'appuie sur un profil du jeu commun (``scripts/reference/profiles.json``) ou, pour
les métiers manuels, sur un profil porté par le cas lui-même. Chaque fait attendu
(``cv_facts.json``) est rendu sur sa page cible ; le générateur vérifie lui-même cet
invariant et lève ``PageInvariantError`` s'il est violé. Les PDF sont régénérables
et ne sont pas versionnés (sortie : ``scripts/data/cv_reference/``).

Usage : ``uv run python scripts/cv_reference_pdfs.py [--out DIR]``
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.cv_parser import extract_page_texts  # noqa: E402
from scripts.reference_dataset import REFERENCE_DIR, load_reference  # noqa: E402

CASES_PATH = REFERENCE_DIR / "cv_pdf_cases.json"
DEFAULT_OUT = Path(__file__).resolve().parent / "data" / "cv_reference"
CATEGORIES = (
    "one_column", "two_columns", "scanned", "mixed_scanned", "english",
    "manual_trade", "long", "empty", "protected", "unreadable",
)
PAGE_W, PAGE_H = 595, 842
MARGIN = 36
SIDEBAR_W = 170
FONT_SIZES = (10, 9, 8, 7, 6)
SCAN_DPI = 72
DEFAULT_PASSWORD = "mot-de-passe-fictif"
CORRUPT_BYTES = b"%PDF-1.7\n" + bytes(range(256)) * 4  # en-tête valide, corps illisible
_HEADINGS = {
    "fr": ("EXPÉRIENCES", "FORMATION", "COMPÉTENCES", "LANGUES", "CERTIFICATIONS", "CONTACT"),
    "en": ("EXPERIENCE", "EDUCATION", "SKILLS", "LANGUAGES", "CERTIFICATIONS", "CONTACT"),
}


class PageInvariantError(RuntimeError):
    """Un fait attendu ne se trouve pas sur sa page cible."""


def load_cases(path: Path = CASES_PATH) -> List[Dict[str, Any]]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def case_profile(case: Dict[str, Any], ref: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Source ``cv`` du cas : profil du jeu commun ou ``extra_profile`` (métiers manuels)."""
    if case.get("extra_profile"):
        return case["extra_profile"]
    pid = case.get("profile_id")
    if not pid:
        return None
    for profile in ref["profiles"]:
        if profile["profile_id"] == pid:
            return profile["sources"]["cv"]
    raise KeyError(f"profil inconnu : {pid}")


def case_facts(case: Dict[str, Any], ref: Dict[str, Any]) -> List[Dict[str, Any]]:
    if case.get("extra_facts"):
        return [dict(f) for f in case["extra_facts"]]
    pid = case.get("profile_id")
    return [dict(f) for f in ref["cv_facts"] if f["profile_id"] == pid] if pid else []


def case_language(case: Dict[str, Any], ref: Dict[str, Any]) -> str:
    for profile in ref["profiles"]:
        if profile["profile_id"] == case.get("profile_id"):
            return profile.get("subgroup", {}).get("langue", "fr")
    return case.get("options", {}).get("lang", "fr")


def date_range(experience: Dict[str, Any]) -> str:
    """Forme des faits ``experiences.dates`` : ``2021-09 - present``."""
    return f"{experience.get('start_date') or ''} - {experience.get('end_date') or 'present'}"


def _fact_page(facts: List[Dict[str, Any]], champ: str, values: List[str]) -> Optional[int]:
    pages = [f["page"] for f in facts if f["champ"] == champ and f["fait"] in values]
    return min(pages) if pages else None


def _fill(pages: List[Optional[int]]) -> List[int]:
    """Un élément sans fait hérite de la page du précédent (le premier, de la première page connue)."""
    known = [p for p in pages if p]
    out: List[int] = []
    last = known[0] if known else 1
    for p in pages:
        last = p or last
        out.append(last)
    return out


def plan_pages(cv: Dict[str, Any], facts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Répartit expériences, formations et compétences sur les pages cibles des faits.

    Renvoie ``{"n_pages": n, "pages": [{"experiences": [i], "education": [i], "skills": [cat],
    "contact": bool}, ...]}`` ; la page d'indice 0 est la page 1.
    """
    experiences = cv.get("experiences") or []
    exp_pages = _fill([
        _fact_page(facts, "experiences.company", [e.get("company")])
        or _fact_page(facts, "experiences.role", [e.get("role")])
        or _fact_page(facts, "experiences.dates", [date_range(e)])
        for e in experiences
    ])
    education = cv.get("education") or []
    edu_pages = _fill([_fact_page(facts, "education.degree", [e.get("degree")]) for e in education])
    skills = cv.get("skills") or {}
    skill_pages = {cat: _fact_page(facts, "skills", items) or 1 for cat, items in skills.items()}
    contact_page = _fact_page(facts, "contact.email", [(cv.get("contact") or {}).get("email")]) or 1

    n_pages = max([f["page"] for f in facts] + exp_pages + edu_pages + list(skill_pages.values()) + [contact_page, 1])
    pages = [{"experiences": [], "education": [], "skills": [], "contact": False} for _ in range(n_pages)]
    for i, p in enumerate(exp_pages):
        pages[p - 1]["experiences"].append(i)
    for i, p in enumerate(edu_pages):
        pages[p - 1]["education"].append(i)
    for cat, p in skill_pages.items():
        pages[p - 1]["skills"].append(cat)
    pages[contact_page - 1]["contact"] = True
    return {"n_pages": n_pages, "pages": pages}


def _experience_text(e: Dict[str, Any]) -> str:
    lines = [e.get("company") or "", e.get("role") or "", date_range(e)]
    lines += [f"- {m}" for m in e.get("missions") or []]
    if e.get("stack"):
        lines.append("Stack : " + ", ".join(e["stack"]))
    return "\n".join(lines)


def _contact_text(contact: Dict[str, Any]) -> str:
    return "\n".join(str(contact[k]) for k in ("email", "phone", "location") if contact.get(k))


def _education_text(e: Dict[str, Any]) -> str:
    return "\n".join(x for x in (e.get("degree"), e.get("school"), e.get("years")) if x)


def _skills_text(cv: Dict[str, Any], cats: List[str]) -> str:
    return "\n".join(f"{cat} : " + ", ".join(cv["skills"][cat]) for cat in cats)


def _certifications_text(cv: Dict[str, Any]) -> str:
    return "\n".join(
        " - ".join(str(c[k]) for k in ("name", "issuer", "year") if c.get(k)) for c in cv.get("certifications") or []
    )


def _section(title: str, body: str) -> str:
    return f"{title}\n{body}\n" if body.strip() else ""


def _page_blocks(cv, plan, number: int, lang: str) -> Dict[str, str]:
    """Textes d'une page : colonne principale et barre latérale (``side``)."""
    h_exp, h_edu, h_skills, h_lang, h_cert, h_contact = _HEADINGS[lang]
    page = plan["pages"][number - 1]
    contact = cv.get("contact") or {}
    main, side = [], []
    if number == 1:
        main.append("\n".join(x for x in (contact.get("name"), cv.get("headline"), cv.get("summary")) if x) + "\n")
    else:
        main.append(f"{contact.get('name', '')} (suite)\n")
    exp = "\n\n".join(_experience_text(cv["experiences"][i]) for i in page["experiences"])
    main.append(_section(h_exp, exp))
    edu = "\n\n".join(_education_text(cv["education"][i]) for i in page["education"])
    main.append(_section(h_edu, edu))
    side.append(_section(h_contact, _contact_text(contact) if page["contact"] else ""))
    side.append(_section(h_skills, _skills_text(cv, page["skills"])))
    if number == 1:
        side.append(_section(h_lang, "\n".join(cv.get("languages") or [])))
        side.append(_section(h_cert, _certifications_text(cv)))
    return {"main": "\n".join(b for b in main if b), "side": "\n".join(b for b in side if b)}


def _put_text(page, rect, text: str) -> None:
    """Insère ``text`` dans ``rect`` en réduisant la police jusqu'à ce que tout tienne."""
    if not text.strip():
        return
    for size in FONT_SIZES:
        if page.insert_textbox(rect, text, fontsize=size, fontname="helv") >= 0:
            return
    raise PageInvariantError("le contenu d'une page déborde : réduire le contenu ou le découpage")


def _render_text_doc(cv, plan, lang: str, layout: str, name: str) -> pymupdf.Document:
    doc = pymupdf.open()
    n = plan["n_pages"]
    for number in range(1, n + 1):
        page = doc.new_page(width=PAGE_W, height=PAGE_H)
        blocks = _page_blocks(cv, plan, number, lang)
        bottom = PAGE_H - 40
        if layout == "two_columns":
            _put_text(page, pymupdf.Rect(MARGIN, MARGIN, MARGIN + SIDEBAR_W, bottom), blocks["side"])
            _put_text(page, pymupdf.Rect(MARGIN + SIDEBAR_W + 16, MARGIN, PAGE_W - MARGIN, bottom), blocks["main"])
        else:
            merged = "\n".join(b for b in (blocks["main"], blocks["side"]) if b)
            _put_text(page, pymupdf.Rect(MARGIN, MARGIN, PAGE_W - MARGIN, bottom), merged)
        page.insert_text((MARGIN, PAGE_H - 20), f"{name} - page {number}/{n}", fontsize=8)
    return doc


def _scan_doc(doc: pymupdf.Document, scanned: List[int]) -> pymupdf.Document:
    """Remplace les pages ``scanned`` (base 1) par leur rendu image, sans couche texte."""
    out = pymupdf.open()
    for index, page in enumerate(doc, start=1):
        if index in scanned:
            new = out.new_page(width=page.rect.width, height=page.rect.height)
            new.insert_image(new.rect, pixmap=page.get_pixmap(dpi=SCAN_DPI))
        else:
            out.insert_pdf(doc, from_page=index - 1, to_page=index - 1)
    return out


def _squash(text: str) -> str:
    return " ".join(text.split())


def check_page_invariant(page_texts: List[str], facts: List[Dict[str, Any]], skip_pages=()) -> None:
    """Lève ``PageInvariantError`` si un fait n'est pas dans le texte de sa page cible."""
    for fact in facts:
        page = fact["page"]
        if page in skip_pages:
            continue
        text = _squash(page_texts[page - 1]) if page <= len(page_texts) else ""
        if _squash(fact["fait"]) not in text:
            raise PageInvariantError(f"fait {fact['fait']!r} ({fact['champ']}) absent de la page {page}")


def _scanned_pages(option: str, n_pages: int) -> List[int]:
    if option == "all":
        return list(range(1, n_pages + 1))
    if option == "after_first":
        return list(range(2, n_pages + 1))
    return []


def _save(doc: pymupdf.Document, path: Path, **kwargs) -> None:
    doc.set_metadata({})
    doc.save(str(path), garbage=4, deflate=True, no_new_id=True, **kwargs)
    doc.close()


def _generate_one(case: Dict[str, Any], ref: Dict[str, Any], out_dir: Path) -> Dict[str, Any]:
    case_id, category = case["case_id"], case["category"]
    options = case.get("options") or {}
    path = out_dir / f"{case_id}.pdf"
    cv, facts = case_profile(case, ref), case_facts(case, ref)
    entry = {"case_id": case_id, "path": str(path), "category": category, "n_pages": 0,
             "facts": facts, "scanned_pages": [], "profile_id": case.get("profile_id")}
    if category == "unreadable":
        path.write_bytes(CORRUPT_BYTES)
        return entry
    if category == "empty":
        doc = pymupdf.open()
        doc.new_page(width=PAGE_W, height=PAGE_H)
        entry["n_pages"] = 1
        _save(doc, path)
        return entry
    if cv is None:
        raise ValueError(f"cas {case_id} : profil requis pour la catégorie {category}")

    plan = plan_pages(cv, facts)
    name = (cv.get("contact") or {}).get("name", case_id)
    doc = _render_text_doc(cv, plan, case_language(case, ref), options.get("layout", "one_column"), name)
    texts = [p.get_text() for p in doc]
    check_page_invariant(texts, facts)
    scanned = _scanned_pages(options.get("scan", "none"), plan["n_pages"])
    entry.update(n_pages=plan["n_pages"], scanned_pages=scanned)
    if scanned:
        doc = _scan_doc(doc, scanned)
    if category == "protected":
        _save(doc, path, encryption=pymupdf.PDF_ENCRYPT_AES_256,
              user_pw=options.get("password", DEFAULT_PASSWORD), owner_pw=DEFAULT_PASSWORD + "-owner")
        return entry
    _save(doc, path)
    check_page_invariant(extract_page_texts(str(path)), facts, skip_pages=scanned)
    return entry


def generate_cases(cases: List[Dict[str, Any]], ref: Dict[str, Any], out_dir=DEFAULT_OUT) -> List[Dict[str, Any]]:
    """Génère les PDF des ``cases`` dans ``out_dir`` et renvoie (et écrit) le manifeste."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = [_generate_one(case, ref, out_dir) for case in cases]
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="dossier de sortie des PDF et du manifeste")
    args = parser.parse_args(argv)
    manifest = generate_cases(load_cases(), load_reference(), args.out)
    by_category: Dict[str, int] = {}
    for entry in manifest:
        by_category[entry["category"]] = by_category.get(entry["category"], 0) + 1
    print(f"{len(manifest)} PDF écrits dans {args.out} :")
    for category in CATEGORIES:
        print(f"  {category:14s} {by_category.get(category, 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
