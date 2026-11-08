"""Banc de couverture hors réseau : métriques, mode simulé, garde-fous du mode réel."""
import json
from unittest.mock import AsyncMock, patch

import pytest

from scripts import llm_budget
from app.services.cv_parser import DEFAULT_CV_PARSER_MODEL, DEFAULT_VLM_MODEL
from scripts.cv_reference_bench import PRICES_USD_PER_M, compute_metrics, estimate_case_usd, run_bench
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
EMAIL_FACT = {"fait": "a@example.com", "champ": "contact.email", "page": 1, "critique": True}


@pytest.fixture
def run(cases, reference, generated):
    """Lance le banc sur quelques cas du manifeste (PDF déjà générés, sortie en tmp)."""

    async def _run(case_ids, **kwargs):
        wanted = [c for c in cases if c["case_id"] in case_ids]
        return await run_bench(generated["manifest"], wanted, reference, out_dir=generated["out_dir"], **kwargs)

    return _run


def by_id(report):
    return {r["case_id"]: r for r in report["results"]}


@pytest.mark.parametrize("facts, extracted, extra, recall, missed, invented, fields", [
    (FACTS, [{"company": "ACME"}], {}, 0.5, ["Société Générale Fictive"], 0, 2),
    (FACTS, [{"company": "societe generale fictive"}], {}, 0.5, ["Acme"], 0, 2),
    (FACTS, [{"company": "Acme"}, {"company": "Inventée SA"}], {}, 0.5, ["Société Générale Fictive"], 1, 2),
    (FACTS, [{"company": "Acme", "role": "Directrice"}], {}, 0.5, ["Société Générale Fictive"], 1, 2),
    (FACTS, [], {}, 0.0, ["Acme", "Société Générale Fictive"], 0, 1),
    (FACTS + [EMAIL_FACT], [{"company": "Acme"}], {"contact": {"email": "b@example.com"}, "skills": {}}, 0.5,
     ["Société Générale Fictive"], 1, 3),
])
def test_compute_metrics(facts, extracted, extra, recall, missed, invented, fields):
    result = {"headline": "x", "summary": "", "experiences": extracted, **extra}
    metrics = compute_metrics(facts, TRUTH, result)
    assert metrics["experience_recall"] == recall and metrics["missed_experiences"] == missed
    assert len(metrics["invented_facts"]) == invented and metrics["fields_extracted"] == fields


@pytest.mark.parametrize("case_id, factory, vlm, text, skipped, complete, invented", [
    ("lg_p04", None, [1, 2, 3], [4], [], True, False),
    ("sc_p04", None, [1, 2, 3], [], [4], False, False),
    ("oc_p01", inventing_oracle(INVENTED_EXPERIENCE), [1, 2], [], [], True, True),
    ("oc_p01", inventing_oracle(INVENTED_ROLE_EXPERIENCE, replace_role=True), [1, 2], [], [], True, True),
])
async def test_pipeline_coverage_and_invented_facts(run, case_id, factory, vlm, text, skipped, complete, invented):
    kwargs = {"oracle_factory": factory} if factory else {}
    r = by_id(await run([case_id], **kwargs))[case_id]
    assert (r["pages_by_method"]["vlm"], r["pages_by_method"]["text"], r["skipped_pages"]) == (vlm, text, skipped)
    assert (r["experience_recall"] == 1.0) == complete and bool(r["invented_facts"]) == invented
    assert r["all_pages_handled"] and r["cost_usd"] > 0
    assert r["pages_covered"] == 1 - len(skipped) / r["total_pages"]


@pytest.mark.parametrize("case_id", ["pr_p02", "un_corrupt", "em_blank"])
async def test_expected_rejections_are_evaluated_on_the_rejection(run, case_id):
    r = by_id(await run([case_id]))[case_id]
    assert r["expected_rejection"] and r["expectation_met"]
    assert r["experience_recall"] is None and r["missed_experiences"] == [] and r["n_company_facts"] == 0
    assert r["errors"] and all(isinstance(e, str) and e for e in r["errors"])
    if case_id == "pr_p02":
        assert "mot de passe" in r["rejected"] and r["n_calls"] == 0 and r["cost_usd"] == 0
    elif case_id == "un_corrupt":
        assert not r["completed"] and any("FileDataError" in e for e in r["errors"])
    else:
        assert r["completed"] and r["fields_extracted"] == 0


