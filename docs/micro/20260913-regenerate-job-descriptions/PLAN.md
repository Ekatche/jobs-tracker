---
task: Implémenter le script et bouton de régénération des descriptions d'offres d'emploi avec traitement des liens morts
status: completed
created: 2026-09-13
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Regenerate Job Descriptions and Handle Dead Links

## Context
- Existing code checked:
  - `backend/job_crawler/crawler1.py`: `crawl_and_extract_jobs_optimized()` extracts 5-section Markdown descriptions and detects dead/expired links via `_is_dead_or_expired()`.
  - `backend/app/database.py`: `get_database()` provides MongoDB access.
  - `backend/app/routers/job_offers.py`: contains existing CRUD and actions (`soft-delete`, `get_job_offers`).
  - `frontend/src/lib/api.ts`: `jobOffersApi` object manages HTTP calls to `/job-offers/*`.
  - `frontend/src/app/offers/page.tsx`: `OfferCard` component renders job cards with `OfferCard({ offer })`.
- Problem solved:
  - 71 offers in MongoDB can now be regenerated on-demand or in batch.
  - When an offer link is dead/broken (404/expired), `is_active` is set to `False` and an informative fallback description is generated summarizing metadata rather than leaving a blank.
  - Both a CLI batch script and an on-demand UI button with spinner are provided.

## Simpler Alternative Considered
- A simple one-off migration script without API endpoint: rejected because user explicitly requested *"soit un script soit un bouton pour regenerer"* — having both the CLI script and the API/UI button covers batch automation and on-demand user actions in the dashboard with minimal extra code.

## Surgical Scope
- **Files touched**:
  - `backend/app/tasks/regenerate_descriptions.py` [NEW]
  - `backend/app/routers/job_offers.py` [MODIFY]
  - `backend/tests/test_regenerate_descriptions.py` [NEW]
  - `frontend/src/lib/api.ts` [MODIFY]
  - `frontend/src/app/offers/page.tsx` [MODIFY]
  - `docs/micro/20260913-regenerate-job-descriptions/PLAN.md` [NEW]
  - `docs/micro/DAILY_LOG-2026-09-13.md` [MODIFY]
- **Files NOT touched**: all others
- **Symbols replaced**: none
- **Symbols extended**:
  - `job_offers_router` in `backend/app/routers/job_offers.py` (added `POST /{offer_id}/regenerate-description`)
  - `jobOffersApi` in `frontend/src/lib/api.ts` (added `regenerateDescription`)
  - `OfferCard` in `frontend/src/app/offers/page.tsx` (added regenerate button with loading spinner, inactive badge, and empty description fallback button)

## Definition of Done
- [x] Build passes: `uv run --project backend python -c "from app.tasks.regenerate_descriptions import regenerate_single_offer; print('OK')"`
- [x] Tests pass: `docker compose exec -T backend pytest tests/test_normalization.py tests/test_job_offers_pipeline.py tests/test_regenerate_descriptions.py` (22 passed in 1.88s)
- [x] No dead code: confirmed
- [x] Type check: n/a
- [x] Manual check: verified single offer regeneration via API and CLI script on live MongoDB.

## Steps
- [x] Step 1: Create `backend/app/tasks/regenerate_descriptions.py` with `regenerate_single_offer()`, batch processing `batch_regenerate()`, and CLI arguments. Handle dead links by marking `is_active: false` and providing an informative fallback description.
- [x] Step 2: Add API endpoint `POST /job-offers/{offer_id}/regenerate-description` in `backend/app/routers/job_offers.py`.
- [x] Step 3: Write comprehensive unit/integration tests in `backend/tests/test_regenerate_descriptions.py` covering active links, dead/expired links (fallback + `is_active=False`), and error scenarios.
- [x] Step 4: Add `regenerateDescription` to `frontend/src/lib/api.ts` and interactive button with loading state in `OfferCard` (`frontend/src/app/offers/page.tsx`).
- [x] Step 5: Rebuild backend and frontend Docker containers, run tests inside Docker.
- [x] Step 6 (teardown): Run a sample regeneration via the CLI script to verify execution against live MongoDB.

## Code Review
- Dead code removed: yes
- Build status: passed (backend and frontend production images rebuilt, containers running)
- Type errors: none
- Unintended side effects: none
- Security surface touched: no
- Verdict: approved

## Execution Log
- [x] Step 1: Created `backend/app/tasks/regenerate_descriptions.py` with `regenerate_single_offer()`, `build_dead_link_fallback_description()`, `batch_regenerate()`, and CLI args. Verified with `uv run --project backend python -c "from app.tasks.regenerate_descriptions import regenerate_single_offer, build_dead_link_fallback_description; print('OK')"`.
- [x] Step 2: Added `POST /job-offers/{offer_id}/regenerate-description` in `backend/app/routers/job_offers.py`. Verified router import with `uv run --project backend python -c "from app.routers.job_offers import job_offers_router; print('ROUTER_OK')"`.
- [x] Step 3: Implemented 6 unit tests in `backend/tests/test_regenerate_descriptions.py`. Ran full suite: 22 passed in 6.01s (`uv run pytest tests/test_normalization.py tests/test_job_offers_pipeline.py tests/test_regenerate_descriptions.py`).
- [x] Step 4: Added `regenerateDescription` in `frontend/src/lib/api.ts`, extended `JobOffer` interface with `is_active`, added `handleRegenerateDescription` with spinner in `frontend/src/app/offers/page.tsx`, and inactive badge.
- [x] Step 5: Built Docker images (`backend` and `frontend`), recreated both containers, ran test suite inside Docker: 22 passed in 1.88s.
- [x] Step 6: Ran live regeneration CLI test on MongoDB offer `6aa39e8f2486633ff7120c11` (`python -m app.tasks.regenerate_descriptions --offer-id ...`) and tested API endpoint `POST /job-offers/{id}/regenerate-description` via curl. Verified successful 5-section Markdown extraction and MongoDB persistence.







## Notes
- Handling dead links:
  - When `status_code in (404, 410)` or `_is_dead_or_expired()` is True:
    `is_active` is set to `False`.
    `description` is set to:
    ```markdown
    • Statut : Cette offre n'est plus disponible (lien expiré ou annonce retirée).
    • Contexte archivé : Opportunité chez {entreprise} pour le poste de {poste}.
    • Compétences initiales : {competences_cles}
    ```
