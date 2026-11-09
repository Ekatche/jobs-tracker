"""Banc lettres : chaîne simulée, estimation sans appel, et registre de budget (hors réseau, registre temporaire)."""

import asyncio
import csv
import json

from scripts import letter_bakeoff as bench
from scripts import llm_budget


def _ledger_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def test_letter_bench_simulated_estimate_and_budget_ledger(tmp_path, monkeypatch, capsys):
    ledger = tmp_path / "ledger.jsonl"
    monkeypatch.setattr(llm_budget, "LEDGER_PATH", ledger)
    out = tmp_path / "out"
    mods = bench._modules()
    # Environnement de CI : modèles sans prix connu (ou absents). Le simulé doit les figer avant d'estimer.
    for env, _ in bench.ROLE_ENV.values():
        monkeypatch.setenv(env, "inconnu/sans-prix")
    monkeypatch.setattr(mods.cv, "DEFAULT_CV_MODEL", "inconnu/sans-prix")
    pairs = bench.load_pairs(2)

    # 1. Simulé sur 2 couples, panne needs_review injectée au couple 0 : dénominateurs, feuille, registre vide.
    sim = asyncio.run(bench.run_bench(pairs, mods, mode="simulated", out_dir=out, label="sim", faults={0: "needs_review"}))
    g = sim["aggregates"]["global"]
    assert (g["pairs"], g["letters_produced"], g["cv_attempted"]) == (2, 2, 2)
    flags = [r["letter"]["needs_review"] for r in sim["results"]]
    assert flags[0] is True and g["letters_needs_review"] == sum(flags)
    assert g["needs_review_rate"] == sum(flags) / 2
    with (out / "sim" / "feuille_evaluation.csv").open(encoding="utf-8") as f:
        sheet = list(csv.DictReader(f))
    assert [r["offer_id"] for r in sheet] == [r["offer_id"] for r in sim["results"]]
    assert "inventees_lettre" in sheet[0] and sheet[0]["lettre"]
    assert _ledger_rows(ledger) == []

    # 2. Modèle sans prix : refus net en estimation comme en réel (code 2, pas de traceback).
    assert bench.main(["--limit", "1"]) == 2 and bench.main(["--real", "--limit", "1"]) == 2
    assert "prix inconnu" in capsys.readouterr().err

    # 3. --real sans --confirm, via main : estimation seule, aucun appel (un point d'appel qui lèverait serait
    #    avalé par le pipeline : on compte les appels dans une liste).
    for role, (env, _) in bench.ROLE_ENV.items():
        monkeypatch.setenv(env, "gemini/gemini-3.8-flash" if role in ("analyst", "critic") else "openai/gpt-6.1-sol")
    monkeypatch.setattr(mods.cv, "DEFAULT_CV_MODEL", "gemini/gemini-3.7-flash")
    calls = []

    async def spy(**kwargs):
        calls.append(kwargs.get("model"))
        raise RuntimeError("appel LLM sans --confirm")

    monkeypatch.setattr(bench, "_real_acompletion", spy)
    assert bench.main(["--real", "--limit", "2", "--label", "est", "--out", str(out)]) == 0
    assert calls == [] and not (out / "est").exists() and _ledger_rows(ledger) == []
    assert "Estimation (prudente, aucun appel)" in capsys.readouterr().out

    # 4. Réel confirmé (points d'appel injectés) : le couple 1 échoue partout (lettre en erreur, CVHonestyError),
    #    le couple 2 réussit. Seule la génération réussie est inscrite : 2 lignes (lettre + CV), du couple 2.
    ok_letter, ok_cv = bench.make_letter_oracle(pairs[1]), bench.make_cv_oracle(pairs[1])
    bad_cv = bench.make_cv_oracle(pairs[0], "cv_honesty")
    # même point d'appel pour les 2 couples : on route selon l'ordre du couple.
    state = {"pair": 0}

    async def routed_letter(**kwargs):
        if state["pair"] == 0:
            raise RuntimeError("panne simulée")
        return await ok_letter(**kwargs)

    async def routed_cv(**kwargs):
        return await (bad_cv if state["pair"] == 0 else ok_cv)(**kwargs)

    orig = bench.run_pair

    async def run_pair_tracking(*a, **kw):
        row = await orig(*a, **kw)
        state["pair"] += 1
        return row

    monkeypatch.setattr(bench, "run_pair", run_pair_tracking)
    monkeypatch.setenv("GEMINI_API_KEY", "dummy")
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    real = asyncio.run(bench.run_bench(pairs, mods, mode="real", confirm=True, out_dir=out, label="real",
                                       letter_inner=routed_letter, cv_inner=routed_cv))
    first, second = real["results"]
    assert first["letter"]["produced"] is False and first["cv"]["honesty_error"] is True
    assert first["recorded_usd"] == 0.0 and second["recorded_usd"] > 0
    rows = _ledger_rows(ledger)
    assert [r["pair"] for r in rows] == [second["pair"]] * 2
    assert sorted(r["kind"] for r in rows) == ["cv", "letter"]
