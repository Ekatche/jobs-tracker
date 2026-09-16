---
task: Multi-tenant user offer interactions isolation and filtering
status: done
created: 2026-09-16
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Multi-tenant user offer interactions isolation and filtering

## Context
- Existing code checked:
  - `backend/app/routers/job_offers.py`: global soft-delete modifies the shared `job_offers` document (`is_deleted=True`), impacting all users. `get_job_offers` does not receive `current_user` or provide personal interaction states (`saved`, `hidden`, `applied`).
  - `backend/app/auth.py`: only has mandatory `get_current_user` which raises 401 if token is absent, lacking an optional user dependency `get_current_user_optional`.
  - `backend/app/models.py`: lacks `UserOfferInteraction` schema and interaction fields on `JobOfferResponse`.
  - `frontend/src/lib/api.ts` and `frontend/src/app/offers/page.tsx`: UI calls `jobOffersApi.softDelete` which global-deletes offers; no per-user bookmark or hide functionality.
- Fresh info looked up: FastAPI optional OAuth2 dependency with `auto_error=False`.
- Git status checked: clean on `main` (only previous micro-dev uncommitted changes present).

## Simpler Alternative Considered
Store interaction lists directly inside `UserModel` (`saved_offers: List[str]`, `hidden_offers: List[str]`). Rejected because an unbounded array on user document grows indefinitely, cannot store interaction metadata (timestamp, notes), and prevents compound indexed joins and scaling. A dedicated `user_offer_interactions` collection with compound index `(user_id, offer_id)` is standard, scalable, and multi-tenant safe.

## Surgical Scope
- **Files touched**:
  - `backend/app/models.py`
  - `backend/app/auth.py`
  - `backend/app/routers/job_offers.py`
  - `backend/tests/test_user_offer_interactions.py`
  - `frontend/src/lib/api.ts`
  - `frontend/src/types/jobOffer.ts`
  - `frontend/src/app/offers/page.tsx`
- **Files NOT touched**:
  - All collectors, tasks, crawlers, and cover letter services.
- **Symbols replaced** (→ to delete before done):
  - In `frontend/src/app/offers/page.tsx`: replace `jobOffersApi.softDelete` in `handleDeleteOffer` with `jobOffersApi.setInteraction(offerId, "hidden")`.
- **Symbols extended** (→ keep):
  - `backend/app/models.py`: `JobOfferResponse` (add `user_interaction`), new `UserOfferInteractionRequest`, `UserOfferInteractionResponse`.
  - `backend/app/auth.py`: add `oauth2_scheme_optional` and `get_current_user_optional`.
  - `backend/app/routers/job_offers.py`: `get_job_offers`, `get_job_offers_count`, new endpoints `/{offer_id}/interaction` (GET, POST), `/my-interactions` (GET).

## Definition of Done
- [x] Build passes: `docker exec jobtracker-backend python -c "import main; print('MAIN OK')"`
- [x] Tests pass: `docker exec jobtracker-backend pytest tests/test_user_offer_interactions.py tests/test_ats_parsers.py tests/test_clean_and_verify_alignment.py` (50 passed in 0.24s)
- [x] No dead code: confirmed `softDelete` call replaced with `setInteraction(..., "hidden")` in `frontend/src/app/offers/page.tsx`.
- [x] Type check: `ruff check` passes (0 errors), `npm run lint` passes (exit 0).
- [x] Manual check: verify endpoints return per-user isolated interactions and filter hidden/saved/min_score offers.

## Steps
- [x] Step 1: Add `UserOfferInteractionRequest`, `UserOfferInteractionResponse` and extend `JobOfferResponse` with `user_interaction` in `backend/app/models.py`.
- [x] Step 2: Implement `get_current_user_optional` in `backend/app/auth.py` with `OAuth2PasswordBearer(..., auto_error=False)` to safely extract user without raising 401 when anonymous.
- [x] Step 3: Implement multi-tenant endpoints in `backend/app/routers/job_offers.py`: `POST /{offer_id}/interaction`, `GET /{offer_id}/interaction`, `GET /my-interactions`, and update `get_job_offers` + `get_job_offers_count` with `only_saved`, `include_hidden`, `min_score`, and per-user score & interaction population.
- [x] Step 4: Write unit tests in `backend/tests/test_user_offer_interactions.py` verifying isolation between users (user A hiding an offer does not hide it for user B or anonymous), bookmarking (`saved`), and clearing interaction (`none`).
- [x] Step 5: Update frontend `frontend/src/lib/api.ts` (API methods & `JobOfferFilter`), `frontend/src/types/jobOffer.ts`, and wire bookmark toggle + candidate-safe hide in `frontend/src/app/offers/page.tsx`.
- [x] Step 6 (teardown): Confirm replaced symbols removed, verify 0 dead code, run test suite and linters.

## Code Review
- Dead code removed: yes (handleDeleteOffer and softDelete removed from frontend/src/app/offers/page.tsx; unused imports removed)
- Build status: pass (main imports cleanly in Docker, Next.js lint passes)
- Type errors: none (ruff check clean, Next.js ESLint clean)
- Unintended side effects: none (anonymous users continue to see full public catalog without regression)
- Security surface touched: yes (auth helper and user interaction endpoints; verified tenant scoping: users can only view and mutate interactions keyed by current_user.id)
- Verdict: ✅ DONE

## Execution Log
- 23:26 Step 1: Added UserOfferInteractionRequest, UserOfferInteractionResponse, and user_interaction field on JobOfferResponse in backend/app/models.py. Verified import in Docker: exit 0 (OK).
- 23:27 Step 2: Added oauth2_scheme_optional (auto_error=False) and get_current_user_optional in backend/app/auth.py. Verified import in Docker: exit 0 (AUTH OK).
- 23:29 Step 3: Implemented apply_user_interaction_filters, user endpoints (POST/GET /{offer_id}/interaction, GET /user/interactions) and updated get_job_offers & count with multi-tenant filtering in backend/app/routers/job_offers.py. Ruff clean: exit 0.
- 23:30 Step 4: Wrote 9 unit tests in backend/tests/test_user_offer_interactions.py covering multi-tenant isolation, anonymous access, saved/hidden/score filters, and upsert/delete of user interactions. 9/9 passed in 0.10s, ruff check clean.
- 23:32 Step 5: Updated frontend types in frontend/src/types/jobOffer.ts and frontend/src/lib/api.ts. Replaced handleDeleteOffer with handleHideOffer and handleToggleSaveOffer with bookmark toggle and quick filter pills (Favoris uniquement, Score IA >= 4.0) in frontend/src/app/offers/page.tsx.
- 23:33 Step 6: Ran teardown and full test suites. 50/50 tests passed in Docker, ruff check clean on all files, next lint clean.

## Notes
(deviations from plan, errors hit, corrections made)
- UserModel required hashed_password in pytest fixtures; updated test fixtures accordingly.
- Aggregate mock in multi-tenant isolation test mutated dict in place; replaced with side_effect returning fresh dictionary copies.
