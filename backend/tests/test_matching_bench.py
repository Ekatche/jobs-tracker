"""Banc de mesure du matching (spec matching hybride, étape 1b).

Aucun réseau ni base : le LLM, l'embedding et le Two-Pass sont simulés, et la
base est la `BenchDatabase` en mémoire construite depuis un export factice.
"""

import json
import random
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

from app.services.evaluation.evaluator import compute_offer_evaluation
from scripts.export_matching_bench import assign_aliases, select_sample
from scripts.matching_bench import (
    BenchDatabase,
    agreement,
    build_results_payload,
    compute_metrics,
    false_positive_rate_at_k,
    judge_coherence,
    parse_judge_label,
    precision_at_k,
    rank_chronological,
    rank_twopass,
    run_judge,
    run_twopass,
    select_validation_pairs,
)

USER_A = "65f000000000000000000001"
USER_B = "65f000000000000000000002"
PROFILE_HEADLINE = "Animatrice petite enfance"


def _oid(n: int) -> str:
    return f"{n:024x}"


def _llm_response(payload):
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=json.dumps(payload)))]
    response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)
    return response


def _offer(n: int, matched=(), created_at=None, **fields):
    doc = {
        "_id": ObjectId(_oid(n)),
        "poste": f"Poste {n}",
        "entreprise": f"Entreprise {n}",
        "description": "Description de l'offre.",
        "matched_user_ids": list(matched),
    }
    if created_at is not None:
        doc["created_at"] = created_at
    doc.update(fields)
    return doc


def _export(offers, sample_ids, interactions=(), publication_counts=None):
    return {
        "exported_at": datetime(2026, 10, 24, tzinfo=timezone.utc),
        "seed": 20261024,
        "profiles": [
            {
                "alias": "A",
                "user_id": USER_A,
                "profile": {"user_id": USER_A, "headline": PROFILE_HEADLINE, "preferences": {}},
            }
        ],
        "sample_offer_ids": list(sample_ids),
        "interactions": list(interactions),
        "offers": list(offers),
        "publication_counts": publication_counts or {},
        "missing_interaction_offer_ids": [],
    }


# --- Échantillon (export) ---


def _candidates():
    candidates = []
    n = 0
    for matched, count in (([USER_A], 50), ([USER_B], 50), ([USER_A, USER_B], 10), ([], 60), (["autre"], 40)):
        for _ in range(count):
            n += 1
            candidates.append({"_id": ObjectId(_oid(n)), "matched_user_ids": list(matched)})
    return candidates


def test_select_sample_mixes_matched_and_unmatched_offers_deterministically():
    candidates = _candidates()
    excluded = {_oid(1), _oid(2), _oid(3)}

    sample = select_sample(candidates, [USER_A, USER_B], excluded, seed=20261024)
    shuffled = list(candidates)
    random.Random(1).shuffle(shuffled)

    assert sample == select_sample(shuffled, [USER_A, USER_B], excluded, seed=20261024)
    assert len(sample) == 100 and len(set(sample)) == 100
    assert not excluded & set(sample)
    matched = {str(c["_id"]): set(c["matched_user_ids"]) for c in candidates}
    assert sum(USER_A in matched[oid] for oid in sample) >= 30
    assert sum(USER_B in matched[oid] for oid in sample) >= 30
    assert sum(not matched[oid] & {USER_A, USER_B} for oid in sample) == 40


def test_select_sample_takes_what_exists_when_pools_are_small():
    candidates = [
        {"_id": ObjectId(_oid(n)), "matched_user_ids": [USER_A]} for n in range(1, 6)
    ] + [{"_id": ObjectId(_oid(n)), "matched_user_ids": []} for n in range(6, 9)]

    sample = select_sample(candidates, [USER_A, USER_B], set(), seed=1)

    assert sorted(sample) == sorted(_oid(n) for n in range(1, 9))


