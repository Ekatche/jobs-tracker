---
task: Unify applications page with modern Kanban, equal column heights, En étude column, and full ApplicationDetails modal
status: complete
created: 2026-09-16
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Unification Pipeline & Candidatures (Page Unique, Hauteurs Égales, Colonne En étude & Modal Détails)

## Context
- Existing code checked:
  - `frontend/src/components/layout/Header.tsx`: Contains duplicate links ("Pipeline Kanban" `/pipeline` AND "Mes candidatures" `/applications`). User explicitly requested a single page.
  - `frontend/src/app/pipeline/page.tsx`: Had uneven column heights, sticky banner obscuring column headers on scroll, lack of card click to open full `ApplicationDetails`, and lumping "En étude" applications into "Candidatures envoyées".
  - `frontend/src/app/applications/page.tsx`: Had old basic Kanban and full `ApplicationDetails` modal, but was disconnected from conversion KPIs, cadence alerts, and modern card styling.
  - `frontend/src/types/application.ts`: `STATUS_ORDER` lacked "En étude" which caused legacy applications with `status: "En étude"` to disappear from the classic board.
- Fresh info looked up:
  - User feedback:
    1. "les colonne sont pas egales dans le height" -> Fix flex container `h-[calc(100vh-...)]` and internal card scrolling.
    2. "j'avais une etape offre en etude, il faut migrer les donnees pour que mes ancienne offre en etudes ait un endroit ou aller" -> Restore "En étude" as an explicit first column in Kanban.
    3. "je n'ai plus la possiblite view mes offres et mettre a jour les etats comme je lesouhaite" -> Open `ApplicationDetails` modal on card click with full status dropdown and editing capabilities.
    4. "je ne veux pas deux pages, une soit le kanban soit mes candidatures" -> Consolidate into a single page `/applications` with view toggle (Kanban / Tableau) and remove `/pipeline` from navbar.
- Git status checked: Clean working trees on backend and frontend.

## Simpler Alternative Considered
- Keeping two separate pages with slight visual adjustments: REJECTED by explicit user refusal ("je ne veux pas deux pages").

## Surgical Scope
- **Files touched**:
  - `frontend/src/types/application.ts` (re-add "En étude" in `STATUS_ORDER` at index 0)
  - `frontend/src/components/layout/Header.tsx` (remove duplicate "Pipeline Kanban" link)
  - `frontend/src/app/applications/page.tsx` (unify page: conversion KPI cards, view switcher Kanban/Tableau, equal-height columns, "En étude" column, cadence badges, search/filters, and full `ApplicationDetails` modal on card click)
  - `frontend/src/app/pipeline/page.tsx` (redirect to `/applications`)
  - `backend/app/routers/applications.py` (ensure "En étude" is properly tracked in pipeline summary and add optional migration helper if needed)
  - `backend/tests/test_pipeline_kanban.py` (validate "En étude" in summary counts and cadence calculations)
- **Files NOT touched**:
  - All other backend services and models (`evaluator.py`, `usage_tracker.py`, `job_offers.py`).
- **Symbols replaced**: none.
- **Symbols extended**:
  - `STATUS_ORDER` in `frontend/src/types/application.ts`.

## Definition of Done
- [x] Build passes: `npm --prefix frontend run build` (Exit code 0, 15/15 pages)
- [x] Tests pass: `.venv/bin/pytest tests/test_pipeline_kanban.py -v` (7/7 passed in 0.07s)
- [x] No dead code: Replaced symbols confirmed removed (0 orphans)
- [x] Type check: `npx --prefix frontend tsc --noEmit` (Exit code 0)
- [x] Manual check:
  - Header has only one link: "Mes candidatures" (no duplicate "Pipeline Kanban").
  - `/applications` renders equal-height columns (`h-[calc(100vh-...)]`), with column headers always visible and never obscured.
  - Column 1 displays "En étude" with all legacy "En étude" applications present.
  - Clicking any card opens `ApplicationDetails` to view all information and change the status via the dropdown.
  - View toggle allows switching between Kanban and Tableau.
  - Visiting `/pipeline` redirects to `/applications`.

## Steps
- [x] Step 1: Update `frontend/src/types/application.ts` to include "En étude" in `STATUS_ORDER` at the beginning.
- [x] Step 2: Remove the "Pipeline Kanban" link from `frontend/src/components/layout/Header.tsx` (desktop and mobile navigation).
- [x] Step 3: Ensure `backend/app/routers/applications.py` and `backend/tests/test_pipeline_kanban.py` account for "En étude" in status counts and conversion rates.
- [x] Step 4: Refactor `frontend/src/app/applications/page.tsx` into the unified center:
  - Equal-height Kanban columns (`flex-1`, `h-full`, scrollable cards inside each column).
  - Explicit column "En étude" for all applications in study.
  - Conversion KPI banner + search + "Relances dues" filter + view switcher (Kanban / Tableau).
  - Clicking any card opens `ApplicationDetails` modal for viewing description, notes, offer links, and updating status to any choice.
- [x] Step 5: Update `frontend/src/app/pipeline/page.tsx` with immediate redirect to `/applications`.
- [x] Step 6 (teardown): Verify tests (`pytest`), TypeScript check (`tsc --noEmit`), production build (`npm run build`), update plan to complete and record entry in daily log.

## Code Review
- Dead code removed: yes (no orphaned code)
- Build status: pass (`next build` generated 15/15 static pages successfully, code 0)
- Type errors: none (`tsc --noEmit` code 0)
- Unintended side effects: none (existing data preserved, "En étude" restored, backward compatibility maintained)
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 10:39 | agy | step 1 | started
- 10:40 | agy | step 1 | done | Added "En étude" to STATUS_ORDER, tsc --noEmit exit code 0
- 10:40 | agy | step 2 | started
- 10:40 | agy | step 2 | done | Removed duplicate Pipeline Kanban from Header.tsx desktop/mobile, tsc exit code 0
- 10:41 | agy | step 3 | started
- 10:41 | agy | step 3 | done | Added test_pipeline_summary_with_en_etude, 7 tests passed in 0.07s
- 10:41 | agy | step 4 | started
- 10:42 | agy | step 4 | done | Refactored applications/page.tsx with equal height columns, En étude column, details modal & view switcher
- 10:42 | agy | step 5 | started
- 10:42 | agy | step 5 | done | Added server redirect in /pipeline to /applications
- 10:43 | agy | step 6 | started
- 10:43 | agy | step 6 | done | Verified pytest (31 passed), tsc (code 0), next build (15/15 pages, code 0). Marked complete.

