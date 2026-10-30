---
task: Tavily search reliability, Apec exclusion, zero-token WTTJ API and Cadremploi extractors
description: Make Tavily search reliable via deterministic Python call, exclude unsearchable apec.fr domain, and add zero-token extractors for Welcome to the Jungle API and Cadremploi curl_cffi in router.py
status: done
created: 2026-10-30
---

# Tavily search reliability, Apec exclusion, zero-token WTTJ API and Cadremploi extractors

## Context
- Existing code checked:
  - `backend/job_trackers/src/job_trackers/tools/custom_tool.py`: `preferred_job_boards` contains `apec.fr` which blocks datacenter IPs with HTTP 403 (DataDome), wasting Tavily credits and crawl slots.
  - `backend/job_trackers/src/job_trackers/crew.py` & `main.py`: `search_executor` LLM agent (`gpt-5-nano`) fails in CrewAI with `Action Input is not a valid key, value dictionary` when passing a list, leading to `Outil de recherche non appelé` failure (25% failure rate in production today).
  - `backend/app/services/ats/router.py`: WTTJ pages block headless Chromium with AWS WAF HTTP 202, but `https://api.welcometothejungle.com/api/v1/organizations/{org}/jobs/{slug}` returns full job JSON on HTTP 200 and HTTP 404 for expired jobs. `cadremploi.fr` returns 403 on plain httpx but succeeds with `curl_cffi` Chrome impersonation.
- Fresh info looked up:
  - WTTJ API structure confirmed live: `r.json()["job"]` fields `name`, `organization.name`, `office.city`, `contract_type`, `description`, `profile`. 404/410 indicates expired offer.
  - `curl_cffi` impersonation verified on Cadremploi for JSON-LD and expiration text detection.
- Git status checked: clean on tracked files; uncommitted changes in `geo.py`, `assess.py`, `role_gate.py` and `domain_relevance.py` from earlier geo/lexical matching tasks.

## Simpler Alternative Considered
- Keep `search_executor` LLM agent and prompt engineer its tool input: rejected because small models will still unpredictably format tool inputs, wasting LLM tokens when a Python call is 100% deterministic, faster, and free.

## Surgical Scope
- **Files touched**:
  - `backend/job_trackers/src/job_trackers/tools/custom_tool.py`
  - `backend/job_trackers/src/job_trackers/crew.py`
  - `backend/job_trackers/src/job_trackers/main.py`
  - `backend/job_trackers/src/job_trackers/config/agents.yaml`
  - `backend/job_trackers/src/job_trackers/config/tasks.yaml`
  - `backend/app/services/ats/router.py`
  - `backend/tests/test_crew_models_and_tools.py`
  - `backend/tests/test_ats_parsers.py`
- **Files NOT touched**:
  - All other backend, frontend, airflow files.
- **Symbols replaced** (→ to delete before done):
  - `search_executor` agent & task in `crew.py`, `agents.yaml`, `tasks.yaml`.
  - `get_search_executor_llm` in `crew.py`.
- **Symbols extended** (→ keep):
  - `TavilyJobBoardSearchTool` in `custom_tool.py`.
  - `extract_ats_or_jsonld_offer` in `router.py`.
  - `run_crew` in `main.py`.

## Definition of Done
- [x] Build passes: `docker exec -w /app jobtracker-backend python -c "import app.services.ats.router; import job_trackers.src.job_trackers.main; print('Build OK')"` -> Build OK
- [x] Tests pass: `docker exec -w /app -e PYTHONPATH=/app jobtracker-backend pytest tests/test_crew_models_and_tools.py tests/test_ats_parsers.py -v` -> 39 passed, 3 skipped in 0.57s
- [x] No dead code: `search_executor` and `get_search_executor_llm` confirmed removed (0 occurrences found by orphan scan).
- [x] Type check: `n/a`
- [x] Manual check: live WTTJ API test returns title, organization, city and contract; 404 triggers ExpiredOfferError; Apec excluded from Tavily queries.

## Steps
- [x] Step 1: Update `custom_tool.py` to remove `apec.fr` from `preferred_job_boards` and add `apec.fr`, `www.apec.fr` to `covered_elsewhere` / `excluded_domains`.
- [x] Step 2: Implement zero-token `extract_wttj_job` and wire into `extract_ats_or_jsonld_offer` in `backend/app/services/ats/router.py`.
- [x] Step 3: Implement Cadremploi / Cloudflare `curl_cffi` fallback in `backend/app/services/ats/router.py`.
- [x] Step 4: Refactor `JobTrackers` and `run_crew` to execute Tavily search deterministically in Python (`optimize_query` -> `tavily_search._run` -> `filter_urls`).
- [x] Step 5: Update tests in `test_crew_models_and_tools.py` and add WTTJ / Cadremploi tests in `test_ats_parsers.py`.
- [x] Step 6 (teardown): Remove dead code (`search_executor`, `get_search_executor_llm`, `execute_search_task`) and run orphan scan.
- [x] Step 7: Run full test suite and verify 0 regressions (187 passed, 3 skipped in 0.67s).

## Code Review
- Dead code removed: yes (search_executor, get_search_executor_llm, execute_search_task eliminated)
- Build status: pass
- Type errors: none
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- Step 1: `custom_tool.py` updated to exclude `apec.fr` from Tavily queries and include it in `covered_elsewhere` / `excluded_domains`.
- Step 2: `extract_wttj_job` implemented using WTTJ REST API `api.welcometothejungle.com/api/v1/organizations/{org}/jobs/{slug}`, with 404/410 mapped to `ExpiredOfferError`.
- Step 3: Added `_fetch_with_curl_cffi` fallback in `router.py` to handle Cloudflare-protected sites like Cadremploi and detect expired job pages.
- Step 4: Refactored `JobTrackers` into modular `query_crew` and `filter_crew`. In `main.py::run_crew`, search is executed directly in Python via `tavily_search._run`, eliminating the flaky `search_executor` LLM proxy.
- Step 5: Added comprehensive unit tests in `test_ats_parsers.py` (WTTJ success, WTTJ 404 expiration, Cadremploi expired, Cadremploi active JSON-LD) and `test_crew_models_and_tools.py` (deterministic execution, query fallback).
- Step 6: Verified orphan symbols scan across `backend/`. 0 references found.
- Step 7: Ran full suite of 187 tests covering scoring, assess, role gate, domain relevance, collectors, ats routers, and crew tools. All 187 tests passed.

## Notes
- Compatible with `python-jobspy 1.4.1` headers in `router.py::extract_indeed_job`.
