"""Banc de couverture de l'import de CV, branché sur le vrai pipeline ``parse_cv_with_llm``.

Il lit le manifeste des PDF synthétiques (``cv_reference_pdfs.py``) et fait passer chaque
PDF dans le pipeline réel (VLM sur 3 pages, complément texte, repli texte).

Mode simulé (défaut, aucun réseau) : ``acompletion`` est remplacé par un oracle parfait.
Il mesure la COUVERTURE DU PIPELINE (pages, repli, scans, complément), pas la qualité du
modèle. Mode réel (``--real --confirm``) : ``acompletion`` est celui du fournisseur ; chaque
cas passe par ``check_budget`` puis ``record_call`` (part ``parser`` du registre commun).
``--real`` seul n'imprime que l'estimation.

Usage :
    uv run python scripts/cv_reference_bench.py                 # simulé
    uv run python scripts/cv_reference_bench.py --real          # estimation seule
    uv run python scripts/cv_reference_bench.py --real --confirm
    uv run python scripts/cv_reference_bench.py --method text|ocr|vlm   # méthode comparée (défaut vlm)

``--method text`` force le chemin texte (rendu des pages neutralisé, code de production inchangé) ;
``--method ocr`` envoie le PDF à l'OCR Mistral (``cv_ocr.py``) puis au LLM texte, par défaut sur les
catégories ``scanned``, ``mixed_scanned`` et ``two_columns`` ; en mode simulé l'OCR est un stub
reconstruit depuis la vérité du cas (OCR simulé, aucun réseau).
"""

import argparse
import asyncio
import contextlib
import json
import os
import sys
import time
import unicodedata
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import cv_parser  # noqa: E402
from scripts import llm_budget  # noqa: E402
from scripts.cv_ocr import OCR_MODEL, OCR_USD_PER_PAGE, ocr_pdf  # noqa: E402
from scripts.cv_reference_pdfs import (  # noqa: E402
    CATEGORIES, DEFAULT_OUT, case_profile, date_range, generate_cases, load_cases, plan_pages,
)
from scripts.reference_dataset import load_reference  # noqa: E402

SCRIPT_NAME = "cv_reference_bench.py"
SIMULATED_KEY = "dummy-simulated-key"
IMAGE_TOKENS = 1500
REJECTION_CATEGORIES = ("protected", "unreadable", "empty")
SECTIONS = ("headline", "summary", "experiences", "projects", "education", "certifications",
            "languages", "interests", "skills", "contact")
# Prix en $ par million de tokens (entrée, sortie). Modèle inconnu : tarif le plus élevé connu.
# Prix vérifiés le 2026-11-08 : ministral-14b-2512 (docs.mistral.ai/models/ministral-3-14b-25-12 ; LiteLLM 2e-07/2e-07),
# gpt-4o-mini (0,15 / 0,60).
PRICES_USD_PER_M = {
    "mistral/pixtral-large-latest": (2.0, 6.0),
    "mistral/ministral-14b-2512": (0.20, 0.20),
    "openai/gpt-4o-mini": (0.15, 0.60),
}
FALLBACK_PRICE = (2.0, 6.0)
PILOT_TARGETS = {"min_pdfs": 20, "invented_facts": 0, "experience_recall": 0.95, "budget_usd": 0.25}
REAL_ONLY_MEASURES = (
    "qualité d'extraction du VLM et du LLM texte (champs, dates, intitulés)",
    "faits inventés par un vrai modèle (l'oracle simulé n'invente jamais)",
    "coût réel facturé et usages indisponibles côté fournisseur",
    "durée réelle des appels et fiabilité du fournisseur (erreurs, JSON invalide)",
)
SIMULATION_NOTE = "mode simulé : couverture du pipeline, pas qualité du modèle"
METHODS = ("vlm", "text", "ocr")
OCR_DEFAULT_CATEGORIES = ("scanned", "mixed_scanned", "two_columns")
OCR_USAGE_MODEL = f"mistral/{OCR_MODEL}"


