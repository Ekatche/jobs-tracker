---
task: Integrate global and generalist ATS into search and normalization pipeline
status: completed
created: 2026-09-15
---

# Integrate Global and Generalist ATS Platforms

## Context
- Existing code checked:
  - `backend/job_trackers/src/job_trackers/tools/custom_tool.py`: `french_job_boards` had basic ATS domains.
  - `backend/app/services/normalization.py`: `extract_company_from_url` lacked Ashby, BambooHR, SuccessFactors, Taleo, iCIMS, Personio path extraction.
  - `backend/tests/test_normalization.py`: Unit tests for URL company extraction.
- Fresh info looked up: URL patterns and schemas for Ashby, BambooHR, Workable, Personio, SAP SuccessFactors, Oracle Taleo, iCIMS.
- Git status checked: clean on target files.

## Simpler Alternative Considered
None — extending domain lists and regex extractors is the standard, minimal approach with zero breaking changes.

## Surgical Scope
- **Files touched**:
  - `backend/job_trackers/src/job_trackers/tools/custom_tool.py`
  - `backend/app/services/normalization.py`
  - `backend/tests/test_normalization.py`
- **Files NOT touched**: all other backend and airflow files.
- **Symbols replaced**: none.
- **Symbols extended**:
  - `french_job_boards` in `custom_tool.py`.
  - `extract_company_from_url` in `normalization.py`.
  - `test_extract_company_from_url` in `test_normalization.py`.

## Definition of Done
- [x] Build passes: `python3 -m py_compile backend/job_trackers/src/job_trackers/tools/custom_tool.py backend/app/services/normalization.py`
- [x] Tests pass: `.venv/bin/pytest tests/test_normalization.py -v` (7 passed in 2.13s)
- [x] No dead code: confirmed
- [x] Type check: clean syntax compilation
- [x] Manual check: Company extraction verified on test URLs for Ashby, BambooHR, Workable, Personio, SAP SuccessFactors, Taleo, iCIMS.

## Steps
- [x] Step 1: Extend domains in `backend/job_trackers/src/job_trackers/tools/custom_tool.py` with the complete set of ATS platforms (Ashby, BambooHR, Personio, Workable, SuccessFactors, Taleo, iCIMS).
- [x] Step 2: Implement URL regex matchers for Ashby, BambooHR, Workable, Personio, SAP SuccessFactors, Taleo, and iCIMS in `backend/app/services/normalization.py`.
- [x] Step 3: Add test assertions in `backend/tests/test_normalization.py` covering all new ATS URL formats.
- [x] Step 4: Run pytest and ensure 100% tests pass.
- [x] Step 5 (teardown): Verify no regression or orphans, update Execution Log and Daily Log.

## Code Review
- Dead code removed: yes
- Build status: pass (exit code 0)
- Type errors: none
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 2026-09-15 11:35: Plan initiated under micro-dev workflow.
- 2026-09-15 11:37: Syntax compilation passed.
- 2026-09-15 11:41: Pytest execution passed: 7 passed, 4 warnings in 2.13s.
- 2026-09-15 11:42: Task completed and verified.

## Notes
- All new ATS platform extractors backward-compatible with existing Workday, Greenhouse, Lever, and SmartRecruiters logic.
