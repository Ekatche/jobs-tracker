---
task: Fix CV tailor model deprecation, secure critic json output, and add searchable offer selector in CV generator
status: completed
created: 2026-09-19
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Fix CV Tailor Model Deprecation, Secure Critic JSON, and Add Searchable Offer Selector

## Context
- Existing code checked:
  - `backend/app/services/cv_tailor.py`: Uses deprecated `gemini/gemini-2.5-flash` as fallback, causing 404 VertexAIException.
  - `docker-compose.yml`: Missing `CV_TAILOR_MODEL` and `EVALUATION_MODEL` in backend environment section.
  - `backend/job_trackers/src/job_trackers/cover_letter_crew.py`: `_call_critic` lacks `response_format={"type": "json_object"}` and has tight token limit (400), causing JSON parsing error when critic preamble is returned.
  - `frontend/src/app/resumes/page.tsx`: Uses a static native `<select>` dropdown with no text search filter for target job offers.
- Fresh info looked up: Google VertexAI model availability (`gemini-3.8-flash`).
- Git status checked: Pre-existing uncommitted changes in `applications.py` noted and untouched.

## Simpler Alternative Considered
- Hardcode model in `cv_tailor.py`: Better to use environment fallback chain with modern default `gemini/gemini-3.8-flash`.

## Surgical Scope
- **Files touched**:
  - `backend/app/services/cv_tailor.py`
  - `backend/job_trackers/src/job_trackers/cover_letter_crew.py`
  - `docker-compose.yml`
  - `frontend/src/app/resumes/page.tsx`
  - `backend/tests/test_cv_tailor.py`
  - `backend/tests/test_cover_letter_crew.py`
- **Files NOT touched**:
  - `backend/app/routers/applications.py`
  - all other files
- **Symbols replaced**: none
- **Symbols extended**:
  - `generate_tailored_cv_content` in `backend/app/services/cv_tailor.py`
  - `_call_critic` in `backend/job_trackers/src/job_trackers/cover_letter_crew.py`
  - `ResumesContent` in `frontend/src/app/resumes/page.tsx`

## Definition of Done
- [x] Build passes: `npm run build` (Next.js 15.2.4 compiled successfully, 18/18 pages)
- [x] Tests pass: `./.venv/bin/pytest tests/test_cv_tailor.py tests/test_cover_letter_crew.py tests/test_letter_guards.py tests/test_cover_letter_prompts.py` (42 passed in 7.94s)
- [x] No dead code: `confirmed removed / no orphans`
- [x] Type check: `pass`
- [x] Manual check: `cv_tailor` defaults to `gemini/gemini-3.8-flash`, `_call_critic` uses `response_format={"type": "json_object"}` and 1000 tokens, and resume generator modal features interactive real-time text search.

## Steps
- [x] Step 1: Update `DEFAULT_CV_MODEL` in `backend/app/services/cv_tailor.py` to default to `gemini/gemini-3.8-flash`, add `response_format={"type": "json_object"}` to `acompletion`, update tests in `test_cv_tailor.py`, and pass `CV_TAILOR_MODEL` and `EVALUATION_MODEL` in `docker-compose.yml`.
- [x] Step 2: In `backend/job_trackers/src/job_trackers/cover_letter_crew.py`, add `response_format={"type": "json_object"}` and raise `max_completion_tokens=1000` on `_call_critic`, and update assertion in `test_cover_letter_crew.py`.
- [x] Step 3: In `frontend/src/app/resumes/page.tsx`, replace the native select in the generator modal with an interactive searchable combobox allowing instant filtering of offers by title, company, or location.
- [x] Step 4 (teardown): Run backend test suite (42 passed) and frontend build (0 errors).

## Code Review
- Dead code removed: yes
- Build status: pass
- Type errors: none
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 11:31 - Step 1: Changed `DEFAULT_CV_MODEL` in `cv_tailor.py` to `gemini/gemini-3.8-flash`, added `response_format` and `drop_params`. Added `CV_TAILOR_MODEL` and `EVALUATION_MODEL` to `docker-compose.yml`.
- 11:31 - Step 2: Updated `_call_critic` in `cover_letter_crew.py` with `response_format={"type": "json_object"}` and `max_completion_tokens=1000`. Updated assertion in `test_cover_letter_crew.py`.
- 11:32 - Step 3: Implemented `offerSearchQuery` and `filteredOffersForModal` in `frontend/src/app/resumes/page.tsx` with search input and interactive cards.
- 11:33 - Step 4: Full verification executed: `npm run build` passed cleanly; `pytest` (42/42 tests) passed in 7.94s.

## Notes
- `cv_tailor` now matches the pinned Gemini model versions across the project without risking 404 from Vertex/AI Studio deprecations.
