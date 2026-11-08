"""Registre de budget LLM commun aux plans parseur, profil et lettres.

Une ligne JSON par appel réel dans ``scripts/data/llm_budget.jsonl`` (non
versionné). Aucun appel réseau : simple lecture/écriture de fichier. Usage :
``check_budget`` avant l'appel, ``record_call`` après.
"""

import json
import math
from datetime import datetime, timezone
from pathlib import Path

LEDGER_PATH = Path(__file__).resolve().parent / "data" / "llm_budget.jsonl"
PLAN_CAPS_USD = {"parser": 0.25, "profil": 0.25, "lettres": 2.0}
TOTAL_CAP_USD = 2.50
COST_KINDS = ("estimated", "billed")
_EPSILON = 1e-9  # tolère l'erreur d'arrondi flottant sur les sommes


class BudgetExceeded(Exception):
    """Un appel dépasserait la part du plan ou le plafond commun."""


def _valid_cost(value) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and value >= 0
    )


def _resolve(path):
    return Path(path) if path is not None else LEDGER_PATH


def _read_rows(path):
    """Lignes du registre ; ``ValueError`` si l'une est illisible."""
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as f:
        for number, raw in enumerate(f, start=1):
            if not raw.strip():
                continue
            try:
                row = json.loads(raw)
                row["plan"]
                if not _valid_cost(row["cost_usd"]):
                    raise ValueError("cost_usd invalide")
            except (ValueError, KeyError, TypeError) as exc:
                raise ValueError(f"ligne {number} illisible dans {path}") from exc
            rows.append(row)
    return rows


def spent_usd(plan=None, path=None) -> float:
    """Somme des ``cost_usd`` (tout le registre, ou un plan). Absent => 0."""
    rows = _read_rows(_resolve(path))
    return sum(float(r["cost_usd"]) for r in rows if plan is None or r["plan"] == plan)


def check_budget(plan, estimated_usd, path=None) -> None:
    """Lève ``BudgetExceeded`` si l'appel dépasserait la part du plan ou le total."""
    if plan not in PLAN_CAPS_USD:
        raise ValueError(f"plan inconnu : {plan!r} (attendu : {sorted(PLAN_CAPS_USD)})")
    if not _valid_cost(estimated_usd):
        raise ValueError(f"estimation invalide (finie et >= 0 attendue) : {estimated_usd}")
    try:
        plan_spent = spent_usd(plan, path)
        total_spent = spent_usd(None, path)
    except ValueError as exc:
        raise BudgetExceeded(f"registre illisible, appel refusé : {exc}") from exc
    cap = PLAN_CAPS_USD[plan]
    if plan_spent + estimated_usd > cap + _EPSILON:
        raise BudgetExceeded(
            f"plan {plan} : {plan_spent:.4f} $ dépensés + {estimated_usd:.4f} $ estimés "
            f"> part de {cap:.2f} $"
        )
    if total_spent + estimated_usd > TOTAL_CAP_USD + _EPSILON:
        raise BudgetExceeded(
            f"total : {total_spent:.4f} $ dépensés + {estimated_usd:.4f} $ estimés "
            f"> plafond commun de {TOTAL_CAP_USD:.2f} $ (plan {plan})"
        )


def record_call(plan, script, model, cost_usd, cost_kind, path=None, **extra) -> dict:
    """Ajoute une ligne au registre (mode ajout) et la renvoie."""
    if plan not in PLAN_CAPS_USD:
        raise ValueError(f"plan inconnu : {plan!r} (attendu : {sorted(PLAN_CAPS_USD)})")
    if not _valid_cost(cost_usd):
        raise ValueError(f"cost_usd invalide (fini et >= 0 attendu) : {cost_usd}")
    if cost_kind not in COST_KINDS:
        raise ValueError(f"cost_kind invalide : {cost_kind!r} (attendu : {COST_KINDS})")
    line = {
        "date": datetime.now(timezone.utc).isoformat(),
        "plan": plan,
        "script": script,
        "model": model,
        "cost_usd": cost_usd,
        "cost_kind": cost_kind,
        **extra,
    }
    target = _resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    return line
