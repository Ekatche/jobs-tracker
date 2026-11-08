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
# Hypothèses (pixtral-12b, gpt-4o-mini) : à confirmer avant --real --confirm.
PRICES_USD_PER_M = {
    "mistral/pixtral-large-latest": (2.0, 6.0),
    "mistral/pixtral-12b-2409": (0.15, 0.15),
    "openai/gpt-4o-mini": (0.15, 0.60),
}
FALLBACK_PRICE = (2.0, 6.0)
PILOT_TARGETS = {"min_pdfs": 20, "pages_handled": 1.0, "invented_facts": 0, "experience_recall": 0.95, "budget_usd": 0.25}
REAL_ONLY_MEASURES = (
    "qualité d'extraction du VLM et du LLM texte (champs, dates, intitulés)",
    "faits inventés par un vrai modèle (l'oracle simulé n'invente jamais)",
    "coût réel facturé et usages indisponibles côté fournisseur",
    "durée réelle des appels et fiabilité du fournisseur (erreurs, JSON invalide)",
)
SIMULATION_NOTE = "mode simulé : couverture du pipeline, pas qualité du modèle"


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
    return sum(price_usd(u.get("model", ""), u.get("input_tokens", 0), u.get("output_tokens", 0)) for u in usages)


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
    """Texte du CV dans le prompt texte (entre les deux lignes de tirets)."""
    parts = prompt.split("-----------------")
    return parts[1] if len(parts) >= 3 else prompt


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

def estimate_case_usd(entry: Dict[str, Any], vlm_model: str, text_model: str) -> float:
    """Estimation avant appel : VLM sur 3 pages au plus, complément texte au-delà."""
    if entry["category"] in ("protected", "unreadable"):
        return 0.0
    pages = entry["n_pages"]
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


def _page_metrics(entry, outcome, report) -> Dict[str, Any]:
    if report is None:
        handled = bool(outcome["rejected"] or outcome["error"])
        return {"total_pages": entry["n_pages"], "pages_by_method": {"vlm": [], "text": []},
                "skipped_pages": [], "pages_covered": None, "all_pages_handled": handled, "fallback_used": None}
    total = report["total_pages"]
    covered = set(report["pages_by_method"]["vlm"]) | set(report["pages_by_method"]["text"])
    flagged = covered | set(report["skipped_pages"])
    return {
        "total_pages": total, "pages_by_method": report["pages_by_method"], "skipped_pages": report["skipped_pages"],
        "pages_covered": 1 - len(report["skipped_pages"]) / total if total else None,
        "all_pages_handled": set(range(1, total + 1)) <= flagged,
        "fallback_used": report["fallback_used"],
    }


def _expectation_met(category, outcome, result) -> Optional[bool]:
    if category not in REJECTION_CATEGORIES:
        return None
    return bool(outcome["rejected"]) and not result


