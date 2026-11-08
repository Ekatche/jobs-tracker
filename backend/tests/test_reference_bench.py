"""Banc de matching sur le jeu de référence (plan profil, 1c). Hors réseau : `embed_texts`
est toujours simulé et le registre de budget vit dans `tmp_path`."""

import asyncio
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.services.offer_scoring.constants import FLOOR
from app.services.offer_scoring.score import ScoreResult
from scripts import llm_budget, matching_bench, reference_bench
from scripts.llm_budget import BudgetExceeded
from scripts.reference_dataset import load_reference
from scripts.reference_bench import (
    compute_reference_metrics,
    aggregate_subgroups,
    ndcg_at_k,
    preference_violations,
    profile_ranking_metrics,
    recall_and_false_negatives,
    reference_labels,
    reference_to_export,
    run_reference_report,
)

MINI = Path(__file__).parent / "fixtures" / "reference_mini"


@pytest.fixture
def ref():
    return load_reference(MINI)


@pytest.fixture
def export(ref):
    return reference_to_export(ref)


def _result(score):
    return ScoreResult(
        score=score, raw_score=score, level="strong", breakdown={"raw_score": score},
        unknown_components=[], failed_conditions=[],
    )


# --- Adaptateur ---


def test_reference_to_export_shape(export):
    assert export["exported_at"] == datetime(2026, 11, 8, tzinfo=timezone.utc)
    assert export["seed"] == 0
    assert export["interactions"] == [] and export["publication_counts"] == {}
    assert export["missing_interaction_offer_ids"] == []
    assert [p["alias"] for p in export["profiles"]] == ["p01", "p02"]
    assert export["profiles"][0]["user_id"] == "p01"
    assert export["profiles"][0]["profile"]["user_id"] == "p01"
    offer = export["offers"][0]
    assert offer["_id"] == "o001" and offer["poste"] == "Data Engineer"
    assert isinstance(offer["created_at"], str)
    assert export["sample_offer_ids"] == ["o001", "o002"]


def test_reference_labels_and_violations(ref):
    assert reference_labels(ref) == {
        "p01": {"o001": "relevant", "o002": "irrelevant"},
        "p02": {"o002": "partial"},
    }
    assert preference_violations(ref) == {"p02": {"o002"}}


# --- Métriques ---

_DCG_SWAPPED = (1 / math.log2(2) + 2 / math.log2(3)) / (2 / math.log2(2) + 1 / math.log2(3))


@pytest.mark.parametrize(
    "ranking,labels,expected",
    [
        (["a", "b"], {"a": "relevant", "b": "partial"}, 1.0),
        (["b", "a"], {"a": "relevant", "b": "partial"}, _DCG_SWAPPED),
        (["a"], {"a": "relevant", "z": "relevant"}, 1 / (1 + 1 / math.log2(3))),
    ],
)
def test_ndcg_at_10(ranking, labels, expected):
    assert ndcg_at_k(ranking, labels, 10) == pytest.approx(expected)


def test_ndcg_ignores_items_beyond_k():
    ranking = [f"i{n}" for n in range(11)]
    labels = {"i10": "relevant"}
    assert ndcg_at_k(ranking, labels, 10) == 0.0


@pytest.mark.parametrize(
    "ranking,labels,violations,p5,violations_at_5",
    [
        (["a", "b", "c"], {"a": "relevant", "b": "partial", "c": "relevant"}, set(), 2 / 3, 0),
        (["a", "b", "c", "d", "e", "f"], {"f": "relevant", "a": "relevant"}, {"b", "f"}, 1 / 5, 1),
        ([], {"a": "relevant"}, {"a"}, 0.0, 0),
    ],
)
def test_profile_ranking_metrics(ranking, labels, violations, p5, violations_at_5):
    metrics = profile_ranking_metrics(ranking, labels, violations)
    assert metrics["p@5"] == pytest.approx(p5)
    assert metrics["preference_violations@5"] == violations_at_5


