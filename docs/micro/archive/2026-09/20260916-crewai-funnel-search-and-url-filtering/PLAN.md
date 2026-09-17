---
task: Implement CrewAI additive funnel search and direct ATS URL qualification
status: done
created: 2026-09-16
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Implement CrewAI additive funnel search and direct ATS URL qualification

## Context
- Existing code checked:
  - `backend/job_trackers/src/job_trackers/tools/custom_tool.py`: runs 2 passes in Tavily, bundling 20+ job boards and ATS into a single `include_domains` call of 15 results, leading to platform saturation (e.g., HelloWork/Indeed crowding out direct company ATS).
  - `backend/job_trackers/src/job_trackers/config/tasks.yaml`: `filter_urls_task` lacks explicit guidance on direct ATS URL structures (Greenhouse, Lever, Workable, Ashby, Teamtailor), leading to risk of rejecting legitimate direct company career postings.
  - Candidate preference search queries: broad and preference-aligned (`rôle`, `localisation`, `contrat`). Funnel must be strictly additive and never drop candidates' targeted locations or roles.
- Fresh info looked up: Tavily search parameters (`include_domains`, `max_results`).
- Git status checked: clean on `main` (only previous micro-dev uncommitted changes present).

## Simpler Alternative Considered
A single combined query with all domains in one Tavily call. Rejected because Tavily's ranker heavily favors high-traffic aggregators, starving direct company ATS pages. Separating into balanced additive passes (National Boards, Company ATS, LinkedIn) ensures diverse multi-source coverage without making the search query restrictive.

## Surgical Scope
- **Files touched**:
  - `backend/job_trackers/src/job_trackers/tools/custom_tool.py`
  - `backend/job_trackers/src/job_trackers/config/tasks.yaml`
  - `backend/tests/test_crew_models_and_tools.py`
- **Files NOT touched**:
  - All routers, models, MongoDB migrations, and frontend components.
- **Symbols replaced** (→ to delete before done): none
- **Symbols extended** (→ keep):
  - `TavilyJobBoardSearchTool._run` in `backend/job_trackers/src/job_trackers/tools/custom_tool.py`: partitioned additive passes.
  - `filter_urls_task` prompt in `backend/job_trackers/src/job_trackers/config/tasks.yaml`: enhanced ATS direct offer patterns.

## Definition of Done
- [x] Build passes: `docker exec jobtracker-backend python -c "from tools.custom_tool import TavilyJobBoardSearchTool; print('TOOL OK')"`
- [x] Tests pass: `docker exec jobtracker-backend pytest tests/test_crew_models_and_tools.py`
- [x] No dead code: verified unused domain lists or obsolete passes removed cleanly.
- [x] Type check: `ruff check backend/job_trackers/src/job_trackers/tools/custom_tool.py backend/tests/test_crew_models_and_tools.py`
- [x] Manual check: verify 3-pass additive search returns balanced results across Job Boards, ATS and LinkedIn.

## Steps
- [x] Step 1: Refactor `TavilyJobBoardSearchTool._run` in `backend/job_trackers/src/job_trackers/tools/custom_tool.py` into a 3-tier balanced funnel: (1) National Job Boards, (2) Direct Company ATS, (3) LinkedIn Jobs, with deduplication.
- [x] Step 2: Update `filter_urls_task` in `backend/job_trackers/src/job_trackers/config/tasks.yaml` with explicit direct ATS and Schema.org URL recognition patterns and relevance scoring rules.
- [x] Step 3: Add unit tests in `backend/tests/test_crew_models_and_tools.py` covering the 3-pass balanced funnel, deduplication, and spam domain stripping.
- [x] Step 4 (teardown): Confirm 0 dead code, run test suite and linters.

## Code Review
- Dead code removed: yes (removed monolithic domain bundle and unused imports)
- Build status: pass (exit 0 across 61 regression tests)
- Type errors: none (ruff check 100% clean)
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 23:41 Step 1: Refactored TavilyJobBoardSearchTool into 3 balanced additive passes (National Job Boards max 12, Company ATS max 10, LinkedIn Jobs max 8) with individual try/except protection and deduplication. Verified import in Docker: exit 0 (TOOL OK).
- 23:42 Step 2: Enriched filter_urls_task prompt in backend/job_trackers/src/job_trackers/config/tasks.yaml with direct ATS patterns (Greenhouse, Lever, Workable, Ashby, Teamtailor, Recruitee, Personio, Workday) and national job board direct offer patterns. Verified YAML in Docker: exit 0 (YAML OK).
- 23:43 Step 3: Added unit tests in backend/tests/test_crew_models_and_tools.py for the 3-pass funnel, balanced result sets, deduplication, and partial failure handling. 11/11 tests passed in 0.05s.
- 23:43 Step 4: Teardown complete. 61 tests passed across the full test suite in 0.25s. ruff clean. All criteria met.

## Notes
(deviations from plan, errors hit, corrections made)
