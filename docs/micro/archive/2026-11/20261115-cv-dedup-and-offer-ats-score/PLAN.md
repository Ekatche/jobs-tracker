---
task: Fix duplicate CV experiences across renamed company variants and compute 60/40 offer-aligned ATS score
description: Deduplicate same-stint CV experiences in merge_experiences.py, cv_templates.py, and cv_tailor.py (Nile by Digitalisim / Agence Nile), and implement offer keyword extraction (ats_keywords.py) with 60/40 offer-aligned scoring in ats_score.py, resumes.py, and ResumeAtsTab.tsx
status: done
created: 2026-11-15
---

# Fix Duplicate CV Experiences & Compute Offer-Aligned ATS Score

## Context
- Existing code checked:
  - `backend/app/services/profile/merge_experiences.py` (`_merge_experiences`): `_keys_loosely_match` fails on renamed company variants like `"nile by digitalisim"` vs `"agence nile"`, creating duplicate concurrent `08/2026 -> Présent` entries across sources and within `manual`.
  - `backend/app/services/cv_templates.py` & `cv_tailor.py`: render and tailor stored profile/CV experiences without same-stint deduplication.
  - `backend/app/services/ats_score.py` & `backend/app/routers/resumes.py` (`get_resume_ats_score`): all 100 ATS score points come from 6 formatting checks; `target_keywords` only reads `offer_doc.get("competences_cles")` which is `None` or `[]` on production offers (`Diagnoly`, `Heva`, `ADENES`, `GE Vernova`), ignoring `offer_evaluations.bloc_b` and offer description/title.
  - `frontend/src/types/resume.ts` & `frontend/src/components/resumes/ResumeAtsTab.tsx`: breakdown displays only the 6 formatting axes (`max: 15/20`).
- Fresh info looked up: n/a — pure Python profile/ATS scoring logic, FastAPI endpoint, and Next.js TypeScript UI.
- Git status checked: existing uncommitted changes from `20261115-skip-prefilter-manual-eval` (now archived); `docs/adrs/` does not exist.

## Simpler Alternative Considered
Running a one-off database migration to delete duplicate `Agence Nile` rows without fixing `merge_experiences.py`, `cv_templates.py`, and `cv_tailor.py` — rejected because any subsequent `website` source merge or CV rendering of existing documents would reproduce the duplicate. Likewise, keeping `keyword_coverage` purely informational — rejected because the user needs `/100` ATS score to actually measure offer alignment.

## Surgical Scope
- **Files touched**:
  - `backend/app/services/profile/merge_experiences.py`
  - `backend/app/services/cv_templates.py`
  - `backend/app/services/cv_tailor.py`
  - `backend/app/services/ats_keywords.py` (new, <= 180 lines)
  - `backend/app/services/ats_score.py`
  - `backend/app/routers/resumes.py`
  - `frontend/src/types/resume.ts`
  - `frontend/src/components/resumes/ResumeAtsTab.tsx`
  - `backend/tests/profile_merge/test_experiences.py`
  - `backend/tests/cv_tailor/test_page_budget.py`
  - `backend/tests/cv_guards/test_career_ops_guards.py`
- **Files NOT touched**: all others (including `backend/tests/test_cv_templates.py`)
- **Symbols replaced** (→ to delete before done): none
- **Symbols extended** (→ keep):
  - `_merge_experiences` (`merge_experiences.py`)
  - `render_cv_html` (`cv_templates.py`)
  - `load_tailor_prompt`, `enforce_page_budget` (`cv_tailor.py`)
  - `score_cv_ats_friendliness` (`ats_score.py`)
  - `get_resume_ats_score` (`resumes.py`)
  - `AtsScoreBreakdown` (`resume.ts`) and `AXES` (`ResumeAtsTab.tsx`)

## Definition of Done
- [x] Lint passes: `cd backend && uv run flake8 --config ../.flake8 .`
- [x] Backend tests pass: `cd backend && uv run python -m pytest tests/profile_merge/test_experiences.py tests/cv_tailor/ tests/test_cv_templates.py tests/cv_guards/test_career_ops_guards.py -q`
- [x] Frontend build passes: `cd frontend && npm run build`
- [x] No dead code: n/a — no symbols replaced
- [x] File sizes respected: all touched Python source files `< 450` lines and touched test files `< 400` lines