@pytest.mark.parametrize(
    "labels,assessed,recall,false_negatives",
    [
        (
            {"a": "relevant", "b": "relevant", "c": "irrelevant"},
            {"a": (None, _result(FLOOR + 30)), "b": (None, _result(FLOOR - 1)), "c": (None, _result(0))},
            0.5,
            [{"offer_id": "b", "reason": "below_floor", "score": FLOOR - 1}],
        ),
        (
            {"a": "relevant"},
            {"a": ("role_mismatch", None)},
            0.0,
            [{"offer_id": "a", "reason": "role_mismatch", "score": None}],
        ),
        ({"a": "relevant"}, {"a": (None, _result(FLOOR))}, 1.0, []),
        ({"a": "partial", "b": "irrelevant"}, {"a": (None, _result(0))}, None, []),
    ],
)
def test_recall_and_false_negatives(labels, assessed, recall, false_negatives):
    assert recall_and_false_negatives(labels, assessed) == (recall, false_negatives)


# --- Sous-groupes ---


def _entry(n_relevant, p5):
    hybrid = {"p@5": p5, "ndcg@10": 0.5, "preference_violations@5": 0, "recall": None, "false_negatives": []}
    chrono = {"p@5": 0.0, "ndcg@10": 0.0, "preference_violations@5": 0}
    return {"n_labels": n_relevant, "n_relevant": n_relevant, "hybrid": hybrid, "chronological": chrono}


@pytest.mark.parametrize("n_relevant,small", [(19, True), (20, False)])
def test_subgroup_small_flag(ref, n_relevant, small):
    per_profile = {"p01": _entry(n_relevant, 0.8), "p02": _entry(1, 0.4)}
    groups = aggregate_subgroups(ref, per_profile)
    de = groups["metier"]["data engineer"]
    assert de["n_profiles"] == 1 and de["n_relevant"] == n_relevant and de["small"] is small
    assert de["hybrid"]["p@5"] == 0.8 and de["hybrid"]["recall"] is None


def test_subgroup_dimensions_and_sources(ref):
    per_profile = {"p01": _entry(3, 1.0), "p02": _entry(1, 0.0)}
    groups = aggregate_subgroups(ref, per_profile)
    assert set(groups) == {"metier", "niveau", "langue", "reconversion", "sources"}
    assert set(groups["sources"]) == {"cv", "cv+manual"}
    assert set(groups["reconversion"]) == {"true", "false"}
    assert groups["niveau"]["junior"]["hybrid"]["p@5"] == 1.0


# --- Rapport ---


def test_report_prints_markdown_and_writes_json(ref, export, tmp_path, capsys):
    results = tmp_path / "results.json"
    run_reference_report(ref, export, cache_path=tmp_path / "absent.json", results_path=results)
    out = capsys.readouterr().out
    assert "| p01 |" in out and "trop petit" in out
    assert "sans cos : 4" in out
    payload = json.loads(results.read_text(encoding="utf-8"))
    assert payload["meta"]["n_pairs_without_cos"] == 4 and payload["meta"]["n_labels"] == 3
    assert {"per_profile", "aggregate", "subgroups", "offer_sources"} <= set(payload)


def _cos_record(alias, oid, cos):
    return {"alias": alias, "offer_id": oid, "cos": cos}


def test_compute_metrics_exact_values_with_cos(ref, export):
    # p01 : o001 (pertinente) et o002 (hors sujet) ; un cos élevé sur o002 ne peut pas
    # faire passer o002 devant o001 si le score l'en empêche, mais le classement reste
    # restreint aux deux offres annotées de p01.
    cos = [_cos_record("p01", "o001", 0.9), _cos_record("p01", "o002", 0.1)]
    metrics = compute_reference_metrics(ref, export, cos)
    p01 = metrics["per_profile"]["p01"]["hybrid"]
    assigned = matching_bench.hybrid_scores(export, cos)["p01"]
    expected_rank = matching_bench.rank_hybrid(["o001", "o002"], assigned, {"o001": 0.9, "o002": 0.1})
    labels = {"o001": "relevant", "o002": "irrelevant"}
    assert expected_rank[0] == "o001"
    assert p01["p@5"] == pytest.approx(1 / 2)
    assert p01["ndcg@10"] == pytest.approx(ndcg_at_k(expected_rank, labels, 10)) == pytest.approx(1.0)
    recall, fns = recall_and_false_negatives(labels, assigned)
    assert p01["recall"] == recall and p01["false_negatives"] == fns
    # p02 n'a qu'une offre annotée, o002 : o001 n'entre jamais dans son classement.
    assert metrics["per_profile"]["p02"]["hybrid"]["p@5"] == 0.0
    assert metrics["per_profile"]["p02"]["hybrid"]["preference_violations@5"] == 1
    assert metrics["per_profile"]["p02"]["hybrid"]["recall"] is None
    assert set(metrics["per_profile"]) == {"p01", "p02"}
    assert metrics["per_profile"]["p01"]["n_labels"] == 2 and metrics["per_profile"]["p01"]["n_relevant"] == 1
    assert set(p01) == {"p@5", "ndcg@10", "preference_violations@5", "recall", "false_negatives"}
    assert metrics["offer_sources"]["synthetic"]["n_relevant"] == 1
    assert metrics["aggregate"]["n_profiles"] == 2


