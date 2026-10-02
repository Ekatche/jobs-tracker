---
task: Découplage des critères de recherche et toggle actif/en pause pour la veille Airflow
description: "Découplage des critères de recherche et toggle actif/en pause pour la veille Airflow — models.py, tasks/job_offers_collectors.py, types/coverLetter.ts, components/profile/TargetingPreferencesSection.tsx, tests/test_candidate_preferences.py, tests/test_job_offers_collectors_queries.py"
status: done
created: 2026-10-02
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Découplage des critères de recherche et toggle actif/en pause pour la veille Airflow

## Context
- Existing code checked:
  - `backend/app/models.py` defined `CandidatePreferences` without a `search_active` flag.
  - `backend/app/tasks/job_offers_collectors.py` line 696 queried all profiles unconditionally (`db["candidate_profile"].find({})`) for Airflow search queries.
  - `frontend/src/types/coverLetter.ts` defined `CandidatePreferences` without `search_active`.
  - `frontend/src/components/profile/TargetingPreferencesSection.tsx` had form fields for roles, locations, contracts, but no toggle switch to pause/activate automated search.
- Fresh info looked up: n/a
- Git status checked: clean on tracked files except uncommitted changes in previous completed tasks.

## Simpler Alternative Considered
- Hardcoding user IDs to exclude: rejected; each user in the personal circle must be able to toggle their search on/off directly from the UI.

## Surgical Scope
- **Files touched**:
  - `backend/app/models.py`
  - `backend/app/tasks/job_offers_collectors.py`
  - `frontend/src/types/coverLetter.ts`
  - `frontend/src/components/profile/TargetingPreferencesSection.tsx`
  - `backend/tests/test_candidate_preferences.py`
  - `backend/tests/test_job_offers_collectors_queries.py`
- **Files NOT touched**: all others
- **Symbols replaced**: none
- **Symbols extended**:
  - `CandidatePreferences` in `backend/app/models.py` (added `search_active: bool = True`)
  - `build_search_queries` in `backend/app/tasks/job_offers_collectors.py` (filtered by `search_active: True` / exists)
  - `CandidatePreferences` in `frontend/src/types/coverLetter.ts` (added `search_active?: boolean`)
  - `TargetingPreferencesSection` in `frontend/src/components/profile/TargetingPreferencesSection.tsx` (added toggle switch and state)

## Definition of Done
- [x] Backend tests pass: `docker exec jobtracker-backend pytest tests/test_job_offers_collectors_queries.py tests/test_candidate_preferences.py` (21 passed in 3.91s)
- [x] Frontend build passes: `npm --prefix frontend run build` (exit code 0)
- [x] Query builder ignores inactive search profiles: when `search_active == False`, profile is skipped in Airflow round-robin.
- [x] Toggle switch displayed in UI: Users can toggle search active/pause and save successfully.

## Steps
- [x] Step 1: Write and validate micro plan.
- [x] Step 2: Add `search_active: bool = True` to `CandidatePreferences` in `backend/app/models.py`.
- [x] Step 3: Update `build_search_queries` in `backend/app/tasks/job_offers_collectors.py` to filter by active search profiles.
- [x] Step 4: Update `frontend/src/types/coverLetter.ts` and `frontend/src/components/profile/TargetingPreferencesSection.tsx` to include the toggle switch banner.
- [x] Step 5: Add tests for `search_active` default and Airflow filtering in `backend/tests/test_candidate_preferences.py` and `backend/tests/test_job_offers_collectors_queries.py`.
- [x] Step 6: Verify backend tests and frontend build, append entry to `docs/micro/DAILY_LOG-2026-10-02.md`, and complete plan.

## Code Review
- Dead code removed: yes
- Build status: pass (`npm --prefix frontend run build` exit code 0)
- Type errors: none
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 2026-10-02 11:01: Micro plan created and validated.
- 2026-10-02 11:02: Added `search_active: bool = True` to `CandidatePreferences` in `backend/app/models.py`.
- 2026-10-02 11:02: Updated `build_search_queries` in `backend/app/tasks/job_offers_collectors.py` to skip inactive profiles in queries round-robin.
- 2026-10-02 11:02: Added `search_active` to TypeScript types and added interactive Toggle Switch banner to `TargetingPreferencesSection.tsx`.
- 2026-10-02 11:03: Added unit tests in `test_candidate_preferences.py` and `test_job_offers_collectors_queries.py`. Verified all 21 tests pass in 3.91s.
- 2026-10-02 11:03: Verified Next.js production build (`npm --prefix frontend run build` exited with code 0). Plan completed.

## Notes
- None.