## Steps
- [x] Step 1: Fix experience deduplication in `merge_experiences.py` (`companies_refer_to_same_entity` + intra-source exact stint dedup), `cv_templates.py` (`_deduplicate_experiences` in `render_cv_html`), and `cv_tailor.py` (dedup in `load_tailor_prompt` and `enforce_page_budget`). Verify with `cd backend && uv run python -m pytest tests/profile_merge/test_experiences.py tests/cv_tailor/ tests/test_cv_templates.py -q`.
- [x] Step 2: Create `backend/app/services/ats_keywords.py` (`extract_offer_keywords` + `keyword_matches_cv`), update `backend/app/services/ats_score.py` to weight 60 pts parseability (10 pts x 6 axes) + 40 pts `offer_alignment`, and update `backend/app/routers/resumes.py` (`get_resume_ats_score`) to resolve offer/application + evaluation `bloc_b` and call `extract_offer_keywords`. Verify with `cd backend && uv run python -m pytest tests/cv_guards/test_career_ops_guards.py -q`.
- [x] Step 3: Update `frontend/src/types/resume.ts` and `frontend/src/components/resumes/ResumeAtsTab.tsx` for `offer_alignment` (`max: 40`) and the 6 technical axes (`max: 10`). Verify with `cd frontend && npm run build`.
- [x] Step 4: Add and update unit tests in `backend/tests/profile_merge/test_experiences.py`, `backend/tests/cv_tailor/test_page_budget.py`, and `backend/tests/cv_guards/test_career_ops_guards.py`. Verify with `cd backend && uv run python -m pytest tests/profile_merge/test_experiences.py tests/cv_tailor/ tests/test_cv_templates.py tests/cv_guards/test_career_ops_guards.py -q`.
- [x] Step 5 (teardown): Check `wc -l`, review `git diff`, and run all Definition of Done commands (`flake8`, `pytest`, `npm run build`).

## Code Review
- Dead code removed: none required; old inline keyword matching in `ats_score.py` cleanly replaced by `keyword_matches_cv`, and `sources` deduplicated in `_merge_one_experience`.
- Build status: `uv run flake8 --config ../.flake8 .` passed (0 errors); targeted pytest suite `148 passed` and extended regression suite `290 passed`; `cd frontend && npm run build` compiled and linted cleanly (20/20 routes).
- Type errors: none (`next build` typecheck clean).
- Unintended side effects: verified consecutive distinct stints at the same employer (`2025-08 -> 2026-08` vs `2026-08 -> Présent`, plus multi-role progression tests) remain separate; ATS scoring falls back proportionally (`tech_total * 40 / 60`) when no offer keywords exist.
- Security surface touched: `get_resume_ats_score` keeps strict `current_user.id` ownership scoping on `offer_evaluations` and `tailored_resumes`; no new external I/O or auth bypass.
- Verdict: ready to merge/commit after user confirmation.

## Execution Log
- 2026-11-15T14:41Z | antigravity | step 0 | done | archived `20261115-skip-prefilter-manual-eval` to `archive/2026-11/` and created plan
- 2026-11-15T14:41Z | antigravity | step 1 | started
- 2026-11-15T14:43Z | antigravity | step 1 | done | `pytest tests/profile_merge/ tests/cv_tailor/ tests/test_cv_templates.py -q` 174 passed
- 2026-11-15T14:43Z | antigravity | step 2 | started
- 2026-11-15T14:44Z | antigravity | step 3 | started
- 2026-11-15T14:46Z | antigravity | step 3 | done | `npm run build` exited 0
- 2026-11-15T14:46Z | antigravity | step 4 | started
- 2026-11-15T14:47Z | antigravity | step 2 | done | `pytest tests/cv_guards/test_career_ops_guards.py -q` passed inside 148-test suite
- 2026-11-15T14:47Z | antigravity | step 4 | done | `pytest tests/profile_merge/test_experiences.py tests/cv_tailor/ tests/test_cv_templates.py tests/cv_guards/test_career_ops_guards.py -q` 148 passed
- 2026-11-15T14:47Z | antigravity | step 5 | started
- 2026-11-15T14:48Z | antigravity | step 5 | done | `flake8` clean, extended `pytest` `290 passed`, `npm run build` clean, line limits respected
- 2026-11-15T14:48Z | antigravity | plan | done

## Notes
- Archive sweep (`2026-11-15`): moved `20261115-skip-prefilter-manual-eval` to `docs/micro/archive/2026-11/` and updated `docs/micro/INDEX.md`.
