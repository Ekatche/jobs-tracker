"""Tests de logique et d'invariants pour le banc de mesure du matching.

Couvre la sélection d'échantillon, les algorithmes de classement,
les métriques mathématiques, les gardes PII et la gestion de cache.
"""

from datetime import datetime, timezone
import json
import random
from unittest.mock import AsyncMock, MagicMock, patch

from bson import ObjectId
import pytest

from app.services.offer_scoring.constants import EMBEDDING_MODEL
from app.services.offer_scoring.embeddings import offer_embedding_text, text_hash
from app.services.offer_scoring.score import ScoreResult, profile_features
from app.services.usage_tracker import estimate_llm_cost
from scripts.export_matching_bench import assign_aliases, select_sample
from scripts.matching_bench import (
    JUDGE_FALLBACK_MODEL,
    JUDGE_MODEL,
    agreement,
    build_results_payload,
    compute_metrics,
    false_positive_rate_at_k,
    hybrid_cos_key,
    hybrid_scores,
    judge_coherence,
    judge_key,
    parse_judge_label,
    precision_at_k,
    rank_chronological,
    rank_hybrid,
    rank_twopass,
    run_embed,
    run_judge,
    select_validation_pairs,
)

USER_A = "65f000000000000000000001"
USER_B = "65f000000000000000000002"
PROFILE_HEADLINE = "Animatrice petite enfance"


def _oid(n: int) -> str:
    return f"{n:024x}"


def _offer(n: int, matched=(), created_at=None, **fields) -> dict:
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


def _export(offers, sample_ids, interactions=()) -> dict:
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
        "publication_counts": {},
        "missing_interaction_offer_ids": [],
    }


def _score_result(score: float, breakdown=None) -> ScoreResult:
    return ScoreResult(
        score=score,
        raw_score=score,
        level="strong",
        breakdown=breakdown or {"raw_score": score},
        unknown_components=[],
        failed_conditions=[],
    )


# --- 1. Échantillonnage & Aliases ---


def test_select_sample_mixes_matched_and_unmatched_offers_deterministically():
    candidates = []
    n = 0
    for matched, count in (([USER_A], 50), ([USER_B], 50), ([USER_A, USER_B], 10), ([], 60), (["autre"], 40)):
        for _ in range(count):
            n += 1
            candidates.append({"_id": ObjectId(_oid(n)), "matched_user_ids": list(matched)})

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


# --- 2. Algorithmes de classement ---


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
        _oid(n): _offer(n, created_at=datetime(2026, 10, n)) for n in range(1, 5)
    }
    scores = {_oid(1): 3.0, _oid(2): 4.5, _oid(3): None, _oid(4): 3.0}
    ranking = rank_twopass(offers, list(offers), scores)
    assert ranking == [_oid(2), _oid(4), _oid(1), _oid(3)]


def test_rank_hybrid_orders_by_score_with_filtered_last_and_breaks_ties():
    assessed = {
        "o1": (None, _score_result(80.0)),
        "o2": (None, _score_result(40.0)),
        "o3": (None, _score_result(60.0)),
        "o4": ("geo", None),
    }
    assert rank_hybrid(["o1", "o2", "o3", "o4"], assessed) == ["o1", "o3", "o2", "o4"]

    # Départage par cosinus brut quand les scores et composantes sémantiques sont identiques
    tied = _score_result(50.0, breakdown={"semantic": 45.0})
    tied_assessed = {"offer_none": (None, tied), "offer_low": (None, tied), "offer_high": (None, tied)}
    cos = {"offer_low": 0.84, "offer_high": 0.98, "offer_none": None}
    assert rank_hybrid(["offer_none", "offer_low", "offer_high"], tied_assessed, cos) == [
        "offer_high", "offer_low", "offer_none"
    ]


# --- 3. Métriques & Parsing LLM ---


