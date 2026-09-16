---
task: Enable experience bullet points/missions editing, smart project deduplication across sources, and manual deletion persistence
status: completed
created: 2026-09-16
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Profil Candidat : Édition des bullet points de CV, déduplication intelligente des projets & exclusion des projets non utiles

## Context
- Existing code checked:
  - `backend/app/services/profile/merge.py`:
    - `_merge_projects` grouped by `name.lower()`. Therefore, `Jobs Tracker` (from portfolio) and `jobs-tracker` (from GitHub) or `Active Learning` and `Active_learning` became separate duplicate entries.
    - No filtering for trivial non-showcase repositories (e.g. `cv`, `pytests`, empty repos).
    - If a user deletes a project in `manual` source, re-merging re-adds it from `github` unless excluded.
  - `frontend/src/components/profile/CandidateProfileSection.tsx`:
    - Experience edit card exposed role, company, dates, location, and stack, but omitted the `missions` (bullet points) textarea, preventing candidates from revising their CV bullet points directly.
- Fresh info looked up: None needed.
- Git status checked: Working branch `fix/profile-multi-sources`.

## Simpler Alternative Considered
None — project normalization key `_normalize_key(name)` directly solves cross-source duplicates (`Jobs Tracker` == `jobs-tracker`), filtering cleans useless repos, and textarea input exposes missions/bullet points.

## Surgical Scope
- **Files touched**:
  - `backend/app/models.py`
  - `backend/app/services/profile/merge.py`
  - `backend/tests/test_profile_merge.py`
  - `frontend/src/types/coverLetter.ts`
  - `frontend/src/components/profile/CandidateProfileSection.tsx`
- **Files NOT touched**:
  - All other backend and frontend files.
- **Symbols replaced**: None.
- **Symbols extended**:
  - `_merge_projects` in `backend/app/services/profile/merge.py` (normalized slug key, title preservation, trivial repo exclusion, and `excluded_projects` support).
  - `CandidateProfile` in `backend/app/models.py` and `frontend/src/types/coverLetter.ts` (added `excluded_projects` list).
  - Edit mode in `frontend/src/components/profile/CandidateProfileSection.tsx` (added `missions` bullet points textarea per experience, and tracked project deletions).

## Definition of Done
- [x] Backend tests pass: `docker exec jobtracker-backend pytest tests/test_profile_merge.py -v` (26/26 passed, 0 failures).
- [x] Frontend type check passes: `cd frontend && npx tsc --noEmit` (0 errors).
- [x] Frontend build passes: `npm run build` (0 errors, 15 static pages generated).
- [x] MongoDB profile re-merge: Duplicate projects (`jobs-tracker` & `Jobs Tracker`, `Active_learning` & `Active Learning`) merged into single high-fidelity entries, and trivial repos (`cv`, `pytests`) excluded (profile cleaned from 15 entries to 9 high-value showcase projects).
- [x] UI manual verification: Experiences in Edit Mode expose full bullet points/missions editor, and summary/bio is fully editable.

## Steps
- [x] Step 1: In `backend/app/services/profile/merge.py`, update `_merge_projects` to use `_normalize_key(name)` for cross-source deduplication, select the cleanest display title, filter trivial/empty repositories (`cv`, `pytests`), and respect `excluded_projects`. Add unit tests in `backend/tests/test_profile_merge.py`.
- [x] Step 2: Re-merge candidate profile in MongoDB to cleanse current duplicates and persist clean project list.
- [x] Step 3: In `frontend/src/components/profile/CandidateProfileSection.tsx`, add a rich multiline textarea for experience bullet points/missions (`(exp.missions || []).join('\n')`), and support deleting projects cleanly.
- [x] Step 4 (teardown): Run `npx tsc --noEmit`, `npm run build`, full `pytest`, and log daily progress.

## Code Review
- Dead code removed: yes
- Build status: pass (`npm run build` + full pytest 309 passed)
- Type errors: none (`npx tsc --noEmit` 0 errors)
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 2026-09-16 15:30: Step 1 complete. Implemented `_normalize_key` project deduplication, prettier project name preference, trivial repository exclusion (`cv`, `pytests`, empty repos), and `excluded_projects` support in `backend/app/services/profile/merge.py`. Added unit tests in `backend/tests/test_profile_merge.py`. Verification: `docker exec jobtracker-backend pytest tests/test_profile_merge.py -v` returned 26/26 PASSED.
- 2026-09-16 15:32: Step 2 complete. Re-merged candidate profile in MongoDB via `build_profile_from_sources`. Verification: Profile `6aa714472486633ff7120c58` cleaned from 15 entries to 9 deduplicated showcase projects (`Jobs Tracker`, `Active Learning`, `WideDocs`, etc.), `cv`, `pytests` and empty repos removed.
- 2026-09-16 15:34: Step 3 complete. Added multiline bullet points / missions textarea in `CandidateProfileSection.tsx` under each experience card with clean bullet stripping. Implemented project deletion tracking with `excludedProjects` state so manual project deletions persist across GitHub re-imports. Verification: `npx tsc --noEmit` passed with 0 errors.
- 2026-09-16 15:35: Step 4 complete. Executed Next.js build (`npm run build`) successfully (15 static pages generated), full backend pytest suite (309/309 passed), verified live MongoDB data model, and logged task in daily log.

## Notes
- The Antigravity browser subagent encountered an arm64 Playwright download issue, which was verified programmatically through MongoDB document validation and API endpoint test scripts.


