# backend/scripts/reference_bench.py
"""Banc de matching sur le jeu de référence synthétique commun (plan profil, tâche 1c).

Adapte `scripts/reference/` au format de `matching_bench.load_export` (les labels annotés
remplacent le juge LLM), puis mesure le score hybride par profil sur ses seules offres
annotées : précision@5, nDCG@10, rappel, faux négatifs, préférences violées dans le
top 5. Aucun appel réseau ici ; l'embedding passe par `matching_bench.py --reference embed`.
Aucune métrique n'est assertée contre les cibles du plan : elles sont rapportées.
"""

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.offer_scoring.constants import EMBEDDING_MODEL, FLOOR
from app.services.profile.merge import build_profile_from_sources
from scripts import matching_bench
from scripts.matching_bench import _is_detached, precision_at_k, rank_chronological, rank_hybrid

LABEL_MAP = {"pertinent": "relevant", "partiel": "partial", "hors_sujet": "irrelevant"}
GAINS = {"relevant": 2, "partial": 1, "irrelevant": 0}
SMALL_SUBGROUP_RELEVANT = 20
EXPORTED_AT = datetime(2026, 11, 8, tzinfo=timezone.utc)
REFERENCE_DATA_DIR = matching_bench.DATA_DIR / "reference"
REFERENCE_COS_CACHE = REFERENCE_DATA_DIR / "hybrid_cos_cache.json"
REFERENCE_RESULTS_PATH = Path("scripts/reference_bench_results.json")
SUBGROUP_DIMENSIONS = ("metier", "niveau", "langue", "reconversion", "sources")
RANKINGS = ("hybrid", "chronological")


# --- Adaptateur vers le format de `load_export` ---