# --------------------------------------------------------------------------- utilitaires

def normalize(value: Any) -> str:
    """Comparaison insensible à la casse, aux accents et aux espaces multiples."""
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.casefold().split())


def _squash(value: Any) -> str:
    return " ".join(str(value or "").split())


def price_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = PRICES_USD_PER_M.get(model, FALLBACK_PRICE)
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


def usage_cost_usd(usages: List[Dict[str, Any]]) -> float:
    """Coût des usages ; une entrée OCR porte son coût (``pages`` x 0,002 $), pas des tokens."""
    return sum(u["cost_usd"] if "pages" in u else
               price_usd(u.get("model", ""), u.get("input_tokens", 0), u.get("output_tokens", 0)) for u in usages)


# --------------------------------------------------------------------------- oracle simulé

def build_truth(case: Dict[str, Any], entry: Dict[str, Any], ref: Dict[str, Any]) -> Dict[str, Any]:
    """CV de vérité d'un cas : profil source, faits, et page de chaque élément."""
    cv = case_profile(case, ref) or {}
    facts = entry["facts"]
    return {"cv": cv, "facts": facts, "plan": plan_pages(cv, facts) if cv else {"n_pages": 0, "pages": []}}


def _element_pages(truth: Dict[str, Any]) -> Dict[str, Any]:
    pages: Dict[str, Any] = {"experiences": {}, "education": {}, "skills": {}, "contact": 1}
    for number, page in enumerate(truth["plan"]["pages"], start=1):
        pages["experiences"].update({i: number for i in page["experiences"]})
        pages["education"].update({i: number for i in page["education"]})
        pages["skills"].update({cat: number for cat in page["skills"]})
        if page["contact"]:
            pages["contact"] = number
    return pages


def _truth_payload(truth: Dict[str, Any], keep: Callable[[int, str], bool]) -> Dict[str, Any]:
    """Éléments du CV de vérité retenus par ``keep(page, texte_identifiant)``."""
    cv, where = truth["cv"], _element_pages(truth)
    if not cv:
        return {}
    contact = cv.get("contact") or {}
    payload: Dict[str, Any] = {
        "headline": cv.get("headline") if keep(1, cv.get("headline") or "") else "",
        "summary": cv.get("summary") if keep(1, cv.get("summary") or "") else "",
        "experiences": [
            {"company": e["company"], "role": e["role"], "start": e.get("start_date"),
             "end": None if e.get("end_date") in (None, "present") else e["end_date"],
             "missions": e.get("missions") or [], "stack": e.get("stack") or []}
            for i, e in enumerate(cv.get("experiences") or []) if keep(where["experiences"][i], e["company"])
        ],
        "education": [e for i, e in enumerate(cv.get("education") or []) if keep(where["education"][i], e["degree"])],
        "languages": [x for x in cv.get("languages") or [] if keep(1, x)],
        "certifications": [c for c in cv.get("certifications") or [] if keep(1, c["name"])],
        "contact": {k: v for k, v in contact.items() if k == "email"} if keep(where["contact"], contact.get("email") or "") else {},
        "skills": {},
    }
    for cat, items in (cv.get("skills") or {}).items():
        kept = [s for s in items if keep(where["skills"][cat], s)]
        if kept:
            payload["skills"][cat] = kept
    return payload


def _cv_text_of(prompt: str) -> str:
    """Texte du CV dans le prompt texte (entre les balises <cv_text> et </cv_text>)."""
    # rfind : la consigne mentionne elle-même la balise (« entre les balises <cv_text> »), avant le vrai bloc.
    start, end = prompt.rfind("<cv_text>"), prompt.rfind("</cv_text>")
    return prompt[start + len("<cv_text>"):end] if 0 <= start < end else prompt


