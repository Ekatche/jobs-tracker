#!/usr/bin/env python3
"""
Letter writer bake-off script — Task 14.

Usage:
    cd backend
    .venv/bin/python scripts/letter_bakeoff.py \
        --profile path/to/profile.json \
        --offer   "Texte de l'offre ou chemin vers un .md/.txt" \
        --company "Nom de l'entreprise" \
        --name    "Prénom Nom du candidat" \
        --offers  3 \
        --out     ../docs/micro/20260914-letter-bakeoff/

The analyst is called ONCE per offer; its output is reused for all three writer
candidates so that the letters are comparable.  The writer model identity is
hidden in a separate key-file; the anonymised report is safe to read first.

DEFAULT_MODELS["writer"] must be updated manually in letter_llm.py after you
have ranked and unmasked the results — this script never mutates source files.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path bootstrap — allow running from backend/ without installing the package.
# ---------------------------------------------------------------------------
_BACKEND = Path(__file__).parent.parent.resolve()
_JOB_TRACKERS_PKG = _BACKEND / "job_trackers" / "src" / "job_trackers"

for _p in [str(_BACKEND), str(_JOB_TRACKERS_PKG.parent), str(_JOB_TRACKERS_PKG)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Dotenv — load .env from repo root if python-dotenv is available.
try:
    from dotenv import load_dotenv  # type: ignore

    _ENV_FILE = _BACKEND.parent / ".env"
    if _ENV_FILE.exists():
        load_dotenv(_ENV_FILE, override=False)
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Internal imports (after path bootstrap)
# ---------------------------------------------------------------------------
from litellm import completion  # type: ignore
from app.services.letter_guards import evaluate_letter_guards
from letter_llm import (  # type: ignore
    DEFAULT_MODELS,
    ROLE_TEMPERATURES,
    get_letter_llm,
    get_model_provider,
    validate_cross_provider,
)
from cover_letter_crew import (  # type: ignore
    _call_analyst,
    _call_writer,
    _call_critic,
    LETTER_RULES,
    MIN_WORDS,
    MAX_WORDS,
    load_prompt,
    PROMPT_VERSION,
)

# ---------------------------------------------------------------------------
# Candidate writer models for the bake-off.
# ---------------------------------------------------------------------------
CANDIDATE_WRITERS = [
    "openai/gpt-5.6-sol",
    "mistral/mistral-large-2407",
    # "gemini/gemini-3.8-flash",  # crédits prépayés épuisés — remplacé par terra
    "openai/gpt-5.6-terra",
]

# OpenAI reasoning models (o1, o3, gpt-5.x) do not accept a `temperature`
# parameter even though litellm reports it as supported in its static model DB.
# We detect them by prefix and omit the kwarg to avoid BadRequestError.
_OPENAI_NO_TEMP_PREFIXES = ("o1", "o3", "gpt-5", "gpt-o")


def _build_completion_kwargs(
    model: str, temperature: float, extra: dict | None = None
) -> dict:
    """Return completion kwargs, omitting temperature for OpenAI reasoning models."""
    short = model.split("/")[-1].lower()
    omit_temp = any(short.startswith(p) for p in _OPENAI_NO_TEMP_PREFIXES)
    kwargs = {"temperature": temperature} if not omit_temp else {}
    if extra:
        kwargs.update(extra)
    return kwargs

# Estimated cost per million tokens (input / output) in USD — update as needed.
COST_PER_MILLION: dict[str, tuple[float, float]] = {
    "openai/gpt-5.6-sol":        (8.00, 40.00),
    "openai/gpt-5.6-terra":      (4.00, 20.00),  # approx — à affiner
    "mistral/mistral-large-2407": (2.00,  6.00),
    "gemini/gemini-3.8-flash":   (0.075, 0.30),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_text(path_or_text: str) -> str:
    """Accept either a file path (*.md / *.txt / *.json) or a raw string."""
    p = Path(path_or_text)
    if p.exists() and p.is_file():
        return p.read_text(encoding="utf-8")
    return path_or_text


def _estimated_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return estimated USD cost for a single completion call."""
    if model not in COST_PER_MILLION:
        return 0.0
    in_price, out_price = COST_PER_MILLION[model]
    return (input_tokens / 1_000_000) * in_price + (output_tokens / 1_000_000) * out_price