async def test_aggregates_by_category_exclude_rejections_from_recall(run):
    report = await run(["oc_p01", "oc_p02", "lg_p04", "pr_p02"])
    agg = report["aggregates"]
    assert agg["by_category"]["one_column"]["n_cases"] == 2 and agg["global"]["n_cases"] == 4
    assert agg["global"]["experience_recall"] == 1.0 and agg["global"]["missed_experiences"] == 0
    assert agg["by_category"]["protected"]["experience_recall"] is None
    assert "mode simulé" in report["summary"]


def test_price_table_knows_the_default_models():
    assert DEFAULT_VLM_MODEL in PRICES_USD_PER_M and DEFAULT_CV_PARSER_MODEL in PRICES_USD_PER_M


@pytest.mark.parametrize("mode, confirm", [("simulated", False), ("real", False)])
async def test_ledger_untouched_and_no_call_without_confirmation(run, mode, confirm):
    fake = refusing_acompletion()
    with patch("app.services.cv_parser.acompletion", fake):
        report = await run(["lg_p04", "oc_p01"], mode=mode, confirm=confirm) if mode == "real" else None
    if mode == "real":
        fake.assert_not_called()
        assert report["estimate_usd"] > 0 and report["results"] == []
    else:
        await run(["oc_p01", "lg_p04", "pr_p02"])
    assert not llm_budget.LEDGER_PATH.exists()


@pytest.mark.parametrize("mid_loop", [False, True])
async def test_exhausted_budget_makes_no_call_and_keeps_partial_results(run, generated, monkeypatch, mid_loop):
    monkeypatch.setenv("MISTRAL_API_KEY", "dummy")
    est = {e["case_id"]: estimate_case_usd(e, DEFAULT_VLM_MODEL, DEFAULT_CV_PARSER_MODEL) for e in generated["manifest"]}
    spent = 0.25 - est["oc_p02"] - est["lg_p04"] / 2 if mid_loop else 0.25
    llm_budget.record_call("parser", "preload", "m", spent, "estimated")
    fake = AsyncMock(return_value=llm_response({"headline": "Data", "experiences": [{"company": "X", "role": "Y"}]}, 10, 5))
    with patch("app.services.cv_parser.acompletion", fake):
        with pytest.raises(llm_budget.BudgetExceeded):
            await run(["oc_p02", "lg_p04"], mode="real", confirm=True)
    if not mid_loop:
        fake.assert_not_called()
        return
    saved = json.loads((generated["out_dir"] / "bench_results_real.json").read_text())
    assert saved["partial"] and [r["case_id"] for r in saved["results"]] == ["oc_p02"]


@pytest.mark.parametrize("content, recorded", [(None, True), ("pas du json", False)])
async def test_real_mode_records_completed_imports_only(run, monkeypatch, content, recorded):
    monkeypatch.setenv("MISTRAL_API_KEY", "dummy")
    response = llm_response({"headline": "Data", "experiences": [{"company": "X", "role": "Y"}]})
    if content:
        response.choices[0].message.content = content
    with patch("app.services.cv_parser.acompletion", AsyncMock(return_value=response)):
        report = await run(["oc_p02"], mode="real", confirm=True)
    r = by_id(report)["oc_p02"]
    assert r["cost_usd"] > 0 and r["cost_recorded"] == recorded
    if recorded:
        rows = [json.loads(line) for line in llm_budget.LEDGER_PATH.read_text().splitlines()]
        assert len(rows) == 1 and rows[0]["case_id"] == "oc_p02" and rows[0]["plan"] == "parser"
        assert rows[0]["cost_usd"] == pytest.approx(r["cost_usd"])
    else:
        assert not llm_budget.LEDGER_PATH.exists()
