---
task: Implement API usage tracking models, quota service, and usage router
status: completed
created: 2026-09-15
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# API Usage Tracking and Quotas Backend Foundation

## Context
- Existing code checked:
  - `backend/app/models.py`: `UserModel` holds user credentials and profile link; needs `tier: UserTier = UserTier.FREE`.
  - `backend/main.py`: registers routers (`auth_router`, `user_router`, `job_router`, `task_router`, `job_offers_router`, `cover_letters_router`).
  - `backend/app/routers/__init__.py`: exports routers.
  - `backend/app/services/`: contains business logic services (`cv_parser.py`, `normalization.py`, `relevance.py`, `profile/`).
  - `docs/SYSTEM_ARCHITECTURE.md` Section 6 and `docs/CAREER_OPS_INTEGRATION_PLAN.md` Section 7: define the tracking schema (`ApiUsageRecord`), tier limits (Free, Advanced, Pro), actions, and endpoints.
- Fresh info looked up:
  - `litellm` in backend `.venv`: supports `litellm.completion_cost`, `litellm.success_callback`, and custom interception.
- Git status checked: clean on target backend files (`models.py`, `main.py`).

## Simpler Alternative Considered
None — tracking LLM consumption and enforcing quotas requires dedicated models (`ApiUsageRecord`), a tracking & quota service, and a router to inspect usage from the UI.

## Surgical Scope
- **Files touched**:
  - `backend/app/models.py`
  - `backend/app/services/usage_tracker.py` (new)
  - `backend/app/routers/usage.py` (new)
  - `backend/app/routers/__init__.py`
  - `backend/main.py`
  - `backend/tests/test_usage_tracker.py` (new)
- **Files NOT touched**:
  - All frontend files, database connectors, crawl/normalization pipelines, Docker config.
- **Symbols replaced**: none.
- **Symbols extended**:
  - `UserModel` in `backend/app/models.py` (added `tier` field defaulting to `UserTier.FREE`).
  - Routers export list in `backend/app/routers/__init__.py`.
  - App routing in `backend/main.py`.

## Definition of Done
- [x] Build passes: `python3 -m py_compile backend/app/models.py backend/app/services/usage_tracker.py backend/app/routers/usage.py backend/main.py`
- [x] Tests pass: `.venv/bin/pytest tests/test_usage_tracker.py -v` (0 failures)
- [x] No dead code: n/a — no symbols replaced
- [x] Type check: clean imports and strict type annotations
- [x] Manual check: `GET /usage/me/summary` returns tier, monthly consumption, and remaining allowances for each action

## Steps
- [x] Step 1: In `backend/app/models.py`, define `UserTier`, `ApiUsageAction`, `ApiUsageRecord`, `TierQuota`, and `UserQuotaSummary`. Add `tier: UserTier = UserTier.FREE` to `UserModel`.
- [x] Step 2: Implement `backend/app/services/usage_tracker.py` with:
  - `TIER_MONTHLY_LIMITS`: predefined quotas for Free, Advanced, and Pro.
  - `MODEL_COST_PER_1K_TOKENS`: pricing table fallback for estimated costs.
  - `estimate_llm_cost(model, input_tokens, output_tokens) -> float`.
  - `record_api_usage(...)`: async helper recording usage into `api_usage` collection.
  - `get_user_monthly_usage(db, user_id, year, month)`: calculates usage by action.
  - `check_user_quota(db, user_id, action) -> tuple[bool, int, int]`: validates if user can perform action.
- [x] Step 3: Implement `backend/app/routers/usage.py` with endpoints:
  - `GET /usage/me` (paginated list of user's usage records).
  - `GET /usage/me/summary` (current month usage, limits per tier, remaining actions).
  - `GET /usage/tiers` (public pricing & tier limits info).
- [x] Step 4: Register `usage_router` in `backend/app/routers/__init__.py` and `backend/main.py`.
- [x] Step 5: Write comprehensive tests in `backend/tests/test_usage_tracker.py` testing models, cost estimator, quota checking, and endpoints.
- [x] Step 6 (teardown): Run python compilation, execute pytest suite, verify zero regressions on existing profile & app tests, update Execution Log and Daily Log.

## Code Review
- Dead code removed: yes
- Build status: pass
- Type errors: none
- Unintended side effects: none
- Security surface touched: no (standard auth-protected endpoints, user_id isolation)
- Verdict: ✅ DONE

## Execution Log
- Step 1 completed: Defined `UserTier`, `ApiUsageAction`, `ApiUsageRecord`, `TierQuota`, `ActionQuotaUsage`, `UserQuotaSummary` in `backend/app/models.py`, updated `UserModel` and `UserResponse`. Verified with `python3 -m py_compile backend/app/models.py`.
- Step 2 completed: Implemented `backend/app/services/usage_tracker.py` (`TIER_MONTHLY_LIMITS`, `MODEL_COST_PER_1K_TOKENS`, `estimate_llm_cost`, `record_api_usage`, `get_user_monthly_usage`, `check_user_quota`, `require_user_quota`). Verified with `python3 -m py_compile backend/app/services/usage_tracker.py`.
- Step 3 completed: Implemented `backend/app/routers/usage.py` (`GET /usage/me`, `GET /usage/me/summary`, `GET /usage/tiers`). Verified with `python3 -m py_compile backend/app/routers/usage.py`.
- Step 4 completed: Registered `usage_router` in `backend/app/routers/__init__.py` and included in `backend/main.py`. Verified with `python3 -m py_compile`.
- Step 5 completed: Wrote comprehensive tests in `backend/tests/test_usage_tracker.py` (11 tests covering models, cost estimation, quota limits, 429 enforcement, and FastAPI endpoints). Verified with pytest (11 passed in 0.12s).
- Step 6 completed: Validated zero regressions across full test suite (63 passed in 0.31s). Updated Daily Log.

## Notes
- Free tier defaults: 5 letters, 20 evaluations, 2 CV tailoring, 2 CV parsing, 1 interview prep per month.
- Backward compatibility: existing users without `tier` attribute in MongoDB default to `UserTier.FREE`.
