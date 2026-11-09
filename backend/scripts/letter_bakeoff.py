#!/usr/bin/env python3
"""Banc de mesure des lettres de motivation et des CV adaptés (jeu de référence).

Compare des VERSIONS DE PROMPTS à modèles, paramètres et entrées constants ; il ne compare
plus des modèles (l'ancien bake-off multi-modèles reste dans l'historique git).

Chaque couple profil/offre de ``scripts/reference/letter_requirements.json`` passe par le
chemin de production : ``run_letter_pipeline_async`` pour la lettre et
``generate_tailored_cv_content`` pour le complément CV (``--no-cv`` pour le couper).

Neutralisé pendant le banc, pour garder une entrée constante : la recherche entreprise
(``cover_letter_crew._get_cached_or_research_company`` renvoie ``""`` : ni Tavily ni LLM
de recherche). La lettre est donc écrite sans contexte entreprise.

Modes (depuis ``backend``) :
  uv run python scripts/letter_bakeoff.py                      estimation seule, aucun appel
  uv run python scripts/letter_bakeoff.py --simulated          pipeline complet hors réseau
  uv run python scripts/letter_bakeoff.py --real               estimation seule (sans --confirm)
  uv run python scripts/letter_bakeoff.py --real --confirm     appels réels, payants
  --limit N  N premiers couples du fichier ; --label NOM  dossier de sortie ;
  --prompts-dir DIR  prompts de lettre à tester (défaut : production) ;
  --reuse-analyst  réutilise la sortie de l'analyste mise en cache par couple ;
  --summarize FEUILLE  métriques des cibles du plan depuis la feuille remplie ;
  --compare RUN_A RUN_B  écart des agrégats entre deux exécutions.

Coût : chaque appel ``acompletion`` (``cover_letter_crew`` et ``cv_tailor``) est enveloppé ;
coût = somme des ``price_usd`` par (modèle, tokens). Un modèle sans prix connu refuse le mode
réel. Estimation par couple (estimation prudente) : voir ``estimate_pair_usd``. Avant chaque couple
en réel confirmé : ``check_budget("lettres", estimation du couple + coût mesuré des échecs non inscrits
depuis le début de l'exécution)``. Après : ``record_call`` seulement
pour une génération complète réussie (la lettre si produite, le CV s'il est produit) ; une
génération en échec, ``CVHonestyError`` compris, n'inscrit aucun coût.

Le CV du banc est généré sans évaluation Bloc B (``evaluation=None``) : il mesure le chemin du
complément seul, pas celui de l'application, qui peut y joindre une évaluation. ``rapport.md`` et
``results.json`` donnent les modèles effectifs par rôle.

Sorties (non versionnées) sous ``scripts/data/letters_bench/<label>/`` : ``results.json``,
``rapport.md``, ``feuille_evaluation.csv`` et ``feuille_violations.csv`` (évaluation humaine).
"""

import argparse
import asyncio
import contextlib
import copy
import csv
import json
import math
import os
import re
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import patch

