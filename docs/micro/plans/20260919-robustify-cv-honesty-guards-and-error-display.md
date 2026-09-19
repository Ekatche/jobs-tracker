---
task: Robustify CV honesty guardrails for full experience stack/missions and fix frontend error display
status: completed
created: 2026-09-19
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Robustify CV Honesty Guardrails and Error Display

## Context
- Existing code checked:
  - `backend/app/services/cv_guards.py`: `verify_cv_honesty` only extracted skills from `skills` and `exp.get("technologies")` (which was `None`), ignoring `exp["stack"]`, `exp["missions"]`, `proj["stack"]`, `proj["description"]`, action prefixes, and French/English technical synonyms.
  - `backend/tests/test_cv_guards.py`: Tested basic valid CV and invented company/skills detection.
  - `frontend/src/app/resumes/page.tsx`: Error handler looked for `err.response.data.detail`, but `fetchApi` in `frontend/src/lib/api.ts` throws standard `Error(message)`, which masked the actual 422 validation message.
- Git status checked: Prior uncommitted changes in `applications.py`, `cv_tailor.py`, etc. noted and preserved.

## Simpler Alternative Considered
- Completely disable honesty guard: Rejected because the guardrail protects against LLM hallucinations on enterprise credentials and invented technologies. Enriching the extraction and token/corpus matching is cleaner and safe.

## Surgical Scope
- **Files touched**:
  - `backend/app/services/cv_guards.py`
  - `backend/tests/test_cv_guards.py`
  - `frontend/src/app/resumes/page.tsx`
- **Files NOT touched**:
  - `backend/app/routers/applications.py`
  - all other files
- **Symbols replaced**: none
- **Symbols extended**:
  - `verify_cv_honesty` in `backend/app/services/cv_guards.py`
  - `handleGenerateSubmit` error catch in `frontend/src/app/resumes/page.tsx`

## Definition of Done
- [x] Tests pass: `pytest tests/test_cv_guards.py tests/test_cv_tailor.py tests/test_cover_letter_crew.py tests/test_letter_guards.py tests/test_cover_letter_prompts.py` (45 passed in 6.68s)
- [x] Real profile validation passes in live test without false-positive 422 violations
- [x] Hallucinated skills and companies still properly flagged
- [x] Build passes: `npm run build` in `frontend/` (18/18 routes compiled cleanly)
- [x] Frontend displays actual error messages if any generation error occurs

## Steps
- [x] Step 1: Extend `verify_cv_honesty` in `backend/app/services/cv_guards.py` to extract from all profile sections (`stack`, `missions`, `projects`, `summary`, `certifications`), support action verb stripping, significant token matching, and technical synonyms.
- [x] Step 2: Add comprehensive unit tests in `backend/tests/test_cv_guards.py` covering multi-field extraction, action verbs (`Conception d'APIs REST`), and English/French technical terms while maintaining anti-hallucination guarantees.
- [x] Step 3: Fix error unwrapping in `frontend/src/app/resumes/page.tsx` so `err instanceof Error ? err.message : ...` displays server validation details.
- [x] Step 4 (teardown): Run full backend test suite, test live generation via docker backend, run frontend build, and update daily log.

## Code Review
- Dead code removed: yes
- Build status: pass
- Type errors: none
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 11:45 - Step 1: Rewrote `cv_guards.py` with accent-insensitive normalization via `unicodedata`, action prefix stripping, full extraction of `stack`, `missions`, `projects`, and technical synonym resolution.
- 11:45 - Step 2: Added `test_verify_cv_honesty_with_missions_and_stack_extraction` in `test_cv_guards.py`. Full pytest suite (45/45 tests) passed in 6.68s.
- 11:45 - Live test: Ran end-to-end CV generation with Gemini in Docker container; generation succeeded with 0 violations.
- 11:46 - Step 3: Updated `frontend/src/app/resumes/page.tsx` error catch to inspect `err instanceof Error ? err.message : ...`.
- 11:46 - Step 4: Full Next.js production build (`npm run build`) succeeded across 18/18 routes.

## Notes
- Authenticated skills from missions and stacks are now seamlessly recognized without sacrificing protection against fabricated companies or frameworks.
