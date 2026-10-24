---
task: Classer les offres du Kanban dans l'ordre chronologique d'envoi
description: sort job applications chronologically oldest-to-newest by application_date with created_at fallback across all Kanban columns in frontend/src/app/applications/page.tsx and frontend/src/types/application.ts Next.js React
status: done
created: 2026-10-23
---

# Classer les offres du Kanban dans l'ordre chronologique d'envoi

## Context
- Existing code checked: `frontend/src/app/applications/page.tsx` computes `columns` via `useMemo` from `filteredApplications`. Currently, cards inside each column preserve the raw order returned by the backend (`sort("application_date", pymongo.DESCENDING)`), which displays the newest applications first.
- Fresh info looked up: n/a
- Git status checked: clean (staged archive sweep for previous plan).

## Simpler Alternative Considered
- Inlining array `.sort()` directly inside `getAppsFor` in `frontend/src/app/applications/page.tsx`. However, placing `getApplicationTimestamp` and `sortApplicationsChronologically` in `frontend/src/types/application.ts` (alongside `formatDate`, `calculateDays`, `normalizeApiData`) ensures robust date parsing, proper fallback to `created_at`, deterministic tie-breaking, and testability.

## Surgical Scope
- **Files touched**:
  - `frontend/src/types/application.ts`
  - `frontend/src/app/applications/page.tsx`
- **Files NOT touched**:
  - `backend/*` (API sorting remains untouched for table/pagination compatibility)
  - `frontend/src/components/applications/*`
  - all others
- **Symbols replaced**: none
- **Symbols extended**:
  - `frontend/src/types/application.ts`: export `getApplicationTimestamp`, `sortApplicationsChronologically`
  - `frontend/src/app/applications/page.tsx`: import `sortApplicationsChronologically` and apply it to each Kanban column

## Definition of Done
- [x] Build passes: `npm --prefix frontend run build`
- [x] Type check passes: `./frontend/node_modules/.bin/tsc --project frontend/tsconfig.json --noEmit`
- [x] Lint passes: `npm --prefix frontend run lint`
- [x] Sorting verification script passes: `node test_sorting.mjs` verifying ascending date ordering (oldest first, e.g. Oct 1 before Oct 15) and fallback on `created_at`
- [x] No dead code: confirmed 0 orphans
- [x] Manual check: verify Kanban column cards are displayed chronologically from oldest sent to newest sent

## Steps
- [x] Step 1: Add and export `getApplicationTimestamp` and `sortApplicationsChronologically` in `frontend/src/types/application.ts`.
- [x] Step 2: Update `columns` `useMemo` in `frontend/src/app/applications/page.tsx` to sort cards with `sortApplicationsChronologically` (ascending: oldest first).
- [x] Step 3: Run unit verification script to confirm ascending ordering and `created_at` fallback logic.
- [x] Step 4: Run typecheck (`tsc --noEmit`), lint (`npm run lint`), and build (`npm run build`).
- [x] Step 5 (teardown): Delete temporary verification script and confirm no dead code.

## Code Review
- Dead code removed: yes
- Build status: pass (exit 0)
- Type errors: none (exit 0)
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 2026-10-23T18:13Z | antigravity | step 1 | started
- 2026-10-23T18:14Z | antigravity | step 1 | done | `./frontend/node_modules/.bin/tsc --project frontend/tsconfig.json --noEmit` exit 0
- 2026-10-23T18:14Z | antigravity | step 2 | started
- 2026-10-23T18:15Z | antigravity | step 2 | done | `./frontend/node_modules/.bin/tsc --project frontend/tsconfig.json --noEmit` exit 0
- 2026-10-23T18:15Z | antigravity | step 3 | started
- 2026-10-23T18:16Z | antigravity | step 3 | done | `node test_sorting.mjs` exit 0 (ALL_SORTING_TESTS_PASSED)
- 2026-10-23T18:16Z | antigravity | step 4 | started
- 2026-10-23T18:17Z | antigravity | step 4 | done | tsc, lint, build exit 0
- 2026-10-23T18:17Z | antigravity | step 5 | started
- 2026-10-23T18:18Z | antigravity | step 5 | done | `rm test_sorting.mjs` exit 0, 0 orphans
- 2026-10-23T18:19Z | antigravity | all | done | all DoD commands pass fresh



## Notes
- Preflight baseline (2026-10-23T18:13Z):
  - Convention files read: AGENTS.md, GEMINI.md
  - `./frontend/node_modules/.bin/tsc --project frontend/tsconfig.json --noEmit`: exit 0
  - `npm --prefix frontend run lint`: exit 0 (2 pre-existing warnings in CandidateProfileSection.tsx and ResumePreviewModal.tsx)

