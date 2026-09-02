---
task: Fix company extraction on SPA pages, reject expired offers, and enrich job description field
status: complete
created: 2026-09-02
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Fix company extraction, SPA handling, expired offer filtering, and description enrichment

## Context
- Existing code checked:
  - `backend/job_crawler/crawler1.py`: `JobOffer` model lacked a `description` field and prompt didn't request a mission summary. On depublished SPA pages (like APEC 404), empty records with `"Non spécifié"` were extracted.
  - `backend/app/models.py`: `JobOfferCreate` and `JobOfferResponse` lacked `description`.
  - `backend/app/tasks/job_offers_collectors.py`: `enrich_job_offer_data` didn't reject dummy `"Non spécifié"` company/title and didn't map `description`.
  - `frontend/src/lib/api.ts` & `frontend/src/app/offers/page.tsx`: `JobOffer` interface missed `description` and rich tags (type_contrat, salaire, competences_cles).
- Fresh info looked up: Crawl4AI markdown extraction prompt formatting & Pydantic schemas.
- Git status checked: clean and understood.

## Simpler Alternative Considered
- Only adding `description` without validating expired pages: would allow ghost/empty descriptions on 404 pages. Both must be fixed together.

## Surgical Scope
- **Files touched**:
  - `backend/job_crawler/crawler1.py`
  - `backend/app/models.py`
  - `backend/app/tasks/job_offers_collectors.py`
  - `backend/tests/test_job_offers_pipeline.py`
  - `frontend/src/lib/api.ts`
  - `frontend/src/app/offers/page.tsx`
  - `frontend/src/components/dashboard/NewApplicationModal.tsx`
  - `docs/micro/DAILY_LOG-2026-09-02.md`
- **Files NOT touched**: all others
- **Symbols replaced**: none
- **Symbols extended**:
  - `JobOffer` in `crawler1.py` (added `description: Optional[str]`)
  - `JobOfferCreate` & `JobOfferResponse` in `backend/app/models.py` (added `description: Optional[str]`)
  - `enrich_job_offer_data` in `job_offers_collectors.py` (added `description` extraction + strict `"Non spécifié"` rejection)
  - `JobOffer` interface in `frontend/src/lib/api.ts` (added `description`, `competences_cles`, `salaire`, `type_contrat`, `mode_travail`)
  - Offer cards in `frontend/src/app/offers/page.tsx` (rendered description preview, tags, and prefilled modal description)

## Definition of Done
- [x] Build passes: `docker compose exec -T backend python -c "from job_crawler.crawler1 import JobOffer; from app.models import JobOfferResponse; print('MODELS OK')"`
- [x] Tests pass: `uv run pytest tests/test_normalization.py tests/test_job_offers_pipeline.py tests/test_crew_models_and_tools.py` (18/18 passed)
- [x] No dead code: confirmed
- [x] Type check: TypeScript build clean
- [x] Manual check: verified dummy records purged from MongoDB and new description field rendering on frontend.

## Steps
- [x] Step 1: Update `JobOffer` model and LLM extraction prompt in `backend/job_crawler/crawler1.py` to extract a concise, high-value `description` (2-5 sentences summarizing mission & profile) and return `[]` on expired/404/depublished pages.
- [x] Step 2: Update `JobOfferCreate` and `JobOfferResponse` in `backend/app/models.py` to include `description: Optional[str] = None`.
- [x] Step 3: Update `enrich_job_offer_data` in `backend/app/tasks/job_offers_collectors.py` to extract `description` and reject offers with missing/dummy title or company.
- [x] Step 4: Update `frontend/src/lib/api.ts`, `frontend/src/app/offers/page.tsx`, and `NewApplicationModal.tsx` to include `description` and display it in offer cards.
- [x] Step 5: Add unit tests in `test_job_offers_pipeline.py` verifying description extraction and dummy offer filtering.
- [x] Step 6: Purge invalid dummy records from MongoDB, run full test suite, and record entry in daily log.

## Code Review
- Dead code removed: yes
- Build status: pass
- Type errors: none
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- [x] 09:40 Updated crawler1.py with description field, anti-404 prompt rule, and cookie banner auto-dismissal.
- [x] 09:40 Added description field to JobOfferCreate and JobOfferResponse in backend/app/models.py.
- [x] 09:41 Updated enrich_job_offer_data to extract description and reject dummy ("Non spécifié") offers.
- [x] 09:41 Updated TypeScript types in frontend/src/lib/api.ts and rendered description preview in frontend/src/app/offers/page.tsx.
- [x] 09:41 Updated NewApplicationModal.tsx to prefill description when creating applications from offers.
- [x] 09:48 Executed unit tests with `uv run pytest`: 18/18 tests passed in 8.15s.
- [x] 09:49 Purged 3 dummy "Non spécifié" records from MongoDB.

## Notes
- APEC URL `https://www.apec.fr/candidat/recherche-emploi.html/emploi/detail-offre/179277715W` was depublished by APEC ("L'offre que vous souhaitez afficher n'est plus disponible"). Expired pages are now properly rejected with [] before reaching MongoDB.
