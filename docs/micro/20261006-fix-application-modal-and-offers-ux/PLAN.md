---
task: Fix application modal spinner loop, offer seen scroll jump, applied filter and pagination return
description: Fix infinite isSubmitting spinner in NewApplicationModal, preserve scroll on toggle seen by un-nesting OfferCard, link applications to user_offer_interactions for applied filter, and preserve page query parameter on return from offer details
status: done
created: 2026-10-06
---

# Fix application modal spinner loop, offer seen scroll jump, applied filter and pagination return

## Context
- Existing code checked:
  - `frontend/src/components/dashboard/NewApplicationModal.tsx`: `isSubmitting` never reset to `false` on success or in `useEffect [isOpen]`.
  - `frontend/src/app/applications/page.tsx`: `onSuccess` missing `setIsNewAppModalOpen(false)`.
  - `frontend/src/app/offers/page.tsx`: `OfferCard` nested inside `OffersPageContent` unmounting/remounting on re-render + `unseenOnly` filter reflow; `handleApplyToOffer` missing `offer_id: offer.id`.
  - `frontend/src/app/offers/[id]/page.tsx`: "Retour aux offres" hardcoded to `/offers` ignoring `?page=`.
  - `backend/app/routers/applications.py`: `create_application` does not record `status: "applied"` in `user_offer_interactions`.
  - `backend/app/routers/job_offers.py`: `_get_multi_tenant_interaction_filter` only checks `user_offer_interactions`, missing applications from `applications` collection.
  - `backend/app/models.py`: `JobApplicationCreate` missing `notes: Optional[List[str]] = None`.
- Fresh info looked up: n/a
- Git status checked: clean (working tree clean, on branch main)

## Simpler Alternative Considered
- none — request is already the minimal change across the 4 reported issues.

## Surgical Scope
- **Files touched**:
  - `frontend/src/components/dashboard/NewApplicationModal.tsx`
  - `frontend/src/app/applications/page.tsx`
  - `frontend/src/app/offers/page.tsx`
  - `frontend/src/app/offers/[id]/page.tsx`
  - `backend/app/routers/applications.py`
  - `backend/app/routers/job_offers.py`
  - `backend/app/models.py`
  - `backend/scripts/sync_applied_interactions.py` (one-off sync script for VPS database)
- **Files NOT touched**: all others
- **Symbols replaced** (→ to delete before done): none
- **Symbols extended** (→ keep):
  - `JobApplicationCreate` in `backend/app/models.py` (add `notes`)
  - `create_application` in `backend/app/routers/applications.py` (upsert `user_offer_interactions` with `status: "applied"`, `seen: True`)
  - `_get_multi_tenant_interaction_filter` in `backend/app/routers/job_offers.py` (include `applications` collection in applied OIDs)
  - `onSubmit` and `useEffect [isOpen]` in `frontend/src/components/dashboard/NewApplicationModal.tsx` (reset `isSubmitting`)
  - `OfferCard` in `frontend/src/app/offers/page.tsx` (un-nested, standalone component with memoization)
  - "Retour aux offres" in `frontend/src/app/offers/[id]/page.tsx` (support `router.back()` and `?page=` preservation)

## Definition of Done
- [x] Build passes: `npm --prefix frontend run build` (exit 0)
- [x] Tests pass: `PYTHONPATH=. .venv/bin/pytest tests/test_user_offer_interactions.py -v` (19 passed exit 0)
- [x] Type check: `npm --prefix frontend run lint` (exit 0)
- [x] No dead code: confirmed 0 orphans
- [x] Manual check:
  - 1. Submitting application modal resets `isSubmitting` and closes cleanly; reopening modal starts with non-spinning button.
  - 2. Toggling "vue" on an offer card maintains scroll position without jumping to top.
  - 3. Filtering by "Postulées" returns offers where user applied (19 applications backfilled on VPS).
  - 4. Navigating from page 2 of offers to an offer detail and clicking "Retour aux offres" returns to page 2.

## Steps
- [x] Step 1: Fix `NewApplicationModal.tsx` (`finally { setIsSubmitting(false); }` and reset in `!isOpen`), `applications/page.tsx` (`onSuccess` modal close), and `models.py` (`notes` in `JobApplicationCreate`).
- [x] Step 2: Fix `offers/page.tsx` `handleApplyToOffer` to pass `offer_id: offer.id`, and un-nest `OfferCard` outside `OffersPageContent` with `type="button"` and `e.stopPropagation()` to eliminate scroll reset.
- [x] Step 3: Fix `offers/[id]/page.tsx` "Retour aux offres" to read `searchParams.get("page")` or `fromPage` and support `router.back()` with fallback to `/offers?page=X`.
- [x] Step 4: Fix backend `applications.py` and `job_offers.py` to ensure creating an application registers `status: "applied"` in `user_offer_interactions` and `_get_multi_tenant_interaction_filter` includes applied offers.
- [x] Step 5: Verify build & tests locally (`npm run build`, `npm run lint`, `pytest`).
- [x] Step 6: Deploy/sync to VPS and run sync script for existing applied offers.
- [x] Step 7 (teardown): Confirm 0 dead code or temporary artifacts left behind.

## Code Review
- Dead code removed: yes (0 orphans)
- Build status: pass (`npm run build` exit 0, Docker images build exit 0 on VPS)
- Type errors: none (`npm run lint` exit 0)
- Unintended side effects: none
- Security surface touched: no (standard CRUD & interaction status)
- Verdict: ✅ DONE

## Execution Log
- 2026-10-05T22:27Z | antigravity | step 1 | started
- 2026-10-05T22:29Z | antigravity | step 1 | done | `npm run lint` exit 0, `pytest test_user_offer_interactions.py` 18 passed exit 0
- 2026-10-05T22:29Z | antigravity | step 2 | started
- 2026-10-05T22:34Z | antigravity | step 2 | done | `npm run lint` exit 0
- 2026-10-05T22:35Z | antigravity | step 3 | started
- 2026-10-05T22:35Z | antigravity | step 3 | done | `npm run lint` exit 0
- 2026-10-05T22:36Z | antigravity | step 4 | started
- 2026-10-05T22:40Z | antigravity | step 4 | done | `pytest test_user_offer_interactions.py` 19 passed exit 0
- 2026-10-05T22:41Z | antigravity | step 5 | started
- 2026-10-05T22:42Z | antigravity | step 5 | done | `npm run build` exit 0, `npm run lint` exit 0, `pytest` 19 passed exit 0
- 2026-10-05T22:43Z | antigravity | step 6 | started
- 2026-10-05T22:45Z | antigravity | step 6 | done | VPS sync done, Docker images built, containers restarted, 19 candidatures backfilled
- 2026-10-05T22:46Z | antigravity | step 7 | done | teardown completed, PLAN.md status done

## Notes
- Baseline: frontend build passed, frontend lint passed, backend pytest test_user_offer_interactions.py (18 passed)
- Deployed on VPS: backend + frontend rebuilt and running; 19 applied offers synchronized in MongoDB
