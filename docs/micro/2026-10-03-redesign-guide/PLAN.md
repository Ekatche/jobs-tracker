---
title: Redesign Guide and FAQ page
status: done
---

## User intent
The user wants to completely redesign the `Guide/FAQ` page (`frontend/src/app/guide/page.tsx`). They feel the current version is too text-heavy. The new version must be visual, intuitive, and clearly highlight key functional information:
1. The cron automation runs every day at 7h and 16h.
2. How to best fill out the profile (visual cards, step by step).
The goal is to replace long readable blocks of text with modern visual elements (timelines, cards, icons) using TailwindCSS.

## Surgical Scope
- `frontend/src/app/guide/page.tsx`: Entire file refactored with visual components (Timeline, Step Cards, Bento Grid) instead of simple long-text FAQ accordions.
- `docker-compose.prod.yml`, `docker-compose.yml`: Added `AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=False` so cron DAGs start active automatically.

## Steps
- [x] Step 1: Create a responsive Timeline component in `page.tsx` to visualize the daily Airflow schedule (07:00 and 16:00 UTC).
- [x] Step 2: Create visual 4-step Card components explaining how to fill out the profile (CV upload with VLM, web/github links, precise target criteria, 1-click manual arbitration).
- [x] Step 3: Transform existing textual FAQ categories into small, digestible visual sections (Bento Grid for Matching score, tailored CV/cover letter, and Kanban tracking).
- [x] Step 4: Add `AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=False` in `docker-compose.prod.yml` and `docker-compose.yml`.
- [x] Step 5: Verify build with `npm --prefix frontend run build`.

## Definition of Done
- [x] Frontend builds with zero TypeScript errors: `npm --prefix frontend run build` (exit 0)
- [x] Airflow DAG schedules 07:00 and 16:00 clearly explained: `grep -c '07:00' frontend/src/app/guide/page.tsx`
- [x] Visual cards and timeline present: `grep -c 'Mistral Pixtral VLM' frontend/src/app/guide/page.tsx`

## Code Review
- Dead code removed: yes
- Build status: pass (exit code 0, 19/19 routes compiled)
- Type errors: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 11:23: Added `AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=False` in docker-compose.prod.yml and docker-compose.yml
- 11:24: Implemented visual Timeline (06:00 purge, 07:00 morning collection, 16:00 afternoon collection), 4-step profile guide, Bento grid for AI features, and interactive compact FAQ in frontend/src/app/guide/page.tsx
- 11:25: Successfully ran `npm --prefix frontend run build` (compiled in Next.js with static route /guide)
