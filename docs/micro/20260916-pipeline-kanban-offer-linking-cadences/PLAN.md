---
task: Phase 4 of Career-Ops Plan - Kanban pipeline, offer linking (offer_id), and automated follow-up cadences
status: complete
created: 2026-09-16
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Phase 4 : Vue Pipeline, liaison des offres (offer_id) et cadences de relance automatisées

## Context
- Existing code checked:
  - `backend/app/models.py`: `JobApplication`, `JobApplicationCreate`, `JobApplicationResponse` lack `offer_id` and follow-up cadence calculation fields. `ApplicationStatus` has legacy `ETUDE`.
  - `backend/app/routers/applications.py`: Manages CRUD for applications without computing automated follow-up cadences (J+7 follow-up, J+1 interview thank you).
  - `frontend/src/types/application.ts`: `Application` interface missing `offer_id` and follow-up alert fields. `STATUS_ORDER` misses later negotiation/offer stages.
  - `frontend/src/components/dashboard/NewApplicationModal.tsx`: `PrefilledData` and form schema do not forward `offer_id`.
  - `frontend/src/app/offers/[id]/page.tsx`: "Postuler" modal opening does not forward `offer.id`.
  - `frontend/src/components/applications/ApplicationCard.tsx`: Renders days count but lacks visible follow-up alert badges.
- Fresh info looked up: Master plan `docs/CAREER_OPS_INTEGRATION_PLAN.md` Phase 4 ("Phase de Pilotage : Vue Pipeline & Suivi").
- Git status checked: Active branch `fix/profile-multi-sources`.

## Simpler Alternative Considered
- Only storing `offer_id` in database without frontend awareness or follow-up alerts: Rejected because users would not know when to follow up on applications and would lose trace of the bridge between scraped offers and applications.

## Surgical Scope
- **Files touched**:
  - `backend/app/models.py` (Add `offer_id`, `follow_up_alert`, `days_since_application`, update `ApplicationStatus`)
  - `backend/app/routers/applications.py` (Compute follow-up cadences, persist `offer_id`)
  - `backend/tests/test_applications.py` (Comprehensive unit tests for creation, offer linking, and cadence alerts)
  - `frontend/src/types/application.ts` (Add `offer_id`, `follow_up_alert`, `days_since_application`, update `STATUS_ORDER` and status styles)
  - `frontend/src/lib/api.ts` (Update `Application` interface with `offer_id`, `follow_up_alert`)
  - `frontend/src/components/dashboard/NewApplicationModal.tsx` (Add `offer_id` to schema and prefilled data)
  - `frontend/src/app/offers/[id]/page.tsx` (Pass `offer.id` in `handleOpenApplyModal`)
  - `frontend/src/components/applications/ApplicationCard.tsx` (Display alert badges for follow-up and interview thank-you)
  - `frontend/src/components/applications/ApplicationDetails.tsx` (Display banner linking back to the source offer)
- **Files NOT touched**:
  - All landing pages (`frontend/src/app/page.tsx`)
  - Other backend routers (`job_offers.py`, `cover_letters.py`, `usage.py`)
- **Symbols replaced** (→ to delete before done):
  - none
- **Symbols extended** (→ keep):
  - `JobApplication`, `JobApplicationCreate`, `JobApplicationResponse` in `backend/app/models.py`
  - `Application` in `frontend/src/types/application.ts` and `frontend/src/lib/api.ts`
  - `PrefilledData` in `frontend/src/components/dashboard/NewApplicationModal.tsx`

## Definition of Done
- [x] Build passes: `npm --prefix frontend run build` (Exit code 0, 14/14 static pages generated)
- [x] Tests pass: `pytest backend/tests/test_applications.py` (2 passed in 0.66s)
- [x] No dead code: Replaced symbols confirmed removed
- [x] Type check: `npx --prefix frontend tsc --noEmit` (Exit code 0)
- [x] Manual check: Applying to an offer links the application with `offer_id`, and Kanban displays follow-up badges (`Relance due` at J+7, `Remerciement` at J+1)

## Steps
- [x] Step 1: Extend backend models in `backend/app/models.py` with `offer_id: Optional[str] = None`, `follow_up_alert: Optional[str] = None`, `days_since_application: Optional[int] = None`, and update `ApplicationStatus` enum.
- [x] Step 2: Update `backend/app/routers/applications.py` to persist `offer_id` and compute `follow_up_alert` dynamically (`relance_due` for `APPLIED` with >= 7 days, `remerciement_due` for `INTERVIEW` with >= 1 day).
- [x] Step 3: Write tests in `backend/tests/test_applications.py` and verify with `pytest backend/tests/test_applications.py`.
- [x] Step 4: Update frontend types in `frontend/src/types/application.ts` and `frontend/src/lib/api.ts` with `offer_id` and `follow_up_alert`.
- [x] Step 5: Update `frontend/src/components/dashboard/NewApplicationModal.tsx` and `frontend/src/app/offers/[id]/page.tsx` to link applications directly with `offer_id`.
- [x] Step 6: Update `frontend/src/components/applications/ApplicationCard.tsx` and `ApplicationDetails.tsx` to render alert badges for cadences and a badge indicating offer origin.
- [x] Step 7: Run frontend typecheck (`npx --prefix frontend tsc --noEmit`) and production build (`npm --prefix frontend run build`).
- [x] Step 8 (teardown): Confirm 0 dead code, update plan to complete and record entry in daily log.

## Code Review
- Dead code removed: yes (no dead code created)
- Build status: pass (`next build` succeeded with exit code 0)
- Type errors: none (`npx tsc --noEmit` clean exit)
- Unintended side effects: none (existing applications remain backward-compatible)
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 10:25: Step 1 completed — Added `offer_id`, `days_since_application`, `follow_up_alert` to backend application models and added `OFFER_RECEIVED` to `ApplicationStatus`.
- 10:26: Step 2 completed — Implemented `enrich_application_with_cadences` in `backend/app/routers/applications.py` to compute days and trigger cadences J+7 / J+1.
- 10:26: Step 3 completed — Added unit and integration tests in `backend/tests/test_applications.py`, passed 100%.
- 10:27: Step 4 completed — Added `offer_id` and `follow_up_alert` to frontend types and API models.
- 10:27: Step 5 completed — Connected "Postuler" on `/offers/[id]` to `NewApplicationModal` with `offer_id` persistence.
- 10:28: Step 6 completed — Enriched `ApplicationCard.tsx` with cadence alert pills (`Relance J+7 due`, `Remerciement J+1`) and `ApplicationDetails.tsx` with a clickable link to the source offer.
- 10:29: Step 7 completed — Verified frontend typecheck (`npx tsc --noEmit` -> code 0) and production build (`npm run build` -> code 0).
- 10:30: Step 8 completed — Confirmed 0 dead code and completed execution log.

## Notes
- None.
