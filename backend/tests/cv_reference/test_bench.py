"""Banc de couverture hors réseau : métriques, mode simulé, garde-fous du mode réel."""
import json
from unittest.mock import AsyncMock, patch

import pytest

from scripts import llm_budget
from scripts.cv_reference_bench import compute_metrics, run_bench
from tests.cv_reference.fixtures import (INVENTED_EXPERIENCE, INVENTED_ROLE_EXPERIENCE, inventing_oracle,
                                         llm_response, refusing_acompletion)

TRUTH = {
    "experiences": [{"company": "Acme", "role": "Data Engineer", "start_date": "2021-09", "end_date": "present"},
                    {"company": "Société Générale Fictive", "role": "Analyste", "start_date": "2019", "end_date": "2021"}],
    "contact": {"email": "a@example.com"},
    "headline": "Data",
}
FACTS = [
    {"fait": "Acme", "champ": "experiences.company", "page": 1, "critique": True},
    {"fait": "Société Générale Fictive", "champ": "experiences.company", "page": 1, "critique": True},
    {"fait": "Data Engineer", "champ": "experiences.role", "page": 1, "critique": True},
]


@pytest.fixture
def run(cases, reference, generated):
    """Lance le banc sur quelques cas du manifeste (PDF déjà générés, sortie en tmp)."""

    async def _run(case_ids, **kwargs):
        wanted = [c for c in cases if c["case_id"] in case_ids]
        return await run_bench(generated["manifest"], wanted, reference, out_dir=generated["out_dir"], **kwargs)

    return _run


def by_id(report):
    return {r["case_id"]: r for r in report["results"]}


@pytest.mark.parametrize("extracted, recall, missed, invented", [
    ([{"company": "ACME", "role": "Data Engineer", "start": "2021-09", "end": None}], 0.5, ["Société Générale Fictive"], 0),
    ([{"company": "societe generale fictive", "role": "Analyste", "start": "2019", "end": "2021"}], 0.5, ["Acme"], 0),
    ([{"company": "Acme"}, {"company": "Société Générale Fictive"}], 1.0, [], 0),
    ([{"company": "Acme"}, {"company": "Inventée SA"}], 0.5, ["Société Générale Fictive"], 1),
    ([{"company": "Acme", "role": "Directrice"}], 0.5, ["Société Générale Fictive"], 1),
    ([], 0.0, ["Acme", "Société Générale Fictive"], 0),
])
def test_compute_metrics(extracted, recall, missed, invented):
    metrics = compute_metrics(FACTS, TRUTH, {"experiences": extracted, "headline": "x"})
    assert metrics["experience_recall"] == recall
    assert metrics["missed_experiences"] == missed
    assert len(metrics["invented_facts"]) == invented


def test_compute_metrics_counts_non_empty_sections_and_wrong_critical_email():
    facts = FACTS + [{"fait": "a@example.com", "champ": "contact.email", "page": 1, "critique": True}]
    result = {"headline": "x", "summary": "", "experiences": [{"company": "Acme"}], "skills": {}, "contact": {"email": "b@example.com"}}
    metrics = compute_metrics(facts, TRUTH, result)
    assert metrics["fields_extracted"] == 3
    assert any("email" in f for f in metrics["invented_facts"])


async def test_long_case_recovers_everything_and_uses_text_for_late_pages(run):
    report = await run(["lg_p04"])
    r = by_id(report)["lg_p04"]
    assert r["experience_recall"] == 1.0 and r["invented_facts"] == []
    assert r["pages_by_method"]["vlm"] == [1, 2, 3] and r["pages_by_method"]["text"] == [4]
    assert r["pages_covered"] == 1.0 and r["all_pages_handled"] and r["cost_usd"] > 0


async def test_scanned_long_case_reports_its_skipped_pages(run):
    r = by_id(await run(["sc_p04"]))["sc_p04"]
    assert r["skipped_pages"] == [4] and r["pages_covered"] == 0.75
    assert r["all_pages_handled"] and r["experience_recall"] < 1.0


@pytest.mark.parametrize("factory", [
    inventing_oracle(INVENTED_EXPERIENCE),
    inventing_oracle(INVENTED_ROLE_EXPERIENCE, replace_role=True),
])
async def test_invented_facts_are_detected(run, factory):
    r = by_id(await run(["oc_p01"], oracle_factory=factory))["oc_p01"]
    assert len(r["invented_facts"]) > 0


async def test_simulated_mode_never_touches_the_budget_ledger(run):
    await run(["oc_p01", "lg_p04", "pr_p02"])
    assert not llm_budget.LEDGER_PATH.exists()


@pytest.mark.parametrize("case_id, expectation", [
    ("pr_p02", "rejected"), ("un_corrupt", "error"), ("em_blank", "empty"),
])
async def test_expected_rejections_are_not_failures(run, case_id, expectation):
    r = by_id(await run([case_id]))[case_id]
    assert r["expected_rejection"] and r["expectation_met"]
    assert r["rejected"] if expectation == "rejected" else True
    assert (r["errors"] and all(isinstance(e, str) and e for e in r["errors"])) or expectation == "empty"


async def test_aggregates_group_by_category(run):
    report = await run(["oc_p01", "oc_p02", "lg_p04"])
    assert report["aggregates"]["by_category"]["one_column"]["n_cases"] == 2
    assert report["aggregates"]["global"]["n_cases"] == 3
    assert "mode simulé" in report["summary"]


async def test_real_mode_with_exhausted_budget_makes_no_call(run):
    llm_budget.record_call("parser", "preload", "m", 0.25, "estimated")
    fake = refusing_acompletion()
    with patch("app.services.cv_parser.acompletion", fake):
        with pytest.raises(llm_budget.BudgetExceeded):
            await run(["lg_p04"], mode="real", confirm=True)
    fake.assert_not_called()


async def test_real_without_confirm_only_estimates(run):
    fake = refusing_acompletion()
    with patch("app.services.cv_parser.acompletion", fake):
        report = await run(["lg_p04", "oc_p01"], mode="real", confirm=False)
    fake.assert_not_called()
    assert report["estimate_usd"] > 0 and report["results"] == []
    assert not llm_budget.LEDGER_PATH.exists()


async def test_real_mode_records_the_cost_of_a_completed_import(run, monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "dummy")
    payload = {"headline": "Data", "experiences": [{"company": "X", "role": "Y"}]}
    with patch("app.services.cv_parser.acompletion", AsyncMock(return_value=llm_response(payload))):
        report = await run(["oc_p02"], mode="real", confirm=True)
    rows = [json.loads(line) for line in llm_budget.LEDGER_PATH.read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["plan"] == "parser" and rows[0]["case_id"] == "oc_p02"
    assert rows[0]["cost_usd"] == pytest.approx(by_id(report)["oc_p02"]["cost_usd"])
    assert rows[0]["cost_usd"] > 0


async def test_real_mode_records_nothing_for_a_total_failure(run, monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "dummy")
    broken = AsyncMock(return_value=llm_response({}, 100, 50))
    broken.return_value.choices[0].message.content = "pas du json"
    with patch("app.services.cv_parser.acompletion", broken):
        report = await run(["oc_p02"], mode="real", confirm=True)
    r = by_id(report)["oc_p02"]
    assert r["cost_usd"] > 0 and not r["cost_recorded"]
    assert not llm_budget.LEDGER_PATH.exists()
