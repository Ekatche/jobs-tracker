---
task: Fix portfolio experiences extraction truncation, headless WebGL crash and multi-role merging
status: completed
created: 2026-09-19
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Fix Portfolio Experiences Extraction Truncation, Headless WebGL Crash and Multi-Role Merging

## Context
- Existing code checked:
  - `backend/app/services/profile/collectors/website.py`:
    1. Headless Crawl4AI browser crashed on Three.js WebGL initialization (`THREE.WebGLRenderer: Error creating WebGL context`) inside headless container, triggering Next.js React Error Boundary (`<html id="__next_error__">` and `# This page couldn’t load`), causing zero experiences to be scraped.
    2. `_extract_with_llm` aggressively truncated markdown content per page to 6,000 characters (`markdown[:6000]`).
  - `backend/app/services/profile/periods.py`: `normalize_month` failed when start date omitted the year (e.g. `Mars` in `Mars — Sept. 2021` for bioMérieux).
  - `backend/app/services/profile/merge.py`: `_merge_experiences` grouped by `(company_slug, start_date)` but did not match close month variances in same year (e.g. `2022-09` vs `2022-10` for Nodya Group).
- Git status checked: Working tree contains current feature updates in progress, preserved.

## Simpler Alternative Considered
- Only disable WebGL: Chromium in headless container still trips Three.js `new WebGLRenderer()` exception. The HTTP SSR fallback using Next.js pre-rendered static HTML is 100% reliable, fast, and does not require JavaScript hydration.

## Surgical Scope
- **Files touched**:
  - `backend/app/services/profile/collectors/website.py`
  - `backend/app/services/profile/periods.py`
  - `backend/app/services/profile/merge.py`
  - `backend/tests/test_profile_collectors.py`
  - `backend/tests/test_profile_merge.py`
- **Files NOT touched**:
  - `backend/app/routers/cover_letters.py`
  - `backend/app/models.py`
  - all other files
- **Symbols replaced**: none
- **Symbols extended**:
  - `_html_to_markdown` & `collect_website` in `backend/app/services/profile/collectors/website.py`
  - `normalize_month` in `backend/app/services/profile/periods.py`
  - `_merge_experiences` in `backend/app/services/profile/merge.py`
  - Unit tests in `test_profile_collectors.py` and `test_profile_merge.py`

## Definition of Done
- [x] Tests pass: `docker compose exec backend pytest tests/test_profile_merge.py tests/test_profile_collectors.py` (55 passed in 0.09s)
- [x] Next.js WebGL error boundary crash handled with automatic HTTP SSR fallback
- [x] All 8 career experiences correctly extracted, merged, and displayed on candidate profile
- [x] Multi-experience merging preserves distinct roles at same company and merges minor cross-source month variations
- [x] No dead code introduced

## Steps
- [x] Step 1: In `backend/app/services/profile/collectors/website.py`, expand markdown limit to 30,000 chars, add `_html_to_markdown`, and implement HTTP SSR fallback when headless browser encounters WebGL or Next.js errors.
- [x] Step 2: In `backend/app/services/profile/periods.py`, add `fallback_year` support to `normalize_month` for dates omitting the year on the start month.
- [x] Step 3: In `backend/app/services/profile/merge.py`, refine `_merge_experiences` and `_merge_one_experience` to prevent same-source collapse and merge minor month variances across sources.
- [x] Step 4: Add unit tests in `backend/tests/test_profile_collectors.py` and `backend/tests/test_profile_merge.py`.
- [x] Step 5 (teardown): Run test suite via `docker compose exec backend pytest`, verify live extraction, and update database.

## Code Review
- Dead code removed: yes
- Build status: pass (55/55 profile tests and 95/95 overall suite passing)
- Type errors: none
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 12:21 - Plan created.
- 12:22 - Initial prompt & markdown length updates.
- 12:26 - Root-cause analysis of empty experiences: Three.js WebGL crash in headless Chromium caused Next.js to render `# This page couldn't load`.
- 12:28 - Implemented HTTP SSR fallback in `collect_website` using `_html_to_markdown`.
- 12:29 - Extended `normalize_month` with `fallback_year` and refined same-year merge in `_merge_experiences`.
- 12:30 - Live test confirmed 8/8 experiences extracted and synchronized in MongoDB.
