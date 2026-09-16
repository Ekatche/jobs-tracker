---
task: Implement candidate targeting preferences and overhaul profile page layout
status: completed
created: 2026-09-15
---

# Profile Targeting Preferences and Layout Overhaul

## Context
- Existing code checked:
  - `backend/app/models.py`: `CandidateProfile` has experiences, projects, education, certifications, skills, sources, but had no active job search targeting preferences.
  - `backend/app/routers/cover_letters.py`: routes `/profile/candidate` (GET, PUT) and sources endpoints.
  - `frontend/src/app/profile/page.tsx`: monolithic single-column page mixing account settings and candidate profile.
  - `frontend/src/components/profile/CandidateProfileSection.tsx`: profile section with text-based skills and sources import.
- Fresh info looked up: None required (internal FastAPI and React / Tailwind stack).
- Git status checked: clean on target files.

## Simpler Alternative Considered
None — creating a dedicated preferences model and section is required to feed job matching and Airflow demand-driven scraping as per Phase 1 of `CAREER_OPS_INTEGRATION_PLAN.md`.

## Surgical Scope
- **Files touched**:
  - `backend/app/models.py`
  - `backend/app/services/profile/merge.py`
  - `backend/tests/test_candidate_preferences.py`
  - `frontend/src/types/coverLetter.ts`
  - `frontend/src/components/profile/TargetingPreferencesSection.tsx`
- **Files NOT touched**: all other backend and frontend files.
- **Symbols replaced**: none.
- **Symbols extended**:
  - `CandidatePreferences` in `models.py` (added `seniority_levels: List[str]` with bi-directional backward compatibility).
  - TypeScript types in `types/coverLetter.ts` (added `seniority_levels?: string[]`).
  - `TargetingPreferencesSection.tsx` (toggle chips multi-selection for seniority levels with reset).

## Definition of Done
- [x] Build passes: `python3 -m py_compile backend/app/models.py backend/app/routers/cover_letters.py backend/app/services/profile/merge.py`
- [x] Tests pass: `backend/.venv/bin/pytest tests/test_candidate_preferences.py -v` (6 passed)
- [x] No dead code: confirmed
- [x] Type check: `npx tsc --noEmit` clean without errors
- [x] Manual check: Multi-selection chips for seniority levels save and persist in MongoDB.

## Steps
- [x] Step 1: Define `RemotePolicy` and `CandidatePreferences` models in `backend/app/models.py`, attach to `CandidateProfile`.
- [x] Step 2: Add `PUT /profile/candidate/preferences` and update profile update logic in `backend/app/routers/cover_letters.py`, update `merge.py`.
- [x] Step 3: Create unit tests in `backend/tests/test_candidate_preferences.py` and verify with pytest.
- [x] Step 4: Add TypeScript interfaces in `frontend/src/types/coverLetter.ts` and API method in `frontend/src/lib/api.ts`.
- [x] Step 5: Implement `frontend/src/components/profile/TargetingPreferencesSection.tsx` with role tags, location tags, remote badges, salary inputs, contract checkboxes, and exclusion tags.
- [x] Step 6: Refactor `frontend/src/app/profile/page.tsx` to use a 3-tab layout (Targeting & Preferences, Profile & Experiences, Account & Security).
- [x] Step 7 (teardown): Run backend tests and frontend TypeScript compiler, update Execution Log and Daily Log.
- [x] Step 8: Add `seniority_levels: List[str]` to `CandidatePreferences` in `models.py` and `types/coverLetter.ts` with bi-directional validator.
- [x] Step 9: Replace single select with multi-selection toggle chips in `TargetingPreferencesSection.tsx`.
- [x] Step 10: Update unit tests in `test_candidate_preferences.py`, run pytest, recompile frontend Docker image.

## Code Review
- Dead code removed: yes
- Build status: pass (exit code 0 on both python and tsc)
- Type errors: none
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 2026-09-15 19:27: Plan created under micro-dev workflow.
- 2026-09-15 19:31: Backend models & routes updated.
- 2026-09-15 19:36: Pytest passed for CandidatePreferences (4 passed).
- 2026-09-15 19:42: Frontend components & tabs layout implemented.
- 2026-09-15 20:00: TypeScript compilation passed (`npx tsc --noEmit`).
- 2026-09-15 20:01: Backend test suite re-verified (11/11 passed).
- 2026-09-16 09:35: Step 8 completed: Added `seniority_levels: List[str]` with bi-directional validator in `CandidatePreferences` (`models.py`) and updated `coverLetter.ts`.
- 2026-09-16 09:36: Step 9 completed: Replaced single select with multi-selection cards grid in `TargetingPreferencesSection.tsx`. `npx tsc --noEmit` passed.
- 2026-09-16 09:37: Step 10 completed: Added multi-seniority unit tests (6/6 passed in `test_candidate_preferences.py`), rebuilt and restarted frontend container.

## Notes
- Backward compatibility: `seniority_levels` and `seniority_level` synchronize automatically via `@model_validator(mode="after")`. Older records with single `seniority_level` are transparently loaded as a single-element list, and legacy readers continue to receive `seniority_level`.

