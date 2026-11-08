import json

import pytest

from scripts import llm_budget
from scripts.llm_budget import BudgetExceeded, check_budget, record_call, spent_usd


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    path = tmp_path / "data" / "llm_budget.jsonl"
    monkeypatch.setattr(llm_budget, "LEDGER_PATH", path)
    return path


def _record(plan, cost, path=None):
    return record_call(plan, "script.py", "model-x", cost, "estimated", path=path)


def test_absent_ledger_spent_zero(ledger):
    assert spent_usd() == 0
    assert spent_usd("profil") == 0
    assert not ledger.exists()


def test_record_then_spent_by_plan_and_total(ledger):
    _record("profil", 0.10)
    _record("parser", 0.05)
    _record("profil", 0.02)
    assert spent_usd("profil") == pytest.approx(0.12)
    assert spent_usd("parser") == pytest.approx(0.05)
    assert spent_usd() == pytest.approx(0.17)


def test_record_line_format_and_extra(ledger):
    line = record_call("lettres", "s.py", "m", 0.3, "billed", tokens=42)
    assert set(line) >= {"date", "plan", "script", "model", "cost_usd", "cost_kind", "tokens"}
    assert json.loads(ledger.read_text().splitlines()[0]) == line


@pytest.mark.parametrize(
    "plan, spent, estimate",
    [
        ("profil", 0.20, 0.10),
    ],
)
def test_refuses_when_plan_share_exceeded(ledger, plan, spent, estimate):
    _record(plan, spent)
    with pytest.raises(BudgetExceeded, match=plan):
        check_budget(plan, estimate)


def test_refuses_when_total_cap_exceeded_though_plan_share_fits(ledger):
    _record("lettres", 1.90)
    _record("parser", 0.30)  # dépassement facturé au-delà de sa part
    _record("profil", 0.25)
    # 2.45 dépensés ; lettres a encore 0.10 de part, mais le total serait 2.51
    with pytest.raises(BudgetExceeded, match="total"):
        check_budget("lettres", 0.06)


def test_accepts_exactly_at_plan_share(ledger):
    _record("profil", 0.15)
    check_budget("profil", 0.10)


@pytest.mark.parametrize(
    "call",
    [
        lambda: check_budget("inconnu", 0.01),
        lambda: check_budget("profil", float("nan")),
        lambda: record_call("profil", "s", "m", -0.01, "estimated"),
        lambda: record_call("inconnu", "s", "m", 0.1, "estimated"),
        lambda: record_call("profil", "s", "m", 0.1, "guessed"),
    ],
)
def test_invalid_arguments_raise_value_error(ledger, call):
    with pytest.raises(ValueError):
        call()


CORRUPT_LINES = [
    "{pas du json",
    '{"plan": "profil", "cost_usd": NaN}',
    '{"plan": "profil", "cost_usd": -0.5}',
    '{"plan": "profil", "cost_usd": true}',
    '{"plan": "profil"}',
    '{"plan": "inconnu", "cost_usd": 0.01}',
    "[1, 2]",
]


@pytest.fixture
def corrupt_ledger(ledger, request):
    _record("profil", 0.01)
    with ledger.open("a", encoding="utf-8") as f:
        f.write(request.param + "\n")
    return ledger


@pytest.mark.parametrize("corrupt_ledger", CORRUPT_LINES, indirect=True)
def test_corrupted_line_refuses_rather_than_undercount(corrupt_ledger):
    with pytest.raises(BudgetExceeded, match="illisible"):
        check_budget("profil", 0.01)