_BACKEND = Path(__file__).resolve().parent.parent
_PIPELINE_DIR = _BACKEND / "job_trackers" / "src" / "job_trackers"
for _p in (str(_BACKEND), str(_PIPELINE_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scripts import llm_budget  # noqa: E402
from scripts.reference_dataset import load_reference  # noqa: E402

SCRIPT_NAME = "letter_bakeoff.py"
PLAN = "lettres"
DATA_DIR = Path(__file__).resolve().parent / "data" / "letters_bench"
SIMULATED_KEY = "dummy-simulated-key"
# Prix en $ par million de tokens (entrée, sortie). Modèle absent : refus du mode réel.
# Source : MODEL_COST_PER_1K_TOKENS de app/services/usage_tracker.py (x1000 ; gemini Standard tier vérifié
# le 2026-09-16, valable jusqu'au 31/12/2026, puis 1,50 / 7,50 ; gpt-6.1-sol d'après la doc OpenAI du 2026-09-30).
PRICES_USD_PER_M = {
    "gemini/gemini-3.8-flash": (0.75, 3.75),
    "gemini/gemini-3.7-flash": (0.75, 3.75),
    "openai/gpt-6.1-sol": (2.00, 10.00),
}
# Estimation prudente : 3 caractères par token (le français en fait plutôt 3,5 à 4).
CHARS_PER_TOKEN = 3
ESTIMATE_CRITIC_CALLS = 2  # majorant : le second appel (fidélité persistante) est rare
ESTIMATE_OUT_TOKENS = {"analyst": 800, "writer": 1500, "critic": 500, "reviser": 1500, "cv": 2500}
ESTIMATE_LETTER_CHARS = 2200  # lettre de 320 mots, majorée
ESTIMATE_ANALYSIS_CHARS = 3000  # JSON d'analyse transmis au rédacteur et au réviseur
ESTIMATE_REVISER_PASSES = 2
ESTIMATE_CV_ATTEMPTS = 2
ROLE_ENV = {"analyst": ("LETTER_MODEL_ANALYST", "offer_analyst"), "writer": ("LETTER_MODEL_WRITER", "writer"),
            "critic": ("LETTER_MODEL_CRITIC", "critic"), "reviser": ("LETTER_MODEL_REVISER", "reviser")}
PROVIDER_KEYS = {"gemini": "GEMINI_API_KEY", "openai": "OPENAI_API_KEY", "mistral": "MISTRAL_API_KEY",
                 "anthropic": "ANTHROPIC_API_KEY"}
DEFAULT_SIM_FAULTS = {3: "needs_review", 5: "cv_honesty", 8: "letter_error"}
SIMULATION_NOTE = ("mode simulé : prouve que la chaîne tourne (oracle déterministe, défauts injectés) ; "
                   "ces chiffres ne sont PAS une référence de qualité")
SHEET_FIXED = ["profile_id", "offer_id", "metier", "lettre_acceptee", "cv_accepte", "lettre", "cv", "exigences",
               "preuves_exactes", "transferables", "lacunes", "violations", "exigences_avec_preuve"]
SHEET_FILL = ["inventees_lettre", "mauvais_poste_lettre", "inventees_cv", "mauvais_poste_cv",
              "exigences_avec_preuve_couvertes_lettre", "exigences_avec_preuve_couvertes_cv", "affirmations_valides", "naturel_1_5", "notes"]
VIOLATION_COLUMNS = ["profile_id", "offer_id", "document", "violation", "faux_rejet"]


class UnknownPriceError(ValueError):
    """Modèle sans prix connu : un coût de 0 sous-estimerait la dépense."""


def price_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    if model not in PRICES_USD_PER_M:
        raise UnknownPriceError(
            f"prix inconnu pour le modèle {model!r} : ajouter une entrée sourcée à PRICES_USD_PER_M "
            f"(modèles connus : {sorted(PRICES_USD_PER_M)})")
    price_in, price_out = PRICES_USD_PER_M[model]
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


def calls_cost_usd(calls: List[Dict[str, Any]]) -> float:
    return sum(price_usd(c["model"], c["input_tokens"], c["output_tokens"]) for c in calls)


# --------------------------------------------------------------------------- chargement

def _modules():
    """Modules de production, importés à la demande (``--summarize`` et ``--compare`` n'en ont pas besoin)."""
    import cover_letter_crew as crew  # noqa: WPS433
    import letter_llm  # noqa: WPS433
    from app.services import cv_tailor  # noqa: WPS433
    return SimpleNamespace(crew=crew, llm=letter_llm, cv=cv_tailor)


def load_pairs(limit: Optional[int] = None, ref: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    from app.services.profile.merge import build_profile_from_sources
    ref = ref or load_reference()
    profiles = {p["profile_id"]: p for p in ref["profiles"]}
    offers = {o["offer_id"]: o for o in ref["offers"]}
    pairs = []
    for req in ref["letter_requirements"][: limit if limit else None]:
        raw = profiles[req["profile_id"]]
        profile, _conflicts = build_profile_from_sources(raw["sources"])
        pairs.append({"profile_id": req["profile_id"], "offer_id": req["offer_id"], "req": req,
                      "profile": profile, "offer": offers[req["offer_id"]],
                      "metier": (raw.get("subgroup") or {}).get("metier") or ""})
    return pairs


def letter_models(mods) -> Dict[str, str]:
    return {role: os.getenv(env, mods.llm.DEFAULT_MODELS[key]) for role, (env, key) in ROLE_ENV.items()}


def all_models(mods, with_cv: bool) -> List[str]:
    models = set(letter_models(mods).values())
    if with_cv:
        models.add(mods.cv.DEFAULT_CV_MODEL)
    return sorted(models)


def ensure_priced(models: List[str]) -> None:
    for model in models:
        price_usd(model, 0, 0)


def ensure_keys(models: List[str]) -> None:
    missing = sorted({PROVIDER_KEYS[m.split("/")[0]] for m in models
                      if m.split("/")[0] in PROVIDER_KEYS and not os.getenv(PROVIDER_KEYS[m.split("/")[0]])})
    if missing:
        raise SystemExit(f"clé d'API absente pour le mode réel : {', '.join(missing)} (valeur jamais affichée)")


# --------------------------------------------------------------------------- estimation

def _tokens(chars: float) -> int:
    return math.ceil(chars / CHARS_PER_TOKEN)


def estimate_pair_usd(pair: Dict[str, Any], mods, prompts_dir: Path, with_cv: bool = True,
                      analyst_cached: bool = False) -> float:
    """Estimation prudente du coût d'un couple. Entrées : taille réelle des prompts et du profil, à 3 caractères
    par token. Sorties forfaitaires (analyste 800, rédacteur 1 500, critique 500 x 2 appels majorants
    (le second, sur la lettre finale, n'a lieu que si le premier signale des défauts de fidélité),
    réviseur 1 500 x 2 passes, CV 2 500 x 2 essais), au prix du modèle de chaque rôle. Le CV utilise la taille réelle du
    prompt rendu. Les jetons de raisonnement cachés ne sont pas couverts au-delà de ces forfaits."""
    models = letter_models(mods)
    profile_chars = sum(len(json.dumps(pair["profile"].get(k) or [], ensure_ascii=False))
                        for k in ("experiences", "projects", "education"))
    offer_chars = min(len(pair["offer"]["description"]), 3000)
    sizes = {}
    for name in ("01_fond", "02_style", "03_critique", "04_revision"):
        path = Path(prompts_dir) / f"{name}.md"
        sizes[name] = len(path.read_text(encoding="utf-8")) if path.exists() else 6000
    out = ESTIMATE_OUT_TOKENS
    parts = []
    if not analyst_cached:
        parts.append((models["analyst"], _tokens(profile_chars + offer_chars + 1500), out["analyst"]))
    parts.append((models["writer"], _tokens(sizes["01_fond"] + sizes["02_style"] + profile_chars
                                            + ESTIMATE_ANALYSIS_CHARS), out["writer"]))
    parts.extend([(models["critic"], _tokens(sizes["03_critique"] + ESTIMATE_LETTER_CHARS + profile_chars + 500),
                   out["critic"])] * ESTIMATE_CRITIC_CALLS)
    parts.extend([(models["reviser"], _tokens(sizes["04_revision"] + ESTIMATE_LETTER_CHARS + ESTIMATE_ANALYSIS_CHARS
                                              + profile_chars), out["reviser"])] * ESTIMATE_REVISER_PASSES)
    if with_cv:
        cv_prompt = mods.cv.load_tailor_prompt(pair["profile"], pair["offer"], None)
        parts.extend([(mods.cv.DEFAULT_CV_MODEL, _tokens(len(cv_prompt)), out["cv"])] * ESTIMATE_CV_ATTEMPTS)
    return sum(price_usd(model, tin, tout) for model, tin, tout in parts)


# --------------------------------------------------------------------------- oracle simulé

def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:] if text else text


def simulated_letter(pair: Dict[str, Any], flawed: bool = False) -> str:
    """Lettre déterministe bâtie sur les preuves exactes du couple (aucune information inventée)."""
    proofs = [_lower_first(p["preuve"].rstrip(".")) for p in pair["req"]["preuves_exactes"]] or \
        ["mon parcours correspond au poste"]
    needs = ", ".join(_lower_first(x) for x in pair["req"]["exigences"][:3])
    p1 = (f"Votre annonce décrit un travail concret, et je préfère y répondre par des faits plutôt que par des "
          f"promesses. Dans mon parcours, {proofs[0]}. Ce travail m'a obligé à relier les besoins des équipes à des "
          f"choix techniques simples, que l'on peut expliquer et vérifier avec ceux qui les utilisent chaque jour.")
    p2 = (f"Sur les points que vous mentionnez, {needs} sont ceux sur lesquels je peux apporter des éléments précis. "
          + " ".join(f"Par exemple, {p}." for p in proofs[1:3])
          + " Par chacun de ces exemples, j'ai travaillé avec des collègues d'autres métiers, et il m'a fallu expliquer mes "
            "choix avant de les voir adoptés dans le quotidien de l'équipe.")
    p3 = ("Cette expérience correspond à ce que vous attendez pour ce poste, et je propose d'en parler plus "
          "précisément avec vous lors d'un échange, afin de comprendre vos priorités et la manière dont l'équipe "
          "travaille aujourd'hui sur ces sujets, puis de voir où je peux être utile rapidement dans les premières "
          "semaines, sans promettre plus que ce que mes réalisations permettent de démontrer aujourd'hui à votre équipe.")
    if flawed:
        p3 += " Ce serait formidable !"
    return (f"Madame, Monsieur,\n\n{p1}\n\n{p2}\n\n{p3}\n\n"
            "Je vous prie d'agréer, Madame, Monsieur, mes salutations distinguées.")


def _reply(content: str, prompt: str) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content), finish_reason="stop")],
        usage=SimpleNamespace(prompt_tokens=len(prompt) // 4, completion_tokens=max(1, len(content) // 4)))


def make_letter_oracle(pair: Dict[str, Any], fault: Optional[str] = None):
    """Faux ``acompletion`` de la lettre, un par couple. Les deux appels JSON sont l'analyste et le critique
    (le prompt du critique contient ``verdict``, et il ne signale jamais de défaut de fidélité : le second
    appel critique n'a donc jamais lieu en simulation) ; les appels texte sont
    le rédacteur puis le réviseur. ``needs_review`` : brouillon fautif que le réviseur ne corrige pas."""

    async def fake(*, model=None, messages=None, **kwargs):
        prompt = messages[0]["content"]
        if kwargs.get("response_format") and "verdict" in prompt:
            return _reply(json.dumps({"verdict": "pass", "flaws": [], "fidelity_flaws": []}), prompt)
        if kwargs.get("response_format"):  # analyste : seul autre appel JSON
            proofs = pair["req"]["preuves_exactes"]
            return _reply(json.dumps({
                "missions": list(pair["req"]["exigences"][:3]), "target_challenge": pair["offer"]["poste"],
                "guiding_thesis": proofs[0]["preuve"] if proofs else "",
                "career_thread": " ; ".join(p["preuve"] for p in proofs[:2]),
                "offer_terms": list(pair["offer"].get("competences_cles") or [])[:3],
                "requirement_evidence": []}, ensure_ascii=False), prompt)
        if fault == "letter_error":
            raise RuntimeError("panne simulée du fournisseur")
        return _reply(simulated_letter(pair, flawed=fault == "needs_review"), prompt)

    return fake


def make_cv_oracle(pair: Dict[str, Any], fault: Optional[str] = None):
    """Faux ``acompletion`` du CV : reprend fidèlement les expériences du profil ; ``cv_honesty`` ajoute un
    employeur inventé à chaque essai, d'où ``CVHonestyError``."""

    async def fake(*, model=None, messages=None, **kwargs):
        profile = pair["profile"]
        exps = [{"title": e.get("role") or e.get("title") or "", "company": e["company"],
                 "start_date": e.get("start") or "", "end_date": e.get("end") or "Présent",
                 "bullet_points": list(e.get("missions") or [])[:3],
                 "relevant_technologies": list(e.get("stack") or [])}
                for e in profile.get("experiences", [])]
        if fault == "cv_honesty":
            exps.append({"title": "Directeur", "company": "Entreprise Inventée SA", "start_date": "2020-01",
                         "end_date": "2021-01", "bullet_points": ["Poste fictif"], "relevant_technologies": []})
        body = {"target_role_title": pair["offer"]["poste"],
                "professional_summary": profile.get("summary") or profile.get("headline") or "",
                "experiences": exps}
        return _reply(json.dumps(body, ensure_ascii=False), messages[0]["content"])

    return fake


# --------------------------------------------------------------------------- exécution d'un couple

def _recording(inner: Callable, calls: List[Dict[str, Any]]):
    """Enveloppe ``acompletion`` : délègue à ``inner`` et note (modèle, tokens entrée/sortie) de chaque appel réussi."""

    async def wrapper(**kwargs):
        model = kwargs.get("model") or ""
        price_usd(model, 0, 0)  # un modèle sans prix connu ne part jamais
        response = await inner(**kwargs)
        usage = getattr(response, "usage", None)
        calls.append({"model": model, "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                      "output_tokens": getattr(usage, "completion_tokens", 0) or 0})
        return response

    return wrapper


async def _real_acompletion(**kwargs):
    import litellm
    return await litellm.acompletion(**kwargs)


_SECRET = re.compile(r"(sk-[A-Za-z0-9_\-]{8,}|AIza[0-9A-Za-z_\-]{20,}|[A-Za-z0-9_\-]{32,})")


def _safe_error(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {_SECRET.sub('[masqué]', str(exc))[:200]}"


def violation_code(message: str) -> str:
    """Code stable d'une violation : le début du message, avant la première apostrophe, parenthèse ou deux-points."""
    return re.split(r"\s*[:('«]", message, maxsplit=1)[0].strip()


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def _patched_analyst(mods, analyst_cache: Optional[Path], reuse: bool):
    original = mods.crew._call_analyst

    async def analyst(offer_description, candidate_profile, candidate_name="", usage_acc=None):
        if reuse and analyst_cache is not None and analyst_cache.exists():
            return copy.deepcopy(json.loads(analyst_cache.read_text(encoding="utf-8")))
        result = await original(offer_description, candidate_profile, candidate_name, usage_acc=usage_acc)
        if analyst_cache is not None:
            analyst_cache.parent.mkdir(parents=True, exist_ok=True)
            analyst_cache.write_text(json.dumps(result, ensure_ascii=False, default=str), encoding="utf-8")
        return copy.deepcopy(result)

    return analyst


async def _no_company_research(company_name, usage_acc=None):
    return ""


async def _run_letter(pair, mods, inner, prompts_dir, analyst_cache, reuse) -> Dict[str, Any]:
    calls: List[Dict[str, Any]] = []
    started = time.perf_counter()
    out: Dict[str, Any] = {"produced": False, "calls": calls}
    try:
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(mods.crew, "acompletion", _recording(inner, calls)))
            stack.enter_context(patch.object(mods.crew, "PROMPTS_DIR", prompts_dir))
            stack.enter_context(patch.object(mods.crew, "_get_cached_or_research_company", _no_company_research))
            stack.enter_context(patch.object(mods.crew, "_call_analyst", _patched_analyst(mods, analyst_cache, reuse)))
            res = await mods.crew.run_letter_pipeline_async(
                pair["offer"]["description"], pair["profile"], pair["offer"].get("entreprise") or "l'entreprise",
                "", job_title=pair["offer"].get("poste") or "")
    except Exception as exc:  # échec complet de la génération : aucun coût inscrit
        out["error"] = _safe_error(exc)
        out["latency_s"] = round(time.perf_counter() - started, 3)
        out["cost_usd"] = calls_cost_usd(calls)
        return out
    guard = res["guard_report"]
    out.update({"produced": True, "body": res["body"], "words": _word_count(res["body"]),
                "needs_review": bool(guard["is_blocking"]), "violations": list(guard["violations"]),
                "violation_codes": [violation_code(v) for v in guard["violations"]],
                "provider_failures": [{**f, "detail": _SECRET.sub("[masqué]", str(f.get("detail") or ""))[:200]}
                                      for f in res.get("provider_failures", [])], "revised": res.get("revised", False),
                "critic_verdict": (res.get("critic_verdict") or {}).get("verdict"),
                "prompt_version": res.get("prompt_version"), "models": res.get("models"),
                "latency_s": round(time.perf_counter() - started, 3), "cost_usd": calls_cost_usd(calls)})
    return out


async def _run_cv(pair, mods, inner) -> Dict[str, Any]:
    calls: List[Dict[str, Any]] = []
    started = time.perf_counter()
    out: Dict[str, Any] = {"produced": False, "honesty_error": False, "calls": calls}
    try:
        with patch.object(mods.cv, "acompletion", _recording(inner, calls)):
            cv = await mods.cv.generate_tailored_cv_content(pair["profile"], pair["offer"], None)
        out.update({"produced": True, "content": cv.model_dump()})
    except mods.cv.CVHonestyError as exc:
        violations = [str(v) for v in getattr(exc, "violations", [])] or [str(exc)]
        out.update({"honesty_error": True, "violations": violations,
                    "violation_codes": [violation_code(v) for v in violations]})
    except Exception as exc:
        out["error"] = _safe_error(exc)
    out["latency_s"] = round(time.perf_counter() - started, 3)
    out["cost_usd"] = calls_cost_usd(calls)
    return out


async def run_pair(pair, mods, letter_inner, cv_inner, prompts_dir, with_cv, analyst_cache, reuse) -> Dict[str, Any]:
    letter = await _run_letter(pair, mods, letter_inner, prompts_dir, analyst_cache, reuse)
    cv = await _run_cv(pair, mods, cv_inner) if with_cv else None
    return {"profile_id": pair["profile_id"], "offer_id": pair["offer_id"], "metier": pair["metier"],
            "letter": letter, "cv": cv}


# --------------------------------------------------------------------------- banc

def _record_row(row: Dict[str, Any], label: str, prompt_version: Optional[str]) -> float:
    """Inscrit au registre ce qui a été généré avec succès ; renvoie le total inscrit."""
    recorded = 0.0
    for kind, part in (("letter", row["letter"]), ("cv", row["cv"])):
        if not part or not part["produced"]:
            continue
        models = "+".join(sorted({c["model"] for c in part["calls"]})) or "?"
        llm_budget.record_call(PLAN, SCRIPT_NAME, models, part["cost_usd"], "estimated", pair=row["pair"], kind=kind,
                               label=label, prompt_version=prompt_version,
                               input_tokens=sum(c["input_tokens"] for c in part["calls"]),
                               output_tokens=sum(c["output_tokens"] for c in part["calls"]))
        recorded += part["cost_usd"]
    row["recorded_usd"] = recorded
    return recorded


SIM_MODELS = {"analyst": "gemini/gemini-3.8-flash", "critic": "gemini/gemini-3.8-flash",
              "writer": "openai/gpt-6.1-sol", "reviser": "openai/gpt-6.1-sol"}
SIM_CV_MODEL = "gemini/gemini-3.7-flash"


@contextlib.contextmanager
def _simulated_env(mods):
    """Modèles tarifés fixes (lettre via l'environnement, CV via l'attribut lu à l'import) et clés factices :
    estimations et résultat ne dépendent ni de l'environnement local ni de la CI."""
    env = {"GEMINI_API_KEY": SIMULATED_KEY, "OPENAI_API_KEY": SIMULATED_KEY}
    env.update({ROLE_ENV[role][0]: model for role, model in SIM_MODELS.items()})
    with patch.dict(os.environ, env), patch.object(mods.cv, "DEFAULT_CV_MODEL", SIM_CV_MODEL):
        yield


async def run_bench(pairs, mods, mode: str = "estimate", **kwargs) -> Dict[str, Any]:
    """``mode`` : ``estimate`` | ``simulated`` | ``real``. ``real`` sans ``confirm`` : estimation seule.
    ``letter_inner`` / ``cv_inner`` : points d'appel injectables (tests) ; sinon oracle (simulé) ou litellm (réel).
    En simulé, les modèles sont figés avant le calcul des estimations."""
    if mode not in ("estimate", "simulated", "real"):
        raise ValueError(f"mode inconnu : {mode!r}")
    with _simulated_env(mods) if mode == "simulated" else contextlib.nullcontext():
        return await _run_bench(pairs, mods, mode, **kwargs)


def _unrecorded_usd(row: Dict[str, Any]) -> float:
    """Coût mesuré des générations en échec : dépensé, mais volontairement non inscrit au registre."""
    return sum(part["cost_usd"] for part in (row["letter"], row["cv"]) if part and not part["produced"])


async def _run_bench(pairs, mods, mode, confirm: bool = False, out_dir: Path = DATA_DIR,
                     label: Optional[str] = None, prompts_dir: Optional[Path] = None, with_cv: bool = True,
                     reuse_analyst: bool = False, faults: Optional[Dict[int, str]] = None,
                     letter_inner: Optional[Callable] = None, cv_inner: Optional[Callable] = None) -> Dict[str, Any]:
    prompts_dir = Path(prompts_dir) if prompts_dir else mods.crew.PROMPTS_DIR
    label = label or mode
    out_dir = Path(out_dir)
    run_dir = out_dir / label
    cache_dir = out_dir / "analyst_cache" / ("real" if mode == "real" else "simulated")

    def cache_path(pair):
        return cache_dir / f"{pair['profile_id']}__{pair['offer_id']}.json"

    estimates = {f"{p['profile_id']}/{p['offer_id']}": estimate_pair_usd(
        p, mods, prompts_dir, with_cv, reuse_analyst and cache_path(p).exists()) for p in pairs}
    if mode == "estimate" or (mode == "real" and not confirm):
        return {"mode": mode, "confirmed": False, "estimate_usd": sum(estimates.values()), "estimates": estimates}
    if mode == "real" and (run_dir / "results.json").exists():
        raise SystemExit(f"le label {label!r} contient déjà un résultat réel ({run_dir}) : choisir un autre --label")
    faults = DEFAULT_SIM_FAULTS if (faults is None and mode == "simulated") else (faults or {})
    rows: List[Dict[str, Any]] = []
    prompt_version = None
    unrecorded = 0.0  # dépensé en échecs depuis le début de l'exécution, absent du registre
    for index, pair in enumerate(pairs):
        key = f"{pair['profile_id']}/{pair['offer_id']}"
        if mode == "real":
            try:
                llm_budget.check_budget(PLAN, estimates[key] + unrecorded)
            except llm_budget.BudgetExceeded:
                _write_run(run_dir, mode, label, rows, prompts_dir, mods, partial=True)
                raise
        fault = faults.get(index)
        l_inner = letter_inner or (make_letter_oracle(pair, fault) if mode == "simulated" else _real_acompletion)
        c_inner = cv_inner or (make_cv_oracle(pair, fault) if mode == "simulated" else _real_acompletion)
        row = await run_pair(pair, mods, l_inner, c_inner, prompts_dir, with_cv, cache_path(pair), reuse_analyst)
        row["pair"] = key
        row["estimate_usd"] = estimates[key]
        prompt_version = row["letter"].get("prompt_version") or prompt_version
        row["recorded_usd"] = _record_row(row, label, prompt_version) if mode == "real" else 0.0
        unrecorded += _unrecorded_usd(row)
        rows.append(row)
    return _write_run(run_dir, mode, label, rows, prompts_dir, mods, prompt_version=prompt_version)


# --------------------------------------------------------------------------- agrégats et feuilles

def _aggregate(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    letters = [r["letter"] for r in rows if r["letter"]["produced"]]
    cvs = [r["cv"] for r in rows if r["cv"] is not None]
    codes: Dict[str, int] = {}
    for part in letters + cvs:
        for code in part.get("violation_codes", []):
            codes[code] = codes.get(code, 0) + 1
    n_review = sum(1 for p in letters if p["needs_review"])
    return {
        "pairs": len(rows), "letters_produced": len(letters), "letter_errors": len(rows) - len(letters),
        "letters_needs_review": n_review,
        "needs_review_rate": (n_review / len(letters)) if letters else None,
        "cv_attempted": len(cvs), "cv_produced": sum(1 for c in cvs if c["produced"]),
        "cv_honesty_errors": sum(1 for c in cvs if c["honesty_error"]),
        "cv_other_errors": sum(1 for c in cvs if c.get("error")),
        "provider_failures": sum(len(p.get("provider_failures", [])) for p in letters),
        "mean_words": (sum(p["words"] for p in letters) / len(letters)) if letters else None,
        "mean_letter_latency_s": (sum(p["latency_s"] for p in letters) / len(letters)) if letters else None,
        "measured_cost_usd": sum(r["letter"]["cost_usd"] + (r["cv"]["cost_usd"] if r["cv"] else 0) for r in rows),
        "recorded_cost_usd": sum(r.get("recorded_usd", 0.0) for r in rows),
        "violation_codes": dict(sorted(codes.items(), key=lambda kv: -kv[1])),
    }


def aggregates(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_metier: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        by_metier.setdefault(r["metier"] or r["profile_id"], []).append(r)
    return {"global": _aggregate(rows), "by_metier": {m: _aggregate(rs) for m, rs in sorted(by_metier.items())}}


def _ratio(n, d) -> str:
    return f"{n}/{d}" + (f" ({100 * n / d:.0f} %)" if d else " (n/a)")


def _r(value, digits=0):
    return None if value is None else round(value, digits) if digits else round(value)


def render_aggregates(agg: Dict[str, Any]) -> str:
    def block(name: str, a: Dict[str, Any]) -> str:
        return (f"- {name} : {a['pairs']} couples ; lettres produites {_ratio(a['letters_produced'], a['pairs'])} ; "
                f"needs_review {_ratio(a['letters_needs_review'], a['letters_produced'])} ; "
                f"CVHonestyError {_ratio(a['cv_honesty_errors'], a['cv_attempted'])} ; "
                f"échecs de lettre {a['letter_errors']} ; pannes fournisseur {a['provider_failures']} ; "
                f"mots moyens {_r(a['mean_words'])} ; latence lettre {_r(a['mean_letter_latency_s'], 2)} s ; "
                f"coût mesuré {a['measured_cost_usd']:.4f} $, inscrit {a['recorded_cost_usd']:.4f} $")
    lines = [block("Global", agg["global"])] + [block(m, a) for m, a in agg["by_metier"].items()]
    codes = agg["global"]["violation_codes"]
    if codes:
        lines.append("- Violations par code : " + " ; ".join(f"{c} x{n}" for c, n in codes.items()))
    return "\n".join(lines)


def _lines(items, fmt=str) -> str:
    return "\n".join(fmt(i) for i in items)


def _cell(value: Any) -> Any:
    """Neutralise l'injection de formule : une cellule texte qui commence par = + - @ tab ou CR est préfixée d'une apostrophe."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def write_sheets(run_dir: Path, rows: List[Dict[str, Any]], reqs_by_key: Dict[str, Dict[str, Any]]) -> None:
    with (run_dir / "feuille_evaluation.csv").open("w", encoding="utf-8", newline="") as f1, \
            (run_dir / "feuille_violations.csv").open("w", encoding="utf-8", newline="") as f2:
        sheet_w, viol_w = csv.writer(f1), csv.writer(f2)
        sheet = SimpleNamespace(writerow=lambda row: sheet_w.writerow([_cell(c) for c in row]))
        viol = SimpleNamespace(writerow=lambda row: viol_w.writerow([_cell(c) for c in row]))
        sheet.writerow(SHEET_FIXED + SHEET_FILL)
        viol.writerow(VIOLATION_COLUMNS)
        for r in rows:
            req = reqs_by_key.get(r["pair"], {})
            letter, cv = r["letter"], r["cv"] or {}
            accepted_letter = letter["produced"] and not letter.get("needs_review")
            letter_viol = letter.get("violations", [])
            cv_viol = cv.get("violations", [])
            cv_text = json.dumps(cv["content"], ensure_ascii=False, indent=1) if cv.get("produced") else ""
            sheet.writerow([
                r["profile_id"], r["offer_id"], r["metier"], "oui" if accepted_letter else "non",
                "oui" if cv.get("produced") else "non", letter.get("body", ""), cv_text,
                _lines(req.get("exigences", [])),
                _lines(req.get("preuves_exactes", []), lambda p: f"{p['exigence']} : {p['preuve']}"),
                _lines(req.get("transferables", []), lambda t: f"{t['exigence']} : {t['element']}"),
                _lines(req.get("lacunes", [])),
                _lines([f"[lettre] {v}" for v in letter_viol] + [f"[cv] {v}" for v in cv_viol]),
                len({p["exigence"] for p in req.get("preuves_exactes", [])})] + [""] * len(SHEET_FILL))
            for doc, items in (("lettre", letter_viol), ("cv", cv_viol)):
                for v in items:
                    viol.writerow([r["profile_id"], r["offer_id"], doc, v, ""])


def _write_run(run_dir: Path, mode: str, label: str, rows, prompts_dir: Path, mods, partial: bool = False,
               prompt_version: Optional[str] = None) -> Dict[str, Any]:
    run_dir.mkdir(parents=True, exist_ok=True)
    agg = aggregates(rows) if rows else {"global": _aggregate([]), "by_metier": {}}
    models = {**letter_models(mods), "cv": mods.cv.DEFAULT_CV_MODEL}
    report = {"mode": mode, "label": label, "confirmed": True, "partial": partial, "prompts_dir": str(prompts_dir),
              "prompt_version": prompt_version, "models": models, "neutralised": ["recherche entreprise (contexte vide)"],
              "results": rows, "aggregates": agg}
    (run_dir / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str),
                                          encoding="utf-8")
    reqs = {f"{r['profile_id']}/{r['offer_id']}": r for r in load_reference()["letter_requirements"]}
    write_sheets(run_dir, rows, reqs)
    note = SIMULATION_NOTE if mode == "simulated" else \
        "mode réel : mesures automatiques ; l'évaluation humaine reste à faire (feuille_evaluation.csv)"
    (run_dir / "rapport.md").write_text(
        f"# Banc lettres : {label}\n\n- mode : {mode}{' (partiel)' if partial else ''}\n- prompts : {prompts_dir}"
        f" (version {prompt_version})\n- modèles effectifs : {', '.join(f'{r} = {m}' for r, m in models.items())}\n"
        f"- CV généré sans évaluation Bloc B\n- neutralisé : recherche entreprise (contexte entreprise vide, entrée constante)\n"
        f"- {note}\n\n## Agrégats (dénominateurs explicites)\n\n{render_aggregates(agg)}\n", encoding="utf-8")
    report["summary"] = render_aggregates(agg)
    report["run_dir"] = str(run_dir)
    return report


# --------------------------------------------------------------------------- feuille remplie

def _int(value: Any) -> Optional[int]:
    try:
        return int(str(value).strip())
    except ValueError:
        return None


def _float(value: Any) -> Optional[float]:
    try:
        return float(str(value).strip().replace(",", "."))
    except ValueError:
        return None


def summarize_sheet(sheet_path: Path) -> Dict[str, Any]:
    """Métriques des cibles du plan depuis la feuille remplie, global et par métier, avec dénominateurs."""
    sheet_path = Path(sheet_path)
    with sheet_path.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    viol_path = sheet_path.with_name("feuille_violations.csv")
    violations: List[Dict[str, str]] = []
    if viol_path.exists():
        with viol_path.open(encoding="utf-8", newline="") as f:
            violations = list(csv.DictReader(f))
    groups: Dict[str, List[Dict[str, str]]] = {"global": rows}
    for r in rows:
        groups.setdefault(r["metier"] or r["profile_id"], []).append(r)
    out: Dict[str, Any] = {}
    for name, grp in groups.items():
        keys = {(r["profile_id"], r["offer_id"]) for r in grp}
        out[name] = _metrics(grp, [v for v in violations if (v["profile_id"], v["offer_id"]) in keys])
    return out


def _metrics(rows: List[Dict[str, str]], violations: List[Dict[str, str]]) -> Dict[str, Any]:
    m: Dict[str, Any] = {}
    for doc, accepted, inv, wrong in (("lettre", "lettre_acceptee", "inventees_lettre", "mauvais_poste_lettre"),
                                      ("cv", "cv_accepte", "inventees_cv", "mauvais_poste_cv")):
        rated = [r for r in rows if r[accepted] == "oui" and _int(r[inv]) is not None]
        bad = [r for r in rated if (_int(r[inv]) or 0) + (_int(r[wrong]) or 0) > 0]
        m[f"fidelite_{doc}"] = {"documents_avec_affirmation_critique": len(bad),
                                "documents_acceptes_evalues": len(rated)}
        col = f"exigences_avec_preuve_couvertes_{doc}"
        cover = [r for r in rows if _int(r[col]) is not None and (_int(r["exigences_avec_preuve"]) or 0) > 0]
        m[f"couverture_{doc}"] = {
            "couvertes": sum(min(_int(r[col]), _int(r["exigences_avec_preuve"])) for r in cover),
            "exigences_avec_preuve": sum(_int(r["exigences_avec_preuve"]) for r in cover)}
    naturel = [v for v in (_float(r["naturel_1_5"]) for r in rows) if v is not None]
    m["naturel"] = {"moyenne": (sum(naturel) / len(naturel)) if naturel else None, "lettres_notees": len(naturel)}
    judged = [v for v in violations if v["faux_rejet"].strip().lower() in ("oui", "non")]
    valid = sum(_int(r["affirmations_valides"]) or 0 for r in rows)
    m["faux_rejets"] = {"faux_rejets": sum(1 for v in judged if v["faux_rejet"].strip().lower() == "oui"),
                        "violations_jugees": len(judged), "violations_total": len(violations),
                        "affirmations_valides": valid}
    return m


def render_summary(summary: Dict[str, Any]) -> str:
    lines = ["Cibles du plan (zéro invention, couverture >= 90 %, faux rejets < 10 %)"]
    for name, m in summary.items():
        f1, f2 = m["fidelite_lettre"], m["fidelite_cv"]
        c1, c2 = m["couverture_lettre"], m["couverture_cv"]
        fr, nat = m["faux_rejets"], m["naturel"]
        naturel = "n/a" if nat["moyenne"] is None else f"{nat['moyenne']:.2f}/5"
        lines.append(
            f"- {name} : fidélité lettre {f1['documents_avec_affirmation_critique']}/{f1['documents_acceptes_evalues']} "
            f"documents acceptés avec affirmation critique (cible 0) ; CV {f2['documents_avec_affirmation_critique']}/"
            f"{f2['documents_acceptes_evalues']} ; couverture lettre {_ratio(c1['couvertes'], c1['exigences_avec_preuve'])} ; "
            f"CV {_ratio(c2['couvertes'], c2['exigences_avec_preuve'])} ; faux rejets "
            f"{_ratio(fr['faux_rejets'], fr['affirmations_valides'])} affirmations valides signalées "
            f"({fr['violations_jugees']}/{fr['violations_total']} violations jugées) ; naturel "
            f"{naturel} sur {nat['lettres_notees']} lettres")
    return "\n".join(lines)


def _resolve_run(name: str) -> Path:
    path = Path(name)
    return path if path.exists() else DATA_DIR / name


def compare_runs(run_a: str, run_b: str) -> str:
    reports = [json.loads((_resolve_run(r) / "results.json").read_text(encoding="utf-8")) for r in (run_a, run_b)]
    ga, gb = (r["aggregates"]["global"] for r in reports)
    lines = [f"{tag} = {r['label']} (prompts {r.get('prompt_version')}, dossier {r.get('prompts_dir')})"
             for tag, r in zip("AB", reports)]
    for key in ("pairs", "letters_produced", "letters_needs_review", "needs_review_rate", "cv_honesty_errors",
                "letter_errors", "provider_failures", "mean_words", "mean_letter_latency_s", "measured_cost_usd"):
        a, b = ga[key], gb[key]
        diff = "n/a" if a is None or b is None else f"{b - a:+.4g}"
        lines.append(f"- {key} : A {a} -> B {b} (écart {diff})")
    return "\n".join(lines)


# --------------------------------------------------------------------------- CLI

def _positive_int(text: str) -> int:
    value = int(text)
    if value < 1:
        raise argparse.ArgumentTypeError("doit être un entier >= 1")
    return value


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--simulated", action="store_true", help="pipeline complet hors réseau, oracle déterministe")
    parser.add_argument("--real", action="store_true", help="appels réels (estimation seule sans --confirm)")
    parser.add_argument("--confirm", action="store_true", help="avec --real : lance réellement les appels, payants")
    parser.add_argument("--limit", type=_positive_int, help="N premiers couples du fichier (entier >= 1)")
    parser.add_argument("--label", help="nom de l'exécution (défaut : le mode)")
    parser.add_argument("--prompts-dir", help="dossier de prompts de lettre (défaut : production)")
    parser.add_argument("--reuse-analyst", action="store_true", help="réutilise la sortie de l'analyste en cache")
    parser.add_argument("--no-cv", action="store_true", help="ne génère pas le complément CV")
    parser.add_argument("--summarize", metavar="FEUILLE", help="métriques des cibles depuis la feuille remplie")
    parser.add_argument("--compare", nargs=2, metavar=("RUN_A", "RUN_B"), help="écart des agrégats entre deux runs")
    parser.add_argument("--out", default=str(DATA_DIR), help="dossier de sortie (défaut : scripts/data/letters_bench)")
    args = parser.parse_args(argv)
    if args.simulated and args.real:
        parser.error("--simulated et --real s'excluent")
    if args.confirm and not args.real:
        parser.error("--confirm n'a de sens qu'avec --real")
    if args.summarize:
        print(render_summary(summarize_sheet(Path(args.summarize))))
        return 0
    if args.compare:
        print(compare_runs(*args.compare))
        return 0
    mode = "simulated" if args.simulated else "real" if args.real else "estimate"
    if mode == "real":
        with contextlib.suppress(ImportError):
            from dotenv import load_dotenv
            load_dotenv(_BACKEND.parent / ".env", override=False)
    mods = _modules()
    with_cv = not args.no_cv
    if mode == "real":
        try:
            ensure_priced(all_models(mods, with_cv))
        except UnknownPriceError as exc:
            print(f"Refus du mode réel : {exc}", file=sys.stderr)
            return 2
        if args.confirm:
            ensure_keys(all_models(mods, with_cv))
    pairs = load_pairs(args.limit)
    try:
        report = asyncio.run(run_bench(pairs, mods, mode=mode, confirm=args.confirm, out_dir=Path(args.out),
                                       label=args.label, prompts_dir=args.prompts_dir, with_cv=with_cv,
                                       reuse_analyst=args.reuse_analyst))
    except UnknownPriceError as exc:
        print(f"Estimation impossible : {exc}", file=sys.stderr)
        return 2
    except llm_budget.BudgetExceeded as exc:
        print(f"Budget lettres refusé, exécution interrompue (résultats partiels écrits) : {exc}", file=sys.stderr)
        return 3
    if not report["confirmed"]:
        for key, usd in report["estimates"].items():
            print(f"  {key} : {usd:.4f} $")
        print(f"Estimation (prudente, aucun appel) : {report['estimate_usd']:.4f} $ pour {len(pairs)} couples ; "
              f"part lettres du registre : {llm_budget.PLAN_CAPS_USD[PLAN]:.2f} $. "
              "Ajouter --real --confirm pour lancer les appels réels.")
        return 0
    print(report["summary"])
    print(f"Sorties : {report['run_dir']}")
    if report["mode"] == "simulated":
        print(SIMULATION_NOTE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