async def _run_case(entry, case, ref, mode, oracle_factory) -> Dict[str, Any]:
    truth = build_truth(case, entry, ref)
    calls: List[Dict[str, Any]] = []
    started = time.perf_counter()
    with contextlib.ExitStack() as stack:
        if mode == "simulated":
            stack.enter_context(patch.dict(os.environ, {"MISTRAL_API_KEY": SIMULATED_KEY}))
            stack.enter_context(patch("app.services.cv_parser.acompletion", oracle_factory(truth, calls)))
        outcome = await _call_pipeline(entry["path"])
    duration = time.perf_counter() - started

    result = outcome["result"]
    usage = (result.pop("_usage", None) or []) if result else outcome["usage"]
    report = result.pop("_import_report", None) if result else outcome["report"]
    errors = list(report["errors"]) if report else []
    if outcome["error"]:
        errors.append(outcome["error"])
    if outcome["rejected"]:
        errors.append(outcome["rejected"])
    metrics = compute_metrics(entry["facts"], truth["cv"], result)
    metrics["evidence_page_accuracy"] = evidence_page_accuracy(entry["facts"], result, report)
    pages = _page_metrics(entry, outcome, report)
    category = entry["category"]
    expected_rejection = category in REJECTION_CATEGORIES or bool(outcome["rejected"])
    if expected_rejection:  # évalué sur le rejet lui-même, pas sur le rappel
        metrics["experience_recall"], metrics["missed_experiences"] = None, []
    skipped = set(pages["skipped_pages"])
    unavailable = sum(1 for u in usage if not u.get("input_tokens") and not u.get("output_tokens"))
    if outcome["error"] and not usage and category not in REJECTION_CATEGORIES:
        unavailable += 1
    return {
        "case_id": entry["case_id"], "category": category, "profile_id": entry["profile_id"],
        **metrics, **pages,
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
        "all_pages_handled": sum(1 for r in rows if r["all_pages_handled"]),
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
    handled = g["all_pages_handled"] / g["n_cases"] if g["n_cases"] else 0.0
    recall = g["experience_recall"]
    t = PILOT_TARGETS
    return [
        {"cible": f"au moins {t['min_pdfs']} PDF, toutes catégories", "mesure": f"{g['n_cases']} PDF, {len(present)}/{len(CATEGORIES)} catégories",
         "atteinte": g["n_cases"] >= t["min_pdfs"] and present == set(CATEGORIES)},
        {"cible": "100 % des pages traitées ou signalées", "mesure": f"{handled:.0%}", "atteinte": handled >= t["pages_handled"]},
        {"cible": "zéro fait inventé (faits critiques)", "mesure": str(g["invented_facts"]), "atteinte": g["invented_facts"] == t["invented_facts"]},
        {"cible": "rappel des expériences >= 95 %", "mesure": "n/a" if recall is None else f"{recall:.1%}",
         "atteinte": recall is not None and recall >= t["experience_recall"]},
        {"cible": f"coût <= {t['budget_usd']:.2f} $ (part parser)", "mesure": f"{g['cost_usd']:.4f} $", "atteinte": g["cost_usd"] <= t["budget_usd"]},
    ]


def _pct(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value:.0%}"


def render_summary(mode: str, rows: List[Dict[str, Any]], agg: Dict[str, Any], targets: List[Dict[str, Any]]) -> str:
    lines = [f"# Banc de couverture de l'import de CV ({mode})", ""]
    if mode == "simulated":
        lines += [f"**{SIMULATION_NOTE}.** L'oracle est parfait par construction.", ""]
    lines += ["| Catégorie | Cas | Rappel exp. | Omises | Inventés | Pages couvertes | Pages traitées | Erreurs | Coût $ | Durée s |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for name, a in [*agg["by_category"].items(), ("**global**", agg["global"])]:
        lines.append(f"| {name} | {a['n_cases']} | {_pct(a['experience_recall'])} | {a['missed_experiences']} | {a['invented_facts']} "
                     f"| {_pct(a['pages_covered'])} | {a['all_pages_handled']}/{a['n_cases']} | {a['errors']} "
                     f"| {a['cost_usd']:.4f} | {a['duration_s']:.2f} |")
    g = agg["global"]
    lines += ["", f"Faux rejets : {g['false_rejections']} ; exactitude des pages de provenance : {_pct(g['evidence_page_accuracy'])}."]
    lines += ["", "## Cibles du pilote (rapportées, non assertées)", ""]
    lines += [f"- {'OK' if t['atteinte'] else 'NON'} : {t['cible']} -> {t['mesure']}" for t in targets]
    lines += ["", "## Mesures qui exigent un fournisseur réel", ""] + [f"- {m}" for m in REAL_ONLY_MEASURES]
    return "\n".join(lines)


# --------------------------------------------------------------------------- banc

async def run_bench(manifest, cases, ref, mode: str = "simulated", confirm: bool = False, out_dir=DEFAULT_OUT,
                    oracle_factory=make_oracle) -> Dict[str, Any]:
    """Fait passer chaque cas dans le pipeline. ``mode`` : ``simulated`` ou ``real``."""
    if mode not in ("simulated", "real"):
        raise ValueError(f"mode inconnu : {mode!r}")
    entries = {e["case_id"]: e for e in manifest}
    estimates = {c["case_id"]: estimate_case_usd(entries[c["case_id"]], cv_parser.DEFAULT_VLM_MODEL,
                                                 cv_parser.DEFAULT_CV_PARSER_MODEL) for c in cases}
    if mode == "real" and not confirm:
        return {"mode": mode, "confirmed": False, "estimate_usd": sum(estimates.values()),
                "estimates": estimates, "results": []}
    rows: List[Dict[str, Any]] = []
    out = Path(out_dir)
    for case in cases:
        entry = entries[case["case_id"]]
        if mode == "real":
            try:
                llm_budget.check_budget("parser", estimates[case["case_id"]])
            except llm_budget.BudgetExceeded:
                _write_report(out, mode, _build_report(mode, rows, partial=True))
                raise
        row = await _run_case(entry, case, ref, mode, oracle_factory)
        if mode == "real" and row["completed"] and row["usage"]:
            models = "+".join(sorted({u.get("model", "?") for u in row["usage"]}))
            llm_budget.record_call("parser", SCRIPT_NAME, models, row["cost_usd"], "estimated",
                                   case_id=row["case_id"], usage_unavailable=row["usage_unavailable"])
            row["cost_recorded"] = True
        rows.append(row)
    report = _build_report(mode, rows)
    _write_report(out, mode, report)
    return report


def _build_report(mode: str, rows: List[Dict[str, Any]], partial: bool = False) -> Dict[str, Any]:
    agg = aggregate(rows)
    targets = pilot_targets(agg, rows)
    return {"mode": mode, "confirmed": True, "partial": partial, "results": rows, "aggregates": agg,
            "pilot_targets": targets, "real_only_measures": list(REAL_ONLY_MEASURES),
            "summary": render_summary(mode, rows, agg, targets)}


def _write_report(out: Path, mode: str, report: Dict[str, Any]) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / f"bench_results_{mode}.json").write_text(
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
    parser.add_argument("--only", nargs="*", help="limiter à ces case_id")
    args = parser.parse_args(argv)
    ref, out_dir = load_reference(), Path(args.out)
    cases = [c for c in load_cases() if not args.only or c["case_id"] in args.only]
    manifest = _load_manifest(cases, ref, out_dir)
    report = asyncio.run(run_bench(manifest, cases, ref, mode="real" if args.real else "simulated",
                                   confirm=args.confirm, out_dir=out_dir))
    if not report["confirmed"]:
        print(f"Estimation (aucun appel) : {report['estimate_usd']:.4f} $ pour {len(cases)} cas ; "
              f"part parser du registre : {PILOT_TARGETS['budget_usd']:.2f} $. Ajouter --confirm pour lancer.")
        return 0
    print(report["summary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