def make_oracle(truth: Dict[str, Any], calls: Optional[List[Dict[str, Any]]] = None):
    """Faux ``acompletion`` parfait par construction.

    Appel VLM (``content`` liste) : éléments dont la page cible est <= nombre d'images reçues.
    Appel texte (``content`` chaîne) : éléments dont le texte identifiant figure littéralement
    dans le texte reçu. Usage : caractères / 4, plus 1 500 par image.
    """

    async def fake(*, model=None, messages=None, **kwargs):
        content = messages[0]["content"]
        if isinstance(content, list):
            images = sum(1 for part in content if part.get("type") == "image_url")
            chars = sum(len(part.get("text", "")) for part in content if part.get("type") == "text")
            payload = _truth_payload(truth, lambda page, _text: page <= images)
            kind = "vlm"
        else:
            images, chars, kind = 0, len(content), "text"
            haystack = _squash(_cv_text_of(content))
            payload = _truth_payload(truth, lambda _page, text: bool(text) and _squash(text) in haystack)
        body = json.dumps(payload, ensure_ascii=False)
        prompt_tokens, completion_tokens = chars // 4 + IMAGE_TOKENS * images, len(body) // 4
        if calls is not None:
            calls.append({"kind": kind, "images": images, "prompt_tokens": prompt_tokens})
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=body))],
            usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
        )

    return fake


def make_ocr_stub(truth: Dict[str, Any]):
    """Faux ``ocr_pdf`` (OCR simulé) : le texte attendu de chaque page, reconstruit depuis la vérité."""

    def fake(_path: str, model: str = OCR_MODEL):
        n_pages = truth["plan"]["n_pages"]
        texts: List[str] = [""] * n_pages
        cv = truth["cv"]
        if cv:
            where = _element_pages(truth)

            def put(page: int, *parts: Any) -> None:
                texts[min(max(page, 1), n_pages) - 1] += "\n".join(str(x) for x in parts if x) + "\n"

            put(1, cv.get("headline"), cv.get("summary"), *(cv.get("languages") or []),
                *(c["name"] for c in cv.get("certifications") or []))
            put(where["contact"], (cv.get("contact") or {}).get("email"))
            for i, e in enumerate(cv.get("experiences") or []):
                put(where["experiences"][i], e["company"], e["role"], *(e.get("missions") or []))
            for i, e in enumerate(cv.get("education") or []):
                put(where["education"][i], e["degree"])
            for cat, items in (cv.get("skills") or {}).items():
                put(where["skills"][cat], *items)
        return texts, n_pages

    return fake


# --------------------------------------------------------------------------- métriques

def _experience_dates(e: Dict[str, Any]) -> str:
    return f"{e.get('start') or ''} - {e.get('end') or 'present'}"