def _call_writer_for_model(
    writer_model: str,
    analyst_json: dict[str, Any],
    company_name: str,
) -> tuple[str, dict[str, Any]]:
    """
    Call the writer with a specific model override, bypassing get_letter_llm(\"writer\")
    so that each candidate model is used regardless of DEFAULT_MODELS.

    Returns (letter_text, usage_dict) where usage_dict contains token counts and
    estimated cost.
    """
    llm = get_letter_llm("writer", model_override=writer_model)

    capped_repetitions = ", ".join(
        f'"{term}" (max {n})' for term, n in LETTER_RULES["capped_repetitions"].items()
    )
    prompt = load_prompt(
        "02_style",
        candidate_name=analyst_json.get("candidate_name", ""),
        candidate_headline=analyst_json.get("candidate_headline", ""),
        company_name=company_name,
        min_words=MIN_WORDS,
        max_words=MAX_WORDS,
        missions=json.dumps(analyst_json.get("missions", []), ensure_ascii=False),
        experiences=json.dumps(analyst_json.get("selected_experiences", []), ensure_ascii=False),
        stacks=", ".join(analyst_json.get("stacks", [])[:15]),
        projects=", ".join(analyst_json.get("projects", [])),
        capped_repetitions=capped_repetitions,
    )

    t0 = time.monotonic()
    resp = completion(
        model=llm.model,
        api_key=llm.api_key,
        messages=[{"role": "user", "content": prompt}],
        max_completion_tokens=2500,
        drop_params=True,
        **_build_completion_kwargs(writer_model, ROLE_TEMPERATURES["writer"]),
    )
    elapsed = time.monotonic() - t0

    content = resp.choices[0].message.content or ""
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        stripped = "\n".join(l for l in lines if not l.startswith("```")).strip()
        content = stripped if stripped else content  # never discard everything

    usage = getattr(resp, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
    output_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
    cost = _estimated_cost(writer_model, input_tokens, output_tokens)

    return content, {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "estimated_cost_usd": round(cost, 6),
        "duration_s": round(elapsed, 2),
    }


def _call_critic_for_model(
    critic_model: str,
    letter_text: str,
    missions: list,
) -> dict[str, Any]:
    """Call the critic with a specific model override."""
    llm = get_letter_llm("critic", model_override=critic_model)
    import json as _json

    prompt = f"""Tu es un recruteur senior intransigeant.
Évalue cette lettre de motivation au regard des missions : {_json.dumps(missions, ensure_ascii=False)}

Lettre :
{letter_text}

Réponds UNIQUEMENT par un objet JSON valide :
{{
    "verdict": "approve" ou "revise",
    "score": 1-10,
    "flaws": ["défaut 1", "défaut 2"]
}}"""

    try:
        resp = completion(
            model=llm.model,
            api_key=llm.api_key,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=400,
            response_format={"type": "json_object"},
            drop_params=True,
            **_build_completion_kwargs(critic_model, ROLE_TEMPERATURES["critic"]),
        )
        return json.loads(resp.choices[0].message.content.strip())
    except Exception as e:
        return {"verdict": "error", "score": 0, "flaws": [str(e)]}


# ---------------------------------------------------------------------------
# Core bake-off logic
# ---------------------------------------------------------------------------

def run_bakeoff_for_offer(
    offer_text: str,
    profile: dict[str, Any],
    company_name: str,
    candidate_name: str,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """
    Run the bake-off for a single offer.

    Returns:
        (anonymised_results, key_map)

        anonymised_results — list of result dicts with model identity removed,
            sorted in random order.  Safe to read first for blind ranking.

        key_map — {candidate_id: model_name}, the key to unmask after ranking.
    """
    print(f"  [analyst] Appel analyst sur l'offre…")
    t0 = time.monotonic()
    analyst_json = _call_analyst(offer_text, profile, candidate_name)
    analyst_json["company_name"] = company_name
    analyst_elapsed = round(time.monotonic() - t0, 2)
    print(f"  [analyst] OK ({analyst_elapsed}s) — missions: {analyst_json.get('missions', [])}")

    shuffled = list(CANDIDATE_WRITERS)
    random.shuffle(shuffled)

    results = []
    key_map: dict[str, str] = {}

    for idx, writer_model in enumerate(shuffled, start=1):
        candidate_id = f"Lettre-{idx}"
        key_map[candidate_id] = writer_model
        critic_model = validate_cross_provider(writer_model)
        if "gemini" in critic_model:
            critic_model = "mistral/mistral-large-2407"

        print(f"  [{candidate_id}] writer={writer_model}  critic={critic_model}")

        # --- Writer ---
        try:
            t1 = time.monotonic()
            letter_text, usage = _call_writer_for_model(writer_model, analyst_json, company_name)
            print(f"  [{candidate_id}] writer OK ({usage['duration_s']}s, {usage['total_tokens']} tokens, ~${usage['estimated_cost_usd']:.4f})")
        except Exception as e:
            print(f"  [{candidate_id}] writer ERREUR: {e}")
            results.append({
                "candidate_id": candidate_id,
                "error": str(e),
                "letter": None,
                "guard_report": None,
                "critic_verdict": None,
                "usage": {},
            })
            continue

        # --- Guard-fous ---
        guard_report = evaluate_letter_guards(letter_text, offer_text, analyst_json)

        # --- Critic (cross-provider) ---
        try:
            critic_verdict = _call_critic_for_model(
                critic_model, letter_text, analyst_json.get("missions", [])
            )
        except Exception as e:
            critic_verdict = {"verdict": "error", "score": 0, "flaws": [str(e)]}

        results.append({
            "candidate_id": candidate_id,
            "letter": letter_text,
            "guard_report": guard_report.model_dump(),
            "guard_violation_count": len(guard_report.violations),
            "guard_is_blocking": guard_report.is_blocking,
            "critic_verdict": critic_verdict,
            "usage": usage,
        })

    return results, key_map


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Letter writer bake-off — Task 14")
    p.add_argument("--profile", required=True, help="Chemin vers profile.json (CandidateProfile sérialisé)")
    p.add_argument("--offer", required=True, action="append", dest="offers",
                   metavar="OFFER", help="Texte ou chemin d'offre (répétable, ou utiliser --offers)")
    p.add_argument("--company", required=True, action="append", dest="companies",
                   metavar="COMPANY", help="Nom d'entreprise associé à chaque offre (même ordre)")
    p.add_argument("--name", default="", help="Nom complet du candidat")
    p.add_argument("--out", required=True, help="Répertoire de sortie")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    profile_path = Path(args.profile)
    if not profile_path.exists():
        print(f"ERREUR: profil introuvable: {profile_path}", file=sys.stderr)
        sys.exit(1)
    profile: dict[str, Any] = json.loads(profile_path.read_text(encoding="utf-8"))

    offers = [_load_text(o) for o in args.offers]
    companies = args.companies

    if len(offers) != len(companies):
        print(
            f"ERREUR: {len(offers)} offre(s) mais {len(companies)} entreprise(s) — même nombre requis.",
            file=sys.stderr,
        )
        sys.exit(1)

    all_results: list[dict[str, Any]] = []
    all_keys: list[dict[str, Any]] = []

    for offer_idx, (offer_text, company_name) in enumerate(zip(offers, companies), start=1):
        print(f"\n=== Offre {offer_idx}/{len(offers)} — {company_name} ===")
        results, key_map = run_bakeoff_for_offer(
            offer_text, profile, company_name, args.name
        )
        all_results.append({
            "offer_index": offer_idx,
            "company": company_name,
            "results": results,
        })
        all_keys.append({
            "offer_index": offer_idx,
            "company": company_name,
            "key_map": key_map,
        })

    # --- Anonymised report (safe to read first) ---
    report_path = out_dir / "bakeoff-report.json"
    report_path.write_text(
        json.dumps(all_results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\n✓ Rapport anonymisé  → {report_path}")

    # --- Key file (unmask AFTER blind ranking) ---
    key_path = out_dir / "bakeoff-keys.json"
    key_path.write_text(
        json.dumps(all_keys, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"✓ Fichier de clés    → {key_path}  (à ouvrir APRÈS classement à l'aveugle)")

    # --- Human-readable summary ---
    summary_lines = [
        "# Bake-off — résumé",
        "",
        "## Candidats",
        *[f"- {m}" for m in CANDIDATE_WRITERS],
        "",
        "## Résultats par offre",
    ]
    for block in all_results:
        summary_lines.append(f"\n### Offre {block['offer_index']} — {block['company']}")
        summary_lines.append("")
        summary_lines.append("| Candidat | Violations garde-fous | Bloquant | Verdict critique | Score | Tokens | Coût USD | Durée (s) |")
        summary_lines.append("|---|---|---|---|---|---|---|---|")
        for r in block["results"]:
            if r.get("error"):
                summary_lines.append(f"| {r['candidate_id']} | ERREUR: {r['error']} | — | — | — | — | — | — |")
                continue
            cv = r.get("critic_verdict") or {}
            u = r.get("usage") or {}
            summary_lines.append(
                f"| {r['candidate_id']}"
                f" | {r.get('guard_violation_count', '?')}"
                f" | {'Oui' if r.get('guard_is_blocking') else 'Non'}"
                f" | {cv.get('verdict', '?')}"
                f" | {cv.get('score', '?')}/10"
                f" | {u.get('total_tokens', '?')}"
                f" | {u.get('estimated_cost_usd', '?')}"
                f" | {u.get('duration_s', '?')}"
                " |"
            )

    summary_lines += [
        "",
        "## Prochaines étapes",
        "",
        "1. Lire `bakeoff-report.json` — classer les lettres **sans** regarder `bakeoff-keys.json`.",
        "2. Ouvrir `bakeoff-keys.json` pour lever l'anonymat.",
        "3. Croiser classement, violations et coûts.",
        "4. Mettre à jour `DEFAULT_MODELS[\"writer\"]` dans `letter_llm.py` avec le modèle retenu.",
        "5. Mettre à jour `validate_cross_provider` si le critique doit changer en conséquence.",
        f"6. Committer : `git commit -m \"feat: bake-off du rédacteur et choix de modèle mesuré\"`",
        "",
        f"> Prompt version utilisée : `{PROMPT_VERSION}`",
        f"> Candidats évalués : {', '.join(CANDIDATE_WRITERS)}",
    ]

    summary_path = out_dir / "bakeoff-summary.md"
    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")
    print(f"✓ Résumé lisible     → {summary_path}")
    print("\nÀ faire maintenant : classez les lettres à l'aveugle, puis ouvrez le fichier de clés.")


if __name__ == "__main__":
    main()