def test_precision_and_false_positive_rate():
    ranking = ["a", "b", "c", "d"]
    labels = {"a": "relevant", "b": "irrelevant", "c": "partial", "d": "relevant"}
    assert precision_at_k(ranking, labels, 2) == 0.5
    assert precision_at_k(ranking, labels, 4) == 0.5
    assert precision_at_k(ranking, labels, 10) == 0.5
    assert false_positive_rate_at_k(ranking, labels, 4) == 0.25


@pytest.mark.parametrize(
    ("raw_json", "expected_label", "expected_justification"),
    [
        ('{"label": "Relevant", "justification": "Même métier."}', "relevant", "Même métier."),
        ('```json\n{"label": "partial", "justification": "Proche."}\n```', "partial", "Proche."),
        ('{"label": "irrelevant", "justification": ""}', "irrelevant", ""),
    ],
)
def test_parse_judge_label_valid(raw_json, expected_label, expected_justification):
    label, justification = parse_judge_label(raw_json)
    assert label == expected_label
    assert justification == expected_justification


@pytest.mark.parametrize("invalid_input", ['{"label": "maybe"}', "pas du JSON", ""])
def test_parse_judge_label_invalid_raises(invalid_input):
    with pytest.raises(ValueError):
        parse_judge_label(invalid_input)


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


def test_compute_metrics_includes_hybrid_and_recall_guard():
    offers = [_offer(1, created_at=datetime(2026, 10, 1)), _offer(2, created_at=datetime(2026, 10, 2))]
    export = _export(offers, [_oid(1), _oid(2)], interactions=[{"alias": "A", "offer_id": _oid(1), "status": "applied"}])
    cos_records = [{"alias": "A", "offer_id": _oid(1), "cos": 0.1}]
    hybrid = hybrid_scores(export, cos_records)

    metrics = compute_metrics(export, [], [], [], twopass_model="gemini/gemini-3.8-flash", hybrid=hybrid)
    assert "p@10" in metrics["per_profile"]["A"]["hybrid"]
    assert metrics["per_profile"]["A"]["separation"]["applied_below_floor"] == [_oid(1)]


# --- 4. Cache & Ruling Identité ---


@pytest.mark.asyncio
async def test_hybrid_cos_cache_reused_only_for_same_text(tmp_path):
    offer = _offer(1)
    export = _export([offer], [_oid(1)])
    cache_path = tmp_path / "hybrid_cos_cache.json"
    identity = profile_features(export["profiles"][0]["profile"]).identity
    stale_record = {
        "alias": "A",
        "offer_id": _oid(1),
        "model": EMBEDDING_MODEL,
        "text_hash": text_hash("texte périmé"),
        "identity_hash": text_hash(identity),
        "cos": 0.1,
    }
    cache_path.write_text(json.dumps({hybrid_cos_key(EMBEDDING_MODEL, "A", _oid(1)): stale_record}))
    fake_embed = AsyncMock(return_value=[[1.0, 0.0]])

    with patch("scripts.matching_bench.embed_texts", fake_embed):
        await run_embed(export, cache_path, confirm=True)

    assert fake_embed.await_count == 2
    updated = json.loads(cache_path.read_text())[hybrid_cos_key(EMBEDDING_MODEL, "A", _oid(1))]
    assert updated["text_hash"] == text_hash(offer_embedding_text(offer))
    assert updated["cos"] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_run_embed_skips_pending_for_profile_without_identity(tmp_path):
    export = _export([_offer(1)], [_oid(1)])
    export["profiles"][0]["profile"]["headline"] = ""
    cache = tmp_path / "hybrid_cos_cache.json"
    fake_embed = AsyncMock(side_effect=AssertionError("aucun embedding sans identité"))

    with patch("scripts.matching_bench.embed_texts", fake_embed):
        await run_embed(export, cache, confirm=True)

    fake_embed.assert_not_called()


# --- 5. Juge LLM : repli et coût multi-modèle ---


