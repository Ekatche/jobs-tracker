---
task: Sécurisation du backend, contrôle d'accès IDOR et code d'invitation à l'inscription
description: "Sécurisation du backend, contrôle d'accès IDOR et code d'invitation à l'inscription — models.py, routers/auth.py, routers/users.py, lib/api.ts, components/auth/RegistrationForm.tsx, docker-compose.yml +1"
status: done
created: 2026-10-02
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Sécurisation du backend, contrôle d'accès IDOR et code d'invitation à l'inscription

## Context
- Existing code checked:
  - `backend/app/routers/users.py` had no IDOR checks (in lines 106, 123, 153 `if str(current_user.id) != user_id: pass` allowed any user to read, edit, or delete any other user's account and data). `GET /users/` returned all users to any authenticated user.
  - `backend/app/routers/auth.py` and `backend/app/models.py` had an open registration endpoint `/auth/register` without any restriction or invitation mechanism.
  - `frontend/src/app/auth/register/page.tsx` had registration fields without an invitation code input.
  - `docker-compose.yml` exposed MongoDB (`27017`), Mongo-Express (`8081`), and Airflow (`8080`) to `0.0.0.0`, which poses a severe risk on a public VPS.
- Fresh info looked up: FastAPI `HTTPException`, Pydantic models.
- Git status checked: clean on tracked files except the previous landing page update.

## Simpler Alternative Considered
- Hardcoding a single static invitation code in Python: rejected; must be configurable via environment variable `INVITATION_CODE` (with fallback or optional when empty in dev mode).

## Surgical Scope
- **Files touched**:
  - `backend/app/models.py`
  - `backend/app/routers/auth.py`
  - `backend/app/routers/users.py`
  - `frontend/src/lib/api.ts`
  - `frontend/src/components/auth/RegistrationForm.tsx`
  - `docker-compose.yml`
  - `backend/tests/test_users.py`
- **Files NOT touched**: all others
- **Symbols replaced**: none
- **Symbols extended**:
  - `UserCreate` in `backend/app/models.py` (added `invitation_code: Optional[str] = None`)
  - `register_user` in `backend/app/routers/auth.py` (checks `INVITATION_CODE` from environment)
  - `get_user`, `update_user`, `delete_user`, `get_users` in `backend/app/routers/users.py` (enforces authorization checks, 403 on IDOR)
  - `RegistrationForm` in `frontend/src/components/auth/RegistrationForm.tsx` (added input field for code)
  - `authApi.register` in `frontend/src/lib/api.ts` (added `invitation_code` parameter)
  - `docker-compose.yml` (bound ports to `127.0.0.1`)

## Definition of Done
- [x] Backend tests pass: `docker exec jobtracker-backend pytest tests/test_users.py` (11 passed in 6.30s)
- [x] Frontend build passes: `npm --prefix frontend run build` (exit code 0)
- [x] IDOR blocked: accessing, editing, or deleting another user's profile raises 403 Forbidden.
- [x] Invitation code enforced: when `INVITATION_CODE` env var is set, `/auth/register` rejects invalid/missing codes with 403, and accepts valid code.
- [x] Port exposure secured: `docker-compose.yml` binds `27017`, `8081`, `8000`, `3875`, `27018`, and `8080` to `127.0.0.1` instead of `0.0.0.0`.

## Steps
- [x] Step 1: Write and validate micro plan.
- [x] Step 2: Update `backend/app/models.py` to add `invitation_code` to `UserCreate` model, and update `backend/app/routers/auth.py` to validate `INVITATION_CODE` from environment.
- [x] Step 3: Fix IDOR in `backend/app/routers/users.py` (`get_user`, `update_user`, `delete_user` reject mismatching `current_user.id` with 403; `get_users` restricted to current user).
- [x] Step 4: Add invitation code field to `frontend/src/lib/api.ts` and `frontend/src/components/auth/RegistrationForm.tsx`.
- [x] Step 5: Update `docker-compose.yml` to bind internal services (`mongodb`, `mongo-express`, `airflow`, `backend`, `frontend`, `mongo_test`) to `127.0.0.1`.
- [x] Step 6: Add test cases to `backend/tests/test_users.py` for IDOR denial, anti-enumeration, and invitation code validation, and verify with `pytest`.
- [x] Step 7: Run full build and test verification, update daily log, and complete plan.

## Code Review
- Dead code removed: yes
- Build status: pass (`npm --prefix frontend run build` exit code 0)
- Type errors: none
- Unintended side effects: none
- Security surface touched: yes (auth, registration restriction, IDOR authorization, Docker port binding)
- Verdict: ✅ DONE

## Execution Log
- 2026-10-02 10:53: Micro plan created and validated.
- 2026-10-02 10:54: Added `invitation_code` to `UserCreate` model (`backend/app/models.py`) and enforced `INVITATION_CODE` in `backend/app/routers/auth.py`.
- 2026-10-02 10:55: Fixed IDOR vulnerabilities and user enumeration in `backend/app/routers/users.py` (`get_users`, `get_user`, `update_user`, `delete_user` return 403 for unauthorized cross-user operations).
- 2026-10-02 10:56: Bound container ports to `127.0.0.1` in `docker-compose.yml`.
- 2026-10-02 10:56: Added invitation code field to frontend (`frontend/src/lib/api.ts` and `frontend/src/components/auth/RegistrationForm.tsx`).
- 2026-10-02 10:57: Added automated tests for IDOR and invitation validation in `backend/tests/test_users.py` (11 passed). Fixed JSX tag balance in RegistrationForm and verified `npm --prefix frontend run build` (exit 0).
- 2026-10-02 10:58: Full test suites verified cleanly. Plan completed.

## Notes
- `INVITATION_CODE` is checked only if configured and non-empty in environment, which allows local dev/CI environments without code configuration while strictly protecting production environments.
