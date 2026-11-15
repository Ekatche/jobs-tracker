---
task: Fix CI flake8 F811 failures on pytest tests and prevent false company history warnings on draft or current applications
description: Fix flake8 F811 per-file-ignores in .flake8 for backend tests and fix compute_company_history_note in bloc_h.py and block_builder.py to exclude draft "En étude" status and current offer_id while parsing ISO application dates
status: done
created: 2026-11-15
---

# Fix Flake8 F811 in Tests & Company History False Positive (`bloc_h.py`)

## Context
- Existing code checked:
  - `.flake8` (`L6-8`): ignores `F401,E302,E303,E306,W391,F841` on `tests/*` and `backend/tests/*`, missing `F811`. CI run `43719259571` (`format-lint.yml`) failed solely at `flake8 backend/` due to `F811` redefinition warnings on pytest fixture imports in `backend/tests/cv_reference/test_bench.py`, `backend/tests/cv_reference/test_generator.py`, `backend/tests/job_offers_relevance/test_offers_list_filters.py`, and `backend/tests/job_offers_relevance/test_relevance_list_and_sort.py` (where `black` wraps long lines and breaks inline `# noqa: F811`).
  - `backend/app/services/evaluation/bloc_h.py` (`L32-117`): `_SILENT_APP_STATUSES` includes `"en étude"` (the default initial Kanban draft status before an application is sent), and `compute_company_history_note` / `_fetch_company_applications` does not exclude `current_offer_id`. `_count_application_outcomes` also ignores ISO-string dates (`isinstance(app_dt, datetime)`).
  - `backend/app/services/evaluation/block_builder.py` (`L145`): calls `compute_company_history_note(db, user_str_id, offer_company)` without passing `offer_doc.get("_id")`.
  - `backend/tests/evaluation/test_evaluation_service.py` (`L273-307`): existing test coverage for `company_history_note`.
- Fresh info looked up: n/a — standard Flake8 config and pure Python/MongoDB evaluation logic.
- Git status checked: pre-existing uncommitted files outside this plan's Surgical Scope exist (`backend/app/llm/utils.py`, `backend/job_crawler/crawler1.py`, `backend/tests/test_summarize_offer_cookie_guard.py`, `docs/micro/INDEX.md`); Surgical Scope files are clean.

## Simpler Alternative Considered
Adding inline `# noqa: F811` in every test file — rejected because `.github/workflows/format-lint.yml` runs `black backend/` right before `flake8 backend/`, which wraps long `def test_...` signatures and invalidates line-level `# noqa: F811`. Ignoring `F811` in `.flake8` `per-file-ignores` for `tests/*` and `backend/tests/*` is durable and standard for pytest fixture imports.

## Surgical Scope
- **Files touched**:
  - `.flake8` (add `F811` to `per-file-ignores` for `tests/*` and `backend/tests/*`)
  - `backend/app/services/evaluation/bloc_h.py` (remove `"en étude"` from `_SILENT_APP_STATUSES`, add optional `current_offer_id` exclusion, parse ISO string dates in `_count_application_outcomes`)
  - `backend/app/services/evaluation/block_builder.py` (pass `current_offer_id=offer_doc.get("_id")` to `compute_company_history_note`)
  - `backend/tests/evaluation/test_evaluation_service.py` (add unit tests covering `"En étude"` exclusion, `current_offer_id` exclusion, and ISO date parsing)
- **Files NOT touched**: all others (including `backend/app/llm/utils.py`, `backend/job_crawler/crawler1.py`, `.github/workflows/format-lint.yml`, and test files under `backend/tests/cv_reference/` and `backend/tests/job_offers_relevance/`)
- **Symbols replaced** (→ to delete before done): none
- **Symbols extended** (→ keep):
  - `compute_company_history_note` in `backend/app/services/evaluation/bloc_h.py`
  - `_count_application_outcomes` in `backend/app/services/evaluation/bloc_h.py`
  - `_build_bloc_g` in `backend/app/services/evaluation/block_builder.py`