def test_assign_aliases_orders_by_interaction_count_then_user_id():
    assert assign_aliases({"u2": 11, "u1": 30, "u3": 11}) == {"u1": "A", "u2": "B", "u3": "C"}


# --- Base en mémoire pour le Two-Pass ---


@pytest.mark.asyncio
async def test_bench_database_runs_compute_offer_evaluation_read_only():
    offer = _offer(
        1,
        entreprise="Mairie de Lyon ",
        canonical_title="animateur periscolaire",
        description="Titulaire du BAFA, vous encadrez des groupes d'enfants.",
    )
    db = BenchDatabase(_export([offer], [_oid(1)], publication_counts={_oid(1): 3}))
    pass1 = _llm_response(
        {
            "archetype": "Animateur périscolaire",
            "summary": "Encadrement périscolaire.",
            "requirements": [
                {"requirement": "BAFA", "weight": "critical", "quote_from_offer": "Titulaire du BAFA"},
            ],
            "ghost_job_warnings": [],
        }
    )
    pass2 = _llm_response({"domain_coherence": "strong", "matched_requirements": [], "missing_requirements": []})
    llm = AsyncMock(side_effect=[pass1, pass2])

    with patch("app.services.evaluation.evaluator.compute_domain_relevance", AsyncMock(return_value=None)), \
         patch("app.services.evaluation.evaluator.acompletion", llm):
        run = await compute_offer_evaluation(db, USER_A, _oid(1))

    assert run.evaluation["offer_id"] == _oid(1)
    assert run.evaluation["bloc_g"]["reposted_frequency"] == "3 publications"
    pass2_prompt = llm.call_args_list[1].kwargs["messages"][0]["content"]
    assert PROFILE_HEADLINE in pass2_prompt
    for name in ("job_offers", "candidate_profile"):
        for method in ("insert_one", "update_one", "update_many", "replace_one", "delete_one", "bulk_write"):
            assert not hasattr(db[name], method)
    with pytest.raises(KeyError):
        db["offer_evaluations"]


# --- Classements et métriques ---


def test_rank_chronological_puts_matched_offers_first_newest_first():
    offers = {
        _oid(1): _offer(1, matched=[USER_A], created_at="2026-10-01T00:00:00"),
        _oid(2): _offer(2, matched=[USER_A], created_at=datetime(2026, 10, 10)),
        _oid(3): _offer(3, matched=[], created_at=datetime(2026, 10, 20, tzinfo=timezone.utc)),
        _oid(4): _offer(4, matched=[USER_A]),
    }

    ranking = rank_chronological(offers, [_oid(1), _oid(2), _oid(3), _oid(4)], USER_A)

    assert ranking == [_oid(2), _oid(1), _oid(4), _oid(3)]


def test_rank_twopass_orders_by_score_with_failures_last():
    offers = {
        _oid(1): _offer(1, created_at=datetime(2026, 10, 1)),
        _oid(2): _offer(2, created_at=datetime(2026, 10, 2)),
        _oid(3): _offer(3, created_at=datetime(2026, 10, 3)),
        _oid(4): _offer(4, created_at=datetime(2026, 10, 4)),
    }
    scores = {_oid(1): 3.0, _oid(2): 4.5, _oid(3): None, _oid(4): 3.0}

    ranking = rank_twopass(offers, list(offers), scores)

    assert ranking == [_oid(2), _oid(4), _oid(1), _oid(3)]


def test_precision_and_false_positive_rate():
    ranking = ["a", "b", "c", "d"]
    labels = {"a": "relevant", "b": "irrelevant", "c": "partial", "d": "relevant"}

    assert precision_at_k(ranking, labels, 2) == 0.5
    assert precision_at_k(ranking, labels, 4) == 0.5
    assert precision_at_k(ranking, labels, 10) == 0.5
    assert false_positive_rate_at_k(ranking, labels, 4) == 0.25