@pytest.mark.asyncio
async def test_judge_fallback_only_judges_pairs_the_main_judge_missed(tmp_path):
    export = _export([_offer(1), _offer(2)], [_oid(1), _oid(2)])
    cache = tmp_path / "judge_cache.json"
    main_record = {
        "alias": "A", "offer_id": _oid(1), "set": "sample", "label": "irrelevant",
        "model": JUDGE_MODEL, "input_tokens": 1000, "output_tokens": 100,
    }
    cache.write_text(json.dumps({judge_key("A", _oid(1)): main_record}))

    llm_response = MagicMock()
    llm_response.choices = [MagicMock(message=MagicMock(content=json.dumps({"label": "partial", "justification": "Proche."})))]
    llm_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)
    llm = AsyncMock(return_value=llm_response)

    with patch("scripts.matching_bench.acompletion", llm):
        await run_judge(export, cache, confirm=True, model=JUDGE_FALLBACK_MODEL)

    assert llm.await_count == 1
    assert llm.call_args.kwargs["model"] == JUDGE_FALLBACK_MODEL
    fallback = json.loads(cache.read_text())[judge_key("A", _oid(2), JUDGE_FALLBACK_MODEL)]
    assert fallback["model"] == JUDGE_FALLBACK_MODEL and fallback["label"] == "partial"


def test_judge_cost_uses_each_record_model():
    export = _export([_offer(1), _offer(2)], [_oid(1), _oid(2)])
    legacy = {"alias": "A", "offer_id": _oid(1), "set": "sample", "label": "relevant", "input_tokens": 1000, "output_tokens": 100}
    fallback = {"alias": "A", "offer_id": _oid(2), "set": "sample", "label": "partial", "model": JUDGE_FALLBACK_MODEL, "input_tokens": 1000, "output_tokens": 100}
    records = [legacy, fallback]

    cost = compute_metrics(export, records, [], [], twopass_model="gemini/gemini-3.8-flash")["judge_cost"]
    expected = estimate_llm_cost(JUDGE_MODEL, 1000, 100) + estimate_llm_cost(JUDGE_FALLBACK_MODEL, 1000, 100)
    assert cost["cost_usd"] == pytest.approx(round(expected, 4))
    assert cost["models"] == {JUDGE_MODEL: 1, JUDGE_FALLBACK_MODEL: 1}


# --- 6. Garde-fou d'anonymisation PII ---


def test_results_payload_contains_no_profile_data():
    export = _export([_offer(1)], [_oid(1)])
    profile = export["profiles"][0]["profile"]
    profile["skills"] = {"tech": ["Python secret skill"]}
    profile["preferences"] = {"target_roles": ["Role très spécifique"]}

    judge_records = [
        {"alias": "A", "offer_id": _oid(1), "set": "sample", "label": "relevant", "justification": "Confidentiel.", "input_tokens": 10, "output_tokens": 5}
    ]
    twopass_records = [
        {"alias": "A", "offer_id": _oid(1), "score": 4.0, "input_tokens": 100, "output_tokens": 50, "latency_ms": 1200}
    ]
    cos_records = [{"alias": "A", "offer_id": _oid(1), "cos": 0.9}]
    hybrid = hybrid_scores(export, cos_records)

    metrics = compute_metrics(
        export, judge_records, twopass_records, [], twopass_model="gemini/gemini-3.8-flash", hybrid=hybrid
    )
    payload = build_results_payload(
        export, judge_records, twopass_records, [], metrics, twopass_model="gemini/gemini-3.8-flash"
    )

    serialized = json.dumps(payload, default=str)
    assert USER_A not in serialized
    assert PROFILE_HEADLINE not in serialized
    assert "secret skill" not in serialized
    assert "spécifique" not in serialized
    assert "justification" not in serialized
    assert set(payload) == {"meta", "judge", "twopass", "human", "metrics"}
