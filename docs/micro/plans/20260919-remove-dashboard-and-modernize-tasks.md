---
task: Remove /dashboard page and modernize /tasks démarches with independent task management
status: completed
created: 2026-09-19
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Remove /dashboard and Modernize Démarches (/tasks)

## Context
- Existing code checked:
  - `frontend/src/app/dashboard/page.tsx`: Legacy duplicate of applications table and charts.
  - `frontend/src/components/layout/Header.tsx`: Links to `/dashboard` on desktop and mobile.
  - `frontend/src/app/onboarding/page.tsx`: Redirects to `/dashboard` on finish/skip.
  - `frontend/src/app/tasks/page.tsx`: Old basic 3-column Kanban with outdated styling and rigid tasks.
  - `backend/app/models.py`: `Task`, `TaskCreate`, `TaskUpdate` models.
- Fresh info looked up: n/a
- Git status checked: clean on task files.

## Simpler Alternative Considered
- Only redirect `/dashboard` without modernizing `/tasks`: rejected by user who explicitly requested both removing `/dashboard` and modernizing `/tasks` to be more useful, with the ability to add standalone tasks independent of applications/offers.

## Surgical Scope
- **Files touched**:
  - `frontend/src/app/dashboard/page.tsx` (replace with Next.js redirect to `/applications`)
  - `frontend/src/components/layout/Header.tsx` (remove `/dashboard` link, keep `/applications` as primary item, add `/tasks` to mobile)
  - `frontend/src/app/onboarding/page.tsx` (update redirect from `/dashboard` to `/applications`)
  - `backend/app/models.py` (add optional `priority`, `category`, `company` fields to `Task`, `TaskCreate`, `TaskUpdate`)
  - `frontend/src/types/tasks.ts` (update `Task` interface with optional `priority`, `category`, `company`)
  - `frontend/src/app/tasks/page.tsx` (modernize Démarches UI: standalone task creation, priority filters, timeline summary, dual Kanban/List view)
  - `frontend/src/components/tasks/NewTaskModal.tsx` & `frontend/src/components/tasks/EditTaskModal.tsx` (support standalone fields: title, category, priority, due_date, notes)
  - `frontend/src/components/tasks/TaskCard.tsx` & `KanbanColumn.tsx` & `KanbanBoard.tsx` (remove slice(0,5), add badges and status cycle)
  - `backend/tests/test_tasks.py` (added unit tests for standalone metadata)
- **Files NOT touched**:
  - All other application, offer, resume, and usage router/frontend files.
- **Symbols replaced**:
  - Legacy `DashboardPage` body in `frontend/src/app/dashboard/page.tsx` -> clean redirect component.
- **Symbols extended**:
  - `TaskCreate`, `TaskUpdate`, `Task` in `backend/app/models.py` (optional non-breaking attributes).

## Definition of Done
- [x] Build passes: `cd frontend && npm run build` (Exit code 0, 18/18 routes compiled)
- [x] Tests pass: `docker exec jobtracker-backend pytest tests/test_tasks.py -v` (5 passed in 2.85s)
- [x] No dead code: Replaced symbols confirmed removed.
- [x] Type check: TypeScript build passes without any errors.
- [x] Manual check:
  - Accessing `/dashboard` immediately redirects to `/applications`.
  - Header has no `/dashboard` link; `Mes candidatures` is the primary tab.
  - `/tasks` allows creating 100% standalone tasks without application requirements.
  - `/tasks` displays priority badges, deadline counters, and dual Kanban/List views.

## Steps
- [x] Step 1: Update backend models in `backend/app/models.py` to allow optional `priority: Optional[str] = "normale"`, `category: Optional[str] = "Général"`, and `company: Optional[str] = None` on `Task`, `TaskCreate`, `TaskUpdate`.
- [x] Step 2: Update frontend types in `frontend/src/types/tasks.ts` to reflect the updated `Task` model.
- [x] Step 3: Replace `frontend/src/app/dashboard/page.tsx` with an immediate redirect to `/applications`.
- [x] Step 4: Update `frontend/src/components/layout/Header.tsx` to remove the "Tableau de bord" navigation link and retain "Mes candidatures" as the first navigation item. Update `frontend/src/app/onboarding/page.tsx` redirects.
- [x] Step 5: Modernize `frontend/src/components/tasks/NewTaskModal.tsx` and `EditTaskModal.tsx` with clean inputs for standalone tasks (title, description, priority, category, due date).
- [x] Step 6: Revamp `frontend/src/app/tasks/page.tsx` with a modern dark theme cockpit: KPIs banner (À faire, En retard, Terminées), Quick Filters, Dual View (Kanban & List), and 1-click standalone task creation.
- [x] Step 7 (teardown): Verify build `cd frontend && npm run build` and ensure 0 dead code or broken imports.

## Code Review
- Dead code removed: yes
- Build status: pass (Next.js 15 build exit code 0)
- Type errors: none (0 errors)
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 00:47 — Step 1 completed: Added `priority`, `category`, and `company` fields to `Task`, `TaskCreate`, `TaskUpdate` in `backend/app/models.py`.
- 00:48 — Step 2 completed: Updated `frontend/src/types/tasks.ts`.
- 00:48 — Step 3 completed: Replaced `frontend/src/app/dashboard/page.tsx` with Next.js redirect to `/applications`.
- 00:48 — Step 4 completed: Removed `/dashboard` from `Header.tsx` desktop and mobile menus; added `/tasks` to mobile; updated `onboarding/page.tsx` redirect.
- 00:49 — Step 5 completed: Modernized `NewTaskModal.tsx`, `EditTaskModal.tsx`, `TaskCard.tsx`, `KanbanColumn.tsx` (removed 5-item cap), and `KanbanBoard.tsx`.
- 00:50 — Step 6 completed: Revamped `frontend/src/app/tasks/page.tsx` with 4 KPI cards, 1-click template suggestions, search & category/priority filters, and dual Kanban/List view.
- 00:52 — Step 7 completed: Fixed TypeScript typing (eliminated `any` casts), verified full Next.js 18-page production build (pass), and confirmed all 5 backend pytest tests in `tests/test_tasks.py` pass.

## Notes
- None. All requirements delivered cleanly.
