---
task: Fix experience dates parsing, synthesize professional headline, preserve all project details, and align profile UI
status: completed
created: 2026-09-16
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Harmoniser le Profil Candidat : Dates d'expériences, Titre/Résumé, Projets scrapés & Alignement UI

## Context
- Existing code checked:
  - `backend/app/services/profile/merge.py`: Looked only for `"start"` and `"end"` keys. CV source stores `"start_date"` and `"end_date"`, resulting in `start: None` and `end: None` across experiences.
  - In `_merge_projects`, `repo`, `context`, and `highlights` were omitted when deduplicating across sources.
  - When `headline` is missing, it remained an empty string `""` displaying "Titre non renseigné".
  - `frontend/src/components/profile/CandidateProfileSection.tsx`: Rendered `{exp.start} — {exp.end || "Présent"}` which became ` — Présent` when start was null. Projects did not display stack badges, repo links or context. Sub-cards used outdated `bg-blue-night` styling.
  - `frontend/src/components/profile/CvDropzone.tsx`: Header styling and buttons differed in size and hierarchy from `CandidateProfileSection.tsx`.
- Fresh info looked up: None needed.
- Git status checked: Working branch `fix/profile-multi-sources`.

## Simpler Alternative Considered
None — request addresses exact bugs in data extraction, merging and presentation.

## Surgical Scope
- **Files touched**:
  - `backend/app/services/profile/merge.py`
  - `backend/tests/test_profile_merge.py`
  - `frontend/src/types/coverLetter.ts`
  - `frontend/src/components/profile/CandidateProfileSection.tsx`
  - `frontend/src/components/profile/CvDropzone.tsx`
- **Files NOT touched**:
  - All other files
- **Symbols replaced**: None
- **Symbols extended**:
  - `_merge_one_experience`, `_merge_experiences`, `_merge_projects`, `build_profile_from_sources` in `merge.py`
  - `formatPeriod`, project card rendering, headline display in `CandidateProfileSection.tsx`

## Definition of Done
- [x] Backend tests pass: `pytest tests/test_profile_merge.py tests/test_profile_periods.py -v` (65/65 passed)
- [x] Frontend type check passes: `npx tsc --noEmit` & `npm run build` (0 errors)
- [x] Profile re-merge executes: User candidate profile in MongoDB is re-merged with valid dates, headline and full project data
- [x] UI visual verification: Headers in `CvDropzone` and `CandidateProfileSection` are aligned, experience periods display formatted dates (e.g. `Août 2025 — 2026`, `Févr. 2023 — Juin 2024`), headline is populated and coherent, and projects show all details (links, github, stack, context).

## Steps
- [x] Step 1: Update `backend/app/services/profile/merge.py` to support `start_date`/`end_date` fallbacks, cross-source start resolution, full project attributes (`repo`, `context`, `highlights`), and automated coherent headline synthesis.
- [x] Step 2: Add unit tests in `backend/tests/test_profile_merge.py` verifying `start_date`/`end_date` normalization, project fields merging, and headline derivation. Run `pytest`.
- [x] Step 3: Run database migration/re-merge script on the active user profile in MongoDB to refresh stored document with correct dates, synthesized headline and merged projects.
- [x] Step 4: Refactor `frontend/src/components/profile/CandidateProfileSection.tsx` and `frontend/src/components/profile/CvDropzone.tsx` to align header layouts, format experience dates cleanly (e.g. `Août 2025 — Présent`), enrich project cards (stack tags, GitHub link, context badge), and modernize sub-cards.
- [x] Step 5 (teardown): Run type check (`tsc --noEmit`), test build, verify live rendering, and update daily log.

## Code Review
- Dead code removed: yes
- Build status: pass
- Type errors: none
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- Step 1: Updated `backend/app/services/profile/merge.py` with `_derive_headline`, `start_date`/`end_date` fallback in `_merge_one_experience`, cross-source grouping in `_merge_experiences`, and `highlights`/`context`/`repo` preservation in `_merge_projects`.
- Step 2: Added 4 test functions to `backend/tests/test_profile_merge.py`. Ran `docker exec jobtracker-backend pytest tests/test_profile_merge.py -v`. Evidence: 21 passed in 0.06s.
- Step 3: Executed candidate profile re-merge against MongoDB. Evidence: headline set to "Data Scientist & AI Engineer", all 4 experiences assigned normalized start/end dates (2025-08 -> 2026, 2023-02 -> 2024-06, etc.), projects retained stack and URLs.
- Step 4: Harmonized `CvDropzone.tsx` and `CandidateProfileSection.tsx` headers with uniform icon badge, typography, status badges, and action buttons. Implemented `formatPeriod` with French month abbreviations (e.g. 'Août 2025 — 2026'). Enriched project cards with context, stack, GitHub repo and external links.
- Step 5: Ran `npx tsc --noEmit` (exit code 0), `npm run build` (exit code 0), and verified backend candidate profile endpoints.

## Notes
- None. All requirements fulfilled cleanly.