def test_parse_judge_label_accepts_known_labels_only():
    assert parse_judge_label('{"label": "Relevant", "justification": "Même métier."}') == (
        "relevant",
        "Même métier.",
    )
    assert parse_judge_label('```json\n{"label": "partial", "justification": ""}\n```')[0] == "partial"
    with pytest.raises(ValueError):
        parse_judge_label('{"label": "maybe", "justification": ""}')
    with pytest.raises(ValueError):
        parse_judge_label("pas du JSON")


def test_judge_coherence_and_agreement():
    labels = {("A", "o1"): "relevant", ("A", "o2"): "partial", ("A", "o3"): "irrelevant"}
    interactions = [
        {"alias": "A", "offer_id": "o1", "status": "applied"},
        {"alias": "A", "offer_id": "o2", "status": "applied"},
        {"alias": "A", "offer_id": "o3", "status": "hidden"},
    ]

    coherence = judge_coherence(interactions, labels)
    assert coherence["applied"] == {"n": 2, "relevant": 1, "partial": 1, "irrelevant": 0}
    assert coherence["hidden"] == {"n": 1, "relevant": 0, "partial": 0, "irrelevant": 1}

    human = {("A", "o1"): "relevant", ("A", "o2"): "irrelevant", ("A", "o3"): "irrelevant"}
    result = agreement(human, labels)
    assert result["n"] == 3
    assert result["exact"] == pytest.approx(2 / 3)
    assert result["binary"] == 1.0


def test_compute_metrics_on_tiny_bench():
    offers = [
        _offer(1, matched=[USER_A], created_at=datetime(2026, 10, 3)),
        _offer(2, matched=[USER_A], created_at=datetime(2026, 10, 2)),
        _offer(3, matched=[], created_at=datetime(2026, 10, 1)),
    ]
    export = _export(offers, [_oid(1), _oid(2), _oid(3)])
    judge_records = [
        {"alias": "A", "offer_id": _oid(1), "set": "sample", "label": "irrelevant", "input_tokens": 10, "output_tokens": 5},
        {"alias": "A", "offer_id": _oid(2), "set": "sample", "label": "partial", "input_tokens": 10, "output_tokens": 5},
        {"alias": "A", "offer_id": _oid(3), "set": "sample", "label": "relevant", "input_tokens": 10, "output_tokens": 5},
    ]
    twopass_records = [
        {"alias": "A", "offer_id": _oid(1), "score": 1.0, "input_tokens": 100, "output_tokens": 50, "latency_ms": 1000},
        {"alias": "A", "offer_id": _oid(2), "score": 2.0, "input_tokens": 100, "output_tokens": 50, "latency_ms": 3000},
        {"alias": "A", "offer_id": _oid(3), "score": 4.5, "input_tokens": 100, "output_tokens": 50, "latency_ms": 2000},
    ]

    metrics = compute_metrics(export, judge_records, twopass_records, [], twopass_model="gemini/gemini-3.8-flash")

    chrono = metrics["per_profile"]["A"]["chronological"]
    twopass = metrics["per_profile"]["A"]["twopass"]
    assert chrono["p@10"] == pytest.approx(1 / 3) and chrono["fp@20"] == pytest.approx(1 / 3)
    assert twopass["p@10"] == pytest.approx(1 / 3)
    assert twopass["top3"] == [_oid(3), _oid(2), _oid(1)]
    assert chrono["top3"] == [_oid(1), _oid(2), _oid(3)]
    assert metrics["twopass_cost"]["n_ok"] == 3 and metrics["twopass_cost"]["latency_ms_mean"] == 2000
    assert metrics["agreement"]["n"] == 0