def compute_metrics(facts: List[Dict[str, Any]], truth_cv: Dict[str, Any], result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Champs extraits, rappel des expériences, omissions et faits inventés."""
    result = result or {}
    extracted = [e for e in result.get("experiences") or [] if isinstance(e, dict)]
    extracted_companies = {normalize(e.get("company")) for e in extracted}
    company_facts = [f["fait"] for f in facts if f["champ"] == "experiences.company"]
    missed = [c for c in company_facts if normalize(c) not in extracted_companies]
    recall = (len(company_facts) - len(missed)) / len(company_facts) if company_facts else None

    experiences = truth_cv.get("experiences") or []
    # Écart assumé avec le brief (« aucun fait du cas ») : les faits n'annotent qu'une partie des
    # expériences (ex. p03, p04 : certaines n'ont aucun fait). Sans les entreprises du CV de vérité,
    # une expérience réelle mais non annotée serait comptée à tort comme inventée.
    known_companies = {normalize(c) for c in company_facts} | {normalize(e.get("company")) for e in experiences}
    invented = [f"experiences.company : {e.get('company')}" for e in extracted
                if normalize(e.get("company")) not in known_companies]

    critical = {f["champ"] for f in facts if f.get("critique")}
    truth_skills = {normalize(s) for items in (truth_cv.get("skills") or {}).values() for s in items}
    checks = {
        "experiences.role": ({normalize(e.get("role")) for e in experiences},
                             [e.get("role") for e in extracted if e.get("role")]),
        "experiences.dates": ({normalize(date_range(e)) for e in experiences},
                              [_experience_dates(e) for e in extracted if e.get("start")]),
        "contact.email": ({normalize((truth_cv.get("contact") or {}).get("email"))},
                          [(result.get("contact") or {}).get("email")] if (result.get("contact") or {}).get("email") else []),
        "education.degree": ({normalize(e.get("degree")) for e in truth_cv.get("education") or []},
                             [e.get("degree") for e in result.get("education") or [] if isinstance(e, dict) and e.get("degree")]),
        "skills": (truth_skills, [s for items in (result.get("skills") or {}).values() for s in items]),
    }
    for champ, (allowed, values) in checks.items():
        if champ in critical:
            invented += [f"{champ} : {v}" for v in values if normalize(v) not in allowed]

    return {
        "fields_extracted": sum(1 for key in SECTIONS if result.get(key)),
        "experience_recall": recall,
        "missed_experiences": missed,
        "invented_facts": invented,
    }


def evidence_page_accuracy(facts: List[Dict[str, Any]], result: Optional[Dict[str, Any]],
                           report: Optional[Dict[str, Any]]) -> Optional[float]:
    """Part des expériences avec provenance dont la page est celle du fait ``experiences.company``.

    ``None`` s'il n'y a aucune entrée comparable (pas de rapport, pas de provenance, pas de fait).
    """
    experiences = (result or {}).get("experiences") or []
    fact_pages = {normalize(f["fait"]): f["page"] for f in facts if f["champ"] == "experiences.company"}
    checks = []
    for entry in (report or {}).get("evidence") or []:
        if entry["section"] != "experiences" or entry["index"] >= len(experiences):
            continue
        expected = fact_pages.get(normalize(experiences[entry["index"]].get("company")))
        if expected is not None:
            checks.append(entry["page"] == expected)
    return sum(checks) / len(checks) if checks else None


# --------------------------------------------------------------------------- exécution d'un cas

def estimate_case_usd(entry: Dict[str, Any], vlm_model: str, text_model: str, method: str = "vlm") -> float:
    """Estimation avant appel. ``vlm`` : 3 pages au plus puis complément texte ; ``text`` : LLM texte
    seul ; ``ocr`` : pages x prix OCR plus LLM texte."""
    if entry["category"] in ("protected", "unreadable"):
        return 0.0
    pages = entry["n_pages"]
    if method in ("text", "ocr"):
        cost = price_usd(text_model, 800 + 700 * pages, 1500)
        return cost + pages * OCR_USD_PER_PAGE if method == "ocr" else cost
    images = min(pages, cv_parser.VLM_MAX_PAGES)
    cost = price_usd(vlm_model, 900 + IMAGE_TOKENS * images, 1500)
    if pages > cv_parser.VLM_MAX_PAGES:
        cost += price_usd(text_model, 800 + 700 * (pages - cv_parser.VLM_MAX_PAGES), 1500)
    return cost


async def _call_pipeline(path: str) -> Dict[str, Any]:
    """Même enchaînement que la route d'import : PDF chiffré, PDF illisible, pipeline, profil vide."""
    out: Dict[str, Any] = {"result": None, "error": None, "rejected": None, "usage": [], "report": None}
    if await asyncio.to_thread(cv_parser.is_pdf_password_protected, path):
        out["rejected"] = cv_parser.PROTECTED_PDF_MESSAGE
        return out
    if not await asyncio.to_thread(cv_parser.is_pdf_readable, path):
        out["rejected"] = cv_parser.UNREADABLE_PDF_MESSAGE
        return out
    try:
        result = await cv_parser.parse_cv_with_llm(pdf_path=path)
        if cv_parser.is_empty_extraction(result):  # rejeté : ni profil, ni usage enregistré par la route
            out["rejected"] = cv_parser.EMPTY_CV_MESSAGE
            out["usage"] = list(result.get("_usage") or [])
            out["report"] = result.get("_import_report")
        else:
            out["result"] = result
    except Exception as exc:  # le banc ne plante jamais sur un cas : l'erreur est une mesure
        out["error"] = f"{type(exc).__name__} : {exc}"
        out["usage"] = list(getattr(exc, "usage", None) or [])
        out["exception"] = exc
    return out


def _page_metrics(entry, outcome, report, method: str = "vlm", failed: bool = False,
                  expected_rejection: bool = False) -> Dict[str, Any]:
    """Couverture des pages. Un import en échec compte 0 page couverte ; un rejet attendu reste hors moyenne."""
    if report is None:
        return {"total_pages": entry["n_pages"], "pages_by_method": {"vlm": [], "text": [], "ocr": []},
                "skipped_pages": [], "fallback_used": None,
                "pages_covered": 0.0 if failed and not expected_rejection and entry["n_pages"] else None}
    total = report["total_pages"]
    by_method = {"vlm": [], "text": [], "ocr": [], **report["pages_by_method"]}
    if method == "ocr":  # le texte de ces pages vient de l'OCR, pas de la couche texte du PDF
        by_method = {"vlm": [], "text": [], "ocr": by_method["text"]}
    covered = 1 - len(report["skipped_pages"]) / total if total else None
    if expected_rejection:
        covered = None
    elif failed and total:
        covered = 0.0
    return {
        "total_pages": total, "pages_by_method": by_method, "skipped_pages": report["skipped_pages"],
        "pages_covered": covered,
        "fallback_used": report["fallback_used"],
    }


def _expectation_met(category, outcome, result) -> Optional[bool]:
    if category not in REJECTION_CATEGORIES:
        return None
    return bool(outcome["rejected"]) and not result


def _ocr_page_source(path: str, ocr_fn: Callable[..., Any], state: Dict[str, Any]) -> Callable[[str], List[str]]:
    """``extract_page_texts`` de remplacement : un seul appel OCR par PDF (résultat ou erreur mémorisé)."""

    def source(_pdf_path: str) -> List[str]:
        if "error" in state:
            raise state["error"]
        if "texts" not in state:
            try:
                state["texts"], state["pages"] = ocr_fn(path)
            except Exception as exc:
                state["error"] = exc
                raise
        return state["texts"]

    return source


async def _run_case(entry, case, ref, mode, oracle_factory, method="vlm", ocr_factory=None) -> Dict[str, Any]:
    truth = build_truth(case, entry, ref)
    calls: List[Dict[str, Any]] = []
    ocr_state: Dict[str, Any] = {}
    started = time.perf_counter()
    with contextlib.ExitStack() as stack:
        if mode == "simulated":
            stack.enter_context(patch.dict(os.environ, {"MISTRAL_API_KEY": SIMULATED_KEY}))
            stack.enter_context(patch("app.services.cv_parser.acompletion", oracle_factory(truth, calls)))
        if method in ("text", "ocr"):  # chemin texte forcé, sans toucher au code de production
            stack.enter_context(patch("app.services.cv_parser.render_pdf_pages_to_base64_images", return_value=[]))
        if method == "ocr":
            ocr_fn = (ocr_factory or make_ocr_stub)(truth) if mode == "simulated" else ocr_pdf
            source = _ocr_page_source(entry["path"], ocr_fn, ocr_state)
            stack.enter_context(patch("app.services.cv_parser.extract_page_texts", source))
            stack.enter_context(patch("app.services.cv_parser.extract_text_from_pdf",
                                      lambda _p, start_page=0: "\n\n".join(source(_p)[start_page:])))
        outcome = await _call_pipeline(entry["path"])
    duration = time.perf_counter() - started

    result = outcome["result"]
    usage = (result.pop("_usage", None) or []) if result else outcome["usage"]
    if "pages" in ocr_state:
        pages_billed = ocr_state["pages"]
        usage = [*usage, {"model": OCR_USAGE_MODEL, "pages": pages_billed, "cost_usd": pages_billed * OCR_USD_PER_PAGE}]
    report = result.pop("_import_report", None) if result else outcome["report"]
    errors = list(report["errors"]) if report else []
    if outcome["error"]:
        errors.append(outcome["error"])
    if outcome["rejected"]:
        errors.append(outcome["rejected"])
    metrics = compute_metrics(entry["facts"], truth["cv"], result)
    metrics["evidence_page_accuracy"] = evidence_page_accuracy(entry["facts"], result, report)
    category = entry["category"]
    expected_rejection = category in REJECTION_CATEGORIES or bool(outcome["rejected"])
    pages = _page_metrics(entry, outcome, report, method, failed=result is None,
                          expected_rejection=category in REJECTION_CATEGORIES)
    if expected_rejection:  # évalué sur le rejet lui-même, pas sur le rappel
        metrics["experience_recall"], metrics["missed_experiences"] = None, []
    skipped = set(pages["skipped_pages"])
    unavailable = sum(1 for u in usage if "pages" not in u and not u.get("input_tokens") and not u.get("output_tokens"))
    if outcome["error"] and not usage and category not in REJECTION_CATEGORIES:
        unavailable += 1
    return {
        "case_id": entry["case_id"], "category": category, "profile_id": entry["profile_id"], "method": method,
        **metrics, **pages,
        "critical_facts_beyond_vlm": sum(1 for f in entry["facts"] if f["page"] > cv_parser.VLM_MAX_PAGES and f.get("critique")),
        "n_company_facts": 0 if expected_rejection else sum(1 for f in entry["facts"] if f["champ"] == "experiences.company"),
        "facts_lost_on_skipped_pages": sum(1 for f in entry["facts"] if f["page"] in skipped and f.get("critique")),
        "rejected": outcome["rejected"], "errors": errors,
        "false_rejection": category not in REJECTION_CATEGORIES and (
            bool(outcome["rejected"]) or bool(outcome["error"]) or result is None), "duration_s": round(duration, 4),
        "cost_usd": usage_cost_usd(usage), "usage": usage, "usage_unavailable": unavailable, "n_calls": len(calls),
        "expected_rejection": expected_rejection,
        "expectation_met": _expectation_met(category, outcome, result),
        "completed": result is not None, "cost_recorded": False,
    }


# --------------------------------------------------------------------------- agrégats et résumé

def _aggregate(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_facts = sum(r["n_company_facts"] for r in rows)
    missed = sum(len(r["missed_experiences"]) for r in rows)
    covered = [r["pages_covered"] for r in rows if r["pages_covered"] is not None]
    accuracies = [r["evidence_page_accuracy"] for r in rows if r["evidence_page_accuracy"] is not None]
    return {
        "n_cases": len(rows),
        "experience_recall": (total_facts - missed) / total_facts if total_facts else None,
        "missed_experiences": missed,
        "invented_facts": sum(len(r["invented_facts"]) for r in rows),
        "pages_covered": sum(covered) / len(covered) if covered else None,
        "false_rejections": sum(1 for r in rows if r["false_rejection"]),
        "evidence_page_accuracy": sum(accuracies) / len(accuracies) if accuracies else None,
        "errors": sum(len(r["errors"]) for r in rows),
        "expectations_met": sum(1 for r in rows if r["expectation_met"]),
        "expected_rejections": sum(1 for r in rows if r["expected_rejection"]),
        "cost_usd": sum(r["cost_usd"] for r in rows),
        "duration_s": sum(r["duration_s"] for r in rows),
        "usage_unavailable": sum(r["usage_unavailable"] for r in rows),
    }


def aggregate(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_category = {c: _aggregate([r for r in rows if r["category"] == c]) for c in CATEGORIES
                   if any(r["category"] == c for r in rows)}
    return {"by_category": by_category, "global": _aggregate(rows)}


def pilot_targets(agg: Dict[str, Any], rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Cibles du pilote mises en regard des mesures (rapportées, jamais assertées)."""
    g = agg["global"]
    present = {r["category"] for r in rows}
    recall = g["experience_recall"]
    t = PILOT_TARGETS
    return [
        {"cible": f"au moins {t['min_pdfs']} PDF, toutes catégories", "mesure": f"{g['n_cases']} PDF, {len(present)}/{len(CATEGORIES)} catégories",
         "atteinte": g["n_cases"] >= t["min_pdfs"] and present == set(CATEGORIES)},
        {"cible": "zéro fait inventé (faits critiques)", "mesure": str(g["invented_facts"]), "atteinte": g["invented_facts"] == t["invented_facts"]},
        {"cible": "rappel des expériences >= 95 %", "mesure": "n/a" if recall is None else f"{recall:.1%}",
         "atteinte": recall is not None and recall >= t["experience_recall"]},
        {"cible": f"coût <= {t['budget_usd']:.2f} $ (part parser)", "mesure": f"{g['cost_usd']:.4f} $", "atteinte": g["cost_usd"] <= t["budget_usd"]},
    ]


def _pct(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def render_summary(mode: str, rows: List[Dict[str, Any]], agg: Dict[str, Any], targets: List[Dict[str, Any]],
                   method: str = "vlm") -> str:
    lines = [f"# Banc de couverture de l'import de CV ({mode}, méthode {method})", ""]
    if mode == "simulated":
        lines += [f"**{SIMULATION_NOTE}.** L'oracle est parfait par construction.", ""]
        if method == "ocr":
            lines += ["**OCR simulé** : le texte de chaque page est reconstruit depuis la vérité du cas, aucun appel OCR.", ""]
    lines += ["| Catégorie | Cas | Rappel exp. | Omises | Inventés | Pages couvertes | Erreurs | Coût $ | Durée s |",
              "|---|---|---|---|---|---|---|---|---|"]
    for name, a in [*agg["by_category"].items(), ("**global**", agg["global"])]:
        lines.append(f"| {name} | {a['n_cases']} | {_pct(a['experience_recall'])} | {a['missed_experiences']} | {a['invented_facts']} "
                     f"| {_pct(a['pages_covered'])} | {a['errors']} "
                     f"| {a['cost_usd']:.4f} | {a['duration_s']:.2f} |")
    g = agg["global"]
    lines += ["", f"Faux rejets : {g['false_rejections']} ; exactitude des pages de provenance : {_pct(g['evidence_page_accuracy'])}."]
    long_rows = [r for r in rows if r["category"] == "long"]
    if method == "vlm" and long_rows:
        beyond = sum(r["critical_facts_beyond_vlm"] for r in long_rows)
        lost = sum(r["facts_lost_on_skipped_pages"] for r in long_rows)
        lines += [f"Catégorie long (vlm) : faits critiques des pages 4 et suivantes, {beyond - lost} retrouvés (complément texte), "
                  f"{lost} perdus (pages non couvertes), sur {beyond}."]
    lines += ["", "## Cibles du pilote (rapportées, non assertées)", ""]
    lines += [f"- {'OK' if t['atteinte'] else 'NON'} : {t['cible']} -> {t['mesure']}" for t in targets]
    lines += ["", "## Mesures qui exigent un fournisseur réel", ""] + [f"- {m}" for m in REAL_ONLY_MEASURES]
    return "\n".join(lines)


# --------------------------------------------------------------------------- banc

async def run_bench(manifest, cases, ref, mode: str = "simulated", confirm: bool = False, out_dir=DEFAULT_OUT,
                    oracle_factory=make_oracle, method: str = "vlm", ocr_factory=None) -> Dict[str, Any]:
    """Fait passer chaque cas dans le pipeline. ``mode`` : ``simulated`` ou ``real`` ; ``method`` : vlm, text, ocr."""
    if mode not in ("simulated", "real"):
        raise ValueError(f"mode inconnu : {mode!r}")
    if method not in METHODS:
        raise ValueError(f"méthode inconnue : {method!r}")
    entries = {e["case_id"]: e for e in manifest}
    estimates = {c["case_id"]: estimate_case_usd(entries[c["case_id"]], cv_parser.DEFAULT_VLM_MODEL,
                                                 cv_parser.DEFAULT_CV_PARSER_MODEL, method) for c in cases}
    if mode == "real" and not confirm:
        return {"mode": mode, "method": method, "confirmed": False, "estimate_usd": sum(estimates.values()),
                "estimates": estimates, "results": []}
    rows: List[Dict[str, Any]] = []
    out = Path(out_dir)
    for case in cases:
        entry = entries[case["case_id"]]
        if mode == "real":
            try:
                llm_budget.check_budget("parser", estimates[case["case_id"]])
            except llm_budget.BudgetExceeded:
                _write_report(out, mode, method, _build_report(mode, rows, method, partial=True))
                raise
        row = await _run_case(entry, case, ref, mode, oracle_factory, method, ocr_factory)
        if mode == "real" and row["completed"] and row["usage"]:
            models = "+".join(sorted({u.get("model", "?") for u in row["usage"]}))
            llm_budget.record_call("parser", SCRIPT_NAME, models, row["cost_usd"], "estimated",
                                   case_id=row["case_id"], usage_unavailable=row["usage_unavailable"])
            row["cost_recorded"] = True
        rows.append(row)
    report = _build_report(mode, rows, method)
    _write_report(out, mode, method, report)
    return report


def _build_report(mode: str, rows: List[Dict[str, Any]], method: str = "vlm", partial: bool = False) -> Dict[str, Any]:
    agg = aggregate(rows)
    targets = pilot_targets(agg, rows)
    return {"mode": mode, "method": method, "confirmed": True, "partial": partial, "results": rows, "aggregates": agg,
            "pilot_targets": targets, "real_only_measures": list(REAL_ONLY_MEASURES),
            "summary": render_summary(mode, rows, agg, targets, method)}


def _write_report(out: Path, mode: str, method: str, report: Dict[str, Any]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / f"bench_results_{mode}_{method}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _load_manifest(cases, ref, out_dir: Path) -> List[Dict[str, Any]]:
    path = out_dir / "manifest.json"
    if path.exists():
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if {e["case_id"] for e in manifest} >= {c["case_id"] for c in cases} and all(Path(e["path"]).exists() for e in manifest):
            return manifest
    return generate_cases(cases, ref, out_dir)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="dossier des PDF, du manifeste et des résultats")
    parser.add_argument("--real", action="store_true", help="appels fournisseurs réels (estimation seule sans --confirm)")
    parser.add_argument("--confirm", action="store_true", help="avec --real : lance réellement les appels")
    parser.add_argument("--only", nargs="*", help="limiter à ces case_id (prévaut sur le périmètre par défaut de l'OCR)")
    parser.add_argument("--method", choices=METHODS, default="vlm", help="méthode d'extraction comparée")
    args = parser.parse_args(argv)
    ref, out_dir = load_reference(), Path(args.out)
    cases = [c for c in load_cases() if not args.only or c["case_id"] in args.only]
    if args.method == "ocr" and not args.only:  # ailleurs la couche texte est propre : l'OCR coûte sans rien apporter
        cases = [c for c in cases if c["category"] in OCR_DEFAULT_CATEGORIES]
    manifest = _load_manifest(cases, ref, out_dir)
    report = asyncio.run(run_bench(manifest, cases, ref, mode="real" if args.real else "simulated",
                                   confirm=args.confirm, out_dir=out_dir, method=args.method))
    if not report["confirmed"]:
        print(f"Estimation (aucun appel, méthode {args.method}) : {report['estimate_usd']:.4f} $ pour {len(cases)} cas ; "
              f"part parser du registre : {PILOT_TARGETS['budget_usd']:.2f} $. Ajouter --confirm pour lancer.")
        return 0
    print(report["summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