def test_offer_source_recall(export):
    labels = {"p01": {"o001": "relevant", "o002": "irrelevant"}}
    assessed = {"p01": {"o001": ("role_mismatch", None)}}
    result = reference_bench.offer_source_recall(export, labels, assessed)
    assert result == {"synthetic": {"n_relevant": 1, "recall": 0.0}}


# --- Budget de l'embedding ---


@pytest.fixture
def fake_embed(monkeypatch):
    calls = []

    async def fake(texts):
        calls.append(list(texts))
        return [[1.0, 0.0] for _ in texts]

    monkeypatch.setattr(matching_bench, "embed_texts", fake)
    return calls


def _embed(export, tmp_path, confirm):
    asyncio.run(matching_bench.run_embed(export, tmp_path / "cos.json", confirm))


def test_embed_budget_exhausted_blocks_call(export, tmp_path, fake_embed):
    llm_budget.record_call("profil", "seed", "m", 0.25, "billed", path=llm_budget.LEDGER_PATH)
    with pytest.raises(BudgetExceeded):
        _embed(export, tmp_path, confirm=True)
    assert fake_embed == []
    assert len(llm_budget.LEDGER_PATH.read_text(encoding="utf-8").splitlines()) == 1


def test_embed_confirmed_records_one_row(export, tmp_path, fake_embed):
    _embed(export, tmp_path, confirm=True)
    assert fake_embed
    rows = [json.loads(line) for line in llm_budget.LEDGER_PATH.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["plan"] == "profil" and rows[0]["cost_kind"] == "estimated"
    assert rows[0]["script"] == "matching_bench.py embed" and rows[0]["n_pairs"] > 0
    assert (tmp_path / "cos.json").exists()


def test_embed_without_confirm_has_no_call_nor_row(export, tmp_path, fake_embed):
    _embed(export, tmp_path, confirm=False)
    assert fake_embed == [] and not llm_budget.LEDGER_PATH.exists()


def test_embed_failure_propagates_and_records_nothing(export, tmp_path, monkeypatch):
    async def boom(texts):
        raise RuntimeError("embedding indisponible")

    monkeypatch.setattr(matching_bench, "embed_texts", boom)
    with pytest.raises(RuntimeError, match="indisponible"):
        _embed(export, tmp_path, confirm=True)
    assert not llm_budget.LEDGER_PATH.exists()
    assert not (tmp_path / "cos.json").exists()


def test_estimate_embed_cost_formula():
    cost = matching_bench.estimate_embed_cost(
        [("a", "o1"), ("a", "o2"), ("b", "o1")],
        {"o1": "x" * 400, "o2": "y" * 400},
        {"a": ("i" * 40, "h"), "b": (None, None)},
    )
    assert cost == pytest.approx(((400 + 400 + 40) / 4) / 1_000_000 * 0.1)


# --- CLI ---


@pytest.mark.parametrize(
    "command,message",
    [("judge", "remplacent le juge"), ("twopass", "Two-Pass hors budget")],
)
def test_cli_reference_rejects_other_commands(monkeypatch, command, message):
    monkeypatch.setattr(sys, "argv", ["matching_bench.py", "--reference", command])
    with pytest.raises(SystemExit) as exc:
        matching_bench.main()
    assert message in str(exc.value.code)


# --- Fumée sur le vrai jeu ---


def test_real_reference_smoke_without_cos():
    real = load_reference()
    metrics = compute_reference_metrics(real, reference_to_export(real), [])
    assert set(metrics["per_profile"]) == {p["profile_id"] for p in real["profiles"]}
    assert metrics["aggregate"]["n_profiles"] == len(real["profiles"])