def test_select_validation_pairs_is_balanced_and_deterministic():
    labels = {}
    for alias in ("A", "B"):
        for i, label in enumerate(["relevant", "partial", "irrelevant"] * 5):
            labels[(alias, f"{alias}{i}")] = label

    pairs = select_validation_pairs(labels, ["A", "B"], seed=7)

    assert pairs == select_validation_pairs(labels, ["A", "B"], seed=7)
    assert len(pairs) == 20 and len(set(pairs)) == 20
    for alias in ("A", "B"):
        mine = [p for p in pairs if p[0] == alias]
        assert len(mine) == 10
        assert all(sum(labels[p] == label for p in mine) >= 3 for label in ("relevant", "partial", "irrelevant"))


# --- Dépense : rien sans --confirm ---


@pytest.mark.asyncio
async def test_judge_dry_run_makes_no_llm_call(tmp_path):
    export = _export(
        [_offer(1), _offer(2), _offer(3)],
        [_oid(1), _oid(2)],
        interactions=[{"alias": "A", "offer_id": _oid(3), "status": "applied"}],
    )
    cache = tmp_path / "judge_cache.json"
    llm = AsyncMock(side_effect=AssertionError("aucun appel LLM sans --confirm"))

    with patch("scripts.matching_bench.acompletion", llm):
        pending = await run_judge(export, cache, confirm=False)

    assert pending == 3
    llm.assert_not_called()
    assert not cache.exists()


@pytest.mark.asyncio
async def test_twopass_dry_run_makes_no_llm_call(tmp_path):
    export = _export([_offer(1), _offer(2)], [_oid(1), _oid(2)])
    cache = tmp_path / "twopass_cache.json"
    compute = AsyncMock(side_effect=AssertionError("aucun Two-Pass sans --confirm"))

    with patch("scripts.matching_bench.compute_offer_evaluation", compute):
        pending = await run_twopass(export, cache, confirm=False)

    assert pending == 2
    compute.assert_not_called()
    assert not cache.exists()


@pytest.mark.asyncio
async def test_judge_confirm_fills_cache_and_resumes(tmp_path):
    export = _export([_offer(1), _offer(2)], [_oid(1), _oid(2)])
    cache = tmp_path / "judge_cache.json"
    llm = AsyncMock(return_value=_llm_response({"label": "relevant", "justification": "Même métier."}))

    with patch("scripts.matching_bench.acompletion", llm):
        await run_judge(export, cache, confirm=True)
        pending_after = await run_judge(export, cache, confirm=False)

    assert llm.await_count == 2
    assert pending_after == 0
    records = json.loads(cache.read_text())
    assert {r["label"] for r in records.values()} == {"relevant"}
    first_messages = llm.call_args_list[0].kwargs["messages"]
    assert PROFILE_HEADLINE in first_messages[1]["content"]


# --- Fichier versionné ---


def test_results_payload_contains_no_profile_data():
    export = _export([_offer(1)], [_oid(1)])
    judge_records = [
        {
            "alias": "A",
            "offer_id": _oid(1),
            "set": "sample",
            "label": "relevant",
            "justification": f"{PROFILE_HEADLINE} avec cinq ans d'expérience.",
            "input_tokens": 10,
            "output_tokens": 5,
        }
    ]
    twopass_records = [
        {
            "alias": "A",
            "offer_id": _oid(1),
            "score": 4.0,
            "input_tokens": 100,
            "output_tokens": 50,
            "latency_ms": 1200,
            "models_used": ["gemini/gemini-3.8-flash"],
        }
    ]
    human = [{"alias": "A", "offer_id": _oid(1), "label": "relevant"}]

    payload = build_results_payload(
        export, judge_records, twopass_records, human, {"per_profile": {}}, twopass_model="gemini/gemini-3.8-flash"
    )

    serialized = json.dumps(payload, default=str)
    assert USER_A not in serialized
    assert PROFILE_HEADLINE not in serialized
    assert "justification" not in serialized
    assert set(payload) == {"meta", "judge", "twopass", "human", "metrics"}
    assert payload["meta"]["n_profiles"] == 1 and payload["meta"]["n_sample"] == 1
