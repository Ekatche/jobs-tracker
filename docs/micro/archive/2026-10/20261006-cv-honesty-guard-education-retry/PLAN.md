---
task: Stop false-positive CV honesty rejections (education corpus, retry with feedback, readable 422)
description: cv_guards verify_cv_honesty ingest education degree/topics and certification topics; cv_tailor generate_tailored_cv_content retries once with violation feedback and raises CVHonestyError; resumes router returns French actionable 422 detail; pytest backend/tests
status: done
created: 2026-10-06
---

# CV honesty guard: education corpus, retry, readable error

## Context
- Existing code checked: cv_guards.verify_cv_honesty is lexical only; corpus ignores education (degree, topics) and certification topics. cv_tailor raises ValueError("CV honesty verification failed: ...") shown raw by routers/resumes.py (422).
- Fresh info looked up: n/a
- Git status checked: clean (only untracked docs/micro/DAILY_LOG)

## Simpler Alternative Considered
Only add skills to the profile manually: no code, but the guard keeps failing on any deducible skill. Rejected as sole fix.

## Surgical Scope
- **Files touched**: backend/app/services/cv_guards.py, backend/app/services/cv_tailor.py, backend/app/routers/resumes.py, backend/tests/test_cv_guards.py, backend/tests/test_cv_tailor.py
- **Files NOT touched**: all others (frontend, prompts, models)
- **Symbols replaced** (→ to delete before done): none
- **Symbols extended** (→ keep): verify_cv_honesty, generate_tailored_cv_content, generate route except-block

## Definition of Done
- [x] Build passes: `python -c "import app.services.cv_tailor, app.routers.resumes"` (from backend/)
- [x] Tests pass: `pytest backend/tests/test_cv_guards.py backend/tests/test_cv_tailor.py backend/tests/test_resumes_api.py backend/tests/test_provider_errors_api.py -v`
- [x] Skill derived from education topics is accepted: new test in test_cv_guards.py passes
- [x] Invented skill still rejected: existing test_verify_cv_honesty_flags_invented_company_and_skills passes
- [x] Retry: new test asserts acompletion called twice and 2nd prompt contains the rejected skill; success on 2nd attempt
- [x] Persistent violation still raises: test_generate_tailored_cv_content_flags_hallucinations passes
- [x] Readable 422: `grep -c "absents de ton profil" backend/app/routers/resumes.py` expected >= 1
- [x] No dead code: n/a — no symbols replaced
- [x] Type check: n/a — no type checker configured
- [x] Manual check: n/a — covered by tests

## Steps
- [x] Step 1: cv_guards.py — ingest education degree/topics and certification topics into corpus/known_skills; add test (topics → skill accepted).
- [x] Step 2: cv_tailor.py — add CVHonestyError(ValueError) with .violations; retry once appending a feedback block listing rejected skills; add tests.
- [x] Step 3: resumes.py — catch CVHonestyError, 422 with French message naming the offending items and advising to add them to the profile or retry.
- [x] Step 4 (teardown): run the DoD tests; confirm no orphans.

## Code Review
- Dead code removed: yes (none created)
- Build status: pass
- Type errors: none
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
(append-only, filled by executing-micro-plans)

## Notes