def _parse_created_at(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def reference_to_export(ref: Dict[str, Any]) -> Dict[str, Any]:
    """Jeu de référence au format de `matching_bench.load_export`. `alias = user_id = profile_id`."""
    profiles = []
    for p in ref["profiles"]:
        pid = p["profile_id"]
        profile, _conflicts = build_profile_from_sources(p["sources"])
        profiles.append({"alias": pid, "user_id": pid, "profile": {**profile, "user_id": pid}})
    offers = [
        {**o, "_id": o["offer_id"], "created_at": _parse_created_at(o.get("created_at"))}
        for o in ref["offers"]
    ]
    labelled = {r["offer_id"] for r in ref["matching_labels"]}
    return {
        "exported_at": EXPORTED_AT,
        "seed": 0,
        "profiles": profiles,
        "sample_offer_ids": [o["offer_id"] for o in ref["offers"] if o["offer_id"] in labelled],
        "interactions": [],
        "offers": offers,
        "publication_counts": {},
        "missing_interaction_offer_ids": [],
    }


def reference_labels(ref: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """`{profile_id: {offer_id: label}}` avec les labels du banc (relevant/partial/irrelevant)."""
    labels: Dict[str, Dict[str, str]] = {}
    for r in ref["matching_labels"]:
        labels.setdefault(r["profile_id"], {})[r["offer_id"]] = LABEL_MAP[r["label"]]
    return labels


def preference_violations(ref: Dict[str, Any]) -> Dict[str, Set[str]]:
    """`{profile_id: {offer_id}}` des paires annotées `preference_violee: true`."""
    violations: Dict[str, Set[str]] = {}
    for r in ref["matching_labels"]:
        if r.get("preference_violee") is True:
            violations.setdefault(r["profile_id"], set()).add(r["offer_id"])
    return violations


# --- Métriques d'un profil ---


def ndcg_at_k(ranking: List[str], labels: Dict[str, str], k: int = 10) -> float:
    """Gains relevant 2 / partial 1 / irrelevant 0, remise `log2(rang + 1)`. L'idéal est
    calculé sur tous les labels du profil ; 0 si le gain idéal est nul."""

    def dcg(gains: Iterable[int]) -> float:
        return sum(g / math.log2(rank + 1) for rank, g in enumerate(gains, start=1))

    ideal = dcg(sorted((GAINS[label] for label in labels.values()), reverse=True)[:k])
    if ideal == 0:
        return 0.0
    return dcg(GAINS.get(labels.get(oid), 0) for oid in ranking[:k]) / ideal


def recall_and_false_negatives(
    labels: Dict[str, str],
    assessed: Dict[str, Tuple[Optional[str], Any]],
) -> Tuple[Optional[float], List[Dict[str, Any]]]:
    """Rappel des offres `relevant` non détachées ; `None` s'il n'y en a aucune. Les
    faux négatifs sont les `relevant` détachées (filtrées, sans composante ou sous FLOOR)."""
    relevant = [oid for oid, label in labels.items() if label == "relevant"]
    if not relevant:
        return None, []
    false_negatives = []
    for oid in relevant:
        result_tuple = assessed.get(oid, ("missing", None))
        if _is_detached(result_tuple, FLOOR):
            reason, result = result_tuple
            false_negatives.append(
                {
                    "offer_id": oid,
                    "reason": reason or "below_floor",
                    "score": result.score if result is not None else None,
                }
            )
    return (len(relevant) - len(false_negatives)) / len(relevant), false_negatives


def profile_ranking_metrics(ranking: List[str], labels: Dict[str, str], violations: Set[str]) -> Dict[str, Any]:
    return {
        "p@5": precision_at_k(ranking, labels, 5),
        "ndcg@10": ndcg_at_k(ranking, labels, 10),
        "preference_violations@5": sum(oid in violations for oid in ranking[:5]),
    }


# --- Agrégats ---


def _mean(values: List[Optional[float]]) -> Optional[float]:
    kept = [v for v in values if v is not None]
    return sum(kept) / len(kept) if kept else None


def _summarize(pids: List[str], per_profile: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    n_relevant = sum(per_profile[pid]["n_relevant"] for pid in pids)
    summary: Dict[str, Any] = {
        "n_profiles": len(pids),
        "n_relevant": n_relevant,
        "small": n_relevant < SMALL_SUBGROUP_RELEVANT,
    }
    for name in RANKINGS:
        entries = [per_profile[pid][name] for pid in pids]
        keys = ("p@5", "ndcg@10", "preference_violations@5") + (("recall",) if name == "hybrid" else ())
        summary[name] = {key: _mean([e.get(key) for e in entries]) for key in keys}
    summary["hybrid"]["n_false_negatives"] = sum(len(per_profile[pid]["hybrid"]["false_negatives"]) for pid in pids)
    return summary


def _subgroup_value(profile: Dict[str, Any], dimension: str) -> str:
    if dimension == "sources":
        return "+".join(sorted(name for name, payload in profile["sources"].items() if payload))
    value = profile["subgroup"][dimension]
    return str(value).lower() if isinstance(value, bool) else str(value)


def aggregate_subgroups(ref: Dict[str, Any], per_profile: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Moyennes par sous-groupe ; `small` quand moins de 20 offres pertinentes annotées."""
    result: Dict[str, Dict[str, Any]] = {}
    for dimension in SUBGROUP_DIMENSIONS:
        members: Dict[str, List[str]] = {}
        for p in ref["profiles"]:
            members.setdefault(_subgroup_value(p, dimension), []).append(p["profile_id"])
        result[dimension] = {value: _summarize(pids, per_profile) for value, pids in sorted(members.items())}
    return result


def offer_source_recall(
    export: Dict[str, Any],
    labels: Dict[str, Dict[str, str]],
    assessed_all: Dict[str, Dict[str, Tuple[Optional[str], Any]]],
) -> Dict[str, Dict[str, Any]]:
    """Rappel sur les offres `relevant` de chaque `offer.source`, tous profils confondus."""
    offers = matching_bench.offers_by_id(export)
    counts: Dict[str, List[int]] = {}
    for pid, plabels in labels.items():
        for oid, label in plabels.items():
            if label != "relevant":
                continue
            kept = not _is_detached(assessed_all[pid].get(oid, ("missing", None)), FLOOR)
            bucket = counts.setdefault(offers[oid].get("source") or "inconnue", [0, 0])
            bucket[0] += 1
            bucket[1] += kept
    return {
        source: {"n_relevant": n, "recall": kept / n} for source, (n, kept) in sorted(counts.items())
    }


def compute_reference_metrics(
    ref: Dict[str, Any], export: Dict[str, Any], cos_records: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Métriques par profil (offres annotées seulement), agrégats, sous-groupes et sources."""
    labels = reference_labels(ref)
    violations = preference_violations(ref)
    offers = matching_bench.offers_by_id(export)
    assessed_all = matching_bench.hybrid_scores(export, cos_records)
    cos_by_alias: Dict[str, Dict[str, Optional[float]]] = {}
    for r in cos_records:
        cos_by_alias.setdefault(r["alias"], {})[r["offer_id"]] = r["cos"]

    per_profile: Dict[str, Dict[str, Any]] = {}
    for p in export["profiles"]:
        pid = p["alias"]
        plabels = labels.get(pid, {})
        ids = [oid for oid in matching_bench.sample_ids(export) if oid in plabels]
        pviol = violations.get(pid, set())
        recall, false_negatives = recall_and_false_negatives(plabels, assessed_all[pid])
        hybrid_ranking = rank_hybrid(ids, assessed_all[pid], cos_by_alias.get(pid))
        per_profile[pid] = {
            "n_labels": len(plabels),
            "n_relevant": sum(label == "relevant" for label in plabels.values()),
            "hybrid": {
                **profile_ranking_metrics(hybrid_ranking, plabels, pviol),
                "recall": recall,
                "false_negatives": false_negatives,
            },
            "chronological": profile_ranking_metrics(rank_chronological(offers, ids, pid), plabels, pviol),
        }
    pids = [p["profile_id"] for p in ref["profiles"]]
    return {
        "per_profile": per_profile,
        "aggregate": _summarize(pids, per_profile),
        "subgroups": aggregate_subgroups(ref, per_profile),
        "offer_sources": offer_source_recall(export, labels, assessed_all),
    }


# --- Rapport ---


def _fmt(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _print_report(metrics: Dict[str, Any], n_pairs: int, n_cos: int) -> None:
    print(f"Paires évaluées : {n_pairs}, avec cos : {n_cos}, sans cos : {n_pairs - n_cos}\n")
    print("| Profil | p@5 | nDCG@10 | Rappel | Faux négatifs | p@5 chrono | nDCG@10 chrono |")
    print("|---|---|---|---|---|---|---|")
    for pid, m in metrics["per_profile"].items():
        h, c = m["hybrid"], m["chronological"]
        print(
            f"| {pid} | {_fmt(h['p@5'])} | {_fmt(h['ndcg@10'])} | {_fmt(h['recall'])} | "
            f"{len(h['false_negatives'])} | {_fmt(c['p@5'])} | {_fmt(c['ndcg@10'])} |"
        )
    agg = metrics["aggregate"]
    h, c = agg["hybrid"], agg["chronological"]
    print(
        f"| **moyenne** | {_fmt(h['p@5'])} | {_fmt(h['ndcg@10'])} | {_fmt(h['recall'])} | "
        f"{h['n_false_negatives']} | {_fmt(c['p@5'])} | {_fmt(c['ndcg@10'])} |"
    )
    print("\n| Sous-groupe | Profils | Pertinentes | p@5 | nDCG@10 | Rappel | Note |")
    print("|---|---|---|---|---|---|---|")
    for dimension, groups in metrics["subgroups"].items():
        for value, g in groups.items():
            h = g["hybrid"]
            note = "trop petit" if g["small"] else ""
            print(
                f"| {dimension}={value} | {g['n_profiles']} | {g['n_relevant']} | {_fmt(h['p@5'])} | "
                f"{_fmt(h['ndcg@10'])} | {_fmt(h['recall'])} | {note} |"
            )
    print("\n| Source d'offre | Pertinentes | Rappel |")
    print("|---|---|---|")
    for source, s in metrics["offer_sources"].items():
        print(f"| {source} | {s['n_relevant']} | {_fmt(s['recall'])} |")


def run_reference_report(
    ref: Dict[str, Any],
    export: Dict[str, Any],
    cache_path: Path = REFERENCE_COS_CACHE,
    results_path: Path = REFERENCE_RESULTS_PATH,
) -> Dict[str, Any]:
    """Calcule les métriques avec les cos en cache, imprime le tableau Markdown sur stdout
    et écrit le JSON de résultats (jeu synthétique, versionnable)."""
    cos_records = matching_bench.cached_hybrid_cos_records(export, cache_path)
    n_pairs = sum(len(matching_bench._hybrid_assessment_ids(export, p["alias"])) for p in export["profiles"])
    metrics = compute_reference_metrics(ref, export, cos_records)
    _print_report(metrics, n_pairs, len(cos_records))
    payload = {
        "meta": {
            "dataset_date": export["exported_at"].date().isoformat(),
            "embedding_model": EMBEDDING_MODEL,
            "floor": FLOOR,
            "n_profiles": len(ref["profiles"]),
            "n_offers": len(ref["offers"]),
            "n_labels": len(ref["matching_labels"]),
            "n_assessed_pairs": n_pairs,
            "n_cos_pairs": len(cos_records),
            "n_pairs_without_cos": n_pairs - len(cos_records),
        },
        **metrics,
    }
    results_path = Path(results_path)
    results_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    matching_bench.logger.info(f"✅ Résultats écrits dans {results_path}")
    return payload