## Definition of Done
- [x] Lint passes (exact CI flake8 check from repo root): `backend/.venv/bin/flake8 backend/`
- [x] Ruff check passes on modified files: `cd backend && uv run ruff check app/services/evaluation tests/evaluation/test_evaluation_service.py`
- [x] Tests pass: `cd backend && uv run python -m pytest tests/evaluation/ -q`
- [x] No dead code: n/a — no symbols replaced
- [x] Type check: `cd backend && uv run python -c "from app.services.evaluation.evaluator import evaluate_offer_two_pass; from app.services.evaluation.bloc_h import compute_company_history_note"`
- [x] Requirement check (`"en étude"` absent from `_SILENT_APP_STATUSES`): `cd backend && uv run python -c 'from app.services.evaluation.bloc_h import _SILENT_APP_STATUSES; assert "en étude" not in _SILENT_APP_STATUSES'`

## Steps
- [x] Step 1: Update `.flake8` `per-file-ignores` to include `F811` for `tests/*` and `backend/tests/*`. Verify with `backend/.venv/bin/flake8 backend/`.
- [x] Step 2: Update `backend/app/services/evaluation/bloc_h.py` to remove `"en étude"` from `_SILENT_APP_STATUSES`, add `current_offer_id: Optional[Any] = None` filtering in `compute_company_history_note`, and support ISO-formatted date strings in `_count_application_outcomes`. Verify import check passes.
- [x] Step 3: Update `backend/app/services/evaluation/block_builder.py` to pass `current_offer_id=offer_doc.get("_id")` into `compute_company_history_note`. Verify `ruff check` and `pytest tests/evaluation/ -q`.
- [x] Step 4: Add parametrized/focused tests in `backend/tests/evaluation/test_evaluation_service.py` covering draft `"En étude"` exclusion, current `offer_id` exclusion, and ISO date recency formatting. Verify `pytest tests/evaluation/ -q`.
- [x] Step 5 (teardown): Confirm 0 dead code / unused imports, run `git diff` review, and re-run all Definition of Done commands (`flake8 backend/`, `ruff check`, `pytest tests/evaluation/ -q`, `"en étude"` assertion).

## Code Review
- Dead code removed: yes — removed pre-existing unused `import json` in `backend/tests/evaluation/test_evaluation_service.py`; no symbols replaced
- Build status: pass (`flake8 backend/` exit 0, `ruff check` All checks passed!, Python imports clean)
- Type errors: none (added optional `current_offer_id: Optional[Any] = None` and typed `_parse_app_datetime`)
- Unintended side effects: none — backward-compatible optional parameter `current_offer_id=None`, `"en étude"` excluded as draft-only status, test suite `53 passed`
- Security surface touched: no (lint config, deterministic company history string builder, unit tests)
- Verdict: ✅ DONE

## Execution Log
- 2026-11-15T13:58Z | antigravity | step 1 | started
- 2026-11-15T13:59Z | antigravity | step 1 | done | `backend/.venv/bin/flake8 backend/` exit 0 (0 errors)
- 2026-11-15T13:59Z | antigravity | step 2 | started
- 2026-11-15T14:00Z | antigravity | step 2 | done | import check + `_SILENT_APP_STATUSES` assertion exit 0
- 2026-11-15T14:00Z | antigravity | step 3 | started
- 2026-11-15T14:00Z | antigravity | step 3 | done | `ruff check` clean, `pytest tests/evaluation/ -q` 50 passed
- 2026-11-15T14:00Z | antigravity | step 4 | started
- 2026-11-15T14:00Z | antigravity | step 4 | done | `pytest tests/evaluation/ -q` 53 passed, `ruff check` All checks passed!
- 2026-11-15T14:00Z | antigravity | step 5 | done | `git diff` reviewed; all DoD commands passed (`flake8` 0 errors, `ruff` clean, `53 passed`)
- 2026-11-15T14:01Z | antigravity | plan | done | all 6 DoD items pass

## Notes
- Convention files read in Phase 3: `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` (identical rules: test files ≤ 300-400 lines, `@pytest.mark.parametrize`, offline/deterministic unit tests).
- Preflight baseline (`2026-11-15T13:58Z`): `flake8 backend/` exit 1 (13x F811 in `test_bench.py`/`test_generator.py`); `ruff check app/services/evaluation tests/evaluation/test_evaluation_service.py` exit 1 (pre-existing unused `import json` in `test_evaluation_service.py:3`); `pytest tests/evaluation/ -q` exit 0 (`50 passed`); import check exit 0; `"en étude"` check expected to fail before Step 2 (`python3` replaced with `uv run python` in DoD).
