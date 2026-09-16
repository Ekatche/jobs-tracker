---
task: Modernize application details sidebar and enable in-kanban AI Two-Pass offer scoring
status: completed
created: 2026-09-16
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Modernize Application Details Sidebar and In-Kanban AI Scoring

## Context
- Existing code checked:
  - `frontend/src/components/applications/ApplicationDetails.tsx`: Visually dated narrow sidebar (`max-w-md`), plain unstyled inputs, lacks scoring trigger or score display.
  - `backend/app/routers/applications.py`: Handles application CRUD and pipeline summary, but has no direct evaluate endpoint for applications.
  - `backend/app/services/evaluation/evaluator.py`: `evaluate_offer_two_pass(offer_id, user_id, db)` evaluates job offers with Gemini 3.7 Flash and enforces quota limits.
  - `frontend/src/lib/api.ts`: Has `jobOffersApi.evaluate()` but no direct application evaluation method.
- Fresh info looked up:
  - User request:
    1. "ameliore la sidebar modernie la comme le reste stp" -> Full visual modernization with glassmorphism, company gradient avatar, meta pills, sticky footer, tabs/cards.
    2. "on ne peux pas lancer le scoring depuis la sidebar quand l'offre est ajoute dans le kanban" -> Add in-sidebar scoring trigger (`applicationApi.evaluate()`), live loading spinner, score badge (1.0-5.0), and link to full Two-Pass report.
- Git status checked: Clean working trees.

## Simpler Alternative Considered
- Only redirecting users to the `/offers` page to evaluate: REJECTED by user request — scoring must be launchable directly from the Kanban sidebar.

## Surgical Scope
- **Files touched**:
  - `backend/app/routers/applications.py` (endpoints `POST /applications/{id}/evaluate` and `GET /applications/{id}/evaluation`)
  - `backend/tests/test_pipeline_kanban.py` (test evaluation of applications with and without pre-existing offer_id)
  - `frontend/src/lib/api.ts` (methods `applicationApi.evaluate()` and `applicationApi.getEvaluation()`)
  - `frontend/src/components/applications/ApplicationDetails.tsx` (modern redesign, glassmorphism, AI scoring card, score gauge, notes cards, and sticky footer)
  - `frontend/src/components/applications/StatusSelect.tsx` (modern select styling)
- **Files NOT touched**:
  - `backend/app/services/evaluation/evaluator.py`
  - `frontend/src/app/applications/page.tsx`
- **Symbols replaced**: none
- **Symbols extended**: `applicationApi` in `frontend/src/lib/api.ts`, `job_router` in `backend/app/routers/applications.py`

## Definition of Done
- [x] Build passes: `npm --prefix frontend run build` (Exit code 0, 15/15 pages)
- [x] Tests pass: `.venv/bin/pytest tests/test_pipeline_kanban.py -v` (All 9 tests pass)
- [x] No dead code: 0 orphans
- [x] Type check: `npx --prefix frontend tsc --noEmit` (Exit code 0)
- [x] Manual check:
  - Opening the sidebar displays modern `max-w-xl` panel with company gradient avatar, clean typography, and meta pills.
  - If the application is unscored, a "✨ Lancer le scoring IA" button is present and triggers evaluation with a spinner.
  - If scored, the score gauge (1.0 - 5.0) and match qualification are displayed with link to view full report.

## Steps
- [x] Step 1: In `backend/app/routers/applications.py`, implement `POST /applications/{id}/evaluate` (evaluates linked offer or creates and evaluates a new offer from application fields) and `GET /applications/{id}/evaluation`.
- [x] Step 2: Write automated tests in `backend/tests/test_pipeline_kanban.py` for application evaluation endpoints.
- [x] Step 3: In `frontend/src/lib/api.ts`, add `evaluate` and `getEvaluation` to `applicationApi`.
- [x] Step 4: Redesign `frontend/src/components/applications/ApplicationDetails.tsx` with modern UI, AI scoring section, score gauge, notes cards, and sticky footer.
- [x] Step 5: Update `frontend/src/components/applications/StatusSelect.tsx` with modern styling.
- [x] Step 6 (teardown): Verify backend tests (`pytest`), TypeScript compilation (`tsc --noEmit`), Next.js build (`npm run build`), update plan to complete and record in `DAILY_LOG-2026-09-16.md`.

## Code Review
- Dead code removed: yes
- Build status: pass (Next.js 15.2.4, 15/15 routes)
- Type errors: none (tsc --noEmit clean)
- Unintended side effects: none
- Security surface touched: no
- Verdict: complete and verified

## Execution Log
- 10:56 | agy | step 1 | started
- 10:58 | agy | step 1 | completed - POST and GET endpoints implemented in applications router
- 10:59 | agy | step 2 | completed - pytest test_pipeline_kanban.py passed (9/9 passed)
- 11:00 | agy | step 3 | started
- 11:01 | agy | step 3 | completed - applicationApi.evaluate and applicationApi.getEvaluation added and type checked cleanly
- 11:01 | agy | step 4 | started
- 11:02 | agy | step 4 | completed - ApplicationDetails.tsx redesigned with glassmorphic layout, AI scoring card, and score gauge
- 11:02 | agy | step 5 | completed - StatusSelect.tsx styled with modern pill styling and chevron
- 11:03 | agy | step 6 | completed - All 9 backend tests pass, tsc clean, Next.js build 15/15 routes passed
