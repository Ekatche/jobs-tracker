import itertools
from types import SimpleNamespace
from unittest.mock import AsyncMock

import scripts.backfill_company_attributes as backfill_module
from scripts.backfill_company_attributes import LLM_COST_PER_COMPANY_USD, backfill, estimate_backfill

SANOFI_PROFILE = {
    "company_name_normalized": "SANOFI",
    "sector": "healthcare_pharma",
    "sector_source": "llm_inferred",
    "company_size": "grand_groupe",
    "size_source": "api_entreprises",
}


def test_estimate_backfill_counts():
    offers = [
        {"entreprise": "Foncia", "raw_data": {"hellowork": {"company_industry": "Immobilier"}}},
        {"entreprise": "Foncia"},
        {"entreprise": "Sanofi"},
        {
            "entreprise": "Confidentiel",
            "raw_data": {"indeed": {"company_industry": "Insurance", "company_num_employees": "10,000+"}},
        },
    ]

    stats = estimate_backfill(offers, {"SANOFI": SANOFI_PROFILE})

    assert stats == {
        "offers": 4,
        "companies": 2,
        "resolved_natively": 1,
        "resolved_from_cache": 1,
        "max_llm_calls": 1,
        "estimated_cost_usd": LLM_COST_PER_COMPANY_USD,
    }
    assert LLM_COST_PER_COMPANY_USD == 0.0006


def test_estimate_backfill_profile_already_tried_by_llm():
    profile = {
        "company_name_normalized": "INCONNUE",
        "sector": None,
        "sector_source": "llm_inferred",
        "company_size": None,
        "size_source": "llm_inferred",
    }

    stats = estimate_backfill([{"entreprise": "Inconnue"}], {"INCONNUE": profile})

    assert stats["companies"] == 1
    assert stats["max_llm_calls"] == 0
    assert stats["estimated_cost_usd"] == 0


class _Cursor:
    def __init__(self, docs):
        self.docs = docs

    def limit(self, n):
        self.docs = self.docs[:n]
        return self

    async def to_list(self, _length):
        return list(self.docs)


async def test_backfill_apply_ignores_ingestion_time_budget(monkeypatch):
    # Horloge qui avance de 1 000 s à chaque lecture : toute échéance est dépassée dès le premier appel
    ticks = itertools.count(step=1000)
    monkeypatch.setattr("app.services.company_profiles.monotonic", lambda: next(ticks))
    lookup = AsyncMock(return_value=("pme", "123456789"))
    infer = AsyncMock(return_value={"sector": "tech_it", "company_size": None})
    monkeypatch.setattr("app.services.company_profiles.lookup_company_size", lookup)
    monkeypatch.setattr("app.services.company_profiles.infer_company_attributes", infer)
    offers = [{"_id": 1, "entreprise": "Alpha"}, {"_id": 2, "entreprise": "Gamma"}]
    job_offers = SimpleNamespace(find=lambda query, projection: _Cursor(offers), update_one=AsyncMock())
    profiles = SimpleNamespace(find_one=AsyncMock(return_value=None), update_one=AsyncMock())
    db = {"job_offers": job_offers, "company_profiles": profiles}
    monkeypatch.setattr(backfill_module, "get_database", AsyncMock(return_value=db))

    stats = await backfill(apply=True)

    assert lookup.await_count == infer.await_count == 2
    assert stats["updated"] == 2
    job_offers.update_one.assert_any_await({"_id": 2}, {"$set": {"company_size": "pme", "sector": "tech_it"}})
